"""
Pydantic models for the declarative ui_generation presentation layer.

This follows the Generative UI pattern: research data is the immutable
truth layer, ui_generation is the presentation layer that controls ALL
rendering decisions. The frontend acts purely as a renderer of this spec.

Research Data = Truth Layer
ui_generation = Presentation Layer
Frontend = Rendering Layer
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ThemePalette(BaseModel):
    primary: str = "#7C3AED"
    secondary: str = "#2563EB"
    success: str = "#10B981"
    warning: str = "#F59E0B"
    danger: str = "#EF4444"
    background: str = "#0F172A"
    surface: str = "#111827"
    text: str = "#F8FAFC"


class Theme(BaseModel):
    name: str = "executive_dark"
    palette: ThemePalette = Field(default_factory=ThemePalette)
    radius: str = "16px"
    font: str = "Inter"
    density: str = "comfortable"  # comfortable | compact | spacious


class GridSpec(BaseModel):
    columns: int = 12
    gap: int = 24


class Layout(BaseModel):
    type: str = "research_dashboard"
    grid: GridSpec = Field(default_factory=GridSpec)
    header: bool = True
    sidebar: bool = True
    sticky_summary: bool = True


class HeroProps(BaseModel):
    show_logo: bool = True
    show_market_position: bool = True
    show_headquarters: bool = True
    show_employee_count: bool = True


class HeroSpec(BaseModel):
    component: str = "CompanyHero"
    source: str = "profile"
    props: HeroProps = Field(default_factory=HeroProps)


class Position(BaseModel):
    row: int
    col: int
    span: int


class ComponentSpec(BaseModel):
    """A UI component positioned on the grid, referencing source data."""
    id: str
    component: str
    source: str  # dotpath into the research data, e.g. "competitors", "profile.overview"
    position: Position
    props: Dict[str, Any] = Field(default_factory=dict)


class ChartSpec(BaseModel):
    """A chart component with its data source and reasoning."""
    id: str
    component: str  # PieChart, BarChart, LineChart, AreaChart
    title: str
    source: str  # dotpath into the research data
    reason: str = ""  # explains why this chart type was selected


class WidgetSpec(BaseModel):
    """Dynamic context-specific widget (varies per company)."""
    component: str
    source: str = ""
    props: Dict[str, Any] = Field(default_factory=dict)


class InteractionSpec(BaseModel):
    """Interaction binding (stubbed for v1)."""
    event: str  # click, hover
    target: str  # component id
    action: str  # expand, show_details, navigate


class ResponsiveBreakpoint(BaseModel):
    columns: int


class ResponsiveSpec(BaseModel):
    mobile: ResponsiveBreakpoint = Field(default_factory=lambda: ResponsiveBreakpoint(columns=1))
    tablet: ResponsiveBreakpoint = Field(default_factory=lambda: ResponsiveBreakpoint(columns=6))
    desktop: ResponsiveBreakpoint = Field(default_factory=lambda: ResponsiveBreakpoint(columns=12))


class ActionSpec(BaseModel):
    """Downloadable artifact action."""
    id: str
    label: str
    format: str  # pdf, pptx, xlsx
    icon: str = "download"


class UIStrategy(BaseModel):
    """Reasoning block explaining why the LLM selected this UI layout."""
    selected_layout: str = "research_dashboard"
    reasoning: List[str] = Field(default_factory=list)
    priority_sections: List[str] = Field(default_factory=list)


class UIGeneration(BaseModel):
    """
    The complete ui_generation presentation layer.
    Appended as a single field to the immutable research data response.
    """
    version: str = "1.0"
    workspace_type: str = "COMPANY_INTELLIGENCE"

    theme: Theme = Field(default_factory=Theme)
    layout: Layout = Field(default_factory=Layout)
    hero: HeroSpec = Field(default_factory=HeroSpec)

    components: List[ComponentSpec] = Field(default_factory=list)
    charts: List[ChartSpec] = Field(default_factory=list)
    widgets: List[WidgetSpec] = Field(default_factory=list)

    interactions: List[InteractionSpec] = Field(default_factory=list)
    responsive: ResponsiveSpec = Field(default_factory=ResponsiveSpec)
    actions: List[ActionSpec] = Field(default_factory=list)

    ui_strategy: UIStrategy = Field(default_factory=UIStrategy)
