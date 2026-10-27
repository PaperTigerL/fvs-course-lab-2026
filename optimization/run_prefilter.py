# -*- coding: utf-8 -*-
"""Compare baseline GateANN with the low-selectivity prefilter path.

Baseline: original binary (no prefilter).
Optimized: same binary with prefilter code; P is controlled by
GATEANN_PREFILTER_P, and only labels with <= MAX_LABEL nodes use it.
"""
from __future__ import annotations

import csv
import os
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path("/home/user/fvs-course-lab")
SYSTEM = ROOT / "systems/GateANN-public"
BASE_BIN = SYSTEM / "build/tests/search_disk_index_yfcc.orig"
AUG_BIN = SYSTEM / "build/tests/search_disk_index_yfcc"
INDEX = ROOT / "course_runs/indices/gateann/formal_1000000/yfcc"
TIER = ROOT / "datasets/yfcc_course_v1/formal_1000000"
OUT = ROOT / "course_runs/optimization/prefilter"
LOGS = OUT / "logs"
OUT.mkdir(parents=True, exist_ok=True)
LOGS.mkdir(parents=True, exist_ok=True)

ROUNDS = 3
LINE = re.compile(r"^\s*(\d+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s*$")
RSS = re.compile(r"MAXRSS_KB=(\d+)")


def run_one(binary: Path, bucket: str, L: int, variant: str, p: int, rnd: int):
    workload = TIER / "workloads" / bucket
    cmd = [
        "/usr/bin/time", "-f", "MAXRSS_KB=%M",
        str(binary), "uint8", str(INDEX), "1", "8",
        str(workload / "query.u8bin"),
        str(TIER / "base.metadata.spmat"),
        str(workload / "query.metadata.spmat"),
        str(workload / "ground_truth.ids.ibin"),
        "10", "l2", "pq", "8", "0", "0", "32", str(L),
    ]
    env = os.environ.copy()
    if variant == "prefilter":
        env["GATEANN_PREFILTER_P"] = str(p)
        env["GATEANN_PREFILTER_MAX_LABEL"] = "12000"
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=600)
    elapsed = time.time() - t0
    log = (proc.stdout or "") + "\n" + (proc.stderr or "")
    (LOGS / f"{variant}_P{p}_{bucket}_L{L}_r{rnd}.log").write_text(log, encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(f"{variant} P={p} {bucket} L={L} r={rnd} rc={proc.returncode}\n{log[-2000:]}")
    row = None
    for line in (proc.stdout or "").splitlines():
        m = LINE.match(line)
        if m and int(m.group(1)) == L:
            row = {
                "round": rnd, "variant": variant, "P": p, "bucket": bucket, "L": L,
                "qps": float(m.group(2)),
                "recall_percent": float(m.group(3)) * 100.0,
                "mean_ios": float(m.group(4)),
                "filter_skips": float(m.group(5)),
                "io_time_us": float(m.group(6)),
                "tunnel_time_us": float(m.group(7)),
                "process_time_us": float(m.group(8)),
                "maxrss_kb": int(RSS.search(proc.stderr or "").group(1)) if RSS.search(proc.stderr or "") else "",
                "elapsed_seconds": round(elapsed, 3),
                "log": str(LOGS / f"{variant}_P{p}_{bucket}_L{L}_r{rnd}.log"),
            }
            break
    if row is None:
        raise RuntimeError(f"cannot parse {variant} P={p} {bucket} L={L}\n{log[-2000:]}")
    row["mean_latency_us"] = 1_000_000.0 / row["qps"] if row["qps"] else ""
    print(f"{variant:10s} P={p:<4d} {bucket:6s} L={L:<4d} r={rnd} "
          f"recall={row['recall_percent']:.2f}% ios={row['mean_ios']:.2f} "
          f"lat={row['mean_latency_us']:.0f}us", flush=True)
    return row


def main():
    for path in (BASE_BIN, AUG_BIN, Path(str(INDEX) + "_disk.index"), TIER):
        if not path.exists():
            sys.exit(f"missing {path}")

    rows = []
    # Low: full P sweep at L=320, 3 rounds; baseline plus 5 P values.
    p_values = [8, 16, 32, 64, 128]
    for rnd in range(1, ROUNDS + 1):
        variants = ["baseline"] + [("prefilter", p) for p in p_values]
        if rnd % 2 == 0:
            variants = variants[::-1]
        for v in variants:
            if v == "baseline":
                rows.append(run_one(BASE_BIN, "low", 320, "baseline", 0, rnd))
            else:
                rows.append(run_one(AUG_BIN, "low", 320, "prefilter", v[1], rnd))

    # Low L scan at the recommended P=32 and baseline (3 rounds).
    for rnd in range(1, ROUNDS + 1):
        for L in (160, 640):
            order = [("baseline", 0), ("prefilter", 32)]
            if rnd % 2 == 0:
                order = order[::-1]
            for variant, p in order:
                binary = BASE_BIN if variant == "baseline" else AUG_BIN
                rows.append(run_one(binary, "low", L, variant, p, rnd))

    # Medium/High: confirm the prefilter branch is not triggered (1 round).
    for bucket in ("medium", "high"):
        for variant, p in (("baseline", 0), ("prefilter", 32)):
            binary = BASE_BIN if variant == "baseline" else AUG_BIN
            rows.append(run_one(binary, bucket, 320, variant, p, 1))

    csv_path = OUT / "results.csv"
    fields = ["round", "variant", "P", "bucket", "L", "qps", "mean_latency_us",
              "recall_percent", "mean_ios", "filter_skips", "io_time_us",
              "tunnel_time_us", "process_time_us", "maxrss_kb", "elapsed_seconds", "log"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    print("wrote", csv_path)

    print("\n=== median of rounds ===")
    for bucket, L in [("low", 320), ("low", 160), ("low", 640), ("medium", 320), ("high", 320)]:
        for variant, p in [("baseline", 0)] + ([("prefilter", x) for x in p_values] if (bucket, L) == ("low", 320) else [("prefilter", 32)]):
            sub = [r for r in rows if r["bucket"] == bucket and r["L"] == L and
                   r["variant"] == variant and r["P"] == p]
            if not sub:
                continue
            med = lambda key: statistics.median([float(r[key]) for r in sub])
            print(f"{bucket:6s} L={L:<4d} {variant:10s} P={p:<4d} "
                  f"recall={med('recall_percent'):.2f}% lat={med('mean_latency_us'):.0f}us "
                  f"ios={med('mean_ios'):.2f} rss={med('maxrss_kb'):.0f}KB")


if __name__ == "__main__":
    main()
