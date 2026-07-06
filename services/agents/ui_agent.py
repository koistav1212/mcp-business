"""
UIAgent — Generative UI Architect

Reads the fully synthesized ResearchContext from the orchestrator and outputs
a deterministic, client-renderable UI specification. The prompt is grounded in
the exact field names of ResearchContext / IntentPlan so the LLM never
hallucinates a field that doesn't exist in the response payload.

Architecture contract:
    Research Data  = Truth layer   (ResearchContext, from orchestrator)
    ui_generation  = Presentation layer (this agent, emits instructions only)
    Frontend       = Rendering layer (React, resolves dotpaths against root response)

The frontend NEVER receives raw data from this agent. It only receives
rendering instructions. Data lives in the root JSON keys.
"""

import json
import logging
from typing import Any, Optional

logger = logging.getLogger("uvicorn.error")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1 — QUERY CLASSIFIER
# Maps the raw user query to a WorkspaceType that drives layout selection.
# This runs BEFORE the main UI prompt so the LLM has an explicit workspace
# signal rather than inferring it from noisy research text.
# ─────────────────────────────────────────────────────────────────────────────

QUERY_CLASSIFIER_PROMPT = """You are a Research Workspace Classifier.

Given a user query, classify it into exactly ONE workspace type.

WORKSPACE TYPES:
- CEO_REPORT          → Full company strategic analysis (profile + financials + competitive + risks)
- COMPETITOR_ANALYSIS → Head-to-head comparison between two or more named companies
- MARKET_RESEARCH     → Industry/sector trends, market sizing, emerging players (no single company focus)
- INVESTMENT_BRIEF    → Investor-grade financial deep-dive (P/E, multiples, CAGR, risk factors)
- SALES_INTELLIGENCE  → Sales team context on a target account (tech stack, hiring, leadership, triggers)
- KPI_DASHBOARD       → Business metrics and KPI tracking (dashboard design, metric selection)
- SECTOR_PULSE        → Fintech, AI, climate, crypto — trend mapping with company positioning

RULES:
- Return ONLY the workspace type string from the list above.
- If the query asks "what metrics should I track" or "what dashboard" → KPI_DASHBOARD
- If the query mentions a country + sector (Indian fintech, US AI) → SECTOR_PULSE
- If the query mentions two companies with "vs" or "compare" → COMPETITOR_ANALYSIS
- If the query asks about investing, multiples, returns → INVESTMENT_BRIEF
- If the query is about a single company with sales/outreach intent → SALES_INTELLIGENCE
- If the query is about a single company with no specific angle → CEO_REPORT
- If no company is mentioned and it is trend/market → MARKET_RESEARCH

Return only the string. No JSON. No explanation."""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2 — WORKSPACE LAYOUT TEMPLATES
# Each workspace type has a preferred layout that the UI architect uses
# as a starting constraint before adapting to available data.
# ─────────────────────────────────────────────────────────────────────────────

WORKSPACE_TEMPLATES = {
    "CEO_REPORT": {
        "theme": "executive_dark",
        "layout_style": "command_center",
        "primary_color": "#7C3AED",
        "accent_color": "#10B981",
        "page_count_hint": "5-6",
        "priority_sections": ["hero_identity", "executive_summary", "financial_performance", "competitive_landscape", "risk_register", "strategic_recommendations"],
    },
    "COMPETITOR_ANALYSIS": {
        "theme": "analytical_light",
        "layout_style": "comparison_matrix",
        "primary_color": "#2563EB",
        "accent_color": "#F59E0B",
        "page_count_hint": "2-3",
        "priority_sections": ["comparison_hero", "head_to_head_metrics", "positioning_matrix", "swot_comparison", "market_share_breakdown", "strategic_verdict"],
    },
    "MARKET_RESEARCH": {
        "theme": "research_gradient",
        "layout_style": "narrative_scroll",
        "primary_color": "#0891B2",
        "accent_color": "#8B5CF6",
        "page_count_hint": "3-5",
        "priority_sections": ["market_pulse_hero", "market_sizing", "trend_radar", "player_landscape", "growth_vectors", "investment_thesis"],
    },
    "INVESTMENT_BRIEF": {
        "theme": "bloomberg_dark",
        "layout_style": "data_dense",
        "primary_color": "#1E40AF",
        "accent_color": "#F59E0B",
        "page_count_hint": "5-6",
        "priority_sections": ["ticker_hero", "financial_scorecard", "valuation_multiples", "earnings_trend", "risk_register", "analyst_verdict"],
    },
    "SALES_INTELLIGENCE": {
        "theme": "crm_clean",
        "layout_style": "account_card",
        "primary_color": "#059669",
        "accent_color": "#7C3AED",
        "page_count_hint": "1-2",
        "priority_sections": ["account_hero", "buying_signals", "tech_stack_fit", "leadership_contacts", "recent_triggers", "outreach_brief"],
    },
    "KPI_DASHBOARD": {
        "theme": "analytics_pro",
        "layout_style": "metric_grid",
        "primary_color": "#DC2626",
        "accent_color": "#2563EB",
        "page_count_hint": "2-4",
        "priority_sections": ["kpi_hero", "north_star_metrics", "financial_kpis", "operational_kpis", "growth_kpis", "benchmark_comparisons"],
    },
    "SECTOR_PULSE": {
        "theme": "intelligence_dark",
        "layout_style": "radar_map",
        "primary_color": "#7C3AED",
        "accent_color": "#06B6D4",
        "page_count_hint": "3-5",
        "priority_sections": ["sector_hero", "trend_timeline", "company_positioning_map", "regulatory_landscape", "emerging_players", "investment_hotspots"],
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3 — THE MAIN UI ARCHITECT PROMPT
# This is the core prompt grounded in the actual ResearchContext schema.
# Every dotpath reference maps to a real field in models.py.
# ─────────────────────────────────────────────────────────────────────────────

UI_ARCHITECT_PROMPT = """You are the Senior UI Architect at a top-tier management consulting firm (McKinsey, BCG, Bain quality).

Your role: Transform verified business research into a multi-page executive dashboard specification.
This specification is consumed by a React renderer — it describes WHAT to show, WHERE, and HOW.
You never duplicate data. You only emit rendering instructions that reference source data by dotpath.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ABSOLUTE RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. NEVER invent data. If a field is null or empty in research_available_fields, mark
   the component "data_status": "unavailable" and set "show_when_empty": false.
2. NEVER put raw data in this response. Only dotpaths like "financials.revenue_history".
3. ALWAYS check research_available_fields before including any component.
   A component with no data must not appear unless explicitly flagged as a gap card.
4. The frontend resolves all dotpaths against the root research JSON.
   Use EXACT field names from the ResearchContext schema (listed below).
5. Design for DECISION-MAKING, not information display. Every section must answer a
   business question. Label each section with its business_question.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXACT RESEARCHCONTEXT FIELD NAMES (use ONLY these as dotpath sources)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Top-level scalars:
  entity.entity.name | entity.entity.ticker | entity.entity.exchange | entity.metadata.confidence
  confidence_score | generated_at

Company profile (all fields carry SourcedValue with .value + .confidence):
  profile.name | profile.overview | profile.website
  profile.headquarters.value | profile.employee_count.value | profile.founders

Financial data:
  financials.revenue_history         → Dict[year_str, float]  (e.g. {"2022": 1.2e9})
  financials.net_income_history      → Dict[year_str, float]
  financials.operating_income_history → Dict[year_str, float]
  financials.assets_history          → Dict[year_str, float]
  financials.liabilities_history     → Dict[year_str, float]
  financials.cash_flow_history       → Dict[year_str, float]
  financials.long_term_debt_history  → Dict[year_str, float]
  financials.market_cap | financials.pe_ratio | financials.current_price
  financials.fifty_two_week_high | financials.fifty_two_week_low

Analytics (computed by Python, never by LLM):
  analytics.revenue_growth           → Dict[year_str, float %]
  analytics.profit_growth            → Dict[year_str, float %]
  analytics.cagr                     → {"3_year": float, "5_year": float, "10_year": float}
  analytics.debt_equity              → float or null
  analytics.operating_margin         → Dict[year_str, float %]

Valuation multiples:
  valuation_multiples.pe_ratio | valuation_multiples.pe_sector_median
  valuation_multiples.ev_ebitda | valuation_multiples.ev_ebitda_sector_median
  valuation_multiples.price_to_sales | valuation_multiples.price_to_sales_sector_median

Leadership & people:
  leadership                         → List[{name, role, linkedin_url}]
  hiring_signals                     → List[{role_title, department, location}]

Competitive intelligence:
  competitors                        → List[{name, website, segment}]
  competitive_positioning.market_share_estimate
  competitive_positioning.axes       → List[{axis_name, our_value, competitor_value}]
  swot.strengths | swot.weaknesses | swot.opportunities | swot.threats

Risk & strategy:
  risk_factors                       → List[{factor, description}]
  capital_allocation.buybacks | capital_allocation.dividends | capital_allocation.capex_trend
  management_commentary              → List[{quote, speaker, role, source}]

News & social:
  news                               → List[{title, url, date, snippet, type}]
  social_sentiment.bullish | social_sentiment.bearish | social_sentiment.neutral

LLM-generated narrative (evidence-grounded):
  draft_report.executive_summary
  draft_report.key_findings          → List[{insight, evidence_ids}]
  draft_report.risks                 → List[{insight, evidence_ids}]
  draft_report.opportunities         → List[{insight, evidence_ids}]
  draft_report.recommendations       → List[{insight, evidence_ids}]
  draft_report.evidence_gaps         → List[str]
  industry_context.industry | industry_context.key_metrics | industry_context.strategic_themes

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMPONENT LIBRARY (renderer supports exactly these components)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HERO COMPONENTS:
  CompanyHero         → Large identity card (logo, name, tagline, key stats strip)
  TickerHero          → Bloomberg-style live price card + 52w range + volume
  SectorHero          → Market map hero for trend/sector reports
  ComparisonHero      → Side-by-side two-company header

DATA CARDS (KPI-style):
  MetricCard          → Single KPI with trend arrow and YoY delta
  MetricStrip         → Horizontal row of 4-6 MetricCards
  ValuationCard       → P/E + EV/EBITDA + P/S vs sector median
  SentimentGauge      → Bullish/Bearish/Neutral dial

CHARTS:
  RevenueLineChart    → Multi-year revenue trend (source: financials.revenue_history)
  MarginAreaChart     → Operating margin over time (source: analytics.operating_margin)
  CapitalAllocationChart → Capital allocation summary (buybacks, dividends, capex) (source: capital_allocation)
  DebtTrendChart      → Long-term debt history (source: financials.long_term_debt_history)
  CAGRBarChart        → 3Y/5Y/10Y CAGR bars (source: analytics.cagr)
  WaterfallChart      → Revenue → EBIT → Net Income bridge
  FinancialHeatmap    → Year×Metric grid with color intensity
  MarketShareDonut    → Pie/donut for competitive share (source: competitors)
  PositioningScatter  → 2-axis competitive scatter plot
  TrendRadarChart     → Radar for multi-dimension scoring
  HiringTrendBar      → Headcount by department (source: hiring_signals)
  SentimentTimeline   → Bullish/bearish over time (source: social_sentiment)

TABLES:
  FinancialTable      → Revenue/NetIncome/Margin multi-year table
  CompetitorMatrix    → Side-by-side competitor comparison table
  RiskTable           → Factor + Description + Severity table (source: risk_factors)
  LeadershipTable     → Name + Role + LinkedIn for executives (source: leadership)
  HiringTable         → Open roles table (source: hiring_signals)
  EvidenceTable       → Cited claims + evidence IDs (source: evidence_graph)

NARRATIVE CARDS:
  ExecutiveSummaryCard → Full-width prose card (source: draft_report.executive_summary)
  FindingsAccordion    → Expandable key findings (source: draft_report.key_findings)
  RecommendationCard   → Action cards with priority badge (source: draft_report.recommendations)
  EvidenceGapBanner    → Warning strip listing data gaps (source: draft_report.evidence_gaps)
  ManagementQuoteCard  → Pull-quote with speaker attribution (source: management_commentary)
  SWOTGrid             → 2×2 quadrant grid (source: swot)

INTELLIGENCE PANELS:
  TechStackBadges      → Logo badges for tech stack (source: technology_stack)
  HiringSignalsPanel   → Signal cards with department + location (source: hiring_signals)
  NewsTimeline         → Vertical timeline of recent news (source: news)
  CompetitorCards      → Card grid per competitor (source: competitors)

POSITIONING & STRATEGY:
  AxesComparisonBar    → Horizontal bars for each competitive axis (source: competitive_positioning.axes)
  BuyingSignalTracker  → CRM-style intent signal list
  OutreachBrief        → Sales email/call prep card

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT SCHEMA — return this exact structure
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{
  "version": "2.0",
  "workspace_type": "<one of the 7 workspace types>",
  "theme": {
    "name": "<theme name from template>",
    "primary_color": "<hex>",
    "accent_color": "<hex>",
    "font": "Inter",
    "density": "comfortable | compact | spacious"
  },
  "layout": {
    "style": "<command_center | comparison_matrix | narrative_scroll | data_dense | account_card | metric_grid | radar_map>",
    "grid_columns": 12,
    "max_content_width": "1400px",
    "sidebar": true | false,
    "sticky_header": true | false
  },
  "pages": [
    {
      "id": "page_snake_case",
      "title": "Page title (sentence case)",
      "icon": "tabler icon name without ti- prefix",
      "business_question": "The decision this page answers in one sentence",
      "sections": [
        {
          "id": "section_snake_case",
          "title": "Section heading (sentence case)",
          "col_span": 12,
          "components": [
            {
              "id": "component_snake_case",
              "component": "<ComponentName from library above>",
              "source": "<exact dotpath from ResearchContext>",
              "col_span": 4 | 6 | 8 | 12,
              "row_span": 1 | 2,
              "props": {
                "title": "Human-readable title",
                "subtitle": "Optional subtitle or axis label",
                "show_when_empty": false,
                "data_status": "available | unavailable | partial",
                "priority": "critical | high | medium | low",
                "format": "<currency_usd | percentage | ratio | number | text>"
              }
            }
          ]
        }
      ]
    }
  ],
  "global_filters": [
    {
      "id": "time_range",
      "label": "Time range",
      "type": "date_range | select | multi_select",
      "default": "5_years | 3_years | 1_year",
      "applies_to": ["page_id or component_id"]
    }
  ],
  "actions": [
    {
      "id": "action_id",
      "label": "Button label",
      "icon": "tabler icon name",
      "type": "export_pdf | export_pptx | export_xlsx | share_link | print",
      "priority": "primary | secondary"
    }
  ],
  "design_decisions": [
    "Explain each layout choice in one sentence — what data drove it and what business decision it serves."
  ],
  "data_gaps": [
    "List each ResearchContext field that was null/empty and how the UI handles its absence."
  ]
}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONSULTING DESIGN PRINCIPLES (apply to every workspace type)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INFORMATION HIERARCHY:
  - Above-the-fold (first screen): Identity + 4-6 north-star KPIs + executive summary.
    A CEO must understand the situation before scrolling.
  - Second screen: Evidence. Charts, tables, competitive data.
  - Third screen: Narrative. Findings, risks, recommendations with citations.
  - Fourth screen: Appendix. Raw data, evidence gaps, source list.

CHART SELECTION LOGIC (match chart type to data shape):
  - Revenue over 5+ years → RevenueLineChart (shows momentum)
  - Year-by-year growth % → CAGRBarChart (shows rate, not level)
  - Revenue → EBIT → Net Income → WaterfallChart (shows margin compression clearly)
  - 3+ competitors on 2+ axes → PositioningScatter (shows whitespace)
  - Multi-metric year grid → FinancialHeatmap (shows outlier years instantly)
  - Market share → MarketShareDonut only if <6 competitors, else CompetitorMatrix

LAYOUT RULES:
  - Financial pages: 12-column grid, charts take 8 cols left, KPIs take 4 cols right
  - Competitive pages: 2-column symmetric layout for comparison
  - Narrative sections: full-width (12 cols), readable line length
  - Never put two charts side-by-side at col_span 6 if they have different Y-axes
  - Always pair a chart with its interpretation component (FindingsAccordion) in the same section

EMPTY STATE RULES:
  - If financials is entirely null → replace FinancialTable with EvidenceGapBanner
    source: "draft_report.evidence_gaps", message about private company limitation
  - If competitors list is empty → replace CompetitorMatrix with a text-only IndustryContext card
    source: "industry_context.strategic_themes"
  - If swot is null → do not render SWOTGrid; render FindingsAccordion instead
  - Never render a chart with a null source. Check data_status first.

WORKSPACE-SPECIFIC RULES:
  CEO_REPORT:
    Build 5-6 pages whenever enough data exists.
    Page 1 — Command Center: CompanyHero + MetricStrip + ExecutiveSummaryCard
    Page 2 — Financial Performance: RevenueLineChart + WaterfallChart + FinancialTable + ValuationCard
    Page 3 — Business Quality: MarginAreaChart + CAGRBarChart + capital allocation metrics + FindingsAccordion
    Page 4 — Competitive Landscape: MarketShareDonut + AxesComparisonBar + SWOTGrid + CompetitorMatrix
    Page 5 — Operating Signals: TechStackBadges + LeadershipTable + NewsTimeline + HiringSignalsPanel
    Page 6 — Risk & Strategy: RiskTable + RecommendationCard + ManagementQuoteCard + EvidenceTable

  COMPETITOR_ANALYSIS:
    Page 1 — Comparison Overview: ComparisonHero + head-to-head MetricStrip (one column per company)
    Page 2 — Financial Battle: Side-by-side RevenueLineChart for each company in same section
    Page 3 — Positioning: PositioningScatter + AxesComparisonBar + SWOTGrid (2 columns)
    Page 4 — Strategic Verdict: RecommendationCard + EvidenceTable

  INVESTMENT_BRIEF:
    Build 5-6 pages whenever enough data exists.
    Page 1 — Thesis: TickerHero + ValuationCard + SentimentGauge + ExecutiveSummaryCard
    Page 2 — Financials: RevenueLineChart + MarginAreaChart + CAGRBarChart + WaterfallChart
    Page 3 — Capital Allocation & Quality: MetricStrip + FinancialHeatmap + FindingsAccordion
    Page 4 — Market Positioning: CompetitorMatrix + PositioningScatter + AxesComparisonBar
    Page 5 — Risk: RiskTable + NewsTimeline + ManagementQuoteCard
    Page 6 — Verdict: RecommendationCard + EvidenceTable

  SALES_INTELLIGENCE:
    Page 1 — Account Snapshot: CompanyHero + MetricStrip + TechStackBadges + LeadershipTable
    Page 2 — Buying Signals: HiringSignalsPanel + NewsTimeline + SentimentGauge
    Page 3 — Outreach Brief: OutreachBrief + RecommendationCard

  KPI_DASHBOARD:
    Page 1 — North Star: SectorHero + MetricStrip (north-star KPIs for the named industry)
    Page 2 — Financial KPIs: RevenueLineChart + MarginAreaChart + FinancialTable
    Page 3 — Operational KPIs: TrendRadarChart + HiringTrendBar + CompetitorMatrix
    Page 4 — Benchmarks: FinancialHeatmap + ValuationCard + RecommendationCard

  MARKET_RESEARCH / SECTOR_PULSE:
    Page 1 — Sector Pulse: SectorHero + TrendRadarChart + MarketShareDonut
    Page 2 — Player Map: PositioningScatter + CompetitorCards + NewsTimeline
    Page 3 — Growth Vectors: CAGRBarChart + FindingsAccordion + EvidenceGapBanner (if gaps)
    Page 4 — Investment Thesis: RecommendationCard + ManagementQuoteCard + EvidenceTable

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INPUT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
You will receive a JSON object with the following keys:
  user_query             → Original raw user query (use this to confirm workspace type)
  workspace_type         → Pre-classified workspace type (trust this unless clearly wrong)
  workspace_template     → Default layout hints for this workspace type
  research_available_fields → Dict of field_name → true/false (true = has real data)
  entity_summary         → Brief entity info (name, exchange, private/public)
  industry               → Classified industry string
  intent_summary         → Primary goal, depth, decision_type from IntentPlan
  evidence_gap_count     → Integer: how many required_data fields have coverage 0
  critique_valid         → Boolean from CriticAgent (false = do NOT show confidence > 0.6)

Return ONLY the raw JSON object matching the output schema above.
Do not include markdown code fences, explanations, or any text outside the JSON.
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4 — THE AGENT CLASS
# ─────────────────────────────────────────────────────────────────────────────

class UIAgent:
    """
    Generative UI Architect.

    Two-pass design:
      Pass 1: classify the workspace type from the raw query (fast, cheap call)
      Pass 2: full UI specification generation (expensive, quality call)

    The agent is context-aware: it reads research_available_fields to ensure
    no component references a null dotpath, and it degrades gracefully.
    """

    def __init__(self, model_router=None):
        """
        model_router: an object with .classify() and .ui() methods, each
                      returning an object with .generate_json(system, user) -> dict
                      and .generate_text(system, user) -> str
        Falls back to structured defaults if no model is available.
        """
        self.router = model_router

    def _build_available_fields(self, context_dict: dict) -> dict:
        """
        Scans the serialized ResearchContext and returns a flat dict of
        field_path -> bool (True if the field has real, non-null, non-empty data).
        This is injected into the prompt so the LLM never references missing data.
        """
        def is_real(v) -> bool:
            if v is None:
                return False
            if isinstance(v, dict):
                return len(v) > 0
            if isinstance(v, list):
                return len(v) > 0
            if isinstance(v, str):
                return v not in ("", "N/A", "Unknown", "null")
            if isinstance(v, float):
                return v > 0.0
            return True

        checks = {
            # Entity
            "entity.company_name":              is_real(((context_dict.get("entity") or {}).get("entity") or {}).get("name")),
            "entity.ticker":                    is_real(((context_dict.get("entity") or {}).get("entity") or {}).get("ticker")),
            "entity.exchange":                  ((context_dict.get("entity") or {}).get("entity") or {}).get("exchange") not in (None, "UNKNOWN", "PRIVATE"),
            # Profile
            "profile.overview":                 is_real((context_dict.get("profile") or {}).get("overview")),
            "profile.headquarters":             is_real((context_dict.get("profile") or {}).get("headquarters")),
            "profile.employee_count":           is_real((context_dict.get("profile") or {}).get("employee_count")),
            # Financials
            "financials.revenue_history":       is_real((context_dict.get("financials") or {}).get("revenue_history")),
            "financials.net_income_history":    is_real((context_dict.get("financials") or {}).get("net_income_history")),
            "financials.operating_income_history": is_real((context_dict.get("financials") or {}).get("operating_income_history")),
            "financials.long_term_debt_history": is_real((context_dict.get("financials") or {}).get("long_term_debt_history")),
            "financials.market_cap":            is_real((context_dict.get("financials") or {}).get("market_cap")),
            "financials.pe_ratio":              is_real((context_dict.get("financials") or {}).get("pe_ratio")),
            "financials.current_price":         is_real((context_dict.get("financials") or {}).get("current_price")),
            # Analytics
            "analytics.revenue_growth":         is_real((context_dict.get("analytics") or {}).get("revenue_growth")),
            "analytics.profit_growth":          is_real((context_dict.get("analytics") or {}).get("profit_growth")),
            "analytics.cagr":                   is_real((context_dict.get("analytics") or {}).get("cagr")),
            "analytics.operating_margin":       is_real((context_dict.get("analytics") or {}).get("operating_margin")),
            "analytics.debt_equity":            is_real((context_dict.get("analytics") or {}).get("debt_equity")),
            # Multiples
            "valuation_multiples":              is_real(context_dict.get("valuation_multiples")),
            # People
            "leadership":                       is_real(context_dict.get("leadership")),
            "hiring_signals":                   is_real(context_dict.get("hiring_signals")),
            # Competitive
            "competitors":                      is_real(context_dict.get("competitors")),
            "competitive_positioning":          is_real(context_dict.get("competitive_positioning")),
            "swot":                             is_real(context_dict.get("swot")),
            # Risk & strategy
            "risk_factors":                     is_real(context_dict.get("risk_factors")),
            "capital_allocation":               is_real(context_dict.get("capital_allocation")),
            "management_commentary":            is_real(context_dict.get("management_commentary")),
            # News & social
            "news":                             is_real(context_dict.get("news")),
            "social_sentiment":                 is_real(context_dict.get("social_sentiment")),
            # Tech
            "technology_stack":                 is_real(context_dict.get("technology_stack")),
            # Narrative
            "draft_report.executive_summary":   is_real((context_dict.get("draft_report") or {}).get("executive_summary")),
            "draft_report.key_findings":        is_real((context_dict.get("draft_report") or {}).get("key_findings")),
            "draft_report.risks":               is_real((context_dict.get("draft_report") or {}).get("risks")),
            "draft_report.opportunities":       is_real((context_dict.get("draft_report") or {}).get("opportunities")),
            "draft_report.recommendations":     is_real((context_dict.get("draft_report") or {}).get("recommendations")),
            "draft_report.evidence_gaps":       is_real((context_dict.get("draft_report") or {}).get("evidence_gaps")),
            "industry_context":                 is_real(context_dict.get("industry_context")),
        }
        return checks

    async def _classify_workspace(self, query: str) -> str:
        """Pass 1: fast workspace classification from the raw query."""
        if not self.router:
            return self._heuristic_classify(query)
        try:
            model = self.router.classify()
            result = await model.generate_text(QUERY_CLASSIFIER_PROMPT, query)
            ws = result.strip().upper()
            valid = set(WORKSPACE_TEMPLATES.keys())
            if ws in valid:
                return ws
            # Fuzzy fallback
            for v in valid:
                if v in ws:
                    return v
        except Exception as e:
            logger.warning(f"UIAgent workspace classifier failed: {e}")
        return self._heuristic_classify(query)

    def _heuristic_classify(self, query: str) -> str:
        """Deterministic fallback for workspace classification with no LLM."""
        q = query.lower()
        if any(w in q for w in ["vs ", " vs", "compare", "versus", "against"]):
            return "COMPETITOR_ANALYSIS"
        if any(w in q for w in ["invest", "return", "multiples", "p/e", "valuation", "dividend"]):
            return "INVESTMENT_BRIEF"
        if any(w in q for w in ["kpi", "metric", "dashboard", "track", "measure", "indicator"]):
            return "KPI_DASHBOARD"
        if any(w in q for w in ["market", "sector", "trend", "industry", "landscape", "fintech",
                                  "neobank", "bnpl", "upi", "ai ", "crypto", "climate"]):
            return "SECTOR_PULSE" if any(w in q for w in ["indian", "us ", "european", "china",
                                                             "global", "latest", "trend"]) else "MARKET_RESEARCH"
        if any(w in q for w in ["outreach", "sales", "pitch", "contact", "reach out", "prospect"]):
            return "SALES_INTELLIGENCE"
        return "CEO_REPORT"

    def _build_payload(self, query: str, context_dict: dict, workspace_type: str) -> dict:
        """Builds the structured payload injected into the main UI architect prompt."""
        available = self._build_available_fields(context_dict)
        template = WORKSPACE_TEMPLATES.get(workspace_type, WORKSPACE_TEMPLATES["CEO_REPORT"])

        def safe_dict(key):
            val = context_dict.get(key)
            logger.info(f"UI Payload '{key}': type={type(val)} value={str(val)[:300]}")
            if not isinstance(val, dict):
                return {}
            return val

        entity = safe_dict("entity")
        profile = safe_dict("profile")
        intent = safe_dict("intent")
        evidence_graph = safe_dict("evidence_graph")
        industry_context = safe_dict("industry_context")
        draft_report = safe_dict("draft_report")
        critique = safe_dict("critique")

        coverage = evidence_graph.get("coverage", {})
        if not isinstance(coverage, dict):
            coverage = {}
        gap_count = sum(1 for v in coverage.values() if v == 0.0)

        return {
            "user_query": query,
            "workspace_type": workspace_type,
            "workspace_template": template,
            "research_available_fields": available,
            "entity_summary": {
                "name": entity.get("entity", {}).get("name", profile.get("name", "Unknown")),
                "ticker": entity.get("entity", {}).get("ticker"),
                "exchange": entity.get("entity", {}).get("exchange", "PRIVATE"),
                "is_public": entity.get("entity", {}).get("exchange") not in (None, "UNKNOWN", "PRIVATE"),
                "resolution_confidence": entity.get("confidence", 0.0),
            },
            "industry": industry_context.get("industry", "general"),
            "intent_summary": {
                "primary_goal": intent.get("primary_goal", query),
                "decision_type": intent.get("decision_type", "informational"),
                "depth": intent.get("depth", "standard"),
                "required_data": intent.get("required_data", []),
            },
            "evidence_gap_count": gap_count,
            "critique_valid": critique.get("valid", True),
        }

    def _fallback_spec(self, workspace_type: str, available_fields: dict) -> dict:
        """
        Returns a safe, conservative UI spec when the LLM is unavailable.
        Only includes components whose source field is marked available.
        """
        template = WORKSPACE_TEMPLATES.get(workspace_type, WORKSPACE_TEMPLATES["CEO_REPORT"])

        pages = []

        # Page 1: Always safe — identity + summary
        page1_components = []
        if available_fields.get("entity.company_name"):
            page1_components.append({
                "id": "company_hero",
                "component": "CompanyHero",
                "source": "profile",
                "col_span": 12,
                "row_span": 1,
                "props": {"title": "Company overview", "show_when_empty": False,
                          "data_status": "available", "priority": "critical"},
            })
        if available_fields.get("draft_report.executive_summary"):
            page1_components.append({
                "id": "exec_summary",
                "component": "ExecutiveSummaryCard",
                "source": "draft_report.executive_summary",
                "col_span": 8,
                "row_span": 1,
                "props": {"title": "Executive summary", "show_when_empty": False,
                          "data_status": "available", "priority": "critical"},
            })

        if page1_components:
            pages.append({
                "id": "overview",
                "title": "Overview",
                "icon": "building",
                "business_question": "What is this company and what is the headline assessment?",
                "sections": [{"id": "hero_section", "title": "Company identity", "col_span": 12,
                               "components": page1_components}],
            })

        # Page 2: Financials (only if available)
        fin_components = []
        if available_fields.get("financials.revenue_history"):
            fin_components.append({
                "id": "revenue_chart",
                "component": "RevenueLineChart",
                "source": "financials.revenue_history",
                "col_span": 8,
                "row_span": 1,
                "props": {"title": "Revenue trend", "format": "currency_usd",
                          "show_when_empty": False, "data_status": "available", "priority": "critical"},
            })
        if available_fields.get("analytics.operating_margin"):
            fin_components.append({
                "id": "margin_chart",
                "component": "MarginAreaChart",
                "source": "analytics.operating_margin",
                "col_span": 4,
                "row_span": 1,
                "props": {"title": "Operating margin", "format": "percentage",
                          "show_when_empty": False, "data_status": "available", "priority": "high"},
            })
        if available_fields.get("capital_allocation"):
            fin_components.append({
                "id": "cap_alloc_chart",
                "component": "CapitalAllocationChart",
                "source": "capital_allocation",
                "col_span": 6,
                "row_span": 1,
                "props": {"title": "Capital allocation",
                          "show_when_empty": False, "data_status": "available", "priority": "high"},
            })
        if available_fields.get("financials.long_term_debt_history"):
            fin_components.append({
                "id": "debt_trend_chart",
                "component": "DebtTrendChart",
                "source": "financials.long_term_debt_history",
                "col_span": 6,
                "row_span": 1,
                "props": {"title": "Debt trend", "format": "currency_usd",
                          "show_when_empty": False, "data_status": "available", "priority": "medium"},
            })
        if fin_components:
            pages.append({
                "id": "financials",
                "title": "Financial performance",
                "icon": "chart-bar",
                "business_question": "Is this company financially healthy and growing?",
                "sections": [{"id": "fin_section", "title": "Financial summary",
                               "col_span": 12, "components": fin_components}],
            })

        # Page 3: Competitive landscape
        comp_components = []
        if available_fields.get("competitors"):
            comp_components.append({
                "id": "competitor_matrix",
                "component": "CompetitorMatrix",
                "source": "competitors",
                "col_span": 8,
                "row_span": 1,
                "props": {"title": "Competitive landscape", "show_when_empty": False,
                          "data_status": "available", "priority": "high"},
            })
        if available_fields.get("swot"):
            comp_components.append({
                "id": "swot_grid",
                "component": "SWOTGrid",
                "source": "swot",
                "col_span": 4,
                "row_span": 1,
                "props": {"title": "Strategic posture", "show_when_empty": False,
                          "data_status": "available", "priority": "high"},
            })
        if comp_components:
            pages.append({
                "id": "competition",
                "title": "Competitive positioning",
                "icon": "target-arrow",
                "business_question": "How well positioned is the company versus competitors?",
                "sections": [{"id": "competition_section", "title": "Market context",
                               "col_span": 12, "components": comp_components}],
            })

        # Page 4: Operating signals
        ops_components = []
        if available_fields.get("technology_stack"):
            ops_components.append({
                "id": "tech_stack",
                "component": "TechStackBadges",
                "source": "technology_stack",
                "col_span": 4,
                "row_span": 1,
                "props": {"title": "Technology stack", "show_when_empty": False,
                          "data_status": "available", "priority": "medium"},
            })
        if available_fields.get("leadership"):
            ops_components.append({
                "id": "leadership_table",
                "component": "LeadershipTable",
                "source": "leadership",
                "col_span": 4,
                "row_span": 1,
                "props": {"title": "Leadership", "show_when_empty": False,
                          "data_status": "available", "priority": "medium"},
            })
        if available_fields.get("news"):
            ops_components.append({
                "id": "news_timeline",
                "component": "NewsTimeline",
                "source": "news",
                "col_span": 4,
                "row_span": 1,
                "props": {"title": "Recent developments", "show_when_empty": False,
                          "data_status": "available", "priority": "medium"},
            })
        if ops_components:
            pages.append({
                "id": "operations",
                "title": "Operating signals",
                "icon": "activity-heartbeat",
                "business_question": "What operating signals or market developments matter right now?",
                "sections": [{"id": "operations_section", "title": "Signals and momentum",
                               "col_span": 12, "components": ops_components}],
            })

        # Page 5: Risks and recommendations
        risk_components = []
        if available_fields.get("risk_factors"):
            risk_components.append({
                "id": "risk_table",
                "component": "RiskTable",
                "source": "risk_factors",
                "col_span": 8,
                "row_span": 1,
                "props": {"title": "Risk register", "show_when_empty": False,
                          "data_status": "available", "priority": "critical"},
            })
        if available_fields.get("draft_report.recommendations"):
            risk_components.append({
                "id": "recommendations_panel",
                "component": "RecommendationCard",
                "source": "draft_report.recommendations",
                "col_span": 4,
                "row_span": 1,
                "props": {"title": "Strategic priorities", "show_when_empty": False,
                          "data_status": "available", "priority": "critical"},
            })
        if risk_components:
            pages.append({
                "id": "risk_strategy",
                "title": "Risks and strategy",
                "icon": "shield-alert",
                "business_question": "What could go wrong, and what should leadership do next?",
                "sections": [{"id": "risk_strategy_section", "title": "Downside and response",
                               "col_span": 12, "components": risk_components}],
            })

        # Page 6: Evidence appendix
        appendix_components = []
        if available_fields.get("draft_report.key_findings"):
            appendix_components.append({
                "id": "findings_accordion",
                "component": "FindingsAccordion",
                "source": "draft_report.key_findings",
                "col_span": 8,
                "row_span": 1,
                "props": {"title": "Key findings", "show_when_empty": False,
                          "data_status": "available", "priority": "medium"},
            })
        appendix_components.append({
            "id": "evidence_gaps",
            "component": "EvidenceGapBanner",
            "source": "draft_report.evidence_gaps",
            "col_span": 4,
            "row_span": 1,
            "props": {"title": "Evidence gaps", "show_when_empty": True,
                      "data_status": "partial", "priority": "low"},
        })
        if appendix_components:
            pages.append({
                "id": "appendix",
                "title": "Appendix",
                "icon": "file-text",
                "business_question": "What evidence supports the view, and where are the gaps?",
                "sections": [{"id": "appendix_section", "title": "Supporting evidence",
                               "col_span": 12, "components": appendix_components}],
            })

        return {
            "version": "2.0",
            "workspace_type": workspace_type,
            "theme": {
                "name": template["theme"],
                "primary_color": template["primary_color"],
                "accent_color": template["accent_color"],
                "font": "Inter",
                "density": "comfortable",
            },
            "layout": {
                "style": template["layout_style"],
                "grid_columns": 12,
                "max_content_width": "1400px",
                "sidebar": True,
                "sticky_header": True,
            },
            "pages": pages,
            "global_filters": [
                {"id": "time_range", "label": "Time range", "type": "select",
                 "default": "5_years", "applies_to": ["financials"]},
            ],
            "actions": [
                {"id": "export_pdf", "label": "Export PDF", "icon": "file-text",
                 "type": "export_pdf", "priority": "primary"},
                {"id": "export_pptx", "label": "Export slides", "icon": "presentation",
                 "type": "export_pptx", "priority": "secondary"},
            ],
            "design_decisions": [
                "Fallback spec: LLM unavailable. Only fields confirmed present in research data are included.",
                f"Workspace: {workspace_type}. Theme: {template['theme']}.",
            ],
            "data_gaps": [
                f"Field '{k}' is unavailable — component omitted"
                for k, v in available_fields.items() if not v
            ],
        }

    async def execute(self, query: str, context_dict: dict) -> dict:
        """
        Main entry point.

        Args:
            query:        The original raw user query string.
            context_dict: The full ResearchContext serialized as a plain dict
                          (call context.model_dump() before passing here).

        Returns:
            {"ui_generation": <spec dict>}
        """
        # Pass 1: classify workspace
        workspace_type = await self._classify_workspace(query)
        logger.info(f"UIAgent workspace classified: {workspace_type}")

        # Build available-fields map (used both by LLM and fallback)
        available_fields = self._build_available_fields(context_dict)

        # Build the structured payload for the LLM
        payload = self._build_payload(query, context_dict, workspace_type)

        # Pass 2: full UI spec generation
        if self.router:
            try:
                model = self.router.ui()
                spec = await model.generate_json(
                    UI_ARCHITECT_PROMPT,
                    json.dumps(payload, default=str)
                )
                # Safety: ensure workspace_type is set correctly
                spec["workspace_type"] = workspace_type
                # Strip any components whose source is marked unavailable
                spec = self._sanitize_spec(spec, available_fields)
                logger.info(f"UIAgent spec generated: {len(spec.get('pages', []))} pages")
                return {"ui_generation": spec}
            except Exception as e:
                logger.warning(f"UIAgent LLM failed: {e}. Using fallback spec.")

        return {"ui_generation": self._fallback_spec(workspace_type, available_fields)}

    def _sanitize_spec(self, spec: dict, available_fields: dict) -> dict:
        """
        Post-processing pass: removes any component that references
        an unavailable field. Prevents the LLM from hallucinating
        a chart over a null dotpath.
        """
        if "pages" not in spec:
            return spec
        for page in spec.get("pages", []):
            for section in page.get("sections", []):
                kept = []
                for comp in section.get("components", []):
                    source = comp.get("source", "")
                    show_empty = comp.get("props", {}).get("show_when_empty", False)
                    if show_empty:
                        kept.append(comp)
                        continue
                    # Check if this source dotpath has data
                    is_available = available_fields.get(source, True)  # default True if path not in our checks
                    if is_available:
                        kept.append(comp)
                    else:
                        logger.debug(f"UIAgent sanitizer dropped: {comp.get('id')} (source={source})")
                section["components"] = kept
        return spec
