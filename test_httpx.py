import asyncio
import httpx

async def main():
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer sk-placeholder"
    }
    data = {
        "model": "qwen3.5:2b",
        "messages": [{"role": "user", "content": "hi"}]
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://127.0.0.1:11434/v1/chat/completions",
            json=data,
            headers=headers
        )
        print("Status:", response.status_code)
        print("Body:", response.text)

asyncio.run(main())
