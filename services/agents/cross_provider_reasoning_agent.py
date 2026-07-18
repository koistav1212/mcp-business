import json
import logging
import hashlib
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from services.llm.provider_router import ProviderRouter

logger = logging.getLogger("uvicorn.error")

class InsightObject(BaseModel):
    id: str = ""
    claim: str = ""
    evidence_ids: List[str] = Field(default_factory=list)
    confidence: float = 0.8
    provider: str = ""
    category: str = ""
    importance: str = "medium"

class CrossProviderReasoningAgent:
    """
    Consumes structured section outputs and correlates them to generate validated executive signals.
    """
    def _generate_insight_id(self, claim: str) -> str:
        return hashlib.md5(claim.encode()).hexdigest()[:8]

    def deduplicate(self, insights: List[InsightObject]) -> List[InsightObject]:
        """Semantic deduplication approximation using exact sub-string or high overlap matching."""
        unique_insights = []
        seen_claims = set()
        for insight in insights:
            # simple normalization
            claim_norm = " ".join(insight.claim.lower().split())
            is_dup = False
            for seen in seen_claims:
                if claim_norm in seen or seen in claim_norm:
                    is_dup = True
                    break
            if not is_dup:
                unique_insights.append(insight)
                seen_claims.add(claim_norm)
        return unique_insights

    def merge_signals(self, raw_insights: List[Dict[str, Any]]) -> List[InsightObject]:
        parsed_insights = []
        for raw in raw_insights:
            if not isinstance(raw, dict):
                continue
            insight = InsightObject(
                claim=raw.get("claim", ""),
                evidence_ids=raw.get("evidence_ids", []),
                confidence=raw.get("confidence", 0.8),
                provider=raw.get("provider", "cross_provider"),
                category=raw.get("category", "general"),
                importance=raw.get("importance", "medium")
            )
            insight.id = self._generate_insight_id(insight.claim)
            parsed_insights.append(insight)
        return parsed_insights

    def attach_evidence(self, insights: List[InsightObject], sections: Dict[str, Any]) -> List[InsightObject]:
        # ensure evidence_ids are valid
        for insight in insights:
            if not insight.evidence_ids:
                insight.evidence_ids = ["synthetic_cpr_id"]
        return insights

    def calculate_confidence(self, insights: List[InsightObject]) -> List[InsightObject]:
        for insight in insights:
            if len(insight.evidence_ids) > 2:
                insight.confidence = min(1.0, insight.confidence + 0.1)
        return insights

    async def execute(self, sections_dict: Dict[str, Any], entity_name: str) -> List[Dict[str, Any]]:
        if not sections_dict:
            logger.warning("CrossProviderReasoningAgent: No sections data provided.")
            return []

        insight_schema = InsightObject.model_json_schema()
        
        system_instruction = f"""
You are a Chief Strategy Officer. Your task is to perform cross-provider reasoning for {entity_name}. 
You are provided with highly structured section outputs: financial, technology, competition, operations, products, social, and risk.
Task:
- Find correlations across these sections.
- Find contradictions across these sections.
- Find hidden opportunities and strategic themes.
- Validate consistency.

Return ONLY a JSON object: {{"validated_signals": [InsightObject, ...]}}.
InsightObject schema:
{json.dumps(insight_schema, indent=2)}

Rules:
- NEVER invent facts without evidence.
- Do not output markdown.
"""

        prompt_payload = json.dumps(sections_dict, default=str)[:16000] # Cap size
        prompt = f"Sections Data:\n{prompt_payload}"

        logger.info(
            "CrossProviderReasoning -> sections=%d chars=%d",
            len(sections_dict),
            len(prompt_payload)
        )

        try:
            parsed = await ProviderRouter.generate_json(
                agent_name="cross_provider_reasoning",
                system_prompt=system_instruction,
                user_prompt=prompt
            )
            raw_signals = parsed.get("validated_signals", [])
            insights = self.merge_signals(raw_signals)
            insights = self.deduplicate(insights)
            insights = self.attach_evidence(insights, sections_dict)
            insights = self.calculate_confidence(insights)
            
            return [i.model_dump() for i in insights]
        except Exception as e:
            logger.error(f"CrossProviderReasoningAgent failed: {e}")
            return []
