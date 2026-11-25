"""ML Engine: Trains & benchmarks Logistic Regression, Decision Tree, Uncalibrated CatBoost, and Platt-Calibrated CatBoost + SHAP TreeExplainer."""
import time
from typing import Dict, Any, List
import numpy as np
import pandas as pd
import shap
from catboost import CatBoostClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score, brier_score_loss
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

from app.services.dataset import FEATURE_COLUMNS, build_cleaned_dataset


def classify_risk_tier(prob: float) -> str:
    pct = prob * 100.0
    if pct <= 25.0:
        return "Optimal"
    if pct <= 50.0:
        return "Mild Drift"
    if pct <= 75.0:
        return "Moderate Slump"
    return "Severe Disengagement"


class EventPulseMLEngine:
    def __init__(self) -> None:
        self.trained = False
        self.benchmarks: List[Dict[str, Any]] = []
        self.base_catboost: CatBoostClassifier | None = None
        self.calibrated_catboost: CalibratedClassifierCV | None = None
        self.explainer: shap.TreeExplainer | None = None
        self.dataset_size: int = 0

    def train(self) -> None:
        df = build_cleaned_dataset()
        self.dataset_size = len(df)
        X = df[FEATURE_COLUMNS].values
        y = df["disengagement_target"].values

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        models = {
            "Logistic Regression": make_pipeline(
                StandardScaler(), LogisticRegression(max_iter=1000, random_state=42)
            ),
            "Decision Tree (max_depth=5)": DecisionTreeClassifier(
                max_depth=5, random_state=42
            ),
            "CatBoost (Uncalibrated)": CatBoostClassifier(
                iterations=100, depth=6, learning_rate=0.1, verbose=0, random_seed=42
            ),
            "CatBoost + Platt (Calibrated)": CalibratedClassifierCV(
                estimator=CatBoostClassifier(
                    iterations=100, depth=6, learning_rate=0.1, verbose=0, random_seed=42
                ),
                method="sigmoid",
                cv=5,
            ),
        }

        results = []
        for name, model in models.items():
            t0 = time.perf_counter()
            model.fit(X_train, y_train)
            train_ms = (time.perf_counter() - t0) * 1000.0

            probs = model.predict_proba(X_test)[:, 1]
            preds = (probs >= 0.5).astype(int)
            results.append({
                "model": name,
                "accuracy": round(float(accuracy_score(y_test, preds)), 4),
                "f1": round(float(f1_score(y_test, preds)), 4),
                "roc_auc": round(float(roc_auc_score(y_test, probs)), 4),
                "brier_score": round(float(brier_score_loss(y_test, probs)), 4),
                "train_ms": round(train_ms, 2),
            })

            if name == "CatBoost (Uncalibrated)":
                self.base_catboost = model
            elif name == "CatBoost + Platt (Calibrated)":
                self.calibrated_catboost = model

        self.benchmarks = results
        self.explainer = shap.TreeExplainer(self.base_catboost)
        self.trained = True

    def predict_with_shap(self, features: Dict[str, float]) -> Dict[str, Any]:
        if not self.trained:
            self.train()

        t0 = time.perf_counter()
        row = np.array([[float(features.get(col, 0.0)) for col in FEATURE_COLUMNS]])
        prob = float(self.calibrated_catboost.predict_proba(row)[0, 1])
        shap_vals = self.explainer.shap_values(row)
        if isinstance(shap_vals, list):
            shap_arr = np.array(shap_vals[1])[0]
        else:
            shap_arr = np.array(shap_vals)[0]
        latency_ms = (time.perf_counter() - t0) * 1000.0

        attributions = [
            {"feature": col, "shap_value": round(float(val), 4), "value": round(float(row[0, i]), 4)}
            for i, (col, val) in enumerate(zip(FEATURE_COLUMNS, shap_arr))
        ]
        attributions.sort(key=lambda x: abs(x["shap_value"]), reverse=True)

        return {
            "risk_probability": round(prob, 4),
            "risk_percent": round(prob * 100.0, 1),
            "risk_tier": classify_risk_tier(prob),
            "inference_latency_ms": round(latency_ms, 2),
            "top_shap_attributions": attributions[:6],
        }


ml_engine = EventPulseMLEngine()
