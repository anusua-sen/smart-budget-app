# backend/app/models/transaction_model.py
from sqlalchemy import Column, Integer, String, Float,Date
from backend.app.db import Base
from datetime import datetime

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    description = Column(String, nullable=False)
    category = Column(String, nullable=True)
    amount = Column(Float, nullable=False)
    date = Column(Date, nullable=True) 