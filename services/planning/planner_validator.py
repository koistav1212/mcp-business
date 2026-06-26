from .models import ExecutionPlan
import logging

logger = logging.getLogger("uvicorn.error")

class PlannerValidator:
    """
    Validates the execution plan to ensure it's structurally sound and ready for scheduling.
    """
    @classmethod
    def validate(cls, plan: ExecutionPlan) -> bool:
        if not plan.research_tasks:
            logger.error("Validation failed: No research tasks defined.")
            return False
            
        task_ids = {task.task_id for task in plan.research_tasks}
        
        has_entity_resolution = False
        
        for task in plan.research_tasks:
            # Check for unknown agents
            valid_agents = {"financial_agent", "competitor_agent", "industry_agent", "news_agent", "technology_agent", "risk_agent", "ai_agent", "strategy_agent", "entity_extractor"}
            if task.owner_agent not in valid_agents:
                logger.error(f"Validation failed: Unknown agent {task.owner_agent} in task {task.task_id}.")
                return False
                
            if task.owner_agent == "entity_extractor":
                has_entity_resolution = True
                
            # Check for missing dependencies
            for dep in task.dependencies:
                if dep not in task_ids:
                    logger.error(f"Validation failed: Task {task.task_id} depends on unknown task {dep}.")
                    return False
                    
            if task.estimated_tokens <= 0:
                logger.error(f"Validation failed: Task {task.task_id} has invalid token estimate.")
                return False
                
        if not has_entity_resolution:
            logger.error("Validation failed: No Entity Resolution task found in the plan.")
            return False

        # Check for circular dependencies
        if not cls._is_dag(plan):
            logger.error("Validation failed: Circular dependency detected in tasks.")
            return False
            
        return True

    @classmethod
    def _is_dag(cls, plan: ExecutionPlan) -> bool:
        graph = {task.task_id: task.dependencies for task in plan.research_tasks}
        visited = set()
        path = set()
        
        def visit(node):
            if node in path:
                return False
            if node in visited:
                return True
            path.add(node)
            for neighbor in graph.get(node, []):
                if not visit(neighbor):
                    return False
            path.remove(node)
            visited.add(node)
            return True
            
        for node in graph:
            if not visit(node):
                return False
        return True
