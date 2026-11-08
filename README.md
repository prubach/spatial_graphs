Test Topoly with graph libraries to find K_3,3 or K_5 subgraphs

## Code layout

- `dash_graphs.py` creates the Dash app and registers its callbacks.
- `graph_algorithms.py` contains planarity, minor/subdivision, simplification, and knot-search algorithms.
- `graph_visualization.py` converts graph data into Cytoscape and Plotly elements and styles.
- `graph_data.py` loads and converts the bundled structure data.
- `wsgi.py` exposes the app's WSGI entry point.

npm install cytoscape-cola
## Context path

The app is served at `/spatialgraph/` by default. Override with the `CONTEXT_PATH` env var (e.g. `CONTEXT_PATH=myapp python dash_graphs.py`); set it to an empty string to serve at `/`.

## Running with mod_wsgi-express

`wsgi.py` exposes the `application` object. Start it with the Dash prefix handling the context path (do not also pass `--mount-point`):

    mod_wsgi-express start-server wsgi.py --port 8014

The app is then available at `http://host:8014/spatialgraph/`.


## Finding K_3,3 and K_5 minors

After choosing a protein, the "Find" panel works as follows:
- "K_3,3" finds all K_3,3 subdivisions (OGDF and SageMath results are merged and deduplicated; the finder(s) that reported each one are shown). "K_5 minor" finds contracted K_5 embeddings by default.
- "Knotted K_3,3" lists K_3,3 subdivisions that contain a knotted loop of the whole graph (at most 100, smallest first). OGDF and SageMath report only a few subdivisions, which can all be unknotted, so these are enumerated from the knotted loops.
- "Knotted K_5 minor" tests cycles of contracted K_5 embeddings, rather than loops of their original models.
- Select "Original minor model (legacy)" to use the previous K_5 searches and display the original subgraphs. The legacy knotted search reports models containing a knotted loop before contraction; that knot need not survive contraction.
- "Next/Prev" steps through the results.
- "Knot within" looks for knotted loops inside the shown K_3,3 / K_5 minor and highlights one in orange with its knot type and handedness (e.g. +3_1 vs -3_1). "Next knot" / "Prev knot" step through them.
- Knots within all K_3,3 / K_5 minors are computed in the background right after a search (starting from the shown one), so Next/Prev show results immediately once ready; the status line says while it is still searching.
- "Highlight knot in full graph" (on by default) colours the original knotted loop orange in the full graph when "Show selected obstruction only" is off. This is not applied to contracted K_5 loops, which need not be loops of the original graph; the original edges of their minor model are highlighted instead.
- "Simplify" (always KMT; also turns on "Show selected obstruction only") shows the simplified subgraph; "Knot within" then works on the simplified subgraph.

## Contracted K_5 embeddings

A contracted result has five vertices of degree four and ten edges. The search keeps the original branch sets and connecting paths. Each branch set is represented by its surviving original vertex; the endpoint of each connecting path is moved to that vertex, while intermediate points retain their coordinates. These points are bends of an edge, not additional K_5 vertices. The same polygonal paths are used for 2D and 3D views, knot tests, and the exported graph. Exported nodes include their `branch_set`, and edges include their intermediate `points`.

This endpoint-replacement convention specifies one spatial embedding; it is not a canonical embedding of an abstract minor and can change knot types or create crossings during the move. The final embedding is checked for zero-length and intersecting segments; an invalid result is reported as an error instead of being classified. If source coordinates are unavailable, the existing 3D spring-layout fallback is used, so its knot results describe that generated layout, not a measured structure.

The knotted search considers up to 1,000 candidate models and one contraction witness per model. It tests all 37 simple K_5 cycles in the resulting embedding using closed-loop HOMFLY. Consequently, no result does **not** prove that no other contraction or model is knotted. Search deadlines are checked between candidates; an individual HOMFLY analysis may take longer. A timeout or inconclusive HOMFLY result is reported as an error rather than an unknot. Contracted results use a separate cache version from legacy results.

## Knotted loops vs "Run HOMFLY" button

Knotted loops are detected on the whole loaded graph, that may be the simplified version selected in the "Simplification" dropdown. The result appears in the "Knotted loops" section of the right panel.
Knotted loops are detected automatically when the graph is loaded or changed, and the result appears in the "Knotted loops" section of the right panel.

"Run HOMFLY" (in the "Advanced" section) runs a 500-try HOMFLY test once, on demand, on the currently shown obstruction subgraph. The result clears on the next change.

## Install Sage using MiniConda3

```aiignore

curl -L -O "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"
conda init
conda create -n sage sage python=3.13
conda activate sage
conda install --yes --file requirements.txt

pip install -r requirements.txt 


export OGDF_INSTALL_DIR="$CONDA_PREFIX"
export OGDF_PYTHON_MODE=release
export CPATH="$CONDA_PREFIX/include/ogdf-release:$CONDA_PREFIX/include${CPATH:+:$CPATH}"
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
python dash_graphs.py
```


For identified knotted loops check if those graphs are the same as one of the Kuratowski subgraphs using both OGDF and SageMath or a K_5 minor and report it in the "Knotted loops" panel.
The "Advanced" button in the "Find" panel (hidden by default) reveals the original controls: the OGDF / SageMath / K5 minor finder, the display modes (including "Knotted loops"), "Run HOMFLY", and the whole-graph "Find knotted loops" search.

## Knot cache

Under each shown knotted loop (whole-graph search and "Knot within") a collapsible "Wirtinger presentation" gives the loop's Gauss code (+ over, - under) and the presentation of its knot group. It is computed on the fly by `wirtinger.py`: the loop's 3D polygon is projected along the generic direction with the fewest crossings, arcs are cut at under-passes, and each crossing gives a relation `x_o x_in x_o^{-1} x_out^{-1} = 1` (negative crossing) or `x_o^{-1} x_in x_o x_out^{-1} = 1` (positive). The panel shows two versions: the convention of the external Gauss-code tool (projection along z, higher z over, Reidemeister I kinks removed, crossing numbers keep gaps, signs ignored; reproduces the reports in `GaussCode/` exactly when the loop starts at the same node), and a signed version from the best projection, which is the correct group. Presentations are not minimal and have one redundant relation. `python compare_gausscode.py` compares the cycles and these presentations with the external reports (`comparison_report.md`).

Knot results are cached in `knot_cache/<pdbid>/` as `<pdbid>_<chain>_<source>_<within>_<subgraph index>_<nodes>n_<hash>.json`. Each file holds the parameters, the nodes of the analyzed graph, the knotted loops (`loops`) and every analyzed loop with its HOMFLY result (`loops_analyzed`), including the unknotted ones.

`python precompute_cache.py [PDBID[CHAIN] ...] [--methods k33 k5 k33knot k5knot k5contracted k5knotcontracted] [--no-subgraphs] [-j JOBS]` fills this cache for all structures with simplified files (or the given ones). `k5` and `k5knot` retain the legacy model searches; the `contracted` methods use the new embeddings. Already cached results are reused, so it can be restarted.

To precompute the contracted knotted search for one structure without the 120-second interactive limit, run `python precompute_cache.py 1A8E --methods k5knotcontracted --no-subgraphs -j 1`. It records the enumeration position, deduplicated candidates, validated K_5 models and contraction witnesses, and knotted results in a SQLite file under `knot_cache/`. Interrupting and rerunning the command resumes from the last checkpoint. The app uses the results once the job completes, including an empty result; an incomplete job is not presented as a completed search. Cache keys include graph nodes, edges, 3D coordinates and the precomputation version. Only one precomputation for a particular graph can write at a time.

This precomputes the same bounded search—up to 1,000 candidate models and one contraction per model—not every possible contraction. It can take substantial time and disk space. Progress is printed while enumerating; model analyses are checkpointed individually, and other combinations at least every 256 attempts.

In the 2D view edges are drawn thick (adjustable with the thickness slider) and the over/under crossing markers follow nodes when you drag them (`assets/crossings.js`); markers whose edges no longer cross are hidden.
In 2D the thickness slider also scales node circles and labels (square root of the edge factor), and the ◀ ▶ ▲ ▼ ⟲ ⟳ buttons next to "View" turn the whole graph in 15° steps (crossings are recomputed); "Reset" restores the original orientation.

"Subgraph file" (Appearance panel) downloads the currently displayed (sub)graph as JSON: parameters, nodes with coordinates, edges, highlighted edges and, when available, the matching `knot_cache` data (`loops`, `loops_analyzed`).

Long knot searches print progress to the console (loops enumerated, HOMFLY loops analyzed, K_3,3 enumeration). Loops are enumerated with `networkx.simple_cycles` (much faster than Topoly's `find_loops`). Partial results are written to `<cache file>.partial.json` every 30 s and reused after an interrupted run; the "Knotted K_3,3" search also stores its per-loop results in a `..._k33knot_...json` cache file.
