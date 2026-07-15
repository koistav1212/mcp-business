import asyncio
from services.host.host_agent import HostAgent
from services.artifacts.artifact_manager import ArtifactManager

async def main():
    ArtifactManager.initialize_workspace()
    orchestrator = HostAgent()
    try:
        result = await orchestrator.run("Research Zoho")
        print("SUCCESS")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
