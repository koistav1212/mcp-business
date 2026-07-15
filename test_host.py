import asyncio
import json
from dotenv import load_dotenv
load_dotenv()
from services.host.host_agent import HostAgent
from services.core.models import ResearchExecutionPlan, ResearchType, AnalysisDepth
async def main():
    agent = HostAgent()
    res = await agent.run(query="Infosys")
    print("FINISHED:", type(res))
asyncio.run(main())
