"""
Sensitivity Analysis
Generate sensitivity tables for DCF valuation
"""
from typing import Dict, List, Tuple
import pandas as pd
from .dcf_engine import dcf_model


def generate_wacc_terminal_sensitivity(
    financials: Dict,
    base_assumptions: Dict,
    wacc_range: List[float] = None,
    terminal_range: List[float] = None
) -> pd.DataFrame:
    """
    Generate WACC × Terminal Growth sensitivity table
    
    Args:
        financials: Historical financial data
        base_assumptions: Base valuation assumptions
        wacc_range: List of WACC values to test (default: base ± 2% in 1% steps)
        terminal_range: List of terminal growth values (default: base ± 1.5% in 0.5% steps)
        
    Returns:
        DataFrame with WACC as rows, Terminal Growth as columns
    """
    wacc_base = base_assumptions['wacc']
    tg_base = base_assumptions['terminal_growth']
    
    # Default ranges
    if wacc_range is None:
        wacc_range = [
            wacc_base - 0.02,
            wacc_base - 0.01,
            wacc_base,
            wacc_base + 0.01,
            wacc_base + 0.02
        ]
    
    if terminal_range is None:
        terminal_range = [
            max(0.0, tg_base - 0.015),
            max(0.0, tg_base - 0.005),
            tg_base,
            tg_base + 0.005,
            tg_base + 0.015
        ]
    
    # Build sensitivity table
    results = []
    for wacc in wacc_range:
        row = {'WACC': wacc}
        for tg in terminal_range:
            sens_assumptions = base_assumptions.copy()
            sens_assumptions['wacc'] = wacc
            sens_assumptions['terminal_growth'] = tg
            try:
                sens_result = dcf_model(financials, sens_assumptions, 'sensitivity')
                row[f'TG_{tg:.3f}'] = sens_result['price_per_share_avg']
            except:
                row[f'TG_{tg:.3f}'] = None
        results.append(row)
    
    df = pd.DataFrame(results)
    df = df.set_index('WACC')
    
    # Rename columns to percentages
    df.columns = [f"{float(col.split('_')[1]):.1%}" for col in df.columns]
    
    return df


def generate_exit_multiple_growth_sensitivity(
    financials: Dict,
    base_assumptions: Dict,
    exit_multiples: List[float] = None,
    growth_range: List[float] = None
) -> pd.DataFrame:
    """
    Generate Exit Multiple × Revenue Growth sensitivity table
    
    Args:
        financials: Historical financial data
        base_assumptions: Base valuation assumptions
        exit_multiples: List of exit multiple values (default: base ± 4x in 2x steps)
        growth_range: List of growth values (default: base ± 4% in 2% steps)
        
    Returns:
        DataFrame with Revenue Growth as rows, Exit Multiple as columns
    """
    exit_base = base_assumptions['exit_multiple']
    growth_base = base_assumptions['revenue_growth']
    
    # Default ranges
    if exit_multiples is None:
        base_rounded = round(exit_base / 2) * 2
        exit_multiples = [
            base_rounded - 4,
            base_rounded - 2,
            base_rounded,
            base_rounded + 2,
            base_rounded + 4
        ]
    
    if growth_range is None:
        growth_range = [
            growth_base - 0.04,
            growth_base - 0.02,
            growth_base,
            growth_base + 0.02,
            growth_base + 0.04
        ]
    
    # Build sensitivity table
    results = []
    for growth in growth_range:
        row = {'Revenue_Growth': growth}
        for exit_mult in exit_multiples:
            sens_assumptions = base_assumptions.copy()
            sens_assumptions['revenue_growth'] = growth
            sens_assumptions['exit_multiple'] = exit_mult
            try:
                sens_result = dcf_model(financials, sens_assumptions, 'sensitivity')
                row[f'Exit_{exit_mult:.1f}'] = sens_result['price_per_share_exit']
            except:
                row[f'Exit_{exit_mult:.1f}'] = None
        results.append(row)
    
    df = pd.DataFrame(results)
    df = df.set_index('Revenue_Growth')
    
    # Rename columns to multiples
    df.columns = [f"{col.split('_')[1]}x" for col in df.columns]
    
    # Rename index to percentages
    df.index = [f"{idx:.1%}" for idx in df.index]
    
    return df


def generate_scenario_analysis(
    financials: Dict,
    base_assumptions: Dict
) -> Dict[str, Dict]:
    """
    Generate Bear/Base/Bull scenario analysis
    
    Args:
        financials: Historical financial data
        base_assumptions: Base case assumptions
        
    Returns:
        Dictionary with 'bear', 'base', 'bull' scenario results
    """
    revenue_growth = base_assumptions['revenue_growth']
    ebit_margin = base_assumptions['ebit_margin']
    
    # Base case
    result_base = dcf_model(financials, base_assumptions, 'base')
    
    # Bear case: -40% growth, -200bps margin
    assumptions_bear = base_assumptions.copy()
    assumptions_bear['revenue_growth'] = revenue_growth * 0.6
    assumptions_bear['ebit_margin'] = max(0.05, ebit_margin - 0.02)
    result_bear = dcf_model(financials, assumptions_bear, 'bear')
    
    # Bull case: +30% growth, +200bps margin
    assumptions_bull = base_assumptions.copy()
    assumptions_bull['revenue_growth'] = revenue_growth * 1.3
    assumptions_bull['ebit_margin'] = min(0.60, ebit_margin + 0.02)
    result_bull = dcf_model(financials, assumptions_bull, 'bull')
    
    return {
        'bear': result_bear,
        'base': result_base,
        'bull': result_bull
    }
