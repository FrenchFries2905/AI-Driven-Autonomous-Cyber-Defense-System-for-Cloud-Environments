"""
src/model/retrain.py

Retrain the Random Forest on NSL-KDD plus labeled flows recorded in the Docker lab, compare the
new model (challenger) with the live model (champion), and promote it only if it wins.

How the lab flows get their labels (ground truth, no guessing):
  - The attack scripts write the start and end time of every attack to lab/data/attack_windows.csv.
  - A recorded flow inside an attack window that did not come from the benign visitor is labeled
    with that attack's class (Probe or DoS).
  - Flows from the benign visitor are labeled Normal.
  - Anything else is dropped, because we cannot be sure what it is.

Run from the repo root:
    python -m src.model.retrain                 compare, and promote if the challenger wins
    python -m src.model.retrain --no-promote    compare only
    python -m src.model.retrain --force         promote even if a rule fails
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score

from src.model import registry
from src.preprocessing.encode_scale import encode_categorical
from src.preprocessing.loader import add_attack_category, load_nsl_kdd

# ---- promotion rules (all must hold)
MAX_LAB_FPR = 0.03          # false positives on benign lab traffic under 3 percent
MAX_NSL_FPR = 0.035         # false positives on KDDTest+ under 3.5 percent (or no worse than the champion)
MAX_NSL_F1_DROP = 0.03      # macro-F1 on KDDTest+ may not fall by more than this
WINDOW_MARGIN = 1.0         # seconds of slack around an attack window


# ------------------------------------------------------------------ data
def preprocess(df, encoders, scaler, feature_cols):
    """Encode and scale with the SAVED encoders and scaler, exactly like live prediction does."""
    X, _ = encode_categorical(df[feature_cols].copy(), encoders=encoders, fit=False)
    X[feature_cols] = scaler.transform(X[feature_cols])
    return X


def load_nsl(path):
    df = add_attack_category(load_nsl_kdd(path)).dropna(subset=["attack_category"])
    return df


def label_lab_flows(flows_csv, windows_csv, benign_ip=None):
    """Return the lab flows with a 'label' column plus the attack windows used."""
    if not os.path.exists(flows_csv):
        sys.exit(f"{flows_csv} not found. Run the lab first (see RETRAINING_GUIDE.md).")
    if not os.path.exists(windows_csv):
        sys.exit(f"{windows_csv} not found. Run attacks with the new attack scripts so their times are recorded.")
    flows = pd.read_csv(flows_csv)
    windows = pd.read_csv(windows_csv)
    if flows.empty or windows.empty:
        sys.exit("The lab files are empty. Run the lab and some attacks first.")

    inside = pd.Series(False, index=flows.index)
    window_label = pd.Series([None] * len(flows), index=flows.index, dtype=object)
    for w in windows.itertuples():
        mask = (flows["timestamp"] >= w.start - WINDOW_MARGIN) & (flows["timestamp"] <= w.end + WINDOW_MARGIN)
        inside |= mask
        window_label[mask] = w.label

    if benign_ip is None:
        candidates = flows.loc[~inside & (flows["flag"] == "SF"), "src_ip"]
        if candidates.empty:
            sys.exit("Could not find the benign visitor's address. Pass it with --benign-ip.")
        benign_ip = candidates.mode().iloc[0]
    print(f"benign visitor address: {benign_ip}")

    is_benign = flows["src_ip"] == benign_ip
    flows["label"] = None
    flows.loc[is_benign, "label"] = "Normal"
    attack_rows = inside & ~is_benign
    flows.loc[attack_rows, "label"] = window_label[attack_rows]
    return flows, windows, benign_ip


def split_lab(flows, windows):
    """Split by whole attack windows: the last run of each attack type becomes the lab test set."""
    windows = windows.sort_values("start").reset_index(drop=True)
    test_windows = []
    for attack, group in windows.groupby("attack"):   # per attack type, so every kind is tested on a run it never trained on
        if len(group) >= 2:
            n_test = max(1, int(round(len(group) * 0.3)))
            test_windows += list(group.tail(n_test).itertuples())
    labeled = flows.dropna(subset=["label"]).copy()
    if not test_windows:
        return labeled, labeled.iloc[0:0], []

    in_test = pd.Series(False, index=labeled.index)
    for w in test_windows:
        in_test |= (labeled["timestamp"] >= w.start - WINDOW_MARGIN) & (labeled["timestamp"] <= w.end + WINDOW_MARGIN)
    cutoff = min(w.start for w in test_windows) - WINDOW_MARGIN
    benign_after = (labeled["label"] == "Normal") & (labeled["timestamp"] >= cutoff)
    test_mask = (in_test & (labeled["label"] != "Normal")) | benign_after
    return labeled[~test_mask], labeled[test_mask], sorted({w.attack for w in test_windows})


# ---------------------------------------------------------------- metrics
def evaluate(model, X, y):
    pred = model.predict(X)
    y = np.asarray(y)
    present = sorted(set(y))
    normal, attacks = y == "Normal", y != "Normal"
    return {
        "records": int(len(y)),
        "accuracy": float(accuracy_score(y, pred)),
        "macro_f1": float(f1_score(y, pred, labels=present, average="macro", zero_division=0)),
        "attack_detection": float(np.mean(pred[attacks] != "Normal")) if attacks.any() else None,
        "false_positive_rate": float(np.mean(pred[normal] != "Normal")) if normal.any() else None,
        "recall": {c: round(float(np.mean(pred[y == c] == c)), 4) for c in present},
    }


def pct(v):
    return "n/a" if v is None else f"{100 * v:.1f}%"


def print_table(title, champ, chall):
    print(f"\n{title}  ({champ['records']} records)")
    print(f"  {'':24s}{'champion':>12s}{'challenger':>12s}")
    for label, key, fmt in [("accuracy", "accuracy", pct), ("macro-F1", "macro_f1", lambda v: f"{v:.3f}"),
                            ("attack detection rate", "attack_detection", pct),
                            ("false positive rate", "false_positive_rate", pct)]:
        print(f"  {label:24s}{fmt(champ[key]) if champ[key] is not None else 'n/a':>12s}"
              f"{fmt(chall[key]) if chall[key] is not None else 'n/a':>12s}")
    for cls in sorted(set(champ["recall"]) | set(chall["recall"])):
        print(f"  {'recall ' + cls:24s}{pct(champ['recall'].get(cls)):>12s}{pct(chall['recall'].get(cls)):>12s}")


# ------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="Retrain on lab flows and promote only if the new model wins")
    ap.add_argument("--flows", default="lab/data/flows.csv")
    ap.add_argument("--windows", default="lab/data/attack_windows.csv")
    ap.add_argument("--train-file", default="data/raw/KDDTrain+.txt")
    ap.add_argument("--test-file", default="data/raw/KDDTest+.txt")
    ap.add_argument("--models-dir", default=registry.MODELS_DIR)
    ap.add_argument("--benign-ip", default=None)
    ap.add_argument("--lab-weight", type=float, default=5.0, help="how much more a lab flow counts than an NSL-KDD record")
    ap.add_argument("--no-promote", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    md = args.models_dir

    encoders = joblib.load(os.path.join(md, "encoders.joblib"))
    scaler = joblib.load(os.path.join(md, "scaler.joblib"))
    feature_cols = joblib.load(os.path.join(md, "feature_cols.joblib"))
    registry.ensure_baseline_version(md)
    champ_path, champ_version = registry.resolve_live_model(md)
    champion = joblib.load(champ_path)
    champion.n_jobs = 1
    print(f"champion (live model): {champ_version}")

    # ---- lab flows with ground-truth labels
    flows, windows, benign_ip = label_lab_flows(args.flows, args.windows, args.benign_ip)
    labeled = flows.dropna(subset=["label"])
    print(f"\nlab flows: {len(flows)} recorded, {len(labeled)} labeled, {len(flows) - len(labeled)} dropped as unknown")
    print("labeled flows by class:", labeled["label"].value_counts().to_dict())
    print("attack runs recorded:", windows["attack"].value_counts().to_dict())
    lab_train, lab_test, test_types = split_lab(flows, windows)
    print(f"lab train: {len(lab_train)} flows | lab test: {len(lab_test)} flows (attack types in test: {test_types or 'none'})")
    if not (lab_train["label"] != "Normal").any():
        sys.exit("No labeled attack flows to learn from. Run attacks with the new attack scripts, then try again.")
    lab_test_ok = len(test_types) > 0 and (lab_test["label"] == "Normal").any()
    if not lab_test_ok:
        print("WARNING: not enough lab data for a test set. Run each attack at least twice. "
              "The new model can still be compared on KDDTest+, but will not be promoted automatically.")

    # ---- NSL-KDD
    print("\nloading NSL-KDD ...")
    nsl_train = load_nsl(args.train_file)
    nsl_test = load_nsl(args.test_file)
    X_nsl_train = preprocess(nsl_train, encoders, scaler, feature_cols)
    X_nsl_test = preprocess(nsl_test, encoders, scaler, feature_cols)
    y_nsl_train, y_nsl_test = nsl_train["attack_category"].values, nsl_test["attack_category"].values

    X_lab_train = preprocess(lab_train, encoders, scaler, feature_cols)
    y_lab_train = lab_train["label"].values

    # ---- train the challenger
    X_train = pd.concat([X_nsl_train, X_lab_train], ignore_index=True)
    y_train = np.concatenate([y_nsl_train, y_lab_train])
    weights = np.concatenate([np.ones(len(X_nsl_train)), np.full(len(X_lab_train), args.lab_weight)])
    print(f"training the challenger on {len(X_train)} records "
          f"({len(X_nsl_train)} NSL-KDD + {len(X_lab_train)} lab flows x weight {args.lab_weight}) ...")
    challenger = RandomForestClassifier(n_estimators=100, class_weight="balanced", random_state=42, n_jobs=-1)
    challenger.fit(X_train, y_train, sample_weight=weights)
    challenger.n_jobs = 1

    # ---- compare
    champ_nsl = evaluate(champion, X_nsl_test, y_nsl_test)
    chall_nsl = evaluate(challenger, X_nsl_test, y_nsl_test)
    print_table("KDDTest+ (benchmark, regression check)", champ_nsl, chall_nsl)
    champ_lab = chall_lab = None
    if lab_test_ok:
        X_lab_test = preprocess(lab_test, encoders, scaler, feature_cols)
        y_lab_test = lab_test["label"].values
        champ_lab = evaluate(champion, X_lab_test, y_lab_test)
        chall_lab = evaluate(challenger, X_lab_test, y_lab_test)
        print_table("Lab test (live traffic never used for training)", champ_lab, chall_lab)

    # ---- decide
    rules = []
    if lab_test_ok:
        rules += [
            ("lab macro-F1 improves", chall_lab["macro_f1"] > champ_lab["macro_f1"]),
            ("lab attack detection does not drop", (chall_lab["attack_detection"] or 0) >= (champ_lab["attack_detection"] or 0)),
            (f"lab false positives under {MAX_LAB_FPR:.0%}", (chall_lab["false_positive_rate"] or 0) < MAX_LAB_FPR),
        ]
    rules += [
        (f"KDDTest+ macro-F1 does not fall by more than {MAX_NSL_F1_DROP}",
         chall_nsl["macro_f1"] >= champ_nsl["macro_f1"] - MAX_NSL_F1_DROP),
        (f"KDDTest+ false positives under {MAX_NSL_FPR:.1%} or no worse than the champion",
         chall_nsl["false_positive_rate"] <= max(MAX_NSL_FPR, champ_nsl["false_positive_rate"])),
    ]
    print("\npromotion rules")
    for text, ok in rules:
        print(f"  [{'PASS' if ok else 'FAIL'}] {text}")
    all_pass = lab_test_ok and all(ok for _, ok in rules)

    # ---- save the challenger as a new version (kept even if rejected, for the record)
    new_number = max(registry.list_versions(md)) + 1
    joblib.dump(challenger, registry.version_path(new_number, md))
    report = {
        "version": f"v{new_number}", "created": datetime.now(timezone.utc).isoformat(), "champion": champ_version,
        "lab_weight": args.lab_weight, "lab_train_flows": int(len(lab_train)), "lab_test_flows": int(len(lab_test)),
        "kdd_test": {"champion": champ_nsl, "challenger": chall_nsl},
        "lab_test": {"champion": champ_lab, "challenger": chall_lab},
        "rules": [{"rule": t, "pass": bool(ok)} for t, ok in rules], "promoted": False,
    }

    if args.no_promote:
        decision = "not promoted (--no-promote)"
    elif all_pass or args.force:
        registry.set_live(new_number, md, note="retrained on NSL-KDD plus labeled lab flows",
                          metrics={"kdd_test_macro_f1": chall_nsl["macro_f1"],
                                   "lab_test_macro_f1": chall_lab["macro_f1"] if chall_lab else None})
        report["promoted"] = True
        decision = f"v{new_number} PROMOTED" + (" (forced)" if not all_pass else "")
    else:
        decision = f"v{new_number} REJECTED: the champion {champ_version} stays live"
    with open(os.path.join(md, registry.VERSIONS_DIR, f"rf_v{new_number}_report.json"), "w", encoding="utf8") as fh:
        json.dump(report, fh, indent=2)

    print(f"\nresult: {decision}")
    if report["promoted"]:
        print("Load it into the running system with:  docker compose restart api")
        print(f"Go back any time with:  python -m src.model.registry set {champ_version.lstrip('v')}")


if __name__ == "__main__":
    main()
