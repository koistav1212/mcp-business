import asyncio
from services.knowledge.knowledge_router import KnowledgeRouter
from services.agents.tool_router_agent import ToolRouterAgent
from services.knowledge.evidence_store import EvidenceStore

async def main():
    router = KnowledgeRouter(ToolRouterAgent(), EvidenceStore())
    ev1 = await router.get_evidence("news_feed", "AAPL")
    ev2 = await router.get_evidence("market_data", "AAPL")
    print(f"news_feed: {len(ev1)}")
    print(f"market_data: {len(ev2)}")

asyncio.run(main())
