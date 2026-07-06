from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ReportPageSpec:
    page_id: str
    title: str
    prompt_name: str
    agent_name: str
    required_fields: List[str] = field(default_factory=list)


@dataclass
class GeneratedPage:
    page_id: str
    title: str
    markdown: str
    citations: List[str] = field(default_factory=list)
    context_keys: List[str] = field(default_factory=list)


@dataclass
class CoverageResult:
    page_id: str
    present_fields: List[str] = field(default_factory=list)
    missing_fields: List[str] = field(default_factory=list)
    coverage_score: float = 0.0


@dataclass
class ReportPlan:
    report_type: str
    pages: List[ReportPageSpec]


@dataclass
class ReportOutput:
    executive_summary: str
    key_findings: List[Dict[str, Any]] = field(default_factory=list)
    risks: List[Dict[str, Any]] = field(default_factory=list)
    opportunities: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    evidence_gaps: List[str] = field(default_factory=list)
    page_order: List[str] = field(default_factory=list)
    report_critique: Dict[str, Any] = field(default_factory=dict)
