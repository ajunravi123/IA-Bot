from crewai.tools import BaseTool
from crewai_tools import FileReadTool, SerperDevTool
import yfinance as yf
from alpha_vantage.timeseries import TimeSeries
from datetime import datetime
import os
import requests
import re
import pandas as pd
from dotenv import load_dotenv
from typing import Any, Optional, Dict, Tuple

load_dotenv()

def format_amount(value, currency="USD"):
    """Format a numeric value into a readable string with currency."""
    if value == "Not Available" or value is None:
        return "Not Available"
    try:
        value = float(value)
        if value >= 1e9:
            return f"{currency} {value / 1e9:.2f} B"  # Billions
        elif value >= 1e6:
            return f"{currency} {value / 1e6:.2f} M"  # Millions
        elif value >= 1e3:
            return f"{currency} {value / 1e3:.2f} K"  # Thousands
        else:
            return f"{currency} {value:.2f}"  # Less than thousands
    except (ValueError, TypeError):
        return str(value)

def format_date(date):
    """Format a date string or Timestamp into DD-MMM-YYYY."""
    if date == "Not Available" or date is None:
        return "Not Available"
    try:
        if isinstance(date, pd.Timestamp):
            return date.strftime("%d-%b-%Y")
        return datetime.strptime(str(date), "%Y-%m-%d").strftime("%d-%b-%Y")
    except (ValueError, TypeError):
        return str(date)

class YFinanceTool(BaseTool):
    name: str = "YahooFinanceDataFetcher"
    description: str = "Fetches financial data from Yahoo Finance for a given ticker symbol."

    def _run(self, ticker: str) -> dict:
        try:
            stock = yf.Ticker(ticker.upper())
            info = stock.info
            if not info or info.get('symbol') is None:
                return {"error": "Company not found. Please check the ticker and try again."}

            balance_sheet = stock.balance_sheet
            income_statement = stock.financials

            if balance_sheet.empty and income_statement.empty:
                return {"error": "Company not found. Please check the ticker and try again."}

            latest_inventory_date = balance_sheet.columns[0] if not balance_sheet.empty else "Not Available"
            latest_financial_date = income_statement.columns[0] if not income_statement.empty else "Not Available"

            inventory_cost = balance_sheet.loc['Inventory', latest_inventory_date] if 'Inventory' in balance_sheet.index else "Not Available"
            if isinstance(inventory_cost, float) and pd.isna(inventory_cost):
                inventory_cost = "Not Available"

            if inventory_cost == "Not Available" or (isinstance(inventory_cost, (int, float)) and inventory_cost <= 0):
                return {"error": f"This application is designed for inventory-based companies only. '{ticker.upper()}' does not have significant inventory data."}

            cogs = income_statement.loc['Cost Of Revenue', latest_financial_date] if 'Cost Of Revenue' in income_statement.index else "Not Available"
            revenue = income_statement.loc['Total Revenue', latest_financial_date] if 'Total Revenue' in income_statement.index else 0
            gross_profit = income_statement.loc['Gross Profit', latest_financial_date] if 'Gross Profit' in income_statement.index else "Not Available"
            market_cap = info.get('marketCap', 0)
            headcount = info.get('fullTimeEmployees', "Not Available")
            sga_expense = income_statement.loc['Selling General And Administration', latest_financial_date] if 'Selling General And Administration' in income_statement.index else "Not Available"
            cost_of_revenue = income_statement.loc['Cost Of Revenue', latest_financial_date] if 'Cost Of Revenue' in income_statement.index else 0
            currency = info.get("currency", "USD")  # Default to USD if not available

            gross_profit_percentage = (gross_profit / revenue * 100) if isinstance(gross_profit, (int, float)) and revenue > 0 else "Not Available"
            salary_avg = sga_expense / headcount if headcount != "Not Available" and sga_expense != "Not Available" else "Not Available"

            return {
                "company": ticker.upper(),
                "analized_data_date": format_date(latest_inventory_date),
                "balance_sheet_inventory_cost": format_amount(inventory_cost, currency),
                "P&L_inventory_cost": format_amount(cogs, currency),
                "Revenue": format_amount(revenue, currency),
                "Headcount Old": headcount if headcount == "Not Available" else f"{headcount:,}",
                "Salary Average": format_amount(salary_avg, currency),
                "gross_profit": format_amount(gross_profit, currency),
                "gross_profit_percentage": f"{gross_profit_percentage:.2f}" if gross_profit_percentage != "Not Available" else "Not Available",
                "market_cap": format_amount(market_cap, currency),
                "currency": currency
            }
        except Exception as e:
            return {"error": f"Failed to fetch data for '{ticker.upper()}': {str(e)}"}

class CalculatorTool(BaseTool):
    name: str = "CalculatorTool"
    description: str = "Calculates financial benefits based on company financial data and company type determined by revenue."

    benefit_mapping: Dict[str, Dict[str, Tuple[float, float]]] = {
        "allocation_and_replenishment" : {
            "Global": {
                "Margin Rate Lift (bps)": (1.00, 1.50),
                "Margin on Revenue Lift": (0.50, 1.00),
                "Efficiency Re-Investment": (100, 200),
                "Reduction in Xfer Expenses": (0.020, 0.024),
                "Inventory Carrying Costs": (5.0, 12.0)
            },
            "Leader": {
                "Margin Rate Lift (bps)": (0.75, 1.20),
                "Margin on Revenue Lift": (0.40, 0.80),
                "Efficiency Re-Investment": (75, 150),
                "Reduction in Xfer Expenses": (0.015, 0.020),
                "Inventory Carrying Costs": (3.0, 10.0)
            },
            "Challenger": {
                "Margin Rate Lift (bps)": (0.50, 1.00),
                "Margin on Revenue Lift": (0.30, 0.60),
                "Efficiency Re-Investment": (50, 100),
                "Reduction in Xfer Expenses": (0.010, 0.016),
                "Inventory Carrying Costs": (2.0, 8.0)
            },
            "Startup": {
                "Margin Rate Lift (bps)": (0.25, 0.80),
                "Margin on Revenue Lift": (0.10, 0.50),
                "Efficiency Re-Investment": (30, 80),
                "Reduction in Xfer Expenses": (0.005, 0.012),
                "Inventory Carrying Costs": (1.0, 5.0)
            }
        },
        "assortment_and_space" : {
            "Global": {
                "Margin Rate Lift (bps)": (0.80, 1.40),
                "Margin on Revenue Lift": (0.40, 0.90),
                "Efficiency Re-Investment": (90, 180),
                "Reduction in Xfer Expenses": (0.018, 0.022),
                "Inventory Carrying Costs": (4.5, 11.0)
            },
            "Leader": {
                "Margin Rate Lift (bps)": (0.60, 1.10),
                "Margin on Revenue Lift": (0.35, 0.75),
                "Efficiency Re-Investment": (70, 140),
                "Reduction in Xfer Expenses": (0.013, 0.018),
                "Inventory Carrying Costs": (3.0, 9.0)
            },
            "Challenger": {
                "Margin Rate Lift (bps)": (0.40, 0.90),
                "Margin on Revenue Lift": (0.25, 0.55),
                "Efficiency Re-Investment": (45, 90),
                "Reduction in Xfer Expenses": (0.009, 0.014),
                "Inventory Carrying Costs": (1.8, 7.5)
            },
            "Startup": {
                "Margin Rate Lift (bps)": (0.20, 0.70),
                "Margin on Revenue Lift": (0.08, 0.45),
                "Efficiency Re-Investment": (25, 70),
                "Reduction in Xfer Expenses": (0.004, 0.010),
                "Inventory Carrying Costs": (0.8, 4.5)
            }
        },
        "merch_financial_planning" : {
            "Global": {
                "Margin Rate Lift (bps)": (1.10, 1.60),
                "Margin on Revenue Lift": (0.55, 1.10),
                "Efficiency Re-Investment": (110, 220),
                "Reduction in Xfer Expenses": (0.025, 0.030),
                "Inventory Carrying Costs": (6.0, 14.0)
            },
            "Leader": {
                "Margin Rate Lift (bps)": (0.85, 1.30),
                "Margin on Revenue Lift": (0.45, 0.90),
                "Efficiency Re-Investment": (85, 170),
                "Reduction in Xfer Expenses": (0.018, 0.024),
                "Inventory Carrying Costs": (4.0, 11.0)
            },
            "Challenger": {
                "Margin Rate Lift (bps)": (0.60, 1.10),
                "Margin on Revenue Lift": (0.35, 0.70),
                "Efficiency Re-Investment": (60, 120),
                "Reduction in Xfer Expenses": (0.012, 0.018),
                "Inventory Carrying Costs": (3.0, 9.0)
            },
            "Startup": {
                "Margin Rate Lift (bps)": (0.30, 0.85),
                "Margin on Revenue Lift": (0.12, 0.55),
                "Efficiency Re-Investment": (40, 90),
                "Reduction in Xfer Expenses": (0.006, 0.014),
                "Inventory Carrying Costs": (1.5, 6.0)
            }
        },
        "pricing": {
            "Global": {
                "Base - Margin on Revenue Lift": (0.50, 1.00),
                "Base - Margin Rate Lift (bps)": (1.00, 1.50),
                "Promo - Margin on Revenue Lift": (0.30, 0.80),
                "Promo - Margin Rate Lift (bps)": (0.75, 1.25),
                "MD - Margin on Revenue Lift": (0.20, 0.60),
                "MD - Margin Rate Lift (bps)": (0.50, 1.00),
                "Efficiency Re-Investment": (100, 200)
            },
            "Leader": {
                "Base - Margin on Revenue Lift": (0.40, 0.80),
                "Base - Margin Rate Lift (bps)": (0.75, 1.20),
                "Promo - Margin on Revenue Lift": (0.25, 0.65),
                "Promo - Margin Rate Lift (bps)": (0.60, 1.00),
                "MD - Margin on Revenue Lift": (0.15, 0.50),
                "MD - Margin Rate Lift (bps)": (0.40, 0.90),
                "Efficiency Re-Investment": (75, 150)
            },
            "Challenger": {
                "Base - Margin on Revenue Lift": (0.30, 0.60),
                "Base - Margin Rate Lift (bps)": (0.50, 1.00),
                "Promo - Margin on Revenue Lift": (0.20, 0.50),
                "Promo - Margin Rate Lift (bps)": (0.40, 0.80),
                "MD - Margin on Revenue Lift": (0.10, 0.40),
                "MD - Margin Rate Lift (bps)": (0.30, 0.70),
                "Efficiency Re-Investment": (50, 100)
            },
            "Startup": {
                "Base - Margin on Revenue Lift": (0.20, 0.50),
                "Base - Margin Rate Lift (bps)": (0.25, 0.80),
                "Promo - Margin on Revenue Lift": (0.10, 0.40),
                "Promo - Margin Rate Lift (bps)": (0.25, 0.60),
                "MD - Margin on Revenue Lift": (0.05, 0.30),
                "MD - Margin Rate Lift (bps)": (0.20, 0.50),
                "Efficiency Re-Investment": (30, 80)
            }
        }    
    }

    def _run(self, financial_data: dict) -> dict:
        def parse_currency(value: str) -> float:
            """Parse formatted currency strings (e.g., 'USD 6.63 B') into a float."""
            if value == "Not Available" or value is None:
                return 0
            try:
                value = str(value).replace(',', '').strip()
                match = re.search(r'(\d+\.?\d*)\s*([BKM]?)', value, re.IGNORECASE)
                if not match:
                    return float(value)
                num = float(match.group(1))
                multiplier = match.group(2).upper() if match.group(2) else ''
                return num * (1e9 if multiplier == 'B' else 1e6 if multiplier == 'M' else 1e3 if multiplier == 'K' else 1)
            except (ValueError, AttributeError) as e:
                print(f"Error parsing currency '{value}': {str(e)}")
                return 0

        def get_company_type(revenue):
            revenue_val = parse_currency(revenue) if isinstance(revenue, str) else revenue if revenue != "Not Available" else 0
            print(f"Parsed Revenue for company type: {revenue_val}")
            if not isinstance(revenue_val, (int, float)) or revenue_val <= 0:
                return "Startup"
            if revenue_val > 50e9:
                return "Global"
            elif revenue_val > 10e9:
                return "Leader"
            elif revenue_val > 1e9:
                return "Challenger"
            else:
                return "Startup"

        print(f"Financial Data Input: {financial_data}")
        company_type = get_company_type(financial_data.get("Revenue", "Not Available"))
        print(f"Company Type: {company_type}")

        # Parse financial data
        revenue = parse_currency(financial_data.get("Revenue", "Not Available"))
        inventory_cost = parse_currency(financial_data.get("balance_sheet_inventory_cost", "Not Available"))
        gross_profit = parse_currency(financial_data.get("gross_profit", "Not Available"))
        gross_profit_pct = float(financial_data.get("gross_profit_percentage", "Not Available") or 0)
        headcount = int(str(financial_data.get("Headcount Old", "Not Available")).replace(',', '')) if str(financial_data.get("Headcount Old", "Not Available")).replace(',', '').isdigit() else 0
        salary_avg = parse_currency(financial_data.get("Salary Average", "Not Available"))
        currency = financial_data.get("currency", "USD")

        print(f"Parsed Values - Revenue: {revenue}, Inventory Cost: {inventory_cost}, Gross Profit: {gross_profit}, Gross Profit %: {gross_profit_pct}, Headcount: {headcount}, Salary Avg: {salary_avg}")

        def safe_calc(low, high, calc_func):
            try:
                low_val = calc_func(low)
                high_val = calc_func(high)
                # Only format if calculation succeeds and values are valid
                if low_val is not None and high_val is not None and isinstance(low_val, (int, float)) and isinstance(high_val, (int, float)):
                    print(f"Calculated - Low: {low_val}, High: {high_val}")
                    return {"low": format_amount(low_val, currency), "high": format_amount(high_val, currency)}
                else:
                    raise ValueError("Calculation returned invalid values")
            except Exception as e:
                print(f"Calculation failed: {str(e)}")
                return {"low": "Not Available", "high": "Not Available"}

        def calculate_benefit_sums(benefits_dict):
            result = {}
            benefits = benefits_dict["benefits"]
            for category, metrics in benefits.items():
                low_sum = 0
                high_sum = 0
                for metric, values in metrics.items():
                    low_val = parse_currency(values["low"]) if isinstance(values["low"], str) else 0
                    high_val = parse_currency(values["high"]) if isinstance(values["high"], str) else 0
                    low_sum += low_val
                    high_sum += high_val
                result[category] = {
                    "low": format_amount(low_sum, currency) if low_sum > 0 else "Not Available",
                    "high": format_amount(high_sum, currency) if high_sum > 0 else "Not Available"
                }
            return result

        headfix = 10
        price_benefit_headfix = 2
        final_results = {"benefits": {}, "sum": {}}

        # Allocation and Replenishment
        all_percentages = self.benefit_mapping.get("allocation_and_replenishment")
        percentages = all_percentages.get(company_type, all_percentages["Startup"])
        allocation_and_replenishment = {
            "Margin Rate Lift (bps)": safe_calc(
                percentages["Margin Rate Lift (bps)"][0], percentages["Margin Rate Lift (bps)"][1],
                lambda x: (revenue * ((gross_profit_pct / 100) + (x / 100))) - gross_profit if revenue and gross_profit else None
            ),
            "Margin on Revenue Lift": safe_calc(
                percentages["Margin on Revenue Lift"][0], percentages["Margin on Revenue Lift"][1],
                lambda x: ((revenue * (1 + (x / 100))) * (gross_profit_pct / 100)) - gross_profit if revenue and gross_profit else None
            ),
            "Efficiency Re-Investment": safe_calc(
                percentages["Efficiency Re-Investment"][0], percentages["Efficiency Re-Investment"][1],
                lambda x: (headfix - (headfix * 100 / (x + 100))) * salary_avg if salary_avg else None
            ),
            "Reduction in Xfer Expenses": safe_calc(
                percentages["Reduction in Xfer Expenses"][0], percentages["Reduction in Xfer Expenses"][1],
                lambda x: (x / 100) * inventory_cost if inventory_cost else None
            ),
            "Inventory Carrying Costs": safe_calc(
                percentages["Inventory Carrying Costs"][0], percentages["Inventory Carrying Costs"][1],
                lambda x: (inventory_cost * 0.2) * (x / 100) if inventory_cost else None
            )
        }
        final_results["benefits"]["allocation_and_replenishment"] = allocation_and_replenishment

        # Assortment and Space (similar updates as above)
        all_percentages = self.benefit_mapping.get("assortment_and_space")
        percentages = all_percentages.get(company_type, all_percentages["Startup"])
        assortment_and_space = {
            "Margin Rate Lift (bps)": safe_calc(
                percentages["Margin Rate Lift (bps)"][0], percentages["Margin Rate Lift (bps)"][1],
                lambda x: (revenue * ((gross_profit_pct / 100) + (x / 100))) - gross_profit if revenue and gross_profit else None
            ),
            "Margin on Revenue Lift": safe_calc(
                percentages["Margin on Revenue Lift"][0], percentages["Margin on Revenue Lift"][1],
                lambda x: ((revenue * (1 + (x / 100))) * (gross_profit_pct / 100)) - gross_profit if revenue and gross_profit else None
            ),
            "Efficiency Re-Investment": safe_calc(
                percentages["Efficiency Re-Investment"][0], percentages["Efficiency Re-Investment"][1],
                lambda x: (headfix - (headfix * 100 / (x + 100))) * salary_avg if salary_avg else None
            ),
            "Reduction in Xfer Expenses": safe_calc(
                percentages["Reduction in Xfer Expenses"][0], percentages["Reduction in Xfer Expenses"][1],
                lambda x: (x / 100) * inventory_cost if inventory_cost else None
            ),
            "Inventory Carrying Costs": safe_calc(
                percentages["Inventory Carrying Costs"][0], percentages["Inventory Carrying Costs"][1],
                lambda x: (inventory_cost * 0.2) * (x / 100) if inventory_cost else None
            )
        }
        final_results["benefits"]["assortment_and_space"] = assortment_and_space

        # Merch Financial Planning (similar updates as above)
        all_percentages = self.benefit_mapping.get("merch_financial_planning")
        percentages = all_percentages.get(company_type, all_percentages["Startup"])
        merch_financial_planning = {
            "Margin Rate Lift (bps)": safe_calc(
                percentages["Margin Rate Lift (bps)"][0], percentages["Margin Rate Lift (bps)"][1],
                lambda x: (revenue * ((gross_profit_pct / 100) + (x / 100))) - gross_profit if revenue and gross_profit else None
            ),
            "Margin on Revenue Lift": safe_calc(
                percentages["Margin on Revenue Lift"][0], percentages["Margin on Revenue Lift"][1],
                lambda x: ((revenue * (1 + (x / 100))) * (gross_profit_pct / 100)) - gross_profit if revenue and gross_profit else None
            ),
            "Efficiency Re-Investment": safe_calc(
                percentages["Efficiency Re-Investment"][0], percentages["Efficiency Re-Investment"][1],
                lambda x: (headfix - (headfix * 100 / (x + 100))) * salary_avg if salary_avg else None
            ),
            "Inventory Carrying Costs": safe_calc(
                percentages["Inventory Carrying Costs"][0], percentages["Inventory Carrying Costs"][1],
                lambda x: (inventory_cost * 0.2) * (x / 100) if inventory_cost else None
            )
        }
        final_results["benefits"]["merch_financial_planning"] = merch_financial_planning

        # Pricing (similar updates as above)
        all_percentages = self.benefit_mapping.get("pricing")
        percentages = all_percentages.get(company_type, all_percentages["Startup"])
        sales_on_base_price_sales_perct_ttl = 0.50
        sales_on_base_price_gm_perct = 0.35
        sales_on_base_promotional_event_sales_perct_ttl = 0.35
        sales_on_base_promotional_event_gm_perct = 0.25
        sales_on_markdown_sales_perct_ttl = 0.15
        sales_on_markdown_gm_perct = 0.10

        pricing = {
            "Base - Margin on Revenue Lift": safe_calc(
                percentages["Base - Margin on Revenue Lift"][0], percentages["Base - Margin on Revenue Lift"][1],
                lambda x: (((sales_on_base_price_sales_perct_ttl * revenue) * (1 + (x / 100)) * sales_on_base_price_gm_perct) - 
                        ((sales_on_base_price_sales_perct_ttl * revenue) * sales_on_base_price_gm_perct)) if revenue else None
            ),
            "Base - Margin Rate Lift (bps)": safe_calc(
                percentages["Base - Margin Rate Lift (bps)"][0], percentages["Base - Margin Rate Lift (bps)"][1],
                lambda x: (((sales_on_base_price_sales_perct_ttl * revenue) * (sales_on_base_price_gm_perct + (x / 100))) - 
                        ((sales_on_base_price_sales_perct_ttl * revenue) * sales_on_base_price_gm_perct)) if revenue else None
            ),
            "Promo - Margin on Revenue Lift": safe_calc(
                percentages["Promo - Margin on Revenue Lift"][0], percentages["Promo - Margin on Revenue Lift"][1],
                lambda x: (((sales_on_base_promotional_event_sales_perct_ttl * revenue) * (1 + (x / 100)) * sales_on_base_promotional_event_gm_perct) - 
                        ((sales_on_base_promotional_event_sales_perct_ttl * revenue) * sales_on_base_promotional_event_gm_perct)) if revenue else None
            ),
            "Promo - Margin Rate Lift (bps)": safe_calc(
                percentages["Promo - Margin Rate Lift (bps)"][0], percentages["Promo - Margin Rate Lift (bps)"][1],
                lambda x: (((sales_on_base_promotional_event_sales_perct_ttl * revenue) * (sales_on_base_promotional_event_gm_perct + (x / 100))) - 
                        ((sales_on_base_promotional_event_sales_perct_ttl * revenue) * sales_on_base_promotional_event_gm_perct)) if revenue else None
            ),
            "MD - Margin on Revenue Lift": safe_calc(
                percentages["MD - Margin on Revenue Lift"][0], percentages["MD - Margin on Revenue Lift"][1],
                lambda x: (((sales_on_markdown_sales_perct_ttl * revenue) * (1 + (x / 100)) * sales_on_markdown_gm_perct) - 
                        ((sales_on_markdown_sales_perct_ttl * revenue) * sales_on_markdown_gm_perct)) if revenue else None
            ),
            "MD - Margin Rate Lift (bps)": safe_calc(
                percentages["MD - Margin Rate Lift (bps)"][0], percentages["MD - Margin Rate Lift (bps)"][1],
                lambda x: (((sales_on_markdown_sales_perct_ttl * revenue) * (sales_on_markdown_gm_perct + (x / 100))) - 
                        ((sales_on_markdown_sales_perct_ttl * revenue) * sales_on_markdown_gm_perct)) if revenue else None
            ),
            "Efficiency Re-Investment": safe_calc(
                percentages["Efficiency Re-Investment"][0], percentages["Efficiency Re-Investment"][1],
                lambda x: (price_benefit_headfix - (price_benefit_headfix * 100 / (x + 100))) * salary_avg if salary_avg else None
            )
        }
        final_results["benefits"]["pricing"] = pricing

        # Calculate sums
        final_results["sum"] = calculate_benefit_sums(final_results)

        print(f"Final Results: {final_results}")
        return final_results


class AlphaVantageTool(BaseTool):
    name: str = "AlphaVantageDataFetcher"
    description: str = "Fetches financial data from Alpha Vantage API for a given ticker symbol."

    def _run(self, ticker: str) -> dict:
        base_url = "https://www.alphavantage.co/query"
        params = {
            "function": "OVERVIEW",
            "symbol": ticker,
            "apikey": os.getenv("ALPHA_VANTAGE_API_KEY"),
        }
        try:
            response = requests.get(base_url, params=params)
            if response.status_code == 200:
                overview = response.json()
                if "Name" not in overview:
                    return {"error": "No data found for this ticker in Alpha Vantage"}
                data = {
                    "company_name": overview.get("Name"),
                    "market_cap": float(overview.get("MarketCapitalization", 0)),
                    "Headcount": overview.get("FullTimeEmployees", "Not Available"),
                    "Salary Average": "Not Available"  # Placeholder
                }
                return data
            else:
                return {"error": f"Alpha Vantage API error: HTTP {response.status_code}"}
        except Exception as e:
            return {"error": f"Alpha Vantage request error: {str(e)}"}

class InventoryCheckTool(BaseTool):
    name: str = "InventoryCompanyChecker"
    description: str = "Checks if a company is inventory-based based on balance sheet and sector data."

    def _run(self, ticker: str) -> bool:
        company = yf.Ticker(ticker)
        balance_sheet = company.balance_sheet
        info = company.info
        
        has_inventory = balance_sheet.get("Inventory", 0) > 0
        sector = info.get("sector", "").lower()
        inventory_sectors = ["consumer", "industrial", "retail", "manufacturing"]
        
        return has_inventory or any(s in sector for s in inventory_sectors)

class SearchCompanyTool(BaseTool):
    name: str = "CompanyInfoSearch"
    description: str = "Searches for additional company information using SerperDevTool."
    
    serper_tool: Optional[SerperDevTool] = None

    class Config:
        arbitrary_types_allowed = True

    def __init__(self):
        super().__init__()
        self.serper_tool = SerperDevTool()

    def _run(self, company_name: str) -> str:
        return self.serper_tool.run(f"{company_name} financial reports inventory data")

class TickerLookupTool(BaseTool):
    name: str = "TickerLookupTool"
    description: str = "Looks up a company's ticker symbol based on its name using Serper API."

    def _run(self, company_name: str) -> str:
        """Fetch ticker symbol dynamically for a given company name using Serper API and return a descriptive message."""
        api_key = os.getenv("SERPER_API_KEY")
        if not api_key:
            return "Error: SERPER_API_KEY not set in .env file"

        url = "https://google.serper.dev/search"
        query = f"{company_name} stock ticker symbol"
        headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "q": query
        }

        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            # Extract ticker from organic search results
            search_results = data.get("organic", [])
            for result in search_results:
                snippet = result.get("snippet", "")
                ticker_match = re.search(r'\b[A-Z]{1,5}\b', snippet)
                if ticker_match:
                    ticker = ticker_match.group(0)
                    return f"This is the ticker for '{company_name}': {ticker}"
            
            return f"Error: No ticker found for '{company_name}'"
        except requests.RequestException as e:
            return f"Error: API request failed for '{company_name}' - {str(e)}"
        except Exception as e:
            return f"Error: Unexpected failure for '{company_name}' - {str(e)}"
        


class FinanceTools:
    def __init__(self):
        self.alpha_vantage_key = os.getenv("ALPHA_VANTAGE_API_KEY")
        self.ts = TimeSeries(key=self.alpha_vantage_key)
        self.file_read_tool = FileReadTool() #enabled
        self.yfinance_tool = YFinanceTool()
        self.alpha_vantage_tool = AlphaVantageTool()
        self.inventory_check_tool = InventoryCheckTool()
        self.search_company_tool = SearchCompanyTool() #enabled
        self.ticker_lookup_tool = TickerLookupTool()
        self.calculator_tool = CalculatorTool()