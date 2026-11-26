"""Classification of spatial theta curves with the Yamada polynomial.

A theta curve is a graph with two vertices of degree 3 joined by three arcs (chains of
degree-2 nodes, possibly a single edge). Two backends are available:

* ``topoly``: ``topoly.yamada`` identifies the curve directly (``chiral=True`` gives the handedness).
* ``knotpy``: the diagram is built from the topoly planar diagram, its Yamada polynomial is
  computed with knotpy and looked up in the table of theta curves with up to 5 crossings.

Both return the same dict: ``method``, ``name`` (e.g. ``T3_1``, ``None`` if not in the tables),
``chirality`` (``'+'``, ``'-'`` or ``None`` when achiral/unknown) and ``polynomial`` (knotpy only).
Chirality ``+`` is the curve as listed in the knotpy table and ``-`` its mirror image.
"""
import logging
import hashlib
import json
import os
import re
import sys
import time
from itertools import combinations, islice

import networkx as nx

log = logging.getLogger(__name__)

METHODS = ('topoly', 'knotpy')
MAX_THETA_CURVES = 20
THETA_CACHE_VERSION = 1
KNOTTED_THETA_SEARCH_VERSION = 2
MAX_KNOTTED_THETAS = 100
MAX_THETA_CANDIDATES = 1000
MAX_THETA_CYCLES = 1000
THETA_SEARCH_SECONDS = 60

_KNOTPY_TABLE = None


class KnottedThetaResults(list):
    """Search results with explicit limits and classification uncertainties."""
    def __init__(self, values=(), warnings=(), examined=0):
        super().__init__(values)
        self.warnings = list(warnings)
        self.examined = examined


def find_knotted_thetas(graph, positions=None, params=None, *, result_limit=MAX_KNOTTED_THETAS,
                        candidate_limit=MAX_THETA_CANDIDATES, cycle_limit=MAX_THETA_CYCLES,
                        time_limit=THETA_SEARCH_SECONDS):
    """Search cycle-plus-path theta subdivisions, prioritizing cached knotted cycles.

    A nontrivial Yamada label or a knotted constituent cycle is evidence of knotting.
    Trivial or unlisted Yamada labels cannot prove a theta curve is unknotted.
    Limits are checked between operations; a single classification can exceed the deadline.
    """
    import graph_algorithms as ga
    if min(result_limit, candidate_limit, cycle_limit, time_limit) <= 0:
        raise ValueError("Theta search limits must be positive")
    deadline = time.monotonic() + time_limit
    ordered = nx.Graph()
    ordered.add_nodes_from((n, dict(graph.nodes[n])) for n in sorted(graph, key=str))
    ordered.add_edges_from(sorted((tuple(sorted((u, v), key=str)) for u, v in graph.edges()),
                                  key=lambda edge: tuple(map(str, edge))))
    by_str = {str(n): n for n in ordered}
    if len(by_str) != len(ordered):
        raise ValueError("Theta search requires distinct string representations of node IDs")
    cached = ga._read_json(ga._knot_cache_path(graph, positions, 500, params=params))
    seeds, cached_cycles = [], {}
    invalid_cache = 0
    if isinstance(cached, dict) and isinstance(cached.get('loops_analyzed'), list):
        for entry in cached['loops_analyzed']:
            try:
                nodes = [by_str[n] for n in entry['nodes']]
                if (len(nodes) < 3 or len(set(nodes)) != len(nodes)
                        or not all(ordered.has_edge(u, v) for u, v in zip(nodes, nodes[1:] + nodes[:1]))):
                    raise ValueError("invalid cycle")
                edges = frozenset(frozenset((u, v)) for u, v in zip(nodes, nodes[1:] + nodes[:1]))
                cached_cycles[edges] = entry['homfly']
            except (KeyError, TypeError, ValueError):
                invalid_cache += 1
                log.warning("Invalid cached cycle ignored during theta search")
        loops = cached.get('loops', [])
        if not isinstance(loops, list):
            invalid_cache += 1
            log.warning("Invalid cached knotted loop list ignored during theta search")
            loops = []
        for loop in loops:
            try:
                nodes = [by_str[n] for n in loop['nodes']]
                if (len(nodes) >= 3 and len(set(nodes)) == len(nodes)
                        and all(ordered.has_edge(u, v) for u, v in zip(nodes, nodes[1:] + nodes[:1]))
                        and ga.classify_homfly({loop['knot']: loop['prob'],
                                               '0_1': loop['unknot_prob']}) is not None):
                    seeds.append((nodes, loop['knot']))
                else:
                    raise ValueError("invalid knotted loop")
            except (KeyError, TypeError, ValueError):
                invalid_cache += 1
                log.warning("Invalid cached knotted loop ignored during theta search")

    seen_cycles, seen_thetas, found, cycle_labels = set(), set(), [], {}
    examined, cycles_examined, unknown, unproven, uncertain_cycles = 0, 0, 0, 0, 0
    reason = None

    def cycle_key(cycle):
        return frozenset(frozenset((u, v)) for u, v in zip(cycle, cycle[1:] + cycle[:1]))

    def cycle_label(cycle):
        nonlocal uncertain_cycles
        key = cycle_key(cycle)
        if key not in cycle_labels:
            result = cached_cycles.get(key)
            if result is None:
                coordinates = []
                for n in cycle:
                    coord = graph.nodes[n].get('coords')
                    if coord is None and positions is not None:
                        coord = positions.get(n)
                    if coord is None:
                        raise ValueError(f"No 3D coordinates for node {n!r}")
                    coordinates.append([float(c) for c in coord])
                result = ga._isolated_homfly(coordinates, 500)
            try:
                cycle_labels[key] = ga._checked_homfly_label(result, 'a theta constituent cycle')
            except (RuntimeError, ValueError, TypeError):
                uncertain_cycles += 1
                cycle_labels[key] = None
        return cycle_labels[key]

    def process_cycle(cycle, knot):
        nonlocal examined, unknown, unproven, uncertain_cycles, reason
        cycle_nodes = set(cycle)
        cycle_edges = cycle_key(cycle)
        branches = [n for n in cycle if ordered.degree(n) >= 3]
        cycle_knot = knot
        cycle_checked = knot is not None
        for u, v in combinations(branches, 2):
            if time.monotonic() >= deadline:
                reason = "time limit reached"
                return
            allowed = (set(ordered) - cycle_nodes) | {u, v}
            paths_graph = ordered.subgraph(allowed)
            for path in nx.all_simple_paths(paths_graph, u, v):
                if time.monotonic() >= deadline:
                    reason = "time limit reached"
                    return
                if len(path) == 2 and frozenset((u, v)) in cycle_edges:
                    continue
                edges = cycle_edges | frozenset(frozenset(e) for e in zip(path, path[1:]))
                if edges in seen_thetas:
                    continue
                seen_thetas.add(edges)
                theta = nx.Graph()
                theta.add_nodes_from((n, dict(ordered.nodes[n])) for n in cycle + path)
                theta.add_edges_from(zip(cycle, cycle[1:] + cycle[:1]))
                theta.add_edges_from(zip(path, path[1:]))
                if not is_theta_graph(theta):
                    raise ValueError("Theta search produced an invalid subdivision")
                examined += 1
                if not cycle_checked:
                    cycle_checked = True
                    label = cycle_label(cycle)
                    if label and label != '0_1':
                        cycle_knot = label
                knot = cycle_knot
                if time.monotonic() >= deadline:
                    if knot:
                        theta.graph['knotted_constituent'] = {'nodes': list(cycle), 'knot': knot}
                        theta.graph['theta_classification_error'] = 'Time limit reached before Yamada classification'
                        found.append(theta)
                    reason = "time limit reached"
                    return
                try:
                    classification = cached_theta_classification(theta, positions, method='topoly')
                    theta.graph['theta_classification'] = classification
                    name = classification.get('name')
                except Exception as e:
                    theta.graph['theta_classification_error'] = str(e)
                    name = None
                witness = cycle
                if not knot and (not name or name == 'T0_1') and time.monotonic() < deadline:
                    for constituent in nx.simple_cycles(theta):
                        if len(constituent) < 3 or cycle_key(constituent) == cycle_edges:
                            continue
                        label = cycle_label(constituent)
                        if label and label != '0_1':
                            knot, witness = label, constituent
                            break
                        if time.monotonic() >= deadline:
                            break
                if knot:
                    theta.graph['knotted_constituent'] = {'nodes': list(witness), 'knot': knot}
                if name and name != 'T0_1':
                    theta.graph['knotted_yamada'] = dict(classification)
                if name is None:
                    unknown += 1
                if knot or (name and name != 'T0_1'):
                    found.append(theta)
                    if len(found) >= result_limit:
                        reason = f"result limit ({result_limit}) reached"
                        return
                elif name == 'T0_1':
                    unproven += 1
                if time.monotonic() >= deadline:
                    reason = "time limit reached"
                    return
                if examined >= candidate_limit:
                    reason = f"candidate limit ({candidate_limit}) reached"
                    return

    for cycle, knot in seeds:
        key = cycle_key(cycle)
        if key in seen_cycles:
            continue
        seen_cycles.add(key)
        cycles_examined += 1
        process_cycle(cycle, knot)
        if reason:
            break
        if cycles_examined >= cycle_limit:
            reason = f"cycle limit ({cycle_limit}) reached"
            break
    if not reason:
        for cycle in nx.simple_cycles(ordered):
            if time.monotonic() >= deadline:
                reason = "time limit reached"
                break
            if len(cycle) < 3 or cycle_key(cycle) in seen_cycles:
                continue
            seen_cycles.add(cycle_key(cycle))
            cycles_examined += 1
            process_cycle(cycle, None)
            if reason:
                break
            if cycles_examined >= cycle_limit:
                reason = f"cycle limit ({cycle_limit}) reached"
                break
    if not reason and time.monotonic() >= deadline:
        reason = "time limit reached"
    warnings = []
    if reason:
        warnings.append(f"Theta search incomplete: {reason}; {examined} candidates examined")
    if unknown:
        warnings.append(f"{unknown} theta candidate(s) have an unlisted or inconclusive Yamada classification")
    if uncertain_cycles:
        warnings.append(f"{uncertain_cycles} constituent cycle(s) had inconclusive HOMFLY results")
    if unproven:
        warnings.append(f"{unproven} theta candidate(s) have a trivial Yamada label, which does not prove they are unknotted")
    if invalid_cache:
        warnings.append(f"{invalid_cache} invalid cached loop record(s) were ignored")
    return KnottedThetaResults(found, warnings, examined)


def is_theta_graph(graph):
    """True if `graph` is a subdivision of the theta graph (two degree-3 nodes, three arcs)."""
    if graph.number_of_nodes() < 2 or not nx.is_connected(graph):
        return False
    degrees = [d for _, d in graph.degree()]
    if degrees.count(3) != 2 or any(d not in (2, 3) for d in degrees):
        return False
    return len(_theta_arcs(graph)) == 3


def find_theta_subgraphs(graph, limit=MAX_THETA_CURVES):
    """Find up to `limit` theta subdivisions, each represented by its three disjoint paths."""
    if limit < 1:
        raise ValueError("limit must be positive")
    ordered = nx.Graph()
    ordered.add_nodes_from((n, dict(graph.nodes[n])) for n in sorted(graph.nodes(), key=str))
    ordered.add_edges_from(sorted(
        (tuple(sorted((u, v), key=str)) for u, v in graph.edges()),
        key=lambda edge: (str(edge[0]), str(edge[1]))))
    component = {n: i for i, nodes in enumerate(nx.connected_components(ordered)) for n in nodes}
    branch_nodes = sorted((n for n in ordered if ordered.degree(n) >= 3), key=str)
    found, seen = [], set()
    for u, v in combinations(branch_nodes, 2):
        if component[u] != component[v]:
            continue
        try:
            paths = list(islice(nx.node_disjoint_paths(ordered, u, v), 3))
        except nx.NetworkXNoPath:
            continue
        if len(paths) < 3:
            continue
        theta = nx.Graph()
        theta.add_nodes_from((n, dict(ordered.nodes[n])) for path in paths for n in path)
        for path in paths:
            theta.add_edges_from(zip(path, path[1:]))
        if not is_theta_graph(theta):
            continue
        key = frozenset(frozenset(edge) for edge in theta.edges())
        if key in seen:
            continue
        seen.add(key)
        found.append(theta)
        if len(found) == limit:
            break
    return found


def _theta_cache_path(kind, payload):
    import graph_algorithms as ga
    encoded = json.dumps([THETA_CACHE_VERSION, kind, payload], separators=(',', ':'), allow_nan=False)
    digest = hashlib.sha256(encoded.encode()).hexdigest()
    return os.path.join(ga.KNOT_CACHE_DIR, f'theta_{kind}_{digest}.json')


def cached_theta_subgraphs(graph, limit=MAX_THETA_CURVES):
    """Cache completed theta searches, restoring node attributes from the current graph."""
    if limit < 1:
        raise ValueError("limit must be positive")
    nodes = list(graph)
    labels = [(type(n).__module__, type(n).__qualname__, repr(n)) for n in nodes]
    if len(set(labels)) != len(labels):
        log.warning("Theta search cache skipped: node representations are not unique")
        return find_theta_subgraphs(graph, limit)
    index = {n: i for i, n in enumerate(nodes)}
    edges = [[index[u], index[v]] for u, v in graph.edges()]
    path = _theta_cache_path('search', [limit, labels, edges])
    import graph_algorithms as ga
    data = ga._read_json(path)
    if data is not None:
        try:
            results = []
            for entry in data['results']:
                node_ids = entry['nodes']
                edge_ids = entry['edges']
                if (not isinstance(node_ids, list) or not isinstance(edge_ids, list)
                        or any(type(i) is not int or not 0 <= i < len(nodes) for i in node_ids)
                        or len(set(node_ids)) != len(node_ids)
                        or any(not isinstance(edge, list) or len(edge) != 2
                               or any(type(i) is not int or i not in node_ids for i in edge)
                               for edge in edge_ids)):
                    raise ValueError("invalid theta node or edge indices")
                selected = [nodes[i] for i in node_ids]
                theta = nx.Graph()
                theta.add_nodes_from((n, dict(graph.nodes[n])) for n in selected)
                theta.add_edges_from((nodes[u], nodes[v]) for u, v in edge_ids)
                if not is_theta_graph(theta) or any(not graph.has_edge(u, v) for u, v in theta.edges()):
                    raise ValueError("invalid theta subdivision")
                results.append(theta)
            if len(results) > limit:
                raise ValueError("too many theta subdivisions")
            return results
        except (KeyError, TypeError, IndexError, ValueError):
            log.warning("Invalid theta search cache %s; recomputing", path)
    results = find_theta_subgraphs(graph, limit)
    ga._write_json(path, {'results': [
        {'nodes': [index[n] for n in theta],
         'edges': [[index[u], index[v]] for u, v in theta.edges()]}
        for theta in results]})
    return results


def _theta_arcs(graph):
    """Node paths of the three arcs, each from one branch node to the other."""
    branch = [n for n in graph if graph.degree(n) == 3]
    if len(branch) != 2:
        return []
    u, w = branch
    arcs, seen = [], set()
    for first in graph.neighbors(u):
        if (u, first) in seen:
            continue
        path, prev, cur = [u, first], u, first
        while cur != w:
            nxts = [n for n in graph.neighbors(cur) if n != prev]
            if cur == u or len(nxts) != 1:
                return []
            prev, cur = cur, nxts[0]
            path.append(cur)
        seen.add((u, path[1]))
        seen.add((w, path[-2]))
        arcs.append(path)
    return arcs


def _topoly_arcs(graph, node_pos_3d=None):
    coords = {}
    for n in graph.nodes():
        c = graph.nodes[n].get('coords')
        if c is None and node_pos_3d and n in node_pos_3d:
            c = node_pos_3d[n]
        if c is None:
            raise ValueError(f"No 3D coordinates for node {n!r}")
        coords[n] = [float(c[0]), float(c[1]), float(c[2])]
    ids = {n: i for i, n in enumerate(graph.nodes())}
    return [[[ids[n]] + coords[n] for n in path] for path in _theta_arcs(graph)]


def _normalize_name(name):
    m = re.match(r'^([+-]?)([tT]\d+[a-z]?_\d+)$', str(name).strip())
    if not m:
        return None, None
    return m.group(2).upper(), (m.group(1) or None)


def _classify_topoly(arcs):
    import topoly as tp
    res = tp.yamada(arcs, closure=tp.Closure.CLOSED, run_parallel=False, chiral=True, hide_trivial=False,
                    hide_rare=False)
    if isinstance(res, dict):
        res = max(res, key=res.get) if res else ''
    name, chirality = _normalize_name(res)
    return {'method': 'topoly', 'name': name, 'chirality': chirality, 'polynomial': None}


def _import_knotpy():
    try:
        import knotpy  # noqa: F401
    except ImportError as e:
        # knotpy's drawing module imports `classes` as a top-level package; expose its directory.
        spec = None
        try:
            import importlib.util
            spec = importlib.util.find_spec('knotpy')
        except Exception:
            pass
        pkg = os.path.dirname(spec.origin) if spec and spec.origin else None
        if pkg is None or not os.path.isdir(os.path.join(pkg, 'classes')):
            raise ImportError("knotpy is not available") from e
        sys.path.append(pkg)
        import knotpy  # noqa: F401


def _knotpy_table():
    """Yamada polynomials of the tabulated theta curves, computed once."""
    global _KNOTPY_TABLE
    if _KNOTPY_TABLE is None:
        _import_knotpy()
        from knotpy.invariants.yamada import yamada, yamada_mirror
        from knotpy.tables.theta import thetas
        table = {}
        for t in thetas():
            p = yamada(t)
            table.setdefault(_poly_key(p), (t.name, '+'))
            table.setdefault(_poly_key(yamada_mirror(p)), (t.name, '-'))
        _KNOTPY_TABLE = table
    return _KNOTPY_TABLE


def _poly_key(p):
    """Key of a Yamada polynomial up to the overall sign (a convention of the normalization)."""
    import sympy as sp
    p = sp.expand(p)
    if p.as_ordered_terms()[0].as_coeff_Mul()[0] < 0:
        p = -p
    return str(p)


def _classify_knotpy(arcs):
    import re as _re
    from topoly.graph import Graph
    _import_knotpy()
    from knotpy.notation.pd import from_pd_notation
    from knotpy.invariants.yamada import yamada

    table = _knotpy_table()
    g = Graph(arcs)
    g.generate_em_from_coords()
    g.generate_pd_from_em()
    # Topoly lists the vertex neighbours in the opposite rotation sense to knotpy.
    parts = []
    for part in g.pdcode.split(';'):
        nums = _re.findall(r'\d+', part)
        if part.startswith('V'):
            nums.reverse()
        parts.append(f"{part[0]}[{','.join(nums)}]")
    poly = yamada(from_pd_notation(';'.join(parts)))
    name, chirality = table.get(_poly_key(poly), (None, None))
    if name is not None and name.upper() == 'T0_1':
        chirality = None
    return {'method': 'knotpy', 'name': name, 'chirality': chirality, 'polynomial': str(poly)}


def classify_theta_curve(subgraph, node_pos_3d=None, method='topoly'):
    """Classify a spatial theta curve by its Yamada polynomial.

    `subgraph` is a networkx graph whose nodes have a 'coords' attribute or appear in `node_pos_3d`.
    Raises ValueError if it is not a theta graph or coordinates are missing.
    """
    if method not in METHODS:
        raise ValueError(f"Unknown method {method!r}; expected one of {METHODS}")
    if not is_theta_graph(subgraph):
        raise ValueError("Not a theta graph: need two degree-3 nodes joined by three arcs")
    arcs = _topoly_arcs(subgraph, node_pos_3d)
    return _classify_topoly(arcs) if method == 'topoly' else _classify_knotpy(arcs)


def cached_theta_classification(subgraph, node_pos_3d=None, method='topoly'):
    """Cache a successful classification separately for each method and geometry."""
    if method not in METHODS:
        raise ValueError(f"Unknown method {method!r}; expected one of {METHODS}")
    if not is_theta_graph(subgraph):
        raise ValueError("Not a theta graph: need two degree-3 nodes joined by three arcs")
    arcs = _topoly_arcs(subgraph, node_pos_3d)
    path = _theta_cache_path('classification', [method, arcs])
    import graph_algorithms as ga
    result = ga._read_json(path)
    if (isinstance(result, dict) and result.get('method') == method
            and all(key in result for key in ('name', 'chirality', 'polynomial'))):
        return result
    if result is not None:
        log.warning("Invalid theta classification cache %s; recomputing", path)
    result = _classify_topoly(arcs) if method == 'topoly' else _classify_knotpy(arcs)
    ga._write_json(path, result)
    return result
