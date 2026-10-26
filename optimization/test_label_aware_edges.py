"""Property tests for the label-aware edge reference implementation."""
import unittest

import numpy as np

from label_aware_edges import augment_edges, build_label_index, merge_adjacency


class LabelAwareEdgeTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(11)
        self.vectors = rng.normal(size=(60, 6)).astype(np.float32)
        self.labels = []
        for i in range(60):
            if i < 30:
                self.labels.append({0})
            else:
                self.labels.append({1})

    def test_label_index(self):
        index = build_label_index(self.labels)
        self.assertEqual(index[0], list(range(30)))
        self.assertEqual(index[1], list(range(30, 60)))

    def test_only_same_label_edges(self):
        extra = augment_edges(self.vectors, self.labels, k=5, labels_to_process={0})
        for u in range(30):
            for v in extra[u]:
                self.assertIn(0, self.labels[v])
        for u in range(30, 60):
            self.assertEqual(extra[u], {})

    def test_no_self_loops_and_no_duplicates(self):
        extra = augment_edges(self.vectors, self.labels, k=8)
        merged = merge_adjacency([set() for _ in range(60)], extra, degree_cap=8)
        for u, neighbors in enumerate(merged):
            self.assertNotIn(u, neighbors)
            self.assertEqual(len(neighbors), len(set(neighbors)))

    def test_degree_cap(self):
        extra = augment_edges(self.vectors, self.labels, k=20)
        merged = merge_adjacency([set() for _ in range(60)], extra, degree_cap=4)
        for neighbors in merged:
            self.assertLessEqual(len(neighbors), 4)

    def test_unseen_label_has_no_effect(self):
        extra = augment_edges(self.vectors, self.labels, k=8, labels_to_process={99})
        self.assertTrue(all(not x for x in extra))

    def test_min_frequency(self):
        extra = augment_edges(self.vectors, self.labels, k=8, min_freq=31)
        self.assertTrue(all(not x for x in extra))


if __name__ == "__main__":
    unittest.main()
