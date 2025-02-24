from crewai.tools import BaseTool
from crewai_tools import FileReadTool, SerperDevTool
import yfinance as yf
from alpha_vantage.timeseries import TimeSeries
from datetime import datetime
import os
import requests
from dotenv import load_dotenv
from typing import Any, Optional
import json

load_dotenv()

class YFinanceTool(BaseTool):
    name: str = "YahooFinanceDataFetcher"
    description: str = "Fetches financial data from Yahoo Finance for a given ticker symbol."

    def _run(self, ticker: str) -> dict:
        try:
            company = yf.Ticker(ticker)
            info = company.info
            financials = company.financials
            balance_sheet = company.balance_sheet
            
            data = {
                "company_name": info.get("longName", ticker),
                "analyzed_data_date": datetime.now().strftime("%Y-%m-%d"),
                "balance_sheet_inventory_cost": balance_sheet.get("Inventory", 0),
                "P&L_inventory_cost": financials.get("Cost Of Revenue", 0),
                "Revenue": financials.get("Total Revenue", 0),
                "market_cap": info.get("marketCap", 0),
                "gross_profit": financials.get("Gross Profit", 0),
                "gross_profit_percentage": (
                    financials.get("Gross Profit", 0) / financials.get("Total Revenue", 0) * 100
                ) if financials.get("Total Revenue", 0) else 0
            }
            return data
        except Exception as e:
            return {"error": f"Yahoo Finance error: {str(e)}"}

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
                if "Name" not in overview:  # Handle case where API returns an error or empty response
                    return {"error": "No data found for this ticker in Alpha Vantage"}
                data = {
                    "company_name": overview.get("Name"),
                    "market_cap": float(overview.get("MarketCapitalization", 0)),
                    "Headcount Old": overview.get("FullTimeEmployees"),
                    "Salary Average": (
                        float(overview.get("EBITDA", 0)) / float(overview.get("FullTimeEmployees", 1))
                    ) if overview.get("FullTimeEmployees") else 0
                }
                merged_json = {**overview, **data}
                return merged_json
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
        
        has_inventory = balance_sheet.loc['Inventory'][0] > 0
        sector = info.get("sector", "").lower()
        inventory_sectors = ["consumer", "industrial", "retail", "manufacturing"]
        
        return has_inventory or any(s in sector for s in inventory_sectors)

class SearchCompanyTool(BaseTool):
    name: str = "CompanyInfoSearch"
    description: str = "Searches for additional company information using SerperDevTool."
    
    serper_tool: Optional[SerperDevTool] = None  # Declare with default None

    class Config:
        arbitrary_types_allowed = True  # Allow SerperDevTool

    def __init__(self):
        super().__init__()
        self.serper_tool = SerperDevTool()

    def _run(self, company_name: str) -> str:
        return self.serper_tool.run(f"{company_name} financial reports inventory data")

class FinanceTools:
    def __init__(self):
        self.alpha_vantage_key = os.getenv("ALPHA_VANTAGE_API_KEY")
        self.ts = TimeSeries(key=self.alpha_vantage_key)
        self.file_read_tool = FileReadTool()
        self.yfinance_tool = YFinanceTool()
        self.alpha_vantage_tool = AlphaVantageTool()
        self.inventory_check_tool = InventoryCheckTool()
        self.search_company_tool = SearchCompanyTool()