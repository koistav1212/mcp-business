import asyncio
from services.host.host_agent import HostAgent
from dotenv import load_dotenv

load_dotenv()

async def main():
    agent = HostAgent()
    res = await agent.run("Analyze Apple")
    import json
    print("FINISHED")
    with open("test_out.json", "w") as f:
        json.dump(res, f, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
