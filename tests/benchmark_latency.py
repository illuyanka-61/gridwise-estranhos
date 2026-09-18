"""Latency benchmarking across all sample cases."""

import json
import time
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

SAMPLE_FILE = Path("sample_cases/BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json")


def benchmark():
    with open(SAMPLE_FILE, encoding="utf-8") as f:
        data = json.load(f)

    cases = data["cases"]
    latencies = []

    print(f"Benchmarking {len(cases)} sample cases...")
    for case in cases:
        inp = case["input"]
        case_id = case["id"]

        t0 = time.perf_counter()
        resp = client.post("/optimize-energy", json=inp)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        latencies.append(elapsed_ms)

        assert resp.status_code == 200, f"Case {case_id} failed: {resp.text}"
        print(f"  [{case_id}] {elapsed_ms:6.2f} ms | Status: {resp.status_code}")

    latencies.sort()
    p50 = latencies[len(latencies) // 2]
    p95 = latencies[int(len(latencies) * 0.95)]
    avg = sum(latencies) / len(latencies)

    print("\n--- Latency Benchmark Results ---")
    print(f"Min:  {min(latencies):6.2f} ms")
    print(f"Avg:  {avg:6.2f} ms")
    print(f"P50:  {p50:6.2f} ms")
    print(f"P95:  {p95:6.2f} ms")
    print(f"Max:  {max(latencies):6.2f} ms")
    print("---------------------------------")


if __name__ == "__main__":
    benchmark()
