import logging
from services.knowledge.views.financial_view import FinancialView
from services.knowledge.views.news_view import NewsView
from services.knowledge.views.technology_view import TechnologyView
from services.knowledge.views.competitor_view import CompetitorView
from services.knowledge.views.industry_view import IndustryView
from services.knowledge.views.risk_view import RiskView
from services.knowledge.views.leadership_view import LeadershipView
from services.knowledge.views.valuation_view import ValuationView
from services.knowledge.views.base_view import KnowledgeView

logger = logging.getLogger("uvicorn.error")

class ViewFactory:
    _view_mapping = {
        "financial_agent": FinancialView,
        "news_agent": NewsView,
        "technology_agent": TechnologyView,
        "competitor_agent": CompetitorView,
        "industry_agent": IndustryView,
        "risk_agent": RiskView,
        "valuation_agent": ValuationView,
        "growth_agent": FinancialView,
        "ai_agent": TechnologyView,
        "mna_agent": ValuationView
    }

    @classmethod
    def get(cls, agent_name: str) -> KnowledgeView:
        view_class = cls._view_mapping.get(agent_name)
        if not view_class:
            logger.warning(f"No specific view found for {agent_name}. Defaulting to NewsView.")
            return NewsView()
        return view_class()
