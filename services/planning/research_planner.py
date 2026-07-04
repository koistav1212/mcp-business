from typing import Any, Dict, List

class DynamicResearchPlanner:
    """
    Converts intent and planning configuration into a concrete sequence of research tasks.
    Each task is paired with a designated data provider.
    """
    
    # Predefined tasks for specific sources to ensure standard mappings
    SOURCE_TASK_MAP = {
        "sec": {"task": "financial_history", "provider": "sec_edgar"},
        "yfinance": {"task": "market_valuation", "provider": "yfinance"},
        "news": {"task": "recent_developments", "provider": "news_provider"},
        "reddit": {"task": "social_sentiment", "provider": "reddit_provider"},
        "company": {"task": "company_profile", "provider": "company_provider"},
        "people": {"task": "leadership", "provider": "people_provider"},
        "hiring": {"task": "hiring_signals", "provider": "people_provider"},
        "competitors": {"task": "competitor_mapping", "provider": "web_provider"},
        "web": {"task": "web_research", "provider": "web_provider"}
    }
    
    def plan(self, plan_data: Any, company_entity: Any = None) -> List[Dict[str, str]]:
        """
        Translates intent/plan into a list of tasks.
        Accepts a dictionary, string, or Pydantic model representation of the plan.
        Optionally takes company_entity for dynamic routing.
        """
        intent = ""
        required_sources = []
        
        if isinstance(plan_data, str):
            intent = plan_data
        elif isinstance(plan_data, dict):
            intent = plan_data.get("intent", "")
            required_sources = plan_data.get("required_sources", [])
        elif hasattr(plan_data, "intent"):
            intent = getattr(plan_data, "intent", "")
            required_sources = getattr(plan_data, "required_sources", [])
            if callable(required_sources):
                required_sources = required_sources()
        
        intent_clean = intent.lower().strip()
        
        # If it's a known intent and we don't have required_sources, use pre-defined defaults
        if intent_clean == "sales_strategy" and not required_sources:
            return [
                {"task": "company_profile", "provider": "company_provider"},
                {"task": "leadership", "provider": "people_provider"},
                {"task": "hiring_signals", "provider": "people_provider"},
                {"task": "competitor_mapping", "provider": "web_provider"}
            ]
            
        # Dynamically build plan based on required_sources
        tasks = []
        
        # Always default to company_profile if not explicitly defined
        if "company" not in required_sources:
            tasks.append({"task": "company_profile", "provider": "company_provider"})
            
        for src in required_sources:
            src_clean = src.lower().strip()
            
            # Dynamic routing for financial data based on entity
            if src_clean in ["sec", "financials"]:
                if company_entity and getattr(company_entity, "cik", None):
                    tasks.append({"task": "financial_history", "provider": "sec_edgar"})
                elif company_entity and getattr(company_entity, "ticker", None) and getattr(company_entity, "exchange", None):
                    tasks.append({"task": "financial_history", "provider": "global_markets"})
                else:
                    # Fallback for private companies
                    tasks.append({"task": "financial_history", "provider": "company_provider"})
                    tasks.append({"task": "recent_developments", "provider": "news_provider"})
                continue
                
            if src_clean in self.SOURCE_TASK_MAP:
                task_def = self.SOURCE_TASK_MAP[src_clean]
                # Avoid duplicates
                if (task_def["task"], task_def["provider"]) not in [(t["task"], t["provider"]) for t in tasks]:
                    tasks.append(task_def)
                    
        # Fallback if no tasks resolved
        if not tasks:
            tasks = [
                {"task": "company_profile", "provider": "company_provider"},
                {"task": "recent_developments", "provider": "news_provider"}
            ]
            
        return tasks
