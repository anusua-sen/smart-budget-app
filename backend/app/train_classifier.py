# backend/app/train_classifier.py
"""
Train a small text classification model on your transaction dataset.
This uses Hugging Face transformers (DistilBERT) for multi-class classification.
"""

import pandas as pd
from sklearn.model_selection import train_test_split
from datasets import Dataset
from transformers import (
    DistilBertTokenizerFast,
    DistilBertForSequenceClassification,
    TrainingArguments,
    Trainer,
)
import torch
import joblib
from sklearn.preprocessing import LabelEncoder
from transformers import AutoTokenizer, AutoModelForSequenceClassification, Trainer, TrainingArguments

# 1️⃣ Load dataset
df = pd.read_csv("backend/data/transactions.csv")
  # make sure your CSV is here
print(f"Loaded {len(df)} rows")

# Expected columns: description, category
if not {"description", "category"}.issubset(df.columns):
    raise ValueError("CSV must have columns: description, category")

#2️⃣ Encode labels using LabelEncoder
label_encoder = LabelEncoder()
df["label"] = label_encoder.fit_transform(df["category"])

# 3️⃣ Split dataset
train_df, test_df = train_test_split(df, test_size=0.2, random_state=42, stratify=df["label"])

# 4️⃣ Convert to Hugging Face Dataset
train_ds = Dataset.from_pandas(train_df)
test_ds = Dataset.from_pandas(test_df)

# 5️⃣ Load tokenizer and tokenize
tokenizer = DistilBertTokenizerFast.from_pretrained("distilbert-base-uncased")

def tokenize(batch):
    return tokenizer(batch["description"], padding="max_length", truncation=True, max_length=64)

train_ds = train_ds.map(tokenize, batched=True)
test_ds = test_ds.map(tokenize, batched=True)

#6️⃣ Define model
num_labels = len(label_encoder.classes_)
id2label = {i: label for i, label in enumerate(label_encoder.classes_)}
label2id = {label: i for i, label in enumerate(label_encoder.classes_)}

model = DistilBertForSequenceClassification.from_pretrained(
    "distilbert-base-uncased",
    num_labels=num_labels,
    id2label=id2label,
    label2id=label2id,
)

# 7️⃣ Training setup
args = TrainingArguments(
    output_dir="backend/app/models/txn_classifier",
    learning_rate=2e-5,
    eval_strategy="epoch",
    save_strategy="epoch",
    per_device_train_batch_size=8,
    #per_device_eval_batch_size=8,
    num_train_epochs=5,
    weight_decay=0.01,
    save_total_limit=1,
    logging_dir="backend/app/logs",
    logging_steps=10,
    load_best_model_at_end=True,
    metric_for_best_model="accuracy",
    
)

def compute_metrics(pred):
    preds = pred.predictions.argmax(-1)
    acc = (preds == pred.label_ids).mean()
    return {"accuracy": acc}

trainer = Trainer(
    model=model,
    args=args,
    train_dataset=train_ds,
    eval_dataset=test_ds,
    tokenizer=tokenizer,
    compute_metrics=compute_metrics,
)

# 8️⃣ Train!
trainer.train()

# 9️⃣ Save model
model.save_pretrained("backend/app/models/txn_classifier")
tokenizer.save_pretrained("backend/app/models/txn_classifier")

joblib.dump(label_encoder, "backend/app/models/txn_classifier/label_encoder.pkl")

print("✅ Model trained and saved to backend/app/models/txn_classifier")
