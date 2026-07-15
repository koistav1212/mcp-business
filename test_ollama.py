import asyncio
import httpx
import os
from dotenv import load_dotenv
load_dotenv()

async def test_ollama():
    base_url = os.environ["OLLAMA_BASE_URL"]
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{base_url}/chat/completions",
            json={
                "model": "llama3.1:8b",
                "messages": [
                    {"role": "system", "content": "You are a helpful planner."},
                    {"role": "user", "content": "Give me 3 bullet points about Apple as a company."},
                ],
                "max_tokens": 128
            },
            headers={"ngrok-skip-browser-warning": "69420"}
        )
        print("Status:", response.status_code)
        if response.status_code == 200:
            data = response.json()
            print("Response:", data["choices"][0]["message"]["content"])
        else:
            print("Error:", response.text)

if __name__ == "__main__":
    asyncio.run(test_ollama())
