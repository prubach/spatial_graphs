"""Compare the cycles found by the external Gauss-code tool (GaussCode/*_simple_cycles_with_gauss_report.txt)
with the cycles analysed by this app (whole-graph results cached in knot_cache/).

Cycles are compared as sets of undirected edges. For cycles present in both, the external tool's
"has a non-empty Gauss code" (crossings in the projection) is cross-tabulated with the app's
HOMFLY-based "knotted" flag. A non-empty Gauss code does not imply a knot (it may be an unknot with
kinks), so only "knotted but empty Gauss code" is a genuine inconsistency.

Usage: python compare_gausscode.py [-o REPORT.md]
"""
import argparse
import glob
import json
import os
import re
from collections import Counter

NODE = re.compile(r"^[A-Za-z0-9]*?(-?\d+[A-Za-z]?):(\w+)$")


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


def compare_presentations(pdb, chain, records):
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
            r = external_wirtinger([pos[n] for n in nodes])
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
            r = external_wirtinger([pos[n] for n in nodes])
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


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--output", default="GaussCode/comparison_report.md")
    args = ap.parse_args()

    rows, details, pres = [], [], {}
    for path in sorted(glob.glob("GaussCode/*_simple_cycles_with_gauss_report.txt")):
        pdb, chain = os.path.basename(path).split("_")[0].split("-")
        ext, ext_count, records = parse_report(path)
        pres[(pdb, chain)] = compare_presentations(pdb, chain, records)
        cached = load_cache(pdb, chain)
        if cached is None:
            rows.append((pdb, chain, ext_count, len(ext), None))
            continue
        cfile, d = cached
        app = {}
        for loop in d["loops_analyzed"]:
            app[cycle_key(loop["nodes"])] = bool(loop.get("knotted"))
        # loops reported as knotted but absent from loops_analyzed
        for loop in d.get("loops", []):
            app.setdefault(cycle_key(loop["nodes"]), True)
        common = ext.keys() & app.keys()
        only_ext, only_app = ext.keys() - app.keys(), app.keys() - ext.keys()
        tab = Counter((ext[k], app[k]) for k in common)
        rows.append((pdb, chain, ext_count, len(ext), (len(app), len(common), len(only_ext), len(only_app), tab,
                                                        os.path.basename(cfile))))
        details.append((pdb, chain, only_ext, only_app))

    out = ["# Cycle comparison: external Gauss-code tool vs. this app", "",
           "Cycles are compared as undirected edge sets. App cycles come from the whole-graph results in `knot_cache/`.", "",
           "| Structure | Ext. cycles (unique) | App cycles | Common | Only external | Only app | Match |",
           "|---|---|---|---|---|---|---|"]
    for pdb, chain, ec, eu, r in rows:
        if r is None:
            out.append(f"| {pdb}-{chain} | {ec} ({eu}) | no cache | - | - | - | - |")
            continue
        na, nc, oe, oa, _, _ = r
        out.append(f"| {pdb}-{chain} | {ec} ({eu}) | {na} | {nc} | {oe} | {oa} | "
                   f"{'identical' if oe == 0 and oa == 0 else f'{100 * nc / max(eu, na):.1f}%'} |")

    out += ["", "## Knottedness on common cycles", "",
            "App flag = HOMFLY says knotted; External flag = non-empty Gauss code (crossings present).", "",
            "| Structure | both knotted/crossing | app knotted, ext empty | app unknot, ext crossings | both trivial |",
            "|---|---|---|---|---|"]
    for pdb, chain, _, _, r in rows:
        if r is None:
            continue
        t = r[4]
        out.append(f"| {pdb}-{chain} | {t[(True, True)]} | {t[(False, True)]} | {t[(True, False)]} | {t[(False, False)]} |")
    out += ["", "\"app unknot, ext crossings\" is expected (unknots drawn with kinks). "
            "\"app knotted, ext empty\" would indicate a real disagreement.", ""]

    out += ["## Gauss code and Wirtinger presentation (same projection)", "",
            "Coordinates come from the atoms in `data/<id>-<chain>_simplified.json` (the bonds CSV files are not used). Recomputed by `wirtinger.external_wirtinger` (projection along z, higher z over, Reidemeister I kinks "
            "removed, crossing signs ignored) from each cycle's node order in the external report.", "",
            "| Structure | Cycles | Identical Gauss code | Identical Wirtinger presentation | Not reproduced |",
            "|---|---|---|---|---|"]
    for (pdb, chain), (n, g, w, bad, _) in pres.items():
        out.append(f"| {pdb}-{chain} | {n} | {g} | {w} | {len(bad)} |")
    out.append("")
    out += ["### Examples (external report vs. recomputed by the app)", ""]
    for (pdb, chain), (_, _, _, _, ex) in pres.items():
        for nn_, g1, w1, g2, w2 in ex:
            out += [f"**{pdb}-{chain}**, cycle of {nn_} nodes", "",
                    f"- External Gauss code: `{g1}`", f"- App Gauss code: `{g2}`",
                    f"- External Wirtinger: `{w1}`", f"- App Wirtinger: `{w2}`", ""]

    for pdb, chain, oe, oa in details:
        if oe or oa:
            out += [f"## {pdb}-{chain}: differing cycles (up to 5 each)", ""]
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
