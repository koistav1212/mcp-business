import json
import logging
import re
import ast
import copy
from typing import Dict, Any, List

from services.models.research_execution_plan import ResearchExecutionPlan
from services.knowledge.evidence_store import EvidenceStore
from services.llm.provider_router import ProviderRouter

logger = logging.getLogger("uvicorn.error")

META_SYNTHESIS_PROMPT = """
You are an executive report writer optimized for a small local model.

Task:
Convert the provided compact brief into a polished consulting-style report.
This is a writing task only. Do not explain reasoning. Do not add facts.

Use these rules:
- Use only facts that appear in the input brief.
- Reuse exact metrics and dates when they are provided.
- If a section has limited evidence, say evidence is limited instead of guessing.
- Keep wording crisp, senior, and board-ready.
- No markdown. No code fences. No commentary. Output JSON only.
- The first character of your response must be { and the last character must be }.
- Do not include any preface such as "Thinking Process", "Here is the JSON", or explanations.

Input shape:
- planning_summary: short context about the research objective
- executive_facts: highest-priority identity and financial facts
- section_packets: compact section-by-section fact packets
- evidence_highlights: short supporting facts

Return exactly this JSON shape with no extra top-level keys:
{
  "executive_summary": {
    "headline": "string",
    "verdict": "string",
    "bullets": ["string", "string", "string"]
  },
  "growth": {
    "title": "Growth",
    "question": "string",
    "evidence": ["string"],
    "insights": ["string"],
    "implications": ["string"],
    "recommendations": ["string"]
  },
  "financial_quality": {
    "title": "Financial Quality",
    "question": "string",
    "evidence": ["string"],
    "insights": ["string"],
    "implications": ["string"],
    "recommendations": ["string"]
  },
  "competition": {
    "title": "Competition",
    "question": "string",
    "evidence": ["string"],
    "insights": ["string"],
    "implications": ["string"],
    "recommendations": ["string"]
  },
  "operations": {
    "title": "Operations",
    "question": "string",
    "evidence": ["string"],
    "insights": ["string"],
    "implications": ["string"],
    "recommendations": ["string"]
  },
  "risks": {
    "title": "Risks",
    "question": "string",
    "evidence": ["string"],
    "insights": ["string"],
    "implications": ["string"],
    "recommendations": ["string"]
  },
  "kpis": {
    "title": "KPIs",
    "question": "string",
    "evidence": ["string"],
    "insights": ["string"],
    "implications": ["string"],
    "recommendations": ["string"]
  },
  "confidence": 0.0,
  "evidence_gaps": ["string"]
}

Additional output constraints:
- executive_summary.bullets: 3 to 5 bullets
- For each section: evidence max 3 items, insights max 2, implications max 2, recommendations max 2
- confidence must be between 0.0 and 1.0
- evidence_gaps should be short and specific

Preferred style:
- sound like a top-tier strategy memo
- short sentences
- synthesis over repetition
- use numbers where available
"""


def _unwrap_value(value: Any) -> Any:
    if isinstance(value, dict) and "value" in value:
        return value.get("value")
    return value


def _is_present(value: Any) -> bool:
    if value in (None, "", [], {}):
        return False
    return True


def _format_scalar(value: Any) -> str:
    value = _unwrap_value(value)
    if value in (None, "", [], {}):
        return "N/A"
    if isinstance(value, float):
        return f"{value:.2f}"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, dict):
        items = list(value.items())[:4]
        return ", ".join(f"{k}: {v}" for k, v in items)
    if isinstance(value, list):
        return ", ".join(str(_unwrap_value(v)) for v in value[:5])
    return str(value)


def _safe_literal_parse(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text or text[0] not in "{[":
        return value
    try:
        return ast.literal_eval(text)
    except (SyntaxError, ValueError):
        return value


def _truncate_text(value: Any, limit: int = 220) -> str:
    text = _format_scalar(value)
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _dedupe_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    deduped: List[str] = []
    for item in items:
        normalized = item.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(item.strip())
    return deduped


def _is_meaningful(value: Any) -> bool:
    if value in (None, "", [], {}, "N/A", "Unknown", "unknown"):
        return False
    return True


def _top_dict_items(value: Any, limit: int = 4) -> List[str]:
    value = _unwrap_value(value)
    if not isinstance(value, dict):
        return []
    items = list(value.items())[:limit]
    return [f"{k}: {v}" for k, v in items]


def _top_list_items(value: Any, limit: int = 5, key: str = None) -> List[str]:
    raw = _unwrap_value(value)
    if not isinstance(raw, list):
        return []
    items: List[str] = []
    for item in raw:
        item = _unwrap_value(item)
        item = _safe_literal_parse(item)
        if isinstance(item, dict):
            if key and item.get(key):
                items.append(_truncate_text(item.get(key), limit=180))
            elif item.get("name"):
                items.append(_truncate_text(item.get("name"), limit=180))
            elif item.get("title"):
                items.append(_truncate_text(item.get("title"), limit=180))
            elif item.get("headline"):
                items.append(_truncate_text(item.get("headline"), limit=180))
            elif item.get("risk"):
                items.append(_truncate_text(item.get("risk"), limit=180))
            elif item.get("quote"):
                items.append(_truncate_text(item.get("quote"), limit=180))
            elif item.get("value"):
                items.append(_truncate_text(item.get("value"), limit=180))
            else:
                items.append(_truncate_text(item, limit=180))
        else:
            items.append(_truncate_text(item, limit=180))
    return _dedupe_preserve_order(items)[:limit]


def _compact_metric_dict(value: Any, keys: List[str]) -> Dict[str, str]:
    raw = _unwrap_value(value)
    if not isinstance(raw, dict):
        return {}
    compact: Dict[str, str] = {}
    for key in keys:
        if key in raw and _is_present(raw[key]):
            compact[key] = _truncate_text(raw[key], limit=120)
    return compact


def _first_meaningful(values: List[Any], fallback: str = "Evidence limited.") -> str:
    for value in values:
        if _is_meaningful(value):
            return str(value)
    return fallback


def _compact_plan_summary(plan: ResearchExecutionPlan) -> Dict[str, Any]:
    return {
        "goal": _truncate_text(getattr(plan, "goal", ""), limit=120),
        "research_type": getattr(getattr(plan, "research_type", None), "value", getattr(plan, "research_type", "")),
        "decision_type": getattr(plan, "decision_type", ""),
        "workspace_type": getattr(plan, "workspace_type", ""),
        "analysis_depth": getattr(getattr(plan, "analysis_depth", None), "value", getattr(plan, "analysis_depth", "")),
        "required_providers": list(getattr(plan, "required_providers", [])[:5]),
    }


def _collect_fact_lines(pairs: List[tuple[str, Any]], limit: int = 4) -> List[str]:
    facts: List[str] = []
    for label, value in pairs:
        if not _is_meaningful(value):
            continue
        facts.append(f"{label}: {value}")
        if len(facts) >= limit:
            break
    return facts


def _build_section_packets(
    company_name: str,
    key_metrics: Dict[str, str],
    financial_snapshot: Dict[str, Any],
    competitive_snapshot: Dict[str, Any],
    operating_signals: Dict[str, Any],
    risk_snapshot: Dict[str, Any],
    evidence_highlights: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    growth_facts = _collect_fact_lines(
        [
            ("Annual revenue", key_metrics.get("revenue_annual")),
            ("Revenue history", ", ".join(financial_snapshot.get("revenue_history", [])[:2])),
            ("Revenue growth", ", ".join(financial_snapshot.get("revenue_growth", [])[:2])),
            ("Recent momentum", _first_meaningful([item.get("title") for item in operating_signals.get("news", [])], fallback="")),
        ],
        limit=4,
    )
    financial_facts = _collect_fact_lines(
        [
            ("Market cap", key_metrics.get("market_cap")),
            ("Current price", key_metrics.get("current_price")),
            ("P/E ratio", key_metrics.get("pe_ratio")),
            ("Operating margin", ", ".join(financial_snapshot.get("operating_margin", [])[:2])),
            ("Debt/equity", key_metrics.get("debt_equity")),
        ],
        limit=4,
    )
    competition_facts = _collect_fact_lines(
        [
            ("Competitors", ", ".join(competitive_snapshot.get("competitors", [])[:4])),
            ("Leadership", ", ".join(competitive_snapshot.get("leadership", [])[:4])),
            ("Category", company_name),
        ],
        limit=4,
    )
    operations_facts = _collect_fact_lines(
        [
            ("Technology stack", ", ".join(operating_signals.get("technology_stack", [])[:4])),
            ("Management commentary", ", ".join(operating_signals.get("management_commentary", [])[:2])),
            ("Recent news", _first_meaningful([item.get("title") for item in operating_signals.get("news", [])], fallback="")),
        ],
        limit=4,
    )
    risk_facts = _collect_fact_lines(
        [
            ("Risk factors", ", ".join(risk_snapshot.get("risk_factors", [])[:3])),
            ("Risk news", _first_meaningful([item.get("fact") for item in evidence_highlights if item.get("category") in {"risk", "news_intelligence"}], fallback="")),
        ],
        limit=4,
    )
    kpi_facts = _collect_fact_lines(
        [
            ("Revenue", key_metrics.get("revenue_annual")),
            ("Market cap", key_metrics.get("market_cap")),
            ("P/E", key_metrics.get("pe_ratio")),
            ("52-week range", f"{key_metrics.get('52_week_low')} to {key_metrics.get('52_week_high')}" if _is_meaningful(key_metrics.get("52_week_low")) and _is_meaningful(key_metrics.get("52_week_high")) else ""),
        ],
        limit=4,
    )
    return {
        "growth": {
            "question": "What is driving growth and scale?",
            "facts": growth_facts,
            "writing_angle": "Emphasize scale, momentum, and the main growth engine.",
        },
        "financial_quality": {
            "question": "What is the quality of the financial profile?",
            "facts": financial_facts,
            "writing_angle": "Assess strength, valuation context, and financial resilience.",
        },
        "competition": {
            "question": "How is the company positioned competitively?",
            "facts": competition_facts,
            "writing_angle": "Summarize leadership, category position, and competitor context.",
        },
        "operations": {
            "question": "What operating and technology signals matter most?",
            "facts": operations_facts,
            "writing_angle": "Highlight operating capabilities, platform signals, and execution indicators.",
        },
        "risks": {
            "question": "What are the most relevant risks and watchouts?",
            "facts": risk_facts,
            "writing_angle": "Keep risk framing specific and decision-relevant.",
        },
        "kpis": {
            "question": "What KPIs should leadership monitor?",
            "facts": kpi_facts,
            "writing_angle": "Recommend the few metrics leadership should track going forward.",
        },
    }


def _brief_size_chars(brief: Dict[str, Any]) -> int:
    return len(json.dumps(brief, default=str))


def _fit_brief_for_small_model(brief: Dict[str, Any], max_chars: int = 6500) -> Dict[str, Any]:
    fitted = copy.deepcopy(brief)
    if _brief_size_chars(fitted) <= max_chars:
        return fitted

    fitted["evidence_highlights"] = fitted.get("evidence_highlights", [])[:6]
    for packet in fitted.get("section_packets", {}).values():
        packet["facts"] = packet.get("facts", [])[:3]
    if _brief_size_chars(fitted) <= max_chars:
        return fitted

    company = fitted.get("company_snapshot", {})
    if company.get("overview"):
        company["overview"] = _truncate_text(company["overview"], limit=240)
    fitted["operating_signals"]["news"] = fitted.get("operating_signals", {}).get("news", [])[:3]
    fitted["operating_signals"]["technology_stack"] = fitted.get("operating_signals", {}).get("technology_stack", [])[:3]
    if _brief_size_chars(fitted) <= max_chars:
        return fitted

    fitted["evidence_highlights"] = fitted.get("evidence_highlights", [])[:4]
    fitted["competitive_snapshot"]["leadership"] = fitted.get("competitive_snapshot", {}).get("leadership", [])[:3]
    fitted["competitive_snapshot"]["competitors"] = fitted.get("competitive_snapshot", {}).get("competitors", [])[:3]
    return fitted


def _compact_news_items(value: Any, limit: int = 4) -> List[Dict[str, str]]:
    raw = _unwrap_value(value)
    if not isinstance(raw, list):
        return []
    items: List[Dict[str, str]] = []
    seen = set()
    for item in raw:
        item = _unwrap_value(item)
        item = _safe_literal_parse(item)
        if isinstance(item, dict) and "value" in item:
            item = _unwrap_value(item["value"])
            item = _safe_literal_parse(item)
        if not isinstance(item, dict):
            continue
        title = item.get("title") or item.get("headline")
        url = item.get("url")
        if not title:
            continue
        dedupe_key = (str(title).strip().lower(), str(url or "").strip().lower())
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        items.append(
            {
                "title": _truncate_text(title, limit=160),
                "date": _truncate_text(item.get("date"), limit=40) if item.get("date") else "",
                "type": _truncate_text(item.get("type"), limit=60) if item.get("type") else "",
            }
        )
        if len(items) >= limit:
            break
    return items


def _sanitize_report_text(text: str) -> str:
    return text.strip()

def _looks_like_invalid_report(report: dict) -> bool:
    if not report:
        return True
    if not isinstance(report, dict):
        return True
    if "executive_summary" not in report:
        return True
    return False

def _render_bullet_lines(items: List[str], fallback: str) -> str:
    clean_items = [item for item in items if item]
    if not clean_items:
        return f"- {fallback}"
    return "\n".join(f"- {item}" for item in clean_items)


def _render_deterministic_report(brief: Dict[str, Any]) -> dict:
    company = brief.get("company_snapshot", {})
    financial = brief.get("financial_snapshot", {})
    competitive = brief.get("competitive_snapshot", {})
    signals = brief.get("operating_signals", {})
    risks = brief.get("risk_snapshot", {})
    metrics = financial.get("key_metrics", {})

    return {
        "executive_summary": {
            "headline": f"{company.get('name', 'The company')} remains a large-scale enterprise.",
            "verdict": "Evidence supports a mixed but resilient headline view.",
            "bullets": [
                f"Market cap {metrics.get('market_cap', 'N/A')} and current price {metrics.get('current_price', 'N/A')}.",
                f"Valuation at P/E {metrics.get('pe_ratio', 'N/A')}.",
                f"Reported annual revenue stands at {metrics.get('revenue_annual', 'N/A')}."
            ][:5]
        },
        "growth": {
            "title": "Growth Engine",
            "question": "What drives revenue growth?",
            "evidence": [f"Revenue: {metrics.get('revenue_annual', 'N/A')}"],
            "insights": ["Primary revenue driver with stable growth."],
            "implications": [],
            "recommendations": []
        },
        "financial_quality": {
            "title": "Financial Quality",
            "question": "What is the financial health?",
            "evidence": [],
            "insights": ["Financial evidence is partial and should be interpreted cautiously."],
            "implications": [],
            "recommendations": []
        },
        "competition": {
            "title": "Competitive Landscape",
            "question": "How does the company compare to competitors?",
            "evidence": [],
            "insights": ["Direct competitor evidence is sparse."],
            "implications": [],
            "recommendations": []
        },
        "operations": {
            "title": "Operating Signals",
            "question": "What are the latest operating and tech signals?",
            "evidence": [],
            "insights": ["Technology and operating signals are limited."],
            "implications": [],
            "recommendations": []
        },
        "risks": {
            "title": "Risks & Strategic Priorities",
            "question": "What are the key risks?",
            "evidence": [],
            "insights": [(risks.get("risk_factors", ["Unknown execution risks"])[0] if isinstance(risks.get("risk_factors"), list) and risks.get("risk_factors") else "Unknown execution risks")],
            "implications": [],
            "recommendations": ["Prioritize topline reacceleration."]
        },
        "kpis": {
            "title": "KPIs",
            "question": "What KPIs should be tracked?",
            "evidence": [f"Market Cap: {metrics.get('market_cap', 'N/A')}", f"P/E Ratio: {metrics.get('pe_ratio', 'N/A')}"],
            "insights": [],
            "implications": [],
            "recommendations": []
        },
        "confidence": 0.5,
        "evidence_gaps": ["Fallback report generated."]
    }


def _build_compact_brief(plan: ResearchExecutionPlan, context_dict: Dict[str, Any], company_entity: str = None) -> Dict[str, Any]:
    profile = context_dict.get("profile") or {}
    financials = context_dict.get("financials") or {}
    analytics = context_dict.get("analytics") or {}
    valuation = context_dict.get("valuation_multiples") or {}
    capital_allocation = context_dict.get("capital_allocation") or {}
    competitors = context_dict.get("competitors") or []
    leadership = context_dict.get("leadership") or []
    technology_stack = context_dict.get("technology_stack") or []
    news = context_dict.get("news") or []
    risk_factors = context_dict.get("risk_factors") or financials.get("risk_factors") or []
    management_commentary = context_dict.get("management_commentary") or []

    key_metrics = {
        "market_cap": _format_scalar(financials.get("market_cap")),
        "current_price": _format_scalar(financials.get("current_price")),
        "pe_ratio": _format_scalar(financials.get("pe_ratio") or valuation.get("pe_ratio")),
        "revenue_annual": _format_scalar(financials.get("revenue_annual")),
        "funding_total": _format_scalar(financials.get("funding_total")),
        "last_round": _format_scalar(financials.get("last_round")),
        "debt_equity": _format_scalar(analytics.get("debt_equity")),
        "52_week_high": _format_scalar(financials.get("fifty_two_week_high")),
        "52_week_low": _format_scalar(financials.get("fifty_two_week_low")),
    }

    evidence_nodes = ((context_dict.get("evidence_graph") or {}).get("nodes") or [])[:8]
    evidence_highlights = [
        {
            "category": node.get("category", "general"),
            "fact": str(node.get("fact", ""))[:160],
            "confidence": node.get("confidence"),
        }
        for node in evidence_nodes
        if node.get("fact")
    ]
    company_snapshot = {
        "name": profile.get("name") or company_entity,
        "overview": _truncate_text(profile.get("overview"), limit=320),
        "headquarters": _format_scalar(profile.get("headquarters")),
        "employee_count": _format_scalar(profile.get("employee_count")),
        "website": _format_scalar(profile.get("website")),
        "founders": _top_list_items(profile.get("founders"), limit=3),
    }
    financial_snapshot = {
        "key_metrics": key_metrics,
        "revenue_history": _top_dict_items(financials.get("revenue_history"), limit=2),
        "net_income_history": _top_dict_items(financials.get("net_income_history"), limit=2),
        "operating_income_history": _top_dict_items(financials.get("operating_income_history"), limit=2),
        "revenue_growth": _top_dict_items(analytics.get("revenue_growth"), limit=2),
        "profit_growth": _top_dict_items(analytics.get("profit_growth"), limit=2),
        "operating_margin": _top_dict_items(analytics.get("operating_margin"), limit=2),
        "cagr": _top_dict_items(analytics.get("cagr"), limit=2),
        "valuation": _compact_metric_dict(valuation, ["pe_ratio", "ev_ebitda", "price_to_sales"]),
        "capital_allocation": _compact_metric_dict(capital_allocation, ["buybacks", "dividends", "capex_trend"]),
    }
    competitive_snapshot = {
        "competitors": _top_list_items(competitors, limit=4, key="name"),
        "leadership": _top_list_items(leadership, limit=4, key="name"),
    }
    operating_signals = {
        "technology_stack": _top_list_items(technology_stack, limit=5, key="name"),
        "management_commentary": _top_list_items(management_commentary, limit=3, key="quote"),
        "news": _compact_news_items(news, limit=4),
    }
    risk_snapshot = {
        "risk_factors": _top_list_items(risk_factors, limit=4, key="factor"),
    }
    brief = {
        "target_company": company_entity or profile.get("name"),
        "planning_summary": _compact_plan_summary(plan),
        "company_snapshot": company_snapshot,
        "executive_facts": {
            "identity": {
                "company": company_snapshot.get("name"),
                "headquarters": company_snapshot.get("headquarters"),
                "employees": company_snapshot.get("employee_count"),
                "website": company_snapshot.get("website"),
            },
            "financials": {k: v for k, v in key_metrics.items() if _is_meaningful(v)},
        },
        "financial_snapshot": financial_snapshot,
        "competitive_snapshot": competitive_snapshot,
        "operating_signals": operating_signals,
        "risk_snapshot": risk_snapshot,
        "section_packets": _build_section_packets(
            company_snapshot.get("name") or company_entity or "The company",
            key_metrics,
            financial_snapshot,
            competitive_snapshot,
            operating_signals,
            risk_snapshot,
            evidence_highlights,
        ),
        "evidence_highlights": evidence_highlights,
    }
    return _fit_brief_for_small_model(brief)

class SynthesizerAgent:
    """
    Consumes the accumulated EvidenceGraph (from EvidenceStore) 
    and generates the final synthesized report.
    """
    async def execute(self, plan: ResearchExecutionPlan, context_dict: Dict[str, Any], company_entity: str = None) -> Dict[str, Any]:
        
        # Validate that we actually have evidence before synthesizing
        evidence_graph = context_dict.get("evidence_graph", {})
        nodes = evidence_graph.get("nodes", [])
        
        if not nodes:
            logger.error("Synthesizer called with empty evidence graph! Aborting to prevent hallucination.")
            return {
                "executive_summary": "Error: Pipeline failed to retrieve any evidence. Synthesis aborted.",
                "key_findings": ["No evidence found"],
                "risks": ["Pipeline failure"],
                "opportunities": [],
                "recommendations": [],
                "evidence_gaps": ["All evidence"],
                "company_story": "",
                "industry_story": "",
                "financial_story": "",
                "competition_story": "",
                "technology_story": "",
                "ai_story": "",
                "risk_story": "",
                "strategic_priorities": [],
                "implementation_roadmap": [],
                "evidence_appendix": [],
                "confidence": 0.0,
                "missing_evidence": ["All evidence"]
            }
        
        # Remove raw_data to prevent LLM Payload Too Large errors
        filtered_context = {k: v for k, v in context_dict.items() if k != "raw_data"}
        
        # Limit evidence graph nodes to top 100 to prevent context limit errors
        if "evidence_graph" in filtered_context and isinstance(filtered_context["evidence_graph"], dict):
            nodes = filtered_context["evidence_graph"].get("nodes", [])
            if len(nodes) > 100:
                logger.info(f"Truncating evidence graph from {len(nodes)} to 100 nodes for synthesizer payload.")
                filtered_context["evidence_graph"]["nodes"] = nodes[:100]

        aggregated_payload = _build_compact_brief(plan, filtered_context, company_entity)
        aggregated_payload_json = json.dumps(aggregated_payload, default=str)
        
        from services.artifacts.artifact_writer import ArtifactWriter
        ArtifactWriter.write_markdown("synthesis/prompt.md", json.dumps(aggregated_payload, indent=2, default=str))
        ArtifactWriter.write_json("synthesis/payload_stats.json", {
            "payload_chars": len(aggregated_payload_json),
            "evidence_highlights": len(aggregated_payload.get("evidence_highlights", [])),
            "section_packet_fact_counts": {
                section: len(packet.get("facts", []))
                for section, packet in aggregated_payload.get("section_packets", {}).items()
            },
        })
        
        try:
            from services.research.models import SynthesisOutput
            
            raw_json = await ProviderRouter.generate_json(
                agent_name="synthesizer",
                system_prompt=META_SYNTHESIS_PROMPT,
                user_prompt=aggregated_payload_json
            )
            if _looks_like_invalid_report(raw_json):
                logger.warning("Synthesizer returned invalid/non-compliant JSON. Falling back to deterministic renderer.")
                raw_json = _render_deterministic_report(aggregated_payload)
            
            # Truncate and validate via Pydantic
            validated_output = SynthesisOutput(**raw_json)
            payload = validated_output.model_dump()
            
            # Keep legacy fields for a short while
            payload["key_findings"] = []
            payload["legacy_risks"] = []
            payload["opportunities"] = []
            payload["recommendations"] = []
            
        except Exception as e:
            logger.error(f"Meta Synthesizer LLM failed completely: {e}. Returning fallback stub.")
            stub = _render_deterministic_report(aggregated_payload)
            from services.research.models import SynthesisOutput
            payload = SynthesisOutput(**stub).model_dump()
            payload["key_findings"] = []
            payload["legacy_risks"] = []
            payload["opportunities"] = []
            payload["recommendations"] = []
                
        ArtifactWriter.write_json("synthesis/executive_report.json", payload)
        ArtifactWriter.write_json("final/executive_report.json", payload)
            
        return payload
