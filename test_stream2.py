import asyncio
from openai import AsyncOpenAI
from src.config.app_config import ConfigManager

async def main():
    config = ConfigManager.load()
    api_key = config.api_key
    if not api_key:
        print("API API key not found in config")
        return

    async with AsyncOpenAI(api_key=api_key) as client:
        stream = await client.responses.create(
            model="gpt-4o-mini",
            input=[{"role": "user", "content": [{"type": "input_text", "text": "Hello"}]}],
            stream=True
        )
        async for event in stream:
            print("EVENT.TYPE:", getattr(event, "type", "NO_TYPE"))
            print("EVENT:", event)
            print("-" * 20)

if __name__ == "__main__":
    asyncio.run(main())
