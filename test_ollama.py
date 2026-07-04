import asyncio
import httpx

async def test_ollama():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:11434/v1/chat/completions",
            json={
                "model": "qwen3.5:2b",
                "messages": [
                    {"role": "system", "content": "You are a helpful planner."},
                    {"role": "user", "content": "Give me 3 bullet points about Apple as a company."},
                ],
                "max_tokens": 128
            }
        )
        print("Status:", response.status_code)
        if response.status_code == 200:
            data = response.json()
            print("Response:", data["choices"][0]["message"]["content"])
        else:
            print("Error:", response.text)

if __name__ == "__main__":
    asyncio.run(test_ollama())
