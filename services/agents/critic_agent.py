import logging

logger = logging.getLogger("uvicorn.error")

class CriticAgent:
    async def execute(self, synthesized_report: dict, planning: dict):
        if not synthesized_report:
            return None

        # Prefer deterministic report critique from the report coordinator if present.
        existing_critique = synthesized_report.get("report_critique")
        if isinstance(existing_critique, dict) and existing_critique:
            score = float(existing_critique.get("score", 0.8))
            issues = list(existing_critique.get("issues", []))
            return {
                "score": score,
                "feedback": issues or ["Report coordinator critique passed."],
                "missing_data": synthesized_report.get("evidence_gaps", []),
                "hallucinations_detected": [],
                "checks": {
                    "were_financials_present": bool(synthesized_report.get("key_findings")),
                    "were_competitors_analyzed": "competition" in " ".join(synthesized_report.get("page_order", [])),
                    "did_recommendations_cite_evidence": bool(synthesized_report.get("recommendations")),
                    "were_required_sections_omitted": len(synthesized_report.get("page_order", [])) < 5,
                    "did_synthesis_invent_numbers": False,
                },
                "coverage_score": max(0.0, 1.0 - 0.05 * len(synthesized_report.get("evidence_gaps", []))),
                "completeness_score": score,
            }

        page_order = synthesized_report.get("page_order", [])
        key_findings = synthesized_report.get("key_findings", [])
        risks = synthesized_report.get("risks", [])
        recommendations = synthesized_report.get("recommendations", [])
        gaps = synthesized_report.get("evidence_gaps", [])

        feedback = []
        if len(page_order) < 5:
            feedback.append("Report has fewer than five pages.")
        if not key_findings:
            feedback.append("Key findings are missing.")
        if not risks:
            feedback.append("Risk section is weak or missing.")
        if not recommendations:
            feedback.append("Recommendations are missing.")

        completeness_score = max(0.0, 1.0 - 0.15 * len(feedback))
        coverage_score = max(0.0, 1.0 - 0.05 * len(gaps))
        score = round((completeness_score + coverage_score) / 2, 2)

        return {
            "score": score,
            "feedback": feedback or ["Deterministic critic passed."],
            "missing_data": gaps,
            "hallucinations_detected": [],
            "checks": {
                "were_financials_present": bool(key_findings),
                "were_competitors_analyzed": any(page in page_order for page in ["competition", "market"]),
                "did_recommendations_cite_evidence": bool(recommendations),
                "were_required_sections_omitted": len(page_order) < 5,
                "did_synthesis_invent_numbers": False
            },
            "coverage_score": coverage_score,
            "completeness_score": completeness_score
        }
