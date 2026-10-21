The graphs can't contain K₅ subdivisions, but most of them do contain K₅ minors. Only 1A8E has neither.

**No K₅ subdivision.** A K₅ subdivision needs 5 vertices of degree ≥4. The loaded graphs have between 0 and 3 such vertices, so the finders can only ever return K₃,₃ subdivisions here:

| PDB | vertices with degree ≥4 |
|---|---|
| 1A8E | 1 |
| 1AOC | 0 |
| 1AOZ | 0 |
| 1ASO | 0 |
| 1B0L | 2 |
| 4DOU | 3 |
| 6KLG | 2 |

**K₅ minors.** I reduced each graph to its topological core by suppressing degree-2 vertices and dropping dangling ends, which leaves 12–25 vertices. Then I searched exhaustively by edge contraction:

| PDB | K₅ minor |
|---|---|
| 1A8E | no |
| 1AOC | yes |
| 1AOZ | yes |
| 1ASO | yes |
| 1B0L | yes |
| 4DOU | yes |
| 6KLG | yes |

A K₅ minor is not a "K₅ subgraph" in the Kuratowski sense, so OGDF and SageMath won't report it. These are minors because K₅ has degree 4 and the cores are almost entirely degree 3.

I didn't run this on 5ZYA or 6FF4; their simplified files are for other chains, so the loader couldn't find them.

If you want K₅ minors shown in the app, I can add a minor finder (its branch sets would be connected groups of nodes, not paths). Do you want that?


Now a quick UI check.

I added a **K5 minor** option to the "Finder" radio buttons. It lists the K₅ minors in the same panel and through the same Prev/Next navigation as the OGDF and SageMath results. I ran it on 1AOZ in the browser and it showed "Found 4 K_5 minor model(s) - showing 1 of 4: K_5 minor", with no errors.

- **What it finds:** it searches by edge contraction and returns up to 20 distinct models, each with 5 connected groups of nodes and the 10 edges joining them. After each hit it deletes one edge of that model and searches again.
- **Time limit:** the whole search is capped at 60 s. If it hits the cap, you get the models found so far.
- **Results by protein:**

| PDB | K₅ minor models found |
|---|---|
| 1A8E | 0 |
| 1AOC | 2 |
| 1AOZ | 4 |
| 1B0L | 1 |
| 4DOU | 4 (about 9 s) |
| 6KLG | 5 (about 6 s) |

1A8E has no K₅ minor, as before. I checked the 1AOC, 1AOZ and 1B0L models: every edge exists in the original graph, each model is connected, and a separate K₅-minor search on the model alone confirms it. 1A8E has no model to check.

The "Show selected obstruction only" and "Simplify subgraph" options work on these models like the other finders. The shared search results are in `dash_graphs.py`.



Page likely stuck loading; retry on a fresh tab.

The "Knotted loops" panel now has a second line under each loop that compares it with the OGDF and SageMath Kuratowski subgraphs and the K₅ minors. I ran it on 1AOC through the live app under the conda `sage` environment, so the Sage worker was used, and it didn't hang.

For 1AOC's single knotted loop (3_1, 28 nodes) it shows:

`OGDF: not related (11 found); SageMath: not related (2 found); K5 minor: not related (2 found)`

A loop is a cycle, so it can never be identical to a Kuratowski subdivision or a K₅ minor. For each finder the panel reports one of three results:
- **identical to #i:** the loop's edges are exactly the edges of that subgraph.
- **contained in #i of N:** the loop's edges are all inside that subgraph.
- **not related (N found):** neither of the above.

Say if you meant a different comparison and I'll change it.



I fixed the dangling edges in the K_5 models. I couldn't reproduce the 1A8E result, and the knot message is now clearer but I haven't found what caused your error.

**1A8E "Found 4 K_5 minor models"**
- I can't reproduce this. I ran the finder on 1A8E with the Simplified graph, and with the Topoly graph under every reduce, numbering and merge-residues setting. It finds 0 each time, which matches `Subgraphs.md`.
- 4DOU gives exactly 4 models. My guess is you were looking at stale panel text or a different graph. Please try again: load 1A8E fresh, then choose K5 minor.
- If you still get 4, tell me which Source, Simplification and merge settings you used.

**Valence-1 edges in 4DOU (fixed)**
- Contracting a group of nodes into one K_5 vertex could leave dangling edges that none of the 10 K_5 connections use. `find_k5_minors` now strips those, so no model has a vertex of valence 1.
- After the fix, the four 4DOU models have no degree-1 vertices.

**Knot in the K_5 minor**
- I didn't see the error you got. The HOMFLY test now runs on the cleaned 4DOU models, using 50 tries as a quick check rather than the app's 500. The four models came back as 4_1, 3_1, 3_1 and 0_1. The dangling edges may have been what upset it, but I haven't confirmed that.
- The "knotted loops" mode searches the whole loaded graph, not the K_5. I added "in the whole graph (not limited to a K_5 minor/Kuratowski subgraph)" to the status line and made the hint text say the same.
- To get the knot type of the K_5 itself, use "Run HOMFLY" or "Test knot (HOMFLY 500)", which test the obstruction shown.

The changes are in `dash_graphs.py`. I didn't run the full app UI after them.


## Problem finding knotted K₃,₃ subdivisions in 1AOC, 1AOZ and 1ASO

I'll start with the current cache and loop-finding code.

I found why no knotted K₃,₃ showed up and added a "Knotted K_3,3" finder to the Find panel. On 1AOC it now lists 11 K₃,₃ subdivisions that contain the knotted loop, and "Knot within" shows `+3_1` for the first. I tested that through the app on 1AOC only. For 1AOZ and 1ASO I only counted the knotted K₃,₃ subdivisions by script (the 80–204 per knotted loop in the last two bullets); I didn't run the new button on them.

- **Why they weren't found:** OGDF and SageMath report only a handful of K₃,₃ subdivisions (13 in 1AOC), and none of those contained a knotted cycle. The graphs actually contain far more, for example about 200 distinct ones in 1AOC.
  - The new "Knotted K_3,3" button enumerates all subdivisions that contain a knotted loop of the whole graph and lists up to 100, smallest first.
  - It first runs the whole-graph knotted-loop search, which took about 30 s on 1AOC.
  - In 1AOZ and 1ASO, each knotted loop lies in 29–204 K₃,₃ subdivisions.
- **Second bug:** Topoly's `find_loops` returns a loop whose first node is repeated at the end. That made 1AOC's knotted loop appear as 28 nodes instead of 27, and it broke the "contained in" check in the Knotted loops panel. Loops are now stripped of the repeated node.
- **Bonds:** `find_loops` has no notion of bond types. It sees whatever edges we pass, and the app passes all of them (CA, disulfide and side-chain edges).
  - I checked completeness against networkx: Topoly found all 186 cycles in 1AOC, and I didn't finish the comparison for 1AOZ and 1ASO.
  - Within the 13 K₃,₃ subdivisions the finders report for 1AOC, all 15 cycles of each came out unknotted, with HOMFLY CLOSED and the earlier `tries`-based closure not involved.
- **Cache:**
  - Files are now named `<pdbid>_<source>_<within>_<subgraph index>_<nodes>n_<hash>.json`, for example `1AOC_simplified_k33knot_0_27n_….json`. I added a short hash because simplification and numbering settings would otherwise collide.
  - Each file now stores the analyzed subgraph's nodes. For the knotted-loop searches it also stores `loops_analyzed`, which holds every analyzed loop with its HOMFLY result, unknots included.
  - The whole-subgraph "Run HOMFLY" cache stores the nodes but no loop list.
  - I deleted the old hash-named files, since the cache version changed.

I added the new finder to `README.md` and a short note on the cache format. The code changes are in `dash_graphs.py`.