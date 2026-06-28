import json
import logging
from typing import Dict, Any, List

from services.models.research_execution_plan import ResearchExecutionPlan
from services.knowledge.evidence_store import EvidenceStore
from services.llm.provider_router import ProviderRouter

logger = logging.getLogger("uvicorn.error")

META_SYNTHESIS_PROMPT = """You are a Senior Partner at McKinsey.
Inputs are evidence-backed findings from a corporate intelligence pipeline.
Do NOT summarize.

Instead construct a highly synthesized report focusing on insight, narrative, and actionable recommendations.
Each statement must reference evidence IDs.
Never invent facts.
Never restate agent outputs verbatim.
Synthesize. Highlight contradictions. Explain why. State confidence. State missing evidence.

Output schema must be valid JSON:
{
  "executive_summary": "string",
  "company_story": "string",
  "industry_story": "string",
  "financial_story": "string",
  "competition_story": "string",
  "technology_story": "string",
  "ai_story": "string",
  "risk_story": "string",
  "strategic_priorities": ["list of strings"],
  "recommendations": ["list of strings"],
  "implementation_roadmap": ["list of strings"],
  "evidence_appendix": ["list of strings"],
  "confidence": 0.95,
  "missing_evidence": ["list of strings"]
}

Return ONLY the raw JSON object. Do not include markdown formatting.
"""

class SynthesizerAgent:
    """
    Consumes the accumulated EvidenceGraph (from EvidenceStore) 
    and generates the final synthesized report.
    """
    async def execute(self, plan: ResearchExecutionPlan, store: EvidenceStore, company_entity: str = None) -> Dict[str, Any]:
        
        # Pull all evidence from the store
        all_evidence = store.get_all()
        evidence_dicts = [e.model_dump() for e in all_evidence]
        
        # Optionally deduplicate or rank evidence here. For now, pass all raw evidence.
        
        aggregated_payload = {
            "planning": plan.to_summary() if hasattr(plan, "to_summary") else {},
            "target_company": company_entity,
            "evidence_graph": evidence_dicts
        }
        
        from services.artifacts.artifact_writer import ArtifactWriter
        ArtifactWriter.write_markdown("synthesis/prompt.md", json.dumps(aggregated_payload, indent=2, default=str))
        
        try:
            payload = await ProviderRouter.generate_json(
                agent_name="synthesizer",
                system_prompt=META_SYNTHESIS_PROMPT,
                user_prompt=json.dumps(aggregated_payload, default=str)
            )
        except Exception as e:
            logger.warning(f"Meta Synthesizer LLM failed: {e}. Returning fallback.")
            payload = {
                "executive_summary": "Basic synthesized summary.",
                "company_story": "",
                "industry_story": "",
                "financial_story": "",
                "competition_story": "",
                "technology_story": "",
                "ai_story": "",
                "risk_story": "",
                "strategic_priorities": [],
                "recommendations": ["Recommendation 1"],
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
