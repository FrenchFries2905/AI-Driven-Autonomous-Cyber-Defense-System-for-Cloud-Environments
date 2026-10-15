"""
simulation/replay_stream.py

Simulates live telemetry: shuffled NSL-KDD test records are sent to the API
one at a time at random intervals, WITHOUT their labels. The true labels are
kept only on this side, so the run can be scored end to end afterwards.

Start the API first, then (from the repo root):
    python -m simulation.replay_stream --count 100
"""

import argparse
import json
import random
import time

import requests

from src.preprocessing.loader import load_nsl_kdd, add_attack_category

JITTER_COLS = ["duration", "src_bytes", "dst_bytes", "count", "srv_count",
               "dst_host_count", "dst_host_srv_count"]
DROP_COLS = ["label", "difficulty_level", "attack_category"]


def jitter(sample: dict, pct: float, rng: random.Random) -> dict:
    """Perturb a few count/byte fields by up to +/- pct so records are not byte-identical to the dataset."""
    out = dict(sample)
    for col in JITTER_COLS:
        if out[col]:
            out[col] = max(0, int(round(out[col] * (1 + rng.uniform(-pct, pct)))))
    return out


def fake_ip(rng: random.Random) -> str:
    return f"10.{rng.randint(0, 9)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}"


def main():
    ap = argparse.ArgumentParser(description="Replay NSL-KDD test records against the API")
    ap.add_argument("--api-url", default="http://127.0.0.1:8000")
    ap.add_argument("--test-file", default="data/raw/KDDTest+.txt")
    ap.add_argument("--count", type=int, default=100, help="number of records to send")
    ap.add_argument("--min-delay", type=float, default=0.3, help="min seconds between records")
    ap.add_argument("--max-delay", type=float, default=2.0, help="max seconds between records")
    ap.add_argument("--jitter", type=float, default=0.0, help="e.g. 0.1 = perturb counts/bytes by up to 10 percent")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--report", default="simulation/last_run.json", help="where to save the run summary")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    df = add_attack_category(load_nsl_kdd(args.test_file)).dropna(subset=["attack_category"])
    df = df.sample(n=min(args.count, len(df)), random_state=args.seed)  # shuffled order

    truth = df["attack_category"].tolist()  # kept locally, never sent
    samples = df.drop(columns=DROP_COLS).to_dict(orient="records")

    try:
        requests.get(f"{args.api_url}/health", timeout=3).raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise SystemExit(f"API not reachable at {args.api_url}: {exc}\n"
                         "Start it with: uvicorn src.api.main:app --reload")

    session = requests.Session()
    results, failures = [], 0
    print(f"Replaying {len(samples)} records to {args.api_url} (delay {args.min_delay}-{args.max_delay}s)\n")

    for i, (sample, actual) in enumerate(zip(samples, truth), start=1):
        if args.jitter:
            sample = jitter(sample, args.jitter, rng)
        payload = {"sample": sample, "source_ip": fake_ip(rng),
                   "instance_id": "web-01", "service_id": "auth-svc"}
        t0 = time.perf_counter()
        try:
            resp = session.post(f"{args.api_url}/respond", json=payload, timeout=30)
            resp.raise_for_status()
            r = resp.json()
        except requests.exceptions.RequestException as exc:
            failures += 1
            print(f"[{i:>4}] request failed: {exc}")
            continue
        round_trip_ms = (time.perf_counter() - t0) * 1000

        results.append({"actual": actual, "predicted": r["predicted_class"], "action": r["action"],
                        "confidence": r["confidence"], "mttd_ms": r["mttd_ms"], "mttr_ms": r["mttr_ms"],
                        "round_trip_ms": round_trip_ms})
        flag = "ok " if actual == r["predicted_class"] else "MISS"
        print(f"[{i:>4}] {flag} actual={actual:<7} predicted={r['predicted_class']:<7} "
              f"conf={r['confidence']:.2f} action={r['action']:<16} MTTR={r['mttr_ms']:.0f}ms")

        if i < len(samples):
            time.sleep(rng.uniform(args.min_delay, args.max_delay))

    if not results:
        raise SystemExit("No successful responses, nothing to summarize.")

    # ------------------------------------------------------------ scoring
    n = len(results)
    correct = sum(r["actual"] == r["predicted"] for r in results)
    normals = [r for r in results if r["actual"] == "Normal"]
    attacks = [r for r in results if r["actual"] != "Normal"]
    fpr = sum(r["predicted"] != "Normal" for r in normals) / len(normals) if normals else None
    det = sum(r["predicted"] != "Normal" for r in attacks) / len(attacks) if attacks else None

    per_class = {}
    for cls in sorted({r["actual"] for r in results}):
        rows = [r for r in results if r["actual"] == cls]
        per_class[cls] = {"records": len(rows),
                          "recall_pct": round(100 * sum(r["predicted"] == cls for r in rows) / len(rows), 1)}

    summary = {
        "records_sent": len(samples), "responses": n, "failed_requests": failures,
        "accuracy_pct": round(100 * correct / n, 2),
        "false_positive_rate_pct": None if fpr is None else round(100 * fpr, 2),
        "attack_detection_rate_pct": None if det is None else round(100 * det, 2),
        "per_class": per_class,
        "mean_round_trip_ms": round(sum(r["round_trip_ms"] for r in results) / n, 1),
    }
    try:
        summary["server_metrics"] = requests.get(f"{args.api_url}/metrics", timeout=5).json()
    except requests.exceptions.RequestException:
        pass

    print("\n=== End-to-end summary (scored against the hidden labels) ===")
    print(json.dumps({k: v for k, v in summary.items() if k != "server_metrics"}, indent=2))
    if "server_metrics" in summary:
        m = summary["server_metrics"]
        print(f"\nServer MTTD mean {m['mttd_ms']['mean']} ms | MTTR mean {m['mttr_ms']['mean']} ms | "
              f"SLO (MTTR) {m['slo_compliance']['mttr_within_target_pct']}% | uptime {m['uptime_pct']}%")
    if fpr is not None:
        print(f"False positive rate {summary['false_positive_rate_pct']}% (target < 3%): "
              f"{'PASS' if fpr < 0.03 else 'ABOVE TARGET'}")

    with open(args.report, "w", encoding="utf8") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSaved summary to {args.report}")


if __name__ == "__main__":
    main()
