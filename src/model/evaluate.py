"""
src/model/evaluate.py

Evaluates the trained Random Forest on the held-out NSL-KDD test set.
Reports accuracy, per-class precision/recall/F1, confusion matrix,
and checks results against the Chapter 6 target metrics.
"""

import os
import joblib
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    roc_auc_score,
)
from sklearn.preprocessing import label_binarize

from src.preprocessing.encode_scale import build_preprocessed_dataset

ARTIFACT_DIR = "models"
MODEL_PATH = os.path.join(ARTIFACT_DIR, "rf_classifier.joblib")

# Chapter 6 targets, for reference when interpreting results
TARGETS = {
    "accuracy": 0.96,
    "precision_recall_dos_probe": 0.95,
}


def evaluate(model, X_test, y_test):
    y_pred = model.predict(X_test)

    # --- Overall accuracy ---
    acc = accuracy_score(y_test, y_pred)
    print(f"\nOverall Test Accuracy: {acc:.4f}  (target: >= {TARGETS['accuracy']})")
    print("PASS" if acc >= TARGETS["accuracy"] else "BELOW TARGET")

    # --- Per-class precision/recall/F1 ---
    print("\n=== Classification Report ===")
    report = classification_report(y_test, y_pred, digits=4)
    print(report)

    # Explicit check on DoS/Probe precision & recall since those have named targets
    report_dict = classification_report(y_test, y_pred, output_dict=True)
    for cls in ["DoS", "Probe"]:
        if cls in report_dict:
            p, r = report_dict[cls]["precision"], report_dict[cls]["recall"]
            status = "PASS" if p >= 0.95 and r >= 0.95 else "BELOW TARGET"
            print(f"{cls}: precision={p:.4f}, recall={r:.4f}  [{status}]")

    # --- Confusion matrix ---
    labels = sorted(y_test.unique())
    cm = confusion_matrix(y_test, y_pred, labels=labels)

    plt.figure(figsize=(7, 6))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", xticklabels=labels, yticklabels=labels)
    plt.xlabel("Predicted")
    plt.ylabel("Actual")
    plt.title("Confusion Matrix — NSL-KDD Test Set")
    plt.tight_layout()
    plt.savefig("models/confusion_matrix.png")
    print("\nSaved confusion matrix plot to models/confusion_matrix.png")
    plt.show()

    # --- AUC-ROC (one-vs-rest, multi-class) ---
    try:
        y_test_bin = label_binarize(y_test, classes=labels)
        y_proba = model.predict_proba(X_test)
        auc = roc_auc_score(y_test_bin, y_proba, average="weighted", multi_class="ovr")
        print(f"\nWeighted AUC-ROC (OvR): {auc:.4f}")
    except Exception as e:
        print(f"Could not compute AUC-ROC: {e}")

    # --- False positive rate (attacks misclassified as Normal, and vice versa) ---
    # Here: FPR = (Normal traffic flagged as an attack) / (total actual Normal)
    normal_actual = (y_test == "Normal")
    normal_predicted_as_attack = normal_actual & (y_pred != "Normal")
    fpr = normal_predicted_as_attack.sum() / normal_actual.sum()
    print(f"\nFalse Positive Rate (Normal flagged as attack): {fpr:.4f}  (target: < 0.03)")
    print("PASS" if fpr < 0.03 else "ABOVE TARGET")

    return acc, report_dict, cm


def feature_importance(model, feature_cols, top_n=15):
    importances = model.feature_importances_
    idx = np.argsort(importances)[::-1][:top_n]

    print(f"\n=== Top {top_n} Feature Importances ===")
    for i in idx:
        print(f"{feature_cols[i]}: {importances[i]:.4f}")

    plt.figure(figsize=(8, 6))
    sns.barplot(x=importances[idx], y=[feature_cols[i] for i in idx])
    plt.title(f"Top {top_n} Feature Importances")
    plt.xlabel("Importance")
    plt.tight_layout()
    plt.savefig("models/feature_importance.png")
    print("Saved feature importance plot to models/feature_importance.png")
    plt.show()


if __name__ == "__main__":
    model = joblib.load(MODEL_PATH)
    feature_cols = joblib.load(os.path.join(ARTIFACT_DIR, "feature_cols.joblib"))

    _, _, X_test, _, _, y_test = build_preprocessed_dataset(
        "data/raw/KDDTrain+.txt",
        "data/raw/KDDTest+.txt",
    )

    evaluate(model, X_test, y_test)
    feature_importance(model, feature_cols)