"""
JL Fair Value - DCF Valuation Model
Build a discounted cash flow model to estimate intrinsic value using multiple valuation methods
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
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1f77b4;
        margin-bottom: 0.3rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #666;
        margin-bottom: 1rem;
    }
    .cta-strip {
        background-color: #1f77b4;
        color: white;
        padding: 0.8rem 1.5rem;
        border-radius: 0.5rem;
        text-align: center;
        font-size: 1.1rem;
        font-weight: 600;
        margin: 1rem 0;
    }
    .quick-steps {
        display: flex;
        justify-content: space-around;
        margin: 1.5rem 0 2rem 0;
        padding: 0;
    }
    .quick-steps div {
        text-align: center;
        flex: 1;
        padding: 0 1rem;
    }
    .quick-steps-text {
        font-size: 0.95rem;
        color: #333;
        font-weight: 500;
    }
    .section-header {
        margin-top: 1.5rem;
        margin-bottom: 0.8rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .stDataFrame {
        font-size: 0.9rem;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem;
    }
    .blue-divider {
        width: 100%;
        height: 3px;
        background: linear-gradient(90deg, #1f77b4 0%, #4a9fd8 100%);
        margin: 2rem 0 1rem 0;
    }
    .divider-text {
        text-align: center;
        color: #1f77b4;
        font-weight: 600;
        font-size: 1rem;
        margin-bottom: 2rem;
    }
    /* Tighter spacing for non-data sections */
    .element-container {
        margin-bottom: 0.5rem;
    }
    /* Preserve breathing room for data */
    div[data-testid="stDataFrame"],
    div[data-testid="stMetric"] {
        margin-top: 1rem;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data
def parse_10k_file(file_content: bytes) -> Dict:
    """Cache the extraction of financial data from 10-K HTML"""
    html_content = file_content.decode('utf-8', errors='ignore')
    return extract_financials(html_content)


@st.cache_data(ttl=3600)  # Cache for 1 hour
def fetch_api_data(ticker: str, api_key: str) -> Dict:
    """
    Fetch financial data from FMP API (cached for 1 hour)
    
    Args:
        ticker: Stock ticker symbol
        api_key: FMP API key
        
    Returns:
        DCF-formatted financial data
        
    Raises:
        FMPAPIError: If API call fails
    """
    raw_data = fetch_all_company_data(ticker, api_key)
    return map_fmp_to_dcf_format(raw_data)


@st.cache_data
def run_dcf_calculation(
    financials_dict: Dict,
    revenue_growth: float,
    ebit_margin: float,
    ebit_margin_terminal: float,
    capex_initial: float,
    capex_terminal: float,
    da_ratio: float,
    tax_rate: float,
    wc_ratio: float,
    wacc: float,
    terminal_growth: float,
    exit_multiple: float,
    projection_years: int
) -> Dict:
    """Cache DCF calculations to avoid recomputation"""
    assumptions = {
        'revenue_growth': revenue_growth,
        'ebit_margin': ebit_margin,
        'ebit_margin_terminal': ebit_margin_terminal,
        'capex_ratio_initial': capex_initial,
        'capex_ratio_terminal': capex_terminal,
        'da_ratio': da_ratio,
        'tax_rate': tax_rate,
        'wc_ratio': wc_ratio,
        'wacc': wacc,
        'terminal_growth': terminal_growth,
        'exit_multiple': exit_multiple,
        'projection_years': projection_years
    }
    return dcf_model(financials_dict, assumptions, 'base')


def main():
    """Main application logic"""
    
    # Header
    st.markdown('<div class="main-header">JL Fair Value</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Build your own discounted cash flow model and estimate intrinsic value</div>', unsafe_allow_html=True)
    
    # CTA Strip
    st.markdown('<div class="cta-strip">SEC filings to intrinsic value in minutes</div>', unsafe_allow_html=True)
    
    # Quick Steps
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown('<div class="quick-steps-text">Upload a 10-K</div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="quick-steps-text">Build your model</div>', unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="quick-steps-text">Estimate intrinsic value</div>', unsafe_allow_html=True)
    
    # Sidebar - Get Started
    with st.sidebar:
        st.header("Get Started")
        
        # Get API key from secrets
        try:
            api_key = st.secrets["api_keys"]["fmp_api_key"]
            api_available = True
        except:
            api_available = False
            st.warning("⚠️ API key not configured. Upload 10-K files only.")
        
        # Option 1: Ticker Entry (Primary method)
        if api_available:
            st.subheader("Enter Stock Ticker")
            ticker_input = st.text_input(
                "Ticker Symbol",
                value="NVDA",
                max_chars=10,
                help="Enter a stock ticker (e.g., AAPL, MSFT, GOOGL)"
            ).upper().strip()
            
            fetch_button = st.button("Fetch Live Data", type="primary", use_container_width=True)
            
            # Initialize session state for ticker data
            if 'ticker_data' not in st.session_state:
                st.session_state.ticker_data = None
                st.session_state.current_ticker = None
                st.session_state.company_name = None
                st.session_state.current_price = None
            
            # Fetch data when button clicked
            if fetch_button and ticker_input:
                with st.spinner(f"Fetching data for {ticker_input}..."):
                    try:
                        # Fetch from API
                        from src.data.fmp_api import fetch_company_profile
                        profile = fetch_company_profile(ticker_input, api_key)
                        financials_data = fetch_api_data(ticker_input, api_key)
                        
                        # Store in session state
                        st.session_state.ticker_data = financials_data
                        st.session_state.current_ticker = ticker_input
                        st.session_state.company_name = profile.get('companyName', ticker_input)
                        st.session_state.current_price = profile.get('price')
                        st.session_state.data_source = 'API'
                        
                        st.success(f"✓ Data loaded for {st.session_state.company_name}")
                        st.caption(f"Current Price: ${st.session_state.current_price:.2f}")
                        
                    except FMPAPIError as e:
                        st.error(f"API Error: {str(e)}")
                        st.session_state.ticker_data = None
                    except Exception as e:
                        st.error(f"Unexpected error: {str(e)}")
                        st.session_state.ticker_data = None
            
            # Show current loaded ticker
            if st.session_state.ticker_data is not None:
                st.info(f"📊 Loaded: {st.session_state.company_name} ({st.session_state.current_ticker})")
            
            st.markdown("---")
        
        # Option 2: 10-K Upload (Fallback method)
        st.subheader("Or Upload 10-K HTML Filing")
        uploaded_file = st.file_uploader(
            "Upload SEC 10-K HTML file",
            type=['html', 'htm'],
            help="Upload the HTML version of a 10-K filing from SEC EDGAR"
        )
        
        if uploaded_file is not None:
            file_size = len(uploaded_file.getvalue()) / (1024 * 1024)
            st.success(f"File uploaded: {uploaded_file.name}")
            st.caption(f"File size: {file_size:.1f} MB")
    
    # Main content - check for data from either source
    has_ticker_data = st.session_state.get('ticker_data') is not None
    has_file_upload = uploaded_file is not None
    
    if not has_ticker_data and not has_file_upload:
        st.info("Enter a ticker and fetch live data, or upload a 10-K HTML filing to begin")
        
        # Instructions - 2 Column Layout
        col_left, col_right = st.columns(2)
        
        with col_left:
            st.markdown("### How It Works")
            st.markdown("""
            1. **Enter a stock ticker** (e.g., AAPL, MSFT) and click "Fetch Live Data"
            2. **Or upload a 10-K HTML file** from [SEC EDGAR](https://www.sec.gov/edgar/searchedgar/companysearch.html)
            3. **Review historical financials** and derived metrics
            4. **Adjust assumptions** using the model inputs
            5. **Analyze valuation results**, scenarios, and sensitivity tables
            6. **Run reverse DCF** to estimate market-implied growth
            """)
        
        with col_right:
            st.markdown("### Capabilities")
            st.markdown("""
            - **iXBRL parsing** — Automatically extracts financial data from SEC filings
            - **Dual terminal value** — Uses both perpetuity growth and exit multiple methods
            - **Revenue plateau** — Applies a short-term plateau before transitioning to long-term growth
            - **CAPEX fade** — Gradually adjusts reinvestment from initial to long-term levels
            - **Scenario analysis** — Compare downside, base, and upside cases
            - **Sensitivity analysis** — Evaluate valuation across key assumption ranges
            - **Reverse DCF** — Estimate the growth required to justify the current market price
            - **EBIT margin glide** — Smoothly transitions margins toward a steady-state level
            """)
        
        return
    
    # Extract financials from either source
    if has_ticker_data:
        # Use ticker data from API
        financials = st.session_state.ticker_data
        data_source_label = f"Live data for {st.session_state.company_name} ({st.session_state.current_ticker})"
    else:
        # Extract from uploaded file
        with st.spinner("Extracting financial data from 10-K HTML filing. This may take a few seconds."):
            try:
                financials = parse_10k_file(uploaded_file.getvalue())
                data_source_label = f"Data from uploaded 10-K file"
                # Clear ticker data if switching to file upload
                st.session_state.ticker_data = None
                st.session_state.current_ticker = None
                st.session_state.data_source = '10-K'
            except Exception as e:
                st.error(f"Unable to parse 10-K HTML file: {str(e)}")
                return
    
    st.success(f"Financial data extracted successfully — {data_source_label}")
    
    # Blue divider - transition moment
    st.markdown('<div class="blue-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="divider-text">Model Initialized — Adjust assumptions below</div>', unsafe_allow_html=True)
    
    # Display historical data
    st.header("Historical Financials")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Reported Financials")
        historical_df = create_historical_summary(financials)
        st.dataframe(historical_df, use_container_width=True, hide_index=True)
    
    with col2:
        st.subheader("Derived Metrics")
        ratios_df = create_ratios_summary(financials['ratios'])
        st.dataframe(ratios_df, use_container_width=True, hide_index=True)
    
    # Get ratios for default values
    ratios = financials['ratios']
    
    # Sidebar - Assumptions
    st.sidebar.header("Model Assumptions")
    
    with st.sidebar:
        st.subheader("Revenue & Margins")
        
        revenue_growth = st.slider(
            "Revenue Growth",
            min_value=-0.10,
            max_value=0.40,
            value=float(ratios['revenue_cagr']) if ratios['revenue_cagr'] else 0.10,
            step=0.005,
            help="Initial revenue growth rate"
        )
        
        ebit_margin = st.slider(
            "EBIT Margin (Initial)",
            min_value=0.0,
            max_value=1.0,
            value=float(ratios['ebit_margin']) if ratios['ebit_margin'] else 0.40,
            step=0.005,
            help="Starting EBIT margin"
        )
        
        ebit_margin_terminal = st.slider(
            "EBIT Margin (Terminal)",
            min_value=0.0,
            max_value=1.0,
            value=float(ratios['ebit_margin']) if ratios['ebit_margin'] else 0.40,
            step=0.005,
            help="Long-term EBIT margin"
        )
        
        st.subheader("CAPEX & Working Capital")
        
        default_capex = float(ratios['capex_ratio']) if ratios['capex_ratio'] else 0.15
        
        capex_initial = st.slider(
            "CAPEX Initial %",
            min_value=0.0,
            max_value=0.40,
            value=default_capex,
            step=0.005,
            help="Initial CAPEX as % of revenue"
        )
        
        capex_terminal = st.slider(
            "CAPEX Terminal %",
            min_value=0.0,
            max_value=0.40,
            value=max(0.10, default_capex - 0.03),
            step=0.005,
            help="Terminal CAPEX as % of revenue"
        )
        
        da_ratio = st.slider(
            "D&A % Revenue",
            min_value=0.01,
            max_value=0.40,
            value=float(ratios['da_ratio']) if ratios['da_ratio'] else 0.05,
            step=0.005,
            help="Depreciation & Amortization as % of revenue"
        )
        
        wc_ratio = st.slider(
            "Working Capital Ratio",
            min_value=-0.10,
            max_value=0.50,
            value=float(ratios['wc_ratio']) if ratios['wc_ratio'] else 0.05,
            step=0.005,
            help="Change in NWC as % of revenue change"
        )
        
        st.subheader("Tax & Discount Rate")
        
        tax_rate = st.slider(
            "Tax Rate",
            min_value=0.01,
            max_value=0.40,
            value=float(ratios['tax_rate']) if ratios['tax_rate'] else 0.21,
            step=0.005,
            help="Effective tax rate"
        )
        
        wacc = st.slider(
            "WACC",
            min_value=0.05,
            max_value=0.15,
            value=0.085,
            step=0.005,
            help="Weighted Average Cost of Capital"
        )
        
        st.subheader("Terminal Value")
        
        terminal_growth = st.slider(
            "Terminal Growth",
            min_value=0.0,
            max_value=0.04,
            value=0.025,
            step=0.005,
            help="Perpetual growth rate"
        )
        
        default_exit = calculate_default_exit_multiple(
            ratios['ebit_margin'],
            ratios['revenue_cagr']
        )
        
        exit_multiple = st.slider(
            "Exit Multiple (EBIT)",
            min_value=0.0,
            max_value=40.0,
            value=default_exit,
            step=0.5,
            format="%.1fx",
            help="Exit multiple for terminal value"
        )
        
        st.subheader("Forecast Period")
        
        projection_years = st.slider(
            "Projection Years",
            min_value=5,
            max_value=10,
            value=7,
            step=1,
            help="Number of years to project"
        )
    
    # Run DCF calculation (cached)
    try:
        result = run_dcf_calculation(
            financials,
            revenue_growth,
            ebit_margin,
            ebit_margin_terminal,
            capex_initial,
            capex_terminal,
            da_ratio,
            tax_rate,
            wc_ratio,
            wacc,
            terminal_growth,
            exit_multiple,
            projection_years
        )
    except Exception as e:
        st.error(f"Error running valuation: {str(e)}")
        return
    
    # Main results
    st.header("Valuation Results")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Perpetuity Method",
            format_price(result['price_per_share_gordon']),
            help="Terminal value using perpetuity formula"
        )
    
    with col2:
        st.metric(
            "Exit Multiple Method",
            format_price(result['price_per_share_exit']),
            help="Terminal value using exit EBIT multiple"
        )
    
    with col3:
        st.metric(
            "Blended Average",
            format_price(result['price_per_share_avg']),
            delta=None,
            help="Average of both methods"
        )
    
    # Tabs for different analyses
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Projection", 
        "Scenarios", 
        "Sensitivity", 
        "Market Expectations",
        "Growth Paths"
    ])
    
    with tab1:
        st.subheader("Projected Cash Flows")
        projection_df = create_projection_summary(result['projection'])
        st.dataframe(projection_df, use_container_width=True, hide_index=True)
        
        # Terminal value breakdown
        st.subheader("Terminal Value")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Perpetuity Method**")
            st.write(f"Sum of PV(FCF): {format_millions(result['sum_pv_fcf'])}")
            st.write(f"Terminal Value: {format_millions(result['terminal_value_gordon'])}")
            st.write(f"PV(Terminal): {format_millions(result['pv_terminal_gordon'])}")
            st.write(f"Enterprise Value: {format_millions(result['enterprise_value_gordon'])}")
            st.write(f"- Net Debt: {format_millions(ratios['net_debt'])}")
            st.write(f"= Equity Value: {format_millions(result['equity_value_gordon'])}")
            shares_display = f"{ratios['shares_diluted'] / 1_000_000:,.0f}M" if ratios.get('shares_diluted') else "N/A"
            st.write(f"÷ Shares: {shares_display}")
            st.markdown(f"**= ${result['price_per_share_gordon']:.2f}/share**")
        
        with col2:
            st.markdown("**Exit Multiple Method**")
            st.write(f"Sum of PV(FCF): {format_millions(result['sum_pv_fcf'])}")
            st.write(f"Terminal Value: {format_millions(result['terminal_value_exit'])}")
            st.write(f"PV(Terminal): {format_millions(result['pv_terminal_exit'])}")
            st.write(f"Enterprise Value: {format_millions(result['enterprise_value_exit'])}")
            st.write(f"- Net Debt: {format_millions(ratios['net_debt'])}")
            st.write(f"= Equity Value: {format_millions(result['equity_value_exit'])}")
            shares_display = f"{ratios['shares_diluted'] / 1_000_000:,.0f}M" if ratios.get('shares_diluted') else "N/A"
            st.write(f"÷ Shares: {shares_display}")
            st.markdown(f"**= ${result['price_per_share_exit']:.2f}/share**")
    
    with tab2:
        st.subheader("Scenario Analysis")
        
        scenarios = generate_scenario_analysis(financials, result['assumptions'])
        
        scenario_data = []
        for scenario_name in ['bear', 'base', 'bull']:
            s = scenarios[scenario_name]
            scenario_data.append({
                'Scenario': scenario_name.capitalize(),
                'Revenue Growth': format_percentage(s['assumptions']['revenue_growth']),
                'EBIT Margin': format_percentage(s['assumptions']['ebit_margin']),
                'Perpetuity Method': format_price(s['price_per_share_gordon']),
                'Exit Method': format_price(s['price_per_share_exit']),
                'Blended': format_price(s['price_per_share_avg'])
            })
        
        scenario_df = pd.DataFrame(scenario_data)
        st.dataframe(scenario_df, use_container_width=True, hide_index=True)
        
        # Visual comparison
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Bear Case", format_price(scenarios['bear']['price_per_share_avg']))
        with col2:
            st.metric("Base Case", format_price(scenarios['base']['price_per_share_avg']))
        with col3:
            st.metric("Bull Case", format_price(scenarios['bull']['price_per_share_avg']))
    
    with tab3:
        st.subheader("Sensitivity Analysis")
        
        # WACC × Terminal Growth
        st.markdown("**WACC × Terminal Growth (Blended Method)**")
        wacc_terminal_table = generate_wacc_terminal_sensitivity(financials, result['assumptions'])
        
        # Format the table for display
        wacc_terminal_display = wacc_terminal_table.copy()
        wacc_terminal_display.index = [f"{idx:.1%}" for idx in wacc_terminal_display.index]
        for col in wacc_terminal_display.columns:
            wacc_terminal_display[col] = wacc_terminal_display[col].apply(
                lambda x: format_price(x) if pd.notna(x) else 'N/A'
            )
        
        st.dataframe(wacc_terminal_display, use_container_width=True)
        
        st.markdown("---")
        
        # Exit Multiple × Revenue Growth
        st.markdown("**Exit Multiple × Revenue Growth (Exit Method)**")
        exit_growth_table = generate_exit_multiple_growth_sensitivity(financials, result['assumptions'])
        
        # Format the table for display
        exit_growth_display = exit_growth_table.copy()
        for col in exit_growth_display.columns:
            exit_growth_display[col] = exit_growth_display[col].apply(
                lambda x: format_price(x) if pd.notna(x) else 'N/A'
            )
        
        st.dataframe(exit_growth_display, use_container_width=True)
    
    with tab4:
        st.subheader("Market Expectations")
        
        st.markdown("""
        Enter the current stock price to estimate the growth required to justify today's valuation, holding all other assumptions constant.
        """)
        
        # Auto-fill price if available from API
        default_price = 100.0
        if st.session_state.get('current_price'):
            default_price = float(st.session_state.current_price)
            st.caption(f"💡 Current market price auto-filled from live data")
        
        market_price = st.number_input(
            "Current Stock Price ($)",
            min_value=0.0,
            value=default_price,
            step=1.0,
            help="Enter the current market price of the stock"
        )
        
        if st.button("Calculate Implied Growth", type="primary"):
            with st.spinner("Calculating implied growth rate."):
                reverse_result = calculate_implied_metrics(
                    market_price,
                    financials,
                    result['assumptions']
                )
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric(
                    "Market Price",
                    format_price(market_price)
                )
            
            with col2:
                st.metric(
                    "Base Case Price",
                    format_price(reverse_result['base_price']),
                    delta=format_price(reverse_result['price_difference'])
                )
            
            with col3:
                st.metric(
                    "Implied Growth",
                    format_percentage(reverse_result['implied_growth']),
                    delta=format_percentage(reverse_result['growth_difference'])
                )
            
            st.markdown("---")
            
            st.subheader("Interpretation")
            st.info(reverse_result['interpretation'])
            
            st.markdown("**Assumptions Held Constant:**")
            const_assumptions = reverse_result['assumptions_held_constant']
            const_df = pd.DataFrame([
                {'Parameter': 'EBIT Margin (Initial)', 'Value': format_percentage(const_assumptions['ebit_margin'])},
                {'Parameter': 'EBIT Margin (Terminal)', 'Value': format_percentage(const_assumptions['ebit_margin_terminal'])},
                {'Parameter': 'CAPEX Initial', 'Value': format_percentage(const_assumptions['capex_ratio_initial'])},
                {'Parameter': 'CAPEX Terminal', 'Value': format_percentage(const_assumptions['capex_ratio_terminal'])},
                {'Parameter': 'Tax Rate', 'Value': format_percentage(const_assumptions['tax_rate'])},
                {'Parameter': 'WACC', 'Value': format_percentage(const_assumptions['wacc'])},
                {'Parameter': 'Terminal Growth', 'Value': format_percentage(const_assumptions['terminal_growth'])},
            ])
            st.dataframe(const_df, use_container_width=True, hide_index=True)
    
    with tab5:
        st.subheader("Revenue Growth Path (2-Year Plateau)")
        
        growth_data = []
        base_year = financials['years'][0]
        for i, growth in enumerate(result['growth_path']):
            phase = 'Plateau' if i >= projection_years - 2 else 'Fade'
            growth_data.append({
                'Year': base_year + i + 1,
                'Growth Rate': format_percentage(growth),
                'Phase': phase
            })
        
        growth_df = pd.DataFrame(growth_data)
        st.dataframe(growth_df, use_container_width=True, hide_index=True)
        
        st.caption(f"Terminal Growth: {format_percentage(terminal_growth)}")
        
        st.markdown("---")
        
        st.subheader("CAPEX Fade Path")
        
        capex_data = []
        for i, capex_pct in enumerate(result['capex_path']):
            capex_data.append({
                'Year': base_year + i + 1,
                'CAPEX % Revenue': format_percentage(capex_pct)
            })
        
        capex_df = pd.DataFrame(capex_data)
        st.dataframe(capex_df, use_container_width=True, hide_index=True)
        
        st.caption(f"Terminal CAPEX: {format_percentage(capex_terminal)}")
        
        st.markdown("---")
        
        st.subheader("EBIT Margin Glide Path")
        
        margin_data = []
        for i, margin in enumerate(result['ebit_margin_path']):
            margin_data.append({
                'Year': base_year + i + 1,
                'EBIT Margin': format_percentage(margin)
            })
        
        margin_df = pd.DataFrame(margin_data)
        st.dataframe(margin_df, use_container_width=True, hide_index=True)
        
        st.caption(f"Terminal EBIT Margin: {format_percentage(ebit_margin_terminal)}")


if __name__ == "__main__":
    main()
