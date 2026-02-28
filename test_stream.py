import asyncio
import os
from openai import AsyncOpenAI
import json

async def main():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Set OPENAI_API_KEY environment variable")
        return

    async with AsyncOpenAI(api_key=api_key) as client:
        stream = await client.responses.create(
            model="gpt-5.2",
            input=[{"role": "user", "content": [{"type": "input_text", "text": "Hello"}]}],
            stream=True
        )
        async for event in stream:
            print("EVENT.TYPE:", getattr(event, "type", "NO_TYPE"))
            print("EVENT:", event)
            print("-" * 20)

if __name__ == "__main__":
    asyncio.run(main())
