"""
Financial Agents Package
This package contains agents for collecting, formatting, and summarizing financial data.
"""

__version__ = "1.0.0"
__all__ = [
    "DataCollectorAgent",
    "DataFormatterAgent",
    "SummaryGeneratorAgent",
    "BenefitCalculatorAgent"
]

# Convenience imports
from .data_collector import DataCollectorAgent
from .data_formatter import DataFormatterAgent
from .summary_generator import SummaryGeneratorAgent
from .benefit_calculator import BenefitCalculatorAgent