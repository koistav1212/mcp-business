from abc import ABC, abstractmethod
from services.core.models import PlanningResult
from services.models.research_models import AgentResult
from services.agents.tool_router_agent import ToolRouterAgent

class BaseResearchAgent(ABC):
    @abstractmethod
    async def execute(self, planning: PlanningResult, tool_router: ToolRouterAgent, company_entity=None, previous_findings=None, knowledge_view=None) -> AgentResult:
        pass
