import os
import json
import re
from typing import Tuple
from services.research.models import ResearchContext

class EntityVerifier:
    """
    Cross-validates company entity details (name, ticker, CIK, website) 
    to ensure research integrity and detect entity resolution errors.
    """
    def __init__(self):
        self.tickers_cache_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "storage", "company_tickers.json"
        )
        self.sec_tickers = {}
        self._load_cache()

    def _load_cache(self):
        if os.path.exists(self.tickers_cache_path):
            try:
                with open(self.tickers_cache_path, "r", encoding="utf-8") as f:
                    self.sec_tickers = json.load(f)
            except Exception:
                pass

    def verify(self, context: ResearchContext) -> Tuple[bool, str]:
        """
        Validates:
        - Ticker matches resolved company name
        - CIK matches ticker according to SEC database
        - Website matches company name
        
        Returns (is_valid, explanation_string)
        """
        entity = context.entity
        if not entity:
            return False, "No resolved entity details found in context."

        name = entity.company_name
        name_lower = name.lower()
        ticker = entity.ticker
        cik = entity.cik
        website = entity.website
        


        # 1. Validate CIK matches Ticker in SEC database
        if ticker and cik:
            ticker_clean = ticker.split(".")[0].upper()
            sec_match = None
            for k, v in self.sec_tickers.items():
                if v.get("ticker", "").upper() == ticker_clean:
                    sec_match = v
                    break
                    
            if sec_match:
                db_cik = str(sec_match.get("cik_str", "")).zfill(10)
                cik_padded = str(cik).zfill(10)
                if db_cik != cik_padded:
                    return False, f"INVALID: Ticker '{ticker}' resolved CIK is '{cik_padded}', but SEC database maps it to CIK '{db_cik}'."
            elif str(cik).isdigit() and str(cik) != "0" and int(cik) > 0:
                # If ticker not found in SEC but we have a non-zero CIK, it is suspicious for standard US equities
                exchange_upper = (entity.exchange or "").upper()
                if any(e in exchange_upper for e in ["NASDAQ", "NYSE", "NMS", "NYQ"]):
                    return False, f"INVALID: Ticker '{ticker}' is listed on exchange '{entity.exchange}' but could not be found in SEC tickers database."

        # 2. Validate Ticker matches Company Name
        if ticker:
            ticker_clean = ticker.split(".")[0].lower()
            # Ticker should share some characters or initials or substrings with company name
            # Remove standard company suffix noise
            clean_name_words = [w for w in name_lower.replace(",", "").replace(".", "").split() if w not in ["corp", "corporation", "inc", "co", "ltd", "limited", "company", "plc"]]
            
            # Initials matching, e.g. "General Electric" -> "ge"
            initials = "".join([w[0] for w in clean_name_words if w])
            
            symbol_chars = set(ticker_clean)
            name_chars = set("".join(clean_name_words))
            
            is_symbol_in_name = ticker_clean in name_lower.replace(" ", "")
            is_initials_match = initials == ticker_clean or ticker_clean in initials
            is_high_overlap = len(symbol_chars.intersection(name_chars)) / len(symbol_chars) >= 0.75 if symbol_chars else False
            
            if not (is_symbol_in_name or is_initials_match or is_high_overlap):
                return False, f"INVALID: Ticker symbol '{ticker}' does not share significant name overlap or initials with company name '{name}'."

        # 3. Validate Website matches Company
        if website:
            domain = website.lower()
            # strip http, https, www, and TLD (.com, .net, etc)
            domain_clean = re.sub(r"https?://", "", domain)
            domain_clean = re.sub(r"www\.", "", domain_clean)
            domain_clean = domain_clean.split(".")[0].split("/")[0]
            
            # Check if domain name is represented in company name words
            clean_name_stripped = name_lower.replace(" ", "").replace(",", "").replace(".", "")
            
            name_words = [w for w in name_lower.replace(",", "").replace(".", "").split() if w not in ["corp", "corporation", "inc", "co", "ltd", "limited", "company", "plc"]]
            
            is_domain_in_name = domain_clean in clean_name_stripped
            is_name_word_in_domain = any(w in domain_clean for w in name_words if len(w) > 2)
            is_domain_matches_ticker = ticker and domain_clean == ticker.split(".")[0].lower()
            
            if not (is_domain_in_name or is_name_word_in_domain or is_domain_matches_ticker):
                # Allow minor exceptions, e.g. "Alphabet" -> "google.com"
                if "alphabet" in name_lower and "google" in domain_clean:
                    pass
                else:
                    return False, f"INVALID: Website domain '{domain_clean}' does not match company name '{name}'."

        return True, f"VALID: Entity resolution cross-verified for '{name}' (Ticker: {ticker or 'N/A'}, CIK: {cik or 'N/A'})."
