from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from services.planning.models import ExecutionPlan, ExecutionWave, ResearchTask, DependencyGraph

class EntityExtractionResult(BaseModel):
    company: str
    ticker: Optional[str] = None
    exchange: Optional[str] = None
    cik: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    subindustry: Optional[str] = None
    country: Optional[str] = None
    headquarters: Optional[str] = None

class PlanningResult(BaseModel):
    intent: str = "general"
    workspace_type: str = "DEEP_RESEARCH"
    companies: List[str] = []
    research_depth: str = "comprehensive"
    report_style: str = "executive"
    required_outputs: List[str] = []
    
    execution_plan: Optional[ExecutionPlan] = None
    research_tasks: List[ResearchTask] = []
    execution_waves: List[ExecutionWave] = []
    token_budget: int = 0
    estimated_runtime: int = 0
    estimated_cost: float = 0.0
    required_sources: List[str] = []
    dependency_graph: Optional[DependencyGraph] = None
    
    model_config = ConfigDict(extra='allow')
