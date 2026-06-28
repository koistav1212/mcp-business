import asyncio
import httpx
import time

async def test_full_pipeline():
    url = "http://localhost:8000/workspace/run"
    
    print("Triggering workspace run for 'NVIDIA'...")
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json={"company": "NVIDIA"}, timeout=10.0)
        resp_data = resp.json()
        task_id = resp_data["task_id"]
        
        print(f"Task started: {task_id}. Polling for completion...")
        status_url = f"http://localhost:8000/workspace/status/{task_id}"
        
        while True:
            status_resp = await client.get(status_url)
            status_data = status_resp.json()
            status = status_data.get("status")
            print(f"Current status: {status}")
            if status in ["completed", "failed"]:
                break
            await asyncio.sleep(3)
            
        print("Done!", status_data)

if __name__ == "__main__":
    asyncio.run(test_full_pipeline())
