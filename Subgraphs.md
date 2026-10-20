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

When the app runs from the `.venv` without Sage, the SageMath part shows "n/a (SageMath worker failed: …)".

The change is in `dash_graphs.py`, in `annotate_knotted_loops`, `obstruction_summary` and `knot_status`.