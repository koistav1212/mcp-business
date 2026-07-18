from datetime import datetime
from typing import List, Optional, Any, Dict, Literal
from pydantic import BaseModel, Field, model_validator

class Source(BaseModel):
    """
    Represents a citation source for verifiability and audits.
    """
    title: str
    url: str
    source_type: str
    published_at: Optional[datetime] = None

class Headquarters(BaseModel):
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None


class OfficialPages(BaseModel):
    homepage: Optional[str] = None
    about: Optional[str] = None
    who_we_are: Optional[str] = None
    consumer: Optional[str] = None
    business: Optional[str] = None
    careers: Optional[str] = None
    contact: Optional[str] = None
    support: Optional[str] = None
    faq: Optional[str] = None
    selfcare: Optional[str] = None
    press: Optional[str] = None
    newsroom: Optional[str] = None
    investor_relations: Optional[str] = None
    sustainability: Optional[str] = None
    privacy_policy: Optional[str] = None
    terms: Optional[str] = None
    developer: Optional[str] = None
    api_docs: Optional[str] = None
    documentation: Optional[str] = None
    blog: Optional[str] = None
    status_page: Optional[str] = None
    partners: Optional[str] = None
    channel_partners: Optional[str] = None
    downloads: Optional[str] = None


class SocialProfiles(BaseModel):
    linkedin: Optional[str] = None
    youtube: Optional[str] = None
    facebook: Optional[str] = None
    twitter: Optional[str] = None
    instagram: Optional[str] = None


class MobileApp(BaseModel):
    name: str
    android: Optional[str] = None
    ios: Optional[str] = None


class EntityCore(BaseModel):
    name: str
    legal_name: Optional[str] = None
    parent_company: Optional[str] = None
    ultimate_parent: Optional[str] = None
    ticker: Optional[str] = None
    exchange: Optional[str] = None
    cik: Optional[str] = None
    country: Optional[str] = None
    headquarters: Optional[Headquarters] = None
    industry: Optional[str] = None
    subindustry: Optional[str] = None
    founded: Optional[int] = None
    website: Optional[str] = None
    canonical_domain: Optional[str] = None
    brand_names: List[str] = Field(default_factory=list)
    aliases: List[str] = Field(default_factory=list)


class Product(BaseModel):
    name: str
    category: str


class Solutions(BaseModel):
    consumer: List[str] = Field(default_factory=list)
    enterprise: List[str] = Field(default_factory=list)
    industries: List[str] = Field(default_factory=list)


class DeveloperResources(BaseModel):
    developer_portal: Optional[str] = None
    api_reference: Optional[str] = None
    sdk_downloads: Optional[str] = None
    github: Optional[str] = None
    open_source: List[str] = Field(default_factory=list)


class Contact(BaseModel):
    support_url: Optional[str] = None
    sales_url: Optional[str] = None
    careers_url: Optional[str] = None


class EntityResolution(BaseModel):
    entity: EntityCore
    official_pages: Optional[OfficialPages] = None
    products: List[Product] = Field(default_factory=list)
    services: List[str] = Field(default_factory=list)
    solutions: Optional[Solutions] = None
    social_profiles: Optional[SocialProfiles] = None
    mobile_apps: List[MobileApp] = Field(default_factory=list)
    subsidiaries_or_brands: List[str] = Field(default_factory=list)
    developer_resources: Optional[DeveloperResources] = None
    contact: Optional[Contact] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def company_name(self) -> str:
        return self.entity.name

    @property
    def ticker(self) -> Optional[str]:
        return self.entity.ticker

    @property
    def cik(self) -> Optional[str]:
        return self.entity.cik

    @property
    def exchange(self) -> Optional[str]:
        return self.entity.exchange

    @property
    def website(self) -> Optional[str]:
        return self.entity.website

    @property
    def confidence(self) -> float:
        return self.metadata.get("confidence", 0.0)

class SourcedValue(BaseModel):
    value: Any
    source_ids: List[str] = Field(default_factory=list)
    confidence: float = 0.0

class CompanyProfile(BaseModel):
    name: str
    overview: str
    headquarters: Optional[SourcedValue] = None
    employee_count: Optional[SourcedValue] = None
    website: Optional[SourcedValue] = None
    founders: List[str] = Field(default_factory=list)

class FinancialData(BaseModel):
    revenue_history: Optional[SourcedValue] = None
    net_income_history: Optional[SourcedValue] = None
    operating_income_history: Optional[SourcedValue] = None
    assets_history: Optional[SourcedValue] = None
    liabilities_history: Optional[SourcedValue] = None
    cash_flow_history: Optional[SourcedValue] = None
    shares_outstanding_history: Optional[SourcedValue] = None
    market_cap: Optional[SourcedValue] = None
    pe_ratio: Optional[SourcedValue] = None
    current_price: Optional[SourcedValue] = None
    fifty_two_week_high: Optional[SourcedValue] = None
    fifty_two_week_low: Optional[SourcedValue] = None
    revenue_annual: str = "N/A"
    funding_total: str = "N/A"
    last_round: str = "N/A"

class AnalyticsData(BaseModel):
    revenue_growth: Dict[str, float] = Field(default_factory=dict)
    profit_growth: Dict[str, float] = Field(default_factory=dict)
    cagr: Dict[str, float] = Field(default_factory=dict)
    debt_equity: Optional[float] = None
    operating_margin: Dict[str, float] = Field(default_factory=dict)
    net_margin: Dict[str, float] = Field(default_factory=dict)
    fcf_margin: Dict[str, float] = Field(default_factory=dict)
    roa: Dict[str, float] = Field(default_factory=dict)
    roe: Dict[str, float] = Field(default_factory=dict)
    interest_coverage: Dict[str, float] = Field(default_factory=dict)

class IntentPlan(BaseModel):
    primary_goal: str
    user_persona: str = "business decision-maker"
    report_type: str = "business intelligence"
    industry_focus: str = "unknown"
    time_horizon: str = "current"
    workspace_type: str = "DEEP_RESEARCH"
    report_style: str = "executive"
    depth: str = "standard"
    decision_type: str = "informational"
    entities: List[str] = Field(default_factory=list)
    required_data: List[str] = Field(default_factory=list)
    required_calculations: List[str] = Field(default_factory=list)
    required_visualizations: List[str] = Field(default_factory=list)
    required_sources: List[str] = Field(default_factory=list)
    required_frameworks: List[str] = Field(default_factory=list)
    success_criteria: List[str] = Field(default_factory=list)
    ui_generation_spec: Dict[str, Any] = Field(default_factory=dict)
    output_format: str = "json"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    clarification_needed: bool = False

class ResearchPlan(BaseModel):
    research_depth: str = "standard"
    research_iterations: int = 5
    minimum_sources: int = 50
    providers: List[str] = Field(default_factory=list)
    research_questions: List[str] = Field(default_factory=list)
    calculations: List[str] = Field(default_factory=list)
    rationale: Dict[str, str] = Field(default_factory=dict)

class IndustryContext(BaseModel):
    industry: str = "general"
    sub_industry: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    key_metrics: List[str] = Field(default_factory=list)
    strategic_themes: List[str] = Field(default_factory=list)

class EvidenceNode(BaseModel):
    id: str
    fact: str
    source_ids: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    category: str = "general"
    entity: Optional[str] = None
    value: Optional[Any] = None
    related_facts: List[str] = Field(default_factory=list)
    status: Literal["verified", "conflicted", "unverified"] = "verified"

class EvidenceGraph(BaseModel):
    nodes: List[EvidenceNode] = Field(default_factory=list)
    conflicts: List[str] = Field(default_factory=list)
    coverage: Dict[str, float] = Field(default_factory=dict)

class ReportSection(BaseModel):
    title: str
    objective: str
    evidence_ids: List[str] = Field(default_factory=list)

class ReportPlan(BaseModel):
    title: str
    sections: List[ReportSection] = Field(default_factory=list)
    output_format: str = "json"

class CitedInsight(BaseModel):
    insight: str
    evidence_ids: List[str] = Field(default_factory=list)

class ExecutiveSummary(BaseModel):
    headline: str = Field(default="", max_length=140)
    verdict: str = Field(default="", max_length=280)
    bullets: List[str] = Field(default_factory=list, max_length=5)

class ReportSection(BaseModel):
    title: str = ""
    question: str = ""
    evidence: List[str] = Field(default_factory=list, max_length=5)
    insights: List[str] = Field(default_factory=list, max_length=4)
    implications: List[str] = Field(default_factory=list, max_length=3)
    recommendations: List[str] = Field(default_factory=list, max_length=4)

class SynthesisOutput(BaseModel):
    executive_summary: Optional[ExecutiveSummary] = None
    growth: Optional[ReportSection] = None
    financial_quality: Optional[ReportSection] = None
    competition: Optional[ReportSection] = None
    operations: Optional[ReportSection] = None
    risks: Optional[ReportSection] = None
    kpis: Optional[ReportSection] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_gaps: List[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def clean_empty_lists(cls, values: Any) -> Any:
        if isinstance(values, dict):
            # Clean up empty lists generated by LLM for object fields
            object_fields = ['executive_summary', 'growth', 'financial_quality', 'competition', 'operations', 'risks', 'kpis']
            for field in object_fields:
                if field in values and isinstance(values[field], list) and len(values[field]) == 0:
                    values[field] = None
        return values

class DraftReport(BaseModel):
    executive_summary: Optional[ExecutiveSummary] = None
    growth: Optional[ReportSection] = None
    financial_quality: Optional[ReportSection] = None
    competition: Optional[ReportSection] = None
    operations: Optional[ReportSection] = None
    risks: Optional[ReportSection] = None
    kpis: Optional[ReportSection] = None
    
    @model_validator(mode="before")
    @classmethod
    def clean_empty_lists(cls, values: Any) -> Any:
        if isinstance(values, dict):
            # Clean up empty lists generated by LLM for object fields
            object_fields = ['executive_summary', 'growth', 'financial_quality', 'competition', 'operations', 'risks', 'kpis']
            for field in object_fields:
                if field in values and isinstance(values[field], list) and len(values[field]) == 0:
                    values[field] = None
        return values
    
    # Keeping old fields for backward compatibility, but they will be deprecated
    key_findings: List[CitedInsight] = Field(default_factory=list)
    legacy_risks: List[CitedInsight] = Field(default_factory=list)
    opportunities: List[CitedInsight] = Field(default_factory=list)
    recommendations: List[CitedInsight] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_gaps: List[str] = Field(default_factory=list)

from pydantic import ConfigDict

class CriticResult(BaseModel):
    valid: bool = True
    issues: List[str] = Field(default_factory=list)
    recommended_fixes: List[str] = Field(default_factory=list)
    score: float = 0.0
    feedback: List[str] = Field(default_factory=list)
    missing_data: List[str] = Field(default_factory=list)
    hallucinations_detected: List[str] = Field(default_factory=list)
    checks: Dict[str, bool] = Field(default_factory=dict)
    coverage_score: float = 0.0
    completeness_score: float = 0.0
    
    model_config = ConfigDict(extra='allow')

class SocialSentiment(BaseModel):
    bullish: float = 0.0
    bearish: float = 0.0
    neutral: float = 0.0
    top_themes: List[str] = Field(default_factory=list)

class Leadership(BaseModel):
    name: str
    role: str
    linkedin_url: Optional[str] = None

class Competitor(BaseModel):
    name: str
    website: str
    segment: str

class NewsItem(BaseModel):
    title: str
    url: str
    date: Optional[str] = None
    snippet: str
    type: str  # general, funding, acquisition, partnership

class HiringSignal(BaseModel):
    role_title: str
    department: str
    location: str

class RawResearchBundle(BaseModel):
    """
    Intermediate bundle wrapping the raw inputs of all providers.
    Passed directly to the synthesizer for resolution and scoring.
    """
    company_raw: Any
    web_raw: Any
    news_raw: Any
    financial_raw: Any
    people_raw: Any

class CompetitiveAxis(BaseModel):
    axis_name: str
    our_value: str
    competitor_value: str

class CompetitivePositioning(BaseModel):
    market_share_estimate: Optional[str] = None
    axes: List[CompetitiveAxis] = Field(default_factory=list)

class SWOTAnalysis(BaseModel):
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    opportunities: List[str] = Field(default_factory=list)
    threats: List[str] = Field(default_factory=list)

class ValuationMultiples(BaseModel):
    pe_ratio: Optional[float] = None
    pe_sector_median: Optional[float] = None
    ev_ebitda: Optional[float] = None
    ev_ebitda_sector_median: Optional[float] = None
    price_to_sales: Optional[float] = None
    price_to_sales_sector_median: Optional[float] = None

class RiskFactor(BaseModel):
    factor: str
    description: str
    source_ids: List[str] = Field(default_factory=list)

class CapitalAllocation(BaseModel):
    buybacks: Optional[Any] = None
    dividends: Optional[Any] = None
    capex_trend: Optional[Any] = None

class ManagementCommentary(BaseModel):
    quote: str
    speaker: str
    role: str
    source: str

class BaseResearchContext(BaseModel):
    """
    Base research context containing shared fields.
    """
    entity: Optional[EntityResolution] = None
    profile: Optional[CompanyProfile] = None
    company_profile: Optional[CompanyProfile] = None
    sources: List[Source] = Field(default_factory=list)
    confidence_score: float = 0.0
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    raw_data: Dict[str, Any] = Field(default_factory=dict)
    
    # Keep pdf_url and ppt_url for API contract compatibility
    pdf_url: Optional[str] = None
    ppt_url: Optional[str] = None

    # Shared research planning artifacts
    intent: Optional[IntentPlan] = None
    research_plan: Optional[ResearchPlan] = None
    industry_context: Optional[IndustryContext] = None
    evidence_graph: Optional[EvidenceGraph] = None
    report_plan: Optional[ReportPlan] = None
    draft_report: Optional[DraftReport] = None
    critique: Optional[CriticResult] = None
    conflicts: List[str] = Field(default_factory=list)
    social_sentiment: Optional[SourcedValue] = None

class FinancialResearchContext(BaseResearchContext):
    """
    Research context tailored for financial and investment analysis.
    """
    financials: Optional[FinancialData] = None
    analytics: Optional[AnalyticsData] = None
    valuation_multiples: Optional[ValuationMultiples] = None
    capital_allocation: Optional[CapitalAllocation] = None
    risk_factors: List[SourcedValue] = Field(default_factory=list)

class HiringResearchContext(BaseResearchContext):
    """
    Research context tailored for hiring and leadership analysis.
    """
    leadership: List[SourcedValue] = Field(default_factory=list)
    hiring_signals: List[HiringSignal] = Field(default_factory=list)

class SalesResearchContext(HiringResearchContext):
    """
    Research context tailored for sales development and customer outreach.
    """
    news: List[SourcedValue] = Field(default_factory=list)
    technology_stack: List[SourcedValue] = Field(default_factory=list)

class CompetitiveResearchContext(BaseResearchContext):
    """
    Research context tailored for competitive positioning and market strategy.
    """
    competitors: List[SourcedValue] = Field(default_factory=list)
    competitive_positioning: Optional[CompetitivePositioning] = None
    swot: Optional[SWOTAnalysis] = None
    management_commentary: List[ManagementCommentary] = Field(default_factory=list)

# --- NEW TWO-PASS PIPELINE MODELS ---

class BusinessEvent(BaseModel):
    id: str
    source_id: str
    provider: str
    timestamp: str
    event_type: str
    entity: str
    headline: str
    summary: str
    metrics: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0

class ExecutiveInsights(BaseModel):
    headline: str = ""
    key_findings: List[str] = Field(default_factory=list)
    supporting_numbers: List[str] = Field(default_factory=list)
    opportunities: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    watch_items: List[str] = Field(default_factory=list)
    confidence: float = 0.0

class CompetitorDetails(BaseModel):
    company: str = ""
    relationship: str = ""
    market_cap: Dict[str, Any] = Field(default_factory=dict)
    revenue: Dict[str, Any] = Field(default_factory=dict)
    employees: Dict[str, Any] = Field(default_factory=dict)
    growth_rate: Dict[str, Any] = Field(default_factory=dict)
    operating_margin: Dict[str, Any] = Field(default_factory=dict)
    business_model: List[str] = Field(default_factory=list)
    core_products: List[str] = Field(default_factory=list)
    technology_strength: List[str] = Field(default_factory=list)
    pricing_strategy: str = ""
    geographic_presence: List[str] = Field(default_factory=list)
    recent_strategic_moves: List[str] = Field(default_factory=list)
    advantages: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    threat_score: int = 0
    overlap_percentage: int = 0
    confidence: float = 0.0

class CompetitorIntelligence(BaseModel):
    summary: Dict[str, Any] = Field(default_factory=dict)
    competitors: List[CompetitorDetails] = Field(default_factory=list)
    comparison_matrix: Dict[str, Any] = Field(default_factory=dict)
    competitive_gaps: List[str] = Field(default_factory=list)
    opportunities: List[str] = Field(default_factory=list)
    executive_takeaway: str = ""
    executive_insights: Optional[ExecutiveInsights] = None

class ProductIntelligence(BaseModel):
    portfolio: List[str] = Field(default_factory=list)
    top_revenue_products: List[str] = Field(default_factory=list)
    new_launches: List[str] = Field(default_factory=list)
    products_discontinued: List[str] = Field(default_factory=list)
    pricing_changes: List[str] = Field(default_factory=list)
    market_share_by_product: List[Dict[str, Any]] = Field(default_factory=list)
    technology_stack: List[str] = Field(default_factory=list)
    product_maturity: Dict[str, Any] = Field(default_factory=dict)
    innovation_score: int = 0
    competitive_overlap: List[str] = Field(default_factory=list)
    growth_products: List[str] = Field(default_factory=list)
    declining_products: List[str] = Field(default_factory=list)
    llm_summary: str = ""
    executive_insights: Optional[ExecutiveInsights] = None

class OperationsIntelligence(BaseModel):
    manufacturing: Dict[str, Any] = Field(default_factory=dict)
    distribution: Dict[str, Any] = Field(default_factory=dict)
    warehouses: Dict[str, Any] = Field(default_factory=dict)
    logistics: Dict[str, Any] = Field(default_factory=dict)
    capacity_expansion: List[str] = Field(default_factory=list)
    automation: List[str] = Field(default_factory=list)
    robotics: List[str] = Field(default_factory=list)
    supply_chain: List[str] = Field(default_factory=list)
    inventory_turnover: Dict[str, Any] = Field(default_factory=dict)
    delivery_speed: Dict[str, Any] = Field(default_factory=dict)
    operational_efficiency: Dict[str, Any] = Field(default_factory=dict)
    cost_optimization: List[str] = Field(default_factory=list)
    operational_risks: List[str] = Field(default_factory=list)
    llm_summary: str = ""
    executive_insights: Optional[ExecutiveInsights] = None

class TechnologyIntelligence(BaseModel):
    cloud_platforms: List[str] = Field(default_factory=list)
    ai_capabilities: List[str] = Field(default_factory=list)
    developer_activity: Dict[str, Any] = Field(default_factory=dict)
    patents: Dict[str, Any] = Field(default_factory=dict)
    engineering_hiring: List[str] = Field(default_factory=list)
    opensource_activity: List[str] = Field(default_factory=list)
    tech_stack: List[str] = Field(default_factory=list)
    security_posture: List[str] = Field(default_factory=list)
    architecture_maturity: str = ""
    technology_trend: str = ""
    innovation_score: int = 0
    llm_summary: str = ""
    executive_insights: Optional[ExecutiveInsights] = None

class NewsArticle(BaseModel):
    headline: str = ""
    publisher: str = ""
    date: str = ""
    category: str = ""
    entities: List[str] = Field(default_factory=list)
    sentiment: str = "Neutral"
    importance: int = 0
    financial_impact: str = "Low"
    operational_impact: str = "Low"
    technology_impact: str = "Low"
    customer_impact: str = "Low"
    supply_chain_impact: str = "Low"
    strategic_theme: str = ""
    affected_products: List[str] = Field(default_factory=list)
    affected_regions: List[str] = Field(default_factory=list)
    risk_level: str = "Low"
    confidence: float = 0.0
    llm_analysis: Dict[str, Any] = Field(default_factory=dict)

class NewsSummary(BaseModel):
    positive_news: int = 0
    negative_news: int = 0
    neutral_news: int = 0
    highest_impact_events: List[str] = Field(default_factory=list)
    major_business_drivers: List[str] = Field(default_factory=list)
    major_risks: List[str] = Field(default_factory=list)
    emerging_themes: List[str] = Field(default_factory=list)
    llm_summary: str = ""

class NewsIntelligence(BaseModel):
    articles: List[NewsArticle] = Field(default_factory=list)
    news_summary: Optional[NewsSummary] = None
    executive_insights: Optional[ExecutiveInsights] = None

class OperatingSignals(BaseModel):
    factory_expansion: Dict[str, Any] = Field(default_factory=dict)
    store_openings: Dict[str, Any] = Field(default_factory=dict)
    warehouse_growth: Dict[str, Any] = Field(default_factory=dict)
    employee_hiring: Dict[str, Any] = Field(default_factory=dict)
    layoffs: Dict[str, Any] = Field(default_factory=dict)
    executive_changes: Dict[str, Any] = Field(default_factory=dict)
    partnerships: List[str] = Field(default_factory=list)
    new_regions: List[str] = Field(default_factory=list)
    pricing_changes: List[str] = Field(default_factory=list)
    product_launches: List[str] = Field(default_factory=list)
    supply_chain_changes: List[str] = Field(default_factory=list)
    capital_projects: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    llm_summary: str = ""
    executive_insights: Optional[ExecutiveInsights] = None

class SocialIntelligence(BaseModel):
    overall_sentiment: str = ""
    pain_points: List[str] = Field(default_factory=list)
    feature_requests: List[str] = Field(default_factory=list)
    competitor_mentions: List[str] = Field(default_factory=list)
    customer_opinions: List[str] = Field(default_factory=list)
    developer_feedback: List[str] = Field(default_factory=list)
    pricing_feedback: List[str] = Field(default_factory=list)
    comparison_matrix: List[str] = Field(default_factory=list)
    executive_mentions: List[str] = Field(default_factory=list)
    market_trends: List[str] = Field(default_factory=list)
    llm_summary: str = ""


class UIHeader(BaseModel):
    show: bool = True
    sticky: bool = False

class UIBody(BaseModel):
    scrollable: bool = False

class UILayout(BaseModel):
    width: str = "full"
    height: str = "dynamic"
    row_span: int = 1
    col_span: int = 12
    alignment: str = "stretch"

class UIStyle(BaseModel):
    border_radius: int = 12
    padding: int = 20
    shadow: str = "md"
    background_opacity: float = 0.95

class UIMetadata(BaseModel):
    component: str
    variant: str = "primary"
    importance: str = "normal"
    theme: str = "default"
    density: str = "comfortable"
    header: Optional[UIHeader] = None
    body: Optional[UIBody] = None
    layout: Optional[UILayout] = None
    style: Optional[UIStyle] = None
    priority: int = 50
    confidence: float = 1.0
    collapsible: bool = False
    drill_down: bool = False
    loading_state: str = "skeleton"
    refreshable: bool = False
    chart_type: Optional[str] = None
    interaction: Optional[str] = None
    mobile_behavior: Optional[str] = None
    exportable: bool = False

class ResearchContext(
    FinancialResearchContext,
    SalesResearchContext,
    CompetitiveResearchContext
):
    """
    Unified result object aggregating all normalized research intelligence.
    Inherits fields from specialized contexts to maintain backward compatibility.
    """
    competitor_intelligence: Optional[CompetitorIntelligence] = None
    product_intelligence: Optional[ProductIntelligence] = None
    operations_intelligence: Optional[OperationsIntelligence] = None
    technology_intelligence: Optional[TechnologyIntelligence] = None
    news_intelligence: Optional[NewsIntelligence] = None
    operating_signals: Optional[OperatingSignals] = None
    social_intelligence: Optional[SocialIntelligence] = None
    ui_metadata: Optional[UIMetadata] = None


# ==============================================================================
# NEW ARCHITECTURE SCHEMAS
# ==============================================================================

class LightweightPlannerOutput(BaseModel):
    required_evidence: List[str] = Field(default_factory=list)
    selected_providers: List[str] = Field(default_factory=list)
    required_sections: List[str] = Field(default_factory=list)
    priority: str = "medium"  # high | medium | low
    reasoning: List[str] = Field(default_factory=list)


class FinancialAgentOutput(BaseModel):
    executive_summary: str = ""
    growth_metrics: Dict[str, Any] = Field(default_factory=dict)
    profitability_metrics: Dict[str, Any] = Field(default_factory=dict)
    financial_health: Dict[str, Any] = Field(default_factory=dict)
    valuation_metrics: Dict[str, Any] = Field(default_factory=dict)
    market_performance: Dict[str, Any] = Field(default_factory=dict)
    analyst_sentiment: Dict[str, Any] = Field(default_factory=dict)
    trend_analysis: str = ""
    risks: List[str] = Field(default_factory=list)
    opportunities: List[str] = Field(default_factory=list)
    confidence: float = 0.9


class TechnologyAgentOutput(BaseModel):
    ai_maturity: str = ""
    architecture: Dict[str, Any] = Field(default_factory=dict)
    stack: List[str] = Field(default_factory=list)
    patents: Dict[str, Any] = Field(default_factory=dict)
    developer_velocity: str = ""
    innovation: str = ""
    modernization: str = ""
    technical_risks: List[str] = Field(default_factory=list)


class CompetitorAgentOutput(BaseModel):
    competitive_matrix: Dict[str, Any] = Field(default_factory=dict)
    positioning: Dict[str, Any] = Field(default_factory=dict)
    swot: Dict[str, Any] = Field(default_factory=dict)
    white_space: List[str] = Field(default_factory=list)
    feature_comparison: Dict[str, Any] = Field(default_factory=dict)
    pricing_comparison: Dict[str, Any] = Field(default_factory=dict)
    threats: List[str] = Field(default_factory=list)
    moat: str = ""


class ProductAgentOutput(BaseModel):
    portfolio: List[Any] = Field(default_factory=list)
    bcg_matrix: Dict[str, Any] = Field(default_factory=dict)
    lifecycle: Dict[str, Any] = Field(default_factory=dict)
    innovation: str = ""
    pricing: Any = Field(default_factory=dict)
    revenue_products: List[str] = Field(default_factory=list)


class SupplyChainOutput(BaseModel):
    factory: Dict[str, Optional[Any]] = Field(default_factory=lambda: {"location": None, "capacity": None, "efficiency": None})
    distribution: Dict[str, Optional[Any]] = Field(default_factory=lambda: {"method": None, "speed": None, "cost": None})
    vendor_risk: Dict[str, Optional[Any]] = Field(default_factory=lambda: {"reliability": None, "financial_stability": None, "geopolitical_risk": None})

class EfficiencyOutput(BaseModel):
    operational_efficiency: Optional[str] = None
    energy_efficiency: Optional[str] = None
    water_efficiency: Optional[str] = None

class CapacityOutput(BaseModel):
    production_capacity: Optional[str] = None
    utilization_rate: Optional[str] = None
    bottleneck_process: Optional[str] = None

class OperationsAgentOutput(BaseModel):
    supply_chain: SupplyChainOutput = Field(default_factory=SupplyChainOutput)
    factory: Dict[str, Any] = Field(default_factory=dict)
    distribution: Dict[str, Any] = Field(default_factory=dict)
    efficiency: EfficiencyOutput = Field(default_factory=EfficiencyOutput)
    capacity: CapacityOutput = Field(default_factory=CapacityOutput)
    vendor_risk: Dict[str, Any] = Field(default_factory=dict)


class SocialAgentOutput(BaseModel):
    sentiment: str = ""
    pain_points: List[str] = Field(default_factory=list)
    feature_requests: List[str] = Field(default_factory=list)
    top_complaints: List[str] = Field(default_factory=list)
    positive_themes: List[str] = Field(default_factory=list)
    competitor_mentions: List[str] = Field(default_factory=list)
    trending_topics: List[str] = Field(default_factory=list)


class RiskAgentOutput(BaseModel):
    risk_register: List[Dict[str, Any]] = Field(default_factory=list)
    likelihood: Dict[str, Any] = Field(default_factory=dict)
    impact: Dict[str, Any] = Field(default_factory=dict)
    mitigation: Dict[str, Any] = Field(default_factory=dict)
    early_warning_signals: List[str] = Field(default_factory=list)
    scenario_analysis: Dict[str, Any] = Field(default_factory=dict)


class CriticAgentOutput(BaseModel):
    quality_score: int = 100
    missing_sections: List[str] = Field(default_factory=list)
    regenerate: List[str] = Field(default_factory=list)
    unsupported_claims: List[str] = Field(default_factory=list)


class ExecutiveSynthesizerOutput(BaseModel):
    executive_summary: str = ""
    investment_case: str = ""
    strategic_outlook: str = ""
    key_risks: str = ""
    opportunities: str = ""
    recommendations: str = ""
    evidence_refs: List[Dict[str, Any]] = Field(default_factory=list, description="Array of real source URLs and citations used")


class NewBusinessEvent(BaseModel):
    type: str
    importance: float = 0.5
    headline: str = ""
    date: str = ""
    entities: List[str] = Field(default_factory=list)
    metrics: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)
