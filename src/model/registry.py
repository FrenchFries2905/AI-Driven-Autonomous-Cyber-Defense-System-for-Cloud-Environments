"""
src/model/registry.py

A tiny model registry: numbered model files plus a pointer saying which one is live.

    models/rf_classifier.joblib        the original model (becomes version 1)
    models/versions/rf_v1.joblib       numbered copies, one per trained model
    models/versions/rf_v2.joblib
    models/live.json                   {"version": "v2", "path": "versions/rf_v2.joblib", ...}

The API reads live.json when it starts, so promoting or rolling back a model means
changing the pointer and restarting the API. Nothing is ever overwritten.

Command line:
    python -m src.model.registry list          show versions and which one is live
    python -m src.model.registry set 1         make version 1 live again (rollback)
"""

import json
import os
import shutil
import sys
from datetime import datetime, timezone

MODELS_DIR = "models"
VERSIONS_DIR = "versions"
POINTER = "live.json"
LEGACY_MODEL = "rf_classifier.joblib"


def read_pointer(models_dir=MODELS_DIR):
    path = os.path.join(models_dir, POINTER)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf8") as fh:
        return json.load(fh)


def resolve_live_model(models_dir=MODELS_DIR):
    """Return (path of the live model file, its version name such as 'v2')."""
    pointer = read_pointer(models_dir)
    if pointer:
        path = os.path.join(models_dir, pointer["path"])
        if os.path.exists(path):
            return path, pointer["version"]
        print(f"WARNING: {path} named in {POINTER} is missing; falling back to {LEGACY_MODEL}")
    return os.path.join(models_dir, LEGACY_MODEL), "v1"


def list_versions(models_dir=MODELS_DIR):
    folder = os.path.join(models_dir, VERSIONS_DIR)
    if not os.path.isdir(folder):
        return []
    numbers = []
    for name in os.listdir(folder):
        if name.startswith("rf_v") and name.endswith(".joblib"):
            try:
                numbers.append(int(name[4:-7]))
            except ValueError:
                pass
    return sorted(numbers)


def version_path(number, models_dir=MODELS_DIR):
    return os.path.join(models_dir, VERSIONS_DIR, f"rf_v{number}.joblib")


def set_live(number, models_dir=MODELS_DIR, note=None, metrics=None):
    if not os.path.exists(version_path(number, models_dir)):
        raise FileNotFoundError(f"version v{number} does not exist in {models_dir}/{VERSIONS_DIR}")
    pointer = {
        "version": f"v{number}",
        "path": f"{VERSIONS_DIR}/rf_v{number}.joblib",
        "promoted_at": datetime.now(timezone.utc).isoformat(),
        "note": note,
        "metrics": metrics,
    }
    with open(os.path.join(models_dir, POINTER), "w", encoding="utf8") as fh:
        json.dump(pointer, fh, indent=2)
    return pointer


def ensure_baseline_version(models_dir=MODELS_DIR):
    """If no numbered versions exist yet, save the current model as v1 so it can be rolled back to."""
    os.makedirs(os.path.join(models_dir, VERSIONS_DIR), exist_ok=True)
    if list_versions(models_dir):
        return
    legacy = os.path.join(models_dir, LEGACY_MODEL)
    if not os.path.exists(legacy):
        raise FileNotFoundError(f"{legacy} not found. Train the original model first: python -m src.model.train")
    shutil.copy2(legacy, version_path(1, models_dir))
    if read_pointer(models_dir) is None:
        set_live(1, models_dir, note="original model trained on NSL-KDD")


def main(argv):
    if len(argv) >= 2 and argv[1] == "list":
        ensure_baseline_version()
        live = (read_pointer() or {}).get("version")
        for n in list_versions():
            print(f"v{n}" + ("   <- live" if live == f"v{n}" else ""))
        return 0
    if len(argv) == 3 and argv[1] == "set":
        ensure_baseline_version()
        number = int(argv[2].lstrip("vV"))
        set_live(number, note="set by hand")
        print(f"v{number} is now live. Restart the API to load it: docker compose restart api")
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
