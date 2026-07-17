import logging
from typing import Any, List, Dict

logger = logging.getLogger("uvicorn.error")

class EvidenceGraphBuilder:
    """
    Programmatically builds a structured Evidence Graph from all fetched provider evidence.
    No LLM is used. Splits the normalized evidence into 8 distinct domains.
    """

    def build(self, raw_evidence: List[Any], entity_name: str) -> Dict[str, Any]:
        graph = {
            "financial": {
                "entity": {"name": entity_name},
                "income_statement": {},
                "balance_sheet": {},
                "cash_flow": {},
                "earnings": {},
                "guidance": {},
                "valuation": {},
                "analyst_estimates": {},
                "financial_news": [],
                "recent_events": [],
                "market_metrics": {}
            },
            "technology": {
                "github": {},
                "patents": {},
                "engineering_jobs": {},
                "developer_docs": {},
                "tech_news": {},
                "opensource": {},
                "security": {},
                "architecture": {}
            },
            "operations": {
                "supply_chain": {},
                "manufacturing": {},
                "logistics": {},
                "warehouses": {},
                "capacity": {},
                "vendors": {},
                "expansion": {},
                "operations_news": {}
            },
            "social": {
                "reddit": [],
                "x": [],
                "youtube": [],
                "forums": [],
                "reviews": [],
                "trustpilot": [],
                "playstore": [],
                "appstore": []
            },
            "products": {
                "portfolio": [],
                "launches": [],
                "pricing": [],
                "market_share": [],
                "roadmap": [],
                "customer_segments": [],
                "sales": []
            },
            "competition": {
                "competitors": [],
                "pricing": [],
                "market_share": [],
                "products": [],
                "feature_matrix": [],
                "analyst_reports": [],
                "news": []
            },
            "leadership": {
                "executives": [],
                "board": [],
                "compensation": {},
                "management_commentary": {}
            },
            "risk": {
                "legal": {},
                "cyber": {},
                "regulatory": {},
                "macro": {},
                "geopolitical": {},
                "supply_chain": {},
                "financial": {},
                "technology": {}
            }
        }

        for ev in raw_evidence:
            attr = getattr(ev, "attribute", "").lower()
            val = getattr(ev, "value", None)
            source = getattr(ev, "source", "").lower()
            source_id = getattr(ev, "source_id", "")
            url = getattr(ev, "source_url", getattr(ev, "url", ""))

            if val is None or val in ("", [], {}):
                continue

            def _inject(item):
                if isinstance(item, dict):
                    item["source_id"] = source_id
                    item["url"] = url
                    return item
                return {"data": item, "source_id": source_id, "url": url}

            # Route based on source name or attribute
            if source in ("sec_edgar", "sec", "sec_provider") or attr in ("income_statement", "balance_sheet", "cash_flow", "revenue_history", "net_income_history", "cash_flow_history", "buybacks_history"):
                injected_val = _inject(val)
                if "income" in attr or "revenue" in attr:
                    graph["financial"]["income_statement"][attr] = injected_val
                elif "balance" in attr or "equity" in attr or "asset" in attr or "liab" in attr or "debt" in attr:
                    graph["financial"]["balance_sheet"][attr] = injected_val
                elif "cash" in attr or "buyback" in attr or "dividend" in attr or "capex" in attr:
                    graph["financial"]["cash_flow"][attr] = injected_val
                else:
                    graph["financial"]["earnings"][attr] = injected_val

            elif source in ("yfinance", "global_markets") or attr in ("market_cap", "pe_ratio", "current_price", "valuation_multiples"):
                injected_val = _inject(val)
                if attr == "market_cap":
                    graph["financial"]["market_metrics"]["market_cap"] = injected_val
                else:
                    graph["financial"]["valuation"][attr] = injected_val
                    graph["financial"]["market_metrics"][attr] = injected_val

            elif attr == "technology_stack" or source in ("github", "git") or "repo" in attr or "language" in attr or "contributor" in attr:
                injected_val = _inject(val)
                if "repo" in attr or "contributor" in attr or "language" in attr:
                    graph["technology"]["github"][attr] = injected_val
                else:
                    graph["technology"]["opensource"]["stack"] = injected_val

            elif "patent" in attr:
                graph["technology"]["patents"][attr] = _inject(val)

            elif attr in ("hiring_signals", "open_roles_by_dept") or "job" in attr:
                graph["technology"]["engineering_jobs"][attr] = _inject(val)

            elif "reddit" in source or "social" in source or attr == "social_sentiment":
                posts = val if isinstance(val, list) else [val]
                for p in posts:
                    graph["social"]["reddit"].append(_inject(p))

            elif "competitor" in attr or "competition" in attr or source == "competitors":
                comps = val if isinstance(val, list) else [val]
                for c in comps:
                    graph["competition"]["competitors"].append(_inject(c))

            elif attr in ("leadership", "executives", "founders") or "people" in source:
                execs = val if isinstance(val, list) else [val]
                for e in execs:
                    graph["leadership"]["executives"].append(_inject(e))

            elif "risk" in attr or "legal" in attr or "regulatory" in attr or "cyber" in attr:
                injected_val = _inject(val)
                if "regulatory" in attr:
                    graph["risk"]["regulatory"][attr] = injected_val
                elif "legal" in attr:
                    graph["risk"]["legal"][attr] = injected_val
                else:
                    graph["risk"]["cyber"][attr] = injected_val

            elif attr == "website_intelligence" or source == "company_website":
                injected_val = _inject(val)
                graph["operations"]["website_data"] = injected_val
                graph["products"]["website_data"] = injected_val
                graph["technology"]["website_data"] = injected_val

            elif "news" in source or attr in ("news", "articles", "recent_developments"):
                articles = val.get("articles", []) if isinstance(val, dict) else (val if isinstance(val, list) else [val])
                for art in articles:
                    if not isinstance(art, dict):
                        doc = {"headline": str(art), "summary": "", "timestamp": "", "url": url, "source_id": source_id}
                        category = ""
                    else:
                        doc = {
                            "headline": art.get("headline", art.get("title", "")),
                            "summary": art.get("summary", art.get("snippet", "")),
                            "timestamp": art.get("date", art.get("timestamp", "")),
                            "url": art.get("url", url),
                            "source_id": art.get("source_id", source_id)
                        }
                        category = art.get("category", "").lower()

                    if "finance" in category or "earn" in category or "stock" in category:
                        graph["financial"]["financial_news"].append(doc)
                    elif "tech" in category or "patent" in category or "github" in category:
                        graph["technology"]["tech_news"].append(doc)
                    elif "oper" in category or "supply" in category or "ship" in category or "logis" in category:
                        graph["operations"]["operations_news"].append(doc)
                    else:
                        graph["competition"]["news"].append(doc)

            elif "supply" in attr or "logistics" in attr or "manufacturing" in attr or "warehouse" in attr:
                graph["operations"]["supply_chain"][attr] = _inject(val)

            elif "product" in attr or "portfolio" in attr or "pricing" in attr:
                graph["products"]["portfolio"].append(_inject(val))

            else:
                # Catch-all fallback routing
                if "financial" in attr:
                    graph["financial"]["earnings"][attr] = _inject(val)
                elif "tech" in attr:
                    graph["technology"]["architecture"][attr] = _inject(val)
                else:
                    graph["risk"]["financial"][attr] = _inject(val)

        return graph
