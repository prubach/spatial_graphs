"""Resumable, graph-specific precomputation of contracted knotted K5 minors."""

import hashlib
import fcntl
import itertools
import json
import os
import sqlite3
import time
from contextlib import closing
from math import comb
from urllib.parse import quote

import networkx as nx

import graph_algorithms as ga


VERSION = 2
CHECKPOINT_INTERVAL = 256


def _context(graph, positions):
    nodes = sorted(graph, key=str)
    if len({str(n) for n in nodes}) != len(nodes):
        raise ValueError("K_5 precomputation requires distinct string representations of node IDs")
    index = {n: i for i, n in enumerate(nodes)}
    if positions is None and any(graph.nodes[n].get('coords') is None for n in graph):
        positions = nx.spring_layout(graph, dim=3, seed=1)
    coords = []
    for node in nodes:
        c = positions.get(node) if positions is not None else graph.nodes[node].get('coords')
        if c is None or len(c) != 3:
            raise ValueError(f"Missing 3D coordinates for K_5 vertex {node}")
        coords.append([float(x) for x in c])
    edges = sorted(tuple(sorted((index[u], index[v]))) for u, v in graph.edges())
    payload = json.dumps([VERSION, [[type(n).__module__, type(n).__qualname__, str(n)] for n in nodes], coords, edges],
                         separators=(',', ':'), allow_nan=False)
    digest = hashlib.sha256(payload.encode()).hexdigest()
    path = os.path.join(ga.KNOT_CACHE_DIR, f'contracted_k5_precompute_{digest}.sqlite')
    ordered = nx.Graph()
    ordered.add_nodes_from((n, dict(graph.nodes[n])) for n in nodes)
    ordered.add_edges_from((nodes[u], nodes[v]) for u, v in edges)
    return nodes, index, ordered, path


def _encode_witness(witness, index):
    adj, trees = witness
    roots = list(adj)
    return {
        'roots': [index[n] for n in roots],
        'trees': [[[index[u], index[v]] for u, v in trees[n]] for n in roots],
        'edges': [[index[u], index[v], [[index[a], index[b]] for a, b in adj[u][v]]]
                  for i, u in enumerate(roots) for v in roots[i + 1:]],
    }


def _decode_witness(data, nodes):
    roots = [nodes[i] for i in data['roots']]
    adj = {n: {} for n in roots}
    trees = {n: [(nodes[u], nodes[v]) for u, v in edges]
             for n, edges in zip(roots, data['trees'])}
    for u, v, edges in data['edges']:
        u, v = nodes[u], nodes[v]
        adj[u][v] = adj[v][u] = [(nodes[a], nodes[b]) for a, b in edges]
    return adj, trees


def _restore_result(data, graph, nodes, positions):
    model = ga._contracted_k5(graph, _decode_witness(data['witness'], nodes), positions)
    expanded = ga.expand_k5_embedding(model)
    expanded_nodes = list(expanded)
    model.graph['sources'] = ['knotted contracted embedding']
    model.graph['knotted_loops'] = [
        {**loop, 'nodes': [expanded_nodes[i] for i in loop['nodes']]}
        for loop in data['loops']
    ]
    return model


def load_precomputed(graph, positions=None, candidate_limit=1000):
    """Return completed cached results, or None when no matching complete cache exists."""
    nodes, _, _, path = _context(graph, positions)
    if not os.path.isfile(path):
        return None
    with closing(sqlite3.connect(f'file:{quote(path, safe="/")}?mode=ro', uri=True)) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='metadata'").fetchone():
            return None
        meta = dict(db.execute('SELECT key, value FROM metadata'))
        if meta.get('complete') != '1' or int(meta.get('candidate_limit', -1)) != candidate_limit:
            return None
        rows = db.execute('SELECT data FROM results ORDER BY sequence').fetchall()
    return [_restore_result(json.loads(row[0]), graph, nodes, positions) for row in rows]


def precompute_knotted_k5(graph, positions=None, params=None, candidate_limit=1000):
    """Analyze up to candidate_limit models, checkpointing enumeration and completed knots."""
    if candidate_limit <= 0:
        raise ValueError("candidate_limit must be positive")
    nodes, index, ordered, path = _context(graph, positions)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lock = open(path + '.lock', 'a')
    try:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as e:
            raise RuntimeError("K_5 precomputation is already running for this graph") from e
        db = sqlite3.connect(path, timeout=30)
        try:
            return _run_precomputation(db, graph, positions, params, candidate_limit, nodes, index, ordered)
        finally:
            db.close()
    finally:
        lock.close()


def _run_precomputation(db, graph, positions, params, candidate_limit, nodes, index, ordered):
    try:
        db.executescript('''
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS seen (edges TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS models (sequence INTEGER PRIMARY KEY, witness TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS results (sequence INTEGER PRIMARY KEY, data TEXT NOT NULL);
        ''')
        db.execute('BEGIN IMMEDIATE')
        metadata = dict(db.execute('SELECT key, value FROM metadata'))
        if metadata and int(metadata['candidate_limit']) != candidate_limit:
            raise ValueError("Existing K_5 precomputation has a different candidate limit")
        for key, value in (('candidate_limit', candidate_limit), ('block', 0), ('offset', 0),
                           ('count', 0), ('complete', 0)):
            db.execute('INSERT OR IGNORE INTO metadata VALUES (?, ?)', (key, str(value)))
        db.commit()
        metadata = dict(db.execute('SELECT key, value FROM metadata'))
        if metadata['complete'] == '1':
            return load_precomputed(graph, positions, candidate_limit)
        resume_block, resume_offset = int(metadata['block']), int(metadata['offset'])
        count = int(metadata['count'])

        def checkpoint(block, offset):
            db.executemany('UPDATE metadata SET value=? WHERE key=?',
                           [(str(block), 'block'), (str(offset), 'offset'), (str(count), 'count')])
            db.commit()

        blocks = sorted(nx.biconnected_components(ordered),
                        key=lambda b: tuple(sorted(index[n] for n in b)))
        for block_index, block in enumerate(blocks):
            if block_index < resume_block:
                continue
            if len(block) < 5:
                checkpoint(block_index + 1, 0)
                continue
            sub = ordered.subgraph(block)
            branch = {n for n in sub if sub.degree(n) >= 3}
            chains, visited = [], set()
            for b in sorted(branch, key=index.get):
                for neighbor in sorted(sub.neighbors(b), key=index.get):
                    if frozenset((b, neighbor)) in visited:
                        continue
                    path_nodes, previous, current = [b, neighbor], b, neighbor
                    while current not in branch:
                        following = next(n for n in sub.neighbors(current) if n != previous)
                        path_nodes.append(following)
                        previous, current = current, following
                    visited.update(frozenset(e) for e in zip(path_nodes, path_nodes[1:]))
                    chains.append((path_nodes[0], path_nodes[-1], path_nodes))
            remove_count = len(chains) - len(branch) + 1 - 6
            if remove_count < 0 or remove_count > len(chains):
                checkpoint(block_index + 1, 0)
                continue
            total = comb(len(chains), remove_count)
            offset = resume_offset if block_index == resume_block else 0
            ga._log(f'K_5 precompute: block {block_index + 1}/{len(blocks)}, '
                    f'{offset}/{total} combinations, {count} models')
            last_log = time.monotonic()
            combinations = itertools.islice(itertools.combinations(range(len(chains)), remove_count), offset, None)
            for position, removed in enumerate(combinations, start=offset):
                gone = set(removed)
                core = nx.MultiGraph()
                for i, (u, v, _) in enumerate(chains):
                    if i not in gone:
                        core.add_edge(u, v, key=i)
                leaves = [n for n in core if core.degree(n) <= 1]
                while leaves:
                    core.remove_nodes_from(leaves)
                    leaves = [n for n in core if core.degree(n) <= 1]
                if core.number_of_nodes() >= 5 and nx.is_connected(core):
                    model = nx.Graph()
                    for _, _, key in core.edges(keys=True):
                        model.add_edges_from(zip(chains[key][2], chains[key][2][1:]))
                    key = json.dumps(sorted(tuple(sorted((index[u], index[v]))) for u, v in model.edges()),
                                     separators=(',', ':'))
                    inserted = db.execute('INSERT OR IGNORE INTO seen VALUES (?)', (key,)).rowcount
                    if inserted:
                        witness = ga._find_k5_minor(model, float('inf'), set(), witness=True)
                        if witness:
                            encoded_witness = _encode_witness(witness, index)
                            db.execute('INSERT INTO models VALUES (?, ?)', (count, json.dumps(encoded_witness)))
                            contracted = ga._contracted_k5(graph, witness, positions)
                            ga.validate_k5_embedding(contracted)
                            expanded = ga.expand_k5_embedding(contracted)
                            loops = ga.find_knotted_loops(expanded, positions,
                                                          params=dict(params or {}, within='k5knotcontracted'))
                            if loops:
                                expanded_index = {n: i for i, n in enumerate(expanded)}
                                data = {'witness': encoded_witness,
                                        'loops': [{**lp, 'nodes': [expanded_index[n] for n in lp['nodes']]}
                                                  for lp in loops]}
                                db.execute('INSERT INTO results VALUES (?, ?)', (count, json.dumps(data)))
                            count += 1
                            checkpoint(block_index, position + 1)
                            ga._log(f'K_5 precompute: {position + 1}/{total} combinations, {count} models')
                            if count >= candidate_limit:
                                db.execute("UPDATE metadata SET value='1' WHERE key='complete'")
                                db.commit()
                                return load_precomputed(graph, positions, candidate_limit)
                if (position + 1) % CHECKPOINT_INTERVAL == 0:
                    checkpoint(block_index, position + 1)
                    if time.monotonic() - last_log >= 10:
                        ga._log(f'K_5 precompute: {position + 1}/{total} combinations, {count} models')
                        last_log = time.monotonic()
            checkpoint(block_index + 1, 0)
        db.execute("UPDATE metadata SET value='1' WHERE key='complete'")
        db.commit()
        return load_precomputed(graph, positions, candidate_limit)
    except BaseException:
        db.rollback()
        raise
