import asyncio
from services.knowledge.knowledge_router import KnowledgeRouter
from services.agents.tool_router_agent import ToolRouterAgent
from services.knowledge.evidence_store import EvidenceStore

async def main():
    router = KnowledgeRouter(ToolRouterAgent(), EvidenceStore())
    res = await router.get_evidence("news_feed", "AAPL")
    print(f"Result count: {len(res)}")

asyncio.run(main())
