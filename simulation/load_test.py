"""
simulation/load_test.py

Measures throughput (samples per second) and latency.

  http mode:       many concurrent POST /predict requests against the running API
  inprocess mode:  no network; times (a) the single-sample pipeline and
                   (b) batch prediction over a whole matrix

Examples (from the repo root):
    python -m simulation.load_test --mode http --requests 500 --workers 16
    python -m simulation.load_test --mode http --requests 5000 --batch-size 250 --workers 4
    python -m simulation.load_test --mode inprocess
"""

import argparse
import time
from concurrent.futures import ThreadPoolExecutor

TARGET_SAMPLES_PER_SEC = 1000  # target from the project report


def percentile(values, pct):
    s = sorted(values)
    return s[max(0, int(round(pct / 100 * len(s))) - 1)]


def report(name, latencies_ms, wall_s, n_ok, n_err=0):
    rate = n_ok / wall_s if wall_s else 0
    print(f"\n--- {name} ---")
    print(f"samples ok: {n_ok}   errors: {n_err}   wall time: {wall_s:.2f}s")
    print(f"throughput: {rate:,.0f} samples/sec  (target >= {TARGET_SAMPLES_PER_SEC:,}: "
          f"{'PASS' if rate >= TARGET_SAMPLES_PER_SEC else 'BELOW TARGET'})")
    if latencies_ms:
        print(f"latency ms  p50 {percentile(latencies_ms, 50):.1f} | p95 {percentile(latencies_ms, 95):.1f} | "
              f"p99 {percentile(latencies_ms, 99):.1f} | max {max(latencies_ms):.1f}")


def run_http(args):
    import requests
    from src.preprocessing.loader import load_nsl_kdd

    df = load_nsl_kdd(args.test_file).sample(n=args.requests, replace=True, random_state=1)
    samples = df.drop(columns=["label", "difficulty_level"]).to_dict(orient="records")

    requests.get(f"{args.api_url}/health", timeout=3).raise_for_status()  # fail fast if the API is down

    if args.batch_size > 1:
        # one POST carries many samples; latency below is per batch request
        chunks = [samples[i:i + args.batch_size] for i in range(0, len(samples), args.batch_size)]

        def one_batch(chunk):
            t0 = time.perf_counter()
            try:
                r = requests.post(f"{args.api_url}/predict/batch", json=chunk, timeout=60)
                r.raise_for_status()
                return (time.perf_counter() - t0) * 1000, len(chunk)
            except requests.exceptions.RequestException:
                return None, 0

        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            out = list(pool.map(one_batch, chunks))
        wall = time.perf_counter() - start
        lat = [ms for ms, n in out if n]
        ok = sum(n for _, n in out)
        report(f"HTTP /predict/batch, batches of {args.batch_size}, {args.workers} workers",
               lat, wall, ok, len(samples) - ok)
        return

    def one(sample):
        t0 = time.perf_counter()
        try:
            r = requests.post(f"{args.api_url}/predict", json=sample, timeout=30)
            r.raise_for_status()
            return (time.perf_counter() - t0) * 1000, True
        except requests.exceptions.RequestException:
            return None, False

    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        out = list(pool.map(one, samples))
    wall = time.perf_counter() - start

    lat = [ms for ms, ok in out if ok]
    report(f"HTTP /predict, {args.workers} workers", lat, wall, len(lat), len(out) - len(lat))


def run_inprocess(args):
    from src.preprocessing.loader import load_nsl_kdd
    from src.preprocessing.pipeline import ThreatDetectionPipeline
    from src.preprocessing.encode_scale import build_preprocessed_dataset

    df = load_nsl_kdd(args.test_file)
    samples = df.drop(columns=["label", "difficulty_level"]).to_dict(orient="records")[: args.requests]

    pipe = ThreatDetectionPipeline()
    lat = []
    start = time.perf_counter()
    for s in samples:
        t0 = time.perf_counter()
        pipe.predict(s)
        lat.append((time.perf_counter() - t0) * 1000)
    wall = time.perf_counter() - start
    report("In-process, one sample at a time", lat, wall, len(samples))

    _, _, X_test, _, _, _ = build_preprocessed_dataset(args.train_file, args.test_file)
    model = pipe.model
    start = time.perf_counter()
    model.predict(X_test)
    wall = time.perf_counter() - start
    report(f"In-process, batch of {len(X_test):,}", [], wall, len(X_test))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["http", "inprocess"], default="http")
    ap.add_argument("--api-url", default="http://127.0.0.1:8000")
    ap.add_argument("--requests", type=int, default=500)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--batch-size", type=int, default=1, help="above 1: send batches to /predict/batch")
    ap.add_argument("--test-file", default="data/raw/KDDTest+.txt")
    ap.add_argument("--train-file", default="data/raw/KDDTrain+.txt")
    args = ap.parse_args()
    (run_http if args.mode == "http" else run_inprocess)(args)


if __name__ == "__main__":
    main()
