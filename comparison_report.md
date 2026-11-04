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

Coordinates come from the atoms in `data/<id>-<chain>_simplified.json` (the bonds CSV files are not used). Recomputed by `wirtinger.external_wirtinger` (projection along z, higher z over, Reidemeister I kinks removed, crossing signs ignored) from each cycle's node order in the external report.

| Structure | Cycles | Identical Gauss code | Identical Wirtinger presentation | Not reproduced |
|---|---|---|---|---|
| 1AOC-A | 186 | 186 | 186 | 0 |
| 1AOZ-A | 497 | 497 | 497 | 0 |
| 1ASO-A | 497 | 497 | 497 | 0 |
| 4B56-A | 20856 | 20856 | 20856 | 0 |
| 4DOU-A | 9154 | 9154 | 9154 | 0 |
| 5ZYA-D | 87 | 87 | 87 | 0 |

### Examples (external report vs. recomputed by the app)

**1AOC-A**, cycle of 15 nodes

- External Gauss code: `[1, 2, 3, -1, -2, -3]`
- App Gauss code: `[1, 2, 3, -1, -2, -3]`
- External Wirtinger: `x_1 x_1 x_1^{-1} x_2^{-1} = 1,  x_1 x_2 x_1^{-1} x_3^{-1} = 1,  x_1 x_3 x_1^{-1} x_1^{-1} = 1`
- App Wirtinger: `x_1 x_1 x_1^{-1} x_2^{-1} = 1,  x_1 x_2 x_1^{-1} x_3^{-1} = 1,  x_1 x_3 x_1^{-1} x_1^{-1} = 1`

**1AOC-A**, cycle of 13 nodes

- External Gauss code: `[1, 2, 3, -1, -2, -3]`
- App Gauss code: `[1, 2, 3, -1, -2, -3]`
- External Wirtinger: `x_1 x_1 x_1^{-1} x_2^{-1} = 1,  x_1 x_2 x_1^{-1} x_3^{-1} = 1,  x_1 x_3 x_1^{-1} x_1^{-1} = 1`
- App Wirtinger: `x_1 x_1 x_1^{-1} x_2^{-1} = 1,  x_1 x_2 x_1^{-1} x_3^{-1} = 1,  x_1 x_3 x_1^{-1} x_1^{-1} = 1`

**1AOZ-A**, cycle of 12 nodes

- External Gauss code: `[1, 2, -3, -4, -5, -6, -2, -1, 4, 5, 6, 3]`
- App Gauss code: `[1, 2, -3, -4, -5, -6, -2, -1, 4, 5, 6, 3]`
- External Wirtinger: `x_1 x_1 x_1^{-1} x_2^{-1} = 1,  x_1 x_2 x_1^{-1} x_3^{-1} = 1,  x_1 x_3 x_1^{-1} x_4^{-1} = 1,  x_1 x_4 x_1^{-1} x_5^{-1} = 1,  x_1 x_5 x_1^{-1} x_6^{-1} = 1,  x_1 x_6 x_1^{-1} x_1^{-1} = 1`
- App Wirtinger: `x_1 x_1 x_1^{-1} x_2^{-1} = 1,  x_1 x_2 x_1^{-1} x_3^{-1} = 1,  x_1 x_3 x_1^{-1} x_4^{-1} = 1,  x_1 x_4 x_1^{-1} x_5^{-1} = 1,  x_1 x_5 x_1^{-1} x_6^{-1} = 1,  x_1 x_6 x_1^{-1} x_1^{-1} = 1`

**1AOZ-A**, cycle of 17 nodes

- External Gauss code: `[1, 2, 3, -1, 4, 5, 6, 8, -5, -6, -8, -9, -10, -3, -2, -4, 9, 10]`
- App Gauss code: `[1, 2, 3, -1, 4, 5, 6, 8, -5, -6, -8, -9, -10, -3, -2, -4, 9, 10]`
- External Wirtinger: `x_1 x_1 x_1^{-1} x_2^{-1} = 1,  x_2 x_2 x_2^{-1} x_3^{-1} = 1,  x_2 x_3 x_2^{-1} x_4^{-1} = 1,  x_2 x_4 x_2^{-1} x_5^{-1} = 1,  x_1 x_5 x_1^{-1} x_6^{-1} = 1,  x_1 x_6 x_1^{-1} x_7^{-1} = 1,  x_1 x_7 x_1^{-1} x_8^{-1} = 1,  x_1 x_8 x_1^{-1} x_9^{-1} = 1,  x_2 x_9 x_2^{-1} x_1^{-1} = 1`
- App Wirtinger: `x_1 x_1 x_1^{-1} x_2^{-1} = 1,  x_2 x_2 x_2^{-1} x_3^{-1} = 1,  x_2 x_3 x_2^{-1} x_4^{-1} = 1,  x_2 x_4 x_2^{-1} x_5^{-1} = 1,  x_1 x_5 x_1^{-1} x_6^{-1} = 1,  x_1 x_6 x_1^{-1} x_7^{-1} = 1,  x_1 x_7 x_1^{-1} x_8^{-1} = 1,  x_1 x_8 x_1^{-1} x_9^{-1} = 1,  x_2 x_9 x_2^{-1} x_1^{-1} = 1`

**1ASO-A**, cycle of 12 nodes

- External Gauss code: `[1, 2, -3, -4, -5, -6, -2, -1, 4, 5, 6, 3]`
- App Gauss code: `[1, 2, -3, -4, -5, -6, -2, -1, 4, 5, 6, 3]`
- External Wirtinger: `x_1 x_1 x_1^{-1} x_2^{-1} = 1,  x_1 x_2 x_1^{-1} x_3^{-1} = 1,  x_1 x_3 x_1^{-1} x_4^{-1} = 1,  x_1 x_4 x_1^{-1} x_5^{-1} = 1,  x_1 x_5 x_1^{-1} x_6^{-1} = 1,  x_1 x_6 x_1^{-1} x_1^{-1} = 1`
- App Wirtinger: `x_1 x_1 x_1^{-1} x_2^{-1} = 1,  x_1 x_2 x_1^{-1} x_3^{-1} = 1,  x_1 x_3 x_1^{-1} x_4^{-1} = 1,  x_1 x_4 x_1^{-1} x_5^{-1} = 1,  x_1 x_5 x_1^{-1} x_6^{-1} = 1,  x_1 x_6 x_1^{-1} x_1^{-1} = 1`

**1ASO-A**, cycle of 17 nodes

- External Gauss code: `[1, 2, 3, -1, 4, 5, 6, 8, -5, -6, -8, -9, -10, -3, -2, -4, 9, 10]`
- App Gauss code: `[1, 2, 3, -1, 4, 5, 6, 8, -5, -6, -8, -9, -10, -3, -2, -4, 9, 10]`
- External Wirtinger: `x_1 x_1 x_1^{-1} x_2^{-1} = 1,  x_2 x_2 x_2^{-1} x_3^{-1} = 1,  x_2 x_3 x_2^{-1} x_4^{-1} = 1,  x_2 x_4 x_2^{-1} x_5^{-1} = 1,  x_1 x_5 x_1^{-1} x_6^{-1} = 1,  x_1 x_6 x_1^{-1} x_7^{-1} = 1,  x_1 x_7 x_1^{-1} x_8^{-1} = 1,  x_1 x_8 x_1^{-1} x_9^{-1} = 1,  x_2 x_9 x_2^{-1} x_1^{-1} = 1`
- App Wirtinger: `x_1 x_1 x_1^{-1} x_2^{-1} = 1,  x_2 x_2 x_2^{-1} x_3^{-1} = 1,  x_2 x_3 x_2^{-1} x_4^{-1} = 1,  x_2 x_4 x_2^{-1} x_5^{-1} = 1,  x_1 x_5 x_1^{-1} x_6^{-1} = 1,  x_1 x_6 x_1^{-1} x_7^{-1} = 1,  x_1 x_7 x_1^{-1} x_8^{-1} = 1,  x_1 x_8 x_1^{-1} x_9^{-1} = 1,  x_2 x_9 x_2^{-1} x_1^{-1} = 1`

**4B56-A**, cycle of 26 nodes

- External Gauss code: `[1, 2, 3, -1, -2, -3, 6, 7, 8, -6, 10, 11, 12, -10, -11, -12, -7, -8]`
- App Gauss code: `[1, 2, 3, -1, -2, -3, 6, 7, 8, -6, 10, 11, 12, -10, -11, -12, -7, -8]`
- External Wirtinger: `x_1 x_1 x_1^{-1} x_2^{-1} = 1,  x_1 x_2 x_1^{-1} x_3^{-1} = 1,  x_1 x_3 x_1^{-1} x_4^{-1} = 1,  x_4 x_4 x_4^{-1} x_5^{-1} = 1,  x_5 x_5 x_5^{-1} x_6^{-1} = 1,  x_5 x_6 x_5^{-1} x_7^{-1} = 1,  x_5 x_7 x_5^{-1} x_8^{-1} = 1,  x_4 x_8 x_4^{-1} x_9^{-1} = 1,  x_4 x_9 x_4^{-1} x_1^{-1} = 1`
- App Wirtinger: `x_1 x_1 x_1^{-1} x_2^{-1} = 1,  x_1 x_2 x_1^{-1} x_3^{-1} = 1,  x_1 x_3 x_1^{-1} x_4^{-1} = 1,  x_4 x_4 x_4^{-1} x_5^{-1} = 1,  x_5 x_5 x_5^{-1} x_6^{-1} = 1,  x_5 x_6 x_5^{-1} x_7^{-1} = 1,  x_5 x_7 x_5^{-1} x_8^{-1} = 1,  x_4 x_8 x_4^{-1} x_9^{-1} = 1,  x_4 x_9 x_4^{-1} x_1^{-1} = 1`

**4B56-A**, cycle of 6 nodes

- External Gauss code: `[-1, -2, -3, -4, -5, 3, 2, 1, 4, 5]`
- App Gauss code: `[-1, -2, -3, -4, -5, 3, 2, 1, 4, 5]`
- External Wirtinger: `x_1 x_1 x_1^{-1} x_2^{-1} = 1,  x_1 x_2 x_1^{-1} x_3^{-1} = 1,  x_1 x_3 x_1^{-1} x_4^{-1} = 1,  x_1 x_4 x_1^{-1} x_5^{-1} = 1,  x_1 x_5 x_1^{-1} x_1^{-1} = 1`
- App Wirtinger: `x_1 x_1 x_1^{-1} x_2^{-1} = 1,  x_1 x_2 x_1^{-1} x_3^{-1} = 1,  x_1 x_3 x_1^{-1} x_4^{-1} = 1,  x_1 x_4 x_1^{-1} x_5^{-1} = 1,  x_1 x_5 x_1^{-1} x_1^{-1} = 1`

**4DOU-A**, cycle of 17 nodes

- External Gauss code: `[1, -2, -3, 4, 5, 3, 2, -1, -4, -5]`
- App Gauss code: `[1, -2, -3, 4, 5, 3, 2, -1, -4, -5]`
- External Wirtinger: `x_3 x_1 x_3^{-1} x_2^{-1} = 1,  x_3 x_2 x_3^{-1} x_3^{-1} = 1,  x_1 x_3 x_1^{-1} x_4^{-1} = 1,  x_3 x_4 x_3^{-1} x_5^{-1} = 1,  x_3 x_5 x_3^{-1} x_1^{-1} = 1`
- App Wirtinger: `x_3 x_1 x_3^{-1} x_2^{-1} = 1,  x_3 x_2 x_3^{-1} x_3^{-1} = 1,  x_1 x_3 x_1^{-1} x_4^{-1} = 1,  x_3 x_4 x_3^{-1} x_5^{-1} = 1,  x_3 x_5 x_3^{-1} x_1^{-1} = 1`

**4DOU-A**, cycle of 13 nodes

- External Gauss code: `[1, -2, -3, 4, 5, 3, 2, -1, -4, -5]`
- App Gauss code: `[1, -2, -3, 4, 5, 3, 2, -1, -4, -5]`
- External Wirtinger: `x_3 x_1 x_3^{-1} x_2^{-1} = 1,  x_3 x_2 x_3^{-1} x_3^{-1} = 1,  x_1 x_3 x_1^{-1} x_4^{-1} = 1,  x_3 x_4 x_3^{-1} x_5^{-1} = 1,  x_3 x_5 x_3^{-1} x_1^{-1} = 1`
- App Wirtinger: `x_3 x_1 x_3^{-1} x_2^{-1} = 1,  x_3 x_2 x_3^{-1} x_3^{-1} = 1,  x_1 x_3 x_1^{-1} x_4^{-1} = 1,  x_3 x_4 x_3^{-1} x_5^{-1} = 1,  x_3 x_5 x_3^{-1} x_1^{-1} = 1`

**5ZYA-D**, cycle of 20 nodes

- External Gauss code: `[1, 2, -3, -4, -6, -1, -2, 3, 4, 6]`
- App Gauss code: `[1, 2, -3, -4, -6, -1, -2, 3, 4, 6]`
- External Wirtinger: `x_1 x_1 x_1^{-1} x_2^{-1} = 1,  x_1 x_2 x_1^{-1} x_3^{-1} = 1,  x_1 x_3 x_1^{-1} x_4^{-1} = 1,  x_1 x_4 x_1^{-1} x_5^{-1} = 1,  x_1 x_5 x_1^{-1} x_1^{-1} = 1`
- App Wirtinger: `x_1 x_1 x_1^{-1} x_2^{-1} = 1,  x_1 x_2 x_1^{-1} x_3^{-1} = 1,  x_1 x_3 x_1^{-1} x_4^{-1} = 1,  x_1 x_4 x_1^{-1} x_5^{-1} = 1,  x_1 x_5 x_1^{-1} x_1^{-1} = 1`

**5ZYA-D**, cycle of 21 nodes

- External Gauss code: `[1, 2, -3, -4, -6, -1, -2, 3, 4, 6]`
- App Gauss code: `[1, 2, -3, -4, -6, -1, -2, 3, 4, 6]`
- External Wirtinger: `x_1 x_1 x_1^{-1} x_2^{-1} = 1,  x_1 x_2 x_1^{-1} x_3^{-1} = 1,  x_1 x_3 x_1^{-1} x_4^{-1} = 1,  x_1 x_4 x_1^{-1} x_5^{-1} = 1,  x_1 x_5 x_1^{-1} x_1^{-1} = 1`
- App Wirtinger: `x_1 x_1 x_1^{-1} x_2^{-1} = 1,  x_1 x_2 x_1^{-1} x_3^{-1} = 1,  x_1 x_3 x_1^{-1} x_4^{-1} = 1,  x_1 x_4 x_1^{-1} x_5^{-1} = 1,  x_1 x_5 x_1^{-1} x_1^{-1} = 1`


###


- **Cycles:** both tools found identical cycle sets in all six structures.

| Structure | Cycles |
|---|---|
| 1AOC-A | 186 |
| 1AOZ-A | 497 |
| 1ASO-A | 497 |
| 4B56-A | 20,856 |
| 4DOU-A | 9,154 |
| 5ZYA-D | 87 |

- **Gauss code and Wirtinger presentation:** all of them match the external reports, using the same projection and coordinates from the simplified JSON files.
- **Knottedness:** no cycle the app calls knotted has an empty Gauss code, so there is no disagreement. Many cycles the app calls unknotted still have crossings; for example, 17,022 in 4B56-A. I haven't verified them, but they are most likely unknots drawn with kinks.