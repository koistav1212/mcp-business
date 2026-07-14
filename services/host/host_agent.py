import asyncio
import logging
import re
from typing import Dict, Any

from services.agents.planner_agent import PlannerAgent
from services.agents.tool_router_agent import ToolRouterAgent
from services.agents.critic_agent import CriticAgent
from services.ui.ui_agent import UIAgent
from services.agents.entity_extractor_agent import EntityExtractorAgent
from services.agents.synthesizer_agent import SynthesizerAgent
from services.intelligence.evidence_distiller import EvidenceDistiller

from services.planning.task_scheduler import TaskScheduler
from services.research.compressor import ResearchMemory
from services.research.models import (
    ResearchContext, EvidenceGraph, EvidenceNode, DraftReport, 
    CompanyProfile, FinancialData, EntityResolution, EntityCore, CriticResult
)
from services.analytics.financial_calculator import FinancialCalculator
from services.knowledge.evidence_store import EvidenceStore
from services.knowledge.knowledge_router import KnowledgeRouter
from services.artifacts.artifact_writer import ArtifactWriter

logger = logging.getLogger("uvicorn.error")

class HostAgent:
    @staticmethod
    def _extract_markdown_section(report_text: str, title: str) -> str:
        if not report_text:
            return ""
        pattern = rf"(?ims)^##\s+{re.escape(title)}\s*$\n(.*?)(?=^##\s+|\Z)"
        match = re.search(pattern, report_text)
        return match.group(1).strip() if match else ""

    @staticmethod
    def _extract_bullets(section_text: str) -> list[str]:
        if not section_text:
            return []
        bullets = []
        for line in section_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("- "):
                bullets.append(stripped[2:].strip())
        return bullets

    @staticmethod
    def _extract_domain(website: str) -> str:
        if not website: return None
        try:
            import urllib.parse
            if not website.startswith('http'): website = 'http://' + website
            parsed = urllib.parse.urlparse(website)
            host = parsed.netloc or parsed.path.split('/')[0]
            if host.startswith("www."): host = host[4:]
            return host
        except Exception:
            return None

    def __init__(self):
        self.entity_extractor = EntityExtractorAgent()
        self.planner = PlannerAgent()
        self.tool_router = ToolRouterAgent()
        self.synthesizer = SynthesizerAgent()
        self.critic = CriticAgent()
        self.ui_agent = UIAgent()

    async def run(self, query: str) -> Dict[str, Any]:
        ArtifactWriter.write_json("agent_inputs/session_query.json", {"query": query})
        
        # 0. Entity Extraction
        logger.info("START entity_extractor")
        company_entity = await self.entity_extractor.execute(query)
        if company_entity:
            ArtifactWriter.write_json("agent_outputs/entity_extractor.json", company_entity.model_dump() if hasattr(company_entity, "model_dump") else company_entity)
        
        # Build base entity data dictionary for the orchestrator
        entity_data = {}
        if company_entity:
            entity_data["canonical_name"] = getattr(company_entity, "company", query)
            entity_data["ticker"] = getattr(company_entity, "ticker", None)
            entity_data["cik"] = getattr(company_entity, "cik", None)
        else:
            entity_data["canonical_name"] = query

        # 1. Planning
        logger.info("START planner")
        plan = await self.planner.execute(query, company_entity)
        ArtifactWriter.write_json("agent_outputs/execution_plan.json", plan.model_dump() if hasattr(plan, "model_dump") else plan)
        
        # Determine target to pass down
        target = entity_data.get("canonical_name", query)

        # 2. Knowledge Layer Setup
        self.memory = ResearchMemory()
        evidence_store = EvidenceStore()
        knowledge_router = KnowledgeRouter(self.tool_router, evidence_store)
        scheduler = TaskScheduler(knowledge_router)
        
        # 3. Wave-based Agent Execution (via TaskScheduler)
        logger.info("START mcp_tools via TaskScheduler")
        # Prepopulate direct domains if the planner requires them
        for provider_name in plan.required_providers:
            await knowledge_router.get_evidence(provider_name, target)
            
        # Execute the formal execution plan
        await scheduler.execute(plan, entity_data)
        
        # Collect raw evidence from EvidenceStore to populate UI Context
        raw_context_dict = {}
        all_evidence = evidence_store.get_all()
        from services.knowledge.context_assembler.source_registry import resolve_domain
        
        for ev in all_evidence:
            domain = resolve_domain(ev.source)
            attr = ev.attribute
            val = ev.value
            
            # Map by domain
            if domain == "financial":
                if "financials" not in raw_context_dict:
                    raw_context_dict["financials"] = {}
                
                if attr == "income_statements" and isinstance(val, list):
                    rev_hist, ni_hist, op_hist = {}, {}, {}
                    for stmt in val:
                        year = str(stmt.get("calendarYear", stmt.get("date", "")[:4]))
                        if not year: continue
                        if "revenue" in stmt: rev_hist[year] = stmt["revenue"]
                        elif "totalRevenue" in stmt: rev_hist[year] = stmt["totalRevenue"]
                        if "netIncome" in stmt: ni_hist[year] = stmt["netIncome"]
                        if "operatingIncome" in stmt: op_hist[year] = stmt["operatingIncome"]
                    if rev_hist: raw_context_dict["financials"]["revenue_history"] = {"value": rev_hist, "source_ids": [ev.id], "confidence": ev.confidence}
                    if ni_hist: raw_context_dict["financials"]["net_income_history"] = {"value": ni_hist, "source_ids": [ev.id], "confidence": ev.confidence}
                    if op_hist: raw_context_dict["financials"]["operating_income_history"] = {"value": op_hist, "source_ids": [ev.id], "confidence": ev.confidence}
                elif attr == "balance_sheets" and isinstance(val, list):
                    ass_hist, liab_hist = {}, {}
                    for stmt in val:
                        year = str(stmt.get("calendarYear", stmt.get("date", "")[:4]))
                        if not year: continue
                        if "totalAssets" in stmt: ass_hist[year] = stmt["totalAssets"]
                        if "totalLiabilities" in stmt: liab_hist[year] = stmt["totalLiabilities"]
                    if ass_hist: raw_context_dict["financials"]["assets_history"] = {"value": ass_hist, "source_ids": [ev.id], "confidence": ev.confidence}
                    if liab_hist: raw_context_dict["financials"]["liabilities_history"] = {"value": liab_hist, "source_ids": [ev.id], "confidence": ev.confidence}
                elif attr == "cash_flow_statements" and isinstance(val, list):
                    cf_hist = {}
                    for stmt in val:
                        year = str(stmt.get("calendarYear", stmt.get("date", "")[:4]))
                        if not year: continue
                        if "freeCashFlow" in stmt: cf_hist[year] = stmt["freeCashFlow"]
                        elif "operatingCashFlow" in stmt: cf_hist[year] = stmt["operatingCashFlow"]
                    if cf_hist: raw_context_dict["financials"]["cash_flow_history"] = {"value": cf_hist, "source_ids": [ev.id], "confidence": ev.confidence}
                else:
                    if attr == "revenue_ttm":
                        raw_context_dict["financials"]["revenue_history"] = {"value": {"TTM": val}, "source_ids": [ev.id], "confidence": ev.confidence}
                        raw_context_dict["financials"]["revenue_annual"] = str(val)
                    elif attr == "net_income_ttm":
                        raw_context_dict["financials"]["net_income_history"] = {"value": {"TTM": val}, "source_ids": [ev.id], "confidence": ev.confidence}
                    elif attr == "ebitda_ttm":
                        raw_context_dict["financials"]["operating_income_history"] = {"value": {"TTM": val}, "source_ids": [ev.id], "confidence": ev.confidence}
                    elif attr == "free_cash_flow_ttm":
                        raw_context_dict["financials"]["cash_flow_history"] = {"value": {"TTM": val}, "source_ids": [ev.id], "confidence": ev.confidence}
                    
                    raw_context_dict["financials"][attr] = {
                        "value": val,
                        "source_ids": [ev.id],
                        "confidence": ev.confidence
                    }
                    
            elif domain == "news":
                if "news" not in raw_context_dict:
                    raw_context_dict["news"] = []
                if "risk_factors" not in raw_context_dict.setdefault("financials", {}):
                    raw_context_dict["financials"]["risk_factors"] = []
                    
                item = ev.value if isinstance(ev.value, dict) else {
                    "snippet": str(ev.value)
                }

                news_item = {
                    "title": item.get("headline") or item.get("title") or "",
                    "url": item.get("url") or ev.source_url or "",
                    "date": (
                        item.get("published_at")
                        or item.get("publishedAt")
                        or item.get("date")
                    ),
                    "snippet": (
                        item.get("summary")
                        or item.get("description")
                        or item.get("snippet")
                        or ""
                    ),
                    "type": (
                        item.get("signal_type")
                        or item.get("type")
                        or "general"
                    ),
                    "publisher": (
                        item.get("publisher")
                        or item.get("source")
                    ),
                }

                if news_item["title"]:
                    raw_context_dict["news"].append({
                        "value": news_item,
                        "source_ids": [ev.id],
                        "confidence": ev.confidence,
                    })

                # Extract risk themes from news
                text = f"{news_item['title']} {news_item['snippet']}".lower()
                if any(w in text for w in ["regulation", "risk", "lawsuit", "shortage", "decline", "challenge", "competitor"]):
                    raw_context_dict["financials"]["risk_factors"].append({
                        "value": f"Market/Regulatory News: {news_item['title']}",
                        "source_ids": [ev.id],
                        "confidence": ev.confidence
                    })

            elif domain == "profile":
                if "profile" not in raw_context_dict:
                    raw_context_dict["profile"] = {}
                    
                if attr == "competitors":
                    if isinstance(val, list):
                        raw_context_dict["competitors"] = [
                            {"value": peer, "source_ids": [ev.id], "confidence": ev.confidence}
                            for peer in val
                        ]
                elif attr == "leadership":
                    if isinstance(val, list):
                        raw_context_dict["leadership"] = [
                            {"value": leader, "source_ids": [ev.id], "confidence": ev.confidence}
                            for leader in val
                        ]
                elif attr in ["name", "overview"]:
                    existing = raw_context_dict["profile"].get(attr, "")
                    if len(str(val)) > len(str(existing)):
                        raw_context_dict["profile"][attr] = val
                elif attr == "founders":
                    if "founders" not in raw_context_dict["profile"]:
                        raw_context_dict["profile"]["founders"] = []
                    founders = val if isinstance(val, list) else [val]
                    for f in founders:
                        if f not in raw_context_dict["profile"]["founders"]:
                            raw_context_dict["profile"]["founders"].append(f)
                else:
                    raw_context_dict["profile"][attr] = {
                        "value": val,
                        "source_ids": [ev.id],
                        "confidence": ev.confidence
                    }
                    
            elif domain == "technology":
                if "technology_stack" not in raw_context_dict:
                    raw_context_dict["technology_stack"] = []
                raw_context_dict["technology_stack"].append({
                    "value": val,
                    "source_ids": [ev.id],
                    "confidence": ev.confidence
                })
                
            elif domain == "social":
                if "social" not in raw_context_dict:
                    raw_context_dict["social"] = {}
                raw_context_dict["social"][attr] = val
                
                # Extract risk factors from social complaints
                is_pain_attr = attr in ["pain_points", "customer_pain_points"] or "pain" in attr.lower()
                is_short_text = isinstance(val, str) and len(val) < 500
                if is_pain_attr or (is_short_text and ("pain" in val.lower() or "complain" in val.lower())):
                    if "risk_factors" not in raw_context_dict.setdefault("financials", {}):
                        raw_context_dict["financials"]["risk_factors"] = []
                    raw_context_dict["financials"]["risk_factors"].append({
                        "value": f"Customer Sentiment Risk: {val}",
                        "source_ids": [ev.id],
                        "confidence": ev.confidence
                    })
                    
            elif domain == "people":
                if "people" not in raw_context_dict:
                    raw_context_dict["people"] = {}
                raw_context_dict["people"][attr] = val
            else:
                raw_context_dict[attr] = val

            # --- ID Prefix Based Mapping ---
            parsed_val = val
            if isinstance(val, str):
                try:
                    import json
                    parsed_val = json.loads(val)
                except Exception:
                    try:
                        import ast
                        parsed_val = ast.literal_eval(val)
                    except Exception:
                        pass

            if ev.id.startswith("social_intel_"):
                if "market_sentiment" in ev.id or attr == "market_sentiment" or "intelligence_payload" in ev.id:
                    if "social_sentiment" not in raw_context_dict:
                        raw_context_dict["social_sentiment"] = {"value": {}, "source_ids": [], "confidence": ev.confidence}
                    
                    if isinstance(parsed_val, dict):
                        raw_context_dict["social_sentiment"]["value"].update(parsed_val)
                    else:
                        if "raw" not in raw_context_dict["social_sentiment"]["value"]:
                            raw_context_dict["social_sentiment"]["value"]["raw"] = []
                        raw_context_dict["social_sentiment"]["value"]["raw"].append(parsed_val)
                        
                    if ev.id not in raw_context_dict["social_sentiment"]["source_ids"]:
                        raw_context_dict["social_sentiment"]["source_ids"].append(ev.id)
                    raw_context_dict["social_sentiment"]["confidence"] = max(raw_context_dict["social_sentiment"]["confidence"], ev.confidence)
                        
                if "competitor" in ev.id or attr == "competitors":
                    if "competitors" not in raw_context_dict:
                        raw_context_dict["competitors"] = []
                    comps = parsed_val if isinstance(parsed_val, list) else [parsed_val]
                    for comp in comps:
                        raw_context_dict["competitors"].append({
                            "value": comp,
                            "source_ids": [ev.id],
                            "confidence": ev.confidence
                        })

                if "management_commentary" in ev.id or attr == "management_commentary":
                    if "financials" not in raw_context_dict:
                        raw_context_dict["financials"] = {}
                    if "mda_text" not in raw_context_dict["financials"]:
                        raw_context_dict["financials"]["mda_text"] = []
                    mcs = parsed_val if isinstance(parsed_val, list) else [parsed_val]
                    for mc in mcs:
                        raw_context_dict["financials"]["mda_text"].append(mc)



        analytics_data = FinancialCalculator.generate_analytics(raw_context_dict.get("financials", {}))

        evidence_graph = EvidenceGraph(nodes=[
            EvidenceNode(
                id=ev.id, 
                fact=str(ev.value)[:100], 
                confidence=ev.confidence,
                category=ev.attribute or "general"
            )
            for ev in all_evidence
        ])

        # Re-build fully populated ResearchContext to pass to Synthesizer and UIAgent
        entity_res = None
        if company_entity:
            # Safely get crawler data
            op_data = raw_context_dict.get("official_pages")
            sp_data = raw_context_dict.get("social_profiles")
            
            contact_data = raw_context_dict.get("contact")
            if isinstance(contact_data, str):
                contact_data = {"support_url": contact_data}

            entity_res = EntityResolution(
                entity=EntityCore(
                    name=getattr(company_entity, "company", target) or target,
                    ticker=getattr(company_entity, "ticker", None),
                    cik=getattr(company_entity, "cik", None),
                    exchange=getattr(company_entity, "exchange", None),
                    website=getattr(company_entity, "website", None),
                    industry=getattr(company_entity, "industry", None),
                    subindustry=getattr(company_entity, "subindustry", None),
                    country=getattr(company_entity, "country", None),
                    canonical_domain=HostAgent._extract_domain(getattr(company_entity, "website", None)),
                ),
                official_pages=op_data if isinstance(op_data, dict) else None,
                products=raw_context_dict.get("products", []),
                services=raw_context_dict.get("services", []),
                solutions=raw_context_dict.get("solutions") if isinstance(raw_context_dict.get("solutions"), dict) else None,
                social_profiles=sp_data if isinstance(sp_data, dict) else None,
                contact=contact_data,
                metadata={"confidence": getattr(company_entity, "confidence", 1.0)}
            )

        profile_data = raw_context_dict.get("profile", {})
        
        if entity_res and profile_data:
            core = entity_res.entity
            # Patch headquarters
            if not core.headquarters and profile_data.get("headquarters"):
                hq_val = profile_data["headquarters"]
                if isinstance(hq_val, dict):
                    hq_val = hq_val.get("value", "")
                
                if isinstance(hq_val, str) and hq_val:
                    parts = [p.strip() for p in hq_val.split(",")]
                    if len(parts) >= 3:
                        core.headquarters = {"city": parts[0], "state": parts[1], "country": parts[-1]}
                    elif len(parts) == 2:
                        core.headquarters = {"city": parts[0], "country": parts[1]}
                    elif len(parts) == 1:
                        core.headquarters = {"country": parts[0]}

            # Patch website
            if not core.website and profile_data.get("website"):
                web_val = profile_data["website"]
                if isinstance(web_val, dict):
                    core.website = web_val.get("value")
                elif isinstance(web_val, str):
                    core.website = web_val
                    
            # Patch industry (Optional but impactful)
            if not core.industry and profile_data.get("industry"):
                ind_val = profile_data["industry"]
                if isinstance(ind_val, dict):
                    core.industry = ind_val.get("value")
                elif isinstance(ind_val, str):
                    core.industry = ind_val

        profile_res = None
        if profile_data:
            profile_data_copy = profile_data.copy()
            hq = profile_data_copy.get("headquarters")
            emp = profile_data_copy.get("employee_count")
            if hq is not None and not isinstance(hq, dict):
                profile_data_copy["headquarters"] = {"value": hq}
            if emp is not None and not isinstance(emp, dict):
                profile_data_copy["employee_count"] = {"value": emp}
            profile_res = CompanyProfile(**profile_data_copy)

        tech_stack_raw = raw_context_dict.get("technology_stack", [])
        if not tech_stack_raw:
            tech_stack_raw = raw_context_dict.get("profile", {}).get("technology_stack", [])
        if isinstance(tech_stack_raw, dict):
            tech_stack_raw = tech_stack_raw.get("technologies", [])
            
        financial_data_res = None
        if raw_context_dict.get("financials"):
            # Ensure safe kwargs mapping
            financial_data_res = FinancialData(**raw_context_dict.get("financials", {}))

        hiring_signals_raw = raw_context_dict.get("people", {}).get("hiring_signals", {})
        hiring_signals_res = []
        if isinstance(hiring_signals_raw, dict):
            for t in hiring_signals_raw.get("sample_titles", []):
                hiring_signals_res.append({"role_title": t, "department": "General", "location": "Any"})

        logger.info(f"RAW CONTEXT DICT KEYS: {list(raw_context_dict.keys())}")
        if "financials" in raw_context_dict:
            logger.info(f"FINANCIALS KEYS: {list(raw_context_dict['financials'].keys())}")
        if "people" in raw_context_dict:
            logger.info(f"PEOPLE KEYS: {list(raw_context_dict['people'].keys())}")
        logger.info(f"RAW TECH STACK: {tech_stack_raw}")

        valuation_multiples_res = None
        capital_allocation_res = None
        if raw_context_dict.get("financials"):
            f = raw_context_dict["financials"]
            # Valuation Multiples
            val_mults = {}
            if "pe_ratio" in f:
                val_mults["pe_ratio"] = f["pe_ratio"].get("value") if isinstance(f["pe_ratio"], dict) else f["pe_ratio"]
            if "ev_ebitda" in f:
                val_mults["ev_ebitda"] = f["ev_ebitda"].get("value") if isinstance(f["ev_ebitda"], dict) else f["ev_ebitda"]
            if "ps_ratio" in f:
                val_mults["price_to_sales"] = f["ps_ratio"].get("value") if isinstance(f["ps_ratio"], dict) else f["ps_ratio"]
            if val_mults:
                from services.research.models import ValuationMultiples
                try: valuation_multiples_res = ValuationMultiples(**val_mults)
                except Exception: pass
            
            # Capital Allocation
            cap_alloc = {}
            if "buybacks_history" in f:
                cap_alloc["buybacks"] = f["buybacks_history"].get("value") if isinstance(f["buybacks_history"], dict) else f["buybacks_history"]
            if "dividends_history" in f:
                cap_alloc["dividends"] = f["dividends_history"].get("value") if isinstance(f["dividends_history"], dict) else f["dividends_history"]
            if "capex_history" in f:
                cap_alloc["capex_trend"] = f["capex_history"].get("value") if isinstance(f["capex_history"], dict) else f["capex_history"]
            if cap_alloc:
                from services.research.models import CapitalAllocation
                try: capital_allocation_res = CapitalAllocation(**cap_alloc)
                except Exception: pass

        industry_context_res = None
        if entity_res and entity_res.entity.industry:
            from services.research.models import IndustryContext
            industry_context_res = IndustryContext(industry=entity_res.entity.industry, sub_industry=entity_res.entity.subindustry)

        # Distill high-cardinality evidence
        entity_name_for_distillation = target
        if entity_res and entity_res.entity.name:
            entity_name_for_distillation = entity_res.entity.name
            
        raw_news = raw_context_dict.get("news", [])
        distilled_news = EvidenceDistiller.distill_news(raw_news, entity_name_for_distillation, max_items=10)
        
        raw_risk_factors = raw_context_dict.get("financials", {}).get("risk_factors", [])
        distilled_risks = EvidenceDistiller.distill_risks(raw_risk_factors, max_items=8)

        context_obj = ResearchContext(
            entity=entity_res,
            profile=profile_res,
            financials=financial_data_res,
            analytics=analytics_data,
            valuation_multiples=valuation_multiples_res,
            capital_allocation=capital_allocation_res,
            news=distilled_news,
            technology_stack=tech_stack_raw,
            leadership=raw_context_dict.get("leadership", []),
            hiring_signals=hiring_signals_res,
            competitors=raw_context_dict.get("competitors", []),
            competitive_positioning=raw_context_dict.get("competitive_positioning"),
            swot=raw_context_dict.get("swot"),
            risk_factors=distilled_risks,
            management_commentary=raw_context_dict.get("financials", {}).get("mda_text", []) if isinstance(raw_context_dict.get("financials", {}).get("mda_text", []), list) else [],
            industry_context=industry_context_res,
            evidence_graph=evidence_graph,
            social_sentiment=raw_context_dict.get("social_sentiment")
        )
        context_dict = context_obj.model_dump()

        # 4. Meta Synthesis
        logger.info("START synthesis")
        synthesis = await self.synthesizer.execute(plan, context_dict, target)
        
        synthesis_dump = synthesis.model_dump() if hasattr(synthesis, "model_dump") else (synthesis if isinstance(synthesis, dict) else getattr(synthesis, "__dict__", {}))
        ArtifactWriter.write_json("synthesis/synthesis_result.json", synthesis_dump)
        
        # 5. Review/Critique
        logger.info("START critic")
        planning_payload = plan.model_dump() if hasattr(plan, "model_dump") else {}
        if isinstance(synthesis_dump, dict) and synthesis_dump.get("report_critique"):
            critique = await self.critic.execute(synthesis_dump, planning_payload)
        else:
            critique = await self.critic.execute(synthesis_dump, planning_payload) if hasattr(self.critic, "execute") else None
        
        try:
            critique_dict = critique.model_dump() if critique else None
        except AttributeError:
            critique_dict = getattr(critique, '__dict__', str(critique)) if not isinstance(critique, dict) else critique

        if critique_dict:
            ArtifactWriter.write_json("critic/critic_result.json", critique_dict)

        if isinstance(synthesis, str):
            try:
                import json
                synthesis_dict = json.loads(synthesis)
            except Exception:
                synthesis_dict = {"executive_summary": synthesis, "key_findings": [], "risks": [], "opportunities": [], "recommendations": []}
        else:
            synthesis_dict = synthesis.model_dump() if hasattr(synthesis, "model_dump") else (synthesis if isinstance(synthesis, dict) else getattr(synthesis, "__dict__", {}))

        report_text = synthesis_dict.get("executive_summary", "")
        if report_text and isinstance(report_text, str):
            findings_section = self._extract_markdown_section(report_text, "Page 3 - Financial Performance")
            risk_section = self._extract_markdown_section(report_text, "Page 6 - Risks and Strategic Priorities")
            competition_section = self._extract_markdown_section(report_text, "Page 4 - Competitive Positioning")
            recommendations_section = self._extract_markdown_section(report_text, "Page 6 - Risks and Strategic Priorities")

            if not synthesis_dict.get("key_findings"):
                synthesis_dict["key_findings"] = self._extract_bullets(findings_section) or self._extract_bullets(competition_section)
            if not synthesis_dict.get("legacy_risks"):
                synthesis_dict["legacy_risks"] = self._extract_bullets(risk_section)
            if not synthesis_dict.get("recommendations"):
                bullets = self._extract_bullets(recommendations_section)
                if "### Strategic priorities" in recommendations_section:
                    bullets = self._extract_bullets(recommendations_section.split("### Strategic priorities", 1)[1])
                synthesis_dict["recommendations"] = bullets

        # Format strings to CitedInsight if needed
        for key in ["key_findings", "legacy_risks", "opportunities", "recommendations"]:
            if key in synthesis_dict:
                formatted_list = []
                for item in synthesis_dict[key]:
                    if isinstance(item, str):
                        formatted_list.append({"insight": item, "evidence_ids": []})
                    else:
                        formatted_list.append(item)
                synthesis_dict[key] = formatted_list
                
        # Append Synthesis into Context object before UIAgent
        context_obj.draft_report = DraftReport(**synthesis_dict)
        if critique_dict:
            context_obj.critique = CriticResult(**critique_dict)
        context_dict = context_obj.model_dump()

        # 6. UI Generation
        logger.info("START ui")
        ui = await self.ui_agent.execute(query, context_dict)
        ui_payload = ui.model_dump(mode="json") if hasattr(ui, "model_dump") else ui
        ArtifactWriter.write_json("ui/ui_response.json", ui_payload)
        
        final_result = {
            **context_dict,
            "context": synthesis_dict,
            "critique": critique_dict,
            "raw_research_context": context_dict,
            **ui_payload
        }
        
        ArtifactWriter.write_json("final/final_context.json", context_dict)
        ArtifactWriter.write_json("final/final_result.json", final_result)

        return final_result
