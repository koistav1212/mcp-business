import pytest
from fastapi.testclient import TestClient
from main import app
from core.config import settings
from core.exceptions import AgentException, ToolExecutionException
from core.state import AgentState, AgentStatus, ExecutionPlan, AgentStep
from core.executor import AgentExecutor
from tools.base import BaseTool
from typing import Optional, Type
from pydantic import BaseModel

client = TestClient(app)

# Define AddTool locally for core executor testing
class AddToolInput(BaseModel):
    a: float
    b: float

class AddTool(BaseTool):
    name: str = "add"
    description: str = "Adds two numbers together."
    args_schema: Optional[Type[BaseModel]] = AddToolInput

    async def execute(self, **kwargs) -> float:
        return kwargs["a"] + kwargs["b"]

def test_health_check():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["app_name"] == settings.APP_NAME
    assert data["status"] == "online"

def test_exceptions():
    with pytest.raises(AgentException) as excinfo:
        raise AgentException("General agent failure", {"context": "test"})
    assert excinfo.value.message == "General agent failure"
    assert excinfo.value.details == {"context": "test"}

    with pytest.raises(ToolExecutionException):
        raise ToolExecutionException("Failed to run tool")

def test_state_serialization():
    state = AgentState(
        session_id="test-session-123",
        query="Explain quantum computing"
    )
    assert state.session_id == "test-session-123"
    assert state.status == AgentStatus.PENDING
    assert len(state.history) == 0

    state.update_status(AgentStatus.PLANNING)
    assert state.status == AgentStatus.PLANNING

    state_dict = state.model_dump()
    state_reloaded = AgentState(**state_dict)
    assert state_reloaded.session_id == "test-session-123"
    assert state_reloaded.status == AgentStatus.PLANNING

@pytest.mark.asyncio
async def test_executor_with_add_tool():
    tool = AddTool()
    executor = AgentExecutor(tools=[tool])

    state = AgentState(
        session_id="test-session-456",
        query="Calculate things"
    )
    step = AgentStep(
        step_id=1,
        name="Calculate sum of 5 and 7",
        tool_name="add",
        tool_input={"a": 5.0, "b": 7.0}
    )
    state.plan = ExecutionPlan(steps=[step])

    updated_state = await executor.execute_plan(state)
    assert updated_state.status == AgentStatus.VERIFYING
    assert updated_state.plan.steps[0].status == "completed"
    assert updated_state.plan.steps[0].tool_output == 12.0

@pytest.mark.asyncio
async def test_executor_missing_tool():
    executor = AgentExecutor(tools=[])
    state = AgentState(
        session_id="test-session-789",
        query="Calculate things"
    )
    step = AgentStep(
        step_id=1,
        name="Calculate sum",
        tool_name="nonexistent_tool",
        tool_input={"a": 1.0}
    )
    state.plan = ExecutionPlan(steps=[step])

    updated_state = await executor.execute_plan(state)
    assert updated_state.status == AgentStatus.FAILED
    assert "not registered" in updated_state.response

def test_api_session_lifecycle():
    # 1. Create a session with Zoho query to match the registered skill
    create_response = client.post("/sessions", json={"query": "Research Zoho company"})
    assert create_response.status_code == 200
    session_data = create_response.json()
    session_id = session_data["session_id"]
    assert session_data["status"] == "pending"
    assert session_data["query"] == "Research Zoho company"

    # 2. Get the session status
    get_response = client.get(f"/sessions/{session_id}")
    assert get_response.status_code == 200
    assert get_response.json()["session_id"] == session_id

    # 3. Execute
    execute_response = client.post(f"/sessions/{session_id}/execute")
    assert execute_response.status_code == 200
    execution_result = execute_response.json()
    assert execution_result["status"] == "completed"
    assert execution_result["verification"]["is_valid"] is True
    assert "zoho" in execution_result["response"].lower()

def test_workspace_run_endpoint():
    response = client.post("/workspace/run", json={"company": "Zoho"})
    assert response.status_code == 200
    data = response.json()
    assert "company_profile" in data
    assert data["company_profile"]["name"] == "Zoho Corporation"
    assert "technology_stack" in data
    assert len(data["sources"]) > 0
