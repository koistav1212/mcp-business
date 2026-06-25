import asyncio

# Global semaphore to restrict maximum concurrent connections to Groq
GROQ_SEMAPHORE = asyncio.Semaphore(2)
