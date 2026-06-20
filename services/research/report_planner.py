from services.research.models import EvidenceGraph, IndustryContext, IntentPlan, ReportPlan, ReportSection


class ReportPlanner:
    def plan(self, intent: IntentPlan, industry: IndustryContext, evidence: EvidenceGraph) -> ReportPlan:
        titles = ["Decision Summary"]
        if intent.decision_type == "investment":
            titles += {
                "banking": ["Deposits and Funding", "Asset Quality and NPA", "Loan Growth", "Capital Adequacy", "Valuation and Risks"],
                "metals": ["Volume and Realizations", "Cost Position", "Commodity Exposure", "Balance Sheet", "Valuation and Risks"],
                "construction": ["Order Book", "Project Pipeline", "Execution and Working Capital", "Government Exposure", "Valuation and Risks"],
                "semiconductors": ["AI and Data Center Growth", "Platform Ecosystem", "Margins and Supply", "Competition", "Valuation and Risks"],
            }.get(industry.industry, ["Growth", "Profitability", "Competitive Position", "Valuation", "Risks"])
        elif intent.decision_type == "sales pursuit":
            titles += ["Company Priorities", "Leadership and Buying Group", "Hiring and Capability Signals", "Technology Fit", "Pursuit Recommendations"]
        else:
            titles += [theme.title() for theme in industry.strategic_themes] + ["Risks", "Recommendations"]

        sections = []
        for title in list(dict.fromkeys(titles)):
            words = {word.lower() for word in title.replace("and", " ").split() if len(word) > 3}
            matched = [node.id for node in evidence.nodes if words.intersection(node.category.lower().split()) or any(word in node.fact.lower() for word in words)]
            sections.append(ReportSection(title=title, objective=f"Assess {title.lower()} for the user's {intent.decision_type} decision.", evidence_ids=matched))
        return ReportPlan(title=f"{intent.report_type.title()}: {', '.join(intent.entities) or 'Target Entity'}", sections=sections, output_format=intent.output_format)
