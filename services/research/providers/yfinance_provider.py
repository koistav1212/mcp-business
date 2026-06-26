import math
import yfinance as yf
from typing import Dict, Any, Optional, List
from services.research.base import BaseProvider
from services.knowledge.evidence import ResearchEvidence
from services.knowledge.citation_manager import CitationManager

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

    async def fetch(self, target: Any) -> List[ResearchEvidence]:
        ticker_symbol = self._extract_identifier(target)
        if not ticker_symbol:
            return []
            
        ticker_clean = str(ticker_symbol).strip().upper()

        evidence_list = []
        try:
            ticker = yf.Ticker(ticker_clean)
            info = ticker.info or {}
            
            market_cap = clean_nan(info.get("marketCap"))
            pe_ratio = clean_nan(info.get("trailingPE") or info.get("forwardPE"))
            current_price = clean_nan(info.get("currentPrice") or info.get("regularMarketPrice") or info.get("regularMarketPreviousClose"))
            high_52w = clean_nan(info.get("fiftyTwoWeekHigh"))
            low_52w = clean_nan(info.get("fiftyTwoWeekLow"))
            
            # Map into ResearchEvidence
            data_map = {
                "market_cap": market_cap,
                "pe_ratio": pe_ratio,
                "current_price": current_price,
                "fifty_two_week_high": high_52w,
                "fifty_two_week_low": low_52w,
            }
            
            for attr, val in data_map.items():
                if val is not None:
                    evidence_list.append(ResearchEvidence(
                        id=CitationManager.generate_id("market_data", ticker_clean, attr, "current"),
                        entity=ticker_clean,
                        attribute=attr,
                        value=val,
                        source="market_data",
                        source_type="mcp",
                        confidence=0.9
                    ))
                    
        except Exception as e:
            # We don't append evidence on failure, just return empty
            pass
            
        return evidence_list
