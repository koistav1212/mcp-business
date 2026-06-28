import logging
import numpy as np
from typing import List, Dict, Any

logger = logging.getLogger("uvicorn.error")

try:
    from sentence_transformers import SentenceTransformer
    # Load model once globally
    model = SentenceTransformer('all-MiniLM-L6-v2')
except Exception as e:
    logger.warning(f"Failed to load sentence_transformers: {e}")
    model = None

class SemanticRanker:
    """
    Computes embeddings and semantic importance scores.
    """
    
    def process_all(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not model or not articles:
            for art in articles:
                art["embedding"] = []
                art["semantic_score"] = 0.5
            return articles
            
        texts = [(art.get("headline", "") + " " + art.get("summary", "")).strip() for art in articles]
        
        try:
            embeddings = model.encode(texts, convert_to_numpy=True)
            
            # Simple heuristic for importance: 
            # How similar is this article to the "average" of all news?
            # Very distant = anomaly (maybe important but maybe noise)
            # Very close = mainstream story (important)
            # We'll use distance to mean as a component of semantic_score
            if len(embeddings) > 1:
                mean_emb = np.mean(embeddings, axis=0)
                sims = np.dot(embeddings, mean_emb) / (np.linalg.norm(embeddings, axis=1) * np.linalg.norm(mean_emb))
            else:
                sims = [0.8] * len(embeddings)
                
            for i, art in enumerate(articles):
                art["embedding"] = embeddings[i].tolist()
                art["semantic_score"] = float(sims[i])
                
        except Exception as e:
            logger.debug(f"Semantic ranking failed: {e}")
            for art in articles:
                art["embedding"] = []
                art["semantic_score"] = 0.5
                
        return articles
