"""
DCF Valuation Engine
Core discounted cash flow calculations with dual terminal value methods
"""
from typing import Dict, List
import numpy as np


def calculate_growth_path_with_plateau(
    initial_growth: float, 
    terminal_growth: float, 
    years: int, 
    plateau_years: int = 2
) -> List[float]:
    """
    Calculate revenue growth path with 2-year plateau before terminal
    
    Args:
        initial_growth: Starting revenue growth rate
        terminal_growth: Long-term perpetual growth rate
        years: Total projection years
        plateau_years: Years to plateau at terminal_growth + 2%
        
    Returns:
        List of growth rates for each year
    """
    plateau_growth = terminal_growth + 0.02
    fade_years = years - plateau_years
    
    growth_path = []
    for year in range(years):
        if year < fade_years:
            fade_progress = year / fade_years
            growth = initial_growth - fade_progress * (initial_growth - plateau_growth)
            growth_path.append(growth)
        else:
            growth_path.append(plateau_growth)
    
    return growth_path


def calculate_capex_path(
    initial_capex_ratio: float, 
    terminal_capex_ratio: float, 
    projection_years: int
) -> List[float]:
    """
    CAPEX ratio fades linearly from initial to terminal
    
    Args:
        initial_capex_ratio: Starting CAPEX as % of revenue
        terminal_capex_ratio: Ending CAPEX as % of revenue
        projection_years: Number of years to fade
        
    Returns:
        List of CAPEX ratios for each year
    """
    capex_path = []
    for year in range(projection_years):
        fade_progress = year / projection_years
        capex_ratio = initial_capex_ratio - fade_progress * (initial_capex_ratio - terminal_capex_ratio)
        capex_path.append(capex_ratio)
    
    return capex_path


def calculate_ebit_margin_path(
    initial_margin: float, 
    terminal_margin: float, 
    projection_years: int
) -> List[float]:
    """
    EBIT margin glides linearly from initial to terminal
    
    Args:
        initial_margin: Starting EBIT margin
        terminal_margin: Ending EBIT margin
        projection_years: Number of years to glide
        
    Returns:
        List of EBIT margins for each year
    """
    margin_path = []
    for year in range(projection_years):
        fade_progress = year / projection_years
        margin = initial_margin - fade_progress * (initial_margin - terminal_margin)
        margin_path.append(margin)
    return margin_path


def dcf_model(financials: Dict, assumptions: Dict, scenario: str = 'base') -> Dict:
    """
    Calculate DCF valuation with dual terminal value methods
    
    Args:
        financials: Historical financial data from SEC parser
        assumptions: User-defined valuation assumptions
        scenario: Scenario name ('base', 'bear', 'bull', etc.)
        
    Returns:
        Dictionary containing projection, terminal values, and intrinsic value
    """
    ratios = financials['ratios']
    
    # Extract assumptions
    revenue_growth_initial = assumptions['revenue_growth']
    ebit_margin_initial = assumptions['ebit_margin']
    ebit_margin_terminal = assumptions['ebit_margin_terminal']
    capex_ratio_initial = assumptions['capex_ratio_initial']
    capex_ratio_terminal = assumptions['capex_ratio_terminal']
    da_ratio = assumptions['da_ratio']
    tax_rate = assumptions['tax_rate']
    wc_ratio = assumptions['wc_ratio']
    wacc = assumptions['wacc']
    terminal_growth = assumptions['terminal_growth']
    projection_years = assumptions['projection_years']
    exit_multiple = assumptions['exit_multiple']
    
    net_debt = ratios['net_debt']
    shares = ratios['shares_diluted']
    revenue_base = financials['Revenue'][0]
    
    # Validation
    if da_ratio == 0:
        raise ValueError("D&A ratio cannot be 0%")
    if tax_rate == 0:
        raise ValueError("Tax rate cannot be 0%")
    
    # Calculate paths
    growth_path = calculate_growth_path_with_plateau(
        revenue_growth_initial, terminal_growth, projection_years, 2
    )
    capex_path = calculate_capex_path(
        capex_ratio_initial, capex_ratio_terminal, projection_years
    )
    ebit_margin_path = calculate_ebit_margin_path(
        ebit_margin_initial, ebit_margin_terminal, projection_years
    )
    
    # Build projection
    projection = []
    revenue_prior = revenue_base
    
    for year_num in range(projection_years):
        growth_rate = growth_path[year_num]
        revenue = revenue_prior * (1 + growth_rate)
        ebit_margin = ebit_margin_path[year_num]
        ebit = revenue * ebit_margin
        nopat = ebit * (1 - tax_rate)
        da = revenue * da_ratio
        capex_ratio = capex_path[year_num]
        capex = -revenue * capex_ratio
        delta_revenue = revenue - revenue_prior
        delta_wc = -delta_revenue * wc_ratio
        fcf = nopat + da + capex + delta_wc
        pv_fcf = fcf / ((1 + wacc) ** (year_num + 1))
        
        projection.append({
            'Year': financials['years'][0] + year_num + 1,
            'Growth': growth_rate,
            'Revenue': revenue,
            'EBIT': ebit,
            'EBIT_Margin': ebit_margin,
            'NOPAT': nopat,
            'D&A': da,
            'CAPEX': capex,
            'CAPEX%': capex_ratio,
            'ΔWC': delta_wc,
            'FCF': fcf,
            'PV': pv_fcf
        })
        
        revenue_prior = revenue
    
    fcf_final = projection[-1]['FCF']
    ebit_final = projection[-1]['EBIT']
    
    # Method 1: Gordon Growth (Perpetuity)
    tv_gordon = fcf_final * (1 + terminal_growth) / (wacc - terminal_growth)
    pv_tv_gordon = tv_gordon / ((1 + wacc) ** projection_years)
    
    # Method 2: Exit Multiple
    tv_exit = ebit_final * exit_multiple
    pv_tv_exit = tv_exit / ((1 + wacc) ** projection_years)
    
    # Valuation - Gordon Growth Method
    sum_pv_fcf = sum(p['PV'] for p in projection)
    ev_gordon = sum_pv_fcf + pv_tv_gordon
    equity_gordon = ev_gordon - net_debt
    price_gordon = equity_gordon / shares
    
    # Valuation - Exit Multiple Method
    ev_exit = sum_pv_fcf + pv_tv_exit
    equity_exit = ev_exit - net_debt
    price_exit = equity_exit / shares
    
    # Average of both methods
    price_avg = (price_gordon + price_exit) / 2
    
    return {
        'projection': projection,
        'growth_path': growth_path,
        'capex_path': capex_path,
        'ebit_margin_path': ebit_margin_path,
        'terminal_value_gordon': tv_gordon,
        'pv_terminal_gordon': pv_tv_gordon,
        'terminal_value_exit': tv_exit,
        'pv_terminal_exit': pv_tv_exit,
        'enterprise_value_gordon': ev_gordon,
        'equity_value_gordon': equity_gordon,
        'price_per_share_gordon': price_gordon,
        'enterprise_value_exit': ev_exit,
        'equity_value_exit': equity_exit,
        'price_per_share_exit': price_exit,
        'price_per_share_avg': price_avg,
        'sum_pv_fcf': sum_pv_fcf,
        'assumptions': assumptions,
        'scenario': scenario
    }
