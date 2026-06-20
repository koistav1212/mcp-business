from services.research.models import CriticResult, DraftReport, EvidenceGraph, IntentPlan, ReportPlan, ResearchPlan


class CriticAgent:
    """Rejects unsupported claims and detects missing coverage before delivery."""

    def review(self, original_request: str, intent: IntentPlan, research_plan: ResearchPlan, evidence: EvidenceGraph, report_plan: ReportPlan, draft: DraftReport) -> CriticResult:
        issues = []
        fixes = []
        valid_ids = {node.id for node in evidence.nodes}
        insights = draft.key_findings + draft.risks + draft.opportunities + draft.recommendations
        for insight in insights:
            unknown = set(insight.evidence_ids) - valid_ids
            if unknown:
                issues.append(f"Unsupported evidence IDs in claim: {sorted(unknown)}")
                fixes.append("Remove the claim or attach valid evidence IDs.")
            if insight.evidence_ids == [] and any(char.isdigit() for char in insight.insight):
                issues.append(f"Uncited quantitative claim: {insight.insight}")
                fixes.append("Cite a verified evidence node for every quantitative claim.")
        missing = [section.title for section in report_plan.sections if not section.evidence_ids]
        if missing and not draft.evidence_gaps:
            issues.append(f"Missing requested topics were not disclosed: {', '.join(missing)}")
            fixes.append("State each uncovered section as an evidence gap.")
        if intent.entities and not any(entity.lower() in (original_request + " " + intent.primary_goal).lower() for entity in intent.entities):
            issues.append("The resolved entity does not match the request.")
            fixes.append("Re-run entity resolution before writing.")
        # Check coverage of required data
        for req_data, coverage_val in evidence.coverage.items():
            if coverage_val == 0.0 and req_data in intent.required_data:
                issues.append(f"{req_data.capitalize()} requested but zero evidence nodes present.")
                fixes.append(f"Acquire primary sources or document {req_data} as an evidence gap.")

        return CriticResult(valid=not issues, issues=list(dict.fromkeys(issues)), recommended_fixes=list(dict.fromkeys(fixes)))
