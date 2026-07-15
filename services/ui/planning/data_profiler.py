from services.schemas.insight import ResearchContext
from ..schemas.data_profile_schema import DataProfile

class DataProfiler:
    def profile(self, context: ResearchContext) -> DataProfile:
        """
        Profiles the available research data to determine what analytical signals
        are supported, outputting boolean flags for available datasets.
        """
        has_financials = bool(context.financials and any(context.financials.model_dump().values()))
        has_news = bool(context.news and len(context.news) > 0)
        has_risk = bool(context.risk_factors and len(context.risk_factors) > 0)
        has_social = bool(context.social_sentiment and context.social_sentiment.value is not None)
        has_tech = bool(context.technology_stack and len(context.technology_stack) > 0)
        has_competition = bool(context.competitors and len(context.competitors) > 0)
        has_leadership = bool(context.leadership and len(context.leadership) > 0)
        has_patents = False # Add patent detection if schema supports
        has_macro = bool(context.industry_context and (context.industry_context.industry != "general" or len(context.industry_context.key_metrics) > 0))
        has_sec = False # Add SEC explicitly if schema supports
        has_knowledge_graph = bool(context.evidence_graph and context.evidence_graph.nodes)

        return DataProfile(
            financial=has_financials,
            news=has_news,
            risk=has_risk,
            social=has_social,
            technology=has_tech,
            competition=has_competition,
            leadership=has_leadership,
            patents=has_patents,
            macro=has_macro,
            sec=has_sec,
            knowledge_graph=has_knowledge_graph
        )
