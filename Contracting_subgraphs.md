 
 Root Cause
 
The K₅ search returns the original subgraph representing a minor, not the contracted K₅ itself. In the test case (1a8e) debugger, a synthetic K₅ model returned 10 vertices and 15 edges, with every vertex having degree 3; contracting its branch-set edges yields K₅.

The knotted search similarly checks for a knotted loop in the uncontracted model. It does not verify that the loop survives the chosen contractions, so a model can be labeled knotted even when the displayed contracted K₅ would not be.

 Recommended Fixes
 
1. Update graph_algorithms.py to retain the branch sets and contraction choices, and return a contracted K₅ representation for display.
2. Update the knotted search and visualization to use the contracted embedding and test its resulting cycles for knots. Invalidate existing cached K₅ results, which contain only original edges.

The searches on the loaded graph returned no results during the debugging session, so the knot-loss behavior was identified from the code rather than reproduced on that graph.I’ll trace the graph representation, rendering and knot-cache paths first, so the contracted K₅ and its knot classification use the same embedding.

I couldn’t safely implement this without changing how spatial edges are represented and analyzed. The current finder discards the contraction choices, while the renderer and knot tools assume every edge is a straight segment between graph nodes. Preserving curved paths requires both a contraction witness and a shared polyline embedding across rendering, knot analysis, export, and caching.


I’ll keep the existing minor-model searches as a separate option and add a contracted representation with curved edges for display and knot analysis. The contraction will use an explicit geometric convention, since the abstract minor alone does not determine an embedding.

The new path now retains contraction witnesses and checks knots on the resulting polygonal embedding; the legacy model search remains selectable. I’m wiring the remaining views and checking that invalid contractions are reported rather than classified as knots.

The contracted view now keeps five visible vertices and uses the same edge paths for HOMFLY and export. I’m checking both a knot that survives contraction and one that disappears, along with the legacy selector.

Implemented contracted K₅ views with five degree-four vertices. Knot detection now analyzes the contracted embedding, including its curved edge paths. The previous searches remain available via **Original minor model (legacy)**.

The contracted knotted search examines up to 1,000 candidate models and one contraction per model, so no result does not rule out other knotted contractions.



Yes. The useful thing to precompute is not the combinations themselves—they’re cheap to generate—but the **validated K₅ models and their contraction witnesses**. We can then analyze their contracted embeddings for knots ahead of time and cache those results for the app.

The precomputation would still have to process the 906,192 combinations once, potentially taking a long time. It should run as a resumable background job, save progress and partial results, and key the cache by graph structure, coordinates, and algorithm version so changes don’t reuse stale results.