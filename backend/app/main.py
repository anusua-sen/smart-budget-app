# backend/app/main.py
from fastapi import FastAPI
from pydantic import BaseModel
from backend.app.models.category_model import classify_transactions
from backend.app.api import budgets

app = FastAPI(title="Smart Shopper Agent")

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or ["http://127.0.0.1:5500"] if you want specific
    allow_credentials=True,
    allow_methods=["*"],  # ✅ ensures DELETE is allowed
    allow_headers=["*"],
)


class Transactions(BaseModel):
    descriptions: list[str]

@app.post("/categorize")
def categorize(transactions: Transactions):
    results = classify_transactions(transactions.descriptions)
    return {"categories": results}

@app.get("/")
def root():
    return {"message": "Smart Shopper API is running 🚀"}
app.include_router(budgets.router, prefix="/budgets", tags=["budgets"])

@app.get("/")
def root():
    return {"message": "Smart Shopper Agent is running!"}