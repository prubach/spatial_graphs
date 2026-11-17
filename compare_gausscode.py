"""Compare the cycles found by the external Gauss-code tool (GaussCode/*_simple_cycles_with_gauss_report.txt)
with the cycles analysed by this app (whole-graph results cached in knot_cache/).

Cycles are compared as sets of undirected edges. For cycles present in both, the external tool's
"has a non-empty Gauss code" (crossings in the projection) is cross-tabulated with the app's
HOMFLY-based "knotted" flag. A non-empty Gauss code does not imply a knot (it may be an unknot with
kinks), so only "knotted but empty Gauss code" is a genuine inconsistency.

Usage: python compare_gausscode.py [-o REPORT.md] [--include-subgraphs]
"""
import argparse
import glob
import json
import multiprocessing
import os
import re
from collections import Counter
from queue import Empty

NODE = re.compile(r"^[A-Za-z0-9]*?(-?\d+[A-Za-z]?):(\w+)$")
SUBGRAPH_SEARCH_TIMEOUT = 120
TIME_BOUNDED_METHODS = {"k33knot", "k5knot", "k5knotcontracted"}


def node_name(token):
    """'CYS134:SG' / 'ZN202:ZN' -> '134_SG' (the app's naming)."""
    m = NODE.match(token.strip())
    if not m:
        raise ValueError(f"cannot parse node {token!r}")
    return f"{m.group(1)}_{m.group(2)}"


def cycle_key(nodes):
    nodes = list(nodes)
    if nodes[0] == nodes[-1]:
        nodes = nodes[:-1]
    n = len(nodes)
    return frozenset(frozenset((nodes[i], nodes[(i + 1) % n])) for i in range(n))


def parse_report(path):
    """Returns {cycle_key: has_gauss}, the number of cycles in the file (incl. duplicates) and a list of
    (node path, gauss text, wirtinger text) records."""
    cycles, count, cur, records, nodes, gauss = {}, 0, None, [], None, None
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("Path:"):
                nodes = [node_name(t) for t in line[5:].split("->")][:-1]
                cur = cycle_key(nodes)
                count += 1
            elif line.startswith("Gauss Code:") and cur is not None:
                gauss = line[len("Gauss Code:"):].strip()
                has = gauss not in ("[]", "")
                cycles[cur] = cycles.get(cur, False) or has
                cur = None
            elif line.startswith("Wirtinger Presentation:") and nodes is not None:
                records.append((nodes, gauss, line[len("Wirtinger Presentation:"):].strip()))
    return cycles, count, records


def compare_presentations(pdb, chain, records, extended=False):
    """Recompute Gauss code / Wirtinger presentation with the external tool's conventions
    (see wirtinger.external_wirtinger) from the same node order and compare with the report."""
    from wirtinger import external_wirtinger, format_relation
    with open(f"data/{pdb}-{chain}_simplified.json") as f:
        atoms = json.load(f)["atoms"]
    pos = {f"{a.get('auth_residue_id', a['residue_number'])}_{a['atom']}": (a["x"], a["y"], a["z"]) for a in atoms}
    same_g = same_w = 0
    bad = []
    for nodes, gauss, wirt in records:
        try:
            r = external_wirtinger([pos[n] for n in nodes], extended=extended)
        except (KeyError, ValueError):
            bad.append(nodes)
            continue
        mine_w = ",  ".join(format_relation(x) for x in r["relations"])
        g_ok, w_ok = str(r["gauss"]) == gauss, mine_w == wirt
        same_g += g_ok
        same_w += w_ok
        if not (g_ok and w_ok):
            bad.append(nodes)
    examples = []
    for nodes, gauss, wirt in records:
        if gauss != "[]" and len(examples) < 2:
            r = external_wirtinger([pos[n] for n in nodes], extended=extended)
            examples.append((len(nodes), gauss, wirt, str(r["gauss"]),
                             ",  ".join(format_relation(x) for x in r["relations"])))
    return len(records), same_g, same_w, bad, examples


def load_cache(pdb, chain):
    """Whole-graph cache file with most analysed loops for a structure."""
    best = None
    for f in glob.glob(f"knot_cache/{pdb}/{pdb}_{chain}_simplified_whole_-_*n_*.json"):
        d = json.load(open(f))
        if "loops_analyzed" not in d:
            continue
        if best is None or len(d["loops_analyzed"]) > len(best[1]["loops_analyzed"]):
            best = (f, d)
    return best


def identify_subgraphs(pdb, chain, method):
    """Run a current obstruction finder and return each result's edge set."""
    from graph_algorithms import expand_k5_embedding, find_obstructions
    from graph_data import TopolyReduce, load_graph_by_id
    from graph_visualization import get_node_positions_3d

    graph, _ = load_graph_by_id(pdb + chain, False)
    positions = get_node_positions_3d(graph)
    params = dict(pdbid=pdb, chain=chain, source="simplified",
                  reduce=str(TopolyReduce.INTERNAL), numbering="auth", merge_residues=False)
    if method in TIME_BOUNDED_METHODS:
        kwargs = dict(node_pos_3d=positions, params=params)
        if method == "k5knot":
            kwargs.update(time_limit=SUBGRAPH_SEARCH_TIMEOUT - 1, raise_on_timeout=True)
        elif method == "k5knotcontracted":
            kwargs["time_limit"] = SUBGRAPH_SEARCH_TIMEOUT - 1
    elif method == "k5contracted":
        kwargs = dict(node_pos_3d=positions)
    else:
        kwargs = {}
    subgraphs = find_obstructions(graph, method, **kwargs)
    return [frozenset(frozenset(edge) for edge in
                      (expand_k5_embedding(sub) if sub.graph.get("kind") == "contracted K_5 minor"
                       else sub).edges())
            for sub in subgraphs]


def _subgraph_worker(pdb, chain, method, result_queue):
    try:
        result_queue.put((True, identify_subgraphs(pdb, chain, method)))
    except TimeoutError as error:
        result_queue.put(("timeout", str(error)))
    except Exception as error:
        result_queue.put((False, type(error).__name__, str(error)))


def run_subgraph_finder(pdb, chain, method):
    """Bound knotted searches and distinguish timeout from an empty result."""
    if method not in TIME_BOUNDED_METHODS:
        return identify_subgraphs(pdb, chain, method)

    context = multiprocessing.get_context("fork")
    result_queue = context.Queue()
    process = context.Process(target=_subgraph_worker, args=(pdb, chain, method, result_queue))
    process.start()
    process.join(SUBGRAPH_SEARCH_TIMEOUT)
    if process.is_alive():
        process.terminate()
        process.join()
        result_queue.close()
        raise TimeoutError(f"{method} search exceeded {SUBGRAPH_SEARCH_TIMEOUT}s")
    try:
        result = result_queue.get(timeout=1)
    except Empty as error:
        result_queue.close()
        raise RuntimeError(f"{method} search exited without returning results "
                           f"(exit code {process.exitcode})") from error
    finally:
        result_queue.close()
    if result[0] == "timeout":
        raise TimeoutError(result[1])
    if not result[0]:
        raise RuntimeError(f"{method} search failed: {result[1]}: {result[2]}")
    return result[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--output", default="GaussCode/comparison_report.md")
    ap.add_argument("--include-subgraphs", action="store_true",
                    help="run all current subgraph identification methods and compare their edge coverage")
    args = ap.parse_args()

    rows, details, pres, subgraph_rows = [], [], {}, []
    methods = ("k33", "k5", "k33knot", "k5knot", "k5contracted", "k5knotcontracted")
    paths = sorted(glob.glob("GaussCode/*_simple_cycles_with_gauss_report.txt")
                   + glob.glob("GaussCode/*_simple_cycles_with_ext_gauss_report.txt"))
    for path in paths:
        pdb, chain = os.path.basename(path).split("_")[0].split("-")
        extended = path.endswith("_simple_cycles_with_ext_gauss_report.txt")
        structure = f"{pdb}-{chain} (extended)" if extended else f"{pdb}-{chain}"
        ext, ext_count, records = parse_report(path)
        pres[structure] = compare_presentations(pdb, chain, records, extended=extended)
        cached = load_cache(pdb, chain)
        if cached is None:
            import networkx as nx
            from graph_data import load_graph_by_id
            graph, _ = load_graph_by_id(pdb + chain, False)
            app = {cycle_key(cycle): None for cycle in nx.simple_cycles(graph) if len(cycle) >= 3}
            cfile = None
        else:
            cfile, d = cached
            app = {}
            for loop in d["loops_analyzed"]:
                app[cycle_key(loop["nodes"])] = bool(loop.get("knotted"))
            # loops reported as knotted but absent from loops_analyzed
            for loop in d.get("loops", []):
                app.setdefault(cycle_key(loop["nodes"]), True)
        common = ext.keys() & app.keys()
        only_ext, only_app = ext.keys() - app.keys(), app.keys() - ext.keys()
        tab = Counter((ext[k], app[k]) for k in common) if cached else None
        rows.append((structure, ext_count, len(ext), (len(app), len(common), len(only_ext), len(only_app), tab,
                                                     os.path.basename(cfile) if cfile else None)))
        details.append((structure, only_ext, only_app))
        if args.include_subgraphs and cached:
            for method in methods:
                print(f"Running {method} subgraph identification for {pdb}-{chain}...", flush=True)
                try:
                    subgraphs = run_subgraph_finder(pdb, chain, method)
                except TimeoutError as e:
                    subgraph_rows.append((structure, method, None, None, None, None, f"incomplete: {e}"))
                    continue
                covered = set()
                for edges in subgraphs:
                    covered.update(cycle for cycle in ext if cycle <= edges)
                subgraph_rows.append((structure, method, len(subgraphs), len(covered),
                                      sum(ext[c] for c in covered),
                                      sum(app.get(c, False) for c in covered), "complete"))

    out = ["# Cycle comparison: external Gauss-code tool vs. this app", "",
           "Cycles are compared as undirected edge sets. App cycles come from whole-graph results in `knot_cache/`; "
           "when no cache exists, cycles are enumerated directly without HOMFLY classification.", "",
           "| Structure | Ext. cycles (unique) | App cycles | Common | Only external | Only app | Match |",
           "|---|---|---|---|---|---|---|"]
    for structure, ec, eu, r in rows:
        na, nc, oe, oa, _, _ = r
        out.append(f"| {structure} | {ec} ({eu}) | {na} | {nc} | {oe} | {oa} | "
                   f"{'identical' if oe == 0 and oa == 0 else f'{100 * nc / max(eu, na):.1f}%'} |")

    out += ["", "## Knottedness on common cycles", "",
            "App flag = HOMFLY says knotted; External flag = non-empty Gauss code (crossings present).", "",
            "| Structure | both knotted/crossing | app knotted, ext empty | app unknot, ext crossings | both trivial |",
            "|---|---|---|---|---|"]
    for structure, _, _, r in rows:
        if r[4] is None:
            out.append(f"| {structure} | unavailable (no HOMFLY cache) | - | - | - |")
            continue
        t = r[4]
        out.append(f"| {structure} | {t[(True, True)]} | {t[(False, True)]} | {t[(True, False)]} | {t[(False, False)]} |")
    out += ["", "\"app unknot, ext crossings\" is expected (unknots drawn with kinks). "
            "\"app knotted, ext empty\" would indicate a real disagreement.", ""]

    if args.include_subgraphs:
        out += ["## Current subgraph identification algorithms", "",
                "A GaussCode cycle is counted as covered when all of its edges occur together in at least one identified subgraph. "
                "This measures containment, not equality between a cycle and a subgraph. Contracted K_5 embeddings are expanded "
                "before comparing edges. Knotted-subgraph searches are limited to 120 seconds; searches that time out are "
                "marked incomplete rather than reported as zero results.", "",
                "| Structure | Method | Identified subgraphs | GaussCode cycles covered | Covered cycles with crossings | Covered app-knotted cycles | Status |",
                "|---|---|---:|---:|---:|---:|---|"]
        for structure, method, n_subgraphs, n_covered, n_crossing, n_knotted, status in subgraph_rows:
            if status != "complete":
                out.append(f"| {structure} | {method} | - | - | - | - | {status.replace('|', '/')} |")
            else:
                out.append(f"| {structure} | {method} | {n_subgraphs} | {n_covered} | {n_crossing} | "
                           f"{n_knotted} | complete |")
        out.append("")

    out += ["## Gauss code and Wirtinger presentation (same projection)", "",
            "Coordinates come from the atoms in `data/<id>-<chain>_simplified.json` (the bonds CSV files are not used). Recomputed by `wirtinger.external_wirtinger` (projection along z, higher z over, Reidemeister I kinks "
            "removed) from each cycle's node order in the external report. Legacy reports ignore crossing signs; "
            "extended reports include over/under and crossing signs.", "",
            "| Structure | Cycles | Identical Gauss code | Identical Wirtinger presentation | Not reproduced |",
            "|---|---|---|---|---|"]
    for structure, (n, g, w, bad, _) in pres.items():
        out.append(f"| {structure} | {n} | {g} | {w} | {len(bad)} |")
    out.append("")
    out += ["### Examples (external report vs. recomputed by the app)", ""]
    for structure, (_, _, _, _, ex) in pres.items():
        for nn_, g1, w1, g2, w2 in ex:
            out += [f"**{structure}**, cycle of {nn_} nodes", "",
                    f"- External Gauss code: `{g1}`", f"- App Gauss code: `{g2}`",
                    f"- External Wirtinger: `{w1}`", f"- App Wirtinger: `{w2}`", ""]

    for structure, oe, oa in details:
        if oe or oa:
            out += [f"## {structure}: differing cycles (up to 5 each)", ""]
            for label, s in (("Only external", oe), ("Only app", oa)):
                for k in sorted(s, key=len)[:5]:
                    nodes = sorted({n for e in k for n in e})
                    out.append(f"- {label} ({len(k)} edges): {', '.join(nodes)}")
            out.append("")

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        f.write("\n".join(out))
    print("\n".join(out))


if __name__ == "__main__":
    main()
