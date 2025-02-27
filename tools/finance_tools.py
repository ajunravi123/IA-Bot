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


class CalculatorTool(BaseTool):
    name: str = "CalculatorTool"
    description: str = "Calculates financial benefits based on company financial data and company type determined by revenue."

    # Annotated benefit_mapping with type hint
    benefit_mapping: Dict[str, Dict[str, Tuple[float, float]]] = {
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
    }

    def _run(self, financial_data: dict) -> dict:
        """Calculate financial benefits directly within the tool."""
        def parse_currency(value: str) -> float:
            try:
                value = value.replace('$', '').replace(',', '').strip()
                if 'billion' in value.lower():
                    return float(value.replace('billion', '').strip()) * 1e9
                elif 'million' in value.lower():
                    return float(value.replace('million', '').strip()) * 1e6
                else:
                    return float(value)
            except (ValueError, AttributeError):
                return 0

        def get_company_type(revenue):
            if isinstance(revenue, str):
                revenue = parse_currency(revenue)
            if not isinstance(revenue, (int, float)) or revenue <= 0:
                return "Startup"
            if revenue > 50e9:
                return "Global"
            elif revenue > 10e9:
                return "Leader"
            elif revenue > 1e9:
                return "Challenger"
            else:
                return "Startup"

        company_type = get_company_type(financial_data.get("Revenue", 0))
        percentages = self.benefit_mapping.get(company_type, self.benefit_mapping["Startup"])
        
        revenue = financial_data.get("Revenue", "Not Available")
        inventory_cost = financial_data.get("balance_sheet_inventory_cost", "Not Available")
        gross_profit = financial_data.get("gross_profit", "Not Available")
        gross_profit_pct = financial_data.get("gross_profit_percentage", "Not Available")
        headcount = financial_data.get("Headcount", "Not Available")
        salary_avg = financial_data.get("Salary Average", "Not Available")

        revenue = parse_currency(revenue) if isinstance(revenue, str) else revenue if revenue != "Not Available" else 0
        inventory_cost = parse_currency(inventory_cost) if isinstance(inventory_cost, str) else inventory_cost if inventory_cost != "Not Available" else 0
        gross_profit = parse_currency(gross_profit) if isinstance(gross_profit, str) else gross_profit if gross_profit != "Not Available" else 0
        gross_profit_pct = float(gross_profit_pct) if isinstance(gross_profit_pct, (str, int, float)) and gross_profit_pct != "Not Available" else 0
        headcount = int(headcount.replace(',', '')) if isinstance(headcount, str) and headcount != "Not Available" else headcount if headcount != "Not Available" else 0
        salary_avg = parse_currency(salary_avg) if isinstance(salary_avg, str) else salary_avg if salary_avg != "Not Available" else 0

        def safe_calc(low, high, calc_func):
            try:
                return {"low": calc_func(low), "high": calc_func(high)}
            except:
                return {"low": "Not Available", "high": "Not Available"}

        results = {
            "Margin_Rate_Lift": safe_calc(
                percentages["Margin Rate Lift (bps)"][0], percentages["Margin Rate Lift (bps)"][1],
                lambda x: (revenue * ((gross_profit_pct / 100) + (x / 100))) - gross_profit if revenue and gross_profit else "Not Available"
            ),
            "Margin_on_Revenue_Lift": safe_calc(
                percentages["Margin on Revenue Lift"][0], percentages["Margin on Revenue Lift"][1],
                lambda x: ((revenue * (1 + (x / 100))) * (gross_profit_pct / 100)) - gross_profit if revenue and gross_profit else "Not Available"
            ),
            "Efficiency_Re_Investment": safe_calc(
                percentages["Efficiency Re-Investment"][0], percentages["Efficiency Re-Investment"][1],
                lambda x: (headcount - (headcount * 100 / (x + 100))) * salary_avg if headcount and salary_avg else "Not Available"
            ),
            "Reduction_in_Xfer_Expenses": safe_calc(
                percentages["Reduction in Xfer Expenses"][0], percentages["Reduction in Xfer Expenses"][1],
                lambda x: (x / 100) * inventory_cost if inventory_cost else "Not Available"
            ),
            "Inventory_Carrying_Costs": safe_calc(
                percentages["Inventory Carrying Costs"][0], percentages["Inventory Carrying Costs"][1],
                lambda x: (inventory_cost * 0.2) * (x / 100) if inventory_cost else "Not Available"
            )
        }
        return results


class YFinanceTool(BaseTool):
    name: str = "YahooFinanceDataFetcher"
    description: str = "Fetches financial data from Yahoo Finance for a given ticker symbol."

    def _run(self, ticker: str) -> dict:
        """Fetch financial data including currency type similar to DataFetcher.get_financials()."""
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

            # Fetch inventory cost and handle NaN
            inventory_cost = balance_sheet.loc['Inventory', latest_inventory_date] if 'Inventory' in balance_sheet.index else "Not Available"
            if isinstance(inventory_cost, float) and pd.isna(inventory_cost):
                inventory_cost = "Not Available"

            # Check if the company has significant inventory
            if inventory_cost == "Not Available" or (isinstance(inventory_cost, (int, float)) and inventory_cost <= 0):
                return {"error": f"This application is designed for inventory-based companies only. '{ticker.upper()}' does not have significant inventory data."}

            cogs = income_statement.loc['Cost Of Revenue', latest_financial_date] if 'Cost Of Revenue' in income_statement.index else "Not Available"
            revenue = income_statement.loc['Total Revenue', latest_financial_date] if 'Total Revenue' in income_statement.index else 0
            gross_profit = income_statement.loc['Gross Profit', latest_financial_date] if 'Gross Profit' in income_statement.index else "Not Available"
            market_cap = info.get('marketCap', 0)
            headcount = info.get('fullTimeEmployees', "Not Available")
            sga_expense = income_statement.loc['Selling General And Administration', latest_financial_date] if 'Selling General And Administration' in income_statement.index else "Not Available"
            cost_of_revenue = income_statement.loc['Cost Of Revenue', latest_financial_date] if 'Cost Of Revenue' in income_statement.index else 0
            currency = info.get("currency", "Currency info not available")  # Fetch currency type

            gross_profit_percentage = (gross_profit / revenue * 100) if isinstance(gross_profit, (int, float)) and revenue > 0 else "Not Available"
            salary_avg = sga_expense / headcount if headcount != "Not Available" and sga_expense != "Not Available" else "Not Available"

            return {
                "company": ticker.upper(),
                "analized_data_date": latest_inventory_date,
                "balance_sheet_inventory_cost": inventory_cost,
                "P&L_inventory_cost": cogs,
                "Revenue": revenue,
                "Headcount Old": headcount,
                "Salary Average": salary_avg,
                "gross_profit": gross_profit,
                "gross_profit_percentage": gross_profit_percentage,
                "market_cap": market_cap,
                "currency": currency  # Added currency field
            }
        except Exception as e:
            return {"error": f"Failed to fetch data for '{ticker.upper()}': {str(e)}"}

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
        
class Calculator:
    def __init__(self):
        self.benefit_mapping = {
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
        }

    def get_company_type(self, revenue):
        """Determine company type based on revenue (in dollars)."""
        if isinstance(revenue, str):
            revenue = self.parse_currency(revenue)
        if not isinstance(revenue, (int, float)) or revenue <= 0:
            return "Startup"
        if revenue > 50e9:  # $50 billion
            return "Global"
        elif revenue > 10e9:  # $10 billion
            return "Leader"
        elif revenue > 1e9:  # $1 billion
            return "Challenger"
        else:
            return "Startup"

    def parse_currency(self, value: str) -> float:
        """Parse string values like '$133.7 billion' to float."""
        try:
            value = value.replace('$', '').replace(',', '').strip()
            if 'billion' in value.lower():
                return float(value.replace('billion', '').strip()) * 1e9
            elif 'million' in value.lower():
                return float(value.replace('million', '').strip()) * 1e6
            else:
                return float(value)
        except (ValueError, AttributeError):
            return 0

    def calculate_benefits(self, values):
        """Calculate financial benefits based on company type and financial data."""
        company_type = self.get_company_type(values.get("Revenue", 0))
        percentages = self.benefit_mapping.get(company_type, self.benefit_mapping["Startup"])
        
        revenue = values.get("Revenue", "Not Available")
        inventory_cost = values.get("balance_sheet_inventory_cost", "Not Available")
        gross_profit = values.get("gross_profit", "Not Available")
        gross_profit_pct = values.get("gross_profit_percentage", "Not Available")
        headcount = values.get("Headcount", "Not Available")
        salary_avg = values.get("Salary Average", "Not Available")

        # Convert to numeric values if possible
        revenue = self.parse_currency(revenue) if isinstance(revenue, str) else revenue if revenue != "Not Available" else 0
        inventory_cost = self.parse_currency(inventory_cost) if isinstance(inventory_cost, str) else inventory_cost if inventory_cost != "Not Available" else 0
        gross_profit = self.parse_currency(gross_profit) if isinstance(gross_profit, str) else gross_profit if gross_profit != "Not Available" else 0
        gross_profit_pct = float(gross_profit_pct) if isinstance(gross_profit_pct, (str, int, float)) and gross_profit_pct != "Not Available" else 0
        headcount = int(headcount.replace(',', '')) if isinstance(headcount, str) and headcount != "Not Available" else headcount if headcount != "Not Available" else 0
        salary_avg = self.parse_currency(salary_avg) if isinstance(salary_avg, str) else salary_avg if salary_avg != "Not Available" else 0

        def safe_calc(low, high, calc_func):
            try:
                return {"low": calc_func(low), "high": calc_func(high)}
            except:
                return {"low": "Not Available", "high": "Not Available"}

        results = {
            "Margin_Rate_Lift": safe_calc(
                percentages["Margin Rate Lift (bps)"][0], percentages["Margin Rate Lift (bps)"][1],
                lambda x: (revenue * ((gross_profit_pct / 100) + (x / 100))) - gross_profit if revenue and gross_profit else "Not Available"
            ),
            "Margin_on_Revenue_Lift": safe_calc(
                percentages["Margin on Revenue Lift"][0], percentages["Margin on Revenue Lift"][1],
                lambda x: ((revenue * (1 + (x / 100))) * (gross_profit_pct / 100)) - gross_profit if revenue and gross_profit else "Not Available"
            ),
            "Efficiency_Re_Investment": safe_calc(
                percentages["Efficiency Re-Investment"][0], percentages["Efficiency Re-Investment"][1],
                lambda x: (headcount - (headcount * 100 / (x + 100))) * salary_avg if headcount and salary_avg else "Not Available"
            ),
            "Reduction_in_Xfer_Expenses": safe_calc(
                percentages["Reduction in Xfer Expenses"][0], percentages["Reduction in Xfer Expenses"][1],
                lambda x: (x / 100) * inventory_cost if inventory_cost else "Not Available"
            ),
            "Inventory_Carrying_Costs": safe_calc(
                percentages["Inventory Carrying Costs"][0], percentages["Inventory Carrying Costs"][1],
                lambda x: (inventory_cost * 0.2) * (x / 100) if inventory_cost else "Not Available"
            )
        }
        return results
    


class FinanceTools:
    def __init__(self):
        self.alpha_vantage_key = os.getenv("ALPHA_VANTAGE_API_KEY")
        self.ts = TimeSeries(key=self.alpha_vantage_key)
        self.file_read_tool = FileReadTool()
        self.yfinance_tool = YFinanceTool()
        self.alpha_vantage_tool = AlphaVantageTool()
        self.inventory_check_tool = InventoryCheckTool()
        self.search_company_tool = SearchCompanyTool()
        self.ticker_lookup_tool = TickerLookupTool()
        # self.calculator_tool = CalculatorTool()