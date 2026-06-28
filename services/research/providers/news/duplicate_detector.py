import logging
import numpy as np
from typing import List, Dict, Any

logger = logging.getLogger("uvicorn.error")

class DuplicateDetector:
    """
    Uses embeddings and cosine similarity to group duplicates and keep only the highest quality article.
    """
    
    def __init__(self, threshold: float = 0.92):
        self.threshold = threshold
        
    def deduplicate(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not articles:
            return []
            
        # Ensure they have embeddings
        valid_articles = [a for a in articles if a.get("embedding")]
        if len(valid_articles) < 2:
            return articles # Can't deduplicate if no embeddings
            
        embeddings = np.array([a["embedding"] for a in valid_articles])
        
        # Calculate pairwise cosine similarity
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        normalized_embs = embeddings / (norms + 1e-10)
        sim_matrix = np.dot(normalized_embs, normalized_embs.T)
        
        n = len(valid_articles)
        keep_indices = set(range(n))
        
        # O(N^2) comparison is fine for N < 500
        for i in range(n):
            if i not in keep_indices:
                continue
            for j in range(i + 1, n):
                if j in keep_indices and sim_matrix[i, j] >= self.threshold:
                    # They are duplicates. Which one to keep?
                    # Keep the one with a higher source_score (if available), or longer text
                    score_i = valid_articles[i].get("source_score", 0.5)
                    score_j = valid_articles[j].get("source_score", 0.5)
                    
                    if score_i > score_j:
                        keep_indices.remove(j)
                    elif score_j > score_i:
                        keep_indices.remove(i)
                        break # i is removed, move to next i
                    else:
                        # Tie breaker: text length
                        len_i = len(valid_articles[i].get("full_text", ""))
                        len_j = len(valid_articles[j].get("full_text", ""))
                        if len_i >= len_j:
                            keep_indices.remove(j)
                        else:
                            keep_indices.remove(i)
                            break
                            
        deduped = [valid_articles[i] for i in sorted(list(keep_indices))]
        
        # Add back any articles that had no embeddings (just in case)
        no_embs = [a for a in articles if not a.get("embedding")]
        
        logger.info(f"Deduplicated from {len(articles)} to {len(deduped) + len(no_embs)}")
        return deduped + no_embs
