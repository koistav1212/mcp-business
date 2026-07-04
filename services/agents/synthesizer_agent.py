import json
import logging
from typing import Dict, Any, List

from services.models.research_execution_plan import ResearchExecutionPlan
from services.knowledge.evidence_store import EvidenceStore
from services.llm.provider_router import ProviderRouter

logger = logging.getLogger("uvicorn.error")

META_SYNTHESIS_PROMPT = """
You are a Senior Partner at a top-tier strategy consulting firm.

OBJECTIVE:
Write a highly synthesized, evidence-backed company report.
Do NOT summarize every detail. Focus on insight, narrative, and actionable recommendations.

INPUTS:
- A planning summary (intent, research_type, required providers).
- A final_context object containing:
  - entity (name, ticker, exchange)
  - profile (overview, headquarters, employee_count, founders, competitors)
  - financials (revenue_history, net_income_history, margins, valuation_multiples)
  - news (list of news items with title, date, snippet)
  - risk_factors (if present)
  - technology_stack (may be empty or missing)
  - leadership, competitors, social_sentiment, capital_allocation, management_commentary
  - evidence_graph (nodes with ids and attributes)

RULES:
- Treat final_context as the single source of truth.
- Never invent numeric values. Only use numbers that appear in financials or analytics.
- If financials.revenue_history or net_income_history is missing, explicitly state that data is unavailable.
- Use competitors to describe competitive positioning (who, what segments).
- Use technology_stack and any AI-related attributes to discuss technology and AI usage.
  - If technology_stack is missing or empty, skip that section and instead lean on profile, financials, and news.
- Use risk_factors directly if present; otherwise infer plausible risks from industry, news, and capital_allocation, labeling them as inferred.

OUTPUT FORMAT:
Return a cohesive, well-structured natural-language report using Markdown headers.
Use this section structure:

# Executive Summary
- 3–5 bullet points on the overall story and key recommendations.

# Company Story
- Who the company is, what it does, and where it operates.
- Business model and strategic positioning.

# Financial Story
- Revenue and profit trajectory (if available).
- Key margins and capital allocation patterns (buybacks, dividends, capex).

# Competitive Landscape
- Main competitors and how this company is positioned versus them.
- Any notable strengths or weaknesses.

# Technology & AI (skip if technology_stack is missing/empty)
- Key technologies, platforms, or AI usage if present in the context.
- How technology shapes their competitive edge or risk.

# Risk & Downside
- Explicit risk_factors from the context.
- Any inferred risks from news, industry, or capital_allocation (clearly labeled as inferred).

# Strategic Priorities & Recommendations
- 3–5 concrete strategic priorities.
- For each, explain why it matters and tie it to specific context fields (financials, competitors, risk_factors, etc.).

STYLE:
- Write in clear, concise, MBA-level language.
- Do not restate raw context verbatim; always synthesize.
- Do not output JSON or code; only Markdown text.
"""

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

        aggregated_payload = {
            "planning": plan.to_summary() if hasattr(plan, "to_summary") else {},
            "target_company": company_entity,
            "final_context": filtered_context
        }
        
        from services.artifacts.artifact_writer import ArtifactWriter
        ArtifactWriter.write_markdown("synthesis/prompt.md", json.dumps(aggregated_payload, indent=2, default=str))
        
        try:
            raw_text = await ProviderRouter.generate_text(
                agent_name="synthesizer",
                system_prompt=META_SYNTHESIS_PROMPT,
                user_prompt=json.dumps(aggregated_payload, default=str)
            )
            
            # Since report builder expects a dict, we wrap the text output
            payload = {
                "executive_summary": raw_text,
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
