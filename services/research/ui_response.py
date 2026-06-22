"""
Declarative UI Generation Builder.

Builds the ui_generation presentation layer from a ResearchContext.
Components reference source data via dotpath strings (e.g., "competitors",
"profile.overview") — the frontend resolves these against the root response.

This module NEVER duplicates research data. It only emits rendering instructions.

Architecture:
    Research Data = Truth Layer (immutable, from orchestrator)
    ui_generation = Presentation Layer (this module)
    Frontend = Rendering Layer (ComponentRegistry + resolveSource)
"""
import logging
from typing import List, Dict

from services.research.models import ResearchContext
from services.research.ui_models import (
    UIGeneration,
    Theme,
    ThemePalette,
    Layout,
    GridSpec,
    HeroSpec,
    HeroProps,
    ComponentSpec,
    ChartSpec,
    WidgetSpec,
    InteractionSpec,
    ResponsiveSpec,
    ResponsiveBreakpoint,
    ActionSpec,
    UIStrategy,
    Position,
)

logger = logging.getLogger("uvicorn.error")


_WIDGET_REGISTRY = {
    "executive_summary": {"component": "ExecutiveSummaryCard", "source": "draft_report.executive_summary", "span": 8},
    "company_overview": {"component": "ExecutiveSummaryCard", "source": "profile.overview", "span": 8},
    "kpi_metrics": {"component": "KpiRow", "source": "financials", "span": 12, "props": {"include_profile": True}},
    "swot_matrix": {"component": "SwotGrid", "source": "swot", "span": 8},
    "competitor_table": {"component": "CompetitorMatrix", "source": "competitors", "span": 12},
    "financial_scorecard": {"component": "FinancialDashboard", "source": "financials", "span": 8},
    "risk_assessment": {"component": "RiskCards", "source": "risk_factors", "span": 4},
    "recommendations": {"component": "RecommendationsPanel", "source": "draft_report.recommendations", "span": 8},
    "detailed_analysis": {"component": "DetailedAnalysis", "source": "draft_report.key_findings", "span": 8},
    "leadership_team": {"component": "LeadershipTeam", "source": "leadership", "span": 4},
    "tech_stack": {"component": "TechStackBadges", "source": "technology_stack", "span": 4},
    "hiring_signals": {"component": "HiringSignals", "source": "hiring_signals", "span": 4},
    "news_feed": {"component": "NewsTimeline", "source": "news", "span": 12},
}


def _classify_workspace_type(context: ResearchContext) -> str:
    """Classify workspace type from intent + data signals."""
    if context.intent:
        goal = (context.intent.primary_goal or "").lower()
        report_type = (context.intent.report_type or "").lower()
        combined = f"{goal} {report_type}"

        best_type = None
        best_score = 0
        for wtype, keywords in _TYPE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in combined)
            if score > best_score:
                best_score = score
                best_type = wtype

        if best_type and best_score > 0:
            return best_type

    # Data-signal fallback
    if context.competitors and context.swot:
        return "COMPETITOR_ANALYSIS"
    if context.financials and context.analytics:
        return "CEO_REPORT"
    if context.competitors:
        return "INDUSTRY_RESEARCH"

    return "DEEP_RESEARCH"


# ────────────────────────────────────────────────────────────────────
# Component Builders
# ────────────────────────────────────────────────────────────────────

def _build_components_from_spec(ui_spec: dict, context: ResearchContext) -> tuple[List[ComponentSpec], List[str]]:
    """
    Build the components list based on LLM requested widgets.
    """
    components: List[ComponentSpec] = []
    reasoning: List[str] = []
    row = 1
    col = 1
    
    widget_list = ui_spec.get("widgets", [])
    
    # Always ensure a top-level summary exists if data allows
    if "executive_summary" not in widget_list and "company_overview" not in widget_list:
        if context.draft_report and context.draft_report.executive_summary:
            widget_list.insert(0, "executive_summary")
        elif context.profile and context.profile.overview:
            widget_list.insert(0, "company_overview")
            
    for widget_id in widget_list:
        registry_entry = _WIDGET_REGISTRY.get(widget_id)
        if not registry_entry:
            reasoning.append(f"skipped {widget_id}: not found in registry")
            continue
            
        source_path = registry_entry["source"]
        has_data = True
        if source_path.startswith("draft_report") and not getattr(context, "draft_report", None):
            has_data = False
        elif source_path == "financials" and not getattr(context, "financials", None):
            has_data = False
        elif source_path == "competitors" and not getattr(context, "competitors", None):
            has_data = False
        elif source_path == "swot" and not getattr(context, "swot", None):
            has_data = False
        elif source_path == "risk_factors" and not getattr(context, "risk_factors", None):
            has_data = False
        elif source_path == "leadership" and not getattr(context, "leadership", None):
            has_data = False
            
        if not has_data:
            reasoning.append(f"skipped {widget_id}: source data '{source_path}' is missing")
            continue
            
        span = registry_entry["span"]
        if col + span > 13:
            row += 1
            col = 1
            
        components.append(ComponentSpec(
            id=widget_id,
            component=registry_entry["component"],
            source=source_path,
            position=Position(row=row, col=col, span=span),
            props=registry_entry.get("props", {})
        ))
        reasoning.append(f"added {widget_id} dynamically based on LLM intent")
        
        col += span
        if col > 12:
            row += 1
            col = 1

    return components, reasoning


# ────────────────────────────────────────────────────────────────────
# Chart Builders
# ────────────────────────────────────────────────────────────────────

def _build_charts_from_spec(ui_spec: dict, context: ResearchContext) -> tuple[List[ChartSpec], List[str]]:
    """Build chart specs based on LLM requested charts."""
    charts: List[ChartSpec] = []
    reasoning: List[str] = []
    
    chart_list = ui_spec.get("charts", [])
    
    comp_map = {
        "line": "LineChart",
        "area": "AreaChart",
        "bar": "BarChart",
        "pie": "PieChart"
    }

    for idx, c in enumerate(chart_list):
        ctype = c.get("type", "line").lower()
        title = c.get("title", f"Chart {idx+1}")
        
        # Simple heuristic to determine data source from chart title
        source = "financials.revenue_history"
        if "market" in title.lower() or ctype == "pie":
            source = "competitors"
        elif "margin" in title.lower():
            source = "analytics.operating_margin"
            
        charts.append(ChartSpec(
            id=f"chart_{idx}",
            component=comp_map.get(ctype, "LineChart"),
            title=title,
            source=source,
            reason=f"LLM dynamically requested {ctype} chart for '{title}'"
        ))
        reasoning.append(f"added {ctype} chart '{title}' based on LLM intent")

    return charts, reasoning


# Removed static widget builders as LLM now selects core widgets explicitly.


# ────────────────────────────────────────────────────────────────────
# Interactions (stubbed for v1)
# ────────────────────────────────────────────────────────────────────

def _build_interactions(components: List[ComponentSpec]) -> List[InteractionSpec]:
    """Build interaction stubs for components."""
    interactions: List[InteractionSpec] = []

    comp_ids = {c.id for c in components}

    if "competitor_grid" in comp_ids:
        interactions.append(InteractionSpec(
            event="click",
            target="competitor_grid",
            action="expand",
        ))

    if "revenue_growth" in comp_ids or any(c.id.startswith("market") for c in components):
        interactions.append(InteractionSpec(
            event="hover",
            target="revenue_growth",
            action="show_details",
        ))

    if "risk_assessment" in comp_ids:
        interactions.append(InteractionSpec(
            event="click",
            target="risk_assessment",
            action="expand",
        ))

    return interactions


# ────────────────────────────────────────────────────────────────────
# Actions (downloadable artifacts)
# ────────────────────────────────────────────────────────────────────

def _build_actions(context: ResearchContext) -> List[ActionSpec]:
    """Build available download actions."""
    actions = [
        ActionSpec(id="download_pdf", label="Export PDF", format="pdf", icon="file-text"),
        ActionSpec(id="download_pptx", label="Export Slides", format="pptx", icon="presentation"),
    ]
    if context.financials and context.financials.revenue_history:
        actions.append(ActionSpec(
            id="download_xlsx", label="Export Data", format="xlsx", icon="table",
        ))
    return actions


# ────────────────────────────────────────────────────────────────────
# Hero Builder
# ────────────────────────────────────────────────────────────────────

def _build_hero(context: ResearchContext) -> HeroSpec:
    """Build the hero section spec."""
    props = HeroProps(
        show_logo=True,
        show_market_position=bool(context.competitive_positioning),
        show_headquarters=bool(context.profile and context.profile.headquarters),
        show_employee_count=bool(context.profile and context.profile.employee_count),
    )
    return HeroSpec(component="CompanyHero", source="profile", props=props)


# ────────────────────────────────────────────────────────────────────
# Main Builder
# ────────────────────────────────────────────────────────────────────

def build_ui_generation(context: ResearchContext) -> dict:
    """
    Build the ui_generation presentation layer from a ResearchContext.

    This is appended as a single field to the immutable research data:
        response["ui_generation"] = build_ui_generation(context)

    The frontend reads rendering instructions from ui_generation and
    resolves source data from the root response via dotpath lookups.
    """
    # Extract intent/UI specs
    workspace_type = getattr(context.intent, "workspace_type", "DEEP_RESEARCH") if context.intent else "DEEP_RESEARCH"
    ui_spec = getattr(context.intent, "ui_generation_spec", {}) if context.intent else {}

    # 2. Build components + reasoning
    components, comp_reasoning = _build_components_from_spec(ui_spec, context)

    # 3. Build charts + reasoning
    charts, chart_reasoning = _build_charts_from_spec(ui_spec, context)

    # 4. Build dynamic widgets (disabled as LLM dictates widgets now)
    widgets = []

    # 5. Build interactions (stubbed)
    interactions = _build_interactions(components)

    # 6. Build actions
    actions = _build_actions(context)

    # 7. Build hero
    hero = _build_hero(context)

    # 8. Combine all reasoning
    all_reasoning = comp_reasoning + chart_reasoning
    if context.profile:
        all_reasoning.insert(0, f"company profile available: {context.profile.name}")
    if context.evidence_graph and context.evidence_graph.nodes:
        all_reasoning.append(f"evidence graph has {len(context.evidence_graph.nodes)} nodes")

    # 9. Determine priority sections
    priority_sections = ["hero"]
    if components:
        # Top 5 components by position row (lowest row = highest priority)
        for c in sorted(components, key=lambda x: x.position.row)[:5]:
            priority_sections.append(c.id)

    # 10. Assemble
    ui_gen = UIGeneration(
        version="1.0",
        workspace_type=workspace_type,
        theme=Theme(
            name="executive_dark",
            palette=ThemePalette(),
            radius="16px",
            font="Inter",
            density="comfortable",
        ),
        layout=Layout(
            type=ui_spec.get("layout", "research_dashboard"),
            grid=GridSpec(columns=12, gap=24),
            header=True,
            sidebar=True,
            sticky_summary=bool(context.draft_report and context.draft_report.executive_summary),
        ),
        hero=hero,
        components=components,
        charts=charts,
        widgets=widgets,
        interactions=interactions,
        responsive=ResponsiveSpec(
            mobile=ResponsiveBreakpoint(columns=1),
            tablet=ResponsiveBreakpoint(columns=6),
            desktop=ResponsiveBreakpoint(columns=12),
        ),
        actions=actions,
        ui_strategy=UIStrategy(
            selected_layout="research_dashboard",
            reasoning=all_reasoning,
            priority_sections=priority_sections,
        ),
    )

    return ui_gen.model_dump(exclude_none=True)
