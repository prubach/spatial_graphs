"""Fill knot_cache with the K_3,3 / K_5 minor results (plain and knotted) of the 'Simplified' structures.

For every structure and chain that has simplified files in data/ this computes, as the app does,
the whole-graph knotted loops, the four obstruction families (k33, k5, k33knot, k5knot) and for
each obstruction the knotted loops within it (original and simplified) and its HOMFLY knot type.
Results already in the cache are reused, so the script can be interrupted and restarted.

Usage: python precompute_cache.py [PDBID[CHAIN] ...] [--methods k33 k5 ...] [--no-subgraphs] [-j JOBS]
"""
import argparse
import os
import sys
from concurrent.futures import ProcessPoolExecutor

from graph_algorithms import (
    cached_subgraph_homfly, find_knotted_loops, find_obstructions, simplify_subgraph_topoly, _log,
)
from graph_data import TopolyReduce, list_data_pdbids, load_graph_by_id, split_pdbid_chain
from graph_visualization import get_node_positions_3d

METHODS = ("k33", "k5", "k33knot", "k5knot")
SIMPLIFY_METHOD = "kmt"


def simplified_ids():
    """Ids (PDBID + chain unless A) that have a simplified file, as listed by the app."""
    ids = []
    for pid in list_data_pdbids():
        p, chain = split_pdbid_chain(pid)
        if os.path.exists(f"data/{p}-{chain}_simplified.json"):
            ids.append(pid)
    return ids


_STATE = {}


def _context(pdbid):
    """Per-process cached graph, node positions and cache params of a structure."""
    if pdbid not in _STATE:
        pid, chain = split_pdbid_chain(pdbid)
        G, _ = load_graph_by_id(pdbid, False)
        params = dict(pdbid=pid, chain=chain, source="simplified", reduce=str(TopolyReduce.INTERNAL),
                      numbering="auth", merge_residues=False)
        _STATE[pdbid] = (G, get_node_positions_3d(G), params)
    return _STATE[pdbid]


def find_task(pdbid, method):
    """Find the obstructions of one family; returns their edge lists."""
    G, node_pos_3d, params = _context(pdbid)
    _log(f"{pdbid}: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    find_knotted_loops(G, node_pos_3d, params=params)
    kwargs = dict(node_pos_3d=node_pos_3d, params=dict(params)) if method in ("k33knot", "k5knot") else {}
    try:
        subs = find_obstructions(G, method, **kwargs)
    except Exception as e:
        _log(f"{pdbid} {method}: failed: {e}")
        return []
    _log(f"{pdbid} {method}: {len(subs)} subgraphs")
    return [list(sub.edges()) for sub in subs]


def subgraph_task(pdbid, method, idx, edges, simplified):
    G, node_pos_3d, params = _context(pdbid)
    try:
        selected = G.edge_subgraph(edges)
        shown = simplify_subgraph_topoly(selected, node_pos_3d, method=SIMPLIFY_METHOD) if simplified \
            else selected
        p = dict(params, subgraph_index=idx, simplified=simplified,
                 simplify_method=SIMPLIFY_METHOD if simplified else None)
        find_knotted_loops(shown, node_pos_3d, tries=500, params=dict(p, within=method))
        cached_subgraph_homfly(shown, node_pos_3d, tries=500,
                               params=dict(p, view="multi", obstruction_finder=method))
    except Exception as e:
        _log(f"{pdbid} {method} #{idx} simplified={simplified}: failed: {e}")


def run(ids, methods, subgraphs, jobs):
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        finds = {(pdbid, m): ex.submit(find_task, pdbid, m) for pdbid in ids for m in methods}
        if not subgraphs:
            for f in finds.values():
                f.result()
            return
        pending = []
        for key, fut in finds.items():
            pdbid, method = key
            for idx, edges in enumerate(fut.result()):
                for simplified in (False, True):
                    pending.append(ex.submit(subgraph_task, pdbid, method, idx, edges, simplified))
        for f in pending:
            f.result()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ids", nargs="*", help="structures, e.g. 4B56B (default: all with simplified files)")
    ap.add_argument("--methods", nargs="+", choices=METHODS, default=list(METHODS))
    ap.add_argument("--no-subgraphs", action="store_true",
                    help="only find the obstructions, skip the knot analysis within each of them")
    ap.add_argument("-j", "--jobs", type=int, default=os.cpu_count() or 1,
                    help="number of parallel worker processes (default: all CPUs)")
    args = ap.parse_args()
    available = simplified_ids()
    ids = [i.upper() if len(i) <= 4 else i[:4].upper() + i[4:] for i in args.ids] or available
    unknown = [i for i in ids if i not in available]
    if unknown:
        sys.exit(f"No simplified files for: {', '.join(unknown)}. Available: {', '.join(available)}")
    run(ids, args.methods, not args.no_subgraphs, args.jobs)
    _log("done")


if __name__ == "__main__":
    main()
