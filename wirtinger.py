"""Gauss code and Wirtinger presentation of a closed 3D polygonal curve (a loop of a spatial graph).

The curve is projected along a generic direction; crossings are found between non-adjacent segments.
Gauss code: crossings are numbered in order of first appearance, +k = over-pass, -k = under-pass.
Wirtinger presentation: one generator x_i per arc (arcs are cut at under-passes); each crossing gives
a relation x_o x_in x_o^{-1} x_out^{-1} = 1 (negative crossing) or x_o^{-1} x_in x_o x_out^{-1} = 1
(positive crossing), where x_o is the over arc and x_in -> x_out the under arc before/after the crossing.
The group does not depend on the projection direction (up to mirror image).
"""
import numpy as np

_EPS = 1e-6


def _crossings(P, d):
    """Crossings of the closed polygon P (n x 3) projected along unit vector d, or None if degenerate.
    Each crossing: (param_a, param_b, over_param, sign); params are segment index + fraction."""
    n = len(P)
    u = np.cross(d, [1.0, 0.0, 0.0] if abs(d[0]) < 0.9 else [0.0, 1.0, 0.0])
    u /= np.linalg.norm(u)
    v = np.cross(d, u)
    X, Y, Z = P @ u, P @ v, P @ d
    A = np.stack([X, Y], 1)
    B = np.roll(A, -1, axis=0)
    D = B - A
    zA, zD = Z, np.roll(Z, -1) - Z
    found = []
    for i in range(n):
        j = np.arange(i + 2, n)
        if i == 0:
            j = j[j != n - 1]
        if len(j) == 0:
            continue
        r, s = D[i], D[j]
        den = r[0] * s[:, 1] - r[1] * s[:, 0]
        w = A[j] - A[i]
        with np.errstate(divide="ignore", invalid="ignore"):
            t = (w[:, 0] * s[:, 1] - w[:, 1] * s[:, 0]) / den
            q = (w[:, 0] * r[1] - w[:, 1] * r[0]) / den
        ok = (np.abs(den) > 1e-12) & (t > -_EPS) & (t < 1 + _EPS) & (q > -_EPS) & (q < 1 + _EPS)
        for k in np.nonzero(ok)[0]:
            tt, qq, jj = t[k], q[k], j[k]
            if min(tt, 1 - tt, qq, 1 - qq) < _EPS:
                return None
            zi, zj = zA[i] + tt * zD[i], zA[jj] + qq * zD[jj]
            if abs(zi - zj) < _EPS:
                return None
            over_i = zi > zj
            ro, uo = (r, s[k]) if over_i else (s[k], r)
            sign = 1 if ro[0] * uo[1] - ro[1] * uo[0] > 0 else -1
            found.append((i + tt, jj + qq, i + tt if over_i else jj + qq, sign))
    return found


def loop_crossings(coords, tries=30, seed=0):
    """Crossings for a generic projection direction with the fewest crossings."""
    P = np.asarray(coords, dtype=float)
    rng = np.random.default_rng(seed)
    dirs = []
    c = P - P.mean(0)
    try:
        dirs.append(np.linalg.svd(c, full_matrices=False)[2][2])
    except np.linalg.LinAlgError:
        pass
    for _ in range(tries):
        x = rng.normal(size=3)
        dirs.append(x / np.linalg.norm(x))
    best = None
    for d in dirs:
        cr = _crossings(P, d / np.linalg.norm(d))
        if cr is not None and (best is None or len(cr) < len(best)):
            best = cr
    if best is None:
        raise ValueError("no generic projection found")
    return best


def wirtinger(coords, tries=30, seed=0):
    """Returns dict with 'gauss' (signed crossing sequence), 'crossings' (signs), 'generators' (arc count)
    and 'relations' (list of (over, in, out, sign) with 1-based arc indices)."""
    cr = loop_crossings(coords, tries, seed)
    m = len(cr)
    if m == 0:
        return dict(gauss=[], crossings=0, generators=1, relations=[], signs=[])
    events = []
    for k, (a, b, over, sign) in enumerate(cr):
        events.append((a, k, a == over))
        events.append((b, k, b == over))
    events.sort()
    label, gauss = {}, []
    for _, k, is_over in events:
        label.setdefault(k, len(label) + 1)
        gauss.append(label[k] if is_over else -label[k])
    n_under = sum(1 for e in events if not e[2])
    arc_before_over, under_arcs = {}, {}
    seen_under = 0
    for _, k, is_over in events:
        if is_over:
            arc_before_over[k] = seen_under if seen_under else n_under
        else:
            under_arcs[k] = (seen_under if seen_under else n_under, seen_under + 1)
            seen_under += 1
    rels = [(arc_before_over[k], *under_arcs[k], cr[k][3]) for k in sorted(label, key=label.get)]
    return dict(gauss=gauss, crossings=m, generators=n_under, relations=rels,
                signs=[cr[k][3] for k in sorted(label, key=label.get)])


def _events(cr):
    ev = []
    for k, (a, b, over, sign) in enumerate(cr):
        ev.append((a, k, a == over))
        ev.append((b, k, b == over))
    ev.sort()
    return ev


def _drop_kinks(ev, iterative):
    """Remove crossings whose two passes are cyclically adjacent (Reidemeister I kinks)."""
    while True:
        n = len(ev)
        kinks = {ev[i][1] for i in range(n) if n > 1 and ev[i][1] == ev[(i + 1) % n][1]}
        if not kinks:
            return ev
        ev = [e for e in ev if e[1] not in kinks]
        if not iterative:
            return ev


def external_wirtinger(coords, iterative=True):
    """Gauss code and Wirtinger presentation as produced by the external tool whose reports are in GaussCode/:
    projection along the z axis (higher z = over), crossings numbered by first appearance before Reidemeister I
    kinks are removed (so numbers may have gaps), arc k = k-1 under-passes passed (arc after the last under = 1),
    relations listed in under-pass order, always in the form x_o x_in x_o^{-1} x_out^{-1} = 1 (crossing signs ignored,
    so the relations are only valid for knots whose crossings all have the same sign)."""
    cr = _crossings(np.asarray(coords, dtype=float), np.array([0.0, 0.0, 1.0]))
    if cr is None:
        raise ValueError("degenerate projection along z")
    ev = _events(cr)
    label = {}
    for _, k, _ in ev:
        label.setdefault(k, len(label) + 1)
    ev = _drop_kinks(ev, iterative)
    gauss = [label[k] if o else -label[k] for _, k, o in ev]
    n = sum(1 for e in ev if not e[2])
    if n == 0:
        return dict(gauss=[], crossings=0, generators=1, relations=[], signs=[])
    arc_over, rels, seen = {}, [], 0
    for _, k, o in ev:
        if o:
            arc_over[k] = seen % n + 1
        else:
            seen += 1
            rels.append([k, seen, seen % n + 1])
    rels = [(arc_over[k], i, out, -1) for k, i, out in rels]
    return dict(gauss=gauss, crossings=len(ev) // 2, generators=n, relations=rels, signs=[])


def format_relation(rel):
    o, i, out, sign = rel
    a, b = (f"x_{o}", f"x_{o}^{{-1}}") if sign < 0 else (f"x_{o}^{{-1}}", f"x_{o}")
    return f"{a} x_{i} {b} x_{out}^{{-1}} = 1"


def format_presentation(w):
    gens = ", ".join(f"x_{i}" for i in range(1, w['generators'] + 1))
    if not w['relations']:
        return f"<{gens} | >  (trivial: free group on one generator)"
    return f"<{gens} | " + ",  ".join(format_relation(r) for r in w['relations']) + ">"
