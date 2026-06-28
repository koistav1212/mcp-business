import asyncio
import logging

from services.host.host_agent import HostAgent
from services.artifacts.artifact_manager import ArtifactManager

logging.basicConfig(level=logging.INFO)

async def test_run():
    # Initialize workspace as expected
    ArtifactManager.initialize_workspace()

    host = HostAgent()
    print("Running host agent for 'Analyze NVIDIA'...")
    res = await host.run("Analyze NVIDIA")
    print("Done!")

if __name__ == "__main__":
    asyncio.run(test_run())
