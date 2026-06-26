from .models import ExecutionPlan, ExecutionWave, DependencyGraph
import logging

logger = logging.getLogger("uvicorn.error")

class TaskScheduler:
    """
    Sorts tasks by priority, resolves dependencies, and groups them into parallel execution waves
    while strictly respecting Token-Per-Minute (TPM) limits.
    """
    MAX_TPM = 25000

    @classmethod
    def schedule(cls, plan: ExecutionPlan) -> ExecutionPlan:
        tasks_by_id = {task.task_id: task for task in plan.research_tasks}
        in_degree = {task.task_id: len(task.dependencies) for task in plan.research_tasks}
        
        adj = {task.task_id: [] for task in plan.research_tasks}
        for task in plan.research_tasks:
            for dep in task.dependencies:
                if dep in adj:
                    adj[dep].append(task.task_id)
                    
        plan.dependency_graph = DependencyGraph(nodes=tasks_by_id, edges=adj)
        
        waves = []
        wave_id = 1
        
        while in_degree:
            current_wave_ids = [tid for tid, deg in in_degree.items() if deg == 0]
            
            if not current_wave_ids:
                logger.error("Cycle detected during scheduling! Or isolated dependencies.")
                break
                
            priority_map = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
            current_wave_ids.sort(key=lambda tid: priority_map.get(tasks_by_id[tid].priority, 4))
            
            # Pack tasks into waves based on token limits
            current_wave_tasks = []
            current_wave_tokens = 0
            
            tasks_processed_in_this_step = []
            
            for tid in current_wave_ids:
                task = tasks_by_id[tid]
                task_tokens = task.estimated_tokens + getattr(task, 'max_completion_tokens', 1500)
                
                # If adding this task exceeds MAX_TPM and we already have tasks in the wave, 
                # we stop adding to this wave. (If it's the only task, we must add it anyway)
                if current_wave_tokens + task_tokens > cls.MAX_TPM and current_wave_tasks:
                    break
                    
                current_wave_tasks.append(task)
                current_wave_tokens += task_tokens
                tasks_processed_in_this_step.append(tid)

            waves.append(ExecutionWave(wave_id=wave_id, tasks=current_wave_tasks))
            
            # Remove processed tasks from in_degree and decrement dependents
            for tid in tasks_processed_in_this_step:
                del in_degree[tid]
                for dependent in adj[tid]:
                    if dependent in in_degree:
                        in_degree[dependent] -= 1
                        
            wave_id += 1
            
        plan.execution_waves = waves
        logger.info(f"Scheduled {len(waves)} execution waves for {len(plan.research_tasks)} tasks.")
        return plan
