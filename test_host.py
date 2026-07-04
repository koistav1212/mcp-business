import asyncio
import json
from services.host.host_agent import HostAgent
from services.models.research_execution_plan import ResearchExecutionPlan
async def main():
    agent = HostAgent()
    plan = ResearchExecutionPlan(company_name="Infosys")
    # Actually wait, HostAgent.run takes (plan, target)
    class Target:
        company = "Infosys"
        ticker = "INFY"
    await agent.run(plan, Target())
asyncio.run(main())
