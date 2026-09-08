"""
src/preprocessing/pipeline.py

Reusable inference pipeline: takes a raw sample (single network connection
record, same 41 features as NSL-KDD, no label), applies the SAME
encoders/scaler fitted in Phase 1, and returns a classification + confidence.

This is what the FastAPI backend (Phase 4) will call for every incoming
telemetry sample.
"""

import os
import time
import joblib
import numpy as np
import pandas as pd

ARTIFACT_DIR = "models"

CATEGORICAL_COLS = ["protocol_type", "service", "flag"]


class ThreatDetectionPipeline:
    """
    Loads the trained model + fitted encoders/scaler once, then exposes
    a fast predict() method for repeated use (e.g. inside an API server).
    """

    def __init__(self, artifact_dir: str = ARTIFACT_DIR):
        self.model = joblib.load(os.path.join(artifact_dir, "rf_classifier.joblib"))
        self.model.n_jobs = 1  # avoid multiprocessing overhead per single-sample call

        self.encoders = joblib.load(os.path.join(artifact_dir, "encoders.joblib"))
        self.scaler = joblib.load(os.path.join(artifact_dir, "scaler.joblib"))
        self.feature_cols = joblib.load(os.path.join(artifact_dir, "feature_cols.joblib"))

    def _preprocess(self, sample: dict) -> pd.DataFrame:
        """
        Convert a raw sample (dict of the 41 NSL-KDD features) into the
        encoded + scaled feature vector the model expects.
        """
        df = pd.DataFrame([sample])

        # Make sure every expected feature column exists (fill missing with 0)
        for col in self.feature_cols:
            if col not in df.columns:
                df[col] = 0

        # Encode categorical columns using the SAME fitted encoders from training
        for col in CATEGORICAL_COLS:
            le = self.encoders[col]
            val = df.at[0, col]
            if val not in le.classes_:
                val = "unknown" if "unknown" in le.classes_ else le.classes_[0]
            df[col] = le.transform([val])

        df = df[self.feature_cols]  # enforce correct column order

        # Scale using the SAME fitted scaler from training
        df[self.feature_cols] = self.scaler.transform(df[self.feature_cols])

        return df

    def predict(self, sample: dict) -> dict:
        """
        Run one sample through preprocessing + classification.
        Returns classification, confidence, per-class probabilities, and latency.
        """
        start = time.perf_counter()

        X = self._preprocess(sample)
        proba = self.model.predict_proba(X)[0]
        classes = self.model.classes_

        pred_idx = int(np.argmax(proba))
        predicted_class = classes[pred_idx]
        confidence = float(proba[pred_idx])

        latency_ms = (time.perf_counter() - start) * 1000

        return {
            "predicted_class": predicted_class,
            "confidence": round(confidence, 4),
            "class_probabilities": {cls: round(float(p), 4) for cls, p in zip(classes, proba)},
            "latency_ms": round(latency_ms, 2),
        }


if __name__ == "__main__":
    # Quick manual test with a made-up "normal-looking" sample
    pipeline = ThreatDetectionPipeline()

    sample = {
        "duration": 0, "protocol_type": "tcp", "service": "http", "flag": "SF",
        "src_bytes": 200, "dst_bytes": 300, "land": 0, "wrong_fragment": 0,
        "urgent": 0, "hot": 0, "num_failed_logins": 0, "logged_in": 1,
        "num_compromised": 0, "root_shell": 0, "su_attempted": 0, "num_root": 0,
        "num_file_creations": 0, "num_shells": 0, "num_access_files": 0,
        "num_outbound_cmds": 0, "is_host_login": 0, "is_guest_login": 0,
        "count": 5, "srv_count": 5, "serror_rate": 0.0, "srv_serror_rate": 0.0,
        "rerror_rate": 0.0, "srv_rerror_rate": 0.0, "same_srv_rate": 1.0,
        "diff_srv_rate": 0.0, "srv_diff_host_rate": 0.0, "dst_host_count": 255,
        "dst_host_srv_count": 255, "dst_host_same_srv_rate": 1.0,
        "dst_host_diff_srv_rate": 0.0, "dst_host_same_src_port_rate": 0.0,
        "dst_host_srv_diff_host_rate": 0.0, "dst_host_serror_rate": 0.0,
        "dst_host_srv_serror_rate": 0.0, "dst_host_rerror_rate": 0.0,
        "dst_host_srv_rerror_rate": 0.0,
    }

    result = pipeline.predict(sample)
    print(result)