import json
import logging
import re
from typing import Dict, Any, List

from services.models.research_execution_plan import ResearchExecutionPlan
from services.knowledge.evidence_store import EvidenceStore
from services.llm.provider_router import ProviderRouter

logger = logging.getLogger("uvicorn.error")

META_SYNTHESIS_PROMPT = """
You are a Senior Partner at a top-tier strategy consulting firm.

OBJECTIVE:
Write a polished, evidence-backed consulting report from the structured context provided.
This is a writing task, not a reasoning task. Do NOT explain your process.

INPUTS:
- A planning summary.
- A compact executive brief derived from structured evidence.
- A short evidence highlights list with the most relevant facts and signals.

RULES:
- Treat the provided brief as the single source of truth.
- Never invent facts, metrics, dates, or company details.
- Never mention missing data unless it materially affects the decision.
- Use exact numbers only when they are provided in the brief.
- Keep the tone BCG/McKinsey-style: crisp, synthetic, executive-ready.
- Do not output chain-of-thought, analysis notes, caveats about your prompt, or self-talk.
- Do not say "Thinking Process", "Analysis", "I assume", or similar phrases.

OUTPUT FORMAT:
Return only the final report in Markdown.
Structure it as 7 clear report pages/sections so it can map naturally to a 7-slide presentation:

## Page 1 - Company Snapshot & Headline Verdict
- 3-5 bullet points with the headline takeaways, key numbers, and decision implication.
- Mention company identity (who they are).

## Page 2 - Growth Engine
Structure this page so it can map to a workflow-style slide with 4-5 steps.
For each key revenue or product segment:
### 2.1 Segment 1 - <Name>
- Metric: <latest revenue or CAGR>
- Insight: <one sentence on growth or risk contribution>
### 2.2 Segment 2 - <Name>
- Metric: <latest revenue or CAGR>
- Insight: <one sentence>
(Repeat for up to 4-5 segments)

## Page 3 - Financial Quality
Provide metrics and insights for charts and tiles:
### 3.1 Growth and scale
- Describe revenue and net income history.
### 3.2 Profit quality and margins
- Discuss operating_margin, net_margin, ROE/ROA.
### 3.3 Multiples and Valuation
- Note valuation_multiples.pe_ratio, ev_ebitda, and dividend yield if available.

## Page 4 - Competitive Landscape
Structure as 6 sub-nodes around the company for a mind-map:
### 4.1 Node 1 - <Competitor Name>
- Edge: <1-2 words, e.g. 'AI leadership', 'scale'>
(Repeat for up to 6 competitors)

## Page 5 - Operating & Tech Signals
### 5.1 Tech stack
- Core technology stack.
### 5.2 Operating signals/news
- Hiring/news signals, github_repo_count, management commentary.
### 5.3 Operational Risks
- Risk factors specifically tagged as operational.

## Page 6 - Risks & Strategic Priorities
Structure as 3-5 funnel stages with a risk label and one action.
### 6.1 Funnel Stage 1 - Macro/Regulatory
- Risk: <description>
- Action: <one concrete play/action>
### 6.2 Funnel Stage 2 - Execution
- Risk: <description>
- Action: <one concrete play/action>
### 6.3 Funnel Stage 3 - Balance sheet/Capital allocation
- Risk: <description>
- Action: <one concrete play/action>

## Page 7 - KPI & Tracking
List the 4-6 most important metrics to track from analytics and financials.
### 7.1 Key Metrics
- <Metric 1>: <Value and insight>
- <Metric 2>: <Value and insight>
- <Metric 3>: <Value and insight>
- <Metric 4>: <Value and insight>

STYLE:
- Write in clear, concise, MBA-level language.
- Prefer short paragraphs and selective bullets over dense walls of text.
- Each subsection must include at least one metric or number when available.
- Do not output JSON or code.
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
    for item in raw[:limit]:
        item = _unwrap_value(item)
        if isinstance(item, dict):
            if key and item.get(key):
                items.append(str(item.get(key)))
            elif item.get("name"):
                items.append(str(item.get("name")))
            elif item.get("title"):
                items.append(str(item.get("title")))
            elif item.get("value"):
                items.append(str(item.get("value")))
            else:
                items.append(str(item))
        else:
            items.append(str(item))
    return items


def _sanitize_report_text(text: str) -> str:
    if not text:
        return ""

    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()

    header_match = re.search(r"(?im)^##?\s*Page\s*1\b.*$", cleaned)
    if not header_match:
        header_match = re.search(r"(?im)^##?\s*Executive Summary\b.*$", cleaned)
    if header_match:
        cleaned = cleaned[header_match.start():].strip()

    thinking_markers = [
        "Thinking Process:",
        "Analyze the Request:",
        "Analyze the Data:",
        "Construct JSON:",
        "Refining the Output:",
    ]
    for marker in thinking_markers:
        cleaned = cleaned.replace(marker, "")

    return cleaned.strip()


def _looks_like_invalid_report(text: str) -> bool:
    if not text:
        return True
    lowered = text.lower()
    invalid_markers = [
        "thinking process",
        "analyze input data",
        "**role:**",
        "**task:**",
        "constraints:",
    ]
    if any(marker in lowered for marker in invalid_markers):
        return True
    return "## page 1" not in lowered and "## executive summary" not in lowered


def _render_bullet_lines(items: List[str], fallback: str) -> str:
    clean_items = [item for item in items if item]
    if not clean_items:
        return f"- {fallback}"
    return "\n".join(f"- {item}" for item in clean_items)


def _render_deterministic_report(brief: Dict[str, Any]) -> str:
    company = brief.get("company_snapshot", {})
    financial = brief.get("financial_snapshot", {})
    competitive = brief.get("competitive_snapshot", {})
    signals = brief.get("operating_signals", {})
    risks = brief.get("risk_snapshot", {})
    metrics = financial.get("key_metrics", {})

    recommendation_lines = [
        "Prioritize topline reacceleration in segments where growth has moderated, while protecting margin discipline.",
        "Sustain capital allocation flexibility by balancing buybacks with selective investment in product and platform differentiation.",
        "Strengthen competitive monitoring where direct peer evidence is sparse so strategic positioning is not inferred from incomplete data.",
    ]

    return "\n".join([
        "## Page 1 - Company Snapshot & Headline Verdict",
        _render_bullet_lines([
            f"{company.get('name', 'The company')} remains a large-scale enterprise with market cap {metrics.get('market_cap', 'N/A')} and current price {metrics.get('current_price', 'N/A')}.",
            f"Valuation remains elevated at P/E {metrics.get('pe_ratio', 'N/A')}, requiring continued execution against high market expectations.",
            f"Reported annual revenue stands at {metrics.get('revenue_annual', 'N/A')}, with recent growth and margin signals needing close monitoring.",
        ], "Evidence supports a mixed but still resilient headline view."),
        "",
        "## Page 2 - Growth Engine",
        "### 2.1 Segment 1 - Core Business",
        f"- Metric: {metrics.get('revenue_annual', 'N/A')}",
        "- Insight: Primary revenue driver with stable growth.",
        "",
        "## Page 3 - Financial Quality",
        _render_bullet_lines([
            f"Revenue history: {', '.join(financial.get('revenue_history', [])[:4]) or 'N/A'}",
            f"Net income history: {', '.join(financial.get('net_income_history', [])[:4]) or 'N/A'}",
            f"Operating margin: {', '.join(financial.get('operating_margin', [])[:4]) or 'N/A'}",
            f"Capital allocation: {', '.join(f'{k}={v}' for k, v in list((financial.get('capital_allocation') or {}).items())[:3]) or 'N/A'}",
        ], "Financial evidence is partial and should be interpreted cautiously."),
        "",
        "## Page 4 - Competitive Landscape",
        _render_bullet_lines(competitive.get("competitors", []), "Direct competitor evidence is sparse in the current run, limiting precise relative benchmarking."),
        "",
        "## Page 5 - Operating & Tech Signals",
        _render_bullet_lines(
            signals.get("technology_stack", []) + signals.get("news", [])[:3],
            "Technology and operating signals are limited; recent news flow is the strongest available operating indicator."
        ),
        "",
        "## Page 6 - Risks & Strategic Priorities",
        "### 6.1 Funnel Stage 1 - Execution",
        "- Risk: " + (risks.get("risk_factors", ["Unknown execution risks"])[0] if isinstance(risks.get("risk_factors"), list) and risks.get("risk_factors") else "Unknown execution risks"),
        "- Action: " + recommendation_lines[0],
        "",
        "## Page 7 - KPI & Tracking",
        "### 7.1 Key Metrics",
        f"- Market Cap: {metrics.get('market_cap', 'N/A')}",
        f"- P/E Ratio: {metrics.get('pe_ratio', 'N/A')}",
    ])


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

    evidence_nodes = ((context_dict.get("evidence_graph") or {}).get("nodes") or [])[:12]
    evidence_highlights = [
        {
            "category": node.get("category", "general"),
            "fact": str(node.get("fact", ""))[:220],
            "confidence": node.get("confidence"),
        }
        for node in evidence_nodes
        if node.get("fact")
    ]

    return {
        "target_company": company_entity or profile.get("name"),
        "planning_summary": plan.to_summary() if hasattr(plan, "to_summary") else {},
        "company_snapshot": {
            "name": profile.get("name") or company_entity,
            "overview": profile.get("overview"),
            "headquarters": _format_scalar(profile.get("headquarters")),
            "employee_count": _format_scalar(profile.get("employee_count")),
            "website": _format_scalar(profile.get("website")),
            "founders": _top_list_items(profile.get("founders"), limit=5),
        },
        "financial_snapshot": {
            "key_metrics": key_metrics,
            "revenue_history": _top_dict_items(financials.get("revenue_history")),
            "net_income_history": _top_dict_items(financials.get("net_income_history")),
            "operating_income_history": _top_dict_items(financials.get("operating_income_history")),
            "revenue_growth": _top_dict_items(analytics.get("revenue_growth")),
            "profit_growth": _top_dict_items(analytics.get("profit_growth")),
            "operating_margin": _top_dict_items(analytics.get("operating_margin")),
            "cagr": _top_dict_items(analytics.get("cagr")),
            "valuation": {k: _format_scalar(v) for k, v in list(valuation.items())[:6]},
            "capital_allocation": {k: _format_scalar(v) for k, v in list(capital_allocation.items())[:6]},
        },
        "competitive_snapshot": {
            "competitors": _top_list_items(competitors, limit=6, key="name"),
            "leadership": _top_list_items(leadership, limit=5, key="name"),
        },
        "operating_signals": {
            "technology_stack": _top_list_items(technology_stack, limit=8, key="name"),
            "management_commentary": _top_list_items(management_commentary, limit=4, key="quote"),
            "news": _top_list_items(news, limit=6, key="title"),
        },
        "risk_snapshot": {
            "risk_factors": _top_list_items(risk_factors, limit=6, key="factor"),
        },
        "evidence_highlights": evidence_highlights,
    }

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
                "company_story": "",
                "industry_story": "",
                "financial_story": "",
                "competition_story": "",
                "technology_story": "",
                "ai_story": "",
                "risk_story": "",
                "strategic_priorities": [],
                "recommendations": [],
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
        
        from services.artifacts.artifact_writer import ArtifactWriter
        ArtifactWriter.write_markdown("synthesis/prompt.md", json.dumps(aggregated_payload, indent=2, default=str))
        
        try:
            raw_text = await ProviderRouter.generate_text(
                agent_name="synthesizer",
                system_prompt=META_SYNTHESIS_PROMPT,
                user_prompt=json.dumps(aggregated_payload, default=str)
            )
            cleaned_text = _sanitize_report_text(raw_text)
            if _looks_like_invalid_report(cleaned_text):
                logger.warning("Synthesizer returned invalid/non-compliant report text. Falling back to deterministic renderer.")
                cleaned_text = _render_deterministic_report(aggregated_payload)
            
            # Since report builder expects a dict, we wrap the text output
            payload = {
                "executive_summary": cleaned_text,
                "company_story": "",
                "industry_story": "",
                "financial_story": "",
                "competition_story": "",
                "technology_story": "",
                "ai_story": "",
                "risk_story": "",
                "strategic_priorities": [],
                "recommendations": [],
                "implementation_roadmap": [],
                "evidence_appendix": [],
                "confidence": 0.9,
                "missing_evidence": []
            }
        except Exception as e:
            logger.error(f"Meta Synthesizer LLM failed completely: {e}. Returning fallback stub.")
            payload = {
                "executive_summary": "Error: Meta Synthesizer LLM failed. This is a fallback stub.",

                "company_story": "",
                "industry_story": "",
                "financial_story": "",
                "competition_story": "",
                "technology_story": "",
                "ai_story": "",
                "risk_story": "",
                "strategic_priorities": [],
                "recommendations": [],
                "implementation_roadmap": [],
                "evidence_appendix": [],
                "confidence": 0.5,
                "missing_evidence": []
            }
                
        ArtifactWriter.write_json("synthesis/executive_report.json", payload)
        ArtifactWriter.write_json("final/executive_report.json", payload)
        
        if "executive_summary" in payload:
            ArtifactWriter.write_markdown("final/executive_summary.md", payload["executive_summary"])
            
        return payload
