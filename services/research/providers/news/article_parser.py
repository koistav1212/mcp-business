import logging
import trafilatura
from bs4 import BeautifulSoup
from typing import Dict, Any, List

logger = logging.getLogger("uvicorn.error")

class ArticleParser:
    """
    Parses raw HTML to extract the main article body, headline, and author.
    Uses trafilatura as the primary engine, with BeautifulSoup as fallback.
    """
    
    def parse_single(self, html: str, url: str = "") -> Dict[str, str]:
        if not html:
            return {"text": "", "summary": ""}
            
        try:
            # Trafilatura is the best for main text extraction
            extracted = trafilatura.extract(
                html,
                url=url,
                include_comments=False,
                include_tables=False,
                include_images=False,
                no_fallback=False
            )
            
            if extracted and len(extracted.strip()) > 100:
                return {
                    "text": extracted.strip(),
                    "summary": extracted[:500] + "..."
                }
                
            # Fallback to simple BeautifulSoup if trafilatura fails or returns too little
            soup = BeautifulSoup(html, "lxml")
            
            # Remove scripts and styles
            for script in soup(["script", "style", "nav", "header", "footer"]):
                script.extract()
                
            text = soup.get_text(separator="\n")
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            return {
                "text": text,
                "summary": text[:500] + "..."
            }
            
        except Exception as e:
            logger.debug(f"Error parsing article {url}: {e}")
            return {"text": "", "summary": ""}

    def parse_all(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Takes dictionaries containing 'html' and populates 'full_text' and 'summary'.
        """
        for art in articles:
            html = art.get("html")
            if html:
                parsed = self.parse_single(html, art.get("url", ""))
                art["full_text"] = parsed["text"]
                if not art.get("summary"):
                    art["summary"] = parsed["summary"]
            else:
                art["full_text"] = ""
                if not art.get("summary"):
                    art["summary"] = ""
                    
            # Remove html to save memory
            art.pop("html", None)
            
        return [a for a in articles if a.get("full_text") and len(a["full_text"]) > 100]
