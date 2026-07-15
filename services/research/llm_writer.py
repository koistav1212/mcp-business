import json
from typing import Awaitable, Callable, Optional

from services.schemas.insight import CitedInsight, DraftReport, EvidenceGraph, IndustryContext, IntentPlan, ReportPlan, ResearchPlan


WRITER_SYSTEM_PROMPT = """You are a Senior Strategy Consultant. Use only the verified evidence supplied.
Never invent facts. Explicitly state evidence gaps. Adapt the analysis to the industry, prioritize
implications over summaries, and cite evidence IDs for every factual claim. Return JSON matching
the requested schema."""


class LLMWriter:
    """Evidence-grounded writer with an injectable LLM and safe local fallback."""

    def __init__(self, json_generator: Optional[Callable[[str, str], Awaitable[dict]]] = None):
        self.json_generator = json_generator

    async def write(self, intent: IntentPlan, research_plan: ResearchPlan, industry: IndustryContext, evidence: EvidenceGraph, report_plan: ReportPlan) -> DraftReport:
        if self.json_generator:
            payload = {
                "user_objective": intent.model_dump(),
                "research_plan": research_plan.model_dump(),
                "industry_context": industry.model_dump(),
                "verified_evidence": evidence.model_dump(),
                "report_structure": report_plan.model_dump(),
                "output_schema": DraftReport.model_json_schema(),
            }
            return DraftReport.model_validate(await self.json_generator(WRITER_SYSTEM_PROMPT, json.dumps(payload, default=str)))
        return self._grounded_fallback(intent, evidence, report_plan)

    def _grounded_fallback(self, intent: IntentPlan, evidence: EvidenceGraph, report_plan: ReportPlan) -> DraftReport:
        verified = [node for node in evidence.nodes if node.status == "verified"]
        findings = [CitedInsight(insight=node.fact, evidence_ids=[node.id]) for node in verified[:8]]
        gaps = [f"Insufficient evidence for {section.title}." for section in report_plan.sections if not section.evidence_ids]
        conflicts = [CitedInsight(insight=conflict, evidence_ids=[]) for conflict in evidence.conflicts]
        summary = (
            f"The available evidence supports {len(findings)} material observations for the "
            f"{intent.decision_type} decision. " + ("Important evidence gaps remain." if gaps else "Coverage is adequate for the planned sections.")
        )
        return DraftReport(
            executive_summary=summary,
            key_findings=findings,
            risks=conflicts,
            opportunities=[],
            recommendations=[CitedInsight(insight="Resolve the identified evidence gaps before making the final decision.", evidence_ids=[])] if gaps else [],
            confidence=round(
                (sum(node.confidence for node in verified) / len(verified) if verified else 0.0) *
                (sum(evidence.coverage.get(req, 0.0) for req in intent.required_data) / len(intent.required_data) if intent.required_data else 1.0),
                2
            ),
            evidence_gaps=gaps,
        )
