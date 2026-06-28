from typing import List, Dict, Any

class BusinessSignalClassifier:
    """
    Detects financial and business signals from article text and headlines.
    """
    
    SIGNALS = {
        "earnings": ["earnings", "eps", "revenue", "profit", "quarterly results", "fiscal", "q1", "q2", "q3", "q4"],
        "guidance": ["guidance", "forecast", "outlook", "projects", "expects"],
        "layoffs": ["layoffs", "job cuts", "headcount reduction", "downsizing", "furlough"],
        "acquisition": ["acquire", "acquisition", "bought", "takeover", "merger", "buyout"],
        "investment": ["funding", "raises", "investment", "vc", "seed round", "series a", "series b"],
        "leadership_change": ["ceo", "cfo", "cto", "hire", "hired", "appoints", "steps down", "resigns", "board of directors"],
        "product_launch": ["launch", "announces", "unveils", "new product", "features", "release"],
        "litigation": ["sue", "sued", "lawsuit", "court", "litigation", "sec investigation", "antitrust", "doj"],
        "partnership": ["partnership", "teams up", "collaborates", "joint venture", "strategic alliance"],
        "dividend_buyback": ["dividend", "stock buyback", "share repurchase"]
    }

    def classify(self, text: str) -> List[str]:
        if not text:
            return []
            
        text_lower = text.lower()
        signals = []
        
        for signal, keywords in self.SIGNALS.items():
            if any(kw in text_lower for kw in keywords):
                signals.append(signal)
                
        return signals

    def process_all(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        for art in articles:
            text = (art.get("headline", "") + " " + art.get("summary", "")).strip()
            art["signal_type"] = self.classify(text)
        return articles
