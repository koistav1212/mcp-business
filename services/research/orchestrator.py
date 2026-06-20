import asyncio
import random
import logging
from datetime import datetime
from typing import Optional
from services.research.models import RawResearchBundle, ResearchContext, AnalyticsData, Source

# Import Providers
from services.research.providers.entity_resolver import EntityResolver
from services.research.providers.sec_edgar_provider import SECEdgarProvider
from services.research.providers.yfinance_provider import YFinanceProvider
from services.research.providers.news_provider import NewsProvider
from services.research.providers.company_provider import CompanyProvider
from services.research.providers.web_provider import WebProvider
from services.research.providers.people_provider import PeopleProvider
from services.research.providers.reddit_provider import RedditProvider

# Import Synthesizer & Logic Layers
from services.research.synthesizer import ResearchSynthesizer
from services.research.analytics import AnalyticsCalculator
from services.research.verifier import EntityVerifier
from services.research.intent_engine import IntentEngine
from services.research.research_planner import ResearchPlanner
from services.research.industry_classifier import IndustryClassifier
from services.research.evidence_graph import EvidenceGraphBuilder
from services.research.report_planner import ReportPlanner
from services.research.llm_writer import LLMWriter
from services.research.critic_agent import CriticAgent
from services.research.json_llm import configured_json_generator


def generate_planned_business_report(context: ResearchContext):
    """Formats the planned, evidence-grounded draft for artifact tools."""
    report = context.draft_report
    plan = context.report_plan
    if not report or not plan:
        raise ValueError("A planned draft report is required before artifact generation")

    def render(items):
        return "\n".join(
            f"- {item.insight}" + (f" [{', '.join(item.evidence_ids)}]" if item.evidence_ids else "")
            for item in items
        ) or "Evidence is currently insufficient for this section."

    body = f"EXECUTIVE SUMMARY\n{report.executive_summary}\n\nKEY FINDINGS\n{render(report.key_findings)}"
    for heading, items in (("RISKS", report.risks), ("OPPORTUNITIES", report.opportunities), ("RECOMMENDATIONS", report.recommendations)):
        body += f"\n\n{heading}\n{render(items)}"
    if report.evidence_gaps:
        body += "\n\nEVIDENCE GAPS\n" + "\n".join(f"- {gap}" for gap in report.evidence_gaps)

    slides = [{"title": "Executive Summary", "points": [report.executive_summary]}]
    insight_by_id = {evidence_id: item.insight for item in report.key_findings for evidence_id in item.evidence_ids}
    for section in plan.sections:
        points = [insight_by_id[eid] for eid in section.evidence_ids if eid in insight_by_id][:4]
        slides.append({"title": section.title, "points": points or [f"Evidence gap: {section.objective}"]})
    return plan.title, body, plan.title, slides

def generate_dynamic_business_report(company: str, context: ResearchContext):
    frameworks = ["SWOT", "Porter's Five Forces", "McKinsey 7S"]
    chosen_framework = random.choice(frameworks)
    
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    company_name = context.profile.name
    hq = context.profile.headquarters.value if context.profile.headquarters else "Unknown"
    size = context.profile.employee_count.value if context.profile.employee_count else 0
    size_str = f"{size:,}" if size else "Unknown"
    website = context.profile.website
    
    financials_text = "N/A"
    if context.financials:
        financials_text = (
            f"Annual Revenue: {context.financials.revenue_annual} | "
            f"Funding Total: {context.financials.funding_total} | "
            f"Last Round: {context.financials.last_round}"
        )
    
    competitors_list = [c.name for c in context.competitors]
    competitors_str = ", ".join(competitors_list) if competitors_list else "industry peers"
    
    leaders_list = [f"{l.name} ({l.role})" for l in context.leadership]
    leaders_str = ", ".join(leaders_list) if leaders_list else "executive team"
    
    hiring_list = [f"{h.role_title} in {h.department} ({h.location})" for h in context.hiring_signals]
    hiring_str = "; ".join(hiring_list[:3]) if hiring_list else "talent expansion"
    
    tech_stack_str = ", ".join(context.technology_stack) if context.technology_stack else "modern tech stack"
    
    pdf_title = f"STRATEGIC ADVISORY DOSSIER: {company_name.upper()}"
    
    pdf_body = (
        f"CONFIDENTIAL STRATEGIC BRIEFING\n\n"
        f"Generated on: {now_str}\n"
        f"Target Enterprise: {company_name} ({website})\n"
        f"Corporate Headquarters: {hq}\n"
        f"Organization Scale: {size_str} employees\n"
        f"Strategic Assessment Framework: {chosen_framework} (Dynamic Analysis)\n\n"
        
        f"1. EXECUTIVE SUMMARY & CORPORATE POSITIONING\n"
        f"{company_name} operates as a key player in its market, driving digital capabilities and client value. "
        f"With an employee base of {size_str} and head offices situated in {hq}, the company has built "
        f"substantial domain expertise. Our intelligence indicators highlight active operational scaling and "
        f"strategic capability growth. Financially, the company's status is represented by: {financials_text}. "
        f"To maintain leadership against competitors like {competitors_str}, {company_name} must leverage its core "
        f"technological and talent capabilities while optimizing operational bottlenecks.\n\n"
    )
    
    if chosen_framework == "SWOT":
        pdf_body += (
            f"2. SWOT ANALYSIS FRAMEWORK\n"
            f"- Strengths: Deep domain integration, robust technology footprint utilizing {tech_stack_str}, "
            f"and established leadership directed by {leaders_str}. Operational agility allows rapid scaling in response to market shifts.\n"
            f"- Weaknesses: Intense hiring pressures and resource allocation latencies in high-demand roles, specifically for positions like {hiring_str}. "
            f"Capital consumption rates need structural optimization relative to annual yields.\n"
            f"- Opportunities: Integration of agentic AI execution pipelines to accelerate content compilation. "
            f"Unlocking developer productivity by automating routine API integrations and business research pipelines.\n"
            f"- Threats: Direct competitive advances from {competitors_str}. "
            f"Rapid wage inflation and recruitment bottlenecks in key tech nodes could constrain product delivery cycles.\n\n"
        )
    elif chosen_framework == "Porter's Five Forces":
        pdf_body += (
            f"2. PORTER'S FIVE FORCES INDUSTRY ANALYSIS\n"
            f"- Threat of New Entrants (Medium-Low): High capital and technology barriers to entry. "
            f"The sophistication of the {tech_stack_str} stack limits simple clone startups.\n"
            f"- Bargaining Power of Buyers (High): Enterprise clients demand customizable integration capabilities. "
            f"Clients have low switching costs if competitors like {competitors_str} offer superior financial terms.\n"
            f"- Bargaining Power of Suppliers (Medium): Highly dependent on top-tier engineering talent. "
            f"Active search profiles for {hiring_str} show continuous dependency on specialized labor markets.\n"
            f"- Threat of Substitutes (Low): Direct enterprise integrations have deep custom logic, making generic "
            f"out-of-the-box workarounds ineffective.\n"
            f"- Intensity of Competitive Rivalry (High): Aggressive feature racing and market share battles "
            f"among {competitors_str} require continuous R&D and aggressive outbound marketing.\n\n"
        )
    else:
        pdf_body += (
            f"2. MCKINSEY 7S STRATEGIC ALIGNMENT ANALYSIS\n"
            f"- Strategy: Maintain technological dominance using modern architectures. Defensive market positioning "
            f"against {competitors_str} while investing in AI and automation.\n"
            f"- Structure: Highly modular and autonomous divisions. Scale constraints are mitigated by outsourcing "
            f"and automating research/marketing pipelines.\n"
            f"- Systems: Core infrastructure runs on {tech_stack_str}. Critical engineering pipelines are supplemented "
            f"by active hiring campaigns ({hiring_str}).\n"
            f"- Shared Values: Innovation-first engineering culture with a strong emphasis on speed-to-market and high trust.\n"
            f"- Staff: Diverse global workforce. Management must focus on reducing engineering burnout and accelerating onboarding.\n"
            f"- Style: Consultative, decentralized decision-making led by key executives including {leaders_str}.\n"
            f"- Skills: High competency in full-stack software development, custom database integrations, and client engagement.\n\n"
        )
        
    pdf_body += (
        f"3. FINANCIAL PROFILE & CAPITAL ALLOCATION\n"
        f"Our research compiled the following indicators from public reports: {financials_text}. "
        f"We detect high alignment between capital allocation and modern technological modernization. "
        f"Cash flows indicate substantial runway, though competitive developments may require accelerated product development cycles.\n\n"
        
        f"4. ADVISORY & RECRUITMENT SYNERGY\n"
        f"Based on active signals, {company_name} is actively expanding its organization: {hiring_str}. "
        f"To optimize these hiring campaigns, we recommend implementing automated candidate screening and "
        f"outreach templates. The primary target audience should be led by key decision makers in product and HR. "
        f"Furthermore, integrating specialized training programs will reduce onboarding overheads by 35%.\n\n"
        
        f"5. STRATEGIC GROWTH RECOMMENDATIONS\n"
        f"- Recommendation 1: Deploy autonomous research agent loops to compile competitor intelligence dynamically, "
        f"negating static market research latency.\n"
        f"- Recommendation 2: Partner with specialized API platforms to optimize high-volume developer vetting processes.\n"
        f"- Recommendation 3: Streamline outbound customer outreach by integrating custom email sequences directed "
        f"towards buyer personas like CHROs and VP of Engineering profiles."
    )
    
    ppt_title = f"{company_name.upper()} CASE COMP DECK"
    
    slides = [
        {
            "title": f"Strategic Analysis: {company_name}",
            "points": [
                f"Headquarters: {hq}",
                f"Scale: {size_str} Employees",
                f"Analysis Framework: {chosen_framework} (Consulting Case Format)",
                f"Brief Date: {now_str}"
              ]
        },
        {
            "title": "Executive Summary & Positioning",
            "points": [
                f"Market Leader battling against rivals: {competitors_str}",
                f"Financial health: {financials_text}",
                "Key Challenge: Recruitment latencies and developer screening bottlenecks",
                "Opportunity: Build AI-assisted operational workflows to double efficiency"
            ]
        }
    ]
    
    if chosen_framework == "SWOT":
        slides.append({
            "title": f"{company_name} SWOT Matrix",
            "points": [
                f"Strengths: Core stack ({tech_stack_str}) and leadership under {leaders_str}",
                f"Weaknesses: High staffing pressure visible via recruitment targets: {hiring_str}",
                "Opportunities: Operational automation using agentic task planners",
                f"Threats: Feature replication by competitors: {competitors_str}"
            ]
        })
    elif chosen_framework == "Porter's Five Forces":
        slides.append({
            "title": "Industry Forces Map (Porter's)",
            "points": [
                f"Rivalry: High competition with {competitors_str}",
                f"Buyers: High power demanding integrations with {tech_stack_str}",
                f"Suppliers: Medium-high pressure due to engineering hiring requirements: {hiring_str}",
                "Threats of Entry: Low due to complex codebase and registry standards"
            ]
        })
    else:
        slides.append({
            "title": "McKinsey 7S Framework Status",
            "points": [
                f"Strategy: Technological differentiation from {competitors_str}",
                f"Systems: Infrastructure built around {tech_stack_str}",
                f"Staff/Skills: High engineering talent demand for {hiring_str}",
                f"Style: Leadership driven by {leaders_str}"
            ]
        })
        
    slides.extend([
        {
            "title": "Financial Performance Analysis",
            "points": [
                f"Annual Revenue Indicator: {context.financials.revenue_annual if context.financials else 'N/A'}",
                f"Total Funding: {context.financials.funding_total if context.financials else 'N/A'}",
                f"Last Seed/Round: {context.financials.last_round if context.financials else 'N/A'}",
                "Capital efficiency metrics suggest stable cash flows with expansion capacity"
            ]
        },
        {
            "title": "Strategic Advisory Recommendations",
            "points": [
                "1. Integrate assessment APIs to speed up engineering vetting pipelines",
                "2. Standardize outreach campaigns with McKinsey/consulting level templates",
                "3. Optimize operational workflows using automated multi-agent research tools"
            ]
        }
    ])
    
    return pdf_title, pdf_body, ppt_title, slides

class ResearchOrchestrator:
    """
    Central coordinator for the Business Intelligence Layer.
    Orchestrates the resolution, provider sourcing, synthesis, and verification loops.
    """
    def __init__(self, json_generator=None):
        self.entity_resolver = EntityResolver()
        self.sec_provider = SECEdgarProvider()
        self.yfinance_provider = YFinanceProvider()
        self.news_provider = NewsProvider()
        self.company_provider = CompanyProvider()
        self.web_provider = WebProvider()
        self.people_provider = PeopleProvider()
        self.reddit_provider = RedditProvider()
        self.synthesizer = ResearchSynthesizer()
        self.analytics_calculator = AnalyticsCalculator()
        self.verifier = EntityVerifier()
        json_generator = json_generator or configured_json_generator()
        self.intent_engine = IntentEngine(json_generator=json_generator)
        self.industry_classifier = IndustryClassifier()
        self.research_planner = ResearchPlanner()
        self.evidence_builder = EvidenceGraphBuilder()
        self.report_planner = ReportPlanner()
        self.writer = LLMWriter(json_generator=json_generator)
        self.critic = CriticAgent()

    async def run(self, company: Optional[str] = None, generate_reports: bool = False, user_query: str = None) -> ResearchContext:
        """
        Runs the full intelligence research pipeline.
        Resolves candidates -> Fetches metrics concurrently -> Synthesizes -> Analytics -> Verifies.
        Retries on alternate candidates if verification fails.
        """
        logger = logging.getLogger("uvicorn.error")
        
        original_request = user_query or f"Research {company}"
        intent = await self.intent_engine.extract(original_request, entity_hint=company)
        if not company:
            company = intent.entities[0] if intent.entities else None
        if not company:
            return {
                "status": "needs_clarification",
                "query": original_request,
                "message": "No company could be identified in the request.",
                "closest_candidates": [],
                "confidence": 0.0,
            }
        industry = self.industry_classifier.classify(intent)
        research_plan = self.research_planner.plan(intent, industry)

        # 1. Resolve entity candidates
        candidates = await self.entity_resolver.get_candidates(company)
        
        # Entity Confidence Gate
        candidate_count = len(candidates)
        auto_resolve = False
        
        if candidate_count > 0:
            top = candidates[0]
            if top.confidence > 0.85:
                auto_resolve = True
            elif candidate_count > 1:
                second = candidates[1]
                if top.confidence > second.confidence + 0.2:
                    auto_resolve = True
            elif candidate_count == 1:
                if top.confidence > 0.6:
                    auto_resolve = True
                    
        if not auto_resolve:
            closest = await self.entity_resolver.get_closest_candidates(company)
            return {
                "status": "needs_clarification",
                "query": company,
                "message": "No company matched this name with sufficient confidence.",
                "closest_candidates": closest,
                "confidence": candidates[0].confidence if candidates else 0.0
            }
            
        final_context = None
        
        # 2. Iterate and verify candidates
        for idx, candidate in enumerate(candidates):
            logger.info(f"Trying research candidate [{idx+1}/{len(candidates)}]: {candidate.company_name} ({candidate.ticker})")
            
            provider_calls = {
                "sec_provider": lambda: self.sec_provider.fetch(candidate.cik),
                "market_provider": lambda: self.yfinance_provider.fetch(candidate.ticker),
                "news_provider": lambda: self.news_provider.fetch(candidate.company_name),
                "company_provider": lambda: self.company_provider.fetch(candidate.company_name),
                "technology_provider": lambda: self.web_provider.fetch(candidate.company_name),
                "people_provider": lambda: self.people_provider.fetch(candidate.company_name),
                "social_provider": lambda: self.reddit_provider.fetch(candidate.company_name),
            }
            selected = [name for name in research_plan.providers if name in provider_calls]
            results = await asyncio.gather(*(provider_calls[name]() for name in selected))
            provider_results = dict(zip(selected, results))
            sec_results = provider_results.get("sec_provider", {"revenue_history": {}, "net_income_history": {}, "operating_income_history": {}, "assets_history": {}, "liabilities_history": {}, "cash_flow_history": {}, "shares_outstanding_history": {}, "raw_data": {}})
            yf_results = provider_results.get("market_provider", {"raw_data": {}})
            news_results = provider_results.get("news_provider", {"news": [], "raw_data": {}})
            company_results = provider_results.get("company_provider", {"name": candidate.company_name, "raw_data": {}})
            web_results = provider_results.get("technology_provider", {"technology_stack": [], "raw_data": {}})
            people_results = provider_results.get("people_provider", {"leadership": [], "hiring_signals": [], "raw_data": {}})
            reddit_results = provider_results.get("social_provider", {"raw_data": {}})
            
            # Add revenue_annual formatted string for FinancialData compatibility
            revenue_history = sec_results.get("revenue_history", {})
            rev_annual_formatted = "N/A"
            if revenue_history:
                sorted_dates = sorted(revenue_history.keys(), reverse=True)
                latest_val = revenue_history[sorted_dates[0]]
                if latest_val:
                    rev_annual_formatted = f"${latest_val / 1e9:.1f}B"
                    
            sec_results["revenue_annual"] = rev_annual_formatted
            
            # Build intermediate raw research bundle
            bundle = RawResearchBundle(
                company_raw=company_results,
                web_raw=web_results,
                news_raw=news_results,
                financial_raw={"financial_reports": [sec_results]},
                people_raw=people_results
            )
            
            # Synthesize into unified context
            context = await self.synthesizer.synthesize(
                bundle=bundle,
                entity=candidate,
                sec_data=sec_results,
                yf_data=yf_results,
                reddit_data=reddit_results
            )
            
            # Compute Python analytics
            analytics_metrics = self.analytics_calculator.calculate(sec_results, yf_results)
            context.analytics = AnalyticsData(**analytics_metrics)
            if "market_provider" in provider_results:
                context.sources.append(Source(
                    title="Yahoo Finance Market Data",
                    url=f"https://finance.yahoo.com/quote/{candidate.ticker}",
                    source_type="market_data",
                ))
            
            # Verify candidates
            is_valid, explanation = self.verifier.verify(context)
            logger.info(explanation)
            
            if is_valid or idx == len(candidates) - 1:
                # If valid, or we reached the last candidate, select it
                final_context = context
                if is_valid:
                    break

        if final_context:
            industry = self.industry_classifier.classify(intent, final_context.profile.overview)
            intent.industry_focus = industry.industry
            evidence = self.evidence_builder.build(final_context, intent.required_data)
            report_plan = self.report_planner.plan(intent, industry, evidence)
            draft = await self.writer.write(intent, research_plan, industry, evidence, report_plan)
            critique = self.critic.review(original_request, intent, research_plan, evidence, report_plan, draft)
            final_context.intent = intent
            final_context.research_plan = research_plan
            final_context.industry_context = industry
            final_context.evidence_graph = evidence
            final_context.report_plan = report_plan
            final_context.draft_report = draft
            final_context.critique = critique
                    
        # 3. Deliver reports (if configured)
        if final_context and generate_reports:
            try:
                from tools.create_pdf import CreatePDFTool
                from tools.create_ppt import CreatePPTTool
                
                pdf_title, pdf_body, ppt_title, slides = generate_planned_business_report(final_context)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                pdf_filename = f"{company.lower().replace(' ', '_')}_report_{timestamp}.pdf"
                ppt_filename = f"{company.lower().replace(' ', '_')}_deck_{timestamp}.pptx"
                
                pdf_tool = CreatePDFTool()
                ppt_tool = CreatePPTTool()
                
                pdf_url = await pdf_tool.execute(
                    filename=pdf_filename,
                    title=pdf_title,
                    body_text=pdf_body
                )
                
                ppt_url = await ppt_tool.execute(
                    filename=ppt_filename,
                    presentation_title=ppt_title,
                    slides=slides
                )
                
                final_context.pdf_url = pdf_url
                final_context.ppt_url = ppt_url
            except Exception as e:
                logger.warning(f"Failed to generate dynamic deliverables PDF/PPT: {e}")
                
        if final_context:
            final_context = filter_context_by_intent(final_context)
        return final_context

def filter_context_by_intent(context: ResearchContext) -> ResearchContext:
    if not context or not context.intent:
        return context
    
    required_data = context.intent.required_data
    field_map = {
        "company profile": ["profile", "company_profile", "competitors", "competitive_positioning", "swot", "risk_factors", "management_commentary"],
        "financial history": ["financials", "analytics", "capital_allocation"],
        "market valuation": ["financials", "analytics", "valuation_multiples"],
        "recent developments": ["news"],
        "leadership": ["leadership"],
        "hiring signals": ["hiring_signals"],
        "technology stack": ["technology_stack"],
        "competitive positioning": ["competitors", "competitive_positioning"],
        "swot": ["swot"],
        "risk factors": ["risk_factors"],
        "management commentary": ["management_commentary"],
    }
    
    keep_keys = set()
    for req in required_data:
        req_clean = req.lower().strip()
        if req_clean in field_map:
            keep_keys.update(field_map[req_clean])
            
    all_filterable = [
        "profile", "company_profile", "financials", "analytics", "news", 
        "leadership", "competitors", "hiring_signals", "technology_stack", 
        "social_sentiment", "competitive_positioning", "swot", 
        "valuation_multiples", "risk_factors", "capital_allocation", 
        "management_commentary"
    ]
    
    for key in all_filterable:
        if key not in keep_keys:
            setattr(context, key, None)
            
    return context
