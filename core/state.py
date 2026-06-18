from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class AgentStatus(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"

class Message(BaseModel):
    """
    Represents a conversation message or interaction trace.
    """
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Optional[Dict[str, Any]] = None

class AgentStep(BaseModel):
    """
    Represents a single step in the agent's plan.
    """
    step_id: int
    name: str
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_output: Optional[Any] = None
    status: str = "pending"  # pending, running, completed, failed
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class ExecutionPlan(BaseModel):
    """
    A sequence of steps produced by the planner.
    """
    steps: List[AgentStep] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class VerificationResult(BaseModel):
    """
    Represents the evaluation of agent outputs or step executions.
    """
    is_valid: bool
    feedback: Optional[str] = None
    verified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class AgentState(BaseModel):
    """
    The main runtime state for an agent session.
    Tracks state through the lifecycle defined in the architecture.
    """
    session_id: str
    query: str
    status: AgentStatus = AgentStatus.PENDING
    history: List[Message] = Field(default_factory=list)
    plan: Optional[ExecutionPlan] = None
    current_step_index: int = 0
    memory: Dict[str, Any] = Field(default_factory=dict)
    verification: Optional[VerificationResult] = None
    response: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def update_status(self, new_status: AgentStatus):
        self.status = new_status
        self.updated_at = datetime.now(timezone.utc)
