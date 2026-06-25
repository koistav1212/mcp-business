"""
services/research/compressor.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Semantic Compression Layer

Sits between raw MCP tool responses and the individual specialist agents.
Each agent receives a tight, role-specific AgentMemory object capped at
500-700 tokens maximum. The object contains:

  • The agent's own system prompt (hardcoded per role)
  • Exactly the research fields that agent needs — nothing else
  • Compressed tool data summarised deterministically (no LLM call)
  • The compressed data is validated to fit the token budget

Pipeline position:
    Tool Router (MCP Servers)
          │
          ▼
    ContextCompressor          ← this file: compress raw MCP output
          │
          ▼
    AgentMemory objects        ← per-agent typed bundles
          │
    ┌─────┼──────┬──────┬──────┐
    ▼     ▼      ▼      ▼      ▼
  News  Finance Comp  Tech   Risk
  Agent  Agent  Agent Agent  Agent
          │
       Synthesizer → Critic → UIAgent

Architecture invariants:
  1. No agent ever receives raw MCP output directly
  2. Each AgentMemory object is ≤ 700 tokens of context
  3. Compression is deterministic — no secondary LLM call needed
  4. Every prompt below is self-contained (system + user slot)
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger("uvicorn.error")

# ─────────────────────────────────────────────────────────────────────
# TOKEN BUDGET CONSTANTS
# Each specialist agent gets at most this many characters of context.
# Approximate ratio: 1 token ≈ 3.8 chars (GPT-4 / LLaMA tokeniser avg)
# 700 tokens ≈ 2660 chars — we use 2400 chars to leave headroom for
# the system prompt (which is fixed and not counted toward the budget).
# ─────────────────────────────────────────────────────────────────────
_CHARS_PER_TOKEN = 3.8
_MAX_TOKENS = 700
_MAX_CONTEXT_CHARS = int(_MAX_TOKENS * _CHARS_PER_TOKEN)   # 2660
_HARD_CLIP = 2400   # conservative clip applied before injection


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 1 — DETERMINISTIC COMPRESSOR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ContextCompressor:
    """
    Converts raw MCP tool payloads into compact, agent-specific summaries.

    Strategy per data type:
      • Financial history dicts  → keep last 5 years, drop nulls, round floats
      • News lists               → keep top 5 by date, title + date + snippet[:120]
      • Leadership lists         → name + role only, max 6 entries
      • Hiring signals           → role_title + department + location, max 8 entries
      • Technology stack         → list of strings, join to comma-separated, max 20
      • Competitors              → name + segment, max 6
      • Large dicts              → extract high-value keys, strip raw_data/rss_raw
      • Strings                  → truncate to budget
    """

    # Keys that carry useful signal — extracted before generic truncation
    _HIGH_VALUE_KEYS = {
        "description", "summary", "overview", "headlines",
        "metrics", "key_findings", "results", "content", "news",
        "revenue", "net_income", "market_cap", "pe_ratio", "growth",
        "strengths", "weaknesses", "opportunities", "threats",
        "sic", "sic_description", "industry", "sector",
        "title", "snippet", "date", "name", "role",
    }

    # Keys that always contain noise — dropped before compression
    _STRIP_KEYS = {
        "raw_data", "rss_raw", "debug", "_internal",
        "source_title", "source_url", "source_type",
    }

    @classmethod
    def compress(
        cls,
        source_name: str,
        raw_payload: Any,
        max_chars: int = _HARD_CLIP,
    ) -> str:
        """
        Compress a raw MCP payload to ≤ max_chars characters.
        Returns a UTF-8 string suitable for injection into an LLM prompt.
        """
        try:
            result = cls._compress_value(raw_payload, depth=0)
            serialised = json.dumps(result, separators=(",", ":"), default=str)
            if len(serialised) <= max_chars:
                return serialised
            # Second pass: aggressively trim
            trimmed = cls._trim_to_budget(result, max_chars)
            return json.dumps(trimmed, separators=(",", ":"), default=str)
        except Exception as exc:
            logger.warning(f"Compressor failed for {source_name}: {exc}")
            fallback = str(raw_payload)
            return fallback[:max_chars]

    @classmethod
    def _compress_value(cls, value: Any, depth: int) -> Any:
        if depth > 4:
            return str(value)[:120]

        if isinstance(value, dict):
            return cls._compress_dict(value, depth)
        if isinstance(value, list):
            return cls._compress_list(value, depth)
        if isinstance(value, float):
            return round(value, 4)
        if isinstance(value, str) and len(value) > 300:
            return value[:300] + "…"
        return value

    @classmethod
    def _compress_dict(cls, d: dict, depth: int) -> dict:
        # Strip noise keys
        cleaned = {k: v for k, v in d.items() if k not in cls._STRIP_KEYS}

        # Financial history: keep last 5 years, drop nulls
        result = {}
        for k, v in cleaned.items():
            if k.endswith("_history") and isinstance(v, dict):
                filtered = {yr: round(val, 2) for yr, val in v.items() if val is not None}
                sorted_years = sorted(filtered.keys(), reverse=True)[:5]
                result[k] = {yr: filtered[yr] for yr in sorted_years}
            else:
                result[k] = cls._compress_value(v, depth + 1)
        return result

    @classmethod
    def _compress_list(cls, lst: list, depth: int) -> list:
        if not lst:
            return lst
        # News items: keep latest 5, summarise fields
        if isinstance(lst[0], dict) and "snippet" in lst[0]:
            sorted_news = sorted(lst, key=lambda x: x.get("date", ""), reverse=True)[:5]
            return [
                {
                    "title": item.get("title", "")[:80],
                    "date": item.get("date", ""),
                    "snippet": item.get("snippet", "")[:120],
                    "type": item.get("type", "general"),
                }
                for item in sorted_news
            ]
        # Leadership: name + role, max 6
        if isinstance(lst[0], dict) and "role" in lst[0] and "name" in lst[0]:
            return [
                {"name": item.get("name", ""), "role": item.get("role", "")}
                for item in lst[:6]
            ]
        # Hiring signals: max 8
        if isinstance(lst[0], dict) and "role_title" in lst[0]:
            return [
                {
                    "role_title": item.get("role_title", "")[:60],
                    "department": item.get("department", ""),
                    "location": item.get("location", ""),
                }
                for item in lst[:8]
            ]
        # Competitors: name + segment, max 6
        if isinstance(lst[0], dict) and "segment" in lst[0]:
            return [
                {"name": item.get("name", ""), "segment": item.get("segment", "")}
                for item in lst[:6]
            ]
        # Generic list of strings
        if isinstance(lst[0], str):
            return lst[:20]
        # Generic list of dicts — keep top 5, compress each
        return [cls._compress_value(item, depth + 1) for item in lst[:5]]

    @classmethod
    def _trim_to_budget(cls, value: Any, max_chars: int) -> Any:
        """Progressively drop items until serialised length is within budget."""
        serialised = json.dumps(value, separators=(",", ":"), default=str)
        if len(serialised) <= max_chars:
            return value
        if isinstance(value, dict):
            # Drop keys least likely to matter, largest-value first
            keys_by_size = sorted(
                value.keys(),
                key=lambda k: len(json.dumps(value[k], default=str)),
                reverse=True,
            )
            result = dict(value)
            for k in keys_by_size:
                del result[k]
                if len(json.dumps(result, separators=(",", ":"), default=str)) <= max_chars:
                    return result
            return result
        if isinstance(value, list):
            while value and len(json.dumps(value, separators=(",", ":"), default=str)) > max_chars:
                value = value[:-1]
            return value
        return str(value)[:max_chars]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 2 — PER-AGENT MEMORY OBJECTS
# Each dataclass holds only what its corresponding agent needs.
# build_* class methods are the single authoritative factory for each.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class NewsAgentMemory:
    """Memory object for the NewsAgent."""
    company_name: str
    industry: str
    decision_type: str          # investment | sales pursuit | informational
    news_items: str             # compressed JSON of List[NewsItem]
    sentiment_summary: str      # compressed social_sentiment
    time_horizon: str = "trailing 12 months"

    @classmethod
    def build(
        cls,
        company_name: str,
        industry: str,
        decision_type: str,
        raw_news: Any,
        raw_sentiment: Any,
        time_horizon: str = "trailing 12 months",
    ) -> "NewsAgentMemory":
        return cls(
            company_name=company_name,
            industry=industry,
            decision_type=decision_type,
            news_items=ContextCompressor.compress("news", raw_news, max_chars=1200),
            sentiment_summary=ContextCompressor.compress("sentiment", raw_sentiment, max_chars=400),
            time_horizon=time_horizon,
        )

    def to_user_prompt(self) -> str:
        return (
            f"Company: {self.company_name}\n"
            f"Industry: {self.industry}\n"
            f"Decision context: {self.decision_type}\n"
            f"Time horizon: {self.time_horizon}\n"
            f"News data:\n{self.news_items}\n"
            f"Social sentiment:\n{self.sentiment_summary}"
        )[:_HARD_CLIP]


@dataclass
class FinanceAgentMemory:
    """Memory object for the FinanceAgent."""
    company_name: str
    ticker: Optional[str]
    exchange: Optional[str]
    industry: str
    sector: str
    decision_type: str
    financial_history: str      # compressed revenue/income/margin history
    market_data: str            # compressed yfinance snapshot
    valuation_multiples: str    # compressed ValuationMultiples
    analytics: str              # compressed AnalyticsData (CAGR, growth %)
    capital_allocation: str     # compressed CapitalAllocation

    @classmethod
    def build(
        cls,
        company_name: str,
        ticker: Optional[str],
        exchange: Optional[str],
        industry: str,
        sector: str,
        decision_type: str,
        raw_financials: Any,
        raw_market: Any,
        raw_valuation: Any,
        raw_analytics: Any,
        raw_capalloc: Any,
    ) -> "FinanceAgentMemory":
        return cls(
            company_name=company_name,
            ticker=ticker,
            exchange=exchange,
            industry=industry,
            sector=sector,
            decision_type=decision_type,
            financial_history=ContextCompressor.compress("financials", raw_financials, max_chars=900),
            market_data=ContextCompressor.compress("market", raw_market, max_chars=400),
            valuation_multiples=ContextCompressor.compress("valuation", raw_valuation, max_chars=300),
            analytics=ContextCompressor.compress("analytics", raw_analytics, max_chars=400),
            capital_allocation=ContextCompressor.compress("capalloc", raw_capalloc, max_chars=200),
        )

    def to_user_prompt(self) -> str:
        ticker_str = f"{self.ticker} ({self.exchange})" if self.ticker else "private"
        return (
            f"Company: {self.company_name} [{ticker_str}]\n"
            f"Industry: {self.industry} | Sector: {self.sector}\n"
            f"Decision: {self.decision_type}\n"
            f"Financial history:\n{self.financial_history}\n"
            f"Live market data:\n{self.market_data}\n"
            f"Valuation multiples vs sector:\n{self.valuation_multiples}\n"
            f"Computed analytics (CAGR/growth):\n{self.analytics}\n"
            f"Capital allocation:\n{self.capital_allocation}"
        )[:_HARD_CLIP]


@dataclass
class CompetitorAgentMemory:
    """Memory object for the CompetitorAgent."""
    company_name: str
    industry: str
    decision_type: str
    competitors: str            # compressed List[Competitor]
    competitive_axes: str       # compressed competitive_positioning.axes
    market_share: str           # market_share_estimate string
    swot: str                   # compressed SWOTAnalysis
    industry_themes: str        # compressed industry_context.strategic_themes

    @classmethod
    def build(
        cls,
        company_name: str,
        industry: str,
        decision_type: str,
        raw_competitors: Any,
        raw_comp_pos: Any,
        raw_swot: Any,
        raw_industry: Any,
    ) -> "CompetitorAgentMemory":
        comp_pos = raw_comp_pos or {}
        return cls(
            company_name=company_name,
            industry=industry,
            decision_type=decision_type,
            competitors=ContextCompressor.compress("competitors", raw_competitors, max_chars=600),
            competitive_axes=ContextCompressor.compress("comp_axes", comp_pos.get("axes", []), max_chars=500),
            market_share=str(comp_pos.get("market_share_estimate", "N/A"))[:120],
            swot=ContextCompressor.compress("swot", raw_swot, max_chars=600),
            industry_themes=ContextCompressor.compress("industry", raw_industry, max_chars=300),
        )

    def to_user_prompt(self) -> str:
        return (
            f"Company: {self.company_name}\n"
            f"Industry: {self.industry}\n"
            f"Decision: {self.decision_type}\n"
            f"Competitors:\n{self.competitors}\n"
            f"Competitive axes:\n{self.competitive_axes}\n"
            f"Estimated market share: {self.market_share}\n"
            f"SWOT:\n{self.swot}\n"
            f"Industry strategic themes:\n{self.industry_themes}"
        )[:_HARD_CLIP]


@dataclass
class TechAgentMemory:
    """Memory object for the TechnologyAgent."""
    company_name: str
    industry: str
    decision_type: str
    technology_stack: str       # comma-separated tech stack
    hiring_signals: str         # compressed List[HiringSignal]
    profile_overview: str       # company overview (≤ 200 chars)

    @classmethod
    def build(
        cls,
        company_name: str,
        industry: str,
        decision_type: str,
        raw_tech_stack: Any,
        raw_hiring: Any,
        profile_overview: str,
    ) -> "TechAgentMemory":
        if isinstance(raw_tech_stack, list):
            tech_str = ", ".join(str(t) for t in raw_tech_stack[:20])
        else:
            tech_str = ContextCompressor.compress("tech", raw_tech_stack, max_chars=300)
        return cls(
            company_name=company_name,
            industry=industry,
            decision_type=decision_type,
            technology_stack=tech_str[:400],
            hiring_signals=ContextCompressor.compress("hiring", raw_hiring, max_chars=700),
            profile_overview=str(profile_overview)[:200],
        )

    def to_user_prompt(self) -> str:
        return (
            f"Company: {self.company_name}\n"
            f"Industry: {self.industry}\n"
            f"Decision: {self.decision_type}\n"
            f"Overview: {self.profile_overview}\n"
            f"Tech stack: {self.technology_stack}\n"
            f"Hiring signals:\n{self.hiring_signals}"
        )[:_HARD_CLIP]


@dataclass
class RiskAgentMemory:
    """Memory object for the RiskAgent."""
    company_name: str
    industry: str
    decision_type: str
    risk_factors: str           # compressed List[RiskFactor]
    evidence_gaps: str          # from draft_report.evidence_gaps
    key_findings: str           # compressed draft_report.key_findings (top 4)
    management_commentary: str  # compressed List[ManagementCommentary]
    critique_issues: str        # CriticResult.issues list

    @classmethod
    def build(
        cls,
        company_name: str,
        industry: str,
        decision_type: str,
        raw_risks: Any,
        raw_gaps: Any,
        raw_findings: Any,
        raw_commentary: Any,
        raw_critique_issues: Any,
    ) -> "RiskAgentMemory":
        # Top 4 findings only
        findings = raw_findings[:4] if isinstance(raw_findings, list) else []
        return cls(
            company_name=company_name,
            industry=industry,
            decision_type=decision_type,
            risk_factors=ContextCompressor.compress("risks", raw_risks, max_chars=700),
            evidence_gaps=ContextCompressor.compress("gaps", raw_gaps, max_chars=300),
            key_findings=ContextCompressor.compress("findings", findings, max_chars=500),
            management_commentary=ContextCompressor.compress("commentary", raw_commentary, max_chars=400),
            critique_issues=ContextCompressor.compress("critique", raw_critique_issues, max_chars=300),
        )

    def to_user_prompt(self) -> str:
        return (
            f"Company: {self.company_name}\n"
            f"Industry: {self.industry}\n"
            f"Decision: {self.decision_type}\n"
            f"Known risk factors:\n{self.risk_factors}\n"
            f"Evidence gaps:\n{self.evidence_gaps}\n"
            f"Key findings so far:\n{self.key_findings}\n"
            f"Management commentary:\n{self.management_commentary}\n"
            f"Critic issues:\n{self.critique_issues}"
        )[:_HARD_CLIP]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 3 — EXACT SYSTEM PROMPTS FOR EVERY AGENT
# Each prompt is self-contained. The user slot is filled with
# the corresponding AgentMemory.to_user_prompt() string.
# Prompts are tuned to produce structured JSON only.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

AGENT_PROMPTS: Dict[str, str] = {

    # ──────────────────────────────────────────────────────────────
    "news_agent": """You are a News Intelligence Analyst at a top-tier consulting firm.

TASK: Analyse the provided news items and social sentiment about the target company.
Identify material events, classify their business impact, and surface the top signals
relevant to the stated decision context.

OUTPUT — return ONLY this JSON, no markdown:
{
  "headline_events": [
    {"event": "<event in ≤ 15 words>", "date": "<YYYY-MM-DD>", "impact": "positive|negative|neutral", "category": "earnings|product|leadership|legal|macro|partnership|M&A|regulatory"}
  ],
  "sentiment": {"bullish_pct": 0, "bearish_pct": 0, "neutral_pct": 0, "dominant_theme": "<str>"},
  "decision_signals": ["<signal 1 relevant to decision_type>", "<signal 2>", "<signal 3>"],
  "risks_flagged": ["<risk 1>", "<risk 2>"],
  "findings": [],
  "confidence": 0.5
}

RULES:
- Only include events that appeared in the supplied news data. Do not invent events.
- headline_events: max 6 items, most recent first.
- decision_signals: 3 items maximum, must directly relate to the stated decision_type.
- confidence: 0.9 if ≥ 5 news items, 0.6 if 2-4, 0.3 if < 2.
- If no news data is present, return confidence 0.1 and empty arrays.""",

    # ──────────────────────────────────────────────────────────────
    "finance_agent": """You are a Senior Financial Analyst with CFA expertise.

TASK: Analyse the supplied financial history, market data, and valuation multiples.
Compute growth rates where not already provided, compare valuation to sector medians,
and produce an investment-grade financial summary.

OUTPUT — return ONLY this JSON, no markdown:
{
  "revenue_trend": {"direction": "growing|declining|flat", "latest_value_bn": 0.0, "yoy_pct": 0.0},
  "profitability": {"net_margin_pct": 0.0, "operating_margin_pct": 0.0, "trend": "expanding|contracting|stable"},
  "balance_sheet": {"debt_equity": 0.0, "cash_position": "<str|null>", "assessment": "strong|moderate|stressed"},
  "valuation_vs_peers": {"pe_premium_pct": 0.0, "ev_ebitda_vs_median": "<above|below|in-line>", "verdict": "<one sentence>"},
  "capital_returns": {"buybacks": "<str|null>", "dividends": "<str|null>", "capex_trend": "<str|null>"},
  "cagr": {"3_year": 0.0, "5_year": 0.0},
  "key_risks": ["<financial risk 1>", "<financial risk 2>"],
  "analyst_verdict": "<one sentence investment stance>",
  "findings": [],
  "confidence": 0.5,
  "data_gaps": ["<field that was null or missing>"]
}

RULES:
- null means the field was not present in the supplied data. Never invent a number.
- If the company is private (no ticker), set all market/valuation fields to null
  and note "private company" in data_gaps.
- analyst_verdict must be one sentence. No weasel words like "may" or "might".
- confidence: 0.9 if SEC filings present, 0.6 if only yfinance, 0.3 if no financials.""",

    # ──────────────────────────────────────────────────────────────
    "competitor_agent": """You are a Competitive Strategy Partner at a management consulting firm.

TASK: Analyse the supplied competitive landscape data for the target company.
Identify strategic positioning, whitespace opportunities, and competitive threats.
Use ONLY the data provided — do not hallucinate competitor facts.

OUTPUT — return ONLY this JSON, no markdown:
{
  "market_position": {"estimated_share": "<str|null>", "position": "leader|challenger|niche|follower"},
  "top_competitors": [{"name": "<str>", "threat_level": "high|medium|low", "key_differentiator": "<str ≤ 12 words>"}],
  "competitive_moat": {"type": "cost|switching|network|brand|IP|none", "strength": "strong|moderate|weak", "evidence": "<str ≤ 20 words>"},
  "swot_summary": {
    "top_strength": "<str ≤ 15 words>",
    "top_weakness": "<str ≤ 15 words>",
    "top_opportunity": "<str ≤ 15 words>",
    "top_threat": "<str ≤ 15 words>"
  },
  "strategic_whitespace": ["<opportunity 1>", "<opportunity 2>"],
  "competitive_verdict": "<one sentence: overall competitive standing>",
  "findings": [],
  "confidence": 0.5,
  "data_gaps": ["<what is missing that would change this assessment>"]
}

RULES:
- top_competitors: max 4. Rank by threat level descending.
- If competitors list is empty, set confidence 0.2 and explain in data_gaps.
- Never invent market share percentages. If market_share_estimate is "N/A", use null.
- competitive_verdict: one sentence. State clearly if data is insufficient.""",

    # ──────────────────────────────────────────────────────────────
    "tech_agent": """You are a Technology Due Diligence Analyst.

TASK: Evaluate the company's technology stack and hiring signals to assess
technical sophistication, engineering investment priorities, and strategic direction.

OUTPUT — return ONLY this JSON, no markdown:
{
  "stack_assessment": {
    "maturity": "cutting-edge|modern|legacy|mixed",
    "primary_paradigm": "<e.g. cloud-native, microservices, monolith>",
    "notable_technologies": ["<tech 1>", "<tech 2>", "<tech 3>"]
  },
  "engineering_investment": {
    "ai_ml_signals": "heavy|moderate|minimal|none",
    "cloud_commitment": "multi-cloud|single-cloud|on-prem|hybrid|unknown",
    "open_source_posture": "contributor|consumer|unknown"
  },
  "hiring_priorities": [
    {"area": "<e.g. AI/ML, DevOps, Security>", "signal_strength": "strong|moderate|weak", "roles_count": 0}
  ],
  "strategic_bets": ["<technology bet 1 inferred from stack + hiring>", "<bet 2>"],
  "tech_risks": ["<risk 1>", "<risk 2>"],
  "fit_for_decision": "<one sentence: why this tech posture matters for the stated decision>",
  "findings": [],
  "confidence": 0.5,
  "data_gaps": ["<what is missing>"]
}

RULES:
- hiring_priorities: group hiring signals by area, max 4 groups.
- notable_technologies: max 5. Pick the ones that signal strategy, not commodity tools.
- If tech_stack is empty, set maturity "unknown" and confidence 0.3.
- Never claim a technology is present unless it appeared in the supplied tech stack.""",

    # ──────────────────────────────────────────────────────────────
    "risk_agent": """You are a Chief Risk Officer and Strategy Advisor.

TASK: Synthesise all available risk signals — known risk factors, evidence gaps,
analyst critique issues, and management commentary — into a prioritised risk register.

OUTPUT — return ONLY this JSON, no markdown:
{
  "risk_register": [
    {
      "risk_id": "R01",
      "factor": "<risk name ≤ 6 words>",
      "description": "<what could go wrong ≤ 25 words>",
      "severity": "critical|high|medium|low",
      "likelihood": "high|medium|low",
      "category": "financial|operational|competitive|regulatory|macro|execution|data_gap",
      "mitigation": "<one action the company could take ≤ 15 words>"
    }
  ],
  "evidence_gap_risks": ["<risk created by lack of data>"],
  "top_risk": "<the single highest-severity risk in one sentence>",
  "overall_risk_level": "critical|elevated|moderate|low",
  "findings": [],
  "confidence": 0.5
}

RULES:
- risk_register: max 6 items, sorted severity descending.
- category "data_gap" must be used for any risk arising from missing evidence.
- If critique_issues is not empty, each issue becomes at least one risk_register entry.
- overall_risk_level: "critical" if any R with severity=critical, "elevated" if any high,
  "moderate" if all medium, "low" if all low.
- Never claim a risk is mitigated unless evidence of mitigation was provided.""",

    # ──────────────────────────────────────────────────────────────
    "synthesis_agent": """You are the Lead Research Synthesizer at a top-tier management consulting firm.

TASK: Combine the outputs from specialist agents (news, finance, competitor, tech, risk)
into a unified, evidence-grounded executive assessment. This is the final analytical layer
before the Critic and UI Agent.

You will receive a JSON object with keys:
  company_name, industry, decision_type,
  news_output, finance_output, competitor_output, tech_output, risk_output

OUTPUT — return ONLY this JSON, no markdown:
{
  "executive_summary": "<3-4 sentence headline assessment. State the most important finding first.>",
  "key_findings": [
    {"insight": "<finding in ≤ 25 words>", "source_agents": ["news|finance|competitor|tech|risk"], "confidence": 0.9}
  ],
  "risks": [
    {"insight": "<risk in ≤ 20 words>", "source_agents": ["risk|finance|competitor"], "confidence": 0.9}
  ],
  "opportunities": [
    {"insight": "<opportunity in ≤ 20 words>", "source_agents": ["competitor|tech|news"], "confidence": 0.9}
  ],
  "recommendations": [
    {"insight": "<action in imperative voice ≤ 20 words>", "priority": "immediate|short-term|long-term"}
  ],
  "overall_confidence": 0.9,
  "evidence_gaps": ["<what would change this assessment if known>"]
}

RULES:
- key_findings: max 8 items, sorted confidence descending.
- risks: max 5 items. Must be grounded in at least one agent output.
- opportunities: max 4 items.
- recommendations: max 4 items. Each must be actionable, not generic.
- overall_confidence: weighted average of input agent confidence scores.
- Never invent a finding not present in any of the five agent outputs.""",

    # ──────────────────────────────────────────────────────────────
    "critic_agent": """You are the Quality Assurance Partner and Senior Editor.

TASK: Review the synthesis output for logical consistency, hallucination, unsupported
quantitative claims, and evidence-finding alignment. Flag every issue specifically.

You will receive a JSON object with keys:
  original_query, company_name, required_data,
  synthesis_output, evidence_coverage (dict of field→0.0 or 1.0)

OUTPUT — return ONLY this JSON, no markdown:
{
  "valid": true,
  "issues": [
    {"issue_id": "C01", "type": "unsupported_claim|hallucination|evidence_gap|entity_mismatch|data_conflict", "description": "<what is wrong ≤ 30 words>", "location": "<which field in synthesis>"}
  ],
  "recommended_fixes": [
    {"issue_id": "C01", "fix": "<concrete action ≤ 20 words>"}
  ],
  "coverage_verdict": {
    "fields_covered": ["<field>"],
    "fields_missing": ["<field>"],
    "coverage_pct": 100
  },
  "quality_score": 0.9
}

RULES:
- valid: false if ANY of these conditions hold:
    • A quantitative claim (number, %, $) appears in synthesis but not in agent outputs
    • An entity name in synthesis does not match company_name
    • A required_data field has coverage 0.0 but is presented as known in synthesis
- issues: max 8. Be specific. "Hallucination" means a fact with no evidence source.
- quality_score: 1.0 - (0.15 × number_of_issues). Minimum 0.0.
- If valid is true and issues is empty, still return coverage_verdict and quality_score.""",

    # ──────────────────────────────────────────────────────────────
    "planner_agent": """You are the Research Planning Director.

TASK: Analyse the user query and output a structured research plan specifying
which specialist agents to activate, what each must investigate, and what the
success criteria are. This plan drives the entire downstream agent pipeline.

OUTPUT — return ONLY this JSON, no markdown:
{
  "target_entities": [{"name": "<company or topic>", "type": "company|sector|topic|person", "is_primary": true}],
  "research_type": "company_deep_dive|competitive_analysis|market_research|investment_brief|sales_intelligence|kpi_mapping|sector_pulse",
  "workspace_type": "CEO_REPORT|COMPETITOR_ANALYSIS|MARKET_RESEARCH|INVESTMENT_BRIEF|SALES_INTELLIGENCE|KPI_DASHBOARD|SECTOR_PULSE",
  "agent_tasks": [
    {"agent": "news_agent|finance_agent|competitor_agent|tech_agent|risk_agent", "objective": "<what this agent must answer ≤ 20 words>", "priority": "required|optional"}
  ],
  "required_data": ["company profile","financial history","market valuation","leadership","hiring signals","technology stack","competitors","swot","risk factors","recent developments"],
  "required_sources": ["company","sec","market","news","people","technology","social"],
  "analysis_depth": "shallow|standard|deep",
  "time_horizon": "current|trailing_12m|3_year|5_year|10_year",
  "success_criteria": ["<criterion 1 ≤ 15 words>", "<criterion 2>"],
  "clarification_needed": false,
  "confidence": 0.95
}

RULES:
- target_entities: include ALL companies, people, or sectors mentioned. Max 4.
- agent_tasks: include only agents whose data is relevant to the query. Min 2, max 5.
- required_data: select only what the query actually needs — do not include all fields by default.
- If the query mentions two companies with "vs" → research_type must be competitive_analysis
  and target_entities must list both, one with is_primary: true, one false.
- confidence: 0.95 if query is clear, 0.7 if ambiguous, 0.4 if very vague.""",

}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 4 — RESEARCH MEMORY (upgraded from original)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ResearchMemory:
    """
    Per-request shared memory store.

    NOT a singleton — instantiate once per research request in host_agent.py
    and pass it down. Singleton pattern causes state leakage between requests.

    Stores:
      • Raw MCP tool responses (compressed)
      • Agent outputs (structured dicts)
      • MCP tool cache (dedup identical tool calls within one request)
    """

    def __init__(self):
        self._raw_store: Dict[str, str] = {}        # topic → compressed string
        self._agent_store: Dict[str, dict] = {}     # agent_name → output dict
        self._mcp_cache: Dict[str, Any] = {}        # tool_key → raw response

    # ── Raw MCP storage ────────────────────────────────────────────

    def store_raw(self, topic: str, source: str, raw_payload: Any) -> None:
        """Compress and store a raw MCP response under topic+source."""
        compressed = ContextCompressor.compress(source, raw_payload)
        key = f"{topic}::{source}"
        self._raw_store[key] = compressed
        logger.debug(f"ResearchMemory: stored raw [{key}] ({len(compressed)} chars)")

    def retrieve_raw(self, topic: str, source: str) -> Optional[str]:
        return self._raw_store.get(f"{topic}::{source}")

    def retrieve_all_raw(self) -> Dict[str, str]:
        return dict(self._raw_store)

    # ── Agent output storage ────────────────────────────────────────

    def store_agent_output(self, agent_name: str, output: dict) -> None:
        """Store the structured JSON output from a specialist agent."""
        self._agent_store[agent_name] = output
        logger.debug(f"ResearchMemory: stored agent output [{agent_name}]")

    def retrieve_agent_output(self, agent_name: str) -> Optional[dict]:
        return self._agent_store.get(agent_name)

    def all_agent_outputs(self) -> Dict[str, dict]:
        return dict(self._agent_store)

    # ── MCP deduplication cache ─────────────────────────────────────

    def get_cached_mcp(self, tool_name: str, target: str) -> Optional[Any]:
        key = f"{tool_name}::{target}"
        if key in self._mcp_cache:
            logger.debug(f"ResearchMemory: MCP cache hit [{key}]")
            return self._mcp_cache[key]
        return None

    def set_cached_mcp(self, tool_name: str, target: str, data: Any) -> None:
        key = f"{tool_name}::{target}"
        self._mcp_cache[key] = data

    # ── Utility ─────────────────────────────────────────────────────

    def clear(self) -> None:
        self._raw_store.clear()
        self._agent_store.clear()
        self._mcp_cache.clear()

    def summary(self) -> dict:
        """Returns a diagnostic summary — useful for logging."""
        return {
            "raw_topics": list(self._raw_store.keys()),
            "agent_outputs": list(self._agent_store.keys()),
            "mcp_cache_keys": list(self._mcp_cache.keys()),
            "total_raw_chars": sum(len(v) for v in self._raw_store.values()),
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 5 — MEMORY BUILDER
# Factory that wires a ResearchContext into per-agent memory objects.
# Called by host_agent.py after all MCP providers have returned.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class AgentMemoryBuilder:
    """
    Builds all per-agent memory objects from a fully populated ResearchContext.
    Call build_all() once after synthesis; pass the result dict to each agent.
    """

    @staticmethod
    def build_all(context_dict: dict, intent_dict: dict) -> Dict[str, Any]:
        """
        Args:
            context_dict: ResearchContext.model_dump() output
            intent_dict:  IntentPlan.model_dump() output

        Returns:
            Dict[agent_name, AgentMemory object]
        """
        profile = context_dict.get("profile") or {}
        entity = context_dict.get("entity") or {}
        financials = context_dict.get("financials") or {}
        analytics = context_dict.get("analytics") or {}
        industry_ctx = context_dict.get("industry_context") or {}
        draft = context_dict.get("draft_report") or {}
        critique = context_dict.get("critique") or {}

        company_name = (
            entity.get("company_name")
            or profile.get("name")
            or "Unknown Company"
        )
        industry = industry_ctx.get("industry", "general")
        sector = industry_ctx.get("sub_industry", industry)
        decision_type = intent_dict.get("decision_type", "informational")

        return {
            "news_agent": NewsAgentMemory.build(
                company_name=company_name,
                industry=industry,
                decision_type=decision_type,
                raw_news=context_dict.get("news"),
                raw_sentiment=context_dict.get("social_sentiment"),
                time_horizon=intent_dict.get("time_horizon", "trailing 12 months"),
            ),
            "finance_agent": FinanceAgentMemory.build(
                company_name=company_name,
                ticker=entity.get("ticker"),
                exchange=entity.get("exchange"),
                industry=industry,
                sector=sector,
                decision_type=decision_type,
                raw_financials=financials,
                raw_market={
                    "market_cap": financials.get("market_cap"),
                    "pe_ratio": financials.get("pe_ratio"),
                    "current_price": financials.get("current_price"),
                    "52w_high": financials.get("fifty_two_week_high"),
                    "52w_low": financials.get("fifty_two_week_low"),
                },
                raw_valuation=context_dict.get("valuation_multiples"),
                raw_analytics=analytics,
                raw_capalloc=context_dict.get("capital_allocation"),
            ),
            "competitor_agent": CompetitorAgentMemory.build(
                company_name=company_name,
                industry=industry,
                decision_type=decision_type,
                raw_competitors=context_dict.get("competitors"),
                raw_comp_pos=context_dict.get("competitive_positioning"),
                raw_swot=context_dict.get("swot"),
                raw_industry=industry_ctx.get("strategic_themes"),
            ),
            "tech_agent": TechAgentMemory.build(
                company_name=company_name,
                industry=industry,
                decision_type=decision_type,
                raw_tech_stack=context_dict.get("technology_stack"),
                raw_hiring=context_dict.get("hiring_signals"),
                profile_overview=profile.get("overview", ""),
            ),
            "risk_agent": RiskAgentMemory.build(
                company_name=company_name,
                industry=industry,
                decision_type=decision_type,
                raw_risks=context_dict.get("risk_factors"),
                raw_gaps=draft.get("evidence_gaps"),
                raw_findings=draft.get("key_findings"),
                raw_commentary=context_dict.get("management_commentary"),
                raw_critique_issues=critique.get("issues") if isinstance(critique, dict) else [],
            ),
        }
