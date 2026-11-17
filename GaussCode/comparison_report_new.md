# Cycle comparison: external Gauss-code tool vs. this app

Cycles are compared as undirected edge sets. App cycles come from whole-graph results in `knot_cache/`; when no cache exists, cycles are enumerated directly without HOMFLY classification.

| Structure | Ext. cycles (unique) | App cycles | Common | Only external | Only app | Match |
|---|---|---|---|---|---|---|
| 1AOC-A (extended) | 186 (186) | 186 | 186 | 0 | 0 | identical |
| 1AOC-A | 186 (186) | 186 | 186 | 0 | 0 | identical |
| 1AOZ-A (extended) | 497 (497) | 497 | 497 | 0 | 0 | identical |
| 1AOZ-A | 497 (497) | 497 | 497 | 0 | 0 | identical |
| 1ASO-A (extended) | 497 (497) | 497 | 497 | 0 | 0 | identical |
| 1ASO-A | 497 (497) | 497 | 497 | 0 | 0 | identical |
| 2XR9-A (extended) | 6110 (6110) | 6110 | 6110 | 0 | 0 | identical |
| 4B56-A (extended) | 20856 (20856) | 20856 | 20856 | 0 | 0 | identical |
| 4B56-A | 20856 (20856) | 20856 | 20856 | 0 | 0 | identical |
| 4DOU-A (extended) | 9154 (9154) | 9154 | 9154 | 0 | 0 | identical |
| 4DOU-A | 9154 (9154) | 9154 | 9154 | 0 | 0 | identical |
| 5ZYA-D (extended) | 87 (87) | 87 | 87 | 0 | 0 | identical |
| 5ZYA-D | 87 (87) | 87 | 87 | 0 | 0 | identical |

## Knottedness on common cycles

App flag = HOMFLY says knotted; External flag = non-empty Gauss code (crossings present).

| Structure | both knotted/crossing | app knotted, ext empty | app unknot, ext crossings | both trivial |
|---|---|---|---|---|
| 1AOC-A (extended) | 1 | 0 | 73 | 112 |
| 1AOC-A | 1 | 0 | 73 | 112 |
| 1AOZ-A (extended) | 6 | 0 | 324 | 167 |
| 1AOZ-A | 6 | 0 | 324 | 167 |
| 1ASO-A (extended) | 6 | 0 | 324 | 167 |
| 1ASO-A | 6 | 0 | 324 | 167 |
| 2XR9-A (extended) | unavailable (no HOMFLY cache) | - | - | - |
| 4B56-A (extended) | 3696 | 0 | 17022 | 138 |
| 4B56-A | 3696 | 0 | 17022 | 138 |
| 4DOU-A (extended) | 1125 | 0 | 3355 | 4674 |
| 4DOU-A | 1125 | 0 | 3355 | 4674 |
| 5ZYA-D (extended) | 6 | 0 | 16 | 65 |
| 5ZYA-D | 6 | 0 | 16 | 65 |

"app unknot, ext crossings" is expected (unknots drawn with kinks). "app knotted, ext empty" would indicate a real disagreement.

## Gauss code and Wirtinger presentation (same projection)

Coordinates come from the atoms in `data/<id>-<chain>_simplified.json` (the bonds CSV files are not used). Recomputed by `wirtinger.external_wirtinger` (projection along z, higher z over, Reidemeister I kinks removed) from each cycle's node order in the external report. Legacy reports ignore crossing signs; extended reports include over/under and crossing signs.

| Structure | Cycles | Identical Gauss code | Identical Wirtinger presentation | Not reproduced |
|---|---|---|---|---|
| 1AOC-A (extended) | 186 | 186 | 186 | 0 |
| 1AOC-A | 186 | 186 | 186 | 0 |
| 1AOZ-A (extended) | 497 | 497 | 497 | 0 |
| 1AOZ-A | 497 | 497 | 497 | 0 |
| 1ASO-A (extended) | 497 | 497 | 497 | 0 |
| 1ASO-A | 497 | 497 | 497 | 0 |
| 2XR9-A (extended) | 6110 | 6110 | 6110 | 0 |
| 4B56-A (extended) | 20856 | 20856 | 20856 | 0 |
| 4B56-A | 20856 | 20856 | 20856 | 0 |
| 4DOU-A (extended) | 9154 | 9154 | 9154 | 0 |
| 4DOU-A | 9154 | 9154 | 9154 | 0 |
| 5ZYA-D (extended) | 87 | 87 | 87 | 0 |
| 5ZYA-D | 87 | 87 | 87 | 0 |

### Examples (external report vs. recomputed by the app)

**1AOC-A (extended)**, cycle of 15 nodes

- External Gauss code: `['b1-', 'a2+', 'a3-', 'a1+', 'b2-', 'b3+']`
- App Gauss code: `['b1-', 'a2+', 'a3-', 'a1+', 'b2-', 'b3+']`
- External Wirtinger: `x_2^{-1} x_1 x_2 x_2^{-1} = 1,  x_2^{-1} x_2 x_2 x_3^{-1} = 1,  x_2 x_3 x_2^{-1} x_1^{-1} = 1`
- App Wirtinger: `x_2^{-1} x_1 x_2 x_2^{-1} = 1,  x_2^{-1} x_2 x_2 x_3^{-1} = 1,  x_2 x_3 x_2^{-1} x_1^{-1} = 1`

**1AOC-A (extended)**, cycle of 13 nodes

- External Gauss code: `['b1-', 'a2+', 'a3-', 'a1+', 'b2-', 'b3+']`
- App Gauss code: `['b1-', 'a2+', 'a3-', 'a1+', 'b2-', 'b3+']`
- External Wirtinger: `x_2^{-1} x_1 x_2 x_2^{-1} = 1,  x_2^{-1} x_2 x_2 x_3^{-1} = 1,  x_2 x_3 x_2^{-1} x_1^{-1} = 1`
- App Wirtinger: `x_2^{-1} x_1 x_2 x_2^{-1} = 1,  x_2^{-1} x_2 x_2 x_3^{-1} = 1,  x_2 x_3 x_2^{-1} x_1^{-1} = 1`

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

**1AOZ-A (extended)**, cycle of 12 nodes

- External Gauss code: `['a1+', 'a2+', 'a3-', 'a4+', 'a5-', 'b1-', 'b6+', 'b3+', 'b4-', 'b5+', 'b2-', 'a6-']`
- App Gauss code: `['a1+', 'a2+', 'a3-', 'a4+', 'a5-', 'b1-', 'b6+', 'b3+', 'b4-', 'b5+', 'b2-', 'a6-']`
- External Wirtinger: `x_1^{-1} x_1 x_1 x_2^{-1} = 1,  x_1 x_2 x_1^{-1} x_3^{-1} = 1,  x_1 x_3 x_1^{-1} x_4^{-1} = 1,  x_1^{-1} x_4 x_1 x_5^{-1} = 1,  x_1 x_5 x_1^{-1} x_6^{-1} = 1,  x_1^{-1} x_6 x_1 x_1^{-1} = 1`
- App Wirtinger: `x_1^{-1} x_1 x_1 x_2^{-1} = 1,  x_1 x_2 x_1^{-1} x_3^{-1} = 1,  x_1 x_3 x_1^{-1} x_4^{-1} = 1,  x_1^{-1} x_4 x_1 x_5^{-1} = 1,  x_1 x_5 x_1^{-1} x_6^{-1} = 1,  x_1^{-1} x_6 x_1 x_1^{-1} = 1`

**1AOZ-A (extended)**, cycle of 17 nodes

- External Gauss code: `['a1-', 'a3+', 'a4-', 'a5+', 'b6-', 'a7-', 'a8+', 'a6+', 'a9-', 'a10+', 'b5-', 'b8-', 'b7+', 'b9+', 'b10-', 'b1+', 'b3-', 'b4+']`
- App Gauss code: `['a1-', 'a3+', 'a4-', 'a5+', 'b6-', 'a7-', 'a8+', 'a6+', 'a9-', 'a10+', 'b5-', 'b8-', 'b7+', 'b9+', 'b10-', 'b1+', 'b3-', 'b4+']`
- External Wirtinger: `x_2^{-1} x_1 x_2 x_2^{-1} = 1,  x_1^{-1} x_2 x_1 x_3^{-1} = 1,  x_2^{-1} x_3 x_2 x_4^{-1} = 1,  x_2 x_4 x_2^{-1} x_5^{-1} = 1,  x_2 x_5 x_2^{-1} x_6^{-1} = 1,  x_2^{-1} x_6 x_2 x_7^{-1} = 1,  x_1 x_7 x_1^{-1} x_8^{-1} = 1,  x_1^{-1} x_8 x_1 x_9^{-1} = 1,  x_1 x_9 x_1^{-1} x_1^{-1} = 1`
- App Wirtinger: `x_2^{-1} x_1 x_2 x_2^{-1} = 1,  x_1^{-1} x_2 x_1 x_3^{-1} = 1,  x_2^{-1} x_3 x_2 x_4^{-1} = 1,  x_2 x_4 x_2^{-1} x_5^{-1} = 1,  x_2 x_5 x_2^{-1} x_6^{-1} = 1,  x_2^{-1} x_6 x_2 x_7^{-1} = 1,  x_1 x_7 x_1^{-1} x_8^{-1} = 1,  x_1^{-1} x_8 x_1 x_9^{-1} = 1,  x_1 x_9 x_1^{-1} x_1^{-1} = 1`

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

**1ASO-A (extended)**, cycle of 12 nodes

- External Gauss code: `['a1+', 'a2+', 'a3-', 'a4+', 'a5-', 'b1-', 'b6+', 'b3+', 'b4-', 'b5+', 'b2-', 'a6-']`
- App Gauss code: `['a1+', 'a2+', 'a3-', 'a4+', 'a5-', 'b1-', 'b6+', 'b3+', 'b4-', 'b5+', 'b2-', 'a6-']`
- External Wirtinger: `x_1^{-1} x_1 x_1 x_2^{-1} = 1,  x_1 x_2 x_1^{-1} x_3^{-1} = 1,  x_1 x_3 x_1^{-1} x_4^{-1} = 1,  x_1^{-1} x_4 x_1 x_5^{-1} = 1,  x_1 x_5 x_1^{-1} x_6^{-1} = 1,  x_1^{-1} x_6 x_1 x_1^{-1} = 1`
- App Wirtinger: `x_1^{-1} x_1 x_1 x_2^{-1} = 1,  x_1 x_2 x_1^{-1} x_3^{-1} = 1,  x_1 x_3 x_1^{-1} x_4^{-1} = 1,  x_1^{-1} x_4 x_1 x_5^{-1} = 1,  x_1 x_5 x_1^{-1} x_6^{-1} = 1,  x_1^{-1} x_6 x_1 x_1^{-1} = 1`

**1ASO-A (extended)**, cycle of 17 nodes

- External Gauss code: `['a1-', 'a3+', 'a4-', 'a5+', 'b6-', 'a7-', 'a8+', 'a6+', 'a9-', 'a10+', 'b5-', 'b8-', 'b7+', 'b9+', 'b10-', 'b1+', 'b3-', 'b4+']`
- App Gauss code: `['a1-', 'a3+', 'a4-', 'a5+', 'b6-', 'a7-', 'a8+', 'a6+', 'a9-', 'a10+', 'b5-', 'b8-', 'b7+', 'b9+', 'b10-', 'b1+', 'b3-', 'b4+']`
- External Wirtinger: `x_2^{-1} x_1 x_2 x_2^{-1} = 1,  x_1^{-1} x_2 x_1 x_3^{-1} = 1,  x_2^{-1} x_3 x_2 x_4^{-1} = 1,  x_2 x_4 x_2^{-1} x_5^{-1} = 1,  x_2 x_5 x_2^{-1} x_6^{-1} = 1,  x_2^{-1} x_6 x_2 x_7^{-1} = 1,  x_1 x_7 x_1^{-1} x_8^{-1} = 1,  x_1^{-1} x_8 x_1 x_9^{-1} = 1,  x_1 x_9 x_1^{-1} x_1^{-1} = 1`
- App Wirtinger: `x_2^{-1} x_1 x_2 x_2^{-1} = 1,  x_1^{-1} x_2 x_1 x_3^{-1} = 1,  x_2^{-1} x_3 x_2 x_4^{-1} = 1,  x_2 x_4 x_2^{-1} x_5^{-1} = 1,  x_2 x_5 x_2^{-1} x_6^{-1} = 1,  x_2^{-1} x_6 x_2 x_7^{-1} = 1,  x_1 x_7 x_1^{-1} x_8^{-1} = 1,  x_1^{-1} x_8 x_1 x_9^{-1} = 1,  x_1 x_9 x_1^{-1} x_1^{-1} = 1`

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

**2XR9-A (extended)**, cycle of 21 nodes

- External Gauss code: `['a2-', 'a3+', 'a5-', 'b2+', 'b3-', 'b5+']`
- App Gauss code: `['a2-', 'a3+', 'a5-', 'b2+', 'b3-', 'b5+']`
- External Wirtinger: `x_1 x_1 x_1^{-1} x_2^{-1} = 1,  x_1^{-1} x_2 x_1 x_3^{-1} = 1,  x_1 x_3 x_1^{-1} x_1^{-1} = 1`
- App Wirtinger: `x_1 x_1 x_1^{-1} x_2^{-1} = 1,  x_1^{-1} x_2 x_1 x_3^{-1} = 1,  x_1 x_3 x_1^{-1} x_1^{-1} = 1`

**2XR9-A (extended)**, cycle of 23 nodes

- External Gauss code: `['a2-', 'a3+', 'a5-', 'b2+', 'b3-', 'b5+']`
- App Gauss code: `['a2-', 'a3+', 'a5-', 'b2+', 'b3-', 'b5+']`
- External Wirtinger: `x_1 x_1 x_1^{-1} x_2^{-1} = 1,  x_1^{-1} x_2 x_1 x_3^{-1} = 1,  x_1 x_3 x_1^{-1} x_1^{-1} = 1`
- App Wirtinger: `x_1 x_1 x_1^{-1} x_2^{-1} = 1,  x_1^{-1} x_2 x_1 x_3^{-1} = 1,  x_1 x_3 x_1^{-1} x_1^{-1} = 1`

**4B56-A (extended)**, cycle of 26 nodes

- External Gauss code: `['a1-', 'a2+', 'a3-', 'b1+', 'b2-', 'b3+', 'a6-', 'a7+', 'a8-', 'b6+', 'a10+', 'a11-', 'a12+', 'b10-', 'b11+', 'b12-', 'b7-', 'b8+']`
- App Gauss code: `['a1-', 'a2+', 'a3-', 'b1+', 'b2-', 'b3+', 'a6-', 'a7+', 'a8-', 'b6+', 'a10+', 'a11-', 'a12+', 'b10-', 'b11+', 'b12-', 'b7-', 'b8+']`
- External Wirtinger: `x_1 x_1 x_1^{-1} x_2^{-1} = 1,  x_1^{-1} x_2 x_1 x_3^{-1} = 1,  x_1 x_3 x_1^{-1} x_4^{-1} = 1,  x_4 x_4 x_4^{-1} x_5^{-1} = 1,  x_5^{-1} x_5 x_5 x_6^{-1} = 1,  x_5 x_6 x_5^{-1} x_7^{-1} = 1,  x_5^{-1} x_7 x_5 x_8^{-1} = 1,  x_4^{-1} x_8 x_4 x_9^{-1} = 1,  x_4 x_9 x_4^{-1} x_1^{-1} = 1`
- App Wirtinger: `x_1 x_1 x_1^{-1} x_2^{-1} = 1,  x_1^{-1} x_2 x_1 x_3^{-1} = 1,  x_1 x_3 x_1^{-1} x_4^{-1} = 1,  x_4 x_4 x_4^{-1} x_5^{-1} = 1,  x_5^{-1} x_5 x_5 x_6^{-1} = 1,  x_5 x_6 x_5^{-1} x_7^{-1} = 1,  x_5^{-1} x_7 x_5 x_8^{-1} = 1,  x_4^{-1} x_8 x_4 x_9^{-1} = 1,  x_4 x_9 x_4^{-1} x_1^{-1} = 1`

**4B56-A (extended)**, cycle of 6 nodes

- External Gauss code: `['b1+', 'b2-', 'b3+', 'b4-', 'b5+', 'a3-', 'a2+', 'a1-', 'a4+', 'a5-']`
- App Gauss code: `['b1+', 'b2-', 'b3+', 'b4-', 'b5+', 'a3-', 'a2+', 'a1-', 'a4+', 'a5-']`
- External Wirtinger: `x_1 x_1 x_1^{-1} x_2^{-1} = 1,  x_1^{-1} x_2 x_1 x_3^{-1} = 1,  x_1 x_3 x_1^{-1} x_4^{-1} = 1,  x_1^{-1} x_4 x_1 x_5^{-1} = 1,  x_1 x_5 x_1^{-1} x_1^{-1} = 1`
- App Wirtinger: `x_1 x_1 x_1^{-1} x_2^{-1} = 1,  x_1^{-1} x_2 x_1 x_3^{-1} = 1,  x_1 x_3 x_1^{-1} x_4^{-1} = 1,  x_1^{-1} x_4 x_1 x_5^{-1} = 1,  x_1 x_5 x_1^{-1} x_1^{-1} = 1`

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

**4DOU-A (extended)**, cycle of 17 nodes

- External Gauss code: `['a1-', 'b2+', 'b3-', 'a4+', 'a5-', 'a3+', 'a2-', 'b1+', 'b4-', 'b5+']`
- App Gauss code: `['a1-', 'b2+', 'b3-', 'a4+', 'a5-', 'a3+', 'a2-', 'b1+', 'b4-', 'b5+']`
- External Wirtinger: `x_3 x_1 x_3^{-1} x_2^{-1} = 1,  x_3^{-1} x_2 x_3 x_3^{-1} = 1,  x_1 x_3 x_1^{-1} x_4^{-1} = 1,  x_3^{-1} x_4 x_3 x_5^{-1} = 1,  x_3 x_5 x_3^{-1} x_1^{-1} = 1`
- App Wirtinger: `x_3 x_1 x_3^{-1} x_2^{-1} = 1,  x_3^{-1} x_2 x_3 x_3^{-1} = 1,  x_1 x_3 x_1^{-1} x_4^{-1} = 1,  x_3^{-1} x_4 x_3 x_5^{-1} = 1,  x_3 x_5 x_3^{-1} x_1^{-1} = 1`

**4DOU-A (extended)**, cycle of 13 nodes

- External Gauss code: `['a1-', 'b2+', 'b3-', 'a4+', 'a5-', 'a3+', 'a2-', 'b1+', 'b4-', 'b5+']`
- App Gauss code: `['a1-', 'b2+', 'b3-', 'a4+', 'a5-', 'a3+', 'a2-', 'b1+', 'b4-', 'b5+']`
- External Wirtinger: `x_3 x_1 x_3^{-1} x_2^{-1} = 1,  x_3^{-1} x_2 x_3 x_3^{-1} = 1,  x_1 x_3 x_1^{-1} x_4^{-1} = 1,  x_3^{-1} x_4 x_3 x_5^{-1} = 1,  x_3 x_5 x_3^{-1} x_1^{-1} = 1`
- App Wirtinger: `x_3 x_1 x_3^{-1} x_2^{-1} = 1,  x_3^{-1} x_2 x_3 x_3^{-1} = 1,  x_1 x_3 x_1^{-1} x_4^{-1} = 1,  x_3^{-1} x_4 x_3 x_5^{-1} = 1,  x_3 x_5 x_3^{-1} x_1^{-1} = 1`

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

**5ZYA-D (extended)**, cycle of 20 nodes

- External Gauss code: `['b2-', 'b3+', 'b7-', 'a8+', 'a9-', 'a2+', 'a3-', 'a7+', 'b8-', 'b9+']`
- App Gauss code: `['b2-', 'b3+', 'b7-', 'a8+', 'a9-', 'a2+', 'a3-', 'a7+', 'b8-', 'b9+']`
- External Wirtinger: `x_4^{-1} x_1 x_4 x_2^{-1} = 1,  x_4 x_2 x_4^{-1} x_3^{-1} = 1,  x_4^{-1} x_3 x_4 x_4^{-1} = 1,  x_4^{-1} x_4 x_4 x_5^{-1} = 1,  x_4 x_5 x_4^{-1} x_1^{-1} = 1`
- App Wirtinger: `x_4^{-1} x_1 x_4 x_2^{-1} = 1,  x_4 x_2 x_4^{-1} x_3^{-1} = 1,  x_4^{-1} x_3 x_4 x_4^{-1} = 1,  x_4^{-1} x_4 x_4 x_5^{-1} = 1,  x_4 x_5 x_4^{-1} x_1^{-1} = 1`

**5ZYA-D (extended)**, cycle of 21 nodes

- External Gauss code: `['b2-', 'b3+', 'b6-', 'a7+', 'a8-', 'a2+', 'a3-', 'a6+', 'b7-', 'b8+']`
- App Gauss code: `['b2-', 'b3+', 'b6-', 'a7+', 'a8-', 'a2+', 'a3-', 'a6+', 'b7-', 'b8+']`
- External Wirtinger: `x_4^{-1} x_1 x_4 x_2^{-1} = 1,  x_4 x_2 x_4^{-1} x_3^{-1} = 1,  x_4^{-1} x_3 x_4 x_4^{-1} = 1,  x_4^{-1} x_4 x_4 x_5^{-1} = 1,  x_4 x_5 x_4^{-1} x_1^{-1} = 1`
- App Wirtinger: `x_4^{-1} x_1 x_4 x_2^{-1} = 1,  x_4 x_2 x_4^{-1} x_3^{-1} = 1,  x_4^{-1} x_3 x_4 x_4^{-1} = 1,  x_4^{-1} x_4 x_4 x_5^{-1} = 1,  x_4 x_5 x_4^{-1} x_1^{-1} = 1`

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
