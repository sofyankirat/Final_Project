from pydantic import BaseModel
from typing import Optional, List, Dict

class PushRequest(BaseModel):
    do_reset: Optional[int] = 0

class SearchRequest(BaseModel):
    text: str
    limit: Optional[int] = 5
    chat_history: Optional[List[Dict]] = []