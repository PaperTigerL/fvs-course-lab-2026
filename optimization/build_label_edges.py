# -*- coding: utf-8 -*-
"""Build label-aware extra edges for GateANN (query-time FullAdjIndex augmentation).

Input:
  - base.u8bin       : [int32 n][int32 d] + uint8 vectors
  - base.metadata.spmat : CSR labels (header 3x int64; indptr int64; indices int32; data float32)
  - workloads/*/labels.csv : label_id column (15 workload labels)

For each workload label, run HNSW kNN among the vectors carrying that label and
emit up to ``k`` same-label neighbors per node.  Edges are made bidirectional,
deduplicated, and capped to ``max_extra`` per node.

Output format matches GateANN FullAdjIndex:
  [uint64 n_nodes][uint64 max_nbrs][uint64 stride] + uint32 data
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import faiss
import numpy as np
import pandas as pd


def read_spmat(path: Path):
    with open(path, "rb") as f:
        nrow, ncol, nnz = np.fromfile(f, dtype=np.int64, count=3)
        indptr = np.fromfile(f, dtype=np.int64, count=int(nrow) + 1)
        indices = np.fromfile(f, dtype=np.int32, count=int(nnz))
        data = np.fromfile(f, dtype=np.float32, count=int(nnz))
    if len(indptr) != nrow + 1 or len(indices) != nnz or len(data) != nnz:
        raise ValueError(f"broken spmat: {path}")
    return int(nrow), int(ncol), int(nnz), indptr, indices, data


def load_workload_labels(workload_root: Path):
    labels = set()
    rows = []
    for bucket in ("low", "medium", "high"):
        p = workload_root / bucket / "labels.csv"
        df = pd.read_csv(p)
        for _, r in df.iterrows():
            lid = int(r["label_id"])
            labels.add(lid)
            rows.append({"bucket": bucket, "label": lid,
                         "base_match_count": int(r.get("base_match_count", 0)),
                         "selectivity": float(r.get("selectivity", 0.0))})
    return sorted(labels), rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-u8bin", type=Path, required=True)
    ap.add_argument("--base-spmat", type=Path, required=True)
    ap.add_argument("--workload-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--k", type=int, default=8, help="same-label neighbors per node")
    ap.add_argument("--max-extra", type=int, default=12, help="total extra edges per node")
    ap.add_argument("--hnsw-m", type=int, default=32)
    ap.add_argument("--ef-construction", type=int, default=80)
    ap.add_argument("--ef-search", type=int, default=64)
    ap.add_argument("--threads", type=int, default=8)
    args = ap.parse_args()

    faiss.omp_set_num_threads(args.threads)
    t_start = time.time()

    with open(args.base_u8bin, "rb") as f:
        n, d = np.fromfile(f, dtype=np.int32, count=2)
        n, d = int(n), int(d)
    print(f"base: n={n} d={d}")
    vecs = np.memmap(args.base_u8bin, dtype=np.uint8, mode="r", offset=8, shape=(n, d))

    nrow, ncol, nnz, indptr, indices, data = read_spmat(args.base_spmat)
    if nrow != n:
        raise ValueError(f"spmat nrow={nrow} != base n={n}")
    print(f"spmat: nrow={nrow} ncol={ncol} nnz={nnz}")

    labels, label_rows = load_workload_labels(args.workload_root)
    print(f"workload labels ({len(labels)}): {labels}")

    # node ids for every non-zero label entry, then select the 15 workload labels.
    row_ids = np.repeat(np.arange(n, dtype=np.int64), np.diff(indptr))
    mask = np.isin(indices, labels)
    sel_rows = row_ids[mask]
    sel_labels = indices[mask]
    del row_ids, mask, indptr, indices, data

    extra = [None] * n  # node -> dict(neighbor -> distance)
    edge_updates = 0
    per_label = []

    for label in labels:
        nodes = np.asarray(sel_rows[sel_labels == label], dtype=np.int64)
        if len(nodes) < 2:
            print(f"skip label {label}: {len(nodes)} nodes")
            continue
        t0 = time.time()
        xb = np.asarray(vecs[nodes], dtype=np.float32)
        index = faiss.IndexHNSWFlat(int(d), args.hnsw_m, faiss.METRIC_L2)
        index.hnsw.efConstruction = args.ef_construction
        index.add(xb)
        index.hnsw.efSearch = args.ef_search
        D, I = index.search(xb, min(args.k + 1, len(nodes)))
        added = 0
        for i in range(len(nodes)):
            u = int(nodes[i])
            if extra[u] is None:
                extra[u] = {}
            for j in range(1, I.shape[1]):
                v = int(nodes[I[i, j]])
                if v == u:
                    continue
                dist = float(D[i, j])
                old = extra[u].get(v)
                if old is None or dist < old:
                    extra[u][v] = dist
                    edge_updates += 1
                if extra[v] is None:
                    extra[v] = {}
                old2 = extra[v].get(u)
                if old2 is None or dist < old2:
                    extra[v][u] = dist
                    edge_updates += 1
                added += 1
        per_label.append({"label": label, "nodes": int(len(nodes)),
                          "knn_edges_directed": int(added * 2),
                          "seconds": round(time.time() - t0, 2)})
        print(f"label {label}: nodes={len(nodes)} edges~{added * 2} "
              f"({time.time() - t0:.1f}s)")

    # Materialize capped adjacency in FullAdjIndex format.
    out = np.zeros((n, 1 + args.max_extra), dtype=np.uint32)
    nodes_with_extra = 0
    deg_sum = 0
    for u in range(n):
        dct = extra[u]
        if not dct:
            continue
        items = sorted(dct.items(), key=lambda kv: (kv[1], kv[0]))[: args.max_extra]
        out[u, 0] = len(items)
        if items:
            out[u, 1:1 + len(items)] = np.asarray([v for v, _ in items], dtype=np.uint32)
            nodes_with_extra += 1
            deg_sum += len(items)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "wb") as f:
        np.asarray([n, args.max_extra, 1 + args.max_extra], dtype=np.uint64).tofile(f)
        out.tofile(f)

    meta = {
        "base_u8bin": str(args.base_u8bin),
        "base_spmat": str(args.base_spmat),
        "workload_root": str(args.workload_root),
        "n": n,
        "d": d,
        "labels": labels,
        "k": args.k,
        "max_extra": args.max_extra,
        "hnsw_m": args.hnsw_m,
        "ef_construction": args.ef_construction,
        "ef_search": args.ef_search,
        "nodes_with_extra": nodes_with_extra,
        "mean_extra_degree": round(deg_sum / max(1, nodes_with_extra), 3),
        "edge_updates": edge_updates,
        "per_label": per_label,
        "seconds": round(time.time() - t_start, 2),
        "out": str(args.out),
    }
    meta_path = Path(str(args.out) + ".json")
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: meta[k] for k in ("nodes_with_extra", "mean_extra_degree",
                                           "edge_updates", "seconds")}, ensure_ascii=False))
    print("wrote", args.out, "and", meta_path)


if __name__ == "__main__":
    main()
