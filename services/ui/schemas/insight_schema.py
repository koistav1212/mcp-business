from typing import List

from pydantic import BaseModel, Field


class ExecutiveQuestion(BaseModel):
    id: str
    question: str
    priority: int
    answerability: float
    evidence_paths: List[str] = Field(default_factory=list)


class InsightCandidate(BaseModel):
    id: str
    insight_type: str
    statement: str
    executive_question_id: str
    evidence_paths: List[str] = Field(default_factory=list)
    confidence: float


class InsightPlan(BaseModel):
    page_objective: str
    executive_questions: List[ExecutiveQuestion] = Field(default_factory=list)
    insight_candidates: List[InsightCandidate] = Field(default_factory=list)
