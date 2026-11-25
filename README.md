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
- "Knotted K_5 minor" classifies original cycles of K_5 minor models and excludes candidates whose contracted drawing has a conflicting cycle classification.
- "Theta curves" searches the entire loaded graph, including planar graphs, for up to 20 theta subdivisions. It finds at most one set of three internally disjoint paths per pair of branch vertices, so it is not an exhaustive enumeration of all theta curves.
- Select "Original minor model (legacy)" to use the previous K_5 searches and display the original subgraphs. The legacy knotted search reports models containing a knotted loop before contraction; that knot need not survive contraction.
- "Next/Prev" steps through the results. Theta curves can be shown alone or highlighted in the full structure, viewed in 2D or 3D, and exported like the other results.
- "Knot within" looks for knotted loops inside the shown K_3,3 / K_5 minor and highlights one in orange with its knot type and handedness (e.g. +3_1 vs -3_1). For contracted K_5 views, the label and Wirtinger presentation describe the original cycle; the highlight shows its corresponding cycle in the contracted drawing, which may have a different knot type. "Next knot" / "Prev knot" step through them.
- Knots within all K_3,3 / K_5 minors are computed in the background right after a search (starting from the shown one), so Next/Prev show results immediately once ready; the status line says while it is still searching.
- "Highlight knot in full graph" (on by default) colours the original knotted loop orange in the full graph when "Show selected obstruction only" is off. This is not applied to contracted K_5 loops, which need not be loops of the original graph; the original edges of their minor model are highlighted instead.
- "Simplify" (always KMT; also turns on "Show selected obstruction only") shows the simplified subgraph; "Knot within" then works on the simplified subgraph.

## Contracted K_5 embeddings

A contracted result has five vertices of degree four and ten edges. The search keeps the original branch sets and connecting paths. Each branch set is represented by its surviving original vertex; the endpoint of each connecting path is moved to that vertex, while intermediate points retain their coordinates. These points are bends of an edge, not additional K_5 vertices. The same polygonal paths are used for 2D and 3D views, knot tests, and the exported graph. Exported nodes include their `branch_set`, and edges include their intermediate `points`.

In the Advanced panel, "Highlight obstruction" shows the full structure and highlights the selected contracted K_5 result's original branch-set and connecting edges, before contraction. Next/Prev selects which result to highlight; the export preserves those highlighted source edges.

This endpoint-replacement convention specifies one spatial embedding; it is not a canonical embedding of an abstract minor and can change knot types or create crossings during the move. The final embedding is checked for zero-length and intersecting segments; an invalid result is reported as an error instead of being classified. If source coordinates are unavailable, the existing 3D spring-layout fallback is used, so its knot results describe that generated layout, not a measured structure.

The knotted search considers up to 1,000 candidate models and one contraction witness per model. It tests all 37 simple K_5 cycles in the resulting drawing and their corresponding original cycles using closed-loop HOMFLY. A candidate is retained only if an original cycle is knotted and no cycle has a conflicting original-versus-contracted classification. On other contracted views, "Knot within" reports original-cycle classifications, identifies the drawn cycle's label and warns about disagreements or undetermined handedness. A drawn cycle can differ from its original even though the original label is shown. Matching HOMFLY labels do not prove that the contraction preserved the knot or that the curves are ambient isotopic. The additional original-cycle tests increase computation time.

No result does **not** prove that no other contraction or model is knotted. Search deadlines are checked between candidates; an individual HOMFLY analysis may take longer. A timeout or inconclusive HOMFLY result for either cycle is reported as an error rather than an unknot. Contracted results use a separate cache version from legacy results; older contracted search and precomputation caches are not reused.

## Knotted loops vs "Run HOMFLY" button

Knotted loops are detected on the whole loaded graph, that may be the simplified version selected in the "Simplification" dropdown. The result appears in the "Knotted loops" section of the right panel.
Knotted loops are detected automatically when the graph is loaded or changed, and the result appears in the "Knotted loops" section of the right panel.

"Run HOMFLY" (in the "Advanced" section) runs a 500-try HOMFLY test once, on demand, on the currently shown obstruction subgraph. The result clears on the next change.
For contracted K_5 embeddings it instead reports the first knotted original cycle, the corresponding drawn cycle's label, and any classification disagreement across the cycles; if no original cycle is knotted, it reports an unknot with any disagreement warning.

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
The controls resize to leave space for the graph; on smaller screens or when results are long, scroll inside the relevant panel to reach all its controls and output.

## Knot cache

Under each shown knotted loop (whole-graph search and "Knot within") a collapsible "Wirtinger presentation" gives the loop's Gauss code (+ over, - under) and the presentation of its knot group. It is computed on the fly by `wirtinger.py`: the loop's 3D polygon is projected along the generic direction with the fewest crossings, arcs are cut at under-passes, and each crossing gives a relation `x_o x_in x_o^{-1} x_out^{-1} = 1` (negative crossing) or `x_o^{-1} x_in x_o x_out^{-1} = 1` (positive). The panel shows two versions: the convention of the external Gauss-code tool (projection along z, higher z over, Reidemeister I kinks removed, crossing numbers keep gaps, signs ignored; reproduces the reports in `GaussCode/` exactly when the loop starts at the same node), and a signed version from the best projection, which is the correct group. Presentations are not minimal and have one redundant relation. `python compare_gausscode.py` compares the cycles and these presentations with the external reports (`comparison_report.md`).

The comparison also reads `*_simple_cycles_with_ext_gauss_report.txt` files, reproducing their signed extended codes and presentations. If no whole-graph knot cache exists, cycles are enumerated directly and HOMFLY classifications are reported as unavailable. Use `-o` to select the output path.

Knot results are cached in `knot_cache/<pdbid>/` as `<pdbid>_<chain>_<source>_<within>_<subgraph index>_<nodes>n_<hash>.json`. Each file holds the parameters, the nodes of the analyzed graph, the knotted loops (`loops`) and every analyzed loop with its HOMFLY result (`loops_analyzed`), including the unknotted ones.

`python precompute_cache.py [PDBID[CHAIN] ...] [--methods k33 k5 k33knot k5knot k5contracted k5knotcontracted] [--no-subgraphs] [-j JOBS]` fills this cache for all structures with simplified files (or the given ones). `k5` and `k5knot` retain the legacy model searches; the `contracted` methods use the new embeddings. Already cached results are reused, so it can be restarted.

To precompute the contracted knotted search for one structure without the 120-second interactive limit, run `python precompute_cache.py 1A8E --methods k5knotcontracted --no-subgraphs -j 1`. It records the enumeration position, deduplicated candidates, validated K_5 models and contraction witnesses, and knotted results in a SQLite file under `knot_cache/`. Interrupting and rerunning the command resumes from the last checkpoint. The app uses the results once the job completes, including an empty result; an incomplete job is not presented as a completed search. Cache keys include graph nodes, edges, 3D coordinates and the precomputation version. Only one precomputation for a particular graph can write at a time.

This precomputes the same bounded search—up to 1,000 candidate models and one contraction per model—not every possible contraction. It can take substantial time and disk space. Progress is printed while enumerating; model analyses are checkpointed individually, and other combinations at least every 256 attempts.

## Structure reports

Precomputation also creates a JSON report and a PDF report for each simplified structure and chain. Use **Report JSON** or **Report PDF** in the Data panel to download the latest matching report. Reports are available only for the same graph geometry, topology, chain and input settings used by precomputation; Topoly and merged-residue inputs do not currently have reports.

Run `python precompute_cache.py 1AOZ -j 2` to precompute all report families, or select families with `--methods`, for example `python precompute_cache.py 1AOZ --methods theta k33knot -j 2`. The whole-graph knot search is also run. Results from separate runs are combined. Each completed search is published as soon as it finishes; per-subgraph knot analyses are then added when finished. `--no-subgraphs` skips those analyses. Missing, in-progress, failed and skipped data are marked in the reports, and errors cause the command to fail rather than being reported as empty results.

Reports include original and simplified subgraph analyses, original-loop knot labels and probabilities, and Topoly theta classifications when available. They record the searches' limits: in particular, theta enumeration is not exhaustive and the contracted K_5 search examines at most 1,000 models. Reports do not imply that all possible minors or curves were found. Existing caches alone do not create reports; rerun precomputation to generate them. Report snapshots are stored under `knot_cache/reports/`; old snapshots remain on disk when newer reports are published.

The PDF summarizes result counts, knot and theta classifications, analysis status and search limits. For each family and view, knot types count analyzed subgraphs containing that type; one subgraph can contain several types. Contracted knotted K_5 results also show original-cycle types found during the search, even if subgraph analyses were skipped. Full graph and per-result data remain in the JSON report. To update PDFs generated by an older version without rerunning the analyses, run `python precompute_cache.py 1AOZ --refresh-reports` (omit the ID to refresh all available structures).

In the 2D view edges are drawn thick (adjustable with the thickness slider) and the over/under crossing markers follow nodes when you drag them (`assets/crossings.js`); markers whose edges no longer cross are hidden.
In 2D the thickness slider also scales node circles and labels (square root of the edge factor), and the ◀ ▶ ▲ ▼ ⟲ ⟳ buttons next to "View" turn the whole graph in 15° steps (crossings are recomputed); "Reset" restores the original orientation.

"Subgraph file" (Appearance panel) downloads the currently displayed (sub)graph as JSON: parameters, nodes with coordinates, edges, highlighted edges and, when available, the matching `knot_cache` data (`loops`, `loops_analyzed`).

Long knot searches print progress to the console (loops enumerated, HOMFLY loops analyzed, K_3,3 enumeration). Loops are enumerated with `networkx.simple_cycles` (much faster than Topoly's `find_loops`). Partial results are written to `<cache file>.partial.json` every 30 s and reused after an interrupted run; the "Knotted K_3,3" search also stores its per-loop results in a `..._k33knot_...json` cache file.

## Theta curve classification

`theta_classification.py` classifies a spatial theta curve (two degree-3 nodes joined by three arcs, with 3D coordinates) by its Yamada polynomial:

```python
from theta_classification import classify_theta_curve
classify_theta_curve(subgraph, node_pos_3d, method="topoly")   # or "knotpy"
# {'method': 'knotpy', 'name': 'T3_1', 'chirality': '-', 'polynomial': '...'}
```

- `topoly` uses `topoly.yamada` directly; `knotpy` computes the Yamada polynomial from the topoly planar diagram and looks it up in knotpy's theta table (up to 5 crossings). `name` is `None` if the curve is not in the tables.
- `chirality` `+` is the curve as tabulated, `-` its mirror image; both methods agree. Needs `knotpy` (and its `tqdm`/`sympy` dependencies) for the `knotpy` method.
- In the app, use "Theta curves" in the Find panel to search and visualize results. To classify the selected curve, open "Advanced", choose topoly or knotpy, and click "Find theta curves". That action also searches and classifies theta subdivisions within other shown graphs (at most 20 per run).
- Completed theta searches, including empty results, are cached under `knot_cache/` by graph topology, search limit and cache version; current node attributes are restored when loading. Successful classifications are cached separately by curve geometry and method. Failed classifications are not cached. To precompute the same theta search used by the app, run `python precompute_cache.py 1A8E --methods theta --no-subgraphs -j 1`.
- Tests: `python -m unittest tests.test_theta_classification`.
