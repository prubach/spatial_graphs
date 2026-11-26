import math
import json
import tempfile
import unittest
from unittest.mock import patch

import networkx as nx

import graph_algorithms as ga
from graph_visualization import build_3d_figure, build_elements
from graph_data import load_graph_by_id
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

    def test_contracted_knotted_search_is_unavailable(self):
        with self.assertRaisesRegex(ValueError, 'was removed'):
            ga.find_obstructions(split_k5(), 'k5knotcontracted')

    def test_original_cycle_lifting_and_comparisons(self):
        graph = split_k5()
        expanded = ga.expand_k5_embedding(ga.find_contracted_k5_minors(graph, max_results=1)[0])
        for cycle in nx.simple_cycles(expanded):
            if len(cycle) < 3:
                continue
            original = ga._original_k5_cycle(expanded, cycle)
            self.assertEqual(len(original), len(set(original)))
            self.assertTrue(all(graph.has_edge(u, v)
                                for u, v in zip(original, original[1:] + original[:1])))
        self.assertEqual(ga._compare_knot_labels('-3_1', '-3_1'), 'same')
        self.assertEqual(ga._compare_knot_labels('+3_1', '-3_1'), 'different')
        self.assertEqual(ga._compare_knot_labels('0_1', '-3_1'), 'different')
        self.assertEqual(ga._compare_knot_labels('3_1', '-3_1'), 'handedness unknown')
        self.assertEqual(ga._compare_knot_labels('3_1', '3_1'), 'handedness unknown')
        self.assertEqual(ga._compare_knot_labels('0_1', '0_1'), 'same')

    def test_disagreements_and_original_labels_survive_cache(self):
        graph = split_k5()
        expanded = ga.expand_k5_embedding(ga.find_contracted_k5_minors(graph, max_results=1)[0])
        with tempfile.TemporaryDirectory() as cache, patch.object(ga, 'KNOT_CACHE_DIR', cache):
            results = iter([item for _ in range(37) for item in
                            ({'+3_1': 0.9, '0_1': 0.1}, {'-3_1': 0.8, '0_1': 0.2})])
            with patch.object(ga, '_isolated_homfly', side_effect=lambda *args: next(results)):
                loops = ga.find_knotted_loops(expanded, workers=1)
            self.assertEqual(len(loops), 37)
            self.assertEqual(expanded.graph['contraction_disagreements'], 37)
            self.assertEqual(expanded.graph['contraction_disagreement_pairs'], [('-3_1', '+3_1')])
            self.assertTrue(all(lp['knot'] == '-3_1' and lp['prob'] == 0.8 and lp['unknot_prob'] == 0.2
                                and lp['contracted_knot'] == '+3_1'
                                and lp['source_comparison'] == 'different'
                                for lp in loops))
            expanded.graph.pop('contraction_disagreements')
            with patch.object(ga, '_isolated_homfly', side_effect=AssertionError('unexpected recomputation')):
                self.assertEqual(ga.find_knotted_loops(expanded, workers=1), loops)
            self.assertEqual(expanded.graph['contraction_disagreements'], 37)
            self.assertEqual(expanded.graph['contraction_disagreement_pairs'], [['-3_1', '+3_1']])

    def test_disappearing_knots_and_inconclusive_source(self):
        expanded = ga.expand_k5_embedding(ga.find_contracted_k5_minors(split_k5(), max_results=1)[0])
        with tempfile.TemporaryDirectory() as cache, patch.object(ga, 'KNOT_CACHE_DIR', cache):
            results = iter([item for _ in range(37) for item in ({'0_1': 1.0}, {'-3_1': 1.0})])
            with patch.object(ga, '_isolated_homfly', side_effect=lambda *args: next(results)):
                loops = ga.find_knotted_loops(expanded, workers=1)
            self.assertEqual(len(loops), 37)
            self.assertTrue(all(lp['knot'] == '-3_1' and lp['contracted_knot'] == '0_1' for lp in loops))
            self.assertEqual(expanded.graph['contraction_disagreements'], 37)
            self.assertEqual(expanded.graph['contraction_disagreement_pairs'], [('-3_1', '0_1')])
        with tempfile.TemporaryDirectory() as cache, patch.object(ga, 'KNOT_CACHE_DIR', cache):
            results = iter([item for _ in range(37) for item in ({'+3_1': 1.0}, {'0_1': 1.0})])
            with patch.object(ga, '_isolated_homfly', side_effect=lambda *args: next(results)):
                self.assertEqual(ga.find_knotted_loops(expanded, workers=1), [])
            self.assertEqual(expanded.graph['contraction_disagreement_pairs'], [('0_1', '+3_1')])
        with tempfile.TemporaryDirectory() as cache, patch.object(ga, 'KNOT_CACHE_DIR', cache), \
             patch.object(ga, '_isolated_homfly', side_effect=[{'0_1': 1.0}, {'TMC': 1.0}]):
            with self.assertRaisesRegex(RuntimeError, 'corresponding original'):
                ga.find_knotted_loops(expanded, workers=1)

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
        changed = expanded.copy()
        changed.graph['k5_source_graph'] = expanded.graph['k5_source_graph'].copy()
        source_node = next(n for n in changed.graph['k5_source_graph'] if n not in expanded)
        changed.graph['k5_source_graph'].nodes[source_node]['coords'] = [99, 98, 97]
        self.assertNotEqual(ga._knot_cache_path(expanded, None, 500),
                            ga._knot_cache_path(changed, None, 500))

    def test_dash_warns_for_contraction_disagreements(self):
        graph = split_k5()
        model = ga.find_contracted_k5_minors(graph, max_results=1)[0]
        app = create_app(graph)
        client = app.server.test_client()

        def call(output, values, changed):
            key = next(k for k in app.callback_map if output in k)
            callback = app.callback_map[key]
            def spec(item):
                return {'id': item.component_id, 'property': item.component_property}
            outputs = callback['output']
            response = client.post('/spatialgraphs/_dash-update-component', json={
                'output': key,
                'outputs': [spec(o) for o in outputs] if isinstance(outputs, list) else spec(outputs),
                'inputs': [dict(item, value=values.get(item['id'])) for item in callback['inputs']],
                'state': [dict(item, value=values.get(item['id'])) for item in callback['state']],
                'changedPropIds': [changed],
            })
            self.assertEqual(response.status_code, 200, response.data.decode())
            return response.get_json()['response']

        def find_loops(expanded, positions, **kwargs):
            expanded.graph['contraction_disagreements'] = 1
            expanded.graph['contraction_disagreement_pairs'] = [('-3_1', '+3_1')]
            return [{'nodes': list(next(nx.simple_cycles(expanded))), 'knot': '-3_1', 'prob': 1.0,
                     'unknot_prob': 0.0, 'source_knot': '-3_1', 'contracted_knot': '+3_1',
                     'source_comparison': 'different'}]

        values = {'obstruction-method': 'k5contracted', 'graph-version': 0}
        with patch('dash_graphs.find_obstructions', return_value=[model]), \
             patch('dash_graphs.find_knotted_loops', side_effect=find_loops), \
             patch('dash_graphs.threading.Thread.start'):
            call('obstruction-method-error.children', values, 'obstruction-method.value')
            values.update({'mode': 'multi', 'subgraph-index': 0, 'graph-version': 1,
                           'simplify-subgraph': [], 'within-index': 0, 'within-version': 0,
                           'within-btn': 1, 'within-prev-btn': 0, 'within-next-btn': 0,
                           'within-poll': 0, 'run-homfly-btn': 1})
            result = call('within-info.children', values, 'within-btn.n_clicks')
            text = str(result['within-info']['children'])
            self.assertIn('WARNING', text)
            self.assertIn('Knot 1 of 1: -3_1', text)
            self.assertIn('drawn contracted cycle: +3_1', text)
            result = call('homfly-result.children', values, 'run-homfly-btn.n_clicks')
            text = str(result['homfly-result']['children'])
            self.assertIn('WARNING', text)
            self.assertIn('knot_type: -3_1', text)
            self.assertIn('Contracted cycle: +3_1', text)

    def test_protein_minor_uses_original_trefoil_handedness(self):
        roots = ['104_CA', '506_CA', '512_CA', '508_CA', '445_CA']
        trees = [
            [('104_CA', '106_CA'), ('106_CA', '106_CG'), ('106_CG', '106_NE2'), ('106_NE2', '702_CU2')],
            [('506_CA', '507_CA')],
            [('512_CA', '512_ND1'), ('512_ND1', '701_CU')],
            [('508_CA', '508_CG'), ('508_CG', '508_NE2'), ('508_NE2', '702_CU3')],
            [('445_CA', '448_CA'), ('448_CA', '450_CA')],
        ]
        paths = [
            ['702_CU2', '506_NE2', '506_CG', '506_CA'],
            ['104_CA', '92_CA', '81_CA', '81_SG', '538_SG', '538_CA', '512_CA'],
            ['104_CA', '104_CG', '104_NE2', '702_CU3'],
            ['702_CU2', '450_NE2', '450_CG', '450_CA'],
            ['507_CA', '507_SG', '701_CU'],
            ['507_CA', '508_CA'],
            ['506_CA', '450_CA'],
            ['512_CA', '508_CA'],
            ['701_CU', '445_ND1', '445_CA'],
            ['702_CU3', '62_ND1', '62_CA', '60_CA', '19_CA', '19_SG',
             '201_SG', '201_CA', '286_CA', '445_CA'],
        ]
        for pdb, mapping in [('1AOZ', {}), ('1ASO', {
                '701_CU': '554_CU', '702_CU2': '555_CU', '702_CU3': '556_CU'})]:
            with self.subTest(pdb=pdb):
                graph, _ = load_graph_by_id(pdb, False)
                rename = lambda n: mapping.get(n, n)
                adj = {n: {} for n in roots}
                paths_iter = iter(paths)
                for i, u in enumerate(roots):
                    for v in roots[i + 1:]:
                        path = list(map(rename, next(paths_iter)))
                        edges = list(zip(path, path[1:]))
                        self.assertTrue(all(graph.has_edge(*edge) for edge in edges))
                        adj[u][v] = adj[v][u] = edges
                branch_trees = {root: [(rename(u), rename(v)) for u, v in tree]
                                for root, tree in zip(roots, trees)}
                contracted = ga._contracted_k5(graph, (adj, branch_trees))
                ga.validate_k5_embedding(contracted)
                expanded = ga.expand_k5_embedding(contracted)
                with tempfile.TemporaryDirectory() as cache, patch.object(ga, 'KNOT_CACHE_DIR', cache):
                    loops = ga.find_knotted_loops(expanded, workers=4)
                self.assertTrue(loops)
                self.assertEqual({loop['knot'] for loop in loops}, {'-3_1'})
                self.assertTrue(all(loop['knot'] == loop['source_knot'] for loop in loops))

    def test_highlight_selected_contracted_source_in_both_views_and_export(self):
        first = split_k5()
        second = split_k5()
        for node in second:
            second.nodes[node]['coords'][0] += 4
        graph = nx.disjoint_union(first, second)
        models = [ga.find_contracted_k5_minors(graph.subgraph(nodes), max_results=1)[0]
                  for nodes in (range(10), range(10, 20))]
        expected = {frozenset(map(str, edge)) for edge in models[1].graph['source_edges']}
        expected_nodes = {node for edge in expected for node in edge}

        with patch('dash_graphs.find_obstructions', side_effect=lambda g, method, **kw:
                   models if method in ('k5contracted', 'k5knotcontracted') else []):
            app = create_app(graph)
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

            values = {'obstruction-method': 'k5contracted', 'graph-version': 0}
            call('obstruction-method-error.children', values, 'obstruction-method.value')
            values.update({'mode': 'highlight', 'subgraph-index': 1, 'graph-version': 1,
                           'selected-obstruction-only': ['on'], 'simplify-subgraph': [],
                           'knot-index': 0, 'knot-version': 0, 'view-dim': '2d',
                           'edge-thickness': 3, 'rainbow-backbone': [], 'edge-color-attr': 'none',
                           'within-index': 0, 'within-version': 0, 'knot-in-original': [],
                           'rot3d': [0, 0, 0], 'show-grid': [], 'node-font-size': 14})
            elements = call('graph.elements', values, 'graph-version.data')['graph']['elements']
            highlighted = {frozenset((e['data']['source'], e['data']['target'])) for e in elements
                           if e.get('classes') == 'obstruction' and 'source' in e['data']}
            self.assertEqual(highlighted, expected)
            self.assertEqual({e['data']['id'] for e in elements
                              if e.get('classes') == 'obstruction' and 'source' not in e['data']},
                             expected_nodes)
            markers = [e for e in elements if e.get('classes') == 'crossing-marker']
            self.assertTrue(markers)
            for marker in markers:
                for i in (1, 2):
                    if frozenset(marker['data'][f'e{i}']) in expected:
                        self.assertEqual(marker['data'][f'c{i}'], 'crimson')
            figure = call('graph-3d.figure', values, 'graph-version.data')['graph-3d']['figure']
            node_trace = figure['data'][-1]
            self.assertEqual(set(node_trace['text']), set(map(str, graph)))
            self.assertEqual({n for n, color in zip(node_trace['text'], node_trace['marker']['color'])
                              if color == 'crimson'}, expected_nodes)
            values['export-sub-btn'] = 1
            exported = call('export-sub-download.data', values, 'export-sub-btn.n_clicks')
            data = json.loads(exported['export-sub-download']['data']['content'])
            self.assertEqual({frozenset(e) for e in data['highlighted_edges']}, expected)
            self.assertEqual(len(data['nodes']), len(graph))

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
        with patch('dash_graphs.find_obstructions', return_value=[trefoil_k5()]) as finder:
            result = call('find-message.children', values, 'find-k5knot-btn.n_clicks')
        self.assertEqual(finder.call_args.args[1], 'k5knot')
        self.assertEqual(result['find-message']['children'], '')
        label = call('subgraph-info.children', values, 'graph-version.data')
        self.assertIn('K_5 model containing a knotted loop', label['subgraph-info']['children'])


if __name__ == '__main__':
    unittest.main()
