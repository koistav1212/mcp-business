import logging
from typing import List, Dict, Any

logger = logging.getLogger("uvicorn.error")

try:
    import spacy
    nlp = spacy.load("en_core_web_sm")
except Exception as e:
    logger.warning(f"Failed to load spacy: {e}")
    nlp = None

class EntityExtractor:
    """
    Extracts entities (Organizations, People, Locations, Products) using SpaCy.
    """
    
    def extract(self, text: str) -> Dict[str, List[str]]:
        if not nlp or not text:
            return {"organizations": [], "people": [], "countries": [], "products": []}
            
        try:
            # Only process first 2000 chars to save time
            doc = nlp(text[:2000])
            
            orgs = list(set([ent.text for ent in doc.ents if ent.label_ == "ORG"]))
            people = list(set([ent.text for ent in doc.ents if ent.label_ == "PERSON"]))
            gpe = list(set([ent.text for ent in doc.ents if ent.label_ in ("GPE", "LOC")]))
            products = list(set([ent.text for ent in doc.ents if ent.label_ == "PRODUCT"]))
            
            return {
                "organizations": orgs[:10],
                "people": people[:10],
                "countries": gpe[:5],
                "products": products[:5]
            }
        except Exception as e:
            logger.debug(f"Entity extraction failed: {e}")
            return {"organizations": [], "people": [], "countries": [], "products": []}

    def process_all(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        for art in articles:
            text = (art.get("headline", "") + " " + art.get("summary", "")).strip()
            extracted = self.extract(text)
            art["organizations"] = extracted["organizations"]
            art["people"] = extracted["people"]
            art["countries"] = extracted["countries"]
            art["products"] = extracted["products"]
            
            # Combine all for a generic entities list
            art["entities"] = extracted["organizations"] + extracted["people"] + extracted["products"]
            
        return articles
