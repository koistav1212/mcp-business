import hashlib
from typing import Any, Iterable, Optional

from services.research.models import EvidenceGraph, EvidenceNode, ResearchContext


class EvidenceGraphBuilder:
    """Converts normalized provider output into claim-level, cited evidence."""

    def build(self, context: ResearchContext, required_data: Iterable[str] = ()) -> EvidenceGraph:
        nodes = []
        source_ids = {source.url: f"S{index:03d}" for index, source in enumerate(context.sources, 1)}

        def source_for(*types: str):
            ids = [source_ids[s.url] for s in context.sources if s.source_type in types]
            return ids[:2]

        def add(fact: str, category: str, value: Any = None, confidence: Optional[float] = None, sources=None):
            if value is None and not fact:
                return
            node_id = "E" + hashlib.sha1(f"{category}:{fact}".encode()).hexdigest()[:8].upper()
            nodes.append(EvidenceNode(
                id=node_id,
                fact=fact,
                category=category,
                entity=context.profile.name,
                value=value,
                source_ids=sources or [],
                confidence=confidence if confidence is not None else context.confidence_score,
                status="verified" if sources else "unverified",
            ))

        company_sources = source_for("official_website", "commercial_database", "directory")
        if context.profile.headquarters:
            hq_val = context.profile.headquarters.value
            hq_sources = [source_ids[url] for url in context.profile.headquarters.source_ids if url in source_ids]
            add(f"{context.profile.name} is headquartered in {hq_val}.", "company profile", hq_val, sources=hq_sources or company_sources)
        if context.profile.employee_count:
            emp_val = context.profile.employee_count.value
            emp_sources = [source_ids[url] for url in context.profile.employee_count.source_ids if url in source_ids]
            add(f"{context.profile.name} reports approximately {emp_val:,} employees.", "company profile", emp_val, sources=emp_sources or company_sources)
        if context.profile.overview:
            add(context.profile.overview, "company profile", sources=company_sources)

        filing_sources = source_for("official_filing")
        for metric, history in (
            ("revenue", context.financials.revenue_history),
            ("net income", context.financials.net_income_history),
            ("operating income", context.financials.operating_income_history),
        ):
            for period, value in sorted(history.items())[-3:]:
                if value is not None:
                    add(f"{metric.title()} was {value:,.0f} in fiscal {period}.", "financial history", {"period": period, "value": value}, 0.95, filing_sources)
        market_sources = source_for("market_data", "commercial_database")
        for label, value in (("market capitalization", context.financials.market_cap), ("P/E ratio", context.financials.pe_ratio), ("current share price", context.financials.current_price)):
            if value is not None:
                add(f"The {label} is {value:,.2f}.", "market valuation", value, 0.85, market_sources)

        news_sources = source_for("news_outlet")
        for item in context.news:
            ids = [source_ids.get(item.url)] if item.url in source_ids else news_sources
            add(f"{item.title}: {item.snippet}", "recent developments", {"date": item.date, "type": item.type}, 0.75, [x for x in ids if x])
        people_sources = source_for("professional_network", "careers_portal")
        for leader in context.leadership:
            add(f"{leader.name} serves as {leader.role}.", "leadership", leader.role, 0.8, people_sources)
        for signal in context.hiring_signals:
            add(f"A {signal.role_title} role is listed in {signal.department} at {signal.location}.", "hiring signals", signal.model_dump(), 0.7, people_sources)
        tech_sources = source_for("web_scraper")
        if context.technology_stack:
            add(f"Observed technologies include {', '.join(context.technology_stack)}.", "technology stack", context.technology_stack, 0.65, tech_sources)
        for competitor in context.competitors:
            add(
                f"{competitor.name} is identified as a competitor in {competitor.segment}.",
                "competitive positioning",
                competitor.model_dump(),
                0.7,
                company_sources,
            )

        # Map business priorities from SWOT or other strategic attributes
        if context.swot:
            add(
                "SWOT evidence is available for the resolved company.",
                "swot",
                context.swot.model_dump(),
                0.75,
                company_sources,
            )
            for s in context.swot.strengths:
                add(f"Strategic priority (Strength): {s}", "business priorities", s, 0.85, company_sources)
            for o in context.swot.opportunities:
                add(f"Strategic priority (Opportunity): {o}", "business priorities", o, 0.85, company_sources)


        categories = {node.category for node in nodes}
        coverage = {item: (1.0 if item in categories else 0.0) for item in required_data}
        return EvidenceGraph(nodes=nodes, conflicts=context.conflicts, coverage=coverage)
