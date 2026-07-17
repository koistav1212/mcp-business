from __future__ import annotations
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


"""
services/models/research_execution_plan.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ResearchExecutionPlan — Output of Planner, Input to Scheduler

The Planner produces this. The Scheduler reads it.
No other component modifies this object.

Responsibility contract:
    Planner     → creates ResearchExecutionPlan
    Scheduler   → reads execution_groups, parallel_groups, dependency_graph
    ToolRouter  → reads required_providers to know which tools to run
    KnowledgeRouter → reads required_providers for cache routing
"""


from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Any
from enum import Enum


class ResearchType(str, Enum):
    COMPANY_DEEP_DIVE     = "company_deep_dive"
    COMPETITIVE_ANALYSIS  = "competitive_analysis"
    MARKET_RESEARCH       = "market_research"
    INVESTMENT_BRIEF      = "investment_brief"
    SALES_INTELLIGENCE    = "sales_intelligence"
    KPI_MAPPING           = "kpi_mapping"
    SECTOR_PULSE          = "sector_pulse"
    RISK_ASSESSMENT       = "risk_assessment"
    TECHNOLOGY_AUDIT      = "technology_audit"
    PEOPLE_INTELLIGENCE   = "people_intelligence"


class AnalysisDepth(str, Enum):
    SHALLOW  = "shallow"     # <30s, 3-4 providers, basic profile
    STANDARD = "standard"    # <90s, 6-7 providers, full profile
    DEEP     = "deep"        # <3m,  all providers, 3+ research loops


class Priority(str, Enum):
    CRITICAL = "critical"
    HIGH     = "high"
    MEDIUM   = "medium"
    LOW      = "low"


@dataclass
class ResearchTask:
    """
    A single atomic unit of work dispatched to ToolRouterAgent.
    Each task maps to exactly one provider call.
    """
    task_id: str                    # e.g. "news_nvidia_001"
    provider_name: str              # must match a key in TOOL_REGISTRY
    target_field: str               # which field of ResolvedCompany to pass as input
                                    # e.g. "canonical_name" | "ticker" | "cik" | "official_website"
    priority: Priority = Priority.MEDIUM
    timeout_seconds: float = 180.0
    max_retries: int = 2
    dependencies: List[str] = field(default_factory=list)   # task_ids that must complete first
    fallback_provider: Optional[str] = None                 # run this if primary times out

    # Agent routing: which specialist agent consumes this task's evidence
    consuming_agents: List[str] = field(default_factory=list)
    # e.g. ["finance_agent", "valuation_agent"] for sec_provider output

    # Metadata for Scheduler telemetry
    estimated_latency_ms: int = 5000
    estimated_tokens: int = 200     # tokens this evidence will contribute to agent context
    cost_signal: str = "free"       # "free" | "api_key" | "paid"


@dataclass
class ExecutionWave:
    """
    A group of ResearchTasks that can be executed in parallel.
    Tasks within a wave have no dependencies on each other.
    Waves are executed sequentially by the Scheduler.
    """
    wave_number: int
    name: str                       # human-readable label, e.g. "Wave 1: Entity Resolution"
    tasks: List[ResearchTask] = field(default_factory=list)
    is_mandatory: bool = True       # if False, skip wave if time budget exceeded
    stop_on_failure: bool = False   # if True, failure of any task aborts the pipeline


@dataclass
class DependencyEdge:
    """Represents a dependency between two tasks: `from_task` must complete before `to_task`."""
    from_task: str
    to_task: str
    dependency_type: str = "data"   # "data" | "identity" | "enrichment"
    reason: str = ""


@dataclass
class StopCondition:
    """Defines when the Scheduler should stop executing waves early."""
    condition_type: str             # "time_budget" | "evidence_coverage" | "error_threshold"
    threshold: float = 0.0          # seconds | coverage fraction | error count
    action: str = "skip_optional"   # "skip_optional" | "abort" | "continue"


@dataclass
class ResearchExecutionPlan:
    """
    The complete research execution plan produced by the Planner.

    Planner reasons in domains, not providers:
        "I need financial data" → provider_selection() → ["sec_provider", "market_provider"]
    The Scheduler reads this plan and executes waves via ToolRouterAgent.
    """

    # ── Goal & intent ─────────────────────────────────────────────────────
    plan_id: str
    goal: str                               # user's raw query
    intent: str                             # classified intent string
    research_type: ResearchType
    decision_type: str                      # "investment" | "sales" | "informational"
    workspace_type: str                     # "CEO_REPORT" | "COMPETITOR_ANALYSIS" | etc.

    # ── Entity requirements ───────────────────────────────────────────────
    primary_entity_query: str               # what to resolve first
    comparison_entity_queries: List[str] = field(default_factory=list)   # for competitive analysis
    entity_confidence_threshold: float = 0.55   # below this → request clarification

    # ── Execution plan ────────────────────────────────────────────────────
    execution_waves: List[ExecutionWave] = field(default_factory=list)
    dependency_graph: List[DependencyEdge] = field(default_factory=list)

    # ── Provider selection (for KnowledgeRouter routing) ──────────────────
    required_providers: List[str] = field(default_factory=list)
    optional_providers: List[str] = field(default_factory=list)
    # Domains the Planner decided on (human-readable)
    required_domains: List[str] = field(default_factory=list)
    # e.g. ["financial_history", "market_data", "news", "leadership"]

    # ── Agent assignment ──────────────────────────────────────────────────
    # Maps agent name → list of provider names it depends on
    agent_dependencies: Dict[str, List[str]] = field(default_factory=dict)
    # e.g. {"finance_agent": ["sec_provider", "market_provider", "earnings_provider"]}

    # ── Budget & constraints ──────────────────────────────────────────────
    analysis_depth: AnalysisDepth = AnalysisDepth.STANDARD
    max_execution_seconds: float = 90.0
    max_total_tokens: int = 12000
    estimated_cost: str = "free"
    stop_conditions: List[StopCondition] = field(default_factory=list)

    # ── Success definition ────────────────────────────────────────────────
    success_criteria: List[str] = field(default_factory=list)
    minimum_evidence_coverage: float = 0.60    # fraction of required_domains that must have data
    required_data: List[str] = field(default_factory=list)

    # ── Research loop config ──────────────────────────────────────────────
    max_research_iterations: int = 1
    # > 1 enables gap-filling: Synthesizer identifies gaps → Planner re-plans → re-execute

    # ── Metadata ─────────────────────────────────────────────────────────
    created_at: str = ""
    planner_reasoning: List[str] = field(default_factory=list)  # domain reasoning trace

    # ─────────────────────────────────────────────────────────────────────
    # Derived properties
    # ─────────────────────────────────────────────────────────────────────

    @property
    def all_tasks(self) -> List[ResearchTask]:
        return [task for wave in self.execution_waves for task in wave.tasks]

    @property
    def all_provider_names(self) -> Set[str]:
        return set(self.required_providers + self.optional_providers)

    @property
    def wave_count(self) -> int:
        return len(self.execution_waves)

    @property
    def total_task_count(self) -> int:
        return len(self.all_tasks)

    def get_wave(self, wave_number: int) -> Optional[ExecutionWave]:
        for wave in self.execution_waves:
            if wave.wave_number == wave_number:
                return wave
        return None

    def tasks_for_provider(self, provider_name: str) -> List[ResearchTask]:
        return [t for t in self.all_tasks if t.provider_name == provider_name]

    def tasks_for_agent(self, agent_name: str) -> List[ResearchTask]:
        return [t for t in self.all_tasks if agent_name in t.consuming_agents]

    def to_summary(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "goal": self.goal[:80],
            "research_type": self.research_type.value,
            "wave_count": self.wave_count,
            "total_tasks": self.total_task_count,
            "required_providers": self.required_providers,
            "optional_providers": self.optional_providers,
            "max_execution_seconds": self.max_execution_seconds,
            "analysis_depth": self.analysis_depth.value,
        }


from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from services.core.models import ExecutionPlan, ExecutionWave, ResearchTask, DependencyGraph

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
