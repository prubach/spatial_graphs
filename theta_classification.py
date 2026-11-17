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
import os
import re
import sys
from itertools import combinations, islice

import networkx as nx

log = logging.getLogger(__name__)

METHODS = ('topoly', 'knotpy')
MAX_THETA_CURVES = 20

_KNOTPY_TABLE = None


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
