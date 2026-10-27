# -*- coding: utf-8 -*-
"""Build label-bridge edges: every node -> nearest nodes carrying a target label.

This addresses the entry/reachability problem left by same-label-only edges:
a filter-fail node in a label-blind region can tunnel directly into the target
label's subgraph instead of walking through many irrelevant nodes.

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
    return int(nrow), int(ncol), int(nnz), indptr, indices, data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-u8bin", type=Path, required=True)
    ap.add_argument("--base-spmat", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--labels", required=True, help="comma-separated label ids")
    ap.add_argument("--k", type=int, default=4, help="bridges per node per label")
    ap.add_argument("--max-extra", type=int, default=16)
    ap.add_argument("--hnsw-m", type=int, default=24)
    ap.add_argument("--ef-construction", type=int, default=80)
    ap.add_argument("--ef-search", type=int, default=64)
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--chunk", type=int, default=100000)
    args = ap.parse_args()
    faiss.omp_set_num_threads(args.threads)
    t_start = time.time()

    labels = [int(x) for x in args.labels.split(",") if x.strip()]
    with open(args.base_u8bin, "rb") as f:
        n, d = np.fromfile(f, dtype=np.int32, count=2)
        n, d = int(n), int(d)
    vecs = np.memmap(args.base_u8bin, dtype=np.uint8, mode="r", offset=8, shape=(n, d))
    nrow, ncol, nnz, indptr, indices, data = read_spmat(args.base_spmat)
    if nrow != n:
        raise ValueError("spmat/base size mismatch")
    print(f"n={n} d={d} labels={labels}", flush=True)

    row_ids = np.repeat(np.arange(n, dtype=np.int64), np.diff(indptr))
    mask = np.isin(indices, labels)
    sel_rows = row_ids[mask]
    sel_labels = indices[mask]
    del row_ids, mask, indptr, indices, data

    extra = [None] * n
    updates = 0
    per_label = []
    for label in labels:
        nodes = np.asarray(sel_rows[sel_labels == label], dtype=np.int64)
        if len(nodes) < 2:
            print(f"skip {label}: {len(nodes)}", flush=True)
            continue
        t0 = time.time()
        xb = np.asarray(vecs[nodes], dtype=np.float32)
        index = faiss.IndexHNSWFlat(int(d), args.hnsw_m, faiss.METRIC_L2)
        index.hnsw.efConstruction = args.ef_construction
        index.add(xb)
        index.hnsw.efSearch = args.ef_search
        added = 0
        for start in range(0, n, args.chunk):
            end = min(n, start + args.chunk)
            q = np.asarray(vecs[start:end], dtype=np.float32)
            D, I = index.search(q, min(args.k + 1, len(nodes)))
            for i in range(end - start):
                u = start + i
                if extra[u] is None:
                    extra[u] = {}
                for j in range(I.shape[1]):
                    v = int(nodes[I[i, j]])
                    if v == u:
                        continue
                    dist = float(D[i, j])
                    old = extra[u].get(v)
                    if old is None or dist < old:
                        extra[u][v] = dist
                        updates += 1
                    added += 1
        per_label.append({"label": label, "nodes": int(len(nodes)),
                          "bridges": int(added), "seconds": round(time.time() - t0, 2)})
        print(f"label {label}: nodes={len(nodes)} bridges={added} ({time.time()-t0:.1f}s)", flush=True)

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
        "mode": "label_bridge",
        "n": n, "d": d, "labels": labels, "k": args.k, "max_extra": args.max_extra,
        "hnsw_m": args.hnsw_m, "ef_construction": args.ef_construction,
        "ef_search": args.ef_search, "nodes_with_extra": nodes_with_extra,
        "mean_extra_degree": round(deg_sum / max(1, nodes_with_extra), 3),
        "edge_updates": updates, "per_label": per_label,
        "seconds": round(time.time() - t_start, 2), "out": str(args.out),
    }
    Path(str(args.out) + ".json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: meta[k] for k in ("nodes_with_extra", "mean_extra_degree", "edge_updates", "seconds")}, ensure_ascii=False))
    print("wrote", args.out)


if __name__ == "__main__":
    main()
