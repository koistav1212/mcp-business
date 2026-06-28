import asyncio
import json
import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx

from services.knowledge.evidence import ResearchEvidence
from services.knowledge.citation_manager import CitationManager
from services.artifacts.artifact_writer import ArtifactWriter

logger = logging.getLogger("uvicorn.error")

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_BOT_UA = "MCPBusinessIntelligenceBot/1.0 (contact@mcp-business.com)"

BROWSER_HEADERS = {
    "User-Agent": _BROWSER_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}
BOT_HEADERS = {"User-Agent": _BOT_UA}
JSON_HEADERS = {**BROWSER_HEADERS, "Accept": "application/json"}

def _write_json(filename: str, data: Any) -> None:
    try:
        ArtifactWriter.write_json(f"provider_outputs/{filename}", data)
    except Exception as exc:
        logger.debug(f"JSON write failed {filename}: {exc}")

def _clean_nan(obj: Any) -> Any:
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: _clean_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean_nan(x) for x in obj]
    return obj

async def _get(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: Optional[Dict] = None,
    params: Optional[Dict] = None,
    timeout: float = 12.0,
) -> Optional[httpx.Response]:
    try:
        r = await client.get(
            url, headers=headers or BROWSER_HEADERS, params=params, timeout=timeout
        )
        if r.status_code == 200:
            return r
        logger.debug(f"HTTP {r.status_code} for {url}")
    except Exception as exc:
        logger.debug(f"GET failed {url}: {exc}")
    return None

def _emit(
    evidence_list: List[ResearchEvidence],
    *,
    entity: str,
    attribute: str,
    value: Any,
    source: str,
    source_type: str,
    confidence: float,
    freshness: Optional[str] = None,
    source_url: Optional[str] = None,
    now_str: Optional[str] = None,
) -> None:
    if value is None or value == "" or value == [] or value == {}:
        return
    if isinstance(value, str) and value.strip() in ("N/A", "Unknown", "null", "None"):
        return
    ev = ResearchEvidence(
        id=CitationManager.generate_id(
            source, entity, attribute, freshness or now_str or "current"
        ),
        entity=entity,
        attribute=attribute,
        value=value,
        source=source,
        source_type=source_type,
        confidence=min(1.0, max(0.0, confidence)),
        freshness=freshness or now_str,
    )
    if hasattr(ev, "source_url") and source_url:
        ev.source_url = source_url
    evidence_list.append(ev)
