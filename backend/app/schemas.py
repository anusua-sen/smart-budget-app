# backend/app/schemas.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class BudgetCreate(BaseModel):
    category: str
    limit: float

class BudgetOut(BudgetCreate):
    id: int
    class Config:
        orm_mode = True

# Pydantic schema for incoming transaction objects (used for validation)
class TransactionIn(BaseModel):
    description: str
    amount: float

# Pydantic schema for output (optional)
class TransactionOut(TransactionIn):
    id: int
    category: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        orm_mode = True
