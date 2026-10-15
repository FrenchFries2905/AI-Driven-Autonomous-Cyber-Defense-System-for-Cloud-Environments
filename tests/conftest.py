import os
import pytest

REQUIRED_ARTIFACTS = [
    "models/rf_classifier.joblib",
    "models/encoders.joblib",
    "models/scaler.joblib",
    "models/feature_cols.joblib",
]

VALID_CLASSES = {"Normal", "Probe", "DoS", "R2L", "U2R"}

# A hand-built, ordinary-looking HTTP connection (same example used in the API docs)
NORMAL_SAMPLE = {
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

# A flood-like connection: many half-open TCP connections (typical DoS shape)
FLOOD_SAMPLE = dict(NORMAL_SAMPLE, service="private", flag="S0", src_bytes=0, dst_bytes=0,
                    logged_in=0, count=250, srv_count=20, serror_rate=1.0, srv_serror_rate=1.0,
                    same_srv_rate=0.08, diff_srv_rate=0.07, dst_host_srv_count=15,
                    dst_host_same_srv_rate=0.06, dst_host_serror_rate=1.0, dst_host_srv_serror_rate=1.0)


@pytest.fixture(scope="session")
def require_model():
    missing = [p for p in REQUIRED_ARTIFACTS if not os.path.exists(p)]
    if missing:
        pytest.skip(f"model artifacts missing {missing}; run: python -m src.model.train")
