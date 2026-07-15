import asyncio
import json
from services.host.host_agent import HostAgent
from services.models.research_execution_plan import ResearchExecutionPlan, ResearchType, AnalysisDepth
async def main():
    agent = HostAgent()
    res = await agent.run(query="Infosys")
    print("FINISHED:", type(res))
asyncio.run(main())
