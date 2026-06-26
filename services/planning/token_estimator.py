from .models import ExecutionPlan

class TokenEstimator:
    """
    Estimates tokens and costs for the execution plan to prevent budget blowouts.
    """
    COST_PER_1K_TOKENS = 0.002 # Arbitrary rough average for mix of input/output

    @classmethod
    def estimate(cls, plan: ExecutionPlan) -> ExecutionPlan:
        total_tokens = 0
        for task in plan.research_tasks:
            # Use hardcoded fallbacks if the LLM hallucinated weird numbers
            if task.estimated_tokens < 100:
                if "financial" in task.owner_agent:
                    task.estimated_tokens = 2000
                elif "competitor" in task.owner_agent:
                    task.estimated_tokens = 2000
                elif "news" in task.owner_agent:
                    task.estimated_tokens = 1500
                else:
                    task.estimated_tokens = 1000
                    
            total_tokens += task.estimated_tokens
            
        plan.estimated_tokens = total_tokens
        plan.estimated_cost = (total_tokens / 1000.0) * cls.COST_PER_1K_TOKENS
        
        return plan
