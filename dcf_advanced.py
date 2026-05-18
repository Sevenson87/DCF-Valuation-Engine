#!/usr/bin/env python3
"""
Advanced DCF (Discounted Cash Flow) Valuation Model
====================================================
A comprehensive DCF analysis tool with professional HTML reporting.

Usage:
    python dcf_advanced.py              # interactive mode
    python dcf_advanced.py AAPL         # direct analysis
    python dcf_advanced.py AAPL NVDA    # batch mode
"""

import sys
import io
# Force UTF-8 on Windows consoles (cp1252 crashes on box-drawing chars)
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
import os

warnings.filterwarnings('ignore')

# ============================================================================
# CONFIGURATION & CONSTANTS
# ============================================================================

# Risk-free rate (10Y Treasury Yield - update as needed)
RISK_FREE_RATE = 0.045  # 4.5%

# Market risk premium (historical average)
MARKET_RISK_PREMIUM = 0.055  # 5.5%

# Default terminal growth rate
DEFAULT_TERMINAL_GROWTH = 0.025  # 2.5%

# Projection period
DEFAULT_PROJECTION_YEARS = 5

# Color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


# ============================================================================
# DATA FETCHING & VALIDATION
# ============================================================================

class StockDataFetcher:
    """Handles all data fetching and validation from Yahoo Finance."""

    def __init__(self, ticker: str):
        self.ticker = ticker.upper()
        self.stock = None
        self.info = {}
        self.cash_flow = None
        self.balance_sheet = None
        self.income_stmt = None
        self.historical_prices = None

    def fetch_all_data(self) -> bool:
        """Fetch all required data for DCF analysis."""
        print(f"\n{Colors.CYAN}[INFO] Fetching data for {self.ticker}...{Colors.ENDC}")

        try:
            self.stock = yf.Ticker(self.ticker)
            self.info = self.stock.info

            # yfinance v0.2+ dropped 'regularMarketPrice' — validate via multiple fallbacks
            price = (self.info.get('currentPrice')
                     or self.info.get('regularMarketPrice')
                     or self.info.get('previousClose'))
            if not self.info or price is None:
                print(f"{Colors.FAIL}[ERROR] Invalid ticker or no price data for {self.ticker}{Colors.ENDC}")
                return False

            # Fetch financial statements
            self.cash_flow = self.stock.cashflow
            self.balance_sheet = self.stock.balance_sheet
            self.income_stmt = self.stock.income_stmt
            self.historical_prices = self.stock.history(period="5y")

            if self.cash_flow is None or self.cash_flow.empty:
                print(f"{Colors.FAIL}[ERROR] No cash flow data for {self.ticker} (ETFs and some foreign stocks not supported){Colors.ENDC}")
                return False

            print(f"{Colors.GREEN}[OK] Data fetched successfully{Colors.ENDC}")
            return True

        except Exception as e:
            print(f"{Colors.FAIL}[ERROR] Failed to fetch data: {str(e)}{Colors.ENDC}")
            return False

    def get_company_name(self) -> str:
        """Get company name."""
        return self.info.get('longName', self.info.get('shortName', self.ticker))

    def get_current_price(self) -> float:
        """Get current stock price."""
        return (self.info.get('currentPrice')
                or self.info.get('regularMarketPrice')
                or self.info.get('previousClose')
                or 0)

    def get_shares_outstanding(self) -> float:
        """Get shares outstanding."""
        return self.info.get('sharesOutstanding', 0)

    def get_market_cap(self) -> float:
        """Get market capitalization."""
        return self.info.get('marketCap', 0)

    def get_beta(self) -> float:
        """Get stock beta (default to 1.0 if not available)."""
        beta = self.info.get('beta', 1.0)
        return beta if beta and beta > 0 else 1.0

    def get_total_debt(self) -> float:
        """Get total debt from balance sheet."""
        try:
            if self.balance_sheet is not None and not self.balance_sheet.empty:
                debt_keys = ['Total Debt', 'Long Term Debt', 'Short Long Term Debt']
                for key in debt_keys:
                    if key in self.balance_sheet.index:
                        val = self.balance_sheet.loc[key].iloc[0]
                        if pd.notna(val):
                            return float(val)
        except:
            pass
        return self.info.get('totalDebt', 0) or 0

    def get_cash_and_equivalents(self) -> float:
        """Get cash and cash equivalents."""
        try:
            if self.balance_sheet is not None and not self.balance_sheet.empty:
                cash_keys = ['Cash And Cash Equivalents', 'Cash Cash Equivalents And Short Term Investments']
                for key in cash_keys:
                    if key in self.balance_sheet.index:
                        val = self.balance_sheet.loc[key].iloc[0]
                        if pd.notna(val):
                            return float(val)
        except:
            pass
        return self.info.get('totalCash', 0) or 0

    def get_interest_expense(self) -> float:
        """Get interest expense for cost of debt calculation."""
        try:
            if self.income_stmt is not None and not self.income_stmt.empty:
                if 'Interest Expense' in self.income_stmt.index:
                    val = self.income_stmt.loc['Interest Expense'].iloc[0]
                    if pd.notna(val):
                        return abs(float(val))
        except:
            pass
        return 0

    def get_tax_rate(self) -> float:
        """Calculate effective tax rate."""
        try:
            if self.income_stmt is not None and not self.income_stmt.empty:
                if 'Tax Provision' in self.income_stmt.index and 'Pretax Income' in self.income_stmt.index:
                    tax = self.income_stmt.loc['Tax Provision'].iloc[0]
                    pretax = self.income_stmt.loc['Pretax Income'].iloc[0]
                    if pd.notna(tax) and pd.notna(pretax) and pretax > 0:
                        rate = abs(float(tax)) / float(pretax)
                        return min(max(rate, 0.1), 0.4)  # Clamp between 10% and 40%
        except:
            pass
        return 0.21  # Default US corporate tax rate

    def get_historical_fcf(self) -> pd.Series:
        """Get historical Free Cash Flow data."""
        try:
            if 'Free Cash Flow' in self.cash_flow.index:
                return self.cash_flow.loc['Free Cash Flow'].dropna()
            else:
                # Calculate FCF manually
                operating_cf = self.cash_flow.loc['Operating Cash Flow']
                capex = self.cash_flow.loc['Capital Expenditure']
                return (operating_cf + capex).dropna()  # CapEx is negative
        except:
            return pd.Series()

    def get_latest_fcf(self) -> float:
        """Get the most recent Free Cash Flow."""
        fcf_series = self.get_historical_fcf()
        if not fcf_series.empty:
            return float(fcf_series.iloc[0])
        return 0

    def get_revenue(self) -> float:
        """Get latest revenue."""
        try:
            if self.income_stmt is not None and not self.income_stmt.empty:
                if 'Total Revenue' in self.income_stmt.index:
                    return float(self.income_stmt.loc['Total Revenue'].iloc[0])
        except:
            pass
        return self.info.get('totalRevenue', 0) or 0

    def get_sector(self) -> str:
        """Get company sector."""
        return self.info.get('sector', 'Unknown')

    def get_industry(self) -> str:
        """Get company industry."""
        return self.info.get('industry', 'Unknown')

    def get_market_multiples(self) -> dict:
        """Get key market valuation multiples."""
        price = self.get_current_price()
        fcf = self.get_latest_fcf()
        shares = self.get_shares_outstanding()
        market_cap = self.get_market_cap()

        pe = self.info.get('trailingPE') or self.info.get('forwardPE')
        forward_pe = self.info.get('forwardPE')
        ev_ebitda = self.info.get('enterpriseToEbitda')
        price_to_book = self.info.get('priceToBook')

        price_to_fcf = None
        if fcf and fcf > 0 and shares and shares > 0:
            fcf_per_share = fcf / shares
            if fcf_per_share > 0:
                price_to_fcf = price / fcf_per_share

        market_cap_to_fcf = None
        if fcf and fcf > 0 and market_cap > 0:
            market_cap_to_fcf = market_cap / fcf

        return {
            'trailing_pe': pe,
            'forward_pe': forward_pe,
            'ev_ebitda': ev_ebitda,
            'price_to_book': price_to_book,
            'price_to_fcf': price_to_fcf,
            'market_cap_to_fcf': market_cap_to_fcf,
        }


# ============================================================================
# WACC CALCULATION
# ============================================================================

class WACCCalculator:
    """Calculates Weighted Average Cost of Capital using CAPM."""

    def __init__(self, data_fetcher: StockDataFetcher):
        self.data = data_fetcher

    def calculate_cost_of_equity(self) -> float:
        """
        Calculate Cost of Equity using CAPM.
        Ke = Rf + Beta * (Rm - Rf)
        """
        beta = self.data.get_beta()
        cost_of_equity = RISK_FREE_RATE + beta * MARKET_RISK_PREMIUM
        return cost_of_equity

    def calculate_cost_of_debt(self) -> float:
        """
        Calculate Cost of Debt.
        Kd = Interest Expense / Total Debt
        """
        total_debt = self.data.get_total_debt()
        interest_expense = self.data.get_interest_expense()

        if total_debt > 0 and interest_expense > 0:
            cost_of_debt = interest_expense / total_debt
            return min(max(cost_of_debt, 0.02), 0.15)  # Clamp between 2% and 15%

        # Default based on credit quality (rough estimate)
        return 0.05  # 5% default

    def calculate_wacc(self) -> dict:
        """
        Calculate WACC.
        WACC = (E/V) * Ke + (D/V) * Kd * (1 - T)
        """
        market_cap = self.data.get_market_cap()
        total_debt = self.data.get_total_debt()

        # Enterprise Value components
        equity_value = market_cap
        debt_value = total_debt
        total_value = equity_value + debt_value

        if total_value <= 0:
            total_value = equity_value if equity_value > 0 else 1

        # Weights
        weight_equity = equity_value / total_value
        weight_debt = debt_value / total_value

        # Costs
        cost_of_equity = self.calculate_cost_of_equity()
        cost_of_debt = self.calculate_cost_of_debt()
        tax_rate = self.data.get_tax_rate()

        # WACC calculation
        wacc = (weight_equity * cost_of_equity) + (weight_debt * cost_of_debt * (1 - tax_rate))

        return {
            'wacc': wacc,
            'cost_of_equity': cost_of_equity,
            'cost_of_debt': cost_of_debt,
            'weight_equity': weight_equity,
            'weight_debt': weight_debt,
            'tax_rate': tax_rate,
            'beta': self.data.get_beta(),
            'risk_free_rate': RISK_FREE_RATE,
            'market_risk_premium': MARKET_RISK_PREMIUM
        }


# ============================================================================
# DCF VALUATION ENGINE
# ============================================================================

class DCFModel:
    """Core DCF valuation model with multi-scenario analysis."""

    def __init__(self, data_fetcher: StockDataFetcher, wacc_data: dict):
        self.data = data_fetcher
        self.wacc_data = wacc_data

    def estimate_growth_rate(self) -> dict:
        """
        Estimate FCF growth rate using a three-tier fallback:
        1. Historical FCF CAGR (if positive and < 100%/year)
        2. Trailing earnings growth from yfinance (with haircut)
        3. Revenue growth as last resort (with larger haircut)
        4. Market-cap defaults if all else fails
        """
        historical_fcf = self.data.get_historical_fcf()

        # 1. Historical FCF CAGR
        historical_growth = None
        if len(historical_fcf) >= 3:
            try:
                first_fcf = historical_fcf.iloc[-1]  # oldest
                last_fcf = historical_fcf.iloc[0]    # most recent
                years = len(historical_fcf) - 1
                if first_fcf > 0 and last_fcf > 0 and years > 0:
                    historical_growth = (last_fcf / first_fcf) ** (1 / years) - 1
            except:
                pass

        # 2. Supplementary growth signals from yfinance
        earnings_growth = self.data.info.get('earningsGrowth')
        revenue_growth = self.data.info.get('revenueGrowth')

        # 3. Choose best available signal
        growth_source = 'market_cap_default'
        if historical_growth is not None and -0.5 < historical_growth < 1.0:
            # Historical FCF CAGR available and plausible (allow up to 100%/yr for high-growth)
            base_growth = historical_growth
            growth_source = 'historical_fcf_cagr'
        elif earnings_growth is not None and 0 < earnings_growth < 2.0:
            # Trailing earnings growth as proxy (apply 70% haircut for FCF conversion)
            base_growth = earnings_growth * 0.70
            growth_source = 'earnings_growth_proxy'
        elif revenue_growth is not None and 0 < revenue_growth < 2.0:
            # Revenue growth as last resort (more conservative 50% haircut)
            base_growth = revenue_growth * 0.50
            growth_source = 'revenue_growth_proxy'
        else:
            # Market cap-based defaults
            market_cap = self.data.get_market_cap()
            if market_cap > 500e9:   # Mega-cap
                base_growth = 0.08
            elif market_cap > 50e9:  # Large-cap
                base_growth = 0.10
            else:                    # Mid/small-cap
                base_growth = 0.15

        # 4. Clamp to sensible range [3%, 40%]
        base_growth = min(max(base_growth, 0.03), 0.40)

        return {
            'bear': base_growth * 0.60,
            'base': base_growth,
            'bull': min(base_growth * 1.40, 0.50),
            'historical': historical_growth,
            'source': growth_source
        }

    def project_fcf(self, initial_fcf: float, growth_rate: float, years: int) -> list:
        """Project Free Cash Flows for the given period."""
        projected = []
        current_fcf = initial_fcf

        for year in range(1, years + 1):
            current_fcf *= (1 + growth_rate)
            projected.append({
                'year': year,
                'fcf': current_fcf,
                'growth_rate': growth_rate
            })

        return projected

    def calculate_terminal_value(self, final_fcf: float, terminal_growth: float, wacc: float) -> float:
        """
        Calculate Terminal Value using Gordon Growth Model.
        TV = FCF * (1 + g) / (WACC - g)
        """
        if wacc <= terminal_growth:
            # Safety check: WACC must be greater than terminal growth
            terminal_growth = wacc - 0.01

        terminal_value = (final_fcf * (1 + terminal_growth)) / (wacc - terminal_growth)
        return terminal_value

    def discount_cash_flows(self, projected_fcf: list, terminal_value: float, wacc: float) -> dict:
        """Discount all cash flows to present value."""
        years = len(projected_fcf)

        discounted_fcfs = []
        for proj in projected_fcf:
            pv = proj['fcf'] / ((1 + wacc) ** proj['year'])
            discounted_fcfs.append({
                'year': proj['year'],
                'fcf': proj['fcf'],
                'pv': pv,
                'discount_factor': 1 / ((1 + wacc) ** proj['year'])
            })

        pv_fcf = sum(d['pv'] for d in discounted_fcfs)
        pv_terminal = terminal_value / ((1 + wacc) ** years)

        return {
            'discounted_fcfs': discounted_fcfs,
            'pv_fcf_total': pv_fcf,
            'terminal_value': terminal_value,
            'pv_terminal': pv_terminal,
            'enterprise_value': pv_fcf + pv_terminal
        }

    def calculate_equity_value(self, enterprise_value: float) -> dict:
        """
        Calculate Equity Value from Enterprise Value.
        Equity Value = EV - Net Debt
        """
        total_debt = self.data.get_total_debt()
        cash = self.data.get_cash_and_equivalents()
        net_debt = total_debt - cash

        equity_value = enterprise_value - net_debt
        shares = self.data.get_shares_outstanding()

        fair_value_per_share = equity_value / shares if shares > 0 else 0

        return {
            'enterprise_value': enterprise_value,
            'total_debt': total_debt,
            'cash': cash,
            'net_debt': net_debt,
            'equity_value': equity_value,
            'shares_outstanding': shares,
            'fair_value_per_share': fair_value_per_share
        }

    def run_dcf(self, growth_rate: float, terminal_growth: float = DEFAULT_TERMINAL_GROWTH,
                years: int = DEFAULT_PROJECTION_YEARS) -> dict:
        """Run complete DCF valuation."""
        wacc = self.wacc_data['wacc']
        initial_fcf = self.data.get_latest_fcf()

        if initial_fcf <= 0:
            return {'error': 'Negative or zero FCF - DCF not applicable'}

        # Project FCF
        projected = self.project_fcf(initial_fcf, growth_rate, years)

        # Calculate Terminal Value
        final_fcf = projected[-1]['fcf']
        terminal_value = self.calculate_terminal_value(final_fcf, terminal_growth, wacc)

        # Discount to present
        dcf_result = self.discount_cash_flows(projected, terminal_value, wacc)

        # Calculate Equity Value
        equity_result = self.calculate_equity_value(dcf_result['enterprise_value'])

        # Current market data
        current_price = self.data.get_current_price()
        market_cap = self.data.get_market_cap()

        # Upside/Downside
        fair_value = equity_result['fair_value_per_share']
        upside = ((fair_value / current_price) - 1) * 100 if current_price > 0 else 0

        return {
            'initial_fcf': initial_fcf,
            'growth_rate': growth_rate,
            'terminal_growth': terminal_growth,
            'wacc': wacc,
            'years': years,
            'projected_fcf': projected,
            **dcf_result,
            **equity_result,
            'current_price': current_price,
            'market_cap': market_cap,
            'upside_percent': upside
        }

    def run_scenarios(self, growth_rates: dict, terminal_growth: float = DEFAULT_TERMINAL_GROWTH,
                      years: int = DEFAULT_PROJECTION_YEARS) -> dict:
        """Run DCF for bear, base, and bull scenarios."""
        scenarios = {}

        scenario_keys = {'bear', 'base', 'bull'}
        for scenario_name, growth_rate in growth_rates.items():
            if scenario_name not in scenario_keys:
                continue
            result = self.run_dcf(growth_rate, terminal_growth, years)
            scenarios[scenario_name] = result

        return scenarios

    def reverse_dcf(self, terminal_growth: float = DEFAULT_TERMINAL_GROWTH,
                    years: int = DEFAULT_PROJECTION_YEARS,
                    model_rate: float = 0.0) -> dict:
        """
        Reverse DCF: find the FCF growth rate that justifies the current market price.
        Uses binary search. Returns the implied rate and a plain-English interpretation.
        """
        current_price = self.data.get_current_price()
        if current_price <= 0:
            return {'feasible': False, 'message': 'No market price available'}

        def fair_value_at(growth_rate):
            result = self.run_dcf(growth_rate, terminal_growth, years)
            if 'error' in result:
                return None
            return result.get('fair_value_per_share', 0)

        # Check bounds: value at 0% growth and at 150% growth
        val_at_zero = fair_value_at(0.0)
        val_at_max  = fair_value_at(1.50)

        if val_at_zero is None:
            return {'feasible': False, 'message': 'Cannot compute DCF (negative FCF?)'}

        if val_at_zero >= current_price:
            return {
                'feasible': True,
                'implied_rate': 0.0,
                'interpretation': 'undervalued',
                'message': 'Undervalued even at 0% FCF growth',
            }

        if val_at_max is not None and val_at_max < current_price:
            return {
                'feasible': False,
                'implied_rate': None,
                'interpretation': 'extreme_premium',
                'message': 'Requires >150% annual FCF growth — market pricing in non-FCF factors (M&A, optionality…)',
            }

        # Binary search for the exact implied growth rate
        low, high = 0.0, 1.50
        for _ in range(80):
            mid = (low + high) / 2.0
            val = fair_value_at(mid)
            if val is None:
                break
            if abs(val - current_price) < 0.05:
                break
            if val < current_price:
                low = mid
            else:
                high = mid

        implied_rate = (low + high) / 2.0
        premium_pct = (implied_rate - model_rate) * 100

        # Interpretation
        if implied_rate < 0.05:
            interp = 'conservative'
        elif implied_rate < 0.15:
            interp = 'moderate'
        elif implied_rate < 0.30:
            interp = 'optimistic'
        elif implied_rate < 0.60:
            interp = 'aggressive'
        else:
            interp = 'very_aggressive'

        interp_labels = {
            'conservative':    'Conservative — easily achievable',
            'moderate':        'Moderate — requires steady execution',
            'optimistic':      'Optimistic — above historical average',
            'aggressive':      'Aggressive — requires strong outperformance',
            'very_aggressive': 'Very Aggressive — rarely sustained at scale',
        }

        return {
            'feasible': True,
            'implied_rate': implied_rate,
            'model_rate': model_rate,
            'growth_premium': premium_pct,
            'interpretation': interp,
            'interpretation_label': interp_labels[interp],
            'message': (
                f'Market prices in {implied_rate*100:.1f}%/yr FCF growth '
                f'(our model uses {model_rate*100:.1f}% — '
                f'gap of {premium_pct:+.1f}pp)'
            ),
        }

    def sensitivity_analysis(self, base_growth: float, base_wacc: float,
                            growth_range: tuple = (-0.02, 0.02), wacc_range: tuple = (-0.02, 0.02),
                            steps: int = 5) -> pd.DataFrame:
        """
        Generate sensitivity analysis matrix.
        Varies growth rate and WACC to show range of fair values.
        """
        growth_rates = np.linspace(base_growth + growth_range[0],
                                   base_growth + growth_range[1], steps)
        wacc_rates = np.linspace(base_wacc + wacc_range[0],
                                 base_wacc + wacc_range[1], steps)

        # Store original WACC
        original_wacc = self.wacc_data['wacc']

        matrix = []
        for gr in growth_rates:
            row = []
            for wr in wacc_rates:
                self.wacc_data['wacc'] = wr
                result = self.run_dcf(gr)
                if 'error' not in result:
                    row.append(result['fair_value_per_share'])
                else:
                    row.append(np.nan)
            matrix.append(row)

        # Restore original WACC
        self.wacc_data['wacc'] = original_wacc

        # Create DataFrame
        df = pd.DataFrame(matrix,
                         index=[f"{r*100:.1f}%" for r in growth_rates],
                         columns=[f"{r*100:.1f}%" for r in wacc_rates])
        df.index.name = 'Growth Rate'
        df.columns.name = 'WACC'

        return df


# ============================================================================
# REPORT GENERATOR
# ============================================================================

class ReportGenerator:
    """Generates professional HTML reports."""

    def __init__(self, data_fetcher: StockDataFetcher, wacc_data: dict,
                 scenarios: dict, sensitivity_df: pd.DataFrame, growth_estimates: dict,
                 reverse_dcf_result: dict = None):
        self.data = data_fetcher
        self.wacc = wacc_data
        self.scenarios = scenarios
        self.sensitivity = sensitivity_df
        self.growth = growth_estimates
        self.reverse_dcf = reverse_dcf_result or {}

    def format_number(self, num: float, decimals: int = 2, is_currency: bool = False,
                      is_percent: bool = False, abbreviate: bool = False) -> str:
        """Format numbers for display."""
        if pd.isna(num) or num is None:
            return "N/A"

        if abbreviate:
            if abs(num) >= 1e12:
                formatted = f"{num/1e12:.{decimals}f}T"
            elif abs(num) >= 1e9:
                formatted = f"{num/1e9:.{decimals}f}B"
            elif abs(num) >= 1e6:
                formatted = f"{num/1e6:.{decimals}f}M"
            elif abs(num) >= 1e3:
                formatted = f"{num/1e3:.{decimals}f}K"
            else:
                formatted = f"{num:.{decimals}f}"
        else:
            formatted = f"{num:,.{decimals}f}"

        if is_currency:
            return f"${formatted}"
        elif is_percent:
            return f"{num*100:.{decimals}f}%"
        return formatted

    def get_recommendation(self) -> tuple:
        """Get investment recommendation based on base case."""
        base = self.scenarios.get('base', {})
        upside = base.get('upside_percent', 0)

        if upside > 30:
            return ('STRONG BUY', '#22c55e', 'Stock appears significantly undervalued')
        elif upside > 10:
            return ('BUY', '#84cc16', 'Stock appears moderately undervalued')
        elif upside > -10:
            return ('HOLD', '#eab308', 'Stock appears fairly valued')
        elif upside > -30:
            return ('SELL', '#f97316', 'Stock appears moderately overvalued')
        else:
            return ('STRONG SELL', '#ef4444', 'Stock appears significantly overvalued')

    def generate_fcf_chart_svg(self) -> str:
        """Generate SVG chart for FCF projection."""
        base = self.scenarios.get('base', {})
        if 'error' in base or 'projected_fcf' not in base:
            return ""

        projected = base['projected_fcf']
        initial_fcf = base['initial_fcf']

        # Prepare data
        years = [0] + [p['year'] for p in projected]
        fcfs = [initial_fcf] + [p['fcf'] for p in projected]

        # Normalize for SVG
        max_fcf = max(fcfs)
        min_fcf = min(0, min(fcfs))
        range_fcf = max_fcf - min_fcf if max_fcf != min_fcf else 1

        width, height = 600, 300
        padding = 60
        chart_width = width - 2 * padding
        chart_height = height - 2 * padding

        # Calculate points
        points = []
        for i, (year, fcf) in enumerate(zip(years, fcfs)):
            x = padding + (i / (len(years) - 1)) * chart_width
            y = padding + chart_height - ((fcf - min_fcf) / range_fcf) * chart_height
            points.append((x, y))

        # Create SVG
        svg = f'''
        <svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
            <defs>
                <linearGradient id="fcfGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" style="stop-color:#3b82f6;stop-opacity:0.3"/>
                    <stop offset="100%" style="stop-color:#3b82f6;stop-opacity:0"/>
                </linearGradient>
            </defs>

            <!-- Background -->
            <rect width="{width}" height="{height}" fill="#f8fafc" rx="8"/>

            <!-- Grid lines -->
        '''

        # Horizontal grid lines
        for i in range(5):
            y = padding + (i / 4) * chart_height
            value = max_fcf - (i / 4) * range_fcf
            svg += f'<line x1="{padding}" y1="{y}" x2="{width-padding}" y2="{y}" stroke="#e2e8f0" stroke-dasharray="4"/>'
            svg += f'<text x="{padding-10}" y="{y+4}" text-anchor="end" font-size="10" fill="#64748b">{self.format_number(value, abbreviate=True)}</text>'

        # Area under line
        area_points = " ".join([f"{x},{y}" for x, y in points])
        area_points += f" {points[-1][0]},{padding+chart_height} {points[0][0]},{padding+chart_height}"
        svg += f'<polygon points="{area_points}" fill="url(#fcfGradient)"/>'

        # Line
        line_points = " ".join([f"{x},{y}" for x, y in points])
        svg += f'<polyline points="{line_points}" fill="none" stroke="#3b82f6" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'

        # Data points
        for i, (x, y) in enumerate(points):
            svg += f'<circle cx="{x}" cy="{y}" r="6" fill="#3b82f6" stroke="white" stroke-width="2"/>'
            svg += f'<text x="{x}" y="{padding+chart_height+20}" text-anchor="middle" font-size="11" fill="#64748b">Year {years[i]}</text>'

        svg += '</svg>'
        return svg

    def generate_sensitivity_table_html(self) -> str:
        """Generate HTML table for sensitivity analysis."""
        if self.sensitivity is None or self.sensitivity.empty:
            return "<p>Sensitivity analysis not available</p>"

        current_price = self.data.get_current_price()

        html = '<table class="sensitivity-table">'
        html += '<thead><tr><th>Growth \\ WACC</th>'
        for col in self.sensitivity.columns:
            html += f'<th>{col}</th>'
        html += '</tr></thead><tbody>'

        for idx, row in self.sensitivity.iterrows():
            html += f'<tr><th>{idx}</th>'
            for val in row:
                if pd.notna(val):
                    color_class = 'positive' if val > current_price else 'negative'
                    html += f'<td class="{color_class}">${val:,.2f}</td>'
                else:
                    html += '<td>N/A</td>'
            html += '</tr>'

        html += '</tbody></table>'
        return html

    def generate_html_report(self, output_path: str) -> str:
        """Generate complete HTML report."""

        # Get all data
        company_name = self.data.get_company_name()
        ticker = self.data.ticker
        sector = self.data.get_sector()
        industry = self.data.get_industry()
        current_price = self.data.get_current_price()
        market_cap = self.data.get_market_cap()
        multiples = self.data.get_market_multiples()

        base = self.scenarios.get('base', {})
        bear = self.scenarios.get('bear', {})
        bull = self.scenarios.get('bull', {})

        # Marge de sécurité (Benjamin Graham) : discount par rapport à la valeur intrinsèque
        base_fv = base.get('fair_value_per_share', 0) or 0
        safety_margin = ((base_fv - current_price) / base_fv * 100) if base_fv > 0 else 0
        sm_positive = safety_margin > 0
        sm_color = "#16A34A" if safety_margin > 20 else "#CA8A04" if safety_margin > 0 else "#DC2626"
        sm_bg    = "#F0FDF4" if safety_margin > 20 else "#FEFCE8" if safety_margin > 0 else "#FEF2F2"
        sm_label = "Undervalued" if safety_margin > 20 else "Fairly Valued" if safety_margin > 0 else "Overvalued"

        recommendation, rec_color, rec_desc = self.get_recommendation()

        # Growth source label for display
        growth_source_labels = {
            'historical_fcf_cagr': 'Historical FCF CAGR',
            'earnings_growth_proxy': 'Earnings Growth (proxied)',
            'revenue_growth_proxy': 'Revenue Growth (proxied)',
            'market_cap_default': 'Market Cap Default',
        }
        growth_source_label = growth_source_labels.get(
            self.growth.get('source', ''), self.growth.get('source', 'N/A'))

        # Market multiples HTML
        def fmt_multiple(val, suffix='x', decimals=1):
            if val is None or (isinstance(val, float) and np.isnan(val)):
                return 'N/A'
            return f'{val:.{decimals}f}{suffix}'

        multiples_html = f'''
            <div class="assumption-item">
                <span class="assumption-label">Trailing P/E</span>
                <span class="assumption-value">{fmt_multiple(multiples.get("trailing_pe"))}</span>
            </div>
            <div class="assumption-item">
                <span class="assumption-label">Forward P/E</span>
                <span class="assumption-value">{fmt_multiple(multiples.get("forward_pe"))}</span>
            </div>
            <div class="assumption-item">
                <span class="assumption-label">EV / EBITDA</span>
                <span class="assumption-value">{fmt_multiple(multiples.get("ev_ebitda"))}</span>
            </div>
            <div class="assumption-item">
                <span class="assumption-label">Price / Book</span>
                <span class="assumption-value">{fmt_multiple(multiples.get("price_to_book"))}</span>
            </div>
            <div class="assumption-item">
                <span class="assumption-label">Market Cap / FCF</span>
                <span class="assumption-value">{fmt_multiple(multiples.get("market_cap_to_fcf"))}</span>
            </div>
        '''

        # Reverse DCF card HTML
        rdcf = self.reverse_dcf
        if rdcf.get('feasible') and rdcf.get('implied_rate') is not None:
            implied_pct   = rdcf['implied_rate'] * 100
            model_pct     = rdcf.get('model_rate', 0) * 100
            gap_pct       = rdcf.get('growth_premium', 0)
            gap_class     = 'positive' if gap_pct >= 0 else 'negative'
            interp_label  = rdcf.get('interpretation_label', '')
            reverse_dcf_html = f'''
            <div class="card wide-card reverse-dcf-card">
                <h3 class="card-title" style="color:#94a3b8; border-bottom-color:#334155;">
                    Reverse DCF — Growth Rate Implied by Market Price
                </h3>
                <p style="color:#94a3b8; font-size:0.9rem; margin-bottom:1.2rem;">
                    To justify the current price of <strong style="color:white">${current_price:,.2f}</strong>,
                    free cash flows must grow at:
                </p>
                <div class="implied-rate">{implied_pct:.1f}%<span style="font-size:1.5rem">/yr</span></div>
                <div class="implied-label">Implied FCF growth rate over {DEFAULT_PROJECTION_YEARS} years</div>
                <div class="rate-comparison">
                    <div class="rate-item">
                        <div class="rate-item-label">Market Implies</div>
                        <div class="rate-item-value implied">{implied_pct:.1f}%</div>
                    </div>
                    <div class="rate-item">
                        <div class="rate-item-label">Our Model Uses</div>
                        <div class="rate-item-value model">{model_pct:.1f}%</div>
                    </div>
                    <div class="rate-item">
                        <div class="rate-item-label">Growth Premium Priced In</div>
                        <div class="rate-item-value gap {gap_class}">{gap_pct:+.1f}pp</div>
                    </div>
                </div>
                <div class="interp-badge">{interp_label}</div>
            </div>
            '''
        elif rdcf.get('interpretation') == 'undervalued':
            reverse_dcf_html = f'''
            <div class="card wide-card reverse-dcf-card">
                <h3 class="card-title" style="color:#94a3b8; border-bottom-color:#334155;">
                    Reverse DCF — Growth Rate Implied by Market Price
                </h3>
                <div class="implied-rate" style="color:#34d399">0%</div>
                <div class="implied-label">Undervalued even at 0% FCF growth</div>
                <div class="interp-badge" style="background:rgba(52,211,153,0.15); border-color:rgba(52,211,153,0.4); color:#6ee7b7;">
                    Strong fundamental value — no growth needed to justify price
                </div>
            </div>
            '''
        else:
            msg = rdcf.get('message', 'Unable to compute implied growth rate')
            reverse_dcf_html = f'''
            <div class="card wide-card reverse-dcf-card">
                <h3 class="card-title" style="color:#94a3b8; border-bottom-color:#334155;">
                    Reverse DCF — Growth Rate Implied by Market Price
                </h3>
                <div style="color:#f87171; font-size:1.1rem; margin-top:0.5rem;">⚠ {msg}</div>
            </div>
            '''

        # Historical FCF
        hist_fcf = self.data.get_historical_fcf()
        hist_fcf_html = ""
        if not hist_fcf.empty:
            for date, val in hist_fcf.items():
                year = date.year if hasattr(date, 'year') else date
                hist_fcf_html += f'<tr><td>{year}</td><td class="{"positive" if val > 0 else "negative"}">{self.format_number(val, is_currency=True, abbreviate=True)}</td></tr>'

        # Generate report date
        report_date = datetime.now().strftime("%B %d, %Y at %H:%M")

        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DCF Valuation Report - {ticker}</title>
    <style>
        :root {{
            --primary: #3b82f6;
            --success: #22c55e;
            --warning: #eab308;
            --danger: #ef4444;
            --gray-50: #f8fafc;
            --gray-100: #f1f5f9;
            --gray-200: #e2e8f0;
            --gray-300: #cbd5e1;
            --gray-500: #64748b;
            --gray-700: #334155;
            --gray-900: #0f172a;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: var(--gray-100);
            color: var(--gray-700);
            line-height: 1.6;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
        }}

        .header {{
            background: linear-gradient(135deg, var(--gray-900) 0%, #1e3a5f 100%);
            color: white;
            padding: 3rem 2rem;
            border-radius: 16px;
            margin-bottom: 2rem;
        }}

        .header h1 {{
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
        }}

        .header .subtitle {{
            color: var(--gray-300);
            font-size: 1.1rem;
        }}

        .header .meta {{
            display: flex;
            gap: 2rem;
            margin-top: 1.5rem;
            flex-wrap: wrap;
        }}

        .header .meta-item {{
            display: flex;
            flex-direction: column;
        }}

        .header .meta-label {{
            font-size: 0.8rem;
            color: var(--gray-300);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .header .meta-value {{
            font-size: 1.25rem;
            font-weight: 600;
        }}

        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}

        .card {{
            background: white;
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}

        .card-title {{
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--gray-500);
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 2px solid var(--gray-100);
        }}

        .recommendation-card {{
            background: linear-gradient(135deg, {rec_color}15 0%, {rec_color}05 100%);
            border-left: 4px solid {rec_color};
        }}

        .recommendation {{
            font-size: 2rem;
            font-weight: 700;
            color: {rec_color};
        }}

        .recommendation-desc {{
            color: var(--gray-500);
            margin-top: 0.5rem;
        }}

        .value-large {{
            font-size: 2rem;
            font-weight: 700;
            color: var(--gray-900);
        }}

        .value-change {{
            font-size: 1rem;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            margin-left: 0.5rem;
        }}

        .positive {{ color: var(--success); }}
        .negative {{ color: var(--danger); }}
        .positive-bg {{ background: #dcfce7; color: #166534; }}
        .negative-bg {{ background: #fee2e2; color: #991b1b; }}

        .scenarios {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 1rem;
            margin-top: 1rem;
        }}

        .scenario {{
            padding: 1rem;
            border-radius: 8px;
            text-align: center;
        }}

        .scenario.bear {{ background: #fef2f2; }}
        .scenario.base {{ background: #f0f9ff; }}
        .scenario.bull {{ background: #f0fdf4; }}

        .scenario-label {{
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 0.5rem;
        }}

        .scenario.bear .scenario-label {{ color: #991b1b; }}
        .scenario.base .scenario-label {{ color: #1e40af; }}
        .scenario.bull .scenario-label {{ color: #166534; }}

        .scenario-value {{
            font-size: 1.5rem;
            font-weight: 700;
        }}

        .scenario.bear .scenario-value {{ color: #dc2626; }}
        .scenario.base .scenario-value {{ color: #2563eb; }}
        .scenario.bull .scenario-value {{ color: #16a34a; }}

        .scenario-upside {{
            font-size: 0.9rem;
            margin-top: 0.25rem;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 1rem;
        }}

        th, td {{
            padding: 0.75rem;
            text-align: left;
            border-bottom: 1px solid var(--gray-200);
        }}

        th {{
            font-weight: 600;
            color: var(--gray-500);
            font-size: 0.85rem;
            text-transform: uppercase;
        }}

        .sensitivity-table {{
            font-size: 0.9rem;
        }}

        .sensitivity-table th {{
            background: var(--gray-50);
            text-align: center;
        }}

        .sensitivity-table td {{
            text-align: center;
        }}

        .chart-container {{
            display: flex;
            justify-content: center;
            margin: 1rem 0;
        }}

        .assumptions {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
        }}

        .assumption-item {{
            display: flex;
            justify-content: space-between;
            padding: 0.5rem 0;
            border-bottom: 1px dotted var(--gray-200);
        }}

        .assumption-label {{
            color: var(--gray-500);
        }}

        .assumption-value {{
            font-weight: 600;
        }}

        .footer {{
            text-align: center;
            padding: 2rem;
            color: var(--gray-500);
            font-size: 0.9rem;
        }}

        .disclaimer {{
            background: #fffbeb;
            border: 1px solid #fcd34d;
            border-radius: 8px;
            padding: 1rem;
            margin-top: 2rem;
            font-size: 0.85rem;
            color: #92400e;
        }}

        .wide-card {{
            grid-column: 1 / -1;
        }}

        .reverse-dcf-card {{
            background: linear-gradient(135deg, #1e3a5f 0%, #0f172a 100%);
            color: white;
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 4px 16px rgba(0,0,0,0.2);
        }}

        .reverse-dcf-card .card-title {{
            color: #94a3b8;
            border-bottom-color: #334155;
        }}

        .implied-rate {{
            font-size: 3rem;
            font-weight: 800;
            color: #60a5fa;
            letter-spacing: -1px;
        }}

        .implied-label {{
            font-size: 0.9rem;
            color: #94a3b8;
            margin-top: 0.25rem;
        }}

        .rate-comparison {{
            display: flex;
            gap: 2rem;
            margin-top: 1.5rem;
            flex-wrap: wrap;
        }}

        .rate-item {{
            flex: 1;
            min-width: 140px;
        }}

        .rate-item-label {{
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #64748b;
            margin-bottom: 0.25rem;
        }}

        .rate-item-value {{
            font-size: 1.4rem;
            font-weight: 700;
        }}

        .rate-item-value.implied {{ color: #60a5fa; }}
        .rate-item-value.model {{ color: #94a3b8; }}
        .rate-item-value.gap.positive {{ color: #34d399; }}
        .rate-item-value.gap.negative {{ color: #f87171; }}

        .interp-badge {{
            display: inline-block;
            margin-top: 1rem;
            padding: 0.4rem 1rem;
            border-radius: 999px;
            font-size: 0.85rem;
            font-weight: 600;
            background: rgba(96, 165, 250, 0.15);
            border: 1px solid rgba(96, 165, 250, 0.4);
            color: #93c5fd;
        }}

        @media print {{
            .container {{ padding: 0; }}
            .card {{ break-inside: avoid; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header class="header">
            <h1>{company_name}</h1>
            <p class="subtitle">{ticker} | {sector} | {industry}</p>
            <div class="meta">
                <div class="meta-item">
                    <span class="meta-label">Current Price</span>
                    <span class="meta-value">${current_price:,.2f}</span>
                </div>
                <div class="meta-item">
                    <span class="meta-label">Market Cap</span>
                    <span class="meta-value">{self.format_number(market_cap, is_currency=True, abbreviate=True)}</span>
                </div>
                <div class="meta-item">
                    <span class="meta-label">Report Date</span>
                    <span class="meta-value">{report_date}</span>
                </div>
            </div>
        </header>

        <div class="grid">
            <!-- Recommendation Card -->
            <div class="card recommendation-card">
                <h3 class="card-title">Investment Recommendation</h3>
                <div class="recommendation">{recommendation}</div>
                <p class="recommendation-desc">{rec_desc}</p>
            </div>

            <!-- Fair Value Card -->
            <div class="card">
                <h3 class="card-title">DCF Fair Value (Base Case)</h3>
                <div>
                    <span class="value-large">${base.get('fair_value_per_share', 0):,.2f}</span>
                    <span class="value-change {'positive-bg' if base.get('upside_percent', 0) > 0 else 'negative-bg'}">
                        {'+' if base.get('upside_percent', 0) > 0 else ''}{base.get('upside_percent', 0):.1f}%
                    </span>
                </div>
                <p style="color: var(--gray-500); margin-top: 0.5rem;">vs Current Price: ${current_price:,.2f}</p>
            </div>

            <!-- Margin of Safety Card -->
            <div class="card" style="border-top: 3px solid {sm_color}">
                <h3 class="card-title">Margin of Safety</h3>
                <div style="background:{sm_bg};border-radius:8px;padding:1rem;text-align:center;margin-top:0.5rem">
                    <div style="font-size:2.2rem;font-weight:800;color:{sm_color}">{safety_margin:+.1f}%</div>
                    <div style="font-size:0.85rem;font-weight:600;color:{sm_color};margin-top:0.2rem">{sm_label}</div>
                </div>
                <p style="color:var(--gray-500);font-size:0.82rem;margin-top:0.75rem;line-height:1.4">
                    (Intrinsic Value − Price) ÷ Intrinsic Value. A positive margin means the stock
                    trades below its DCF fair value — the buffer absorbs estimation error.
                    Graham recommended ≥ 20% for a conservative entry.
                </p>
                <table style="margin-top:0.75rem;font-size:0.85rem">
                    <tr><td style="color:var(--gray-500)">Intrinsic Value (Base)</td>
                        <td style="text-align:right;font-weight:600">${base_fv:,.2f}</td></tr>
                    <tr><td style="color:var(--gray-500)">Current Price</td>
                        <td style="text-align:right;font-weight:600">${current_price:,.2f}</td></tr>
                    <tr><td style="color:var(--gray-500)">Bear-case MoS</td>
                        <td style="text-align:right;font-weight:600">{((bear.get('fair_value_per_share',0) - current_price) / bear.get('fair_value_per_share',1)) * 100 if bear.get('fair_value_per_share',0) > 0 else 0:+.1f}%</td></tr>
                </table>
            </div>

            <!-- Scenario Analysis -->
            <div class="card wide-card">
                <h3 class="card-title">Scenario Analysis - Fair Value per Share</h3>
                <div class="scenarios">
                    <div class="scenario bear">
                        <div class="scenario-label">Bear Case</div>
                        <div class="scenario-value">${bear.get('fair_value_per_share', 0):,.2f}</div>
                        <div class="scenario-upside negative">{bear.get('upside_percent', 0):+.1f}%</div>
                        <div style="font-size: 0.8rem; color: var(--gray-500); margin-top: 0.5rem;">
                            Growth: {self.format_number(self.growth.get('bear', 0), is_percent=True)}
                        </div>
                    </div>
                    <div class="scenario base">
                        <div class="scenario-label">Base Case</div>
                        <div class="scenario-value">${base.get('fair_value_per_share', 0):,.2f}</div>
                        <div class="scenario-upside {'positive' if base.get('upside_percent', 0) > 0 else 'negative'}">{base.get('upside_percent', 0):+.1f}%</div>
                        <div style="font-size: 0.8rem; color: var(--gray-500); margin-top: 0.5rem;">
                            Growth: {self.format_number(self.growth.get('base', 0), is_percent=True)}
                        </div>
                    </div>
                    <div class="scenario bull">
                        <div class="scenario-label">Bull Case</div>
                        <div class="scenario-value">${bull.get('fair_value_per_share', 0):,.2f}</div>
                        <div class="scenario-upside positive">{bull.get('upside_percent', 0):+.1f}%</div>
                        <div style="font-size: 0.8rem; color: var(--gray-500); margin-top: 0.5rem;">
                            Growth: {self.format_number(self.growth.get('bull', 0), is_percent=True)}
                        </div>
                    </div>
                </div>
            </div>

            <!-- Reverse DCF -->
            {reverse_dcf_html}

            <!-- WACC Breakdown -->
            <div class="card">
                <h3 class="card-title">WACC Analysis</h3>
                <div class="value-large">{self.format_number(self.wacc['wacc'], is_percent=True)}</div>
                <table style="margin-top: 1rem;">
                    <tr>
                        <td>Cost of Equity</td>
                        <td style="text-align: right; font-weight: 600;">{self.format_number(self.wacc['cost_of_equity'], is_percent=True)}</td>
                    </tr>
                    <tr>
                        <td>Cost of Debt (after-tax)</td>
                        <td style="text-align: right; font-weight: 600;">{self.format_number(self.wacc['cost_of_debt'] * (1 - self.wacc['tax_rate']), is_percent=True)}</td>
                    </tr>
                    <tr>
                        <td>Weight of Equity</td>
                        <td style="text-align: right; font-weight: 600;">{self.format_number(self.wacc['weight_equity'], is_percent=True)}</td>
                    </tr>
                    <tr>
                        <td>Weight of Debt</td>
                        <td style="text-align: right; font-weight: 600;">{self.format_number(self.wacc['weight_debt'], is_percent=True)}</td>
                    </tr>
                    <tr>
                        <td>Beta</td>
                        <td style="text-align: right; font-weight: 600;">{self.wacc['beta']:.2f}</td>
                    </tr>
                </table>
            </div>

            <!-- Enterprise Value Bridge -->
            <div class="card">
                <h3 class="card-title">Valuation Bridge (Base Case)</h3>
                <table>
                    <tr>
                        <td>PV of FCF (Years 1-{base.get('years', 5)})</td>
                        <td style="text-align: right; font-weight: 600;">{self.format_number(base.get('pv_fcf_total', 0), is_currency=True, abbreviate=True)}</td>
                    </tr>
                    <tr>
                        <td>PV of Terminal Value</td>
                        <td style="text-align: right; font-weight: 600;">{self.format_number(base.get('pv_terminal', 0), is_currency=True, abbreviate=True)}</td>
                    </tr>
                    <tr style="background: var(--gray-50);">
                        <td><strong>Enterprise Value</strong></td>
                        <td style="text-align: right; font-weight: 700;">{self.format_number(base.get('enterprise_value', 0), is_currency=True, abbreviate=True)}</td>
                    </tr>
                    <tr>
                        <td>Less: Net Debt</td>
                        <td style="text-align: right; font-weight: 600;">({self.format_number(base.get('net_debt', 0), is_currency=True, abbreviate=True)})</td>
                    </tr>
                    <tr style="background: var(--gray-50);">
                        <td><strong>Equity Value</strong></td>
                        <td style="text-align: right; font-weight: 700;">{self.format_number(base.get('equity_value', 0), is_currency=True, abbreviate=True)}</td>
                    </tr>
                    <tr>
                        <td>Shares Outstanding</td>
                        <td style="text-align: right; font-weight: 600;">{self.format_number(base.get('shares_outstanding', 0), abbreviate=True)}</td>
                    </tr>
                    <tr style="background: #f0f9ff;">
                        <td><strong>Fair Value / Share</strong></td>
                        <td style="text-align: right; font-weight: 700; color: var(--primary);">${base.get('fair_value_per_share', 0):,.2f}</td>
                    </tr>
                </table>
            </div>

            <!-- FCF Projection Chart -->
            <div class="card wide-card">
                <h3 class="card-title">Free Cash Flow Projection (Base Case)</h3>
                <div class="chart-container">
                    {self.generate_fcf_chart_svg()}
                </div>
            </div>

            <!-- Historical FCF -->
            <div class="card">
                <h3 class="card-title">Historical Free Cash Flow</h3>
                <table>
                    <thead>
                        <tr><th>Year</th><th style="text-align: right;">FCF</th></tr>
                    </thead>
                    <tbody>
                        {hist_fcf_html}
                    </tbody>
                </table>
            </div>

            <!-- Sensitivity Analysis -->
            <div class="card wide-card">
                <h3 class="card-title">Sensitivity Analysis - Fair Value per Share</h3>
                <p style="color: var(--gray-500); margin-bottom: 1rem; font-size: 0.9rem;">
                    How fair value changes with different growth rate and WACC assumptions
                </p>
                {self.generate_sensitivity_table_html()}
                <p style="color: var(--gray-500); margin-top: 0.5rem; font-size: 0.8rem;">
                    Current price: ${current_price:,.2f} | Green = Undervalued | Red = Overvalued
                </p>
            </div>

            <!-- Key Assumptions -->
            <div class="card wide-card">
                <h3 class="card-title">Key Assumptions</h3>
                <div class="assumptions">
                    <div class="assumption-item">
                        <span class="assumption-label">Risk-Free Rate</span>
                        <span class="assumption-value">{self.format_number(RISK_FREE_RATE, is_percent=True)}</span>
                    </div>
                    <div class="assumption-item">
                        <span class="assumption-label">Market Risk Premium</span>
                        <span class="assumption-value">{self.format_number(MARKET_RISK_PREMIUM, is_percent=True)}</span>
                    </div>
                    <div class="assumption-item">
                        <span class="assumption-label">Terminal Growth Rate</span>
                        <span class="assumption-value">{self.format_number(DEFAULT_TERMINAL_GROWTH, is_percent=True)}</span>
                    </div>
                    <div class="assumption-item">
                        <span class="assumption-label">Projection Period</span>
                        <span class="assumption-value">{DEFAULT_PROJECTION_YEARS} years</span>
                    </div>
                    <div class="assumption-item">
                        <span class="assumption-label">Tax Rate</span>
                        <span class="assumption-value">{self.format_number(self.wacc['tax_rate'], is_percent=True)}</span>
                    </div>
                    <div class="assumption-item">
                        <span class="assumption-label">Historical FCF Growth</span>
                        <span class="assumption-value">{self.format_number(self.growth.get('historical'), is_percent=True) if self.growth.get('historical') else 'N/A'}</span>
                    </div>
                    <div class="assumption-item">
                        <span class="assumption-label">Growth Rate Source</span>
                        <span class="assumption-value">{growth_source_label}</span>
                    </div>
                    <div class="assumption-item">
                        <span class="assumption-label">Growth Rate (Base)</span>
                        <span class="assumption-value">{self.format_number(self.growth.get('base', 0), is_percent=True)}</span>
                    </div>
                </div>
            </div>

            <!-- Market Multiples -->
            <div class="card wide-card">
                <h3 class="card-title">Market Valuation Multiples</h3>
                <p style="color: var(--gray-500); margin-bottom: 1rem; font-size: 0.9rem;">
                    Current market pricing context — what the market is implying about future growth
                </p>
                <div class="assumptions">
                    {multiples_html}
                </div>
            </div>
        </div>

        <div class="disclaimer">
            <strong>Disclaimer:</strong> This DCF analysis is for educational and informational purposes only.
            It should not be considered as financial advice. The model relies on assumptions and projections
            that may not reflect actual future performance. Always conduct your own research and consult with
            a qualified financial advisor before making investment decisions.
        </div>

        <footer class="footer">
            <p>Generated by Advanced DCF Valuation Model</p>
            <p>{report_date}</p>
        </footer>
    </div>
</body>
</html>'''

        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)

        return output_path


# ============================================================================
# INTERACTIVE CLI
# ============================================================================

def print_banner():
    """Print welcome banner."""
    banner = f"""
{Colors.CYAN}╔══════════════════════════════════════════════════════════════════╗
║                                                                      ║
║   {Colors.BOLD}    ██████╗  ██████╗███████╗    ███╗   ███╗ ██████╗ ██████╗ ███████╗██╗     {Colors.ENDC}{Colors.CYAN}║
║   {Colors.BOLD}    ██╔══██╗██╔════╝██╔════╝    ████╗ ████║██╔═══██╗██╔══██╗██╔════╝██║     {Colors.ENDC}{Colors.CYAN}║
║   {Colors.BOLD}    ██║  ██║██║     █████╗      ██╔████╔██║██║   ██║██║  ██║█████╗  ██║     {Colors.ENDC}{Colors.CYAN}║
║   {Colors.BOLD}    ██║  ██║██║     ██╔══╝      ██║╚██╔╝██║██║   ██║██║  ██║██╔══╝  ██║     {Colors.ENDC}{Colors.CYAN}║
║   {Colors.BOLD}    ██████╔╝╚██████╗██║         ██║ ╚═╝ ██║╚██████╔╝██████╔╝███████╗███████╗{Colors.ENDC}{Colors.CYAN}║
║   {Colors.BOLD}    ╚═════╝  ╚═════╝╚═╝         ╚═╝     ╚═╝ ╚═════╝ ╚═════╝ ╚══════╝╚══════╝{Colors.ENDC}{Colors.CYAN}║
║                                                                      ║
║           {Colors.GREEN}Advanced Discounted Cash Flow Valuation Tool{Colors.ENDC}{Colors.CYAN}              ║
║                        {Colors.WARNING}v2.0 - Professional Edition{Colors.ENDC}{Colors.CYAN}                  ║
╚══════════════════════════════════════════════════════════════════════╝{Colors.ENDC}
"""
    print(banner)


def get_user_input():
    """Get ticker and optional parameters from user."""
    print(f"\n{Colors.BOLD}Enter Stock Ticker Symbol:{Colors.ENDC}")
    ticker = input(f"{Colors.CYAN}>>> {Colors.ENDC}").strip().upper()

    if not ticker:
        print(f"{Colors.FAIL}[ERROR] No ticker entered. Exiting.{Colors.ENDC}")
        return None, None

    print(f"\n{Colors.BOLD}Use custom parameters? (y/N):{Colors.ENDC}")
    custom = input(f"{Colors.CYAN}>>> {Colors.ENDC}").strip().lower()

    params = {}
    if custom == 'y':
        print(f"\n{Colors.WARNING}Enter parameters (press Enter for default):{Colors.ENDC}")

        # Terminal Growth
        print(f"Terminal Growth Rate (default: {DEFAULT_TERMINAL_GROWTH*100:.1f}%):")
        tg = input(f"{Colors.CYAN}>>> {Colors.ENDC}").strip()
        if tg:
            try:
                params['terminal_growth'] = float(tg.replace('%', '')) / 100
            except:
                pass

        # Projection Years
        print(f"Projection Years (default: {DEFAULT_PROJECTION_YEARS}):")
        years = input(f"{Colors.CYAN}>>> {Colors.ENDC}").strip()
        if years:
            try:
                params['years'] = int(years)
            except:
                pass

    return ticker, params


def run_analysis(ticker: str, params: dict = None):
    """Run complete DCF analysis for given ticker."""
    params = params or {}

    # 1. Fetch Data
    fetcher = StockDataFetcher(ticker)
    if not fetcher.fetch_all_data():
        return False

    # 2. Calculate WACC
    print(f"\n{Colors.CYAN}[INFO] Calculating WACC...{Colors.ENDC}")
    wacc_calc = WACCCalculator(fetcher)
    wacc_data = wacc_calc.calculate_wacc()
    print(f"{Colors.GREEN}[OK] WACC: {wacc_data['wacc']*100:.2f}%{Colors.ENDC}")

    # 3. Initialize DCF Model
    dcf = DCFModel(fetcher, wacc_data)

    # 4. Estimate Growth Rates
    print(f"\n{Colors.CYAN}[INFO] Estimating growth rates...{Colors.ENDC}")
    growth_estimates = dcf.estimate_growth_rate()
    print(f"{Colors.GREEN}[OK] Base Case Growth: {growth_estimates['base']*100:.2f}%{Colors.ENDC}")

    # 5. Run Scenarios
    print(f"\n{Colors.CYAN}[INFO] Running scenario analysis...{Colors.ENDC}")
    terminal_growth = params.get('terminal_growth', DEFAULT_TERMINAL_GROWTH)
    years = params.get('years', DEFAULT_PROJECTION_YEARS)

    scenarios = dcf.run_scenarios(growth_estimates, terminal_growth, years)

    # Check for errors
    if 'error' in scenarios.get('base', {}):
        print(f"{Colors.FAIL}[ERROR] {scenarios['base']['error']}{Colors.ENDC}")
        print(f"{Colors.WARNING}DCF model requires positive Free Cash Flow.{Colors.ENDC}")
        return False

    print(f"{Colors.GREEN}[OK] Scenarios calculated{Colors.ENDC}")

    # 6. Reverse DCF
    print(f"\n{Colors.CYAN}[INFO] Computing reverse DCF (market-implied growth)...{Colors.ENDC}")
    reverse_dcf_result = dcf.reverse_dcf(terminal_growth, years, growth_estimates['base'])
    if reverse_dcf_result.get('feasible') and reverse_dcf_result.get('implied_rate') is not None:
        print(f"{Colors.GREEN}[OK] Market implies {reverse_dcf_result['implied_rate']*100:.1f}%/yr FCF growth{Colors.ENDC}")
    else:
        print(f"{Colors.WARNING}[OK] {reverse_dcf_result.get('message', 'N/A')}{Colors.ENDC}")

    # 7. Sensitivity Analysis
    print(f"\n{Colors.CYAN}[INFO] Generating sensitivity analysis...{Colors.ENDC}")
    sensitivity_df = dcf.sensitivity_analysis(
        growth_estimates['base'],
        wacc_data['wacc']
    )
    print(f"{Colors.GREEN}[OK] Sensitivity matrix generated{Colors.ENDC}")

    # 8. Print Summary to Console
    print_summary(fetcher, wacc_data, scenarios, growth_estimates, reverse_dcf_result)

    # 9. Generate HTML Report
    print(f"\n{Colors.CYAN}[INFO] Generating HTML report...{Colors.ENDC}")
    report_gen = ReportGenerator(fetcher, wacc_data, scenarios, sensitivity_df,
                                 growth_estimates, reverse_dcf_result)

    output_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(output_dir, f"DCF_Report_{ticker}.html")
    report_gen.generate_html_report(output_path)

    print(f"{Colors.GREEN}[OK] Report saved: {output_path}{Colors.ENDC}")

    return True


def print_summary(fetcher, wacc_data, scenarios, growth_estimates, reverse_dcf_result=None):
    """Print summary to console."""
    base = scenarios.get('base', {})
    bear = scenarios.get('bear', {})
    bull = scenarios.get('bull', {})

    company_name = fetcher.get_company_name()
    ticker = fetcher.ticker
    current_price = fetcher.get_current_price()

    base_fv = base.get('fair_value_per_share', 0) or 0
    safety_margin = ((base_fv - current_price) / base_fv * 100) if base_fv > 0 else 0
    sm_color = Colors.GREEN if safety_margin > 20 else Colors.WARNING if safety_margin > 0 else Colors.FAIL

    print(f"""
{Colors.BOLD}{'='*70}
                         VALUATION SUMMARY
{'='*70}{Colors.ENDC}

{Colors.CYAN}Company:{Colors.ENDC} {company_name} ({ticker})
{Colors.CYAN}Current Price:{Colors.ENDC} ${current_price:,.2f}
{Colors.CYAN}WACC:{Colors.ENDC} {wacc_data['wacc']*100:.2f}%

{Colors.BOLD}Scenario Analysis:{Colors.ENDC}
┌─────────────┬───────────────┬─────────────┐
│   Scenario  │   Fair Value  │   Upside    │
├─────────────┼───────────────┼─────────────┤
│ {Colors.FAIL}Bear Case{Colors.ENDC}   │ ${bear.get('fair_value_per_share', 0):>11,.2f} │ {bear.get('upside_percent', 0):>+9.1f}% │
│ {Colors.BLUE}Base Case{Colors.ENDC}   │ ${base.get('fair_value_per_share', 0):>11,.2f} │ {base.get('upside_percent', 0):>+9.1f}% │
│ {Colors.GREEN}Bull Case{Colors.ENDC}   │ ${bull.get('fair_value_per_share', 0):>11,.2f} │ {bull.get('upside_percent', 0):>+9.1f}% │
└─────────────┴───────────────┴─────────────┘

{Colors.BOLD}Margin of Safety (Base Case):{Colors.ENDC} {sm_color}{safety_margin:+.1f}%{Colors.ENDC}
  (Intrinsic ${base_fv:,.2f} − Market ${current_price:,.2f}) / Intrinsic
  Graham threshold: ≥ 20% for a conservative entry point.

{Colors.BOLD}Growth Assumptions:{Colors.ENDC}
  Bear: {growth_estimates['bear']*100:.1f}% | Base: {growth_estimates['base']*100:.1f}% | Bull: {growth_estimates['bull']*100:.1f}%
""")

    # Recommendation
    upside = base.get('upside_percent', 0)
    if upside > 30:
        rec = f"{Colors.GREEN}{Colors.BOLD}STRONG BUY{Colors.ENDC}"
    elif upside > 10:
        rec = f"{Colors.GREEN}BUY{Colors.ENDC}"
    elif upside > -10:
        rec = f"{Colors.WARNING}HOLD{Colors.ENDC}"
    elif upside > -30:
        rec = f"{Colors.FAIL}SELL{Colors.ENDC}"
    else:
        rec = f"{Colors.FAIL}{Colors.BOLD}STRONG SELL{Colors.ENDC}"

    print(f"{Colors.BOLD}Recommendation:{Colors.ENDC} {rec}")

    # Reverse DCF block
    if reverse_dcf_result:
        rdcf = reverse_dcf_result
        print(f"\n{Colors.BOLD}{'─'*70}")
        print(f"  REVERSE DCF — MARKET-IMPLIED GROWTH RATE")
        print(f"{'─'*70}{Colors.ENDC}")
        if rdcf.get('feasible') and rdcf.get('implied_rate') is not None:
            impl  = rdcf['implied_rate'] * 100
            model = rdcf.get('model_rate', 0) * 100
            gap   = rdcf.get('growth_premium', 0)
            interp = rdcf.get('interpretation_label', '')
            gap_color = Colors.GREEN if gap >= 0 else Colors.FAIL
            print(f"  Market implies  : {Colors.CYAN}{Colors.BOLD}{impl:.1f}%/yr FCF growth{Colors.ENDC}")
            print(f"  Our model uses  : {Colors.WARNING}{model:.1f}%/yr{Colors.ENDC}")
            print(f"  Growth premium  : {gap_color}{gap:+.1f}pp priced in by market{Colors.ENDC}")
            print(f"  Assessment      : {interp}")
        else:
            print(f"  {Colors.WARNING}{rdcf.get('message', 'N/A')}{Colors.ENDC}")
        print(f"{Colors.BOLD}{'─'*70}{Colors.ENDC}")

    print(f"{'='*70}")


def main():
    """Main entry point — interactive or CLI batch mode."""
    print_banner()

    # CLI mode: python dcf_advanced.py AAPL NVDA MSFT
    cli_tickers = [a.upper() for a in sys.argv[1:] if not a.startswith('-')]
    if cli_tickers:
        print(f"{Colors.CYAN}[INFO] Batch mode — tickers: {', '.join(cli_tickers)}{Colors.ENDC}")
        for ticker in cli_tickers:
            run_analysis(ticker)
            print()
        return

    # Interactive mode
    while True:
        ticker, params = get_user_input()

        if ticker is None:
            break

        success = run_analysis(ticker, params)

        if success:
            print(f"\n{Colors.BOLD}Analyze another stock? (y/N):{Colors.ENDC}")
            again = input(f"{Colors.CYAN}>>> {Colors.ENDC}").strip().lower()
            if again != 'y':
                break
        else:
            print(f"\n{Colors.WARNING}Try another ticker.{Colors.ENDC}")

    print(f"\n{Colors.CYAN}Thank you for using DCF Model. Goodbye!{Colors.ENDC}\n")


if __name__ == "__main__":
    main()
