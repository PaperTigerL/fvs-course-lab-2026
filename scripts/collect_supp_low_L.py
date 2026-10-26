#!/usr/bin/env python3
"""Aggregate the repeated GateANN Low-bucket L scan into one CSV.

Reads <run-root>/results/gateann/<tier>/<bucket>/<tag>_r{1..N}/results.csv
and writes <run-root>/results/gateann/<tier>/<bucket>/<tag>/results_aggregated.csv
with one row per L: median, min and max over the repeats for every metric.

Also prints a human-readable summary so you can eyeball the numbers.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path

METRICS = [
    "qps",
    "mean_latency_us",
    "recall_percent",
    "mean_ios",
    "filter_skips",
    "io_time_us",
    "tunnel_time_us",
    "process_time_us",
    "peak_rss_kb",
]


def discover_tier(run_root: Path) -> str:
    """Prefer the formal tier; fall back to the largest base-size tier."""
    base = run_root / "results" / "gateann"
    tiers = sorted(p.name for p in base.iterdir() if p.is_dir()) if base.is_dir() else []
    if not tiers:
        raise SystemExit(f"no gateann result tiers under {base}")
    formal = [t for t in tiers if t.startswith("formal")]
    return formal[0] if formal else tiers[-1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-root", type=Path, required=True)
    ap.add_argument("--bucket", default="low")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--tier", default=None)
    ap.add_argument("--repeats", type=int, default=3)
    args = ap.parse_args()

    run_root = args.run_root.resolve()
    tier = args.tier or discover_tier(run_root)
    parent = run_root / "results" / "gateann" / tier / args.bucket

    per_l: dict[int, list[dict]] = {}
    missing = []
    for r in range(1, args.repeats + 1):
        d = parent / f"{args.tag}_r{r}"
        csv_path = d / "results.csv"
        if not csv_path.is_file():
            missing.append(str(d))
            continue
        with csv_path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                L = int(row["L"])
                per_l.setdefault(L, []).append(row)

    if not per_l:
        raise SystemExit(f"no results found under {parent}; missing={missing}")

    out_dir = parent / args.tag
    out_dir.mkdir(parents=True, exist_ok=True)

    fieldnames = ["L", "repeats"]
    for m in METRICS:
        fieldnames += [f"{m}_median", f"{m}_min", f"{m}_max"]
    fieldnames += ["index_bytes", "system_commit", "run_dirs"]

    rows = []
    for L in sorted(per_l):
        group = per_l[L]
        rec: dict = {"L": L, "repeats": len(group)}
        for m in METRICS:
            vals = [float(g[m]) for g in group if g.get(m) not in (None, "")]
            if not vals:
                continue
            rec[f"{m}_median"] = statistics.median(vals)
            rec[f"{m}_min"] = min(vals)
            rec[f"{m}_max"] = max(vals)
        rec["index_bytes"] = group[0].get("index_bytes", "")
        rec["system_commit"] = group[0].get("system_commit", "")
        rec["run_dirs"] = ";".join(f"{args.tag}_r{i}" for i in range(1, args.repeats + 1))
        # keep 4 significant decimals for readability
        for k, v in list(rec.items()):
            if isinstance(v, float):
                rec[k] = round(v, 4)
        rows.append(rec)

    out_csv = out_dir / "results_aggregated.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)

    (out_dir / "aggregate_meta.json").write_text(
        json.dumps(
            {
                "tag": args.tag,
                "bucket": args.bucket,
                "tier": tier,
                "repeats": args.repeats,
                "missing_runs": missing,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"=== GateANN {args.bucket}-bucket L scan, {args.repeats} repeats ===")
    hdr = f"{'L':>6} {'Recall%':>16} {'Lat_us':>16} {'IOs':>14} {'Skips':>14} {'Tunnel_us':>16}"
    print(hdr)
    for row in rows:
        print(
            f"{row['L']:>6} "
            f"{row['recall_percent_median']:>7.2f} [{row['recall_percent_min']:.2f}-{row['recall_percent_max']:.2f}] "
            f"{row['mean_latency_us_median']:>7.0f} [{row['mean_latency_us_min']:.0f}-{row['mean_latency_us_max']:.0f}] "
            f"{row['mean_ios_median']:>6.2f} [{row['mean_ios_min']:.2f}-{row['mean_ios_max']:.2f}] "
            f"{row['filter_skips_median']:>6.1f} [{row['filter_skips_min']:.1f}-{row['filter_skips_max']:.1f}] "
            f"{row['tunnel_time_us_median']:>6.0f} [{row['tunnel_time_us_min']:.0f}-{row['tunnel_time_us_max']:.0f}]"
        )
    print()
    print("written:", out_csv)
    if missing:
        print("WARNING missing runs:", missing)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
