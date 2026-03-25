"""
DCF Valuation Model - Streamlit Web Application
Professional DCF valuation with dual terminal value methods
"""
import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict

# Import custom modules
from src.data.sec_parser import extract_financials
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
    page_title="DCF Valuation Model",
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
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        margin-bottom: 2rem;
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
</style>
""", unsafe_allow_html=True)


@st.cache_data
def parse_10k_file(file_content: bytes) -> Dict:
    """Cache the extraction of financial data from 10-K HTML"""
    html_content = file_content.decode('utf-8', errors='ignore')
    return extract_financials(html_content)


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
    st.markdown('<div class="main-header">📊 DCF Valuation Model</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Professional discounted cash flow valuation with dual terminal value methods</div>', unsafe_allow_html=True)
    
    # Sidebar - File Upload
    with st.sidebar:
        st.header("📤 Upload 10-K Filing")
        uploaded_file = st.file_uploader(
            "Upload SEC 10-K HTML file",
            type=['html', 'htm'],
            help="Upload the HTML version of a 10-K filing from SEC EDGAR"
        )
        
        if uploaded_file is not None:
            file_size = len(uploaded_file.getvalue()) / (1024 * 1024)
            st.success(f"✅ Uploaded: {uploaded_file.name}")
            st.caption(f"File size: {file_size:.1f} MB")
    
    # Main content
    if uploaded_file is None:
        st.info("👈 Please upload a 10-K HTML file from the sidebar to begin")
        
        # Instructions
        st.markdown("### 📖 How to use this tool")
        st.markdown("""
        1. **Download a 10-K filing** from [SEC EDGAR](https://www.sec.gov/edgar/searchedgar/companysearch.html)
        2. **Upload the HTML file** using the sidebar
        3. **Review historical data** and calculated ratios
        4. **Adjust assumptions** using the sliders
        5. **Analyze results** including scenarios and sensitivity tables
        6. **Run reverse DCF** to see market-implied growth rates
        """)
        
        st.markdown("### ✨ Key Features")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            - **iXBRL parsing** - Automatic extraction from SEC filings
            - **Dual terminal value** - Gordon Growth + Exit Multiple
            - **Revenue plateau** - 2-year plateau before terminal growth
            - **CAPEX fade** - Linear fade from initial to terminal
            """)
        with col2:
            st.markdown("""
            - **Scenario analysis** - Bear/Base/Bull cases
            - **Sensitivity tables** - WACC × Terminal, Exit × Growth
            - **Reverse DCF** - Market-implied growth solver
            - **EBIT margin glide** - Smooth transition to terminal margin
            """)
        
        return
    
    # Extract financials (cached)
    with st.spinner("Parsing 10-K filing... This may take a few seconds..."):
        try:
            financials = parse_10k_file(uploaded_file.getvalue())
        except Exception as e:
            st.error(f"❌ Error parsing file: {str(e)}")
            return
    
    st.success("✅ Financial data extracted successfully!")
    
    # Display historical data
    st.header("📊 Historical Financials")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Historical Data")
        historical_df = create_historical_summary(financials)
        st.dataframe(historical_df, use_container_width=True, hide_index=True)
    
    with col2:
        st.subheader("Calculated Ratios")
        ratios_df = create_ratios_summary(financials['ratios'])
        st.dataframe(ratios_df, use_container_width=True, hide_index=True)
    
    # Get ratios for default values
    ratios = financials['ratios']
    
    # Sidebar - Assumptions
    st.sidebar.header("🎛️ Valuation Assumptions")
    
    with st.sidebar:
        st.subheader("Revenue & Margins")
        
        revenue_growth = st.slider(
            "Revenue Growth",
            min_value=-0.10,
            max_value=0.40,
            value=float(ratios['revenue_cagr']) if ratios['revenue_cagr'] else 0.10,
            step=0.005,
            format="%.1f%%",
            help="Initial revenue growth rate"
        )
        
        ebit_margin = st.slider(
            "EBIT Margin (Initial)",
            min_value=0.0,
            max_value=1.0,
            value=float(ratios['ebit_margin']) if ratios['ebit_margin'] else 0.40,
            step=0.005,
            format="%.1f%%",
            help="Starting EBIT margin"
        )
        
        ebit_margin_terminal = st.slider(
            "EBIT Margin (Terminal)",
            min_value=0.0,
            max_value=1.0,
            value=float(ratios['ebit_margin']) if ratios['ebit_margin'] else 0.40,
            step=0.005,
            format="%.1f%%",
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
            format="%.1f%%",
            help="Initial CAPEX as % of revenue"
        )
        
        capex_terminal = st.slider(
            "CAPEX Terminal %",
            min_value=0.0,
            max_value=0.40,
            value=max(0.10, default_capex - 0.03),
            step=0.005,
            format="%.1f%%",
            help="Terminal CAPEX as % of revenue"
        )
        
        da_ratio = st.slider(
            "D&A % Revenue",
            min_value=0.01,
            max_value=0.40,
            value=float(ratios['da_ratio']) if ratios['da_ratio'] else 0.05,
            step=0.005,
            format="%.1f%%",
            help="Depreciation & Amortization as % of revenue"
        )
        
        wc_ratio = st.slider(
            "Working Capital Ratio",
            min_value=-0.10,
            max_value=0.50,
            value=float(ratios['wc_ratio']) if ratios['wc_ratio'] else 0.05,
            step=0.005,
            format="%.1f%%",
            help="Change in NWC as % of revenue change"
        )
        
        st.subheader("Tax & Discount Rate")
        
        tax_rate = st.slider(
            "Tax Rate",
            min_value=0.01,
            max_value=0.40,
            value=float(ratios['tax_rate']) if ratios['tax_rate'] else 0.21,
            step=0.005,
            format="%.1f%%",
            help="Effective tax rate"
        )
        
        wacc = st.slider(
            "WACC",
            min_value=0.05,
            max_value=0.15,
            value=0.085,
            step=0.005,
            format="%.1f%%",
            help="Weighted Average Cost of Capital"
        )
        
        st.subheader("Terminal Value")
        
        terminal_growth = st.slider(
            "Terminal Growth",
            min_value=0.0,
            max_value=0.04,
            value=0.025,
            step=0.005,
            format="%.1f%%",
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
        
        st.subheader("Projection Period")
        
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
        st.error(f"❌ Error calculating DCF: {str(e)}")
        return
    
    # Main results
    st.header("💰 Valuation Results")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Gordon Growth Method",
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
        "📈 Projection", 
        "🎯 Scenarios", 
        "📊 Sensitivity", 
        "🔄 Reverse DCF",
        "📋 Growth Paths"
    ])
    
    with tab1:
        st.subheader("Cash Flow Projection")
        projection_df = create_projection_summary(result['projection'])
        st.dataframe(projection_df, use_container_width=True, hide_index=True)
        
        # Terminal value breakdown
        st.subheader("Terminal Value Calculation")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Gordon Growth Method**")
            st.write(f"Sum of PV(FCF): {format_millions(result['sum_pv_fcf'])}")
            st.write(f"Terminal Value: {format_millions(result['terminal_value_gordon'])}")
            st.write(f"PV(Terminal): {format_millions(result['pv_terminal_gordon'])}")
            st.write(f"Enterprise Value: {format_millions(result['enterprise_value_gordon'])}")
            st.write(f"- Net Debt: {format_millions(ratios['net_debt'])}")
            st.write(f"= Equity Value: {format_millions(result['equity_value_gordon'])}")
            st.write(f"÷ Shares: {ratios['shares_diluted'] / 1_000_000:,.0f}M")
            st.markdown(f"**= ${result['price_per_share_gordon']:.2f}/share**")
        
        with col2:
            st.markdown("**Exit Multiple Method**")
            st.write(f"Sum of PV(FCF): {format_millions(result['sum_pv_fcf'])}")
            st.write(f"Terminal Value: {format_millions(result['terminal_value_exit'])}")
            st.write(f"PV(Terminal): {format_millions(result['pv_terminal_exit'])}")
            st.write(f"Enterprise Value: {format_millions(result['enterprise_value_exit'])}")
            st.write(f"- Net Debt: {format_millions(ratios['net_debt'])}")
            st.write(f"= Equity Value: {format_millions(result['equity_value_exit'])}")
            st.write(f"÷ Shares: {ratios['shares_diluted'] / 1_000_000:,.0f}M")
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
                'Gordon Method': format_price(s['price_per_share_gordon']),
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
        st.subheader("Reverse DCF - Market-Implied Growth")
        
        st.markdown("""
        Enter the current market price to solve for the revenue growth rate that 
        would justify this valuation (holding all other assumptions constant).
        """)
        
        market_price = st.number_input(
            "Current Stock Price ($)",
            min_value=0.0,
            value=100.0,
            step=1.0,
            help="Enter the current market price of the stock"
        )
        
        if st.button("Calculate Implied Growth", type="primary"):
            with st.spinner("Solving for implied growth rate..."):
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
