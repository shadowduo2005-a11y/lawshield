import asyncio
from config.settings import settings
from llm.providers.factory import get_llm_provider
from langchain_core.messages import HumanMessage

async def main():
    model = get_llm_provider("gemini").get_model()
    response = model.invoke([HumanMessage(content="What is the capital of France?")])
    print("LLM RESPONSE:", response.content)

if __name__ == "__main__":
    asyncio.run(main())
