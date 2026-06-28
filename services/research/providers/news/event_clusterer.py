import logging
import numpy as np
from typing import List, Dict, Any

logger = logging.getLogger("uvicorn.error")

class EventClusterer:
    """
    Groups articles into distinct events using a looser cosine similarity threshold.
    """
    
    def __init__(self, threshold: float = 0.75):
        # A looser threshold than duplicate detection
        self.threshold = threshold
        
    def cluster(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Assigns an 'event_cluster' string to each article.
        """
        if not articles:
            return []
            
        valid_articles = [a for a in articles if a.get("embedding")]
        if not valid_articles:
            for i, a in enumerate(articles):
                a["event_cluster"] = f"Event_{i}"
            return articles
            
        embeddings = np.array([a["embedding"] for a in valid_articles])
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        normalized_embs = embeddings / (norms + 1e-10)
        sim_matrix = np.dot(normalized_embs, normalized_embs.T)
        
        n = len(valid_articles)
        visited = set()
        clusters = []
        
        for i in range(n):
            if i in visited:
                continue
                
            # Start a new cluster
            current_cluster = [i]
            visited.add(i)
            
            # Find all related articles
            for j in range(i + 1, n):
                if j not in visited and sim_matrix[i, j] >= self.threshold:
                    current_cluster.append(j)
                    visited.add(j)
                    
            clusters.append(current_cluster)
            
        # Assign cluster names
        for cluster_idx, article_indices in enumerate(clusters):
            # Give the cluster a generic name based on the first article's headline
            head_idx = article_indices[0]
            cluster_name = f"Event: {valid_articles[head_idx].get('headline', 'Unknown')[:50]}"
            
            for idx in article_indices:
                valid_articles[idx]["event_cluster"] = cluster_name
                
        # Handle articles without embeddings
        for i, a in enumerate(articles):
            if not a.get("event_cluster"):
                a["event_cluster"] = f"Standalone_{i}"
                
        return articles
