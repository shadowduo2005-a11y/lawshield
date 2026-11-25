from fastapi import APIRouter

router = APIRouter(prefix="/llm", tags=["LLM"])

# Placeholder for LLM specific routes (e.g., changing providers, listing models)
@router.get("/status")
async def status():
    return {"status": "LLM module is active"}
