# backend/app/api/budgets.py
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from datetime import datetime
import io, csv
from rapidfuzz import process, fuzz
import pandas as pd
from typing import List
from pydantic import BaseModel

from backend.app.db import SessionLocal, engine, Base, get_db  # get_db if present else we provide below
from backend.app.models.budget_model import Budget
from backend.app.models.transaction_model import Transaction
from backend.app.schemas import BudgetCreate, BudgetOut, TransactionIn as TransactionSchema
from backend.app.models.category_model import classify_transactions
import pandas as pd
from datetime import datetime
from io import StringIO

# Ensure tables exist
Base.metadata.create_all(bind=engine)

router = APIRouter()


# If your db module doesn't already export get_db, define it here (no-op if you imported one above)
def _get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Choose whichever is available: use get_db if imported else fallback to _get_db
_db_dependency = get_db if "get_db" in globals() else _get_db


@router.post("/upload-csv")
def upload_transactions_csv(file: UploadFile = File(...), db: Session = Depends(_db_dependency)):
    """
    Upload a CSV with columns: description, amount, (optional) date
    Classify, save to DB, and return a simple summary count.
    Date format expected: YYYY-MM-DD (if provided). If missing/invalid, uses today's date.
    """
    try:
        df = pd.read_csv(file.file)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Unable to read CSV: {e}")

    if not {"description", "amount"}.issubset(df.columns):
        raise HTTPException(status_code=400, detail="CSV must have 'description' and 'amount' columns")

    # Build list of rows preserving order and capture optional date column per row
    rows: List[dict] = []
    for _, row in df.iterrows():
        desc = str(row["description"])
        try:
            amt = float(row["amount"])
        except Exception:
            raise HTTPException(status_code=400, detail=f"Invalid amount for description '{desc}'")
        # prefer lowercase column 'date' but accept 'Date' too; if neither, set None
        date_val = None
        if "date" in df.columns and not pd.isna(row["date"]):
            date_val = str(row["date"])
        elif "Date" in df.columns and not pd.isna(row["Date"]):
            date_val = str(row["Date"])
        rows.append({"description": desc, "amount": amt, "date": date_val})

    # Validate description + amount with Pydantic
    validated = []
    for r in rows:
        try:
            t = TransactionSchema(description=r["description"], amount=r["amount"])
            validated.append({"schema": t, "date": r["date"]})
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Validation error for '{r['description']}': {e}")

    # Classify descriptions (use your classifier function)
    descriptions = [v["schema"].description for v in validated]
    try:
        categories = classify_transactions(descriptions)
    except Exception as e:
        # classifier failures should not break everything; return an informative error
        raise HTTPException(status_code=500, detail=f"Classification failed: {e}")

    saved = 0
    # Save each validated row + predicted category
    for v, cat in zip(validated, categories):
        schema = v["schema"]
        date_str = v["date"]
        # parse category returned by classifier (supports dict or plain string)
        if isinstance(cat, dict):
            category_name = cat.get("predicted_category") or cat.get("category") or "Uncategorized"
        else:
            category_name = str(cat)

        # Parse date string if present
        txn_date = None
        if date_str:
            # accept common formats; try YYYY-MM-DD first
            parsed = None
            for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
                try:
                    parsed = datetime.strptime(date_str, fmt).date()
                    break
                except Exception:
                    parsed = None
            txn_date = parsed or datetime.utcnow().date()
        else:
            txn_date = datetime.utcnow().date()

        db_tx = Transaction(
            description=schema.description,
            amount=float(schema.amount),
            category=category_name,
            date=txn_date
        )
        db.add(db_tx)
        saved += 1

    db.commit()
    return {"message": f"{saved} transactions uploaded, classified and saved."}


@router.delete("/transactions/clear")
def clear_transactions(db: Session = Depends(_db_dependency)):
    try:
        deleted = db.query(Transaction).delete()
        db.commit()
        return {"message": f"Deleted {deleted} transactions successfully."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=BudgetOut)
def add_budget(budget: BudgetCreate, db: Session = Depends(_db_dependency)):
    existing = db.query(Budget).filter(Budget.category == budget.category).first()
    if existing:
        existing.limit = budget.limit
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing
    new_budget = Budget(category=budget.category, limit=budget.limit)
    db.add(new_budget)
    db.commit()
    db.refresh(new_budget)
    return new_budget


@router.post("/bulk", response_model=List[BudgetOut])
def create_budgets_bulk(payloads: List[BudgetCreate], db: Session = Depends(_db_dependency)):
    results = []
    for payload in payloads:
        existing = db.query(Budget).filter(Budget.category == payload.category).first()
        if existing:
            existing.limit = payload.limit
            db.add(existing)
            db.commit()
            db.refresh(existing)
            results.append(existing)
        else:
            new_budget = Budget(category=payload.category, limit=payload.limit)
            db.add(new_budget)
            db.commit()
            db.refresh(new_budget)
            results.append(new_budget)
    return results


@router.get("/view")
def view_budgets(db: Session = Depends(_db_dependency)):
    """
    Return the budgets directly as a list of {category, budget_limit}.
    """
    budgets = db.query(Budget).all()
    return [
        {
            "category": b.category,
            "budget_limit": float(b.limit or 0)
        }
        for b in budgets
    ]


@router.delete("/clear-limits")
def clear_budget_limits(db: Session = Depends(get_db)):
    try:
        deleted = db.query(Budget).delete()
        db.commit()
        return {"message": f"Cleared {deleted} budget limits successfully."}
    except Exception as e:
        db.rollback()
        return {"error": str(e)}


@router.get("/compute_spend")
def compute_spend(db: Session = Depends(_db_dependency)):
    """
    Return computed spend summary comparing persisted transactions to budgets.
    """
    persisted = db.query(Transaction).all()
    budgets = db.query(Budget).all()
    budget_map = {b.category: b.limit for b in budgets}

    def find_best_match(cat):
        if not budget_map or not cat:
            return None
        match = process.extractOne(cat, list(budget_map.keys()), scorer=fuzz.partial_ratio)
        if match and match[1] >= 80:
            return match[0]
        return None

    spend_summary = {}
    for txn in persisted:
        key = find_best_match(txn.category) or txn.category or "Uncategorized"
        spend_summary[key] = spend_summary.get(key, 0) + (txn.amount or 0.0)

    result = []
    for cat, spent in spend_summary.items():
        limit = budget_map.get(cat, 0.0)
        remaining = limit - spent
        spent_percent = (spent / limit * 100) if (limit and limit > 0) else None

        if limit == 0:
            status = "no budget set"
        elif remaining < 0:
            status = "overspent"
        elif spent_percent is not None and spent_percent >= 80:
            status = "close to limit"
        else:
            status = "within budget"

        result.append({
            "category": cat,
            "spent": round(spent, 2),
            "budget_limit": float(limit),
            "remaining": round(remaining, 2),
            "spent_percent": round(spent_percent, 1) if spent_percent is not None else None,
            "status": status
        })

    result.sort(key=lambda x: x["spent"], reverse=True)
    return {"summary": result}


@router.get("/insights")
def get_insights(db: Session = Depends(_db_dependency)):
    """
    Get analytics insights about transactions:
    - Total spend
    - Category-wise breakdown
    - Monthly trend
    """
    category_data = (
        db.query(Transaction.category, func.sum(Transaction.amount))
        .group_by(Transaction.category)
        .all()
    )
    category_breakdown = {cat: float(total or 0) for cat, total in category_data}
    total_spent = sum(category_breakdown.values())

    category_percentages = {
        k: round((v / total_spent) * 100, 2) if total_spent > 0 else 0
        for k, v in category_breakdown.items()
    }

    monthly_data = (
        db.query(
            extract("year", Transaction.date).label("year"),
            extract("month", Transaction.date).label("month"),
            func.sum(Transaction.amount).label("total")
        )
        .group_by("year", "month")
        .order_by("year", "month")
        .all()
    )
    monthly_summary = {
        f"{int(y)}-{int(m):02d}": float(t or 0)
        for y, m, t in monthly_data
        if y and m
    }

    top_categories = sorted(
        [{"category": k, "amount": v} for k, v in category_breakdown.items()],
        key=lambda x: x["amount"],
        reverse=True
    )[:5]

    return {
        "total_spent": round(total_spent, 2),
        "category_breakdown": category_breakdown,
        "category_percentages": category_percentages,
        "monthly_summary": monthly_summary,
        "top_categories": top_categories
    }


@router.get("/analytics")
def get_analytics(db: Session = Depends(_db_dependency)):
    """
    Return analytics data for visualization:
    - Monthly total spend
    - Category spend per month
    - Top merchants/keywords
    """
    transactions = db.query(Transaction).all()

    if not transactions:
        return {"message": "No transaction data available."}

    monthly_spend = {}
    category_monthly = {}
    merchant_count = {}

    for txn in transactions:
        month = txn.date.strftime("%b %Y") if txn.date else "Unknown"
        category = txn.category or "Uncategorized"
        desc = txn.description.lower() if txn.description else ""

        monthly_spend[month] = monthly_spend.get(month, 0) + txn.amount

        if category not in category_monthly:
            category_monthly[category] = {}
        category_monthly[category][month] = category_monthly[category].get(month, 0) + txn.amount

        for word in desc.split():
            if len(word) > 3:
                merchant_count[word] = merchant_count.get(word, 0) + 1

    sorted_monthly = sorted(monthly_spend.items(), key=lambda x: x[0])
    sorted_merchants = sorted(merchant_count.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "monthly_spend": [{"month": m, "total": t} for m, t in sorted_monthly],
        "category_monthly": category_monthly,
        "top_merchants": [{"merchant": m, "count": c} for m, c in sorted_merchants],
    }



@router.get("/download-report")
def download_report(db: Session = Depends(get_db)):
    """
    Download insights summary (category, total spent, percentage) as CSV
    """
    # Fetch insights logic from your existing endpoint
    category_data = (
        db.query(Transaction.category, func.sum(Transaction.amount))
        .group_by(Transaction.category)
        .all()
    )

    category_breakdown = {cat: float(total or 0) for cat, total in category_data}
    total_spent = sum(category_breakdown.values())

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Category", "Total Spent", "Percentage"])

    for cat, total in category_breakdown.items():
        percent = round((total / total_spent) * 100, 2) if total_spent > 0 else 0
        writer.writerow([cat, total, f"{percent}%"])

    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=insights_report.csv"},
    )
