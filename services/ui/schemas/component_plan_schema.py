from typing import List

from pydantic import BaseModel, Field


class PlannedComponent(BaseModel):
    component_type: str
    executive_question_id: str
    insight_ids: List[str] = Field(default_factory=list)
    priority: int
    span: int


class ComponentPlan(BaseModel):
    selected_components: List[PlannedComponent] = Field(default_factory=list)
