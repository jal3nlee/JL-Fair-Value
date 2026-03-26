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
        padding: 0.5rem 1rem;
        font-weight: 500;
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
    
    # Extract data
    company_name = profile.get('companyName', 'Unknown Company')
    ticker = profile.get('symbol', 'N/A')
    exchange = profile.get('exchange', 'N/A')
    country = profile.get('country', 'N/A')
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
    else:
        market_cap_str = f"${market_cap/1_000_000:.1f}M"
    
    # Format volume
    if volume >= 1_000_000:
        volume_str = f"{volume/1_000_000:.0f}M"
    else:
        volume_str = f"{volume/1_000:.0f}K"
    
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
    
    # Ticker input (temporary - will move to proper search later)
    col1, col2, col3 = st.columns([3, 1, 8])
    with col1:
        ticker_input = st.text_input("Enter Ticker", value="NVDA", label_visibility="collapsed", placeholder="Enter ticker or company...")
    with col2:
        fetch_button = st.button("Fetch Data", type="primary", use_container_width=True)
    
    # Initialize session state
    if 'company_data' not in st.session_state:
        st.session_state.company_data = None
    if 'financials' not in st.session_state:
        st.session_state.financials = None
    if 'profile' not in st.session_state:
        st.session_state.profile = None
    
    # Fetch data
    if fetch_button and ticker_input:
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
                
                st.success(f"✓ Data loaded for {profile.get('companyName', ticker_input)}")
        
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
    
    # Create tabs
    tabs = st.tabs([
        "Dashboard",
        "Financials", 
        "Assumptions",
        "Growth Paths",
        "Forecast",
        "Gordon Growth",
        "Exit Multiple",
        "Implied"
    ])
    
    # Tab 1: Dashboard
    with tabs[0]:
        st.header("Dashboard")
        st.markdown("**Summary of all valuation scenarios**")
        
        # Placeholder for now
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Bear Case", "$197/share", delta="-52%", delta_color="inverse")
        with col2:
            st.metric("Base Case", "$422/share", delta="Reference")
        with col3:
            st.metric("Bull Case", "$697/share", delta="+65%")
        
        st.markdown("---")
        st.markdown("*Dashboard will show summary of key assumptions and results*")
    
    # Tab 2: Financials
    with tabs[1]:
        st.header("Financials")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Reported Financials")
            hist_df = create_historical_summary(financials)
            st.dataframe(hist_df, use_container_width=True, hide_index=True)
        
        with col2:
            st.subheader("Derived Metrics")
            ratios_df = create_ratios_summary(financials['ratios'])
            st.dataframe(ratios_df, use_container_width=True, hide_index=True)
    
    # Tab 3: Assumptions
    with tabs[2]:
        st.header("Assumptions")
        st.markdown("**Adjust model inputs (sliders will be added here)**")
        
        # Scenario selector
        scenario = st.radio("Scenario:", ["Bear", "Base", "Bull"], index=1, horizontal=True)
        
        st.markdown("---")
        st.markdown("*All input sliders will be migrated to this tab*")
    
    # Tab 4: Growth Paths
    with tabs[3]:
        st.header("Growth Paths")
        st.markdown("*Charts showing how assumptions translate over projection period*")
    
    # Tab 5: Forecast
    with tabs[4]:
        st.header("Forecast")
        st.markdown("*Projected revenue and free cash flow tables*")
    
    # Tab 6: Gordon Growth
    with tabs[5]:
        st.header("Gordon Growth Method")
        st.markdown("*Perpetuity valuation results and sensitivity analysis*")
    
    # Tab 7: Exit Multiple
    with tabs[6]:
        st.header("Exit Multiple Method")
        st.markdown("*Exit multiple valuation results and sensitivity analysis*")
    
    # Tab 8: Implied
    with tabs[7]:
        st.header("Implied Market Expectations")
        st.markdown("*Reverse DCF analysis showing what the market is pricing in*")


if __name__ == "__main__":
    main()
