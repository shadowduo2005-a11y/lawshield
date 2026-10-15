from pydantic import BaseModel
from typing import Optional

# Base parsing if we need structured outputs
class ChatResponse(BaseModel):
    content: str
    error: Optional[str] = None
