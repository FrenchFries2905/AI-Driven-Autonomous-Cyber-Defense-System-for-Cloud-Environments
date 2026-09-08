"""
src/preprocessing/encode_scale.py

Encodes categorical features and scales numeric features for NSL-KDD.
Saves the fitted encoders/scaler so the exact same transforms can be
applied later at inference time (Phase 3).
"""

import os
import joblib
import pandas as pd
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import train_test_split

from src.preprocessing.loader import load_nsl_kdd, add_attack_category

CATEGORICAL_COLS = ["protocol_type", "service", "flag"]
DROP_COLS = ["label", "difficulty_level"]  # not used as model features
TARGET_COL = "attack_category"

ARTIFACT_DIR = "models"


def encode_categorical(df: pd.DataFrame, encoders: dict = None, fit: bool = True):
    """
    Label-encode protocol_type, service, flag.
    If fit=True, fits new encoders. If fit=False, uses the provided encoders
    (for transforming test data / new inference samples with the SAME encoding).
    """
    df = df.copy()
    encoders = encoders or {}

    for col in CATEGORICAL_COLS:
        if fit:
            le = LabelEncoder()
            df[col] = le.fit_transform(df[col])
            encoders[col] = le
        else:
            import numpy as np
            le = encoders[col]
            # Handle unseen categories at test/inference time gracefully
            df[col] = df[col].apply(lambda x: x if x in le.classes_ else "unknown")
            if "unknown" not in le.classes_:
                 le.classes_ = np.array(list(le.classes_) + ["unknown"])
            df[col] = le.transform(df[col])

    return df, encoders


def scale_numeric(df: pd.DataFrame, feature_cols: list, scaler: StandardScaler = None, fit: bool = True):
    """
    Standard-scale all numeric feature columns.
    """
    df = df.copy()
    if fit:
        scaler = StandardScaler()
        df[feature_cols] = scaler.fit_transform(df[feature_cols])
    else:
        df[feature_cols] = scaler.transform(df[feature_cols])
    return df, scaler


def build_preprocessed_dataset(train_path: str, test_path: str):
    # 1. Load + map labels
    train_df = add_attack_category(load_nsl_kdd(train_path))
    test_df = add_attack_category(load_nsl_kdd(test_path))

    # Drop any rows that failed label mapping (rare/unseen labels)
    train_df = train_df.dropna(subset=[TARGET_COL])
    test_df = test_df.dropna(subset=[TARGET_COL])

    # 2. Encode categorical features (fit on train, apply same encoders to test)
    train_df, encoders = encode_categorical(train_df, fit=True)
    test_df, _ = encode_categorical(test_df, encoders=encoders, fit=False)

    # 3. Identify feature columns (everything except label/difficulty/target)
    feature_cols = [c for c in train_df.columns if c not in DROP_COLS + [TARGET_COL]]

    # 4. Scale numeric features (fit on train, apply same scaler to test)
    train_df, scaler = scale_numeric(train_df, feature_cols, fit=True)
    test_df, _ = scale_numeric(test_df, feature_cols, scaler=scaler, fit=False)

    # 5. Split train into train/validation (80/20), stratified by class
    X = train_df[feature_cols]
    y = train_df[TARGET_COL]

    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    X_test = test_df[feature_cols]
    y_test = test_df[TARGET_COL]

    # 6. Save fitted encoders + scaler for reuse in Phase 3 (inference pipeline)
    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    joblib.dump(encoders, os.path.join(ARTIFACT_DIR, "encoders.joblib"))
    joblib.dump(scaler, os.path.join(ARTIFACT_DIR, "scaler.joblib"))
    joblib.dump(feature_cols, os.path.join(ARTIFACT_DIR, "feature_cols.joblib"))

    print(f"Saved encoders, scaler, and feature_cols to {ARTIFACT_DIR}/")
    print(f"Train: {X_train.shape}, Val: {X_val.shape}, Test: {X_test.shape}")

    return X_train, X_val, X_test, y_train, y_val, y_test


if __name__ == "__main__":
    X_train, X_val, X_test, y_train, y_val, y_test = build_preprocessed_dataset(
        "data/raw/KDDTrain+.txt",
        "data/raw/KDDTest+.txt",
    )

    print("\nClass distribution in y_train:")
    print(y_train.value_counts())
