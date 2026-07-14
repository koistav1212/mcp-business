from typing import List, Dict, Any, Optional
from datetime import datetime
import re
class EventClusterer:

    @staticmethod
    def _normalize_date(date_str: str) -> str:
        if not date_str:
            return ""
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt.isoformat().replace("+00:00", "Z")
        except Exception:
            return ""

    @staticmethod
    def _normalize_text(text: str) -> str:
        if not text:
            return ""
        return " ".join(re.split(r"\s+", text.strip().lower()))

    @staticmethod
    def cluster_events(items: List[Dict[str, Any]], days_threshold: int = 2, title_overlap_threshold: int = 3) -> List[Dict[str, Any]]:
        # Normalize items: extract text and normalize date
        normalized = []
        for item in items:
            value = item.get("value", item)
            if isinstance(value, dict):
                title = value.get("title") or value.get("headline")
                date_str = value.get("date") or value.get("publishedAt")
            else:
                title = None
                date_str = None
            normalized.append({
                "_original": item,
                "_text": EventClusterer._normalize_text(title or ""),
                "_date_iso": EventClusterer._normalize_date(date_str or ""),
                "_date_dt": EventClusterer._parse_date_dt(date_str) if date_str else None,
            })

        # Sort by date descending
        normalized.sort(key=lambda x: x["_date_dt"] or datetime.min, reverse=True)

        clusters = []
        remaining = list(normalized)

        while remaining:
            seed = remaining.pop(0)
            current_cluster = [seed]
            candidates = []

            for other in remaining[:]:
                # Date proximity check
                date_diff = (seed["_date_dt"] - other["_date_dt"]).days if seed["_date_dt"] and other["_date_dt"] else None
                is_near = date_diff is not None and date_diff <= days_threshold

                # Title overlap check
                seed_words = set(seed["_text"].split())
                other_words = set(other["_text"].split())
                overlap = len(seed_words.intersection(other_words))
                is_related = overlap >= title_overlap_threshold

                if is_near and is_related:
                    current_cluster.append(other)
                    remaining.remove(other)
                    candidates.append(other)

            # Create representative from the cluster
            representative = {
                "value": {
                    "title": "",
                    "snippet": "",
                    "date": seed["_date_iso"],
                },
                "source_ids": [],
                "confidence": 0.0,
            }

            # Deduplicate items within the cluster
            unique_values = {}
            for n in current_cluster:
                val = n["_original"].get("value", n["_original"])
                if isinstance(val, dict):
                    val_key = val.get("url") or str(val)
                else:
                    val_key = str(val)
                if val_key not in unique_values:
                    unique_values[val_key] = val

            values_list = list(unique_values.values())
            representative["value"]["title"] = values_list[0].get("title") if values_list else ""
            representative["value"]["snippet"] = values_list[0].get("snippet") if values_list else ""

            # Collect all source_ids
            all_source_ids = []
            for n in current_cluster:
                all_source_ids.extend(n["_original"].get("source_ids", []))
            representative["source_ids"] = list(set(all_source_ids))

            # Calculate confidence as average
            all_confidences = [n["_original"].get("confidence", 0.0) for n in current_cluster]
            if all_confidences:
                representative["confidence"] = sum(all_confidences) / len(all_confidences)

            # Pick best title and snippet from cluster
            best_title = ""
            best_snippet = ""
            max_len = 0
            for v in values_list:
                if isinstance(v, dict):
                    s = v.get("snippet") or v.get("description") or ""
                    if len(s) > max_len:
                        max_len = len(s)
                        best_snippet = s
            if not best_snippet and best_title:
                best_snippet = best_title
            if not best_title and values_list:
                best_title = str(values_list[0])

            representative["value"]["title"] = best_title
            representative["value"]["snippet"] = best_snippet

            clusters.append(representative)

        return clusters

    @staticmethod
    def _parse_date_dt(date_str: str) -> Optional[datetime]:
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            return None
