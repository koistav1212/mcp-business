import re
from typing import List, Dict, Any

class Deduplicator:
    @staticmethod
    def deduplicate(items: List[Dict[str, Any]], url_key: str = "url", title_key: str = "title") -> List[Dict[str, Any]]:
        seen_urls = set()
        seen_titles = set()
        deduped = []
        
        for item in items:
            val = item.get("value", item) if isinstance(item, dict) else {}
            if not isinstance(val, dict):
                deduped.append(item)
                continue
                
            url = val.get(url_key, "")
            title = val.get(title_key, "")
            
            if url:
                canonical_url = re.sub(r'\?.*$', '', url).rstrip('/')
                if canonical_url in seen_urls:
                    continue
                seen_urls.add(canonical_url)
                
            if title:
                canonical_title = re.sub(r'[^a-z0-9]', '', title.lower())
                if canonical_title and canonical_title in seen_titles:
                    continue
                if canonical_title:
                    seen_titles.add(canonical_title)
                
            deduped.append(item)
            
        return deduped
