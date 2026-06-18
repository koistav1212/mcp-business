from typing import Optional
from skills.base import BaseSkill
from core.state import AgentState, AgentStep, AgentStatus, ExecutionPlan, VerificationResult
from core.executor import AgentExecutor

class ProposalWriterSkill(BaseSkill):
    """
    Orchestrates the dynamic business proposal generation and delivery.
    Collects facts about a client company, renders PDF briefs and PowerPoint slide decks,
    uploads them to Google Drive (simulated), and dispatches download links to target client emails.
    """
    name: str = "proposal-writer"
    description: str = "Researches a company, generates structured PDFs and slide decks, and emails download links."
    prompt_template: str = (
        "Identify the target company name and recipient email. Call search_company and search_web. "
        "Generate proposal PDF and PPT slide deck. Send email containing download links to the user."
    )

    async def run(self, query: str, state: AgentState, executor: AgentExecutor) -> AgentState:
        query_lower = query.lower()
        
        # 1. Parse target company (heuristic matching)
        company_name = "zoho"
        for word in ["google", "zoho"]:
            if word in query_lower:
                company_name = word
                break
                
        # 2. Parse target email (looks for standard email patterns)
        target_email = "client@target.com"
        for word in query_lower.split():
            if "@" in word:
                target_email = word.strip(".,?!()")
                break

        # 3. Research Phase
        state.update_status(AgentStatus.PLANNING)
        step1 = AgentStep(
            step_id=1,
            name=f"Lookup company details for {company_name}",
            tool_name="search_company",
            tool_input={"company_name": company_name}
        )
        
        step2 = AgentStep(
            step_id=2,
            name=f"Retrieve public web updates for {company_name}",
            tool_name="search_web",
            tool_input={"query": f"{company_name} news updates"}
        )
        
        state.plan = ExecutionPlan(steps=[step1, step2])
        
        # Execute initial lookup
        state = await executor.execute_plan(state)
        if state.status == AgentStatus.FAILED:
            return state

        # Retrieve research tool outputs
        company_info = state.plan.steps[0].tool_output
        web_info = state.plan.steps[1].tool_output
        company_fullname = company_info.get("name", company_name.capitalize())
        
        # Format text parameters for proposal PDF
        pdf_title = f"Business Proposal for {company_fullname}"
        pdf_body = (
            f"This proposal outline details partnership opportunities with {company_fullname}.\n\n"
            f"Company Metadata:\n"
            f"- HQ Location: {company_info.get('hq')}\n"
            f"- Industry Focus: {company_info.get('industry')}\n"
            f"- Organization Size: {company_info.get('size')}\n"
            f"- Year Founded: {company_info.get('founded')}\n\n"
            f"Our AI analysis gathered the following news context from the public web:\n\n"
        )
        for article in web_info:
            pdf_body += f"- {article['title']}: {article['snippet']} (Url: {article['url']})\n\n"
            
        pdf_body += "Recommendation: Implement multi-agent workflows to streamline company operations."

        # Format slide contents for PPT
        slides = [
            {
                "title": f"Strategic Analysis: {company_fullname}",
                "points": [
                    f"Headquarters: {company_info.get('hq')}",
                    f"Operational size: {company_info.get('size')}",
                    f"Target Segment: {company_info.get('industry')}"
                ]
            },
            {
                "title": "Actionable News Signals",
                "points": [
                    f"Signal: {web_info[0]['title'] if web_info else 'General News'}",
                    "Opportunity to deploy automated workspace agents",
                    "Reduces time-to-market for slide and report compilation by 90%."
                ]
            }
        ]

        # 4. Document Generation Phase
        # Append steps 3 and 4 to the current plan
        step3 = AgentStep(
            step_id=3,
            name="Generate Proposal PDF",
            tool_name="create_pdf",
            tool_input={
                "filename": f"{company_name}_proposal.pdf",
                "title": pdf_title,
                "body_text": pdf_body
            }
        )
        
        step4 = AgentStep(
            step_id=4,
            name="Generate PowerPoint Brief Slides",
            tool_name="create_ppt",
            tool_input={
                "filename": f"{company_name}_slides.pptx",
                "presentation_title": f"{company_fullname} Partnership Brief",
                "slides": slides
            }
        )
        
        state.plan.steps.extend([step3, step4])
        
        # Execute PDF/PPT creation
        state = await executor.execute_plan(state)
        if state.status == AgentStatus.FAILED:
            return state

        pdf_url = state.plan.steps[2].tool_output
        ppt_url = state.plan.steps[3].tool_output

        # 5. Delivery Phase
        email_body = (
            f"Hello,\n\n"
            f"Here are the business intelligence resources you requested for {company_fullname}.\n\n"
            f"Download Resources:\n"
            f"- Proposal Report (PDF): {pdf_url}\n"
            f"- Presentation Deck (PPTX): {ppt_url}\n\n"
            f"Best regards,\n"
            f"AI Operational Agent"
        )
        
        step5 = AgentStep(
            step_id=5,
            name=f"Dispatch briefing email to {target_email}",
            tool_name="send_email",
            tool_input={
                "to": target_email,
                "subject": f"Briefing Deliverables for {company_fullname}",
                "body": email_body
            }
        )
        
        state.plan.steps.append(step5)
        
        # Execute email sending step
        state = await executor.execute_plan(state)
        if state.status == AgentStatus.FAILED:
            return state

        # 6. Verification Phase
        state.update_status(AgentStatus.VERIFYING)
        all_completed = all(s.status == "completed" for s in state.plan.steps)
        
        state.verification = VerificationResult(
            is_valid=all_completed,
            feedback="All structured research, rendering, and mailing pipelines executed successfully." if all_completed else "Workflow failed step execution."
        )
        
        if all_completed:
            state.update_status(AgentStatus.COMPLETED)
            state.response = (
                f"Successfully processed request for {company_fullname}.\n"
                f"- PDF: {pdf_url}\n"
                f"- PPT: {ppt_url}\n"
                f"- Email: Sent to {target_email}"
            )
        else:
            state.update_status(AgentStatus.FAILED)
            state.response = "Proposal workflow verification step failed."

        return state
