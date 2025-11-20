# core/model.py
import asyncio
import ollama
from .config import settings

async def call_model_async(prompt: str):
    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(
        None,
        lambda: ollama.generate(
            model=settings.LLM_MODEL,
            prompt=prompt,
            options={"num_predict": 200},
        )
    )
    return response["response"]

