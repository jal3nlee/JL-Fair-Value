"""
SEC 10-K iXBRL Parser
Extracts financial data from SEC HTML filings
"""
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
from bs4 import XMLParsedAsHTMLWarning
from datetime import datetime
from typing import Dict, List, Optional
import warnings

# Suppress XML parser warning
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


# Configuration constants
ANNUAL_MIN_DAYS = 330
ANNUAL_MAX_DAYS = 400

METRIC_DEFINITIONS = {
    'Revenue': [
        'us-gaap:Revenues',
        'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax',
        'us-gaap:SalesRevenueNet',
        'us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax'
    ],
    'EBIT': [
        'us-gaap:OperatingIncomeLoss',
        'us-gaap:IncomeLossFromOperations'
    ],
    'CAPEX': [
        'us-gaap:PaymentsToAcquirePropertyPlantAndEquipment',
        'us-gaap:PaymentsToAcquirePropertyPlantAndEquipmentAndIntangibleAssets',
        'us-gaap:PaymentsToAcquireProductiveAssets',
        'us-gaap:CapitalExpendituresIncurredButNotYetPaid'
    ],
    'Depreciation': [
        'us-gaap:DepreciationDepletionAndAmortization',
        'us-gaap:DepreciationAndAmortization',
        'us-gaap:Depreciation',
        'us-gaap:DepreciationAmortizationAndAccretionNet'
    ],
    'IncomeTax': [
        'us-gaap:IncomeTaxExpenseBenefit',
        'us-gaap:IncomeTaxesPaid',
        'us-gaap:CurrentIncomeTaxExpenseBenefit'
    ],
    'PreTaxIncome': [
        'us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest',
        'us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments',
        'us-gaap:IncomeLossBeforeIncomeTaxes'
    ],
    'CurrentAssets': [
        'us-gaap:AssetsCurrent',
        'us-gaap:AssetsCurrentAbstract'
    ],
    'CurrentLiabilities': [
        'us-gaap:LiabilitiesCurrent',
        'us-gaap:LiabilitiesCurrentAbstract'
    ],
    'Cash': [
        'us-gaap:CashAndCashEquivalentsAtCarryingValue',
        'us-gaap:Cash',
        'us-gaap:CashCashEquivalentsAndShortTermInvestments'
    ],
    'ShortTermDebt': [
        'us-gaap:DebtCurrent',
        'us-gaap:ShortTermBorrowings',
        'us-gaap:LongTermDebtCurrent'
    ],
    'LongTermDebt': [
        'us-gaap:LongTermDebt',
        'us-gaap:LongTermDebtNoncurrent',
        'us-gaap:LongTermDebtAndCapitalLeaseObligations'
    ],
    'SharesOutstanding': [
        'us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding',
        'us-gaap:WeightedAverageNumberOfSharesOutstandingDiluted',
        'us-gaap:CommonStockSharesOutstanding'
    ]
}


def parse_value(text: str, scale: str) -> Optional[float]:
    """Parse XBRL numeric value with scale"""
    try:
        cleaned = text.replace(',', '').replace('(', '-').replace(')', '').strip()
        if not cleaned or cleaned in ['-', '—', '']:
            return None
        value = float(cleaned)
        if scale and scale.lstrip('-').isdigit():
            value *= (10 ** int(scale))
        return value
    except:
        return None


def calculate_duration_days(start: pd.Timestamp, end: pd.Timestamp) -> Optional[int]:
    """Calculate duration in days between two dates"""
    if pd.isna(start) or pd.isna(end):
        return None
    return (end - start).days


def extract_financials(html_content: str) -> Dict:
    """
    Extract financial data from SEC 10-K HTML filing
    
    Args:
        html_content: Raw HTML content from 10-K filing
        
    Returns:
        Dictionary containing extracted financial data and calculated ratios
    """
    soup = BeautifulSoup(html_content, 'lxml')
    
    # Extract XBRL facts
    facts_raw = []
    for tag in soup.find_all(['ix:nonfraction', 'ix:nonFraction'], recursive=True):
        facts_raw.append({
            'concept': tag.get('name', ''),
            'contextRef': tag.get('contextref', ''),
            'scale': tag.get('scale', '0'),
            'text': tag.get_text(strip=True)
        })
    
    # Extract contexts
    contexts = {}
    for ctx_tag in soup.find_all('xbrli:context'):
        ctx_id = ctx_tag.get('id', '')
        period = ctx_tag.find('xbrli:period')
        if not period:
            continue
            
        ctx_data = {'id': ctx_id}
        
        # Duration period
        start_tag = period.find('xbrli:startdate')
        end_tag = period.find('xbrli:enddate')
        if start_tag and end_tag:
            ctx_data['startDate'] = start_tag.get_text(strip=True)
            ctx_data['endDate'] = end_tag.get_text(strip=True)
            ctx_data['period_type'] = 'duration'
        
        # Instant period
        instant_tag = period.find('xbrli:instant')
        if instant_tag:
            ctx_data['instant'] = instant_tag.get_text(strip=True)
            ctx_data['period_type'] = 'instant'
        
        # Check for dimensions (segment data)
        entity = ctx_tag.find('xbrli:entity')
        has_dimensions = False
        if entity:
            segment = entity.find('xbrli:segment')
            if segment and segment.find_all('xbrldi:explicitmember'):
                has_dimensions = True
        ctx_data['has_dimensions'] = has_dimensions
        
        contexts[ctx_id] = ctx_data
    
    # Build facts dataframe
    facts_df = pd.DataFrame(facts_raw)
    facts_df['context_data'] = facts_df['contextRef'].map(contexts)
    facts_df = facts_df[facts_df['context_data'].notna()].copy()
    
    # Expand context data
    context_expanded = pd.json_normalize(facts_df['context_data'])
    facts_df = pd.concat([facts_df.reset_index(drop=True), context_expanded], axis=1)
    facts_df.drop('context_data', axis=1, inplace=True)
    
    # Parse values
    facts_df['value'] = facts_df.apply(lambda r: parse_value(r['text'], r['scale']), axis=1)
    
    # Convert dates
    for col in ['startDate', 'endDate', 'instant']:
        if col in facts_df.columns:
            facts_df[col] = pd.to_datetime(facts_df[col], errors='coerce')
    
    # Filter to annual periods
    duration_facts = facts_df[facts_df['period_type'] == 'duration'].copy()
    duration_facts['duration_days'] = duration_facts.apply(
        lambda r: calculate_duration_days(r['startDate'], r['endDate']), axis=1
    )
    
    annual_duration = duration_facts[
        (duration_facts['duration_days'] >= ANNUAL_MIN_DAYS) &
        (duration_facts['duration_days'] <= ANNUAL_MAX_DAYS) &
        (duration_facts['has_dimensions'] == False)
    ].copy()
    
    instant_facts = facts_df[
        (facts_df['period_type'] == 'instant') &
        (facts_df['has_dimensions'] == False)
    ].copy()
    
    filtered_facts = pd.concat([annual_duration, instant_facts], ignore_index=True)
    
    # Extract each metric
    def extract_metric(concept_list: List[str]) -> Dict[int, float]:
        metric_df = filtered_facts[filtered_facts['concept'].isin(concept_list)].copy()
        if metric_df.empty:
            return {}
        
        is_duration = metric_df['period_type'].iloc[0] == 'duration'
        
        if is_duration:
            metric_df = metric_df[metric_df['endDate'].notna()].copy()
            metric_df['fiscal_year'] = metric_df['endDate'].dt.year
            metric_df = metric_df.sort_values('endDate', ascending=False)
            metric_df = metric_df.drop_duplicates(subset=['fiscal_year'], keep='first')
        else:
            metric_df = metric_df[metric_df['instant'].notna()].copy()
            metric_df['fiscal_year'] = metric_df['instant'].dt.year
            metric_df = metric_df.sort_values('instant', ascending=False)
            metric_df = metric_df.drop_duplicates(subset=['fiscal_year'], keep='first')
        
        metric_df = metric_df[metric_df['value'].notna()]
        return dict(zip(metric_df['fiscal_year'], metric_df['value']))
    
    financials = {}
    for metric_name, concept_list in METRIC_DEFINITIONS.items():
        financials[metric_name] = extract_metric(concept_list)
    
    # Get 4 most recent years
    all_years = set()
    for metric_dict in financials.values():
        all_years.update(metric_dict.keys())
    years_sorted = sorted(list(all_years), reverse=True)[:4]
    
    # Build result dictionary
    result = {}
    for metric_name in METRIC_DEFINITIONS.keys():
        result[metric_name] = [financials[metric_name].get(year) for year in years_sorted]
    result['years'] = years_sorted
    
    # Calculate Net Working Capital
    result['NWC'] = []
    for i in range(len(years_sorted)):
        ca = result['CurrentAssets'][i]
        cl = result['CurrentLiabilities'][i]
        cash = result['Cash'][i]
        std = result['ShortTermDebt'][i] if result['ShortTermDebt'][i] else 0
        if ca and cl and cash:
            result['NWC'].append((ca - cash) - (cl - std))
        else:
            result['NWC'].append(None)
    
    # Calculate ratios
    result['ratios'] = calculate_ratios(result, years_sorted)
    
    return result


def calculate_ratios(result: Dict, years_sorted: List[int]) -> Dict:
    """Calculate financial ratios from extracted data"""
    
    # Revenue CAGR
    rev_latest = result['Revenue'][0]
    rev_3yrs_ago = result['Revenue'][3] if len(result['Revenue']) > 3 else result['Revenue'][-1]
    if rev_latest and rev_3yrs_ago:
        years_diff = years_sorted[0] - years_sorted[min(3, len(years_sorted)-1)]
        revenue_cagr = (rev_latest / rev_3yrs_ago) ** (1 / years_diff) - 1
    else:
        revenue_cagr = None
    
    # Average metrics over last 3 years
    n_years_avg = min(3, len(years_sorted))
    
    # EBIT Margin
    ebit_margins = [
        result['EBIT'][i] / result['Revenue'][i] 
        for i in range(n_years_avg) 
        if result['EBIT'][i] and result['Revenue'][i]
    ]
    ebit_margin_avg = np.mean(ebit_margins) if ebit_margins else None
    
    # CAPEX Ratio
    capex_ratios = [
        abs(result['CAPEX'][i]) / result['Revenue'][i] 
        for i in range(n_years_avg) 
        if result['CAPEX'][i] and result['Revenue'][i]
    ]
    capex_ratio_avg = np.mean(capex_ratios) if capex_ratios else None
    
    # D&A Ratio
    da_ratios = [
        result['Depreciation'][i] / result['Revenue'][i] 
        for i in range(n_years_avg) 
        if result['Depreciation'][i] and result['Revenue'][i]
    ]
    da_ratio_avg = np.mean(da_ratios) if da_ratios else None
    
    # Tax Rate
    tax_rates = [
        result['IncomeTax'][i] / result['PreTaxIncome'][i] 
        for i in range(n_years_avg) 
        if result['IncomeTax'][i] and result['PreTaxIncome'][i] and result['PreTaxIncome'][i] > 0
    ]
    tax_rate_avg = np.mean(tax_rates) if tax_rates else None
    
    # Working Capital Ratio
    wc_ratios = []
    for i in range(min(3, len(years_sorted) - 1)):
        nwc_curr = result['NWC'][i]
        nwc_prev = result['NWC'][i + 1]
        rev_curr = result['Revenue'][i]
        rev_prev = result['Revenue'][i + 1]
        if nwc_curr and nwc_prev and rev_curr and rev_prev:
            delta_nwc = nwc_curr - nwc_prev
            delta_rev = rev_curr - rev_prev
            if delta_rev != 0:
                wc_ratios.append(delta_nwc / delta_rev)
    wc_ratio_avg = np.mean(wc_ratios) if wc_ratios else None
    
    # Net Debt
    ltd = result['LongTermDebt'][0] if result['LongTermDebt'][0] else 0
    std = result['ShortTermDebt'][0] if result['ShortTermDebt'][0] else 0
    cash = result['Cash'][0] if result['Cash'][0] else 0
    net_debt = ltd + std - cash
    
    shares = result['SharesOutstanding'][0]
    
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
