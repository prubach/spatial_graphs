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
- "K_3,3" finds all K_3,3 subdivisions (OGDF and SageMath results are merged and deduplicated; the finder(s) that reported each one are shown). "K_5 minor" finds original K_5 minor models by default.
- "Knotted K_3,3" lists K_3,3 subdivisions that contain a knotted loop of the whole graph (at most 100, smallest first). OGDF and SageMath report only a few subdivisions, which can all be unknotted, so these are enumerated from the knotted loops.
- "K_5 models with knotted loops" finds original K_5 minor models containing knotted loops. It does not claim that a contracted K_5 preserves those knots.
- "Knotted theta curves" searches the entire loaded graph, including planar graphs, for theta subdivisions with evidence of knotting. It runs in the background and reports when the bounded search or classification is incomplete.
- Select "Contracted K_5 (unverified topology)" for the endpoint-replacement drawing of the ordinary K_5 search. The knotted-loop model search always uses the original graph, regardless of this selector.
- "Next/Prev" steps through the results. Theta curves can be shown alone or highlighted in the full structure, viewed in 2D or 3D, and exported like the other results.
- "Knot within" looks for knotted loops inside the shown K_3,3 / K_5 minor and highlights one in orange with its knot type and handedness (e.g. +3_1 vs -3_1). For contracted K_5 views, the label and Wirtinger presentation describe the original cycle; the highlight shows its corresponding cycle in the contracted drawing, which may have a different knot type. "Next knot" / "Prev knot" step through them.
- Knots within all K_3,3 / K_5 minors are computed in the background right after a search (starting from the shown one), so Next/Prev show results immediately once ready; the status line says while it is still searching.
- "Highlight knot in full graph" (on by default) colours the original knotted loop orange in the full graph when "Show selected obstruction only" is off. This is not applied to contracted K_5 loops, which need not be loops of the original graph; the original edges of their minor model are highlighted instead.
- "Simplify" (always KMT; also turns on "Show selected obstruction only") shows the simplified subgraph; "Knot within" then works on the simplified subgraph.

## Contracted K_5 embeddings

A contracted result has five vertices of degree four and ten edges. The search keeps the original branch sets and connecting paths. Each branch set is represented by its surviving original vertex; the endpoint of each connecting path is moved to that vertex, while intermediate points retain their coordinates. These points are bends of an edge, not additional K_5 vertices. The same polygonal paths are used for 2D and 3D views, knot tests, and the exported graph. Exported nodes include their `branch_set`, and edges include their intermediate `points`.

In the Advanced panel, "Highlight obstruction" shows the full structure and highlights the selected contracted K_5 result's original branch-set and connecting edges, before contraction. Next/Prev selects which result to highlight; the export preserves those highlighted source edges.

This endpoint-replacement convention specifies one spatial embedding; it is not a canonical embedding of an abstract minor and can change knot types or create crossings during the move. The final embedding is checked for zero-length and intersecting segments; an invalid result is reported as an error instead of being classified. If source coordinates are unavailable, the existing 3D spring-layout fallback is used, so its knot results describe that generated layout, not a measured structure.

The contracted knotted K_5 search has been removed because matching HOMFLY labels do not prove that a contraction preserves the spatial graph topology. Old contracted-knotted results are no longer used or included in current reports. On contracted views, "Knot within" reports original-cycle classifications alongside the drawn cycle's label and warns about disagreements; these comparisons do not prove topology preservation.

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

`python precompute_cache.py [PDBID[CHAIN] ...] [--source simplified|topoly|both] [--methods k33 k5 k33knot k5knot k5contracted theta] [--no-subgraphs] [-j JOBS]` fills this cache for available simplified and Topoly/Internal structures (or the given ones). Both sources are selected by default; use `--source` to select one. A missing simplified input is skipped and logged. Topoly downloads missing CIF files from RCSB into `data/` and uses the app's selectable chains, author numbering and unmerged residues; if Topoly cannot load a chain, it is reported as an error while other chains continue. `k5` and `k5knot` use original models; `k5contracted` is an unverified drawing. Already cached results are reused, so it can be restarted.

## Structure reports

Precomputation also creates a JSON report and a PDF report for each available simplified and Topoly/Internal structure and chain. Interactive **Find** searches also create or update reports, including for other Topoly reductions, numbering and merged-residue settings. Later searches add their results; missing analyses remain marked as incomplete. Use **Report JSON** or **Report PDF** in the Data panel to download the latest matching report. Reports are available only for the same graph geometry, topology, chain and input settings.

Run `python precompute_cache.py 1AOZ -j 2` to precompute all report families, or select families with `--methods`, for example `python precompute_cache.py 1AOZ --methods theta k33knot -j 2`. The whole-graph knot search is also run. Results from separate runs are combined, and a later incomplete or failed run does not erase completed analyses. Each completed search is published as soon as it finishes; per-subgraph analyses are checkpointed in batches of up to 20 results. `--no-subgraphs` skips those analyses. Missing, in-progress, failed and skipped data are marked in the reports, and errors cause the command to fail rather than being reported as empty results.

The K_3,3 search uses both OGDF and SageMath. If one backend fails, results from the other are retained and the report records the limitation; the precomputation command exits with an error. An earlier complete search remains available when a later incomplete search finds no new results.

Reports include original and simplified subgraph analyses, original-loop knot labels and probabilities, and Topoly theta classifications when available. They record search limits; theta enumeration is not exhaustive. Reports do not imply that all possible minors or curves were found. Existing caches alone do not create reports; rerun precomputation to generate them. Report snapshots are stored under `knot_cache/reports/`; old snapshots remain on disk when newer reports are published.

The PDF summarizes result counts, knot and theta classifications, analysis status and search limits. Statuses use green for complete, yellow for partial or in-progress, and red for not precomputed, failed or skipped; a completed search can have zero results. For each family and view, knot types count analyzed subgraphs containing that type; one subgraph can contain several types. Full graph and per-result data remain in the JSON report. The app updates older reports when opened, excluding retired contracted-knotted results; historical snapshots remain on disk. To refresh reports in bulk without rerunning analyses, run `python precompute_cache.py 1AOZ --refresh-reports` (omit the ID to refresh all available structures, or select a source with `--source`).

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
- The Find panel searches cycle-plus-path subdivisions of the original graph, including alternative paths for the same branch vertices. It prioritizes cached knotted loops and returns curves with a nontrivial Yamada table label or a knotted constituent cycle. A trivial or unlisted Yamada label does **not** prove a curve is unknotted; such unresolved candidates are excluded and reported as a limitation.
- The search stops after 100 results, 1,000 candidates, 1,000 cycles, or 60 seconds, whichever comes first. The time limit is checked between operations, so an individual enumeration or classification can take longer. Limit and uncertainty warnings mark the report partial and make the precomputation command exit unsuccessfully; no results do not prove that no knotted theta exists.
- To classify the selected curve, open "Advanced", choose topoly or knotpy, and click "Classify selected theta". Successful classifications are cached by curve geometry and method; failed classifications are not cached. Precomputation uses the same search: `python precompute_cache.py 1A8E --methods theta --no-subgraphs -j 1`. Older unfiltered theta report sections are reset to not precomputed when opened; other sections and historical snapshots are preserved.
- Tests: `python -m unittest tests.test_theta_classification`.
