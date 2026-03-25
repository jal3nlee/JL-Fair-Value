"""
Financial Modeling Prep (FMP) API Integration
Fetches live financial data for DCF valuation
"""
import requests
from typing import Dict, List, Optional
import pandas as pd


class FMPAPIError(Exception):
    """Custom exception for FMP API errors"""
    pass


def fetch_company_profile(ticker: str, api_key: str) -> Optional[Dict]:
    """
    Fetch company profile including current price, market cap, shares
    Uses FMP /stable/ API endpoints (post-August 2025)
    
    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL')
        api_key: FMP API key
        
    Returns:
        Dictionary with profile data or None if error
    """
    # New stable endpoint structure
    url = f"https://financialmodelingprep.com/stable/profile"
    params = {"symbol": ticker, "apikey": api_key}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not data or len(data) == 0:
            raise FMPAPIError(f"No data found for ticker '{ticker}'")
        
        profile = data[0]
        
        # Return in consistent format
        return {
            'symbol': profile.get('symbol'),
            'price': profile.get('price'),
            'companyName': profile.get('companyName'),
            'marketCap': profile.get('marketCap'),
            'sharesOutstanding': profile.get('sharesOutstanding'),
            'exchange': profile.get('exchange')
        }
    
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            raise FMPAPIError(f"Ticker '{ticker}' not found")
        elif e.response.status_code == 429:
            raise FMPAPIError("API rate limit exceeded. Please try again later.")
        else:
            raise FMPAPIError(f"API error: {str(e)}")
    except requests.RequestException as e:
        raise FMPAPIError(f"Network error: {str(e)}")


def fetch_income_statement(ticker: str, api_key: str, limit: int = 4) -> List[Dict]:
    """
    Fetch income statement data (revenue, EBIT, taxes)
    Uses FMP /stable/ API endpoints (post-August 2025)
    
    Args:
        ticker: Stock ticker symbol
        api_key: FMP API key
        limit: Number of years to fetch
        
    Returns:
        List of income statement dictionaries (most recent first)
    """
    url = f"https://financialmodelingprep.com/stable/income-statement"
    params = {"symbol": ticker, "apikey": api_key, "limit": limit}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not data or len(data) == 0:
            raise FMPAPIError(f"No income statement data for '{ticker}'")
        
        return data
    
    except requests.HTTPError as e:
        raise FMPAPIError(f"Failed to fetch income statement: {str(e)}")
    except requests.RequestException as e:
        raise FMPAPIError(f"Network error: {str(e)}")


def fetch_cash_flow_statement(ticker: str, api_key: str, limit: int = 4) -> List[Dict]:
    """
    Fetch cash flow statement (CAPEX, D&A, FCF)
    Uses FMP /stable/ API endpoints (post-August 2025)
    
    Args:
        ticker: Stock ticker symbol
        api_key: FMP API key
        limit: Number of years to fetch
        
    Returns:
        List of cash flow dictionaries (most recent first)
    """
    url = f"https://financialmodelingprep.com/stable/cash-flow-statement"
    params = {"symbol": ticker, "apikey": api_key, "limit": limit}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not data or len(data) == 0:
            raise FMPAPIError(f"No cash flow data for '{ticker}'")
        
        return data
    
    except requests.HTTPError as e:
        raise FMPAPIError(f"Failed to fetch cash flow: {str(e)}")
    except requests.RequestException as e:
        raise FMPAPIError(f"Network error: {str(e)}")


def fetch_balance_sheet(ticker: str, api_key: str, limit: int = 4) -> List[Dict]:
    """
    Fetch balance sheet (assets, liabilities, debt, cash)
    Uses FMP /stable/ API endpoints (post-August 2025)
    
    Args:
        ticker: Stock ticker symbol
        api_key: FMP API key
        limit: Number of years to fetch
        
    Returns:
        List of balance sheet dictionaries (most recent first)
    """
    url = f"https://financialmodelingprep.com/stable/balance-sheet-statement"
    params = {"symbol": ticker, "apikey": api_key, "limit": limit}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not data or len(data) == 0:
            raise FMPAPIError(f"No balance sheet data for '{ticker}'")
        
        return data
    
    except requests.HTTPError as e:
        raise FMPAPIError(f"Failed to fetch balance sheet: {str(e)}")
    except requests.RequestException as e:
        raise FMPAPIError(f"Network error: {str(e)}")


def fetch_key_metrics(ticker: str, api_key: str, limit: int = 4) -> List[Dict]:
    """
    Fetch key metrics (margins, ratios, multiples)
    Uses FMP /stable/ API endpoints (post-August 2025)
    
    Args:
        ticker: Stock ticker symbol
        api_key: FMP API key
        limit: Number of years to fetch
        
    Returns:
        List of metrics dictionaries (most recent first)
    """
    url = f"https://financialmodelingprep.com/stable/key-metrics"
    params = {"symbol": ticker, "apikey": api_key, "limit": limit}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not data or len(data) == 0:
            raise FMPAPIError(f"No metrics data for '{ticker}'")
        
        return data
    
    except requests.HTTPError as e:
        raise FMPAPIError(f"Failed to fetch metrics: {str(e)}")
    except requests.RequestException as e:
        raise FMPAPIError(f"Network error: {str(e)}")


def fetch_all_company_data(ticker: str, api_key: str) -> Dict:
    """
    Fetch all financial data needed for DCF valuation
    
    Args:
        ticker: Stock ticker symbol
        api_key: FMP API key
        
    Returns:
        Dictionary containing all financial data
        
    Raises:
        FMPAPIError: If any API call fails
    """
    ticker = ticker.upper().strip()
    
    try:
        # Fetch all data sources
        profile = fetch_company_profile(ticker, api_key)
        income_statements = fetch_income_statement(ticker, api_key)
        cash_flows = fetch_cash_flow_statement(ticker, api_key)
        balance_sheets = fetch_balance_sheet(ticker, api_key)
        metrics = fetch_key_metrics(ticker, api_key)
        
        return {
            'ticker': ticker,
            'profile': profile,
            'income_statements': income_statements,
            'cash_flows': cash_flows,
            'balance_sheets': balance_sheets,
            'metrics': metrics
        }
    
    except FMPAPIError:
        raise
    except Exception as e:
        raise FMPAPIError(f"Unexpected error fetching data for '{ticker}': {str(e)}")


def map_fmp_to_dcf_format(fmp_data: Dict) -> Dict:
    """
    Convert FMP API data to DCF model format (matching SEC parser output)
    
    Args:
        fmp_data: Raw data from fetch_all_company_data()
        
    Returns:
        Dictionary matching the format from sec_parser.extract_financials()
    """
    income_statements = fmp_data['income_statements']
    cash_flows = fmp_data['cash_flows']
    balance_sheets = fmp_data['balance_sheets']
    profile = fmp_data['profile']
    
    # Extract years from income statements
    years = [int(item['calendarYear']) for item in income_statements]
    
    # Helper function to extract values
    def get_values(data_list: List[Dict], field: str) -> List[Optional[float]]:
        """Extract field values, handle missing data"""
        values = []
        for item in data_list:
            value = item.get(field)
            if value is not None and value != 0:
                values.append(float(value))
            else:
                values.append(None)
        return values
    
    # Revenue
    revenue = get_values(income_statements, 'revenue')
    
    # EBIT (Operating Income)
    ebit = get_values(income_statements, 'operatingIncome')
    
    # CAPEX (negative in FMP, need to keep negative)
    capex = get_values(cash_flows, 'capitalExpenditure')
    
    # Depreciation & Amortization
    depreciation = get_values(cash_flows, 'depreciationAndAmortization')
    
    # Income Tax
    income_tax = get_values(income_statements, 'incomeTaxExpense')
    
    # Pre-tax Income
    pretax_income = get_values(income_statements, 'incomeBeforeTax')
    
    # Balance sheet items
    current_assets = get_values(balance_sheets, 'totalCurrentAssets')
    current_liabilities = get_values(balance_sheets, 'totalCurrentLiabilities')
    cash_values = get_values(balance_sheets, 'cashAndCashEquivalents')
    short_term_debt = get_values(balance_sheets, 'shortTermDebt')
    long_term_debt = get_values(balance_sheets, 'longTermDebt')
    
    # Calculate Net Working Capital
    nwc = []
    for i in range(len(years)):
        ca = current_assets[i]
        cl = current_liabilities[i]
        cash_val = cash_values[i]
        std = short_term_debt[i] if short_term_debt[i] else 0
        
        if ca and cl and cash_val:
            nwc.append((ca - cash_val) - (cl - std))
        else:
            nwc.append(None)
    
    # Shares outstanding (diluted)
    shares = profile.get('sharesOutstanding', profile.get('numberOfShares'))
    
    # Net Debt (using most recent balance sheet)
    latest_bs = balance_sheets[0]
    ltd = latest_bs.get('longTermDebt', 0) or 0
    std = latest_bs.get('shortTermDebt', 0) or 0
    cash_latest = latest_bs.get('cashAndCashEquivalents', 0) or 0
    net_debt = ltd + std - cash_latest
    
    # Calculate ratios (matching sec_parser logic)
    ratios = calculate_ratios_from_fmp(
        years, revenue, ebit, capex, depreciation,
        income_tax, pretax_income, nwc, net_debt, shares
    )
    
    return {
        'years': years,
        'Revenue': revenue,
        'EBIT': ebit,
        'CAPEX': capex,
        'Depreciation': depreciation,
        'IncomeTax': income_tax,
        'PreTaxIncome': pretax_income,
        'CurrentAssets': current_assets,
        'CurrentLiabilities': current_liabilities,
        'Cash': cash_values,
        'ShortTermDebt': short_term_debt,
        'LongTermDebt': long_term_debt,
        'SharesOutstanding': [shares] * len(years),
        'NWC': nwc,
        'ratios': ratios
    }


def calculate_ratios_from_fmp(
    years: List[int],
    revenue: List[float],
    ebit: List[float],
    capex: List[float],
    depreciation: List[float],
    income_tax: List[float],
    pretax_income: List[float],
    nwc: List[float],
    net_debt: float,
    shares: float
) -> Dict:
    """Calculate financial ratios from FMP data (matches sec_parser logic)"""
    import numpy as np
    
    # Revenue CAGR
    rev_latest = revenue[0]
    rev_3yrs_ago = revenue[3] if len(revenue) > 3 else revenue[-1]
    if rev_latest and rev_3yrs_ago:
        years_diff = years[0] - years[min(3, len(years)-1)]
        revenue_cagr = (rev_latest / rev_3yrs_ago) ** (1 / years_diff) - 1
    else:
        revenue_cagr = None
    
    # Average over last 3 years
    n_years_avg = min(3, len(years))
    
    # EBIT Margin
    ebit_margins = [
        ebit[i] / revenue[i] 
        for i in range(n_years_avg) 
        if ebit[i] and revenue[i]
    ]
    ebit_margin_avg = np.mean(ebit_margins) if ebit_margins else None
    
    # CAPEX Ratio
    capex_ratios = [
        abs(capex[i]) / revenue[i] 
        for i in range(n_years_avg) 
        if capex[i] and revenue[i]
    ]
    capex_ratio_avg = np.mean(capex_ratios) if capex_ratios else None
    
    # D&A Ratio
    da_ratios = [
        depreciation[i] / revenue[i] 
        for i in range(n_years_avg) 
        if depreciation[i] and revenue[i]
    ]
    da_ratio_avg = np.mean(da_ratios) if da_ratios else None
    
    # Tax Rate
    tax_rates = [
        income_tax[i] / pretax_income[i] 
        for i in range(n_years_avg) 
        if income_tax[i] and pretax_income[i] and pretax_income[i] > 0
    ]
    tax_rate_avg = np.mean(tax_rates) if tax_rates else None
    
    # Working Capital Ratio
    wc_ratios = []
    for i in range(min(3, len(years) - 1)):
        nwc_curr = nwc[i]
        nwc_prev = nwc[i + 1]
        rev_curr = revenue[i]
        rev_prev = revenue[i + 1]
        if nwc_curr and nwc_prev and rev_curr and rev_prev:
            delta_nwc = nwc_curr - nwc_prev
            delta_rev = rev_curr - rev_prev
            if delta_rev != 0:
                wc_ratios.append(delta_nwc / delta_rev)
    wc_ratio_avg = np.mean(wc_ratios) if wc_ratios else None
    
    return {
        'revenue_cagr': revenue_cagr,
        'ebit_margin': ebit_margin_avg,
        'capex_ratio': capex_ratio_avg,
        'da_ratio': da_ratio_avg,
        'tax_rate': tax_rate_avg,
        'wc_ratio': wc_ratio_avg,
        'net_debt': net_debt,
        'shares_diluted': shares
    }
