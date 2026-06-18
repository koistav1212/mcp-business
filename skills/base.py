from abc import ABC, abstractmethod
from pydantic import BaseModel, ConfigDict
from core.state import AgentState
from core.executor import AgentExecutor

class BaseSkill(BaseModel, ABC):
    """
    Abstract base class for all skills in the AI Agent Framework.
    A skill orchestrates multiple tool execution steps to solve a goal.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    prompt_template: str

    @abstractmethod
    async def run(self, query: str, state: AgentState, executor: AgentExecutor) -> AgentState:
        """
        Orchestrates tool executions using the executor to update the AgentState.
        """
        pass
