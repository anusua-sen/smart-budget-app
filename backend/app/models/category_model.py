from transformers import DistilBertTokenizerFast, DistilBertForSequenceClassification
import torch
import joblib
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import os
from transformers import DistilBertTokenizerFast, DistilBertForSequenceClassification
model_path = "backend/app/models/txn_classifier"

#def keyword_override(text):
#    s = text.lower()
#    if any(k in s for k in ["zomato", "swiggy", #"dominos", "pizza", "restaurant", "eat", "meal"]):
#        return "Food & Beverage"
#    if any(k in s for k in ["netflix", "hotstar", #"prime", "spotify", "pvr", "movie", "cinema", "youtube #premium"]):
#        return "Entertainment"
#    if any(k in s for k in ["uber", "ola", "cab", "taxi", #"metro", "bus", "fuel", "petrol", "parking"]):
#        return "Transport"
#    return None


tokenizer = DistilBertTokenizerFast.from_pretrained(model_path)
model = DistilBertForSequenceClassification.from_pretrained(model_path)
label_encoder = joblib.load(os.path.join(model_path, "label_encoder.pkl"))

# 🔹 Ensure the model runs on CPU (or GPU if available)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)
model.eval()

def classify_transactions(descriptions: list[str]):
    # apply keyword override first
    #kw = keyword_override(description)
    #if kw:
    #     use kw as category (skip model)

    inputs = tokenizer(descriptions, padding=True, truncation=True, return_tensors="pt")
    inputs = {key: val.to(device) for key, val in inputs.items()}
    with torch.no_grad():
        outputs = model(**inputs)
        preds = torch.argmax(outputs.logits, dim=-1)
    predicted_labels = label_encoder.inverse_transform(preds)
    results = [{"description": desc, "predicted_category": cat} for desc, cat in zip(descriptions, predicted_labels)]
    return results
