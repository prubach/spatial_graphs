import random
import unittest

import networkx as nx

import theta_classification as tc


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


if __name__ == '__main__':
    unittest.main()
