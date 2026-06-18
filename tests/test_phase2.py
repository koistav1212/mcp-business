import pytest
from fastapi.testclient import TestClient
from main import app
from registry.tool_registry import tool_registry, ToolRegistry
from registry.skill_registry import skill_registry, SkillRegistry
from core.router import AgentRouter
from tools.base import BaseTool
from pydantic import BaseModel
from typing import Optional, Type, Dict, Any

client = TestClient(app)

# Test custom mock tool
class MockToolInput(BaseModel):
    param: str

class MockTool(BaseTool):
    name: str = "mock_tool"
    description: str = "A mock tool for registry tests."
    args_schema: Optional[Type[BaseModel]] = MockToolInput

    async def execute(self, **kwargs) -> str:
        return f"result: {kwargs.get('param')}"

def test_tool_registry():
    reg = ToolRegistry()
    tool = MockTool()
    
    assert len(reg.list_tools()) == 0
    reg.register(tool)
    assert len(reg.list_tools()) == 1
    assert reg.get("mock_tool") == tool
    assert reg.list_tool_names() == ["mock_tool"]

def test_skill_registry_and_routing():
    # Make sure we have skills registered in global skill_registry
    skills = skill_registry.list_skills()
    assert len(skills) >= 1
    assert "sales-account-research" in skill_registry.list_skill_names()

    router = AgentRouter(skill_registry)
    
    # 1. Match query
    skill = router.route("Research Zoho corporation for tomorrow's call")
    assert skill is not None
    assert skill.name == "sales-account-research"

    # 2. No matching skill query
    no_skill = router.route("Order some pizza for lunch")
    assert no_skill is None

def test_api_skills_endpoint():
    response = client.get("/skills")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    names = [s["name"] for s in data]
    assert "sales-account-research" in names

def test_api_full_routed_execution_success():
    # 1. Create session with query for Zoho
    create_resp = client.post("/sessions", json={"query": "Research Zoho company"})
    assert create_resp.status_code == 200
    session_id = create_resp.json()["session_id"]

    # 2. Execute
    exec_resp = client.post(f"/sessions/{session_id}/execute")
    assert exec_resp.status_code == 200
    result = exec_resp.json()

    assert result["status"] == "completed"
    assert result["metadata"]["routed_skill"] == "sales-account-research"
    assert result["verification"]["is_valid"] is True
    
    response_text = result["response"]
    assert "Account Research: Zoho Corporation" in response_text
    assert "Chennai, India & Austin, Texas" in response_text
    assert "Zoho launches new AI-driven CRM tools" in response_text

def test_api_full_routed_execution_failure():
    # 1. Create session with unroutable query
    create_resp = client.post("/sessions", json={"query": "Make coffee"})
    assert create_resp.status_code == 200
    session_id = create_resp.json()["session_id"]

    # 2. Execute
    exec_resp = client.post(f"/sessions/{session_id}/execute")
    assert exec_resp.status_code == 200
    result = exec_resp.json()

    assert result["status"] == "failed"
    assert "Routing error: No skill found" in result["response"]
