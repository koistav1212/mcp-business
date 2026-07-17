import asyncio
import logging
from typing import Dict, Any

from services.core.models import ResearchExecutionPlan, ExecutionWave, ResearchTask
from services.agents.tool_router_agent import ToolRouterAgent
from services.knowledge.knowledge_router import KnowledgeRouter
from services.artifacts.artifact_writer import ArtifactWriter

logger = logging.getLogger("uvicorn.error")

class TaskScheduler:
    """
    Orchestrates the execution of a ResearchExecutionPlan.
    Reads execution waves, handles parallel execution, retries, and timeouts.
    """
    
    def __init__(self, knowledge_router: KnowledgeRouter):
        self.knowledge_router = knowledge_router

    async def execute(self, plan: ResearchExecutionPlan, entity_data: Dict[str, Any]) -> None:
        """
        Executes the provided research execution plan wave by wave.
        `entity_data` should contain the ResolvedCompany fields (like canonical_name, ticker, etc.)
        """
        logger.info(f"Scheduler starting execution of plan {plan.plan_id}")
        
        for wave in plan.execution_waves:
            logger.info(f"Executing {wave.name} (Wave {wave.wave_number})")
            
            wave_tasks = []
            for task in wave.tasks:
                # The task target_field tells us which field of the resolved entity to pass
                target_val = entity_data.get(task.target_field)
                if not target_val:
                    logger.warning(f"Task {task.task_id}: Target field '{task.target_field}' not found in entity data. Using full entity.")
                    target_val = entity_data

                wave_tasks.append(
                    self._execute_task_with_retries(task, target_val)
                )

            # Execute all tasks in this wave with pacing and concurrency limit of 2
            sem_wave = asyncio.Semaphore(2)
            async def run_task_paced(task_coro, index):
                await asyncio.sleep(index * 0.5)
                async with sem_wave:
                    return await task_coro
            
            paced_wave_tasks = [run_task_paced(t, i) for i, t in enumerate(wave_tasks)]
            results = await asyncio.gather(*paced_wave_tasks, return_exceptions=True)
            
            failed = False
            wave_results_dict = {}
            for task, res in zip(wave.tasks, results):
                if isinstance(res, Exception):
                    logger.error(f"Task {task.task_id} failed: {res}")
                    wave_results_dict[task.task_id] = {"error": str(res)}
                    if wave.stop_on_failure:
                        failed = True
                        break
                else:
                    wave_results_dict[task.task_id] = res

            ArtifactWriter.write_json(f"agent_outputs/wave_{wave.wave_number}_results.json", wave_results_dict)

            if failed:
                logger.error(f"Wave {wave.wave_number} failed and stop_on_failure is True. Aborting pipeline.")
                break

        logger.info(f"Scheduler completed execution of plan {plan.plan_id}")

    async def _execute_task_with_retries(self, task: ResearchTask, target: Any) -> Any:
        attempts = 0
        max_attempts = task.max_retries + 1
        
        while attempts < max_attempts:
            try:
                # Execute with timeout
                result = await asyncio.wait_for(
                    self.knowledge_router.execute_task(task, target),
                    timeout=task.timeout_seconds
                )
                return result
            except asyncio.TimeoutError:
                attempts += 1
                logger.warning(f"Task {task.task_id} timed out on attempt {attempts}")
                if attempts >= max_attempts and task.fallback_provider:
                    logger.info(f"Task {task.task_id} using fallback provider {task.fallback_provider}")
                    try:
                        fallback_task = ResearchTask(
                            task_id=f"{task.task_id}_fallback",
                            provider_name=task.fallback_provider,
                            target_field=task.target_field
                        )
                        return await asyncio.wait_for(
                            self.knowledge_router.execute_task(fallback_task, target),
                            timeout=task.timeout_seconds
                        )
                    except Exception as e:
                        logger.error(f"Task {task.task_id} fallback also failed: {e}")
                        raise e
            except Exception as e:
                attempts += 1
                logger.warning(f"Task {task.task_id} failed with error {e} on attempt {attempts}")
                if attempts >= max_attempts:
                    raise e
                    
        raise Exception(f"Task {task.task_id} exceeded max retries")
