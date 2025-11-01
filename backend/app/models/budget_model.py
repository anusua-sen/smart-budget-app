from sqlalchemy import Column, Integer, String, Float
from backend.app.db import Base

class Budget(Base):
    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String, unique=True, index=True, nullable=False)
    limit = Column(Float, nullable=False)
