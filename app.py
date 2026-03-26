"""
JL Fair Value - DCF Valuation Model
Professional tab-based layout for institutional-grade valuations
"""
import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict

# Import custom modules
from src.data.sec_parser import extract_financials
from src.data.fmp_api import fetch_all_company_data, map_fmp_to_dcf_format, FMPAPIError
from src.valuation.dcf_engine import dcf_model
from src.valuation.reverse_dcf import calculate_implied_metrics
from src.valuation.sensitivity import (
    generate_wacc_terminal_sensitivity,
    generate_exit_multiple_growth_sensitivity,
    generate_scenario_analysis
)
from src.utils.formatters import (
    format_millions, format_percentage, format_price, format_multiple,
    calculate_default_exit_multiple, create_historical_summary,
    create_projection_summary, create_ratios_summary
)

# Page configuration
st.set_page_config(
    page_title="JL Fair Value",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"  # Hide sidebar by default
)

# Custom CSS
st.markdown("""
<style>
    /* Hide sidebar */
    [data-testid="stSidebar"] {
        display: none;
    }
    
    /* Header styling */
    .company-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1.5rem 2rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    
    .company-name {
        font-size: 1.8rem;
        font-weight: 700;
        margin: 0;
    }
    
    .company-details {
        font-size: 0.95rem;
        opacity: 0.9;
        margin: 0.3rem 0 0 0;
    }
    
    .price-info {
        font-size: 1.3rem;
        font-weight: 600;
        margin-top: 0.5rem;
    }
    
    .price-change-positive {
        color: #10b981;
    }
    
    .price-change-negative {
        color: #ef4444;
    }
    
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
        background-color: #f8f9fa;
        padding: 0.5rem;
        border-radius: 0.5rem;
    }
    
    .stTabs [data-baseweb="tab"] {
        padding: 0.75rem 1.5rem;
        font-weight: 600;
        font-size: 1rem;
        color: #1f2937 !important;
        background-color: transparent;
    }
    
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background-color: white;
        color: #667eea !important;
        border-radius: 0.375rem;
    }
    
    /* Branding */
    .branding {
        font-size: 1.2rem;
        font-weight: 600;
        color: #667eea;
        margin-bottom: 1rem;
    }
    
    /* Compact spacing */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data
def parse_10k_file(file_content: bytes) -> Dict:
    """Cache the extraction of financial data from 10-K HTML"""
    html_content = file_content.decode('utf-8', errors='ignore')
    return extract_financials(html_content)


@st.cache_data(ttl=3600)
def fetch_api_data(ticker: str, api_key: str) -> Dict:
    """Fetch financial data from FMP API (cached for 1 hour)"""
    raw_data = fetch_all_company_data(ticker, api_key)
    return map_fmp_to_dcf_format(raw_data)


def render_company_header(profile: Dict, financials: Dict):
    """Render persistent company header"""
    
    # Extract data with proper fallbacks
    company_name = profile.get('companyName', 'Unknown Company')
    ticker = profile.get('symbol', 'N/A')
    exchange = profile.get('exchange', 'N/A')
    country = profile.get('country', 'US')  # Default to US
    sector = profile.get('sector', 'N/A')
    industry = profile.get('industry', 'N/A')
    price = profile.get('price', 0)
    change = profile.get('change', 0)
    change_pct = profile.get('changePercentage', 0)
    market_cap = profile.get('marketCap', 0)
    volume = profile.get('volume', 0)
    
    # Format market cap
    if market_cap >= 1_000_000_000_000:
        market_cap_str = f"${market_cap/1_000_000_000_000:.1f}T"
    elif market_cap >= 1_000_000_000:
        market_cap_str = f"${market_cap/1_000_000_000:.1f}B"
    elif market_cap > 0:
        market_cap_str = f"${market_cap/1_000_000:.1f}M"
    else:
        market_cap_str = "N/A"
    
    # Format volume
    if volume >= 1_000_000:
        volume_str = f"{volume/1_000_000:.0f}M"
    elif volume >= 1_000:
        volume_str = f"{volume/1_000:.0f}K"
    else:
        volume_str = f"{volume:,.0f}" if volume > 0 else "N/A"
    
    # Change color
    change_class = "price-change-positive" if change >= 0 else "price-change-negative"
    change_sign = "+" if change >= 0 else ""
    
    # Render header
    st.markdown(f"""
    <div class="company-header">
        <div class="company-name">{company_name} ({ticker})</div>
        <div class="company-details">
            {exchange} | {country} | {sector} - {industry}
        </div>
        <div class="price-info">
            ${price:.2f} 
            <span class="{change_class}">{change_sign}${change:.2f} ({change_sign}{change_pct:.2f}%)</span>
            &nbsp;&nbsp;|&nbsp;&nbsp;
            Mkt Cap: {market_cap_str}
            &nbsp;&nbsp;|&nbsp;&nbsp;
            Vol: {volume_str}
        </div>
    </div>
    """, unsafe_allow_html=True)


def main():
    # Branding
    st.markdown('<div class="branding">JL Fair Value</div>', unsafe_allow_html=True)
    
    # Ticker input - auto-fetches when changed
    ticker_input = st.text_input("Enter Ticker", value="NVDA", placeholder="Enter ticker symbol...")
    
    # Initialize session state
    if 'company_data' not in st.session_state:
        st.session_state.company_data = None
    if 'financials' not in st.session_state:
        st.session_state.financials = None
    if 'profile' not in st.session_state:
        st.session_state.profile = None
    if 'last_ticker' not in st.session_state:
        st.session_state.last_ticker = None
    
    # Auto-fetch when ticker changes
    if ticker_input and ticker_input.upper() != st.session_state.last_ticker:
        try:
            api_key = st.secrets["api_keys"]["fmp_api_key"]
            
            with st.spinner(f"Fetching data for {ticker_input}..."):
                # Fetch profile
                from src.data.fmp_api import fetch_company_profile
                profile = fetch_company_profile(ticker_input.upper(), api_key)
                
                # Fetch financials
                financials = fetch_api_data(ticker_input.upper(), api_key)
                
                # Store in session state
                st.session_state.profile = profile
                st.session_state.financials = financials
                st.session_state.company_data = {
                    'profile': profile,
                    'financials': financials
                }
                st.session_state.last_ticker = ticker_input.upper()
                
                st.success(f"Data loaded for {profile.get('companyName', ticker_input)}")
        
        except FMPAPIError as e:
            st.error(f"API Error: {str(e)}")
        except Exception as e:
            st.error(f"Error: {str(e)}")
    
    # If no data loaded, show instructions
    if st.session_state.company_data is None:
        st.info("👆 Enter a ticker symbol and click 'Fetch Data' to begin")
        
        st.markdown("### How It Works")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            1. Enter a stock ticker (e.g., NVDA, AAPL)
            2. Review historical financials
            3. Adjust valuation assumptions
            4. Analyze DCF results across scenarios
            """)
        with col2:
            st.markdown("""
            - Real-time market data from FMP API
            - Dual terminal value methods
            - Scenario and sensitivity analysis
            - Market-implied expectations
            """)
        return
    
    # Extract data from session state
    profile = st.session_state.profile
    financials = st.session_state.financials
    
    # Render company header
    render_company_header(profile, financials)
    
    # Initialize assumptions ONLY ONCE (check if already exists)
    if 'assumptions' not in st.session_state:
        ratios = financials['ratios']
        default_capex = float(ratios['capex_ratio']) if ratios['capex_ratio'] else 0.15
        default_exit = calculate_default_exit_multiple(
            ratios['ebit_margin'],
            ratios['revenue_cagr']
        )
        
        
        st.session_state.assumptions = {
            'base': {
                'revenue_growth': float(ratios['revenue_cagr']) if ratios['revenue_cagr'] else 0.10,
                'terminal_growth': 0.025,
                'ebit_margin_initial': float(ratios['ebit_margin']) if ratios['ebit_margin'] else 0.40,
                'ebit_margin_terminal': float(ratios['ebit_margin']) if ratios['ebit_margin'] else 0.40,
                'capex_initial': default_capex,
                'capex_terminal': max(0.10, default_capex - 0.03),
                'da_ratio': float(ratios['da_ratio']) if ratios['da_ratio'] else 0.05,
                'wc_ratio': float(ratios['wc_ratio']) if ratios['wc_ratio'] else 0.05,
                'tax_rate': float(ratios['tax_rate']) if ratios['tax_rate'] else 0.21,
                'wacc': 0.085,
                'exit_multiple': default_exit,
                'projection_years': 7
            }
        }
    
    # ALWAYS update Bear and Bull based on current Base values (runs every time page renders)
    base = st.session_state.assumptions['base']
    
    # Bear scenario - conservative
    st.session_state.assumptions['bear'] = {
        'revenue_growth': base['revenue_growth'] * 0.65,  # Wide dispersion for growth
        'terminal_growth': base['terminal_growth'] * 0.85,  # Tight range
        'ebit_margin_initial': base['ebit_margin_initial'] * 0.85,  # Tighter margin compression
        'ebit_margin_terminal': base['ebit_margin_terminal'] * 0.85,
        'capex_initial': base['capex_initial'] * 1.20,  # Higher reinvestment (less efficient)
        'capex_terminal': base['capex_terminal'] * 1.20,
        'da_ratio': base['da_ratio'] * 1.20,  # Higher D&A burden
        'wc_ratio': base['wc_ratio'] * 1.20,  # More working capital needed
        'tax_rate': base['tax_rate'],  # Keep same
        'wacc': base['wacc'] * 1.15,  # CRITICAL: Higher discount rate
        'exit_multiple': base['exit_multiple'] * 0.80,  # Lower exit valuation
        'projection_years': base['projection_years']  # Keep same
    }
    
    # Bull scenario - optimistic
    st.session_state.assumptions['bull'] = {
        'revenue_growth': base['revenue_growth'] * 1.25,  # Wide dispersion for growth
        'terminal_growth': base['terminal_growth'] * 1.15,  # Tight range
        'ebit_margin_initial': base['ebit_margin_initial'] * 1.10,  # Tighter margin expansion
        'ebit_margin_terminal': base['ebit_margin_terminal'] * 1.10,
        'capex_initial': base['capex_initial'] * 0.90,  # Lower reinvestment (more efficient)
        'capex_terminal': base['capex_terminal'] * 0.90,
        'da_ratio': base['da_ratio'] * 0.90,  # Lower D&A burden
        'wc_ratio': base['wc_ratio'] * 0.90,  # Less working capital needed
        'tax_rate': base['tax_rate'],  # Keep same
        'wacc': base['wacc'] * 0.90,  # CRITICAL: Lower discount rate
        'exit_multiple': base['exit_multiple'] * 1.20,  # Higher exit valuation
        'projection_years': base['projection_years']  # Keep same
    }
    
    # Run DCF for all 3 scenarios
    if 'dcf_results' not in st.session_state:
        st.session_state.dcf_results = {}
    
    # Show DCF calculation status
    dcf_errors = []
    
    for scenario_name in ['bear', 'base', 'bull']:
        # Map session state assumptions to dcf_model format
        scenario_assumptions = st.session_state.assumptions[scenario_name]
        dcf_assumptions = {
            'revenue_growth': scenario_assumptions['revenue_growth'],
            'ebit_margin': scenario_assumptions['ebit_margin_initial'],
            'ebit_margin_terminal': scenario_assumptions['ebit_margin_terminal'],
            'capex_ratio_initial': scenario_assumptions['capex_initial'],
            'capex_ratio_terminal': scenario_assumptions['capex_terminal'],
            'da_ratio': scenario_assumptions['da_ratio'],
            'tax_rate': scenario_assumptions['tax_rate'],
            'wc_ratio': scenario_assumptions['wc_ratio'],
            'wacc': scenario_assumptions['wacc'],
            'terminal_growth': scenario_assumptions['terminal_growth'],
            'projection_years': scenario_assumptions['projection_years'],
            'exit_multiple': scenario_assumptions['exit_multiple']
        }
        
        # Run DCF
        try:
            result = dcf_model(financials, dcf_assumptions, scenario_name)
            st.session_state.dcf_results[scenario_name] = result
        except Exception as e:
            error_msg = f"DCF {scenario_name}: {str(e)}"
            dcf_errors.append(error_msg)
            st.session_state.dcf_results[scenario_name] = None
    
    # Show errors if any
    if dcf_errors:
        st.error("DCF Calculation Errors:")
        for err in dcf_errors:
            st.write(f"- {err}")
    
    # Create tabs
    tabs = st.tabs([
        "Overview",
        "Dashboard",
        "Financials", 
        "Assumptions",
        "Growth Paths",
        "Forecast",
        "Gordon Growth",
        "Exit Multiple",
        "Price Drivers"
    ])
    
    # Tab 1: Overview
    with tabs[0]:
        st.markdown("### Company Overview")
        
        # Company basics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Price", f"${profile.get('price', 0):.2f}")
        with col2:
            market_cap = profile.get('marketCap', 0)
            st.metric("Market Cap", f"${market_cap/1e9:.1f}B")
        with col3:
            st.metric("Sector", profile.get('sector', 'N/A'))
        with col4:
            st.metric("Industry", profile.get('industry', 'N/A'))
        
        st.markdown("---")
        
        # Business Snapshot
        st.markdown("### Business Snapshot")
        st.caption("What size and earnings power is this business?")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            revenue_ttm = financials['Revenue'][0] if financials['Revenue'] else 0
            st.metric("Revenue (TTM)", f"${revenue_ttm/1e9:.1f}B")
        with col2:
            ebit_ttm = financials['EBIT'][0] if financials['EBIT'] else 0
            st.metric("EBIT (TTM)", f"${ebit_ttm/1e9:.1f}B")
        with col3:
            # Calculate FCF from most recent year
            if financials['Revenue'] and len(financials['Revenue']) > 0:
                latest_revenue = financials['Revenue'][0]
                latest_ebit = financials['EBIT'][0]
                latest_capex = financials['CAPEX'][0]
                latest_da = financials['Depreciation'][0]
                tax_rate = financials['ratios']['tax_rate']
                nopat = latest_ebit * (1 - tax_rate) if tax_rate else latest_ebit * 0.79
                fcf_ttm = nopat + latest_da + latest_capex  # CAPEX already negative
                st.metric("FCF (TTM)", f"${fcf_ttm/1e9:.1f}B")
            else:
                st.metric("FCF (TTM)", "N/A")
        
        st.markdown("---")
        
        # Growth
        st.markdown("### Growth")
        
        col1, col2 = st.columns(2)
        with col1:
            revenue_cagr = financials['ratios'].get('revenue_cagr', 0)
            st.metric("Revenue CAGR (3Y)", f"{revenue_cagr*100:.1f}%")
        with col2:
            # Most recent YoY growth
            if financials['Revenue'] and len(financials['Revenue']) >= 2:
                yoy_growth = (financials['Revenue'][0] / financials['Revenue'][1] - 1)
                st.metric("Most Recent YoY", f"{yoy_growth*100:.1f}%")
            else:
                st.metric("Most Recent YoY", "N/A")
        
        st.markdown("---")
        
        # Profitability
        st.markdown("### Profitability")
        
        col1, col2 = st.columns(2)
        with col1:
            ebit_margin = financials['ratios'].get('ebit_margin', 0)
            st.metric("EBIT Margin", f"{ebit_margin*100:.1f}%")
        with col2:
            # FCF Margin
            if financials['Revenue'] and 'fcf_ttm' in locals():
                fcf_margin = fcf_ttm / latest_revenue
                st.metric("FCF Margin", f"{fcf_margin*100:.1f}%")
            else:
                st.metric("FCF Margin", "N/A")
        
        st.markdown("---")
        
        # Capital & Risk
        st.markdown("### Capital & Risk")
        
        col1, col2 = st.columns(2)
        with col1:
            net_debt = financials['ratios'].get('net_debt', 0)
            if net_debt < 0:
                st.metric("Net Cash", f"${abs(net_debt)/1e9:.1f}B")
            else:
                st.metric("Net Debt", f"${net_debt/1e9:.1f}B")
        with col2:
            shares = financials['ratios'].get('shares_diluted', 0)
            st.metric("Shares Outstanding", f"{shares/1e9:.2f}B")
        
        st.markdown("---")
        
        # Reinvestment
        st.markdown("### Reinvestment")
        
        col1, col2 = st.columns(2)
        with col1:
            capex_ratio = financials['ratios'].get('capex_ratio', 0)
            st.metric("CAPEX % Revenue", f"{capex_ratio*100:.1f}%")
        with col2:
            da_ratio = financials['ratios'].get('da_ratio', 0)
            st.metric("D&A % Revenue", f"{da_ratio*100:.1f}%")
    
    # Tab 2: Dashboard
    with tabs[8]:
        # Get current price from profile
        current_price = profile.get('price', 178.68)
        
        # Extract DCF results
        dcf_results = st.session_state.get('dcf_results', {})
        
        # Gordon Growth Method
        st.markdown("**Gordon Growth Method**")
        col1, col2, col3 = st.columns(3)
        with col1:
            gordon_bear = dcf_results.get('bear', {}).get('price_per_share_gordon', 0) if dcf_results.get('bear') else 0
            gordon_bear_delta = ((gordon_bear - current_price) / current_price) * 100 if gordon_bear > 0 else 0
            st.metric("Bear", f"${gordon_bear:.0f}/share", f"{gordon_bear_delta:+.1f}%")
        with col2:
            gordon_base = dcf_results.get('base', {}).get('price_per_share_gordon', 0) if dcf_results.get('base') else 0
            gordon_base_delta = ((gordon_base - current_price) / current_price) * 100 if gordon_base > 0 else 0
            st.metric("Base", f"${gordon_base:.0f}/share", f"{gordon_base_delta:+.1f}%")
        with col3:
            gordon_bull = dcf_results.get('bull', {}).get('price_per_share_gordon', 0) if dcf_results.get('bull') else 0
            gordon_bull_delta = ((gordon_bull - current_price) / current_price) * 100 if gordon_bull > 0 else 0
            st.metric("Bull", f"${gordon_bull:.0f}/share", f"{gordon_bull_delta:+.1f}%")
        
        st.markdown("---")
        
        # Exit Multiple Method
        st.markdown("**Exit Multiple Method**")
        col1, col2, col3 = st.columns(3)
        with col1:
            exit_bear = dcf_results.get('bear', {}).get('price_per_share_exit', 0) if dcf_results.get('bear') else 0
            exit_bear_delta = ((exit_bear - current_price) / current_price) * 100 if exit_bear > 0 else 0
            st.metric("Bear", f"${exit_bear:.0f}/share", f"{exit_bear_delta:+.1f}%")
        with col2:
            exit_base = dcf_results.get('base', {}).get('price_per_share_exit', 0) if dcf_results.get('base') else 0
            exit_base_delta = ((exit_base - current_price) / current_price) * 100 if exit_base > 0 else 0
            st.metric("Base", f"${exit_base:.0f}/share", f"{exit_base_delta:+.1f}%")
        with col3:
            exit_bull = dcf_results.get('bull', {}).get('price_per_share_exit', 0) if dcf_results.get('bull') else 0
            exit_bull_delta = ((exit_bull - current_price) / current_price) * 100 if exit_bull > 0 else 0
            st.metric("Bull", f"${exit_bull:.0f}/share", f"{exit_bull_delta:+.1f}%")
        
        st.markdown("---")
        
        # Blended Average
        st.markdown("**Blended Average**")
        col1, col2, col3 = st.columns(3)
        with col1:
            bear_value = dcf_results.get('bear', {}).get('price_per_share_avg', 0) if dcf_results.get('bear') else 0
            bear_delta = ((bear_value - current_price) / current_price) * 100 if bear_value > 0 else 0
            st.metric("Bear", f"${bear_value:.0f}/share", f"{bear_delta:+.1f}%")
        with col2:
            base_value = dcf_results.get('base', {}).get('price_per_share_avg', 0) if dcf_results.get('base') else 0
            base_delta = ((base_value - current_price) / current_price) * 100 if base_value > 0 else 0
            st.metric("Base", f"${base_value:.0f}/share", f"{base_delta:+.1f}%")
        with col3:
            bull_value = dcf_results.get('bull', {}).get('price_per_share_avg', 0) if dcf_results.get('bull') else 0
            bull_delta = ((bull_value - current_price) / current_price) * 100 if bull_value > 0 else 0
            st.metric("Bull", f"${bull_value:.0f}/share", f"{bull_delta:+.1f}%")
    
    # Tab 3: Financials
    with tabs[8]:
        
        if financials is None:
            st.error("Financials data is None!")
            st.stop()
        
        try:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Historical Financials")
                st.caption("Reported performance across revenue, profitability, and cash flow")
                hist_df = create_historical_summary(financials)
                st.dataframe(hist_df, use_container_width=True, hide_index=True)
            
            with col2:
                st.subheader("Historical Averages")
                st.caption("Three-year average growth and margins to guide forward assumptions")
                ratios_df = create_ratios_summary(financials['ratios'])
                st.dataframe(ratios_df, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Error: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
    
    # Tab 4: Assumptions
    with tabs[8]:
        # Assumptions Summary Table
        st.markdown("### Current Assumptions")
        
        assumptions_data = []
        base = st.session_state.assumptions['base']
        bear = st.session_state.assumptions['bear']
        bull = st.session_state.assumptions['bull']
        
        assumptions_data = [
            {'Assumption': 'Revenue Growth', 'Bear': f"{bear['revenue_growth']*100:.1f}%", 'Base': f"{base['revenue_growth']*100:.1f}%", 'Bull': f"{bull['revenue_growth']*100:.1f}%"},
            {'Assumption': 'Terminal Growth', 'Bear': f"{bear['terminal_growth']*100:.1f}%", 'Base': f"{base['terminal_growth']*100:.1f}%", 'Bull': f"{bull['terminal_growth']*100:.1f}%"},
            {'Assumption': 'EBIT Margin (Init)', 'Bear': f"{bear['ebit_margin_initial']*100:.1f}%", 'Base': f"{base['ebit_margin_initial']*100:.1f}%", 'Bull': f"{bull['ebit_margin_initial']*100:.1f}%"},
            {'Assumption': 'EBIT Margin (Term)', 'Bear': f"{bear['ebit_margin_terminal']*100:.1f}%", 'Base': f"{base['ebit_margin_terminal']*100:.1f}%", 'Bull': f"{bull['ebit_margin_terminal']*100:.1f}%"},
            {'Assumption': 'CAPEX Initial', 'Bear': f"{bear['capex_initial']*100:.1f}%", 'Base': f"{base['capex_initial']*100:.1f}%", 'Bull': f"{bull['capex_initial']*100:.1f}%"},
            {'Assumption': 'CAPEX Terminal', 'Bear': f"{bear['capex_terminal']*100:.1f}%", 'Base': f"{base['capex_terminal']*100:.1f}%", 'Bull': f"{bull['capex_terminal']*100:.1f}%"},
            {'Assumption': 'Tax Rate', 'Bear': f"{bear['tax_rate']*100:.1f}%", 'Base': f"{base['tax_rate']*100:.1f}%", 'Bull': f"{bull['tax_rate']*100:.1f}%"},
            {'Assumption': 'WACC', 'Bear': f"{bear['wacc']*100:.1f}%", 'Base': f"{base['wacc']*100:.1f}%", 'Bull': f"{bull['wacc']*100:.1f}%"},
            {'Assumption': 'Exit Multiple', 'Bear': f"{bear['exit_multiple']:.1f}x", 'Base': f"{base['exit_multiple']:.1f}x", 'Bull': f"{bull['exit_multiple']:.1f}x"},
        ]
        
        summary_df = pd.DataFrame(assumptions_data)
        st.dataframe(summary_df, hide_index=True, use_container_width=True)
        
        st.markdown("---")
        
        # Editable Base Assumptions - Header with button inline
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown("### Edit Base Case Assumptions")
        with col2:
            if st.button("Update Assumptions", type="primary", use_container_width=True, key="update_btn"):
                st.session_state.valuation_ready = True
        
        st.caption("Adjust the sliders below. Bear and Bull scenarios use multipliers of Base values.")
        
        # Extract current values from session state
        ratios = financials['ratios']
        
        st.markdown("#### Revenue & Margins")
        
        col1, col2 = st.columns(2)
        
        with col1:
            revenue_growth_pct = st.slider(
                "Revenue Growth (Initial)",
                min_value=-10.0,
                max_value=100.0,
                value=min(st.session_state.assumptions['base']['revenue_growth'] * 100, 100.0),
                step=0.5,
                format="%.1f%%",
                help="Initial revenue growth rate",
                key="rev_growth"
            )
            st.session_state.assumptions['base']['revenue_growth'] = revenue_growth_pct / 100
            
            ebit_margin_pct = st.slider(
                "EBIT Margin (Initial)",
                min_value=0.0,
                max_value=100.0,
                value=st.session_state.assumptions['base']['ebit_margin_initial'] * 100,
                step=0.5,
                format="%.1f%%",
                help="Starting EBIT margin",
                key="ebit_init"
            )
            st.session_state.assumptions['base']['ebit_margin_initial'] = ebit_margin_pct / 100
        
        with col2:
            terminal_growth_pct = st.slider(
                "Terminal Growth",
                min_value=0.0,
                max_value=4.0,
                value=st.session_state.assumptions['base']['terminal_growth'] * 100,
                step=0.1,
                format="%.1f%%",
                help="Perpetual growth rate",
                key="term_growth"
            )
            st.session_state.assumptions['base']['terminal_growth'] = terminal_growth_pct / 100
            
            ebit_margin_terminal_pct = st.slider(
                "EBIT Margin (Terminal)",
                min_value=0.0,
                max_value=100.0,
                value=st.session_state.assumptions['base']['ebit_margin_terminal'] * 100,
                step=0.5,
                format="%.1f%%",
                help="Long-term EBIT margin",
                key="ebit_term"
            )
            st.session_state.assumptions['base']['ebit_margin_terminal'] = ebit_margin_terminal_pct / 100
        
        st.markdown("---")
        st.markdown("#### CAPEX & Working Capital")
        
        col1, col2 = st.columns(2)
        
        with col1:
            capex_initial_pct = st.slider(
                "CAPEX Initial %",
                min_value=0.0,
                max_value=40.0,
                value=st.session_state.assumptions['base']['capex_initial'] * 100,
                step=0.5,
                format="%.1f%%",
                help="Initial CAPEX as % of revenue",
                key="capex_init"
            )
            st.session_state.assumptions['base']['capex_initial'] = capex_initial_pct / 100
            
            da_ratio_pct = st.slider(
                "D&A % Revenue",
                min_value=1.0,
                max_value=40.0,
                value=st.session_state.assumptions['base']['da_ratio'] * 100,
                step=0.5,
                format="%.1f%%",
                help="Depreciation & Amortization as % of revenue",
                key="da_ratio"
            )
            st.session_state.assumptions['base']['da_ratio'] = da_ratio_pct / 100
        
        with col2:
            capex_terminal_pct = st.slider(
                "CAPEX Terminal %",
                min_value=0.0,
                max_value=40.0,
                value=st.session_state.assumptions['base']['capex_terminal'] * 100,
                step=0.5,
                format="%.1f%%",
                help="Terminal CAPEX as % of revenue",
                key="capex_term"
            )
            st.session_state.assumptions['base']['capex_terminal'] = capex_terminal_pct / 100
            
            wc_ratio_pct = st.slider(
                "Working Capital Ratio",
                min_value=-10.0,
                max_value=50.0,
                value=st.session_state.assumptions['base']['wc_ratio'] * 100,
                step=0.5,
                format="%.1f%%",
                help="Change in NWC as % of revenue change",
                key="wc_ratio"
            )
            st.session_state.assumptions['base']['wc_ratio'] = wc_ratio_pct / 100
        
        st.markdown("---")
        st.markdown("#### Tax & Discount Rate")
        
        col1, col2 = st.columns(2)
        
        with col1:
            tax_rate_pct = st.slider(
                "Tax Rate",
                min_value=1.0,
                max_value=40.0,
                value=st.session_state.assumptions['base']['tax_rate'] * 100,
                step=0.5,
                format="%.1f%%",
                help="Effective tax rate",
                key="tax_rate"
            )
            st.session_state.assumptions['base']['tax_rate'] = tax_rate_pct / 100
        
        with col2:
            wacc_pct = st.slider(
                "WACC",
                min_value=5.0,
                max_value=15.0,
                value=st.session_state.assumptions['base']['wacc'] * 100,
                step=0.1,
                format="%.1f%%",
                help="Weighted Average Cost of Capital",
                key="wacc"
            )
            st.session_state.assumptions['base']['wacc'] = wacc_pct / 100
        
        st.markdown("---")
        st.markdown("#### Exit Multiple & Projection Period")
        
        col1, col2 = st.columns(2)
        
        with col1:
            exit_multiple = st.slider(
                "Exit Multiple (EBIT)",
                min_value=0.0,
                max_value=40.0,
                value=st.session_state.assumptions['base']['exit_multiple'],
                step=0.5,
                format="%.1fx",
                help="Exit multiple for terminal value",
                key="exit_mult"
            )
            st.session_state.assumptions['base']['exit_multiple'] = exit_multiple
        
        with col2:
            projection_years = st.slider(
                "Projection Years",
                min_value=5,
                max_value=10,
                value=st.session_state.assumptions['base']['projection_years'],
                step=1,
                help="Number of years to project",
                key="proj_years"
            )
            st.session_state.assumptions['base']['projection_years'] = projection_years
        
        st.markdown("---")
    
    # Tab 5: Growth Paths
    with tabs[8]:
        # Get base assumptions
        base_assumptions = st.session_state.assumptions['base']
        
        # Import path calculation functions
        from src.valuation.dcf_engine import (
            calculate_growth_path_with_plateau,
            calculate_ebit_margin_path,
            calculate_capex_path
        )
        
        # Calculate paths based on current assumptions
        projection_years = int(base_assumptions['projection_years'])
        
        revenue_path = calculate_growth_path_with_plateau(
            base_assumptions['revenue_growth'],
            base_assumptions['terminal_growth'],
            projection_years
        )
        
        ebit_margin_path = calculate_ebit_margin_path(
            base_assumptions['ebit_margin_initial'],
            base_assumptions['ebit_margin_terminal'],
            projection_years
        )
        
        capex_path = calculate_capex_path(
            base_assumptions['capex_initial'],
            base_assumptions['capex_terminal'],
            projection_years
        )
        
        # Create combined table
        years = list(range(1, projection_years + 1))
        
        path_data = {
            'Year': years,
            'Revenue Growth': [f"{round(r * 100 * 2) / 2:.1f}%" for r in revenue_path],
            'EBIT Margin': [f"{round(m * 100 * 2) / 2:.1f}%" for m in ebit_margin_path],
            'CAPEX % Revenue': [f"{round(c * 100 * 2) / 2:.1f}%" for c in capex_path]
        }
        
        path_df = pd.DataFrame(path_data)
        
        st.subheader("Base Case Assumption Paths")
        st.caption("How base case assumptions transition from initial to terminal values over the projection period")
        st.dataframe(path_df, use_container_width=True, hide_index=True)
    
    # Tab 6: Forecast
    with tabs[8]:
        st.subheader("Base Case Financial Projections")
        st.caption("Forecasted revenue, EBIT, and free cash flow over the projection period")
        
        # Get base case DCF results
        base_dcf = st.session_state.dcf_results.get('base')
        
        if base_dcf and base_dcf.get('projection'):
            projection = base_dcf['projection']
            
            # Build forecast table
            forecast_data = []
            for p in projection:
                forecast_data.append({
                    'Year': int(p['Year']),
                    'Revenue Growth': f"{p['Growth']*100:.1f}%",
                    'Revenue': f"${p['Revenue']/1e9:.1f}B",
                    'EBIT Margin': f"{p['EBIT_Margin']*100:.1f}%",
                    'EBIT': f"${p['EBIT']/1e9:.1f}B",
                    'NOPAT': f"${p['NOPAT']/1e9:.1f}B",
                    'D&A': f"${p['D&A']/1e9:.1f}B",
                    'CAPEX': f"${p['CAPEX']/1e9:.1f}B",
                    'ΔWC': f"${p['ΔWC']/1e9:.1f}B",
                    'FCF': f"${p['FCF']/1e9:.1f}B",
                    'PV(FCF)': f"${p['PV']/1e9:.1f}B"
                })
            
            forecast_df = pd.DataFrame(forecast_data)
            st.dataframe(forecast_df, use_container_width=True, hide_index=True)
            
            # Summary metrics
            st.markdown("---")
            col1, col2, col3 = st.columns(3)
            with col1:
                total_pv_fcf = base_dcf.get('sum_pv_fcf', 0)
                st.metric("Sum of PV(FCF)", f"${total_pv_fcf/1e9:.1f}B")
            with col2:
                final_fcf = projection[-1]['FCF']
                st.metric("Final Year FCF", f"${final_fcf/1e9:.1f}B")
            with col3:
                final_revenue = projection[-1]['Revenue']
                st.metric("Final Year Revenue", f"${final_revenue/1e9:.1f}B")
        else:
            st.warning("No forecast data available. DCF calculation may have failed.")
    
    # Tab 7: Gordon Growth
    with tabs[8]:
        st.subheader("Gordon Growth (Perpetuity) Method")
        st.caption("Terminal value calculated using perpetual growth formula")
        
        # Get all scenario results
        bear_dcf = st.session_state.dcf_results.get('bear')
        base_dcf = st.session_state.dcf_results.get('base')
        bull_dcf = st.session_state.dcf_results.get('bull')
        
        if base_dcf:
            # Fair Value Across Scenarios
            st.markdown("#### Fair Value Per Share")
            
            col1, col2, col3 = st.columns(3)
            current_price = profile.get('price', 0)
            
            with col1:
                bear_price = bear_dcf.get('price_per_share_gordon', 0) if bear_dcf else 0
                bear_delta = ((bear_price - current_price) / current_price * 100) if current_price > 0 else 0
                st.metric("Bear", f"${bear_price:.2f}", f"{bear_delta:+.1f}%")
            
            with col2:
                base_price = base_dcf.get('price_per_share_gordon', 0)
                base_delta = ((base_price - current_price) / current_price * 100) if current_price > 0 else 0
                st.metric("Base", f"${base_price:.2f}", f"{base_delta:+.1f}%")
            
            with col3:
                bull_price = bull_dcf.get('price_per_share_gordon', 0) if bull_dcf else 0
                bull_delta = ((bull_price - current_price) / current_price * 100) if current_price > 0 else 0
                st.metric("Bull", f"${bull_price:.2f}", f"{bull_delta:+.1f}%")
            
            st.markdown("---")
            
            # Base Case Drivers
            st.markdown("##### Base Case Drivers")
            base_assumptions = st.session_state.assumptions['base']
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Revenue Growth", f"{base_assumptions['revenue_growth']*100:.1f}%")
            with col2:
                st.metric("Terminal Growth", f"{base_assumptions['terminal_growth']*100:.1f}%")
            with col3:
                st.metric("EBIT Margin (Term)", f"{base_assumptions['ebit_margin_terminal']*100:.1f}%")
            with col4:
                st.metric("WACC", f"{base_assumptions['wacc']*100:.1f}%")
            
            st.markdown("---")
            
            # Sensitivity Analysis
            st.markdown("#### Sensitivity Analysis")
            st.caption("Fair value at different WACC and Terminal Growth combinations (Base case)")
            
            # Get base case values
            base_assumptions = st.session_state.assumptions['base']
            base_wacc = base_assumptions['wacc']
            base_term_growth = base_assumptions['terminal_growth']
            
            # Define tight ranges around base
            # WACC: ±1.5% total range, 0.5% steps
            wacc_range = [
                base_wacc - 0.015,
                base_wacc - 0.010,
                base_wacc - 0.005,
                base_wacc,
                base_wacc + 0.005,
                base_wacc + 0.010,
                base_wacc + 0.015
            ]
            
            # Terminal Growth: ±1.0% total range, 0.25% steps
            term_growth_range = [
                base_term_growth - 0.010,
                base_term_growth - 0.0075,
                base_term_growth - 0.005,
                base_term_growth - 0.0025,
                base_term_growth,
                base_term_growth + 0.0025,
                base_term_growth + 0.005
            ]
            
            # Build sensitivity table
            sensitivity_data = []
            for wacc in wacc_range:
                row = {'WACC': f"{wacc*100:.1f}%"}
                for tg in term_growth_range:
                    # Ensure terminal growth stays below WACC (Gordon Growth constraint)
                    if tg >= wacc:
                        row[f"{tg*100:.2f}%"] = "N/A"
                        continue
                    
                    # Create temp assumptions
                    temp_assumptions = base_assumptions.copy()
                    temp_assumptions['wacc'] = wacc
                    temp_assumptions['terminal_growth'] = tg
                    
                    # Map to DCF format
                    dcf_temp = {
                        'revenue_growth': temp_assumptions['revenue_growth'],
                        'ebit_margin': temp_assumptions['ebit_margin_initial'],
                        'ebit_margin_terminal': temp_assumptions['ebit_margin_terminal'],
                        'capex_ratio_initial': temp_assumptions['capex_initial'],
                        'capex_ratio_terminal': temp_assumptions['capex_terminal'],
                        'da_ratio': temp_assumptions['da_ratio'],
                        'tax_rate': temp_assumptions['tax_rate'],
                        'wc_ratio': temp_assumptions['wc_ratio'],
                        'wacc': wacc,
                        'terminal_growth': tg,
                        'projection_years': temp_assumptions['projection_years'],
                        'exit_multiple': temp_assumptions['exit_multiple']
                    }
                    
                    try:
                        result = dcf_model(financials, dcf_temp, 'sensitivity')
                        price = result.get('price_per_share_gordon', 0)
                        row[f"{tg*100:.2f}%"] = f"${price:.0f}"
                    except:
                        row[f"{tg*100:.2f}%"] = "N/A"
                
                sensitivity_data.append(row)
            
            sens_df = pd.DataFrame(sensitivity_data)
            st.dataframe(sens_df, use_container_width=True, hide_index=True)
        else:
            st.warning("No Gordon Growth data available. DCF calculation may have failed.")
    
    # Tab 8: Exit Multiple
    with tabs[8]:
        st.subheader("Exit Multiple Method")
        st.caption("Terminal value calculated using exit EBIT multiple")
        
        # Get all scenario results
        bear_dcf = st.session_state.dcf_results.get('bear')
        base_dcf = st.session_state.dcf_results.get('base')
        bull_dcf = st.session_state.dcf_results.get('bull')
        
        if base_dcf:
            # Fair Value Across Scenarios
            st.markdown("#### Fair Value Per Share")
            
            col1, col2, col3 = st.columns(3)
            current_price = profile.get('price', 0)
            
            with col1:
                bear_price = bear_dcf.get('price_per_share_exit', 0) if bear_dcf else 0
                bear_delta = ((bear_price - current_price) / current_price * 100) if current_price > 0 else 0
                st.metric("Bear", f"${bear_price:.2f}", f"{bear_delta:+.1f}%")
            
            with col2:
                base_price = base_dcf.get('price_per_share_exit', 0)
                base_delta = ((base_price - current_price) / current_price * 100) if current_price > 0 else 0
                st.metric("Base", f"${base_price:.2f}", f"{base_delta:+.1f}%")
            
            with col3:
                bull_price = bull_dcf.get('price_per_share_exit', 0) if bull_dcf else 0
                bull_delta = ((bull_price - current_price) / current_price * 100) if current_price > 0 else 0
                st.metric("Bull", f"${bull_price:.2f}", f"{bull_delta:+.1f}%")
            
            st.markdown("---")
            
            # Base Case Drivers
            st.markdown("##### Base Case Drivers")
            base_assumptions = st.session_state.assumptions['base']
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Revenue Growth", f"{base_assumptions['revenue_growth']*100:.1f}%")
            with col2:
                st.metric("EBIT Margin (Term)", f"{base_assumptions['ebit_margin_terminal']*100:.1f}%")
            with col3:
                st.metric("WACC", f"{base_assumptions['wacc']*100:.1f}%")
            with col4:
                st.metric("Exit Multiple", f"{base_assumptions['exit_multiple']:.1f}x")
            
            st.markdown("---")
            
            # Sensitivity Analysis
            st.markdown("#### Sensitivity Analysis")
            st.caption("Fair value at different WACC and Exit Multiple combinations (Base case)")
            
            # Get base case values
            base_assumptions = st.session_state.assumptions['base']
            base_wacc = base_assumptions['wacc']
            base_exit_mult = base_assumptions['exit_multiple']
            
            # Define ranges around base
            # WACC: ±1.5% total range, 0.5% steps (same as Gordon Growth)
            wacc_range = [
                base_wacc - 0.015,
                base_wacc - 0.010,
                base_wacc - 0.005,
                base_wacc,
                base_wacc + 0.005,
                base_wacc + 0.010,
                base_wacc + 0.015
            ]
            
            # Exit Multiple: ±20-25% range, 2x increments
            exit_mult_range = [
                base_exit_mult - 6,
                base_exit_mult - 4,
                base_exit_mult - 2,
                base_exit_mult,
                base_exit_mult + 2,
                base_exit_mult + 4,
                base_exit_mult + 6
            ]
            
            # Build sensitivity table
            sensitivity_data = []
            for wacc in wacc_range:
                row = {'WACC': f"{wacc*100:.1f}%"}
                for em in exit_mult_range:
                    # Create temp assumptions
                    temp_assumptions = base_assumptions.copy()
                    temp_assumptions['wacc'] = wacc
                    temp_assumptions['exit_multiple'] = em
                    
                    # Map to DCF format
                    dcf_temp = {
                        'revenue_growth': temp_assumptions['revenue_growth'],
                        'ebit_margin': temp_assumptions['ebit_margin_initial'],
                        'ebit_margin_terminal': temp_assumptions['ebit_margin_terminal'],
                        'capex_ratio_initial': temp_assumptions['capex_initial'],
                        'capex_ratio_terminal': temp_assumptions['capex_terminal'],
                        'da_ratio': temp_assumptions['da_ratio'],
                        'tax_rate': temp_assumptions['tax_rate'],
                        'wc_ratio': temp_assumptions['wc_ratio'],
                        'wacc': wacc,
                        'terminal_growth': temp_assumptions['terminal_growth'],
                        'projection_years': temp_assumptions['projection_years'],
                        'exit_multiple': em
                    }
                    
                    try:
                        result = dcf_model(financials, dcf_temp, 'sensitivity')
                        price = result.get('price_per_share_exit', 0)
                        row[f"{em:.0f}x"] = f"${price:.0f}"
                    except:
                        row[f"{em:.0f}x"] = "N/A"
                
                sensitivity_data.append(row)
            
            sens_df = pd.DataFrame(sensitivity_data)
            st.dataframe(sens_df, use_container_width=True, hide_index=True)
        else:
            st.warning("No Exit Multiple data available. DCF calculation may have failed.")
    
    # Tab 9: Price Drivers
    with tabs[8]:
        st.subheader("What Does the Current Price Assume?")
        st.caption("Reverse DCF showing what would need to be true for today's price to make sense based on your inputs.")
        
        # Get current market price
        current_price = profile.get('price', 0)
        base_assumptions = st.session_state.assumptions['base']
        
        if current_price > 0:
            st.markdown(f"**Current Price:** ${current_price:.2f} per share")
            st.markdown("---")
            
            # Helper function to find implied value
            def find_implied_value(param_name, min_val, max_val, target_price, assumptions_template):
                """Binary search to find parameter value that gets us to target price"""
                tolerance = 0.5  # $0.50 tolerance
                max_iterations = 50
                
                for _ in range(max_iterations):
                    mid_val = (min_val + max_val) / 2
                    
                    # Create temp assumptions
                    temp_assumptions = assumptions_template.copy()
                    temp_assumptions[param_name] = mid_val
                    
                    # Map to DCF format
                    dcf_temp = {
                        'revenue_growth': temp_assumptions['revenue_growth'],
                        'ebit_margin': temp_assumptions['ebit_margin_initial'],
                        'ebit_margin_terminal': temp_assumptions['ebit_margin_terminal'],
                        'capex_ratio_initial': temp_assumptions['capex_initial'],
                        'capex_ratio_terminal': temp_assumptions['capex_terminal'],
                        'da_ratio': temp_assumptions['da_ratio'],
                        'tax_rate': temp_assumptions['tax_rate'],
                        'wc_ratio': temp_assumptions['wc_ratio'],
                        'wacc': temp_assumptions['wacc'],
                        'terminal_growth': temp_assumptions['terminal_growth'],
                        'projection_years': temp_assumptions['projection_years'],
                        'exit_multiple': temp_assumptions['exit_multiple']
                    }
                    
                    try:
                        result = dcf_model(financials, dcf_temp, 'implied')
                        # Use blended average
                        calculated_price = result.get('price_per_share_avg', 0)
                        
                        if abs(calculated_price - target_price) < tolerance:
                            return mid_val
                        
                        if calculated_price < target_price:
                            min_val = mid_val
                        else:
                            max_val = mid_val
                    except:
                        return None
                
                return mid_val
            
            # BLOCK 1: If valuation assumptions hold
            st.markdown("### If valuation assumptions hold")
            
            with st.spinner("Calculating required revenue growth..."):
                required_rev_growth = find_implied_value(
                    'revenue_growth',
                    -0.10,  # -10%
                    2.0,    # 200%
                    current_price,
                    base_assumptions.copy()
                )
            
            if required_rev_growth is not None:
                # Display required value prominently
                st.metric("Revenue Growth Required", f"{required_rev_growth*100:.1f}%", 
                         label_visibility="visible")
                
                st.caption("Based on your current assumptions for margins, reinvestment, discount rate, and exit multiple.")
                
                # Show key assumptions in table
                assumptions_data = [
                    {'Assumption': 'Exit Multiple', 'Value': f"{base_assumptions['exit_multiple']:.1f}x"},
                    {'Assumption': 'WACC', 'Value': f"{base_assumptions['wacc']*100:.1f}%"},
                    {'Assumption': 'Terminal EBIT Margin', 'Value': f"{base_assumptions['ebit_margin_terminal']*100:.1f}%"},
                    {'Assumption': 'Terminal Growth', 'Value': f"{base_assumptions['terminal_growth']*100:.1f}%"}
                ]
                assumptions_df = pd.DataFrame(assumptions_data)
                st.dataframe(assumptions_df, use_container_width=True, hide_index=True)
            else:
                st.warning("Unable to solve for required revenue growth within reasonable range.")
            
            st.markdown("---")
            
            # BLOCK 2: If operating assumptions hold
            st.markdown("### If operating assumptions hold")
            
            with st.spinner("Calculating required exit multiple..."):
                required_exit_mult = find_implied_value(
                    'exit_multiple',
                    5,
                    50,
                    current_price,
                    base_assumptions.copy()
                )
            
            if required_exit_mult is not None:
                # Display required value prominently
                st.metric("Exit Multiple Required", f"{required_exit_mult:.1f}x",
                         label_visibility="visible")
                
                st.caption("Based on your current assumptions for growth, margins, reinvestment, and discount rate.")
                
                # Show key assumptions in table
                assumptions_data = [
                    {'Assumption': 'Revenue Growth', 'Value': f"{base_assumptions['revenue_growth']*100:.1f}%"},
                    {'Assumption': 'WACC', 'Value': f"{base_assumptions['wacc']*100:.1f}%"},
                    {'Assumption': 'Terminal EBIT Margin', 'Value': f"{base_assumptions['ebit_margin_terminal']*100:.1f}%"},
                    {'Assumption': 'Terminal Growth', 'Value': f"{base_assumptions['terminal_growth']*100:.1f}%"}
                ]
                assumptions_df = pd.DataFrame(assumptions_data)
                st.dataframe(assumptions_df, use_container_width=True, hide_index=True)
            else:
                st.warning("Unable to solve for required exit multiple within reasonable range.")
        else:
            st.warning("No current price available to calculate required assumptions.")


if __name__ == "__main__":
    main()
