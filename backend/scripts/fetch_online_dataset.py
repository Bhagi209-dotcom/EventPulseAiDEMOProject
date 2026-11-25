"""Standalone script to re-fetch 1,500 rows from HuggingFace dataset into backend/data/online_lecture_feedback.csv."""
from pathlib import Path
import urllib.request
import json
import pandas as pd

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "online_lecture_feedback.csv"
HF_PARQUET_API = "https://datasets-server.huggingface.co/parquet?dataset=chillies/course-review-multilabel-sentiment-analysis"


def fetch_dataset(limit: int = 1500) -> pd.DataFrame:
    with urllib.request.urlopen(HF_PARQUET_API, timeout=30) as resp:
        meta = json.loads(resp.read().decode("utf-8"))
    parquet_url = meta["parquet_files"][0]["url"]
    df = pd.read_parquet(parquet_url)
    if len(df) > limit:
        df = df.head(limit)
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(DATA_PATH, index=False)
    return df


if __name__ == "__main__":
    out = fetch_dataset(1500)
    print(f"Saved {len(out)} rows to {DATA_PATH}")
