"""Reference implementation of build-time label-aware edge augmentation.

This module is intentionally small and dependency-light (NumPy only).  It is a
reference for the edge-selection logic described in the experiment report, not
a drop-in patch for GateANN's C++ query path.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Sequence, Set

import numpy as np


def build_label_index(labels: Sequence[Iterable[int]]) -> Dict[int, List[int]]:
    """Return an inverted index ``label -> sorted node ids``."""
    index: Dict[int, List[int]] = defaultdict(list)
    for node, node_labels in enumerate(labels):
        for label in set(node_labels):
            index[int(label)].append(node)
    return {label: sorted(nodes) for label, nodes in index.items()}


def _sample_nodes(nodes: List[int], max_candidates: int) -> List[int]:
    if len(nodes) <= max_candidates:
        return nodes
    # Deterministic, evenly spaced subsample; production code should use an ANN.
    positions = np.linspace(0, len(nodes) - 1, max_candidates, dtype=np.int64)
    return [nodes[int(p)] for p in positions]


def augment_edges(
    vectors: np.ndarray,
    labels: Sequence[Iterable[int]],
    *,
    k: int = 8,
    min_freq: int = 2,
    max_freq: Optional[int] = None,
    max_candidates: int = 4096,
    labels_to_process: Optional[Iterable[int]] = None,
) -> List[Dict[int, float]]:
    """Build extra same-label edges for low-frequency labels.

    Parameters
    ----------
    vectors : (n, d) float array
    labels : sequence of label sets, one per node
    k : number of same-label neighbors per node
    min_freq : skip labels with fewer than this many nodes
    max_freq : optionally only process labels at most this frequent
    max_candidates : deterministic cap for very large labels
    labels_to_process : optional whitelist of labels (for tests / selective builds)

    Returns
    -------
    extra : list of dicts, ``extra[u][v] = distance``.  Only processed labels
        contribute edges; nodes without such labels get an empty dict.
    """
    vectors = np.asarray(vectors, dtype=np.float32)
    if vectors.ndim != 2:
        raise ValueError("vectors must be a 2-D array")
    if len(vectors) != len(labels):
        raise ValueError("vectors and labels must have the same length")

    whitelist = None if labels_to_process is None else {int(x) for x in labels_to_process}
    index = build_label_index(labels)
    extra: List[Dict[int, float]] = [dict() for _ in range(len(vectors))]

    for label, nodes in index.items():
        if whitelist is not None and label not in whitelist:
            continue
        if len(nodes) < max(2, min_freq):
            continue
        if max_freq is not None and len(nodes) > max_freq:
            continue
        candidates = _sample_nodes(nodes, max_candidates)
        if len(candidates) < 2:
            continue
        candidate_vectors = vectors[candidates]
        for u in nodes:
            if u not in candidates:
                # Keep the build bounded; the sampled nodes still help their own edges.
                continue
            diff = candidate_vectors - vectors[u]
            dist = np.einsum("ij,ij->i", diff, diff)
            order = np.argsort(dist, kind="stable")
            added = 0
            for pos in order:
                v = candidates[int(pos)]
                if v == u:
                    continue
                d = float(dist[int(pos)])
                old = extra[u].get(v)
                if old is None or d < old:
                    extra[u][v] = d
                added += 1
                if added >= k:
                    break
    return extra


def merge_adjacency(
    original: Sequence[Iterable[int]],
    extra: Sequence[Dict[int, float]],
    *,
    degree_cap: int = 32,
) -> List[Set[int]]:
    """Merge original neighbors with extra edges, preserving original edges first."""
    if len(original) != len(extra):
        raise ValueError("original and extra must have the same length")
    merged: List[Set[int]] = []
    for u, (orig, add) in enumerate(zip(original, extra)):
        neighbors = {int(v) for v in orig if int(v) != u}
        if len(neighbors) >= degree_cap:
            merged.append(neighbors)
            continue
        for v, _ in sorted(add.items(), key=lambda kv: (kv[1], kv[0])):
            v = int(v)
            if v == u or v in neighbors:
                continue
            neighbors.add(v)
            if len(neighbors) >= degree_cap:
                break
        merged.append(neighbors)
    return merged


def _demo() -> None:
    rng = np.random.default_rng(7)
    n, d = 200, 8
    vectors = rng.normal(size=(n, d)).astype(np.float32)
    labels = []
    for i in range(n):
        if i < 20:
            labels.append({0})
        elif i < 80:
            labels.append({1})
        elif i < 160:
            labels.append({2})
        else:
            labels.append({3, 4})
    extra = augment_edges(vectors, labels, k=8)
    merged = merge_adjacency([set() for _ in range(n)], extra, degree_cap=32)
    sizes = [len(x) for x in merged]
    print("nodes:", n)
    print("labels:", {label: len(nodes) for label, nodes in build_label_index(labels).items()})
    print("extra edges:", sum(len(x) for x in extra))
    print("degree min/median/max:", min(sizes), int(np.median(sizes)), max(sizes))
    assert all(len(x) <= 32 for x in merged)
    assert all(u not in x for u, x in enumerate(merged))


if __name__ == "__main__":
    _demo()
