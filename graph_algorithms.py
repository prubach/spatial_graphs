"""Graph search, obstruction, and knot-analysis algorithms."""

import logging
import multiprocessing as mp
import os
import random
import re
import threading
import time

import networkx as nx
import topoly as tp
from topoly.params import OutputType
from ogdf_python import *

def create_graph(seed=42,n_cliques=5,n_bicliques=6,n_random_edges=10):
    random.seed(seed)
    G=nx.Graph()
    nxt=0
    def new_nodes(n):
        nonlocal nxt
        r=list(range(nxt,nxt+n)); nxt+=n; return r
    cliques=[]
    shared=new_nodes(3)
    for i in range(n_cliques):
        clique=shared+new_nodes(2) if i==0 else random.sample(cliques[-1],3)+new_nodes(2)
        cliques.append(clique)
        for a in range(len(clique)):
            for b in range(a+1,len(clique)):
                G.add_edge(clique[a],clique[b])
    for _ in range(n_bicliques):
        left=random.sample(random.choice(cliques),3)
        right=(random.sample(list(G.nodes()),2)+new_nodes(1)) if random.random()<0.5 else new_nodes(3)
        for u in left:
            for v in right:
                G.add_edge(u,v)
    nodes=list(G.nodes())
    for _ in range(n_random_edges):
        u,v=random.sample(nodes,2); G.add_edge(u,v)
    return G
def find_multiple_kuratowski_subgraphs(graph):
    """Finds distinct Kuratowski subgraphs by breaking found structures."""
    G_copy = graph.copy()
    subgraphs = []

    while True:
        is_planar, certificate = nx.check_planarity(G_copy, counterexample=True)
        if is_planar:
            break
        print("Found a Kuratowski subgraph:")
        nodes = sorted(certificate.nodes(), key=lambda e: int(e))
        print(f'nodes: {nodes}')
        edges = sorted(certificate.edges(), key=lambda e: int(e[0]) * 1000 + int(e[1]))
        print(f'edges: {edges}')

        print("Full graph:")
        nodes = sorted(G_copy.nodes(), key=lambda e: int(e))
        print(f'nodes: {nodes}')
        #edges = sorted(G_copy.edges(), key=lambda e: int(e[0]) * 1000 + int(e[1]))
        edges = G_copy.edges()
        print(f'edges: {edges}')

        #for e in certificate.edges():
        #    print(f'edge: {e}')
        # Save the found subgraph
        subgraphs.append(certificate)
        # Remove an edge from the identified subgraph to force the algorithm
        # to look for a different non-planar structure in the next iteration

        edges_to_remove = list(certificate.edges())
        if edges_to_remove:
            G_copy.remove_edge(*edges_to_remove[0])
        else:
            break
    return subgraphs
def find_multiple_kuratowski_subgraphs_ogdf(graph):
    """Extracts all Kuratowski (K5/K3,3) subdivisions from `graph` using OGDF's
    Boyer-Myrvold planarity test, which finds them all in a single linear-time pass
    instead of repeatedly re-running planarity checks like the networkx-only version."""
    cppinclude("ogdf/planarity/BoyerMyrvold.h")

    G = ogdf.Graph()
    node_to_ogdf = {}
    ogdf_index_to_node = {}
    for node in graph.nodes():
        onode = G.newNode()
        node_to_ogdf[node] = onode
        ogdf_index_to_node[onode.index()] = node
    for u, v in graph.edges():
        G.newEdge(node_to_ogdf[u], node_to_ogdf[v])

    bm = ogdf.BoyerMyrvold()
    kuratowski_list = ogdf.SList[ogdf.KuratowskiWrapper]()
    # embeddingGrade=-1 (doFindUnlimited) extracts every subdivision instead of
    # stopping at the first one; avoidE2Minors=True keeps the results unique.
    is_planar = bm.planarEmbed(G, kuratowski_list, -1, False, False, False, True)
    if is_planar:
        return []

    subgraphs = []
    for wrapper in kuratowski_list:
        sub = nx.Graph()
        for e in wrapper.edgeList:
            u = ogdf_index_to_node[e.source().index()]
            v = ogdf_index_to_node[e.target().index()]
            sub.add_edge(u, v)
        subgraphs.append(sub)
    return subgraphs
def _find_multiple_kuratowski_subgraphs_sage(graph):
    """Finds distinct Kuratowski subgraphs with SageMath's Graph.is_planar(kuratowski=True),
    which returns one subgraph per call, so an edge of each found subgraph is removed before searching again."""
    try:
        from sage.graphs.graph import Graph as SageGraph
    except ImportError as e:
        raise RuntimeError("SageMath is not available in this Python environment (cannot import 'sage')") from e
    G = SageGraph([list(graph.nodes()), list(graph.edges())], format='vertices_and_edges')
    subgraphs = []
    while True:
        planar, cert = G.is_planar(kuratowski=True)
        if planar:
            break
        sub = nx.Graph()
        sub.add_edges_from((u, v) for u, v, *_ in cert.edges(sort=False))
        subgraphs.append(sub)
        G.delete_edge(*next(iter(sub.edges())))
    return subgraphs
def _sage_kuratowski_worker(conn, graph):
    try:
        from sage.all import ZZ
        from sage.graphs.graph import Graph as SageGraph
        import os
        import sys
        # print("Python:", sys.executable)
        # print("Working directory:", os.getcwd())
        # print("PYTHONPATH:", os.environ.get("PYTHONPATH"))
        # print("sys.path:", sys.path)
        conn.send((True, _find_multiple_kuratowski_subgraphs_sage(graph)))
    except Exception as e:
        conn.send((False, str(e)))
    finally:
        conn.close()
def find_multiple_kuratowski_subgraphs_sage(graph):
    """Run SageMath in a child process, where its signal handlers can be installed."""
    ctx = mp.get_context('fork')
    recv, send = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_sage_kuratowski_worker, args=(send, graph), daemon=True)
    try:
        proc.start()
        send.close()
        try:
            succeeded, result = recv.recv()
        except EOFError as e:
            raise RuntimeError(f"SageMath worker crashed (exit code {proc.exitcode})") from e
        if not succeeded:
            raise RuntimeError(f"SageMath worker failed: {result}")
        return result
    finally:
        send.close()
        if proc.is_alive():
            proc.kill()
        proc.join()
        recv.close()
def kuratowski_subgraph_type(subgraph):
    """Identify a Kuratowski subdivision by suppressing its degree-2 path vertices."""
    branch_nodes = {node for node, degree in subgraph.degree() if degree != 2}
    if not branch_nodes:
        return "unknown Kuratowski type"

    core = nx.Graph()
    core.add_nodes_from(branch_nodes)
    visited_edges = set()
    for start in branch_nodes:
        for neighbor in subgraph.neighbors(start):
            first_edge = frozenset((start, neighbor))
            if first_edge in visited_edges:
                continue
            visited_edges.add(first_edge)
            previous, current = start, neighbor
            while current not in branch_nodes:
                next_nodes = [node for node in subgraph.neighbors(current) if node != previous]
                if len(next_nodes) != 1:
                    break
                following = next_nodes[0]
                visited_edges.add(frozenset((current, following)))
                previous, current = current, following
            if current in branch_nodes:
                core.add_edge(start, current)

    if nx.is_isomorphic(core, nx.complete_graph(5)):
        return "K_5 subdivision (implies a K_5 minor)"
    if nx.is_isomorphic(core, nx.complete_bipartite_graph(3, 3)):
        return "K_3,3 subdivision (implies a K_3,3 minor)"
    return "unknown Kuratowski type"
def _find_k5_minor(graph, deadline, seen):
    """Search `graph` for a K_5 minor by exhaustive edge contraction (after removing degree <=1 vertices and
    suppressing degree-2 ones, which preserve K_5 minors). Every reduced vertex keeps the original tree edges
    of its branch set and every reduced edge the original edges of the path realizing it, so a hit can be
    mapped back. Returns the list of original edges of the minor model, or None."""
    adj = {u: {v: [(u, v)] for v in graph[u]} for u in graph}
    tree = {u: [] for u in graph}

    def rec(adj, tree):
        if time.monotonic() > deadline:
            raise TimeoutError
        adj = {u: dict(nb) for u, nb in adj.items()}
        tree = dict(tree)
        changed = True
        while changed:
            changed = False
            for n in list(adj):
                nb = adj[n]
                if len(nb) <= 1:
                    for m in nb:
                        del adj[m][n]
                    del adj[n]
                    changed = True
                elif len(nb) == 2:
                    (a, la), (b, lb) = nb.items()
                    del adj[a][n], adj[b][n], adj[n]
                    if b not in adj[a]:
                        adj[a][b] = adj[b][a] = la + lb + tree[n]
                    changed = True
        n_v = len(adj)
        if n_v < 5 or sum(map(len, adj.values())) < 20:
            return None
        if n_v == 5:
            return [e for u in adj for v in adj[u] if u < v for e in adj[u][v]] + [e for t in tree.values() for e in t] \
                if all(len(nb) == 4 for nb in adj.values()) else None
        key = frozenset(frozenset((u, v)) for u in adj for v in adj[u])
        if key in seen:
            return None
        seen.add(key)
        for u in list(adj):
            for v in list(adj[u]):
                if not (u < v):
                    continue
                h = {x: dict(nb) for x, nb in adj.items()}
                t = dict(tree)
                t[u] = t[u] + t[v] + h[u][v]
                del t[v]
                for w, lab in h[v].items():
                    del h[w][v]
                    if w != u and w not in h[u]:
                        h[u][w] = h[w][u] = lab
                del h[v]
                res = rec(h, t)
                if res:
                    return res
        return None

    return rec(adj, tree)
def find_k5_minors(graph, max_results=20, time_limit=60):
    """Return up to `max_results` subgraphs, each a K_5 minor model (5 connected branch sets plus the 10 edges
    joining them). After each hit one edge of the model is deleted so the next search finds a different one."""
    work = nx.Graph(graph)
    deadline = time.monotonic() + time_limit
    negative = set()
    results = []
    try:
        while max_results is None or len(results) < max_results:
            hit = None
            for comp in nx.biconnected_components(work):
                if len(comp) < 5:
                    continue
                sub = work.subgraph(comp)
                key = frozenset(frozenset(e) for e in sub.edges())
                if key in negative:
                    continue
                hit = _find_k5_minor(sub, deadline, set())
                if hit:
                    break
                negative.add(key)
            if not hit:
                break
            model = nx.Graph(hit)
            # contracted branch sets can keep dangling tree edges that no K_5 edge uses
            leaves = [n for n in model if model.degree(n) <= 1]
            while leaves:
                model.remove_nodes_from(leaves)
                leaves = [n for n in model if model.degree(n) <= 1]
            model.graph['kind'] = 'K_5 minor'
            results.append(model)
            work.remove_edge(*hit[0])
    except TimeoutError:
        log.warning('K_5 minor search stopped after %ss; %d found', time_limit, len(results))
    return results
def enumerate_k33_subdivisions(graph, must_contain=None, limit=100000):
    """All K_3,3 subdivisions of `graph` (OGDF/SageMath only report a few), as nx graphs.
    Each biconnected component is reduced to its topological core (chains of degree-2 nodes become single
    edges); a K_3,3 subdivision is what is left after deleting cyclomatic-4 core edges and pruning.
    `must_contain` (iterable of node pairs) keeps only subdivisions containing all those edges."""
    import time
    from itertools import combinations
    from math import comb
    required = {frozenset(e) for e in (must_contain or ())}
    results, unique = [], set()
    for block in nx.biconnected_components(graph):
        if len(block) < 6:
            continue
        H = graph.subgraph(block)
        branch = {n for n in H if H.degree(n) >= 3}
        if len(branch) < 6:
            continue
        chains, seen = [], set()
        for b in branch:
            for nb in H.neighbors(b):
                if frozenset((b, nb)) in seen:
                    continue
                path, prev, cur = [b, nb], b, nb
                while cur not in branch:
                    nxt = [x for x in H.neighbors(cur) if x != prev][0]
                    path.append(nxt)
                    prev, cur = cur, nxt
                for a, c in zip(path, path[1:]):
                    seen.add(frozenset((a, c)))
                chains.append((path[0], path[-1], path))
        if len(chains) - len(branch) + 1 < 4:
            continue
        # a chain that holds a required edge can never be deleted
        keep = [i for i, (_, _, path) in enumerate(chains)
                if any(frozenset(e) in required for e in zip(path, path[1:]))]
        deletable = [i for i in range(len(chains)) if i not in keep]
        r = len(chains) - len(branch) + 1 - 4
        total = comb(len(deletable), r)
        if total > 100000:
            _log(f'  K_3,3 enumeration: {total} edge-removal combinations in a block of {len(block)} nodes')
        last_log = time.time()
        for n_done, removed in enumerate(combinations(deletable, r)):
            if total > 100000 and time.time() - last_log > 10:
                last_log = time.time()
                _log(f'  K_3,3 enumeration: {n_done}/{total} combinations ({len(results)} found)')
            gone = set(removed)
            core = nx.MultiGraph()
            for i, (u, v, _) in enumerate(chains):
                if i not in gone:
                    core.add_edge(u, v, key=i)
            leaves = [n for n in core if core.degree(n) <= 1]
            while leaves:
                core.remove_nodes_from(leaves)
                leaves = [n for n in core if core.degree(n) <= 1]
            degrees = dict(core.degree())
            if (not core or max(degrees.values()) > 3 or sum(1 for d in degrees.values() if d == 3) != 6
                    or not nx.is_connected(core)):
                continue
            # chains were cut at the original branch nodes, so degree-2 ones need suppressing
            sg = nx.Graph()
            for _, _, key in core.edges(keys=True):
                sg.add_edges_from(zip(chains[key][2], chains[key][2][1:]))
            hubs = [n for n in sg if sg.degree(n) == 3]
            simple = nx.Graph()
            for h in hubs:
                for nb in sg.neighbors(h):
                    prev, cur = h, nb
                    while sg.degree(cur) == 2:
                        nxt = [x for x in sg.neighbors(cur) if x != prev][0]
                        prev, cur = cur, nxt
                    simple.add_edge(h, cur)
            if (simple.number_of_nodes() != 6 or simple.number_of_edges() != 9
                    or not nx.is_isomorphic(simple, nx.complete_bipartite_graph(3, 3))):
                continue
            key = frozenset(frozenset(e) for e in sg.edges())
            if key in unique:
                continue
            unique.add(key)
            sg.graph['kind'] = 'K_3,3'
            results.append(sg)
            if len(results) >= limit:
                return results
    return results
def find_knotted_k33_subgraphs(graph, node_pos_3d=None, params=None, limit=100):
    """K_3,3 subdivisions that contain a knotted loop of `graph`, smallest first (at most `limit`).
    OGDF/SageMath report only a few subdivisions, which can all be unknotted, so these are enumerated
    from the knotted loops: a subdivision is knotted when one of its cycles is."""
    found = {}
    loops = find_knotted_loops(graph, node_pos_3d, params=params)
    _log(f'Knotted K_3,3 search: {len(loops)} knotted loops to expand')
    # per-loop results are stored so an interrupted search resumes where it stopped
    path = _knot_cache_path(graph, node_pos_3d, 500, kind='k33knot', params=params)
    stored = (_read_json(path) or {}).get('loops', {})
    by_str = {str(n): n for n in graph.nodes()}
    for i, lp in enumerate(loops):
        key = ','.join(sorted(str(n) for n in lp['nodes']))
        if key in stored:
            subs = [nx.Graph([(by_str[u], by_str[v]) for u, v in edges]) for edges in stored[key]]
            for sg in subs:
                sg.graph['kind'] = 'K_3,3'
        else:
            subs = enumerate_k33_subdivisions(graph, must_contain=loop_edges(lp['nodes']))
            stored[key] = [[[str(u), str(v)] for u, v in sg.edges()] for sg in subs]
            _write_json(path, dict(params=dict(params or {}, kind='k33knot'), loops=stored))
        _log(f'Knotted K_3,3 search: loop {i + 1}/{len(loops)} ({len(lp["nodes"])} nodes) -> {len(subs)} K_3,3 subdivisions')
        for sg in subs:
            ek = frozenset(frozenset(e) for e in sg.edges())
            if ek not in found:
                sg.graph['kind'] = 'K_3,3'
                sg.graph['sources'] = ['knotted loop']
                found[ek] = sg
    return sorted(found.values(), key=lambda g: (g.number_of_nodes(), sorted(map(str, g.nodes()))))[:limit]
def enumerate_k5_minors(graph, must_contain=None, limit=1000, deadline=None):
    """All minimal K_5 minor models of `graph` (5 branch trees plus the 10 joining edges; cyclomatic number 6)
    that contain every edge of `must_contain`. Each biconnected component is reduced to its core (chains of
    degree-2 nodes become single edges); a model is what is left after deleting cyclomatic-6 core edges and
    pruning. Chains holding a required edge are never deleted, so a long knotted loop leaves few choices."""
    from itertools import combinations
    from math import comb
    required = {frozenset(e) for e in (must_contain or ())}
    results, unique = [], set()
    for block in nx.biconnected_components(graph):
        if len(block) < 5:
            continue
        H = graph.subgraph(block)
        if any(e not in {frozenset(x) for x in H.edges()} for e in required) and required:
            continue
        branch = {n for n in H if H.degree(n) >= 3}
        chains, seen = [], set()
        for b in branch:
            for nb in H.neighbors(b):
                if frozenset((b, nb)) in seen:
                    continue
                path, prev, cur = [b, nb], b, nb
                while cur not in branch:
                    nxt = [x for x in H.neighbors(cur) if x != prev][0]
                    path.append(nxt)
                    prev, cur = cur, nxt
                for a, c in zip(path, path[1:]):
                    seen.add(frozenset((a, c)))
                chains.append((path[0], path[-1], path))
        r = len(chains) - len(branch) + 1 - 6
        if r < 0:
            continue
        keep = [i for i, (_, _, path) in enumerate(chains)
                if any(frozenset(e) in required for e in zip(path, path[1:]))]
        deletable = [i for i in range(len(chains)) if i not in keep]
        if r > len(deletable):
            continue
        total = comb(len(deletable), r)
        if total > 100000:
            _log(f'  K_5 enumeration: {total} edge-removal combinations in a block of {len(block)} nodes')
        for removed in combinations(deletable, r):
            if deadline is not None and time.monotonic() > deadline:
                raise TimeoutError
            gone = set(removed)
            core = nx.MultiGraph()
            for i, (u, v, _) in enumerate(chains):
                if i not in gone:
                    core.add_edge(u, v, key=i)
            leaves = [n for n in core if core.degree(n) <= 1]
            while leaves:
                core.remove_nodes_from(leaves)
                leaves = [n for n in core if core.degree(n) <= 1]
            if core.number_of_nodes() < 5 or not nx.is_connected(core):
                continue
            sg = nx.Graph()
            for _, _, key in core.edges(keys=True):
                sg.add_edges_from(zip(chains[key][2], chains[key][2][1:]))
            ek = frozenset(frozenset(e) for e in sg.edges())
            if ek in unique:
                continue
            unique.add(ek)
            try:
                hit = _find_k5_minor(sg, time.monotonic() + 60, set())
            except TimeoutError:
                continue
            if not hit:
                continue
            sg.graph['kind'] = 'K_5 minor'
            results.append(sg)
            if len(results) >= limit:
                return results
    return results
def find_knotted_k5_minors(graph, node_pos_3d=None, params=None, max_results=None, time_limit=120):
    """K_5 minor models that contain a knotted loop of `graph`.
    The models are enumerated from the knotted loops (a model is knotted when one of its cycles is),
    until none remain or the time limit is reached."""
    loops = find_knotted_loops(graph, node_pos_3d, params=params)
    deadline = time.monotonic() + time_limit
    found = {}
    # per-loop results (also empty ones) are stored so the search is not repeated
    path = _knot_cache_path(graph, node_pos_3d, 500, kind='k5knot', params=params)
    stored = (_read_json(path) or {}).get('loops', {})
    by_str = {str(n): n for n in graph.nodes()}
    try:
        for i, lp in enumerate(loops):
            key = ','.join(sorted(str(n) for n in lp['nodes']))
            if key in stored:
                models = [nx.Graph([(by_str[u], by_str[v]) for u, v in edges]) for edges in stored[key]]
            else:
                models = enumerate_k5_minors(graph, must_contain=loop_edges(lp['nodes']), deadline=deadline)
                stored[key] = [[[str(u), str(v)] for u, v in m.edges()] for m in models]
                _write_json(path, dict(params=dict(params or {}, kind='k5knot'), loops=stored))
            _log(f'Knotted K_5 search: loop {i + 1}/{len(loops)} ({len(lp["nodes"])} nodes) -> {len(models)} K_5 minors')
            for model in models:
                ek = frozenset(frozenset(e) for e in model.edges())
                if ek not in found:
                    model.graph['kind'] = 'K_5 minor'
                    model.graph['sources'] = ['knotted loop']
                    found[ek] = model
                    if max_results is not None and len(found) >= max_results:
                        raise StopIteration
    except TimeoutError:
        log.warning('Knotted K_5 minor search stopped after %ss; %d found', time_limit, len(found))
    except StopIteration:
        pass
    return sorted(found.values(), key=lambda g: (g.number_of_nodes(), sorted(map(str, g.nodes()))))
def find_k33_subgraphs(graph):
    """All K_3,3 subdivisions found by OGDF and SageMath, merged and deduplicated by edge set.
    Each subgraph records in graph['sources'] which finder(s) reported it; a finder that fails is skipped."""
    merged = {}
    errors = []
    for key, label, finder in (("ogdf", "OGDF", find_multiple_kuratowski_subgraphs_ogdf),
                               ("sage", "SageMath", find_multiple_kuratowski_subgraphs_sage)):
        try:
            found = finder(graph)
        except Exception as e:
            errors.append(f"{label}: {e}")
            continue
        for sg in found:
            if not kuratowski_subgraph_type(sg).startswith("K_3,3"):
                continue
            edges = frozenset(frozenset(e) for e in sg.edges())
            if edges not in merged:
                sg.graph['kind'] = 'K_3,3'
                sg.graph['sources'] = []
                merged[edges] = sg
            merged[edges].graph['sources'].append(label)
    if len(errors) == 2:
        raise RuntimeError("; ".join(errors))
    return list(merged.values())
def find_obstructions(graph, method="ogdf", **kwargs):
    """Return obstruction subgraphs found by `method`."""
    if method == "k33":
        return find_k33_subgraphs(graph)
    if method == "k5":
        return find_k5_minors(graph)
    if method == "k33knot":
        return find_knotted_k33_subgraphs(graph, **kwargs)
    if method == "k5knot":
        return find_knotted_k5_minors(graph, **kwargs)
    if method == "sage":
        return find_multiple_kuratowski_subgraphs_sage(graph)
    return find_multiple_kuratowski_subgraphs_ogdf(graph)
def simplify_subgraph_topoly(selected_graph, node_pos_3d=None, method='kmt'):
    """Simplify a subgraph (e.g. Kuratowski subdivision) by generating a Topoly
    Graph object from its 3D arcs and applying its reduce() method."""
    if selected_graph.number_of_edges() == 0:
        return selected_graph.copy()

    # Map reduction method string to topoly ReduceMethod if needed
    reduce_method = method
    if isinstance(method, str):
        from topoly.params import ReduceMethod
        method_upper = method.upper()
        if hasattr(ReduceMethod, method_upper):
            reduce_method = getattr(ReduceMethod, method_upper)

    branch_nodes = [n for n in selected_graph.nodes() if selected_graph.degree(n) != 2]
    visited = set()
    arcs = []
    for u in branch_nodes:
        for v in selected_graph.neighbors(u):
            e = frozenset((u, v))
            if e in visited:
                continue
            visited.add(e)
            path = [u, v]
            curr, prev = v, u
            while selected_graph.degree(curr) == 2 and curr not in branch_nodes:
                nbrs = [n for n in selected_graph.neighbors(curr) if n != prev]
                if not nbrs:
                    break
                nxt = nbrs[0]
                visited.add(frozenset((curr, nxt)))
                path.append(nxt)
                prev, curr = curr, nxt
            arcs.append(path)
    for u, v in selected_graph.edges():
        e = frozenset((u, v))
        if e in visited:
            continue
        visited.add(e)
        path = [u, v]
        curr, prev = v, u
        while curr != u:
            nbrs = [n for n in selected_graph.neighbors(curr) if n != prev]
            if not nbrs:
                break
            nxt = nbrs[0]
            visited.add(frozenset((curr, nxt)))
            path.append(nxt)
            prev, curr = curr, nxt
        arcs.append(path)

    node_to_id = {n: i for i, n in enumerate(selected_graph.nodes())}
    id_to_node = {i: n for n, i in node_to_id.items()}

    arcs_4d = []
    for p in arcs:
        arc = []
        for n in p:
            c = selected_graph.nodes[n].get('coords')
            if c is None and node_pos_3d is not None:
                c = node_pos_3d.get(n)
            if c is None:
                c = (0.0, 0.0, 0.0)
            arc.append([node_to_id[n], float(c[0]), float(c[1]), float(c[2])])
        arcs_4d.append(arc)

    try:
        tp_g = tp.Graph(arcs_4d)
        tp_g.reduce(method=reduce_method)
    except Exception:
        return selected_graph.copy()

    simp_g = nx.Graph()
    for n in selected_graph.nodes():
        idx = node_to_id[n]
        if idx in tp_g.coordinates:
            c = selected_graph.nodes[n].get('coords')
            if c is None and node_pos_3d is not None:
                c = node_pos_3d.get(n)
            if c is None:
                c = tuple(tp_g.coordinates[idx])
            simp_g.add_node(n, coords=c)

    for arc in tp_g.arcs:
        for i in range(len(arc) - 1):
            u = id_to_node.get(arc[i])
            v = id_to_node.get(arc[i+1])
            if u is None or v is None or u == v:
                continue
            if selected_graph.has_edge(u, v):
                attrs = dict(selected_graph[u][v])
            else:
                orig_path = None
                for p in arcs:
                    if u in p and v in p:
                        orig_path = p
                        break
                attrs = {}
                if orig_path:
                    iu, iv = orig_path.index(u), orig_path.index(v)
                    if iu > iv:
                        iu, iv = iv, iu
                    sub = orig_path[iu : iv + 1]
                    types = [selected_graph[sub[k]][sub[k+1]].get('type')
                             for k in range(len(sub) - 1)
                             if selected_graph.has_edge(sub[k], sub[k+1])]
                    bridges = [t for t in types if t in ('disulfide', 'covalent', 'ion', 'bridge', 'metalc', 'disulf')]
                    if bridges:
                        attrs['type'] = bridges[0]
                    elif 'side chain' in types:
                        attrs['type'] = 'side chain'
                    elif 'CA' in types:
                        attrs['type'] = 'CA'
                    elif types and types[0] is not None:
                        attrs['type'] = types[0]
                    if 'type' in attrs:
                        attrs['weight'] = 5 if attrs['type'] == 'CA' else 1
            simp_g.add_edge(u, v, **attrs)

    return simp_g
log = logging.getLogger(__name__)
HOMFLY_TIMEOUT = 1200
_HOMFLY_LOCK = threading.Lock()
def _homfly_call(conn, chain, tries):
    try:
        conn.send(tp.homfly(chain, closure=tp.Closure.CLOSED, run_parallel=False))
    except Exception:
        conn.send(None)
    conn.close()
def _isolated_homfly(chain, tries=None):
    # Loops are closed curves, so `tries` (random closure) is unused: closure=Closure.CLOSED.
    """Run tp.homfly in a fresh interpreter so a liblmpoly abort() only loses this chain.
    A subprocess (not fork) is used because forking this multithreaded process from several
    threads yields children with a corrupted heap ("malloc(): corrupted top size") or deadlocks."""
    import pickle
    import subprocess
    import sys
    worker = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'homfly_worker.py')
    try:
        proc = subprocess.run([sys.executable, worker], input=pickle.dumps((chain, tries)),
                              stdout=subprocess.PIPE, timeout=HOMFLY_TIMEOUT)
        return pickle.loads(proc.stdout) if proc.returncode == 0 and proc.stdout else None
    except Exception:
        return None
def _evaluate_subgraph_knot_worker(arcs_4d, node_coords_list, tries=500):
    loops = []
    try:
        tp_g = tp.Graph(arcs_4d)
        loops = list(tp_g.find_loops(output_type=OutputType.XYZ, arc_bridges=0))
    except Exception as e:
        log.warning(f"Failed to find loops via topoly: {e}")

    if not loops and node_coords_list:
        if len(node_coords_list) >= 3:
            try:
                res = _isolated_homfly(node_coords_list, tries)
                if res is None:
                    return '0_1', 1.0
                non_trivial = {k: v for k, v in res.items() if k not in ('0_1', 'TMC')}
                if non_trivial:
                    best_k = max(non_trivial, key=non_trivial.get)
                    return best_k, float(non_trivial[best_k])
                return '0_1', float(res.get('0_1', 1.0))
            except Exception:
                pass
        return '0_1', 1.0

    all_knots = []
    max_unknot_prob = 0.0
    for lp in loops:
        try:
            res = _isolated_homfly(lp, tries)
            if res is None:
                continue
            max_unknot_prob = max(max_unknot_prob, float(res.get('0_1', 0.0)))
            for k, prob in res.items():
                if k not in ('0_1', 'TMC') and prob > 0:
                    all_knots.append((k, float(prob)))
        except Exception as e:
            pass

    if all_knots:
        best_knot = max(all_knots, key=lambda x: x[1])
        return best_knot[0], best_knot[1]
    return '0_1', max_unknot_prob if max_unknot_prob > 0 else 1.0
def _parse_nxyz_loop(text):
    ids, coords = [], []
    for line in text.strip().splitlines():
        parts = line.split()
        if len(parts) == 4:
            ids.append(int(parts[0]))
            coords.append([float(parts[1]), float(parts[2]), float(parts[3])])
    return ids, coords
def classify_homfly(res, max_unknot=0.5, min_knot=0.48):
    """Return (knot_type, knot_prob, unknot_prob) if the HOMFLY result is knotted, else None."""
    if not res:
        return None
    unknot = float(res.get('0_1', 0.0))
    knots = {k: float(v) for k, v in res.items() if k not in ('0_1', 'TMC')}
    if not knots:
        return None
    best = max(knots, key=knots.get)
    if unknot < max_unknot and knots[best] >= min_knot:
        return best, knots[best], unknot
    return None
KNOT_CACHE_DIR = os.environ.get('KNOT_CACHE_DIR', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'knot_cache'))
def _knot_cache_path(graph, node_pos_3d, tries, kind='', params=None):
    """Cache file path: <pdbid>/<pdbid>_<chain>_<source>_<within>_<subgraph index>_<nodes>n_<hash>.json.
    The hash covers the graph's edges, node coordinates and the HOMFLY settings, so graphs that
    differ only in e.g. simplification still get distinct files."""
    import hashlib
    params = params or {}
    h = hashlib.sha256(f'v4-closed|{tries}|{kind}'.encode())
    for n in sorted(graph.nodes(), key=str):
        c = graph.nodes[n].get('coords')
        if c is None and node_pos_3d is not None:
            c = node_pos_3d.get(n)
        h.update(f'{n}:{None if c is None else [round(float(x), 4) for x in c]};'.encode())
    for e in sorted(tuple(sorted((str(u), str(v)))) for u, v in graph.edges()):
        h.update(f'{e};'.encode())
    within = params.get('within') or kind or 'whole'
    if params.get('simplified'):
        within += '-simplified'
    index = params.get('subgraph_index')
    parts = [params.get('pdbid') or 'unknown', params.get('chain') or 'A', params.get('source') or 'unknown', within,
             '-' if index is None else str(index), f'{graph.number_of_nodes()}n', h.hexdigest()[:12]]
    parts = [re.sub(r'[^A-Za-z0-9.,+-]', '-', str(x)) for x in parts]
    return os.path.join(KNOT_CACHE_DIR, parts[0], '_'.join(parts) + '.json')
def _log(msg):
    """Progress line on the console (long searches otherwise look hung)."""
    import time
    print(f'[{time.strftime("%H:%M:%S")}] {msg}', flush=True)
def _read_json(path):
    import json
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None
def _write_json(path, data):
    import json
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f'{path}.{os.getpid()}.{threading.get_ident()}.tmp'
        with open(tmp, 'w') as f:
            json.dump(data, f, indent=1)
        os.replace(tmp, path)
    except OSError:
        logging.warning('Could not write cache %s', path)
def loop_edges(nodes):
    """Edge set (frozensets) of the cycle through `nodes`, ignoring a repeated closing node."""
    nodes = list(nodes)
    if len(nodes) > 1 and nodes[0] == nodes[-1]:
        nodes = nodes[:-1]
    return {frozenset((nodes[i], nodes[(i + 1) % len(nodes)])) for i in range(len(nodes))}
def find_knotted_loops(graph, node_pos_3d=None, tries=500, workers=None, params=None):
    """Cached wrapper around _find_knotted_loops; results are stored as JSON files in KNOT_CACHE_DIR
    together with the `params` (PDB ID, source, reduction, numbering, ...) they were computed for, the
    nodes of the analyzed graph and every loop that was analyzed, also those without a knot."""
    import json
    path = _knot_cache_path(graph, node_pos_3d, tries, params=params)
    by_str = {str(n): n for n in graph.nodes()}
    try:
        with open(path) as f:
            data = json.load(f)
        loops = data['loops']
        for lp in loops:
            lp['nodes'] = [by_str[n] for n in lp['nodes']]
        return loops
    except (OSError, ValueError, KeyError, TypeError):
        pass
    analyzed = []
    loops = _find_knotted_loops(graph, node_pos_3d, tries, workers, analyzed=analyzed,
                                partial_path=path[:-len('.json')] + '.partial.json')
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f'{path}.{os.getpid()}.tmp'
        with open(tmp, 'w') as f:
            json.dump(dict(params=dict(params or {}, tries=tries, nodes=graph.number_of_nodes(),
                                       edges=graph.number_of_edges()),
                           nodes=[str(n) for n in graph.nodes()],
                           loops=[{**lp, 'nodes': [str(n) for n in lp['nodes']]} for lp in loops],
                           loops_analyzed=[{**a, 'nodes': [str(n) for n in a['nodes']]} for a in analyzed]),
                      f, indent=1)
        os.replace(tmp, path)
        try:
            os.remove(path[:-len('.json')] + '.partial.json')
        except OSError:
            pass
    except OSError:
        logging.warning('Could not write knot cache %s', path)
    return loops
def cached_subgraph_homfly(subgraph, node_pos_3d=None, tries=500, params=None):
    """File-cached test_obstruction_knot_homfly; failed/timed-out runs (knot_type None) are not cached."""
    import json
    path = _knot_cache_path(subgraph, node_pos_3d, tries, kind='subgraph', params=params)
    try:
        with open(path) as f:
            data = json.load(f)
        return data['knot_type'], data['prob']
    except (OSError, ValueError, KeyError):
        pass
    knot_type, prob = test_obstruction_knot_homfly(subgraph, node_pos_3d, tries=tries)
    if knot_type is not None:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = f'{path}.{os.getpid()}.tmp'
            with open(tmp, 'w') as f:
                json.dump(dict(params=dict(params or {}, tries=tries, nodes=subgraph.number_of_nodes(),
                                           edges=subgraph.number_of_edges()),
                               nodes=[str(n) for n in subgraph.nodes()],
                               knot_type=knot_type, prob=prob), f, indent=1)
            os.replace(tmp, path)
        except OSError:
            logging.warning('Could not write HOMFLY cache %s', path)
    return knot_type, prob
def _node_coords(graph, n, node_pos_3d):
    c = graph.nodes[n].get('coords')
    if c is None and node_pos_3d is not None:
        c = node_pos_3d.get(n)
    return [float(x) for x in c] if c is not None else (0.0, 0.0, 0.0)
def _find_knotted_loops(graph, node_pos_3d=None, tries=500, workers=None, analyzed=None, partial_path=None):
    """Enumerate loops of `graph` with Topoly and return those that HOMFLY classifies as knotted,
    as dicts with the loop's node sequence, knot type and probabilities (most probable first)."""
    from concurrent.futures import ThreadPoolExecutor
    nodes = list(graph.nodes())
    id_to_node = dict(enumerate(nodes))
    arcs = []
    for u, v in graph.edges():
        arc = []
        for n in (u, v):
            c = graph.nodes[n].get('coords')
            if c is None and node_pos_3d is not None:
                c = node_pos_3d.get(n)
            c = c if c is not None else (0.0, 0.0, 0.0)
            arc.append([nodes.index(n), float(c[0]), float(c[1]), float(c[2])])
        arcs.append(arc)
    if not arcs:
        return []
    import time
    t0 = time.time()
    partial = (_read_json(partial_path) or {}) if partial_path else {}
    _log(f'Enumerating loops of a graph with {len(nodes)} nodes and {len(arcs)} edges '
         f'(exponential in the number of independent cycles; counts are logged every 10s)...')
    # every simple cycle once; same set as Topoly's find_loops, which is far slower on larger graphs
    index = {n: i for i, n in enumerate(nodes)}
    unique, last = [], time.time()
    for cycle in nx.simple_cycles(nx.Graph(graph.edges())):
        if len(cycle) >= 3:
            ids = [index[n] for n in cycle]
            unique.append((ids, [list(_node_coords(graph, n, node_pos_3d)) for n in cycle]))
        if time.time() - last > 10:
            last = time.time()
            _log(f'  {len(unique)} loops enumerated so far ({last - t0:.0f}s)')
    _log(f'Found {len(unique)} loops in {time.time() - t0:.0f}s')

    def loop_key(names):
        return frozenset(frozenset((names[i], names[(i + 1) % len(names)])) for i in range(len(names)))

    # HOMFLY results of an earlier, interrupted run are reused
    entries = list(partial.get('analyzed', []))
    done = {loop_key(a['nodes']): a['homfly'] for a in entries}
    if done:
        _log(f'Resuming: {len(done)} loops already analyzed in {os.path.basename(partial_path)}')
    lock = threading.Lock()
    progress = dict(count=0, last_save=time.time(), last_log=0.0)
    total = len(unique)

    def evaluate(item):
        ids, coords = item
        names = [str(id_to_node[i]) for i in ids]
        key = loop_key(names)
        cached = key in done
        res = done[key] if cached else _isolated_homfly(coords, tries)
        loop_nodes = [id_to_node[i] for i in ids]
        verdict = classify_homfly(res)
        with lock:
            if analyzed is not None:
                analyzed.append(dict(nodes=loop_nodes, homfly=res, knotted=verdict is not None))
            if not cached:
                entries.append(dict(nodes=names, homfly=res))
            progress['count'] += 1
            now = time.time()
            if now - progress['last_log'] > 10 or progress['count'] == total:
                progress['last_log'] = now
                _log(f'HOMFLY: {progress["count"]}/{total} loops analyzed ({now - t0:.0f}s elapsed)')
            if partial_path and now - progress['last_save'] > 30:
                progress['last_save'] = now
                _write_json(partial_path, dict(analyzed=entries))
        if verdict is None:
            return None
        return dict(nodes=loop_nodes, knot=verdict[0], prob=verdict[1], unknot_prob=verdict[2])

    with ThreadPoolExecutor(max_workers=workers or min(8, os.cpu_count() or 1)) as pool:
        found = [r for r in pool.map(evaluate, unique) if r is not None]
    if partial_path:
        with lock:
            _write_json(partial_path, dict(analyzed=entries))
    _log(f'Loop analysis finished: {len(found)} knotted of {total} loops')
    return sorted(found, key=lambda r: -r['prob'])
def _homfly_child(conn, arcs_4d, node_coords_list, tries):
    conn.send(_evaluate_subgraph_knot_worker(arcs_4d, node_coords_list, tries))
    conn.close()
def test_obstruction_knot_homfly(subgraph, node_pos_3d=None, tries=500):
    """Test if the obstruction subgraph forms a knot using Topoly's HOMFLY algorithm with `tries` tries.
    Returns (knot_type, probability)."""
    if subgraph is None or subgraph.number_of_nodes() == 0 or subgraph.number_of_edges() == 0:
        return None, 0.0

    node_coords = {}
    for n in subgraph.nodes():
        coord = subgraph.nodes[n].get('coords')
        if coord is None and node_pos_3d and n in node_pos_3d:
            coord = node_pos_3d[n]
        if coord is not None:
            node_coords[n] = [float(coord[0]), float(coord[1]), float(coord[2])]

    branch_nodes = [n for n in subgraph.nodes() if subgraph.degree(n) != 2]
    if not branch_nodes and subgraph.number_of_nodes() > 0:
        branch_nodes = [next(iter(subgraph.nodes()))]

    visited = set()
    arcs = []
    for u in branch_nodes:
        for v in subgraph.neighbors(u):
            e = frozenset((u, v))
            if e in visited:
                continue
            visited.add(e)
            path = [u, v]
            curr, prev = v, u
            while subgraph.degree(curr) == 2 and curr not in branch_nodes:
                nbrs = [n for n in subgraph.neighbors(curr) if n != prev]
                if not nbrs:
                    break
                nxt = nbrs[0]
                visited.add(frozenset((curr, nxt)))
                path.append(nxt)
                prev, curr = curr, nxt
            arcs.append(path)

    for u, v in subgraph.edges():
        e = frozenset((u, v))
        if e not in visited:
            visited.add(e)
            path = [u, v]
            curr, prev = v, u
            while curr != u:
                nbrs = [n for n in subgraph.neighbors(curr) if n != prev]
                if not nbrs:
                    break
                nxt = nbrs[0]
                visited.add(frozenset((curr, nxt)))
                path.append(nxt)
                prev, curr = curr, nxt
            arcs.append(path)

    node_to_id = {n: i for i, n in enumerate(subgraph.nodes())}
    arcs_4d = []
    for p in arcs:
        arc_pts = []
        for n in p:
            coord = node_coords.get(n, [0.0, 0.0, 0.0])
            arc_pts.append([node_to_id[n], float(coord[0]), float(coord[1]), float(coord[2])])
        arcs_4d.append(arc_pts)

    node_coords_list = [node_coords[n] for n in subgraph.nodes() if n in node_coords]

    # Run in a child process: liblmpoly can abort() (buffer overflow) or hang on large
    # inputs, which must not take down the app.
    with _HOMFLY_LOCK:
        ctx = mp.get_context('fork')
        recv, send = ctx.Pipe(duplex=False)
        proc = ctx.Process(target=_homfly_child, args=(send, arcs_4d, node_coords_list, tries))
        try:
            proc.start()
            send.close()
            if recv.poll(HOMFLY_TIMEOUT):
                try:
                    return recv.recv()
                except EOFError:
                    log.warning(f"HOMFLY worker crashed (exit code {proc.exitcode})")
                    return None, 0.0
            log.warning(f"HOMFLY computation timed out after {HOMFLY_TIMEOUT}s")
            return None, 0.0
        except Exception as e:
            log.warning(f"HOMFLY worker failed: {e}")
            return None, 0.0
        finally:
            if proc.is_alive():
                proc.kill()
            proc.join()
            recv.close()
