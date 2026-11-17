import math
import json
import tempfile
import unittest
from unittest.mock import patch

import networkx as nx

import graph_algorithms as ga
from graph_visualization import build_3d_figure, build_elements
from dash_graphs import create_app


def split_k5():
    graph = nx.Graph(
        [((i, (j - (j > i)) // 2), (j, (i - (i > j)) // 2))
         for i in range(5) for j in range(i + 1, 5)]
        + [((i, 0), (i, 1)) for i in range(5)]
    )
    positions = nx.spring_layout(graph, dim=3, seed=7)
    nx.set_node_attributes(graph, {n: list(c) for n, c in positions.items()}, 'coords')
    return graph


def trefoil_k5():
    graph = nx.Graph()
    count = 30
    for i in range(count):
        t = 2 * math.pi * i / count
        graph.add_node(i, coords=[(2 + math.cos(3 * t)) * math.cos(2 * t),
                                  (2 + math.cos(3 * t)) * math.sin(2 * t),
                                  math.sin(3 * t)])
        graph.add_edge(i, (i + 1) % count)
    roots = list(range(0, count, 6))
    for i, u in enumerate(roots):
        for v in roots[i + 1:]:
            if (roots.index(v) - i) not in (1, 4):
                graph.add_edge(u, v)
    return graph


def split_k5_with_trefoil():
    graph = split_k5()
    cycle = next(c for c in nx.simple_cycles(graph) if len(c) == 10)
    for i, node in enumerate(cycle):
        t = 2 * math.pi * i / len(cycle)
        graph.nodes[node]['coords'] = [(2 + math.cos(3 * t)) * math.cos(2 * t),
                                       (2 + math.cos(3 * t)) * math.sin(2 * t),
                                       math.sin(3 * t)]
    return graph, cycle


class ContractedK5Tests(unittest.TestCase):
    def test_split_model_contracts_to_five_degree_four_vertices(self):
        graph = split_k5()
        legacy = ga.find_k5_minors(graph, max_results=1)[0]
        result = ga.find_contracted_k5_minors(graph, max_results=1)[0]
        self.assertEqual(set(dict(legacy.degree()).values()), {3})
        self.assertEqual((len(result), result.number_of_edges()), (5, 10))
        self.assertEqual(set(dict(result.degree()).values()), {4})
        branches = [set(result.nodes[n]['branch_set']) for n in result]
        self.assertEqual(set.union(*branches), set(graph))
        self.assertTrue(all(not a & b for i, a in enumerate(branches) for b in branches[i + 1:]))
        for branch in branches:
            self.assertTrue(nx.is_connected(graph.subgraph(branch)))
        self.assertTrue(all(graph.has_edge(*e) for e in result.graph['source_edges']))
        self.assertEqual(len(result.graph['source_edges']), 15)

    def test_curves_survive_expansion_and_are_not_drawn_as_vertices(self):
        model = ga.find_contracted_k5_minors(trefoil_k5(), max_results=1)[0]
        expanded = ga.expand_k5_embedding(model)
        bends = [n for n in expanded if expanded.nodes[n].get('k5_bend')]
        self.assertEqual(len(bends), 25)
        self.assertTrue(all(expanded.degree(n) == 2 for n in bends))
        coords = {n: expanded.nodes[n]['coords'] for n in expanded}
        elements = build_elements(expanded, {n: c[:2] for n, c in coords.items()})
        self.assertEqual(sum(e.get('classes') == 'k5-bend' for e in elements), 25)
        figure = build_3d_figure(expanded, coords)
        self.assertEqual(len(figure.data[-1].x), 5)

    def test_new_search_analyzes_contracted_cycles_not_source_graph(self):
        graph = split_k5()
        sizes = []

        def homfly(coords, tries):
            sizes.append(len(coords))
            return {'3_1': 1.0} if len(coords) > 5 else {'0_1': 1.0}

        with tempfile.TemporaryDirectory() as cache, \
             patch.object(ga, 'KNOT_CACHE_DIR', cache), \
             patch.object(ga, '_isolated_homfly', side_effect=homfly):
            result = ga.find_contracted_knotted_k5_minors(graph, time_limit=30)
        self.assertEqual(result, [])
        self.assertEqual(len(sizes), 37)
        self.assertLessEqual(max(sizes), 5)

    def test_knotted_contracted_candidate_is_returned(self):
        graph = trefoil_k5()
        with tempfile.TemporaryDirectory() as cache, \
             patch.object(ga, 'KNOT_CACHE_DIR', cache), \
             patch.object(ga, '_isolated_homfly', return_value={'3_1': 1.0}):
            result = ga.find_contracted_knotted_k5_minors(graph, max_results=1, time_limit=30)
        self.assertEqual(len(result), 1)
        self.assertEqual((len(result[0]), result[0].number_of_edges()), (5, 10))

    def test_failed_homfly_is_not_an_unknot(self):
        model = ga.find_contracted_k5_minors(split_k5(), max_results=1)[0]
        with tempfile.TemporaryDirectory() as cache, \
             patch.object(ga, 'KNOT_CACHE_DIR', cache), \
             patch.object(ga, '_isolated_homfly', return_value=None):
            with self.assertRaisesRegex(RuntimeError, 'HOMFLY failed'):
                ga.find_knotted_loops(ga.expand_k5_embedding(model), workers=1)

    def test_intersecting_embedding_is_rejected(self):
        graph = nx.complete_graph(5)
        for i in graph:
            graph.nodes[i]['coords'] = [math.cos(2 * math.pi * i / 5),
                                        math.sin(2 * math.pi * i / 5), 0]
        with self.assertRaisesRegex(ValueError, 'intersecting'):
            ga.find_contracted_k5_minors(graph, max_results=1)

    def test_contracted_cache_is_distinct_from_legacy(self):
        graph = split_k5()
        model = ga.find_contracted_k5_minors(graph, max_results=1)[0]
        expanded = ga.expand_k5_embedding(model)
        legacy = nx.Graph(expanded)
        legacy.graph.clear()
        self.assertNotEqual(ga._knot_cache_path(expanded, None, 500),
                            ga._knot_cache_path(legacy, None, 500))

    def test_real_homfly_knots_before_and_after_contraction(self):
        graph, cycle = split_k5_with_trefoil()
        source = ga._isolated_homfly([graph.nodes[n]['coords'] for n in cycle], 500)
        self.assertIsNotNone(ga.classify_homfly(source))
        with tempfile.TemporaryDirectory() as cache, patch.object(ga, 'KNOT_CACHE_DIR', cache):
            self.assertEqual(ga.find_contracted_knotted_k5_minors(graph, time_limit=120), [])
            retained = ga.find_contracted_knotted_k5_minors(trefoil_k5(), max_results=1, time_limit=120)
        self.assertEqual(len(retained), 1)
        self.assertTrue(retained[0].graph['knotted_loops'])

    def test_dash_selection_views_and_export(self):
        app = create_app(trefoil_k5())
        client = app.server.test_client()

        def call(output, values, changed):
            key = next(k for k in app.callback_map if output in k)
            callback = app.callback_map[key]
            outputs = callback['output']
            def spec(item):
                return {'id': item.component_id, 'property': item.component_property}
            response = client.post('/spatialgraphs/_dash-update-component', json={
                'output': key,
                'outputs': [spec(o) for o in outputs] if isinstance(outputs, list) else spec(outputs),
                'inputs': [dict(item, value=values.get(item['id'])) for item in callback['inputs']],
                'state': [dict(item, value=values.get(item['id'])) for item in callback['state']],
                'changedPropIds': [changed],
            })
            self.assertEqual(response.status_code, 200, response.data.decode())
            return response.get_json()['response']

        values = {'find-k33-btn': 0, 'find-k5-btn': 1, 'find-k33knot-btn': 0,
                  'find-k5knot-btn': 0, 'graph-version': 0, 'k5-representation': 'contracted'}
        result = call('find-message.children', values, 'find-k5-btn.n_clicks')
        self.assertEqual(result['mode']['value'], 'multi')
        self.assertEqual(result['find-message']['children'], '')
        values.update({'mode': 'multi', 'subgraph-index': 0, 'graph-version': 1,
                       'selected-obstruction-only': ['on'], 'simplify-subgraph': [],
                       'knot-index': 0, 'knot-version': 0, 'view-dim': '2d',
                       'edge-thickness': 3, 'rainbow-backbone': [], 'edge-color-attr': 'none',
                       'within-index': 0, 'within-version': 0, 'knot-in-original': [],
                       'rot3d': [15, 0, 0], 'show-grid': [], 'node-font-size': 14})
        elements = call('graph.elements', values, 'graph-version.data')['graph']['elements']
        self.assertEqual(sum(e.get('classes') == 'k5-bend' for e in elements), 25)
        figure = call('graph-3d.figure', values, 'graph-version.data')['graph-3d']['figure']
        self.assertEqual(len(figure['data'][-1]['text']), 5)
        values['export-sub-btn'] = 1
        exported = call('export-sub-download.data', values, 'export-sub-btn.n_clicks')
        data = json.loads(exported['export-sub-download']['data']['content'])
        self.assertEqual((len(data['nodes']), len(data['edges'])), (5, 10))
        self.assertTrue(any(edge['points'] for edge in data['edges']))
        self.assertTrue(all('branch_set' in node for node in data['nodes']))

        values.update({'k5-representation': 'legacy', 'find-k5-btn': 2})
        result = call('find-message.children', values, 'find-k5-btn.n_clicks')
        self.assertEqual(result['find-message']['children'], '')
        label = call('subgraph-info.children', values, 'graph-version.data')
        self.assertIn('legacy', label['subgraph-info']['children'])
        values.update({'k5-representation': 'contracted', 'find-k5knot-btn': 1})
        with tempfile.TemporaryDirectory() as cache, \
             patch.object(ga, 'KNOT_CACHE_DIR', cache), \
             patch.object(ga, '_isolated_homfly', return_value={'3_1': 1.0}):
            result = call('find-message.children', values, 'find-k5knot-btn.n_clicks')
        self.assertEqual(result['find-message']['children'], '')
        label = call('subgraph-info.children', values, 'graph-version.data')
        self.assertIn('Knotted contracted K_5', label['subgraph-info']['children'])


if __name__ == '__main__':
    unittest.main()
