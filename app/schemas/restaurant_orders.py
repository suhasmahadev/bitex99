from pydantic import BaseModel
from typing import Optional

class AcceptOrderRequest(BaseModel):
    preparation_time: int

class RejectOrderRequest(BaseModel):
    reason: str
    description: str = ""
