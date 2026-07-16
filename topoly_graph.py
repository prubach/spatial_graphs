from topoly.graph import Graph
from time import time
import networkx as nx
import logging
log = logging.getLogger()

bridges_expected = {'1a8e':
        {'all': [[9, 48], [19, 39], [118, 194], [137, 331], [158, 174], [161, 179], [171, 177], [227, 241], [63, 95],
                 [188, 63], [249, 63], [188, 95], [249, 95], [249, 188]],
         'ssbond': [[9, 48], [19, 39], [118, 194], [137, 331], [158, 174], [161, 179], [171, 177], [227, 241]],
         'ion': [[63, 95], [188, 63], [249, 63], [188, 95], [249, 95], [249, 188]],
         'covalent': []},

                    '1rpb':
        {'all': [[1, 13], [7, 19], [1, 9]],
         'ssbond': [[1, 13], [7, 19]],
         'ion': [],
         'covalent': [[1, 9]]}}

def test_bridges():
    log.info("Testing different bridges types")
    bridges = {}
    for code in bridges_expected.keys():
        bridges[code] = {}
        for bridge_type in ['all', 'ssbond', 'ion', 'covalent']:
            g = Graph('data/' + code + '.pdb', bridges_type=bridge_type)
            edges = []
            for n in range(len(g.arcs)-1):
                arc = g.arcs[n]
                if [arc[0], arc[-1]] not in g.bridges:
                    edges.append([arc[0], arc[-1], 'Ca'])
            for br in g.bridges:
                edges.append([br[0], br[1], 'B'])
            print(code + ' ' + bridge_type + ": ", end="")
            print(edges)
            bridges[code][bridge_type] = g.bridges

    log.info("Results:")
    log.info(str(bridges))
    assert bridges == bridges_expected



def find_non_planar_subgraph(G):
    # Check if graph is planar
    is_planar, obstruction = nx.check_planarity(G)

    if is_planar:
        return "The graph is planar. No non-planar subgraphs exist."
    else:
        print("The graph is non-planar. The Kuratowski subgraph is:")
        return obstruction




if __name__ == '__main__':
    test_bridges()

    # --- Example Usage ---
    # Create K5 (a known non-planar graph)
    K5 = nx.complete_graph(5)

    subgraph = find_non_planar_subgraph(K5)
    print(subgraph.edges())