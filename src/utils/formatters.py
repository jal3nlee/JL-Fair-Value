"""
Utility Functions
Formatting and helper functions for the DCF app
"""
import pandas as pd
from typing import Optional


def format_millions(value: Optional[float]) -> str:
    """Format value in millions with $ prefix"""
    if pd.isna(value) or value is None:
        return '—'
    millions = value / 1_000_000
    return f'${millions:,.0f}M'


def format_percentage(value: Optional[float]) -> str:
    """Format value as percentage with 1 decimal"""
    if pd.isna(value) or value is None:
        return '—'
    return f'{value * 100:.1f}%'


def format_price(value: Optional[float]) -> str:
    """Format value as price with $ prefix"""
    if pd.isna(value) or value is None:
        return '—'
    return f'${value:.2f}'


def format_multiple(value: Optional[float]) -> str:
    """Format value as multiple with 1 decimal"""
    if pd.isna(value) or value is None:
        return '—'
    return f'{value:.1f}x'


def calculate_default_exit_multiple(ebit_margin: Optional[float], revenue_growth: Optional[float]) -> float:
    """
    Calculate intelligent default exit multiple based on quality metrics
    
    Args:
        ebit_margin: Current EBIT margin
        revenue_growth: Revenue growth rate
        
    Returns:
        Exit multiple between 12-25x (always float)
    """
    if ebit_margin and revenue_growth:
        margin_premium = (ebit_margin - 0.30) * 20
        growth_premium = (revenue_growth - 0.10) * 30
        exit_multiple = 15.0 + margin_premium + growth_premium
        return float(max(12.0, min(25.0, exit_multiple)))
    return 18.0


def create_historical_summary(financials: dict) -> pd.DataFrame:
    """
    Create a formatted historical financials summary table
    
    Args:
        financials: Historical financial data
        
    Returns:
        DataFrame with formatted historical data
    """
    years = financials['years']
    revenues = financials['Revenue']
    data = []
    
    for i, year in enumerate(years):
        rev = revenues[i]
        ebit = financials['EBIT'][i]
        capex = financials['CAPEX'][i]
        da = financials['Depreciation'][i]
        nwc = financials['NWC'][i]
        
        # Calculate year-over-year revenue growth
        if i < len(years) - 1 and revenues[i] and revenues[i + 1]:
            rev_growth = (revenues[i] - revenues[i + 1]) / revenues[i + 1]
        else:
            rev_growth = None
        
        ebit_pct = (ebit / rev) if (ebit and rev) else None
        capex_pct = (abs(capex) / rev) if (capex and rev) else None
        
        # Skip EBIT for oldest year (usually incomplete)
        if i == 3:
            data.append({
                'Year': year,
                'Revenue': format_millions(rev),
                'Rev Growth': '—',
                'EBIT': '—',
                'EBIT %': '—',
                'CAPEX': '—',
                'CAPEX %': '—',
                'D&A': '—',
                'NWC': format_millions(nwc)
            })
        else:
            data.append({
                'Year': year,
                'Revenue': format_millions(rev),
                'Rev Growth': format_percentage(rev_growth),
                'EBIT': format_millions(ebit),
                'EBIT %': format_percentage(ebit_pct),
                'CAPEX': format_millions(capex),
                'CAPEX %': format_percentage(capex_pct),
                'D&A': format_millions(da),
                'NWC': format_millions(nwc)
            })
    
    return pd.DataFrame(data)


def create_projection_summary(projection: list) -> pd.DataFrame:
    """
    Create a formatted projection table
    
    Args:
        projection: List of projection dictionaries from DCF model
        
    Returns:
        DataFrame with formatted projection
    """
    data = []
    for p in projection:
        data.append({
            'Year': p['Year'],
            'Revenue': format_millions(p['Revenue']),
            'EBIT': format_millions(p['EBIT']),
            'NOPAT': format_millions(p['NOPAT']),
            '+D&A': format_millions(p['D&A']),
            '-CAPEX': format_millions(p['CAPEX']),
            '-ΔWC': format_millions(p['ΔWC']),
            'FCF': format_millions(p['FCF']),
            'PV(FCF)': format_millions(p['PV'])
        })
    
    return pd.DataFrame(data)


def create_ratios_summary(ratios: dict) -> pd.DataFrame:
    """
    Create a formatted ratios summary table
    
    Args:
        ratios: Ratios dictionary from financials
        
    Returns:
        DataFrame with formatted ratios
    """
    data = [
        {'Metric': 'Revenue CAGR (3-yr)', 'Value': format_percentage(ratios['revenue_cagr'])},
        {'Metric': 'EBIT Margin (3-yr avg)', 'Value': format_percentage(ratios['ebit_margin'])},
        {'Metric': 'CAPEX % Revenue (3-yr avg)', 'Value': format_percentage(ratios['capex_ratio'])},
        {'Metric': 'D&A % Revenue (3-yr avg)', 'Value': format_percentage(ratios['da_ratio'])},
        {'Metric': 'Tax Rate (3-yr avg)', 'Value': format_percentage(ratios['tax_rate'])},
        {'Metric': 'Working Capital Ratio', 'Value': format_percentage(ratios['wc_ratio'])},
        {'Metric': 'Net Debt', 'Value': format_millions(ratios['net_debt'])},
        {'Metric': 'Shares (diluted)', 'Value': f"{ratios['shares_diluted'] / 1_000_000:,.0f}M" if ratios.get('shares_diluted') else "N/A"}
    ]
    
    return pd.DataFrame(data)
