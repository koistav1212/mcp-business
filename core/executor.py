import logging
from datetime import datetime, timezone
from typing import Dict, List, Any
from core.state import AgentState, AgentStep, AgentStatus
from core.exceptions import ToolExecutionException
from services.artifacts.artifact_writer import ArtifactWriter
from tools.base import BaseTool

logger = logging.getLogger(__name__)

class AgentExecutor:
    """
    Handles execution of the planner's ExecutionPlan step by step.
    Coordinates tool lookup, argument validation, and status updates.
    """
    def __init__(self, tools: List[BaseTool] = None):
        self.tools: Dict[str, BaseTool] = {}
        if tools:
            for tool in tools:
                self.register_tool(tool)

    def register_tool(self, tool: BaseTool):
        """Register a new tool instance in the executor."""
        self.tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")

    async def execute_step(self, step: AgentStep, state: AgentState) -> Any:
        """
        Executes a single step in the execution plan.
        Validates arguments against schema (if defined) and handles execution tracking.
        """
        if not step.tool_name:
            raise ToolExecutionException(f"Step {step.step_id} ({step.name}) has no tool name specified.")

        tool = self.tools.get(step.tool_name)
        if not tool:
            raise ToolExecutionException(f"Tool '{step.tool_name}' is not registered.")

        step.started_at = datetime.now(timezone.utc)
        step.status = "running"
        logger.info(f"Executing step {step.step_id} using tool: {step.tool_name}")

        try:
            inputs = step.tool_input or {}
            # If tool has args schema, validate input
            if tool.args_schema:
                validated_inputs = tool.args_schema(**inputs).model_dump()
            else:
                validated_inputs = inputs

            output = await tool.execute(**validated_inputs)
            step.tool_output = output
            step.status = "completed"
            
            # Save step output to artifacts
            ArtifactWriter.write_json(f"agent_outputs/step_{step.step_id}_{step.tool_name}_output.json", {"tool_name": step.tool_name, "output": output})
            
            return output
        except Exception as e:
            step.status = "failed"
            step.error = str(e)
            logger.error(f"Step {step.step_id} execution failed: {e}")
            ArtifactWriter.write_json(f"agent_outputs/step_{step.step_id}_{step.tool_name}_error.json", {"error": str(e)})
            raise ToolExecutionException(f"Failed to execute tool {step.tool_name}: {e}") from e
        finally:
            step.completed_at = datetime.now(timezone.utc)

    async def execute_plan(self, state: AgentState) -> AgentState:
        """
        Executes the entire execution plan stored in the state sequentially.
        """
        if not state.plan or not state.plan.steps:
            state.update_status(AgentStatus.FAILED)
            state.response = "No execution plan found to execute."
            return state

        state.update_status(AgentStatus.EXECUTING)
        
        # Save the plan to artifacts before executing
        ArtifactWriter.write_json("agent_outputs/execution_plan.json", state.plan.model_dump())
        
        for index, step in enumerate(state.plan.steps):
            if step.status == "completed":
                continue
            state.current_step_index = index
            
            # Save step input
            ArtifactWriter.write_json(f"agent_inputs/step_{step.step_id}_{step.tool_name}_input.json", {"tool_name": step.tool_name, "input": step.tool_input})
            
            try:
                await self.execute_step(step, state)
            except Exception as e:
                state.update_status(AgentStatus.FAILED)
                state.response = f"Execution failed at step {step.step_id} ({step.name}): {str(e)}"
                return state

        state.update_status(AgentStatus.VERIFYING)
        return state
