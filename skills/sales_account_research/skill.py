from typing import Optional
from skills.base import BaseSkill
from core.state import AgentState, AgentStep, AgentStatus, ExecutionPlan, VerificationResult
from core.executor import AgentExecutor

class SalesAccountResearchSkill(BaseSkill):
    """
    Orchestrated skill that researches an account by joining structured parameters
    with recent news search snippets.
    """
    name: str = "sales-account-research"
    description: str = "Researches a target company using structured lookup tools and web searches, then synthesizes a report."
    prompt_template: str = (
        "Identify the target company name from the query. Run 'search_company' to obtain base parameters "
        "and 'search_web' to fetch recent news. Compile the final synthesized brief."
    )

    async def run(self, query: str, state: AgentState, executor: AgentExecutor) -> AgentState:
        # Determine company name from query (simple heuristic for Phase 2)
        company_name = "unknown"
        for word in query.lower().replace("?", "").replace(".", "").split():
            if word in ["zoho", "google"]:
                company_name = word
                break
        
        # If no heuristic matched, default to zoho
        if company_name == "unknown":
            company_name = "zoho"

        # 1. Update state status to PLANNING
        state.update_status(AgentStatus.PLANNING)
        
        # Define execution plan steps
        step1 = AgentStep(
            step_id=1,
            name=f"Lookup structured data for {company_name}",
            tool_name="search_company",
            tool_input={"company_name": company_name}
        )
        
        step2 = AgentStep(
            step_id=2,
            name=f"Search recent news for {company_name}",
            tool_name="search_web",
            tool_input={"query": f"{company_name} company news"}
        )
        
        state.plan = ExecutionPlan(steps=[step1, step2])
        
        # 2. Run steps using executor
        state = await executor.execute_plan(state)
        
        # 3. Verification Phase
        if state.status == AgentStatus.VERIFYING:
            company_info = state.plan.steps[0].tool_output
            web_info = state.plan.steps[1].tool_output
            
            is_valid = bool(company_info and web_info)
            state.verification = VerificationResult(
                is_valid=is_valid,
                feedback="All research steps succeeded and returned data." if is_valid else "Missing research outputs."
            )
            
            if is_valid:
                # Compile a synthesized report
                report = (
                    f"# Account Research: {company_info.get('name', company_name.capitalize())}\n\n"
                    f"## Company Overview\n"
                    f"- **HQ**: {company_info.get('hq')}\n"
                    f"- **Size**: {company_info.get('size')}\n"
                    f"- **Industry**: {company_info.get('industry')}\n"
                    f"- **Founded**: {company_info.get('founded')}\n\n"
                    f"## Recent News & Web Mentions\n"
                )
                for item in web_info:
                    report += f"- **[{item['title']}]({item['url']})**: {item['snippet']}\n"
                
                state.update_status(AgentStatus.COMPLETED)
                state.response = report
            else:
                state.update_status(AgentStatus.FAILED)
                state.response = "Research failed due to incomplete tool outputs."
                
        return state
