# Cycle comparison: external Gauss-code tool vs. this app

Cycles are compared as undirected edge sets. App cycles come from the whole-graph results in `knot_cache`.

| Structure | Ext. cycles (unique) | App cycles | Common | Only external | Only app | Match |
|---|---|---|---|---|---|---|
| 1AOC-A | 186 (186) | 186 | 186 | 0 | 0 | identical |
| 1AOZ-A | 497 (497) | 497 | 497 | 0 | 0 | identical |
| 1ASO-A | 497 (497) | 497 | 497 | 0 | 0 | identical |
| 4B56-A | 20856 (20856) | 20856 | 20856 | 0 | 0 | identical |
| 4DOU-A | 9154 (9154) | 9154 | 9154 | 0 | 0 | identical |
| 5ZYA-D | 87 (87) | 87 | 87 | 0 | 0 | identical |

## Knottedness on common cycles

App flag = HOMFLY says knotted; External flag = non-empty Gauss code (crossings present).

| Structure | both knotted/crossing | app knotted, ext empty | app unknot, ext crossings | both trivial |
|---|---|---|---|---|
| 1AOC-A | 1 | 0 | 73 | 112 |
| 1AOZ-A | 6 | 0 | 324 | 167 |
| 1ASO-A | 6 | 0 | 324 | 167 |
| 4B56-A | 3696 | 0 | 17022 | 138 |
| 4DOU-A | 1125 | 0 | 3355 | 4674 |
| 5ZYA-D | 6 | 0 | 16 | 65 |

"app unknot, ext crossings" is expected (unknots drawn with kinks). "app knotted, ext empty" would indicate a real disagreement.

## Gauss code and Wirtinger presentation (same projection)

Recomputed by `wirtinger.external_wirtinger` (projection along z, higher z over, Reidemeister I kinks removed, crossing signs ignored) from each cycle's node order in the external report.

| Structure | Cycles | Identical Gauss code | Identical Wirtinger presentation | Not reproduced |
|---|---|---|---|---|
| 1AOC-A | 186 | 186 | 186 | 0 |
| 1AOZ-A | 497 | 497 | 497 | 0 |
| 1ASO-A | 497 | 497 | 497 | 0 |
| 4B56-A | 20856 | n/a | n/a | graph cannot be loaded from data/ (bonds CSV is not in the app's format) |
| 4DOU-A | 9154 | 9154 | 9154 | 0 |
| 5ZYA-D | 87 | 87 | 87 | 0 |
