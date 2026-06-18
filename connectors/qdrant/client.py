import logging
from typing import Any, Dict, List, ClassVar
from connectors.base import BaseConnector

logger = logging.getLogger(__name__)

class QdrantConnector(BaseConnector):
    """
    Simulates a connection to a Qdrant Vector database.
    Indexes text documents in memory and performs scoring search lookups.
    """
    name: str = "qdrant"
    _connected: bool = False
    _collection: ClassVar[List[Dict[str, Any]]] = []

    async def connect(self) -> Any:
        logger.info("Connecting to Qdrant vector database client.")
        self._connected = True
        return self

    async def close(self) -> None:
        logger.info("Closing Qdrant vector database connection.")
        self._connected = False

    async def upsert(self, doc_id: str, text: str, metadata: Dict[str, Any] = None) -> bool:
        """
        Simulates upserting a vector point. Stores the raw text and metadata.
        """
        if not self._connected:
            await self.connect()
            
        # Overwrite if ID matches
        for point in self._collection:
            if point["id"] == doc_id:
                point["text"] = text
                point["metadata"] = metadata or {}
                logger.info(f"[QdrantConnector] Updated document ID: {doc_id}")
                return True
                
        self._collection.append({
            "id": doc_id,
            "text": text,
            "metadata": metadata or {}
        })
        logger.info(f"[QdrantConnector] Upserted new document ID: {doc_id}")
        return True

    async def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Simulates cosine similarity search using token overlap scoring.
        """
        if not self._connected:
            await self.connect()
            
        query_words = query.lower().split()
        results = []
        for point in self._collection:
            score = 0.0
            point_text_lower = point["text"].lower()
            for word in query_words:
                if word in point_text_lower:
                    score += 0.5
            
            if score > 0:
                results.append({
                    "id": point["id"],
                    "text": point["text"],
                    "metadata": point["metadata"],
                    "score": score
                })
                
        # Sort results by match score
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]
