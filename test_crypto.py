import asyncio
import os
import sys

# Set up path so we can import backend modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "backend")))

from backend.services.chat_service import generate_chat_response

async def test():
    # Use empty history and simple topic
    response = await generate_chat_response(
        topic="",
        message="What is the current price and market cap of PEP? Keep it extremely short.",
        history=[],
        stream=False
    )
    print("Agent says:\n", response)

if __name__ == "__main__":
    asyncio.run(test())
