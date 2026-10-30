"""Fill knot_cache with the K_3,3 / K_5 minor results (plain and knotted) of the 'Simplified' structures.

For every structure and chain that has simplified files in data/ this computes, as the app does,
the whole-graph knotted loops, the four obstruction families (k33, k5, k33knot, k5knot) and for
each obstruction the knotted loops within it (original and simplified) and its HOMFLY knot type.
Results already in the cache are reused, so the script can be interrupted and restarted.

Usage: python precompute_cache.py [PDBID[CHAIN] ...] [--methods k33 k5 ...] [--no-subgraphs]
"""
import argparse
import sys

from graph_algorithms import (
    cached_subgraph_homfly, find_knotted_loops, find_obstructions, simplify_subgraph_topoly, _log,
)
from graph_data import TopolyReduce, list_data_pdbids, load_graph_by_id, split_pdbid_chain
from graph_visualization import get_node_positions_3d

METHODS = ("k33", "k5", "k33knot", "k5knot")
SIMPLIFY_METHOD = "kmt"


def simplified_ids():
    """Ids (PDBID + chain unless A) that have a simplified file, as listed by the app."""
    import os
    ids = []
    for pid in list_data_pdbids():
        p, chain = split_pdbid_chain(pid)
        if os.path.exists(f"data/{p}-{chain}_simplified_bonds.csv"):
            ids.append(pid)
    return ids


def process(pdbid, methods, subgraphs=True):
    pid, chain = split_pdbid_chain(pdbid)
    G, _ = load_graph_by_id(pdbid, False)
    node_pos_3d = get_node_positions_3d(G)
    params = dict(pdbid=pid, chain=chain, source="simplified", reduce=str(TopolyReduce.INTERNAL),
                  numbering="auth", merge_residues=False)
    _log(f"{pdbid}: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    find_knotted_loops(G, node_pos_3d, params=params)
    for method in methods:
        kwargs = dict(node_pos_3d=node_pos_3d, params=dict(params)) if method in ("k33knot", "k5knot") else {}
        try:
            subs = find_obstructions(G, method, **kwargs)
        except Exception as e:
            _log(f"{pdbid} {method}: failed: {e}")
            continue
        _log(f"{pdbid} {method}: {len(subs)} subgraphs")
        if not subgraphs:
            continue
        for idx, sub in enumerate(subs):
            selected = G.edge_subgraph(sub.edges())
            for simplified in (False, True):
                try:
                    shown = simplify_subgraph_topoly(selected, node_pos_3d, method=SIMPLIFY_METHOD) if simplified \
                        else selected
                    p = dict(params, subgraph_index=idx, simplified=simplified,
                             simplify_method=SIMPLIFY_METHOD if simplified else None)
                    find_knotted_loops(shown, node_pos_3d, tries=500, params=dict(p, within=method))
                    cached_subgraph_homfly(shown, node_pos_3d, tries=500,
                                           params=dict(p, view="multi", obstruction_finder=method))
                except Exception as e:
                    _log(f"{pdbid} {method} #{idx} simplified={simplified}: failed: {e}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ids", nargs="*", help="structures, e.g. 4B56B (default: all with simplified files)")
    ap.add_argument("--methods", nargs="+", choices=METHODS, default=list(METHODS))
    ap.add_argument("--no-subgraphs", action="store_true",
                    help="only find the obstructions, skip the knot analysis within each of them")
    args = ap.parse_args()
    available = simplified_ids()
    ids = [i.upper() if len(i) <= 4 else i[:4].upper() + i[4:] for i in args.ids] or available
    unknown = [i for i in ids if i not in available]
    if unknown:
        sys.exit(f"No simplified files for: {', '.join(unknown)}. Available: {', '.join(available)}")
    for pdbid in ids:
        process(pdbid, args.methods, not args.no_subgraphs)
    _log("done")


if __name__ == "__main__":
    main()
