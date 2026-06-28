import os
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
import httpx

from services.host.host_agent import HostAgent
from services.research.models import ResearchContext
from services.research.ui_response import build_ui_generation
from core.config import settings

# Import tools
from tools.create_pdf import CreatePDFTool
from tools.create_ppt import CreatePPTTool
from tools.create_docs import CreateDocsTool

router = APIRouter()
logger = logging.getLogger("uvicorn.error")

# In-memory dictionary to store background task status and results
tasks_db = {}
import uuid

class ResearchRequest(BaseModel):
    company: Optional[str] = None
    query: Optional[str] = None

class GenerateArtifactRequest(BaseModel):
    company: Optional[str] = None
    format: str  # "pdf", "ppt", "docs"
    style: Optional[str] = "professional"
    prompt: Optional[str] = None

class GenerateArtifactResponse(BaseModel):
    url: str
    filename: str
    format: str

@router.post("/workspace/run")
async def run_workspace(req: ResearchRequest, background_tasks: BackgroundTasks):
    """
    Triggers the central ResearchOrchestrator for the target company
    in the background to prevent HTTP timeouts.
    """
    if not req.company and not req.query:
        raise HTTPException(status_code=400, detail="Either company or query must be provided")

    task_id = str(uuid.uuid4())
    tasks_db[task_id] = {
        "status": "processing",
        "result": None,
        "error": None
    }
    
    query = req.query or f"Research {req.company}"

    async def _run_task(task_id: str, query: str):
        try:
            import json
            from services.artifacts.artifact_manager import ArtifactManager
            ArtifactManager.initialize_workspace()
            
            orchestrator = HostAgent()
            result = await orchestrator.run(query)
            tasks_db[task_id]["status"] = "completed"
            tasks_db[task_id]["result"] = json.loads(json.dumps(result, default=str))
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            tasks_db[task_id]["status"] = "failed"
            tasks_db[task_id]["error"] = str(e)

    background_tasks.add_task(_run_task, task_id, query)
    return {
        "task_id": task_id, 
        "status": "processing", 
        "message": "Task started in background. Poll /workspace/status/{task_id} for results."
    }

@router.get("/workspace/status/{task_id}")
async def get_workspace_status(task_id: str):
    """
    Check the status of a background research or artifact generation task.
    """
    task = tasks_db.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

async def generate_content_via_llm(context: dict, format: str, style: str, prompt_text: str) -> Any:
    # Build a clean context representation for the LLM
    profile = context.get("profile", {})
    financials = context.get("financials", {})
    
    context_data = {
        "company_name": profile.get("name"),
        "overview": profile.get("overview"),
        "headquarters": profile.get("headquarters"),
        "employee_count": profile.get("employee_count"),
        "website": profile.get("website"),
        "founders": profile.get("founders", []),
        "financials": financials,
        "competitors": context.get("competitors", []),
        "leadership": context.get("leadership", []),
        "technology_stack": context.get("technology_stack", []),
        "hiring_signals": context.get("hiring_signals", [])
    }
    
    system_instruction = "You are a professional business intelligence consultant."
    
    if format in ["pdf", "docs"]:
        llm_prompt = f"""
You are creating a business report in {format.upper()} format using style '{style}'.
Based on the following company research context:
{json.dumps(context_data, indent=2)}

The user request/prompt for content focus is:
"{prompt_text}"

Please generate the report content. It MUST consist of:
1. A concise, professional title.
2. The body text of the report. The body text must be formatted with paragraphs separated by double newlines (\\n\\n). Do not use markdown syntax (like **bold** or bullet lists) in the text itself since it will be rendered directly by reportlab/docx generators.

Return your response in the following JSON format:
{{
  "title": "Report Title Here",
  "body": "Paragraph 1 here.\\n\\nParagraph 2 here.\\n\\nParagraph 3 here."
}}
        """
    else:  # ppt
        llm_prompt = f"""
You are creating a business presentation slide deck (PPT) using style '{style}'.
Based on the following company research context:
{json.dumps(context_data, indent=2)}

The user request/prompt for content focus is:
"{prompt_text}"

Please generate a presentation structure consisting of:
1. A main presentation title.
2. A list of 4-6 slides, each slide having a title and a list of 3-4 bullet points.

Return your response in the following JSON format:
{{
  "presentation_title": "Presentation Title Here",
  "slides": [
    {{
      "title": "Slide 1 Title",
      "points": ["Bullet 1", "Bullet 2", "Bullet 3"]
    }},
    {{
      "title": "Slide 2 Title",
      "points": ["Bullet 1", "Bullet 2", "Bullet 3"]
    }}
  ]
}}
        """
        
    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": settings.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": llm_prompt}
        ],
        "response_format": {"type": "json_object"}
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            json=data,
            headers=headers,
            timeout=30.0
        )
        response.raise_for_status()
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        return json.loads(content)

def generate_custom_report_content(context: dict, format: str, style: str, prompt_text: str) -> Any:
    profile = context.get("profile", {})
    company_name = profile.get("name", "Unknown")
    hq = profile.get("headquarters", "Unknown")
    size = profile.get("employee_count", 0)
    size_str = f"{size:,}" if size else "Unknown"
    website = profile.get("website", "")
    
    # 1. Parse prompt keywords to customize focus
    prompt_lower = (prompt_text or "").lower()
    
    focus_financials = "financial" in prompt_lower or "revenue" in prompt_lower or "funding" in prompt_lower
    focus_tech = "tech" in prompt_lower or "stack" in prompt_lower or "software" in prompt_lower or "engineering" in prompt_lower
    focus_people = "hiring" in prompt_lower or "people" in prompt_lower or "leadership" in prompt_lower or "founder" in prompt_lower
    focus_competitors = "competitor" in prompt_lower or "rival" in prompt_lower
    
    # Choose framework based on prompt or style
    if "swot" in prompt_lower:
        chosen_framework = "SWOT"
    elif "porter" in prompt_lower:
        chosen_framework = "Porter's Five Forces"
    elif "7s" in prompt_lower or "mckinsey" in prompt_lower:
        chosen_framework = "McKinsey 7S"
    else:
        # Style mapping
        if style == "creative":
            chosen_framework = "Porter's Five Forces"
        elif style == "minimalist":
            chosen_framework = "McKinsey 7S"
        else:
            chosen_framework = "SWOT"
            
    # Gather variables
    financials = context.get("financials", {})
    financials_text = "N/A"
    if financials:
        financials_text = (
            f"Annual Revenue: {financials.get('revenue_annual')} | "
            f"Funding Total: {financials.get('funding_total')} | "
            f"Last Round: {financials.get('last_round')}"
        )
    competitors_list = [c.get("name") for c in context.get("competitors", [])]
    competitors_str = ", ".join(competitors_list) if competitors_list else "industry peers"
    
    leaders_list = [f"{l.get('name')} ({l.get('role')})" for l in context.get("leadership", [])]
    leaders_str = ", ".join(leaders_list) if leaders_list else "executive team"
    
    hiring_list = [f"{h.get('role_title')} in {h.get('department')} ({h.get('location')})" for h in context.get("hiring_signals", [])]
    hiring_str = "; ".join(hiring_list[:3]) if hiring_list else "talent expansion"
    
    tech_stack = context.get("technology_stack", [])
    tech_stack_str = ", ".join(tech_stack) if tech_stack else "modern tech stack"
    
    # Construct customizable sections
    summary_section = (
        f"1. EXECUTIVE SUMMARY & CORPORATE POSITIONING\n"
        f"{company_name} is a key enterprise operating under a strategic framework, driving value from "
        f"headquarters in {hq} with an employee base of {size_str}. Our research indicates active growth and "
        f"development across operational layers. To maintain leadership against {competitors_str}, {company_name} "
        f"must continuously innovate and leverage its core talent."
    )
    
    # Customize Summary based on prompt focus
    if focus_financials:
        summary_section += f" Financially, key milestones include: {financials_text}."
    if focus_tech:
        summary_section += f" The technology foundation relies on {tech_stack_str}."
    if focus_people:
        summary_section += f" The leadership is driven by {leaders_str}."

    # Framework section
    framework_section = ""
    if chosen_framework == "SWOT":
        framework_section = (
            f"2. SWOT ANALYSIS FRAMEWORK\n"
            f"- Strengths: Strong technology stack ({tech_stack_str}) and leadership led by {leaders_str}.\n"
            f"- Weaknesses: Resource constraints in high-demand roles, specifically for positions like {hiring_str}.\n"
            f"- Opportunities: Expanding AI automation and integrating developer vetting pipelines.\n"
            f"- Threats: Direct competition from {competitors_str} and recruitment bottlenecks."
        )
    elif chosen_framework == "Porter's Five Forces":
        framework_section = (
            f"2. PORTER'S FIVE FORCES INDUSTRY ANALYSIS\n"
            f"- Threat of New Entrants: Medium-Low. The complexity of the technology stack ({tech_stack_str}) is a barrier.\n"
            f"- Bargaining Power of Buyers: High. Enterprise clients can choose between {company_name} and {competitors_str}.\n"
            f"- Bargaining Power of Suppliers: Medium. High dependency on key engineering roles ({hiring_str}).\n"
            f"- Threat of Substitutes: Low due to custom integration hooks.\n"
            f"- Industry Rivalry: High. Competitors like {competitors_str} drive rapid feature cycles."
        )
    else:
        framework_section = (
            f"2. MCKINSEY 7S ALIGNMENT ANALYSIS\n"
            f"- Strategy: Expand technical differentiation and defend market share against {competitors_str}.\n"
            f"- Systems: Run core architectures on {tech_stack_str}.\n"
            f"- Staff/Skills: Strong demand for specialized roles ({hiring_str}).\n"
            f"- Style: Led by {leaders_str}.\n"
            f"- Shared Values: Speed-to-market, quality, and collaboration."
        )

    # Customize framework section based on prompt
    if focus_competitors:
        framework_section += f"\nNote: Competitor positioning against {competitors_str} is the primary strategic priority."

    financials_section = (
        f"3. FINANCIAL PROFILE & CAPITAL ALLOCATION\n"
        f"The company financial health shows the following metrics: {financials_text}. "
        f"Capital allocation strategies indicate alignment with growth and active developer hiring."
    )
    
    recruitment_section = (
        f"4. LEADERSHIP & RECRUITMENT SYNERGY\n"
        f"Under key executives ({leaders_str}), the company is expanding talent pools targeting: {hiring_str}. "
        f"We recommend optimizing applicant screening processes and utilizing custom outreach sequences."
    )
    
    recommendation_section = (
        f"5. STRATEGIC RECOMMENDATIONS\n"
        f"- Recommendation 1: Deploy task-specific AI agent loops to automate research pipelines.\n"
        f"- Recommendation 2: Address talent shortages in {hiring_str} through optimized candidate templates.\n"
        f"- Recommendation 3: Differentiate services and build high-value solutions to compete with {competitors_str}."
    )
    
    # If the prompt itself is a general request, we can append it as a custom note/section
    custom_note = ""
    if prompt_text and not any([focus_financials, focus_tech, focus_people, focus_competitors]):
        custom_note = f"\n\nCUSTOM USER INPUT NOTE:\nThis report was generated with custom guidance focus: '{prompt_text}'."

    if format in ["pdf", "docs"]:
        title = f"{company_name.upper()} STRATEGIC BRIEFING"
        body = f"{summary_section}\n\n{framework_section}\n\n{financials_section}\n\n{recruitment_section}\n\n{recommendation_section}{custom_note}"
        return {"title": title, "body": body}
    else:  # ppt
        presentation_title = f"{company_name.upper()} BRIEFING DECK"
        slides = [
            {
                "title": f"Strategic Analysis: {company_name}",
                "points": [
                    f"Headquarters: {hq}",
                    f"Scale: {size_str} Employees",
                    f"Analysis Framework: {chosen_framework}",
                    f"Presentation Style: {style.capitalize()}"
                ]
            },
            {
                "title": "Executive Summary",
                "points": [
                    f"Key player in market battling against {competitors_str}",
                    f"Leaders: {leaders_str}",
                    "Focus area: Growth and strategic positioning"
                ]
            }
        ]
        
        if chosen_framework == "SWOT":
            slides.append({
                "title": "SWOT Matrix Analysis",
                "points": [
                    f"Strengths: Tech Stack ({tech_stack_str})",
                    f"Weaknesses: Staffing roles like {hiring_str}",
                    "Opportunities: Automation and agent workflow integration",
                    f"Threats: Competitors like {competitors_str}"
                ]
            })
        elif chosen_framework == "Porter's Five Forces":
            slides.append({
                "title": "Porter's Five Forces",
                "points": [
                    f"Rivalry: High competition with {competitors_str}",
                    f"Buyers: High bargaining power demanding integrations",
                    f"Suppliers: High pressure for talent ({hiring_str})",
                    "New Entrants: Medium-Low barrier to entry"
                ]
            })
        else:
            slides.append({
                "title": "McKinsey 7S Alignment",
                "points": [
                    f"Strategy: Technical differentiation from {competitors_str}",
                    f"Systems: Infrastructure built around {tech_stack_str}",
                    f"Staff/Skills: High engineering talent demand for {hiring_str}",
                    f"Style: Leadership driven by {leaders_str}"
                ]
            })
            
        slides.extend([
            {
                "title": "Financial Profile",
                "points": [
                    f"Annual Revenue Indicator: {financials.get('revenue_annual') if financials else 'N/A'}",
                    f"Total Funding: {financials.get('funding_total') if financials else 'N/A'}",
                    f"Last Round: {financials.get('last_round') if financials else 'N/A'}"
                ]
            },
            {
                "title": "Strategic Recommendations",
                "points": [
                    f"Address recruitment pipelines for {hiring_str}",
                    f"Deploy automation to stand out against {competitors_str}",
                    "Optimize resource allocation to leverage tech strengths"
                ]
            }
        ])
        
        # If custom prompt was passed, append a custom slide
        if prompt_text and not any([focus_financials, focus_tech, focus_people, focus_competitors]):
            slides.append({
                "title": "Custom Focus Note",
                "points": [
                    f"Guidance focus: {prompt_text}",
                    "Strategic alignment with user prompt suggestions completed."
                ]
            })
            
        return {"presentation_title": presentation_title, "slides": slides}

@router.post("/workspace/generate-artifact")
async def generate_artifact(req: GenerateArtifactRequest, background_tasks: BackgroundTasks):
    """
    On-demand document/artifact generation (PDF, PPT, Word/Docs) for a target company
    executed as a background task to prevent HTTP timeouts.
    """
    company = req.company
    if not company:
        if req.prompt:
            from services.planning.planner import PromptUnderstandingAgent
            agent = PromptUnderstandingAgent()
            plan = await agent.plan(req.prompt)
            company = plan.get("target_company")
        if not company:
            raise HTTPException(status_code=400, detail="Company name could not be inferred. Please provide it explicitly.")

    format_clean = req.format.lower().strip()
    if format_clean not in ["pdf", "ppt", "docs"]:
        raise HTTPException(status_code=400, detail="Invalid format. Supported formats: pdf, ppt, docs")

    task_id = str(uuid.uuid4())
    tasks_db[task_id] = {
        "status": "processing",
        "result": None,
        "error": None
    }

    async def _run_artifact_task(task_id: str, req: GenerateArtifactRequest, company: str, format_clean: str):
        try:
            # 1. Run the research pipeline (without auto generation)
            orchestrator = HostAgent()
            query = req.prompt or f"Research {company}"
            context = await orchestrator.run(query)
            
            if not context:
                raise ValueError(f"No research data found for company: {company}")
                
            if isinstance(context, dict) and context.get("status") == "needs_clarification":
                raise ValueError(context.get("message", "Clarification needed"))
                
            style_clean = req.style.lower().strip() if req.style else "professional"
            prompt_clean = req.prompt.strip() if req.prompt else ""
            
            # 2. Content synthesis
            content = None
            if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != "sk-placeholder":
                try:
                    content = await generate_content_via_llm(context, format_clean, style_clean, prompt_clean)
                except Exception as e:
                    logger.warning(f"LLM content generation failed, falling back to rule-based template: {e}")
                    
            if not content:
                content = generate_custom_report_content(context, format_clean, style_clean, prompt_clean)
                
            # 3. Call generation tools based on format
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            company_slug = company.lower().replace(" ", "_")
            
            if format_clean == "pdf":
                tool = CreatePDFTool()
                filename = f"{company_slug}_report_{timestamp}.pdf"
                url = await tool.execute(
                    filename=filename,
                    title=content["title"],
                    body_text=content["body"],
                    style=style_clean
                )
            elif format_clean == "docs":
                tool = CreateDocsTool()
                filename = f"{company_slug}_report_{timestamp}.docx"
                url = await tool.execute(
                    filename=filename,
                    title=content["title"],
                    body_text=content["body"],
                    style=style_clean
                )
            else:  # ppt
                tool = CreatePPTTool()
                filename = f"{company_slug}_deck_{timestamp}.pptx"
                url = await tool.execute(
                    filename=filename,
                    presentation_title=content["presentation_title"],
                    slides=content["slides"],
                    style=style_clean
                )
                
            tasks_db[task_id]["status"] = "completed"
            tasks_db[task_id]["result"] = {
                "url": url,
                "filename": filename,
                "format": format_clean
            }
        except Exception as e:
            logger.error(f"Artifact task {task_id} failed: {e}")
            tasks_db[task_id]["status"] = "failed"
            tasks_db[task_id]["error"] = str(e)

    background_tasks.add_task(_run_artifact_task, task_id, req, company, format_clean)
    
    return {
        "task_id": task_id, 
        "status": "processing", 
        "message": "Artifact generation started in background. Poll /workspace/status/{task_id} for results."
    }
