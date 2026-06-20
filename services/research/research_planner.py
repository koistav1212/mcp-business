from services.planning.research_planner import DynamicResearchPlanner
from services.research.models import IndustryContext, IntentPlan, ResearchPlan

class ResearchPlanner:
    """Selects only provider capabilities needed for the stated decision."""

    def plan(self, intent: IntentPlan, industry: IndustryContext) -> ResearchPlan:
        dynamic_planner = DynamicResearchPlanner()
        # Convert intent model to dict
        plan_dict = {
            "intent": intent.decision_type,
            "required_sources": intent.required_sources
        }
        tasks = dynamic_planner.plan(plan_dict)
        
        # Map task providers to actual orchestrator providers
        provider_map = {
            "company": "company_provider",
            "people": "people_provider",
            "web": "technology_provider",
            "sec": "sec_provider",
            "yfinance": "market_provider",
            "news": "news_provider",
            "reddit": "social_provider"
        }
        
        providers = []
        rationale = {}
        for t in tasks:
            short_p = t["provider"]
            full_p = provider_map.get(short_p)
            if full_p:
                providers.append(full_p)
                rationale[full_p] = f"dynamically selected for task: {t['task']}"
                
        # ensure default company and news provider are present if not already
        if "company_provider" not in providers:
            providers.insert(0, "company_provider")
            rationale["company_provider"] = "fallback resolve the target profile"
        if "news_provider" not in providers:
            providers.append("news_provider")
            rationale["news_provider"] = "fallback recent developments"
            
        provider_order = [
            "company_provider", "news_provider", "sec_provider", "market_provider",
            "people_provider", "technology_provider", "social_provider",
        ]
        unique_providers = list(dict.fromkeys(providers))

        return ResearchPlan(
            providers=[provider for provider in provider_order if provider in unique_providers],
            research_questions=[f"What evidence is required to support: {item}?" for item in intent.required_data],
            calculations=intent.required_calculations,
            rationale=rationale,
        )
