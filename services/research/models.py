from datetime import datetime
from typing import List, Optional, Any, Dict, Literal
from pydantic import BaseModel, Field

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

class DraftReport(BaseModel):
    executive_summary: str = ""
    key_findings: List[CitedInsight] = Field(default_factory=list)
    risks: List[CitedInsight] = Field(default_factory=list)
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
    buybacks: Optional[str] = None
    dividends: Optional[str] = None
    capex_trend: Optional[str] = None

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

class ResearchContext(
    FinancialResearchContext,
    SalesResearchContext,
    CompetitiveResearchContext
):
    """
    Unified result object aggregating all normalized research intelligence.
    Inherits fields from specialized contexts to maintain backward compatibility.
    """
    pass

