import math
import yfinance as yf
from typing import Dict, Any, Optional
from services.research.base import BaseProvider

def clean_nan(obj):
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif isinstance(obj, dict):
        return {k: clean_nan(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_nan(x) for x in obj]
    return obj

class YFinanceProvider(BaseProvider):
    """
    Provides live market data for a resolved corporate ticker using yfinance.
    """

    async def fetch(self, ticker_symbol: Optional[str]) -> Dict[str, Any]:
        empty_data = {
            "market_cap": None,
            "pe_ratio": None,
            "current_price": None,
            "fifty_two_week_high": None,
            "fifty_two_week_low": None,
            "raw_data": {"note": "No ticker symbol resolved or private company."}
        }
        
        if not ticker_symbol:
            return empty_data
            
        ticker_clean = str(ticker_symbol).strip().upper()


        try:
            ticker = yf.Ticker(ticker_clean)
            info = ticker.info or {}
            
            market_cap = info.get("marketCap")
            pe_ratio = info.get("trailingPE") or info.get("forwardPE")
            current_price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("regularMarketPreviousClose")
            high_52w = info.get("fiftyTwoWeekHigh")
            low_52w = info.get("fiftyTwoWeekLow")
            
            return {
                "market_cap": clean_nan(market_cap),
                "pe_ratio": clean_nan(pe_ratio),
                "current_price": clean_nan(current_price),
                "fifty_two_week_high": clean_nan(high_52w),
                "fifty_two_week_low": clean_nan(low_52w),
                "raw_data": {
                    "ticker": ticker_clean,
                    "info": clean_nan(info)
                }
            }
        except Exception as e:
            return {
                "market_cap": None,
                "pe_ratio": None,
                "current_price": None,
                "fifty_two_week_high": None,
                "fifty_two_week_low": None,
                "raw_data": {
                    "error": str(e),
                    "ticker": ticker_clean
                }
            }
