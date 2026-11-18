import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from unittest.mock import patch

import networkx as nx

import graph_algorithms as ga
import k5_precompute as kp
import precompute_cache
from test_contracted_k5 import split_k5


def graph_with_multiple_models():
    graph = nx.complete_graph(6)
    positions = nx.spring_layout(graph, dim=3, seed=3)
    nx.set_node_attributes(graph, {n: list(c) for n, c in positions.items()}, 'coords')
    return graph


class PrecomputeTests(unittest.TestCase):
    def test_interrupted_job_resumes_and_app_reads_completed_results(self):
        graph = graph_with_multiple_models()
        calls = []

        def find_loops(expanded, positions, params):
            calls.append(tuple(expanded.nodes))
            if len(calls) == 2:
                raise RuntimeError("interrupted")
            expanded.graph['contraction_disagreements'] = 1
            expanded.graph['contraction_disagreement_pairs'] = [('-3_1', '+3_1')]
            return [{'nodes': list(expanded)[:3], 'knot': '+3_1', 'prob': 1.0, 'unknot_prob': 0.0,
                     'source_knot': '-3_1', 'source_comparison': 'different'}]

        with tempfile.TemporaryDirectory() as cache, \
             patch.object(ga, 'KNOT_CACHE_DIR', cache), \
             patch.object(ga, 'find_knotted_loops', side_effect=find_loops):
            with self.assertRaisesRegex(RuntimeError, 'interrupted'):
                kp.precompute_knotted_k5(graph, candidate_limit=3)
            self.assertIsNone(kp.load_precomputed(graph, candidate_limit=3))
            _, _, _, path = kp._context(graph, None)
            with closing(sqlite3.connect(path)) as db:
                meta = dict(db.execute('SELECT key, value FROM metadata'))
                self.assertEqual(meta['count'], '1')
                self.assertEqual(meta['complete'], '0')
                self.assertEqual(db.execute('SELECT count(*) FROM models').fetchone()[0], 1)
            results = kp.precompute_knotted_k5(graph, candidate_limit=3)
            self.assertEqual(len(results), 3)
            self.assertEqual(len(calls), 4)
            restored = kp.load_precomputed(graph, candidate_limit=3)
            self.assertEqual([list(m.edges()) for m in results], [list(m.edges()) for m in restored])
            self.assertEqual(results[0].graph['knotted_loops'], restored[0].graph['knotted_loops'])
            self.assertEqual(restored[0].graph['contraction_disagreements'], 1)
            self.assertEqual(restored[0].graph['contraction_disagreement_pairs'], [['-3_1', '+3_1']])
            self.assertEqual(restored[0].graph['knotted_loops'][0]['source_knot'], '-3_1')
            with patch.object(kp, 'VERSION', kp.VERSION - 1):
                self.assertIsNone(kp.load_precomputed(graph, candidate_limit=3))
            with patch.object(ga, '_iter_k5_minors', side_effect=AssertionError('should use cache')):
                self.assertEqual(len(ga.find_contracted_knotted_k5_minors(graph, candidate_limit=3)), 3)
                self.assertEqual(len(ga.find_contracted_knotted_k5_minors(graph, candidate_limit=3, max_results=1)), 1)

            changed = graph.copy()
            changed.nodes[0]['coords'] = [0.1, 0.2, 0.3]
            self.assertIsNone(kp.load_precomputed(changed, candidate_limit=3))
            self.assertIsNone(kp.load_precomputed(graph, candidate_limit=1000))

    def test_zero_knots_are_cached_as_completed(self):
        graph = graph_with_multiple_models()
        with tempfile.TemporaryDirectory() as cache, \
             patch.object(ga, 'KNOT_CACHE_DIR', cache), \
             patch.object(ga, 'find_knotted_loops', return_value=[]):
            self.assertEqual(kp.precompute_knotted_k5(graph, candidate_limit=1), [])
            self.assertEqual(kp.load_precomputed(graph, candidate_limit=1), [])

    def test_precompute_task_surfaces_failure(self):
        graph = graph_with_multiple_models()
        with patch.object(precompute_cache, '_context', return_value=(graph, None, {})), \
             patch.object(precompute_cache, 'precompute_knotted_k5', side_effect=RuntimeError('failure')):
            with self.assertRaisesRegex(RuntimeError, 'failure'):
                precompute_cache.find_task('test', 'k5knotcontracted')

    def test_precompute_task_populates_interactive_search_cache(self):
        graph = split_k5()
        positions = {n: graph.nodes[n]['coords'] for n in graph}

        def find_loops(expanded, positions, params):
            expanded.graph['contraction_disagreements'] = 0
            expanded.graph['contraction_disagreement_pairs'] = []
            return [{'nodes': list(expanded)[:3], 'knot': '3_1', 'prob': 1.0, 'unknot_prob': 0.0}]

        with tempfile.TemporaryDirectory(prefix='k5 cache #') as cache, \
             patch.object(ga, 'KNOT_CACHE_DIR', cache), \
             patch.object(precompute_cache, '_context', return_value=(graph, positions, {})), \
             patch.object(ga, 'find_knotted_loops', side_effect=find_loops):
            models = precompute_cache.find_task('test', 'k5knotcontracted')
            self.assertEqual(len(models), 1)
            with patch.object(ga, '_find_k5_minor', side_effect=AssertionError('unexpected search')):
                loaded = ga.find_obstructions(graph, 'k5knotcontracted', node_pos_3d=positions)
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0].graph['knotted_loops'], models[0].graph['knotted_loops'])

    def test_precompute_rejects_another_writer(self):
        import fcntl
        graph = graph_with_multiple_models()
        with tempfile.TemporaryDirectory() as cache, patch.object(ga, 'KNOT_CACHE_DIR', cache):
            _, _, _, path = kp._context(graph, None)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path + '.lock', 'a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaisesRegex(RuntimeError, 'already running'):
                    kp.precompute_knotted_k5(graph, candidate_limit=1)

    def test_interruption_between_models_resumes_from_combination_checkpoint(self):
        graph = graph_with_multiple_models()
        calls = 0

        def find_minor(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 260:
                raise RuntimeError('interrupted enumeration')
            return None

        with tempfile.TemporaryDirectory() as cache, \
             patch.object(ga, 'KNOT_CACHE_DIR', cache), \
             patch.object(ga, '_find_k5_minor', side_effect=find_minor):
            with self.assertRaisesRegex(RuntimeError, 'interrupted enumeration'):
                kp.precompute_knotted_k5(graph)
            _, _, _, path = kp._context(graph, None)
            with closing(sqlite3.connect(path)) as db:
                meta = dict(db.execute('SELECT key, value FROM metadata'))
                self.assertGreaterEqual(int(meta['offset']), 256)
                self.assertEqual(meta['complete'], '0')
            with patch.object(ga, '_find_k5_minor', return_value=None):
                self.assertEqual(kp.precompute_knotted_k5(graph), [])
            self.assertEqual(kp.load_precomputed(graph), [])

    def test_graph_identity_includes_full_precision_coordinates_and_edges(self):
        graph = graph_with_multiple_models()
        _, _, _, first = kp._context(graph, None)
        changed = graph.copy()
        changed.nodes[0]['coords'] = list(graph.nodes[0]['coords'])
        changed.nodes[0]['coords'][0] += 1e-8
        self.assertNotEqual(first, kp._context(changed, None)[3])
        changed = graph.copy()
        changed.remove_edge(0, 1)
        self.assertNotEqual(first, kp._context(changed, None)[3])


if __name__ == '__main__':
    unittest.main()
