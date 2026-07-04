import os
import uuid
from typing import Dict, List, Optional, Type
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.config import settings
from core.state import AgentState, AgentStatus, ExecutionPlan, AgentStep, VerificationResult
from core.executor import AgentExecutor
from core.router import AgentRouter
from registry.tool_registry import tool_registry
from registry.skill_registry import skill_registry
from services.artifacts.artifact_writer import ArtifactWriter

# Import tools
from tools.search_company import SearchCompanyTool
from tools.search_web import SearchWebTool
from tools.create_pdf import CreatePDFTool
from tools.create_ppt import CreatePPTTool
from tools.create_docs import CreateDocsTool
from tools.send_email import SendEmailTool

# Import skills
from skills.sales_account_research.skill import SalesAccountResearchSkill
from skills.proposal_writer.skill import ProposalWriterSkill

from fastapi.middleware.cors import CORSMiddleware
from api.routes import router as workspace_router

app = FastAPI(
    title=settings.APP_NAME,
    description="Reusable Enterprise AI Agent Framework REST API",
    version="0.3.0",
    debug=settings.DEBUG
)

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the workspace router
app.include_router(workspace_router)

# Serve generated PDFs and PPTs statically
os.makedirs("artifacts", exist_ok=True)
app.mount("/static", StaticFiles(directory="artifacts"), name="static")

# Register default tools
tool_registry.register(SearchCompanyTool())
tool_registry.register(SearchWebTool())
tool_registry.register(CreatePDFTool())
tool_registry.register(CreatePPTTool())
tool_registry.register(CreateDocsTool())
tool_registry.register(SendEmailTool())

# Register default skills
skill_registry.register(SalesAccountResearchSkill())
skill_registry.register(ProposalWriterSkill())

# Initialize executor and router
executor = AgentExecutor(tools=tool_registry.list_tools())
router = AgentRouter(skill_registry)

# In-memory storage for active sessions
sessions: Dict[str, AgentState] = {}

class CreateSessionRequest(BaseModel):
    query: str

class SkillMetadataResponse(BaseModel):
    name: str
    description: str
    prompt_template: str

@app.get("/")
def get_root():
    """
    Framework health check and metadata.
    """
    return {
        "app_name": settings.APP_NAME,
        "status": "online",
        "version": "0.3.0",
        "debug": settings.DEBUG,
        "registered_tools": tool_registry.list_tool_names(),
        "registered_skills": skill_registry.list_skill_names()
    }

@app.get("/skills", response_model=List[SkillMetadataResponse])
def get_skills():
    """
    List all dynamically registered skills.
    """
    return [
        SkillMetadataResponse(
            name=s.name,
            description=s.description,
            prompt_template=s.prompt_template
        ) for s in skill_registry.list_skills()
    ]

@app.post("/sessions", response_model=AgentState)
def create_session(request: CreateSessionRequest):
    """
    Create a new agent execution session with the user query.
    """
    session_id = str(uuid.uuid4())
    state = AgentState(
        session_id=session_id,
        query=request.query
    )
    sessions[session_id] = state
    
    # Save the initial user input to artifacts
    ArtifactWriter.write_json("agent_inputs/session_query.json", {"session_id": session_id, "query": request.query})
    
    return state

@app.get("/sessions/{session_id}", response_model=AgentState)
def get_session(session_id: str):
    """
    Retrieve current execution state of an active session.
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return sessions[session_id]

@app.post("/sessions/{session_id}/execute", response_model=AgentState)
async def execute_session_plan(session_id: str):
    """
    Routes the session query to a registered skill, runs the orchestrated plan,
    and returns the final updated state.
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    from services.artifacts.artifact_manager import ArtifactManager
    ArtifactManager.initialize_workspace()
    
    state = sessions[session_id]
    
    # Sync executor tools with dynamic registry
    global executor
    executor = AgentExecutor(tools=tool_registry.list_tools())
    
    # 1. Route the query to a matching skill
    skill = router.route(state.query)
    if not skill:
        state.update_status(AgentStatus.FAILED)
        state.response = "Routing error: No skill found to handle the query."
        ArtifactWriter.write_json("agent_outputs/routing_error.json", {"error": state.response})
        return state
    
    state.metadata["routed_skill"] = skill.name
    ArtifactWriter.write_json("agent_outputs/routed_skill.json", {"routed_skill": skill.name})
    
    # 2. Run the matched skill
    try:
        updated_state = await skill.run(state.query, state, executor)
        sessions[session_id] = updated_state
        
        # Save final state and response
        ArtifactWriter.write_json(f"final/session_state_{session_id}.json", updated_state.model_dump())
        if updated_state.response:
            ArtifactWriter.write_markdown(f"final/response_{session_id}.md", updated_state.response)
            
        return updated_state
    except Exception as e:
        state.update_status(AgentStatus.FAILED)
        state.response = f"Unhandled skill execution failure: {str(e)}"
        ArtifactWriter.write_json("final/execution_error.json", {"error": state.response})
        return state
