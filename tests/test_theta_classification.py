import random
import json
import os
import tempfile
import unittest
from unittest.mock import patch

import networkx as nx

import theta_classification as tc
import graph_algorithms as ga
import precompute_cache
from dash_graphs import create_app


def random_theta(seed, points=2, mirror=False):
    """Theta graph u - v with three arcs of random 3D polylines."""
    g = nx.Graph()
    g.add_node('u', coords=(0.0, 0.0, 0.0))
    g.add_node('v', coords=(1.0, 0.0, 0.0))
    for a in range(3):
        rnd = random.Random(seed * 10 + a + 1)
        prev = 'u'
        for k in range(points):
            n = f'a{a}_{k}'
            z = rnd.uniform(-1, 1)
            g.add_node(n, coords=(rnd.uniform(-1, 2), rnd.uniform(-1, 1), -z if mirror else z))
            g.add_edge(prev, n)
            prev = n
        g.add_edge(prev, 'v')
    return g


class ThetaClassificationTest(unittest.TestCase):
    def test_is_theta_graph(self):
        self.assertTrue(tc.is_theta_graph(random_theta(1)))
        self.assertFalse(tc.is_theta_graph(nx.cycle_graph(5)))
        self.assertFalse(tc.is_theta_graph(nx.complete_graph(5)))

    def test_find_theta_subgraph_in_larger_graph(self):
        graph = random_theta(23, 3)
        graph.add_node('leaf', coords=(2.0, 2.0, 2.0))
        graph.add_edge('a0_0', 'leaf')
        self.assertFalse(tc.is_theta_graph(graph))
        found = tc.find_theta_subgraphs(graph)
        self.assertTrue(found)
        self.assertTrue(all(tc.is_theta_graph(theta) for theta in found))
        self.assertEqual(tc.classify_theta_curve(found[0], method='topoly')['name'], 'T3_1')
        self.assertEqual(tc.find_theta_subgraphs(nx.cycle_graph(5)), [])

    def test_not_theta_raises(self):
        with self.assertRaises(ValueError):
            tc.classify_theta_curve(nx.cycle_graph(4))

    def test_unknown_method(self):
        with self.assertRaises(ValueError):
            tc.classify_theta_curve(random_theta(1), method='x')

    def test_planar_is_trivial(self):
        for method in tc.METHODS:
            res = tc.classify_theta_curve(random_theta(5), method=method)
            self.assertEqual(res['name'], 'T0_1')

    def test_methods_agree_and_mirror(self):
        for seed in (23, 27, 36):
            res = {}
            for mirror in (False, True):
                for method in tc.METHODS:
                    res[mirror, method] = tc.classify_theta_curve(random_theta(seed, 3, mirror=mirror), method=method)
            for mirror in (False, True):
                self.assertEqual(res[mirror, 'topoly']['name'], res[mirror, 'knotpy']['name'])
                self.assertEqual(res[mirror, 'topoly']['chirality'], res[mirror, 'knotpy']['chirality'])
            if res[False, 'knotpy']['name'] != 'T0_1':
                self.assertNotEqual(res[False, 'knotpy']['chirality'], res[True, 'knotpy']['chirality'])

    def test_trefoil_theta(self):
        res = tc.classify_theta_curve(random_theta(23, 3), method="knotpy")
        self.assertEqual(res['name'], 'T3_1')


class KnottedThetaSearchTest(unittest.TestCase):
    def setUp(self):
        self.cache = tempfile.TemporaryDirectory()
        self.addCleanup(self.cache.cleanup)
        patcher = patch.object(ga, 'KNOT_CACHE_DIR', self.cache.name)
        patcher.start()
        self.addCleanup(patcher.stop)

    def graph(self):
        graph = nx.Graph()
        for node in range(6):
            graph.add_node(node, coords=(float(node), 0.0, 0.0))
        for interior in range(2, 6):
            graph.add_edges_from(((0, interior), (interior, 1)))
        return graph

    @staticmethod
    def classification(name):
        return {'method': 'topoly', 'name': name, 'chirality': None, 'polynomial': None}

    def test_alternative_paths_and_noninitial_knotted_constituent(self):
        graph = self.graph()
        graph.add_node(6, coords=(6.0, 0.0, 0.0))
        graph.add_edges_from(((0, 6), (6, 1)))
        def homfly(coords, tries):
            nodes = {int(p[0]) for p in coords}
            return {'+3_1': 1.0} if {4, 5} <= nodes else {'0_1': 1.0}
        with patch.object(ga, '_isolated_homfly', side_effect=homfly), \
             patch.object(tc, 'cached_theta_classification', return_value=self.classification('T0_1')):
            results = tc.find_knotted_thetas(graph)
        self.assertEqual(results.examined, 10)
        self.assertEqual(len(results), 3)
        for theta in results:
            self.assertTrue(tc.is_theta_graph(theta))
            self.assertTrue({4, 5} <= set(theta.graph['knotted_constituent']['nodes']))
            self.assertEqual(theta.graph['knotted_constituent']['knot'], '+3_1')
        self.assertTrue(any('does not prove' in warning for warning in results.warnings))

    def test_nontrivial_yamada_and_inconclusive_cases(self):
        graph = self.graph()
        with patch.object(ga, '_isolated_homfly', return_value={'0_1': 1.0}), \
             patch.object(tc, 'cached_theta_classification', return_value=self.classification('T3_1')):
            results = tc.find_knotted_thetas(graph)
        self.assertEqual(len(results), 4)
        self.assertEqual(results.warnings, [])
        with patch.object(ga, '_isolated_homfly', return_value=None), \
             patch.object(tc, 'cached_theta_classification', side_effect=RuntimeError('Yamada failed')):
            results = tc.find_knotted_thetas(graph)
        self.assertEqual(results, [])
        self.assertTrue(any('inconclusive Yamada' in warning for warning in results.warnings))
        self.assertTrue(any('inconclusive HOMFLY' in warning for warning in results.warnings))

    def test_limits_and_deadline_after_classification(self):
        graph = self.graph()
        with patch.object(ga, '_isolated_homfly', return_value={'0_1': 1.0}), \
             patch.object(tc, 'cached_theta_classification', return_value=self.classification('T3_1')):
            for kwargs, expected in (({'result_limit': 1}, 'result limit'),
                                     ({'candidate_limit': 1}, 'candidate limit'),
                                     ({'cycle_limit': 1}, 'cycle limit')):
                results = tc.find_knotted_thetas(graph, **kwargs)
                self.assertTrue(any(expected in warning for warning in results.warnings), results.warnings)
        clock = [0]
        def classify(*args, **kwargs):
            clock[0] = 2
            return self.classification('T3_1')
        with patch.object(tc.time, 'monotonic', side_effect=lambda: clock[0]), \
             patch.object(ga, '_isolated_homfly', return_value={'0_1': 1.0}), \
             patch.object(tc, 'cached_theta_classification', side_effect=classify):
            results = tc.find_knotted_thetas(graph, time_limit=1)
        self.assertTrue(any('time limit' in warning for warning in results.warnings))

    def test_1a8e_known_knotted_loop_is_extended_without_contraction(self):
        graph, positions, params = precompute_cache._context('1A8E', 'simplified')
        nodes = ['95_CA', '118_CA', '137_CA', '137_SG', '331_SG', '331_CA', '249_CA',
                 '241_CA', '241_SG', '227_SG', '227_CA', '194_CA', '188_CA', '188_CG',
                 '188_CD2', '188_CZ', '188_OH', '339_FE', '63_OD1', '63_CA']
        loop = {'nodes': nodes, 'knot': '+3_1', 'prob': 1.0, 'unknot_prob': 0.0}
        knot_cache = ga._knot_cache_path(graph, positions, 500, params=params)
        read = ga._read_json
        with patch.object(ga, '_read_json', side_effect=lambda path:
                          {'loops': [loop], 'loops_analyzed': []} if path == knot_cache else read(path)):
            results = tc.find_knotted_thetas(graph, positions, params, result_limit=2, time_limit=30)
        self.assertEqual(len(results), 2)
        for theta in results:
            self.assertTrue(tc.is_theta_graph(theta))
            self.assertTrue(all(graph.has_edge(u, v) for u, v in theta.edges()))
            self.assertEqual(theta.graph['knotted_constituent']['knot'], '+3_1')
            self.assertEqual(theta.graph['theta_classification']['name'], 'T3_1')

    def test_1a8e_knotted_k33_contains_a_found_knotted_theta(self):
        graph, positions, params = precompute_cache._context('1A8E', 'simplified')
        paths = [
            '188_CZ 188_OH 339_FE 63_OD1 63_CA 95_CA 118_CA 137_CA 137_SG 331_SG 331_CA 249_CA 241_CA 233_N 227_CA 194_CA 188_CA 188_CG 188_CZ',
            '339_FE 249_NE2 249_CG 249_CA',
            '188_CA 179_CA 179_SG 161_SG 161_CA 158_CA 137_CA',
            '118_CA 118_SG 194_SG 194_CA',
        ]
        edges = [edge for path in paths for edge in zip(path.split(), path.split()[1:])]
        model = graph.edge_subgraph(edges).copy()
        cycle = paths[0].split()[:-1]
        self.assertEqual(ga._checked_homfly_label(
            ga._isolated_homfly([graph.nodes[n]['coords'] for n in cycle], 500),
            'the known 1A8E cycle'), '+3_1')
        loop = {'nodes': cycle, 'knot': '+3_1', 'prob': 1.0, 'unknot_prob': 0.0}
        knot_cache = ga._knot_cache_path(model, positions, 500, params=params)
        read = ga._read_json
        with patch.object(ga, '_read_json', side_effect=lambda path:
                          {'loops': [loop], 'loops_analyzed': []} if path == knot_cache else read(path)):
            results = tc.find_knotted_thetas(model, positions, params, result_limit=2, time_limit=30)
        self.assertTrue(results)
        for theta in results:
            self.assertTrue(tc.is_theta_graph(theta))
            self.assertTrue(all(model.has_edge(u, v) for u, v in theta.edges()))
            self.assertEqual(theta.graph['knotted_constituent']['knot'], '+3_1')


class ThetaSearchUITest(unittest.TestCase):
    def setUp(self):
        cache = tempfile.TemporaryDirectory()
        self.addCleanup(cache.cleanup)
        patcher = patch.object(ga, 'KNOT_CACHE_DIR', cache.name)
        patcher.start()
        self.addCleanup(patcher.stop)

    def call(self, app, output, values, changed):
        key = output if output in app.callback_map else next(k for k in app.callback_map if output in k)
        callback = app.callback_map[key]
        outputs = callback['output']

        def spec(item):
            return {'id': item.component_id, 'property': item.component_property}

        response = app.server.test_client().post('/spatialgraphs/_dash-update-component', json={
            'output': key,
            'outputs': [spec(o) for o in outputs] if isinstance(outputs, list) else spec(outputs),
            'inputs': [dict(item, value=values.get(item['id'])) for item in callback['inputs']],
            'state': [dict(item, value=values.get(item['id'])) for item in callback['state']],
            'changedPropIds': [changed],
        })
        self.assertEqual(response.status_code, 200, response.data.decode())
        return response.get_json()['response']

    def test_find_navigate_highlight_classify_and_export_thetas(self):
        graph = nx.disjoint_union(random_theta(1), random_theta(5))
        expected = tc.find_theta_subgraphs(graph)
        self.assertTrue(nx.check_planarity(graph)[0])
        self.assertEqual(len(expected), 2)
        app = create_app(graph)
        values = {'find-k33-btn': 0, 'find-k5-btn': 0, 'find-k33knot-btn': 0,
                  'find-k5knot-btn': 0, 'find-theta-btn': 1, 'graph-version': 0,
                  'k5-representation': 'contracted'}
        with patch('dash_graphs.threading.Thread.start', lambda thread: thread.run()), \
             patch('dash_graphs.find_knotted_thetas', return_value=tc.KnottedThetaResults(expected)):
            started = self.call(app, 'find-message.children', values, 'find-theta-btn.n_clicks')
            self.assertFalse(started['theta-search-poll']['disabled'])
            result = self.call(app, 'find-message.children', values, 'theta-search-poll.n_intervals')
            self.assertEqual(result['mode']['value'], 'multi')
            self.assertEqual(result['selected-obstruction-only']['value'], ['on'])
            values.update({'mode': 'multi', 'subgraph-index': 0, 'graph-version': 1,
                           'selected-obstruction-only': ['on'], 'simplify-subgraph': [],
                           'knot-index': 0, 'knot-version': 0, 'view-dim': '2d',
                           'edge-thickness': 3, 'rainbow-backbone': [], 'edge-color-attr': 'none',
                           'within-index': 0, 'within-version': 0, 'knot-in-original': [],
                           'rot3d': [0, 0, 0], 'show-grid': [], 'node-font-size': 14,
                           'prev-btn': 0, 'next-btn': 1, 'run-theta-btn': 1, 'theta-method': 'topoly'})
            label = self.call(app, 'subgraph-info.children', values, 'graph-version.data')
            self.assertIn('Knotted theta curve 1 of 2', label['subgraph-info']['children'])
            navigation = self.call(app, 'subgraph-index.data', values, 'next-btn.n_clicks')
            self.assertEqual(navigation['subgraph-index']['data'], 1)
            values['subgraph-index'] = 1
            result = self.call(app, 'graph.elements', values, 'subgraph-index.data')
            elements = result['graph']['elements']
            actual = {frozenset((e['data']['source'], e['data']['target'])) for e in elements
                      if 'source' in e['data']}
            edges = {frozenset(map(str, e)) for e in expected[1].edges()}
            self.assertEqual(actual, edges)
            figure = self.call(app, 'graph-3d.figure', values, 'subgraph-index.data')['graph-3d']['figure']
            self.assertEqual(set(figure['data'][-1]['text']), set(map(str, expected[1])))
            classification = self.call(app, 'theta-result.children', values, 'run-theta-btn.n_clicks')
            self.assertIn('Theta classification', classification['theta-result']['children'])
            self.assertIn('T0_1', classification['theta-result']['children'])
            self.assertEqual(self.call(app, 'theta-result.children', values,
                                       'subgraph-index.data')['theta-result']['children'], '')
            values['export-sub-btn'] = 1
            exported = self.call(app, 'export-sub-download.data', values, 'export-sub-btn.n_clicks')
            data = json.loads(exported['export-sub-download']['data']['content'])
            self.assertEqual({frozenset((e['source'], e['target'])) for e in data['edges']}, edges)
            values.update({'mode': 'highlight', 'export-sub-btn': 1})
            elements = self.call(app, 'graph.elements', values, 'mode.value')['graph']['elements']
            highlighted = {frozenset((e['data']['source'], e['data']['target'])) for e in elements
                           if e.get('classes') == 'obstruction' and 'source' in e['data']}
            self.assertEqual(highlighted, edges)
            figure = self.call(app, 'graph-3d.figure', values, 'mode.value')['graph-3d']['figure']
            nodes = figure['data'][-1]
            self.assertEqual({n for n, color in zip(nodes['text'], nodes['marker']['color'])
                              if color == 'crimson'}, set(map(str, expected[1])))
            exported = self.call(app, 'export-sub-download.data', values, 'export-sub-btn.n_clicks')
            data = json.loads(exported['export-sub-download']['data']['content'])
            self.assertEqual({frozenset(e) for e in data['highlighted_edges']}, edges)

    def test_no_thetas_in_planar_graph(self):
        graph = nx.cycle_graph(5)
        nx.set_node_attributes(graph, {n: (float(n), float(n % 2), 0.0) for n in graph}, 'coords')
        app = create_app(graph)
        values = {'find-theta-btn': 1, 'graph-version': 0, 'k5-representation': 'contracted'}
        with patch('dash_graphs.threading.Thread.start', lambda thread: thread.run()):
            self.call(app, 'find-message.children', values, 'find-theta-btn.n_clicks')
            result = self.call(app, 'find-message.children', values, 'theta-search-poll.n_intervals')
        self.assertEqual(result['mode']['value'], 'original')
        info = self.call(app, 'subgraph-info.children', {'subgraph-index': 0, 'graph-version': 1},
                         'graph-version.data')
        self.assertIn('No Knotted theta curve found', info['subgraph-info']['children'])

    def test_limit_is_reported(self):
        graph = random_theta(1)
        app = create_app(graph)
        found = tc.KnottedThetaResults([graph], ['Theta search incomplete: result limit reached'], 1)
        with patch('dash_graphs.threading.Thread.start', lambda thread: thread.run()), \
             patch('dash_graphs.find_knotted_thetas', return_value=found) as search:
            values = {'find-theta-btn': 1, 'graph-version': 0, 'k5-representation': 'contracted'}
            self.call(app, 'find-message.children', values, 'find-theta-btn.n_clicks')
            result = self.call(app, 'find-message.children', values, 'theta-search-poll.n_intervals')
            search.assert_called_once()
            self.assertIn('incomplete', result['find-message']['children'])
            info = self.call(app, 'subgraph-info.children', {'subgraph-index': 0, 'graph-version': 1},
                             'graph-version.data')
            self.assertIn('Knotted theta curve 1 of 1', info['subgraph-info']['children'])
            self.assertIn('search incomplete', info['subgraph-info']['children'])

    def test_stale_search_cannot_override_new_family(self):
        graph = random_theta(1)
        app = create_app(graph)
        values = {'find-theta-btn': 1, 'find-k5-btn': 1, 'graph-version': 0,
                  'k5-representation': 'model'}
        with patch('dash_graphs.threading.Thread.start'):
            self.call(app, 'find-message.children', values, 'find-theta-btn.n_clicks')
            self.call(app, 'find-message.children', values, 'find-k5-btn.n_clicks')
            stale = self.call(app, 'find-message.children', values, 'theta-search-poll.n_intervals')
        self.assertTrue(stale['theta-search-poll']['disabled'])
        self.assertNotIn('mode', stale)

    def test_search_failure_is_visible(self):
        app = create_app(random_theta(1))
        values = {'find-theta-btn': 1, 'graph-version': 0}
        with patch('dash_graphs.threading.Thread.start', lambda thread: thread.run()), \
             patch('dash_graphs.find_knotted_thetas', side_effect=ValueError('bad geometry')):
            self.call(app, 'find-message.children', values, 'find-theta-btn.n_clicks')
            result = self.call(app, 'find-message.children', values, 'theta-search-poll.n_intervals')
        self.assertIn('bad geometry', result['find-message']['children'])
        self.assertTrue(result['theta-search-poll']['disabled'])


class ThetaCacheTest(unittest.TestCase):
    def setUp(self):
        cache = tempfile.TemporaryDirectory()
        self.addCleanup(cache.cleanup)
        self.cache = cache.name
        patcher = patch.object(ga, 'KNOT_CACHE_DIR', self.cache)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_search_cache_reuses_results_and_current_attributes(self):
        graph = nx.disjoint_union(random_theta(1), random_theta(5))
        found = tc.cached_theta_subgraphs(graph, limit=3)
        self.assertEqual(len(found), 2)
        changed = graph.copy()
        changed.nodes[0]['coords'] = (99, 98, 97)
        with patch.object(tc, 'find_theta_subgraphs', side_effect=AssertionError('unexpected search')):
            loaded = tc.cached_theta_subgraphs(changed, limit=3)
        self.assertEqual([list(g.edges()) for g in loaded], [list(g.edges()) for g in found])
        self.assertEqual(next(g for g in loaded if 0 in g).nodes[0]['coords'], (99, 98, 97))
        with patch.object(tc, 'find_theta_subgraphs', wraps=tc.find_theta_subgraphs) as search:
            tc.cached_theta_subgraphs(graph, limit=1)
            changed.remove_edge(*next(iter(changed.edges())))
            tc.cached_theta_subgraphs(changed, limit=3)
            self.assertEqual(search.call_count, 2)

    def test_empty_search_and_precompute_are_cached(self):
        graph = nx.cycle_graph(4)
        with patch.object(precompute_cache, '_context', return_value=(graph, None, {})), \
             patch.object(precompute_cache, 'find_knotted_thetas', wraps=tc.find_knotted_thetas) as search:
            self.assertEqual(precompute_cache.find_task('test', 'theta'), [])
            self.assertEqual(search.call_count, 1)

    def test_invalid_cache_is_recomputed_and_versions_are_distinct(self):
        graph = random_theta(1)
        tc.cached_theta_subgraphs(graph)
        filename = os.path.join(self.cache, next(name for name in os.listdir(self.cache)
                                                 if name.startswith('theta_search_')))
        with open(filename, 'w') as f:
            json.dump({'results': [{'nodes': [-1], 'edges': []}]}, f)
        with self.assertLogs('theta_classification', level='WARNING'), \
             patch.object(tc, 'find_theta_subgraphs', wraps=tc.find_theta_subgraphs) as search:
            self.assertEqual(len(tc.cached_theta_subgraphs(graph)), 1)
            search.assert_called_once()
        with patch.object(tc, 'THETA_CACHE_VERSION', tc.THETA_CACHE_VERSION + 1), \
             patch.object(tc, 'find_theta_subgraphs', wraps=tc.find_theta_subgraphs) as search:
            tc.cached_theta_subgraphs(graph)
            search.assert_called_once()

    def test_classification_cache_tracks_method_and_geometry(self):
        graph = random_theta(1)
        result = {'method': 'topoly', 'name': 'T0_1', 'chirality': None, 'polynomial': None}
        with patch.object(tc, '_classify_topoly', return_value=result) as classify:
            self.assertEqual(tc.cached_theta_classification(graph), result)
            self.assertEqual(tc.cached_theta_classification(graph), result)
            self.assertEqual(classify.call_count, 1)
            graph.nodes['u']['coords'] = (0.1, 0.0, 0.0)
            tc.cached_theta_classification(graph)
            self.assertEqual(classify.call_count, 2)
        other = dict(result, method='knotpy', polynomial='1')
        with patch.object(tc, '_classify_knotpy', return_value=other) as classify:
            self.assertEqual(tc.cached_theta_classification(graph, method='knotpy'), other)
            classify.assert_called_once()

    def test_failed_classification_is_not_cached(self):
        graph = random_theta(1)
        with patch.object(tc, '_classify_topoly', side_effect=RuntimeError('failed')):
            with self.assertRaisesRegex(RuntimeError, 'failed'):
                tc.cached_theta_classification(graph)
        self.assertFalse(os.path.exists(self.cache) and os.listdir(self.cache))
        with patch.object(tc, '_classify_topoly', return_value={
            'method': 'topoly', 'name': None, 'chirality': None, 'polynomial': None
        }) as classify:
            tc.cached_theta_classification(graph)
            tc.cached_theta_classification(graph)
            classify.assert_called_once()

if __name__ == '__main__':
    unittest.main()
