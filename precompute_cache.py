"""Precompute graph analyses and JSON/PDF reports for structures and chains.

For simplified and Topoly/Internal inputs available in data/ this computes, as the app does,
the whole-graph knotted loops, the four obstruction families (k33, k5, k33knot, k5knot) and for
each obstruction the knotted loops within it (original and simplified) and its HOMFLY knot type.
Results already in the cache are reused, so the script can be interrupted and restarted.

Usage: python precompute_cache.py [PDBID[CHAIN] ...] [--source simplified|topoly|both] [--methods k33 k5 k5contracted theta ...] [--no-subgraphs] [-j JOBS]
"""
import argparse
import os
import re
import sys
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait

from graph_algorithms import (
    _checked_homfly_label, _knot_cache_path, _read_json, cached_subgraph_homfly, expand_k5_embedding, find_k5_minors,
    find_knotted_k5_minors, find_knotted_loops, find_obstructions, simplify_subgraph_topoly, _log,
)
from graph_data import TopolyReduce, list_data_pdbids, load_graph_by_id, split_pdbid_chain
from graph_visualization import get_node_positions_3d
from k5_precompute import precompute_knotted_k5
from theta_classification import MAX_THETA_CURVES, cached_theta_classification, cached_theta_subgraphs
import structure_reports as reports

METHODS = ("k33", "k5", "k33knot", "k5knot", "k5contracted", "k5knotcontracted", "theta")
SIMPLIFY_METHOD = "kmt"
REPORT_CHECKPOINT_SIZE = 20


def simplified_ids():
    """Ids (PDBID + chain unless A) that have a simplified file, as listed by the app."""
    ids = []
    for pid in list_data_pdbids():
        p, chain = split_pdbid_chain(pid)
        if os.path.exists(f"data/{p}-{chain}_simplified.json"):
            ids.append(pid)
    return ids


def topoly_ids():
    """Selectable structure/chain IDs; missing coordinate files are fetched on load."""
    return list_data_pdbids()


_STATE = {}


def _validated_loops(graph, positions, params):
    loops = find_knotted_loops(graph, positions, tries=500, params=params)
    cache = _read_json(_knot_cache_path(graph, positions, 500, params=params))
    if not isinstance(cache, dict) or not isinstance(cache.get('loops_analyzed'), list):
        raise RuntimeError('Completed loop analysis is unavailable in the cache')
    for entry in cache['loops_analyzed']:
        _checked_homfly_label(entry.get('homfly'), 'a precomputed cycle')
    return loops


def _context(pdbid, source="simplified"):
    """Per-process cached graph, node positions and cache params of a structure."""
    if source not in ("simplified", "topoly"):
        raise ValueError(f"Unsupported source: {source}")
    key = (pdbid, source)
    if key not in _STATE:
        pid, chain = split_pdbid_chain(pdbid)
        G, _ = load_graph_by_id(pdbid, source == "topoly", reduce=TopolyReduce.INTERNAL,
                                numbering="auth", merge_residues=False)
        params = dict(pdbid=pid, chain=chain, source=source, reduce=str(TopolyReduce.INTERNAL),
                      numbering="auth", merge_residues=False)
        _STATE[key] = (G, get_node_positions_3d(G), params)
    return _STATE[key]


def find_task(pdbid, method, source="simplified"):
    """Find the obstructions of one family."""
    G, node_pos_3d, params = _context(pdbid, source)
    _log(f"{pdbid} {source}: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    if method in ("k33knot", "k5knot"):
        _validated_loops(G, node_pos_3d, params)
    kwargs = dict(node_pos_3d=node_pos_3d, params=dict(params)) if method in ("k33knot", "k5knot", "k5knotcontracted") else {}
    if method == "k5contracted":
        kwargs = dict(node_pos_3d=node_pos_3d)
    if method == "theta":
        subs = cached_theta_subgraphs(G, limit=MAX_THETA_CURVES + 1)[:MAX_THETA_CURVES]
        for sub in subs:
            try:
                sub.graph['theta_classification'] = cached_theta_classification(sub, node_pos_3d, method='topoly')
            except Exception as e:
                sub.graph['theta_classification_error'] = str(e)
                _log(f"{pdbid} theta classification failed: {e}")
    elif method == "k5knotcontracted":
        subs = precompute_knotted_k5(G, node_pos_3d, params)
    elif method == "k5":
        subs = find_k5_minors(G, raise_on_timeout=True)
    elif method == "k5knot":
        subs = find_knotted_k5_minors(G, node_pos_3d, params, raise_on_timeout=True)
    else:
        subs = find_obstructions(G, method, **kwargs)
    _log(f"{pdbid} {method}: {len(subs)} subgraphs")
    return subs


def subgraph_task(pdbid, method, idx, sub, simplified, source="simplified"):
    G, node_pos_3d, params = _context(pdbid, source)
    selected = expand_k5_embedding(sub) if sub.graph.get('kind') == 'contracted K_5 minor' else G.edge_subgraph(sub.edges())
    shown = simplify_subgraph_topoly(selected, node_pos_3d, method=SIMPLIFY_METHOD) if simplified \
        else selected
    p = dict(params, subgraph_index=idx, simplified=simplified,
             simplify_method=SIMPLIFY_METHOD if simplified else None)
    loops = _validated_loops(shown, node_pos_3d, dict(p, within=method))
    knot, probability = cached_subgraph_homfly(shown, node_pos_3d, tries=500,
                                              params=dict(p, view="multi", obstruction_finder=method))
    if knot is None:
        raise RuntimeError('Subgraph HOMFLY failed or was inconclusive')
    return {'status': 'complete', 'graph': reports.graph_data(shown),
            'knotted_loops': [reports.loop_data(loop, shown) for loop in loops],
            'homfly': {'knot': knot, 'probability': probability},
            'contraction_disagreements': shown.graph.get('contraction_disagreements'),
            'contraction_disagreement_pairs': shown.graph.get('contraction_disagreement_pairs')}


def whole_graph_task(pdbid, source="simplified"):
    G, positions, params = _context(pdbid, source)
    return [reports.loop_data(loop) for loop in _validated_loops(G, positions, params)]


def run(ids, methods, subgraphs, jobs, source="simplified"):
    failures = []
    available = []
    for pdbid in ids:
        try:
            _context(pdbid, source)
        except Exception as e:
            failures.append(f'{pdbid} {source} loading: {e}')
            _log(f'{pdbid} {source}: loading failed: {e}')
        else:
            available.append(pdbid)
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        pending = {ex.submit(whole_graph_task, pdbid, source): ('whole', pdbid, None) for pdbid in available}
        pending.update({ex.submit(find_task, pdbid, method, source): ('find', pdbid, method)
                        for pdbid in available for method in methods})
        sections = {}

        def publish(pdbid, method, section):
            graph, positions, params = _context(pdbid, source)
            reports.publish_section(graph, positions, params, method, section)
            _log(f'{pdbid} {source}: report updated ({method})')

        while pending:
            finished, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in finished:
                kind, pdbid, info = pending.pop(future)
                if kind == 'whole':
                    try:
                        section = {'status': 'complete', 'results': future.result()}
                    except Exception as e:
                        failures.append(f'{pdbid} {source} knotted loops: {e}')
                        graph, positions, params = _context(pdbid, source)
                        reports.publish_failure(graph, positions, params, 'knotted_loops', e)
                    else:
                        publish(pdbid, 'knotted_loops', section)
                elif kind == 'find':
                    method = info
                    try:
                        found = future.result()
                    except Exception as e:
                        failures.append(f'{pdbid} {source} {method}: {e}')
                        graph, positions, params = _context(pdbid, source)
                        reports.publish_failure(graph, positions, params, method, e)
                        continue
                    for warning in getattr(found, 'warnings', ()):
                        failures.append(f'{pdbid} {source} {method}: {warning}')
                    for idx, sub in enumerate(found):
                        if 'theta_classification_error' in sub.graph:
                            failures.append(f"{pdbid} {source} theta #{idx + 1}: {sub.graph['theta_classification_error']}")
                    graph, positions, params = _context(pdbid, source)
                    reports.publish_found(graph, positions, params, method, found)
                    _log(f'{pdbid} {source}: report updated ({method})')
                    sections[pdbid, method] = {'found': found, 'updates': [],
                                                'remaining': 2 * len(found) if subgraphs else 0}
                    if subgraphs:
                        for idx, sub in enumerate(found):
                            for simplified in (False, True):
                                task = ex.submit(subgraph_task, pdbid, method, idx, sub, simplified, source)
                                pending[task] = ('subgraph', pdbid, (method, idx, simplified))
                else:
                    method, idx, simplified = info
                    try:
                        detail = future.result()
                    except Exception as e:
                        failures.append(f'{pdbid} {source} {method} #{idx + 1} simplified={simplified}: {e}')
                        detail = {'status': 'failed', 'error': str(e)}
                    state = sections[pdbid, method]
                    state['updates'].append((state['found'][idx], 'simplified' if simplified else 'original',
                                             detail, None))
                    state['remaining'] -= 1
                    if len(state['updates']) >= REPORT_CHECKPOINT_SIZE or not state['remaining']:
                        graph, positions, params = _context(pdbid, source)
                        reports.update_found_batch(graph, positions, params, method, state['updates'])
                        state['updates'].clear()
    if failures:
        raise RuntimeError('Precomputation failed:\n' + '\n'.join(failures))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ids", nargs="*", help="structures, e.g. 4B56B (default: all available chains)")
    ap.add_argument("--source", choices=("simplified", "topoly", "both"), default="both",
                    help="input source to precompute (default: both; Topoly uses Internal reduction)")
    ap.add_argument("--methods", nargs="+", choices=METHODS, default=list(METHODS))
    ap.add_argument("--no-subgraphs", action="store_true",
                    help="only find the obstructions, skip the knot analysis within each of them")
    ap.add_argument("--refresh-reports", action="store_true",
                    help="regenerate summary PDFs for existing reports without recomputing analyses")
    ap.add_argument("-j", "--jobs", type=int, default=os.cpu_count() or 1,
                    help="number of parallel worker processes (default: all CPUs)")
    args = ap.parse_args()
    if args.jobs < 1:
        ap.error("--jobs must be positive")
    sources = ("simplified", "topoly") if args.source == "both" else (args.source,)
    available = {source: (simplified_ids() if source == "simplified" else topoly_ids()) for source in sources}
    ids = [i.upper() if len(i) <= 4 else i[:4].upper() + i[4:] for i in args.ids]
    unknown = [i for i in ids if not any(
        i in available[source] or (source == 'topoly' and re.fullmatch(r'[0-9][A-Z0-9]{3}[A-Za-z0-9]*', i))
        for source in sources)]
    if unknown:
        sys.exit(f"No {args.source} input for: {', '.join(unknown)}")
    failures = []
    for source in sources:
        selected = ([pid for pid in ids if source == 'topoly' or pid in available[source]]
                    if ids else available[source])
        for pid in ids:
            if pid not in selected:
                _log(f"{pid} {source}: no input available; skipping")
        if args.refresh_reports:
            for pdbid in selected:
                try:
                    graph, positions, params = _context(pdbid, source)
                    if reports.refresh_pdf(graph, positions, params):
                        _log(f"{pdbid} {source}: summary PDF refreshed")
                    else:
                        _log(f"{pdbid} {source}: no existing report to refresh")
                except Exception as e:
                    failures.append(f"{pdbid} {source} report refresh: {e}")
        elif selected:
            try:
                run(selected, args.methods, not args.no_subgraphs, args.jobs, source)
            except Exception as e:
                failures.append(f"{source}: {e}")
    if failures:
        sys.exit('\n'.join(failures))
    _log("done")


if __name__ == "__main__":
    main()
