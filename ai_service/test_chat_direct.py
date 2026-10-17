import asyncio
import os
import sys

from dotenv import load_dotenv
load_dotenv()

from config.settings import settings
print(f"[1] Settings loaded. Provider: {settings.DEFAULT_LLM_PROVIDER}")
print(f"[1] Gemini Key present: {bool(settings.GEMINI_API_KEY)}")

try:
    from legal_guardrails import validate_input
    masked, state = validate_input("what is constitution")
    print(f"[2] Masking success! Masked query: '{masked}'")
except Exception as e:
    print(f"[2] Masking error: {e}")
    sys.exit(1)

try:
    from llm.providers.factory import get_llm_provider
    from langchain_core.messages import HumanMessage
    model = get_llm_provider("gemini").get_model()
    res = model.invoke([HumanMessage(content="Say hello in 3 words")])
    print(f"[3] Gemini LLM success! Response: {res.content}")
except Exception as e:
    print(f"[3] Gemini LLM error: {e}")
    sys.exit(1)

async def test_full():
    try:
        from chat.chat_service import ChatService
        service = ChatService()
        print("[4] Running ChatService stream_chat...")
        chunks = []
        async for chunk in service.stream_chat("test-123", "what is constitution"):
            chunks.append(chunk)
            print(f"    Chunk: {chunk[:60]}...")
        print("[5] FULL CHAT PIPELINE SUCCEEDED!")
    except Exception as e:
        import traceback
        print(f"[4] Stream chat error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_full())
