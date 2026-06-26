from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Optional, Any
from enum import Enum

class Priority(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"

class ResearchTask(BaseModel):
    task_id: str
    title: str
    description: str = ""
    objective: str
    priority: Priority
    owner_agent: str
    required_sources: List[str] = Field(default_factory=list)
    required_evidence: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    expected_output: str
    success_criteria: List[str] = Field(default_factory=list)
    estimated_tokens: int = 1000
    max_completion_tokens: int = 1500
    estimated_cost: float = 0.0
    estimated_runtime: int = 30
    parallelizable: bool = True
    status: str = "pending"
    confidence_threshold: float = 0.8
    retry_limit: int = 3

    model_config = ConfigDict(extra='allow')

class WorkBreakdown(BaseModel):
    research_objective: str
    work_packages: List[ResearchTask] = Field(default_factory=list)
    total_estimated_tokens: int = 0
    estimated_runtime: int = 0
    estimated_cost: float = 0.0
    parallel_groups: List[List[str]] = Field(default_factory=list)
    critical_path: List[str] = Field(default_factory=list)

class DependencyGraph(BaseModel):
    nodes: Dict[str, ResearchTask] = Field(default_factory=dict)
    edges: Dict[str, List[str]] = Field(default_factory=dict) # task_id -> [dependent_task_ids]
    
class ExecutionWave(BaseModel):
    wave_id: int
    tasks: List[ResearchTask] = Field(default_factory=list)
    
class ExecutionPlan(BaseModel):
    execution_id: str = "execution_001"
    research_objective: str
    company: str
    entities: List[str] = Field(default_factory=list)
    execution_waves: List[ExecutionWave] = Field(default_factory=list)
    research_tasks: List[ResearchTask] = Field(default_factory=list)
    dependency_graph: DependencyGraph = Field(default_factory=DependencyGraph)
    parallel_groups: List[List[str]] = Field(default_factory=list)
    estimated_runtime: int = 0
    estimated_cost: float = 0.0
    estimated_tokens: int = 0
    required_sources: List[str] = Field(default_factory=list)
    expected_outputs: List[str] = Field(default_factory=list)
    quality_checks: List[str] = Field(default_factory=list)
    confidence_target: float = 0.8
    retry_strategy: str = "exponential_backoff"

    model_config = ConfigDict(extra='allow')
