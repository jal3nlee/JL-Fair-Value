"""
Reverse DCF Analysis
Solve for market-implied growth rates given a stock price
"""
from typing import Dict, Tuple
from .dcf_engine import dcf_model


def reverse_dcf_growth_solver(
    market_price: float,
    financials: Dict,
    base_assumptions: Dict,
    max_iterations: int = 100
) -> Tuple[float, float]:
    """
    Solve for the revenue growth rate that produces the target market price
    
    Args:
        market_price: Current stock price
        financials: Historical financial data
        base_assumptions: Base case assumptions (all except revenue_growth)
        max_iterations: Maximum solver iterations
        
    Returns:
        Tuple of (implied_growth_rate, converged_price)
    """
    min_growth = -0.05
    max_growth = 0.50
    
    best_diff = float('inf')
    best_growth = None
    best_price = None
    
    for i in range(max_iterations):
        mid_growth = (min_growth + max_growth) / 2
        test_assumptions = base_assumptions.copy()
        test_assumptions['revenue_growth'] = mid_growth
        
        try:
            result = dcf_model(financials, test_assumptions, 'reverse')
            model_price = result['price_per_share_avg']
            
            diff = abs(model_price - market_price)
            if diff < best_diff:
                best_diff = diff
                best_growth = mid_growth
                best_price = model_price
            
            # Converged within $0.10
            if diff < 0.10:
                return best_growth, best_price
            
            # Binary search
            if model_price > market_price:
                max_growth = mid_growth
            else:
                min_growth = mid_growth
                
        except:
            max_growth = mid_growth
    
    return best_growth, best_price


def calculate_implied_metrics(
    market_price: float,
    financials: Dict,
    base_assumptions: Dict
) -> Dict:
    """
    Calculate full reverse DCF analysis with interpretation
    
    Args:
        market_price: Current stock price
        financials: Historical financial data
        base_assumptions: Base case assumptions
        
    Returns:
        Dictionary with implied growth, base comparison, and interpretation
    """
    # Solve for implied growth
    implied_growth, converged_price = reverse_dcf_growth_solver(
        market_price, financials, base_assumptions
    )
    
    # Calculate base case for comparison
    base_result = dcf_model(financials, base_assumptions, 'base')
    base_price = base_result['price_per_share_avg']
    base_growth = base_assumptions['revenue_growth']
    
    # Determine interpretation
    growth_diff = implied_growth - base_growth
    
    if implied_growth > 0.30:
        interpretation = "WARNING: Market price implies extremely high growth (>30%)"
    elif implied_growth < 0:
        interpretation = "WARNING: Market price implies negative growth"
    elif growth_diff > 0.05:
        interpretation = f"Market is pricing in {growth_diff:.1%} HIGHER growth than base case"
    elif growth_diff < -0.05:
        interpretation = f"Market is pricing in {abs(growth_diff):.1%} LOWER growth than base case"
    else:
        interpretation = "Market is approximately aligned with base case growth"
    
    return {
        'implied_growth': implied_growth,
        'converged_price': converged_price,
        'base_growth': base_growth,
        'base_price': base_price,
        'growth_difference': growth_diff,
        'price_difference': market_price - base_price,
        'interpretation': interpretation,
        'assumptions_held_constant': {
            k: v for k, v in base_assumptions.items() 
            if k != 'revenue_growth'
        }
    }
