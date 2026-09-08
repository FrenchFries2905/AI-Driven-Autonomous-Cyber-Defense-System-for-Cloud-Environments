"""
src/model/train.py

Trains a Random Forest classifier on the preprocessed NSL-KDD data,
tunes hyperparameters, and saves the final model.
"""

import os
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import RandomizedSearchCV

from src.preprocessing.encode_scale import build_preprocessed_dataset

ARTIFACT_DIR = "models"
MODEL_PATH = os.path.join(ARTIFACT_DIR, "rf_classifier.joblib")


def train_baseline(X_train, y_train) -> RandomForestClassifier:
    """Quick baseline model — good sanity check before tuning."""
    model = RandomForestClassifier(
        n_estimators=100,
        random_state=42,
        n_jobs=-1,
        class_weight="balanced",  # helps with U2R/R2L being tiny classes
    )
    model.fit(X_train, y_train)
    return model


def tune_hyperparameters(X_train, y_train) -> RandomForestClassifier:
    """
    Random search over key hyperparameters.
    Swap to GridSearchCV if you want an exhaustive search instead
    (slower, but more thorough) once you've narrowed the range.
    """
    param_dist = {
        "n_estimators": [100, 200, 300, 400],
        "max_depth": [None, 10, 20, 30, 40],
        "min_samples_split": [2, 5, 10],
        "min_samples_leaf": [1, 2, 4],
        "max_features": ["sqrt", "log2"],
    }

    base_model = RandomForestClassifier(
        random_state=42, n_jobs=-1, class_weight="balanced"
    )

    search = RandomizedSearchCV(
        estimator=base_model,
        param_distributions=param_dist,
        n_iter=20,          # number of random combinations to try
        cv=3,               # 3-fold cross-validation
        scoring="f1_weighted",
        n_jobs=-1,
        random_state=42,
        verbose=2,
    )

    search.fit(X_train, y_train)

    print("Best params:", search.best_params_)
    print("Best CV F1 (weighted):", search.best_score_)

    return search.best_estimator_


if __name__ == "__main__":
    X_train, X_val, X_test, y_train, y_val, y_test = build_preprocessed_dataset(
        "data/raw/KDDTrain+.txt",
        "data/raw/KDDTest+.txt",
    )

    print("\n=== Training baseline model ===")
    baseline_model = train_baseline(X_train, y_train)
    baseline_val_acc = baseline_model.score(X_val, y_val)
    print(f"Baseline validation accuracy: {baseline_val_acc:.4f}")

    print("\n=== Hyperparameter tuning ===")
    tuned_model = tune_hyperparameters(X_train, y_train)
    tuned_val_acc = tuned_model.score(X_val, y_val)
    print(f"Tuned validation accuracy: {tuned_val_acc:.4f}")

    # Keep whichever model performs better on validation
    final_model = tuned_model if tuned_val_acc >= baseline_val_acc else baseline_model
    print(f"\nSelected {'tuned' if final_model is tuned_model else 'baseline'} model.")

    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    joblib.dump(final_model, MODEL_PATH)
    print(f"Saved final model to {MODEL_PATH}")