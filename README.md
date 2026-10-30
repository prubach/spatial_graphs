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
- "K_3,3" finds all K_3,3 subdivisions (OGDF and SageMath results are merged and deduplicated; the finder(s) that reported each one are shown). "K_5 minor" finds K_5 minors.
- "Knotted K_3,3" lists K_3,3 subdivisions that contain a knotted loop of the whole graph (at most 100, smallest first). OGDF and SageMath report only a few subdivisions, which can all be unknotted, so these are enumerated from the knotted loops.
- "Knotted K_5 minor" searches for K_5 minor models that contain a knotted loop of the whole graph. It searches until no more models are found or the 120-second time limit is reached; on timeout, the models found so far are returned.
- "Next/Prev" steps through the results.
- "Knot within" looks for knotted loops inside the shown K_3,3 / K_5 minor and highlights one in orange with its knot type and handedness (e.g. +3_1 vs -3_1). "Next knot" / "Prev knot" step through them.
- Knots within all K_3,3 / K_5 minors are computed in the background right after a search (starting from the shown one), so Next/Prev show results immediately once ready; the status line says while it is still searching.
- "Highlight knot in full graph" (on by default) colours the knotted loop orange in the full graph when "Show selected obstruction only" is off.
- "Simplify" (always KMT; also turns on "Show selected obstruction only") shows the simplified subgraph; "Knot within" then works on the simplified subgraph.

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

Knot results are cached in `knot_cache/<pdbid>/` as `<pdbid>_<chain>_<source>_<within>_<subgraph index>_<nodes>n_<hash>.json`. Each file holds the parameters, the nodes of the analyzed graph, the knotted loops (`loops`) and every analyzed loop with its HOMFLY result (`loops_analyzed`), including the unknotted ones.

In the 2D view edges are drawn thick (adjustable with the thickness slider) and the over/under crossing markers follow nodes when you drag them (`assets/crossings.js`); markers whose edges no longer cross are hidden.
In 2D the thickness slider also scales node circles and labels (square root of the edge factor), and the ◀ ▶ ▲ ▼ ⟲ ⟳ buttons next to "View" turn the whole graph in 15° steps (crossings are recomputed); "Reset" restores the original orientation.

"Subgraph file" (Appearance panel) downloads the currently displayed (sub)graph as JSON: parameters, nodes with coordinates, edges, highlighted edges and, when available, the matching `knot_cache` data (`loops`, `loops_analyzed`).

Long knot searches print progress to the console (loops enumerated, HOMFLY loops analyzed, K_3,3 enumeration). Loops are enumerated with `networkx.simple_cycles` (much faster than Topoly's `find_loops`). Partial results are written to `<cache file>.partial.json` every 30 s and reused after an interrupted run; the "Knotted K_3,3" search also stores its per-loop results in a `..._k33knot_...json` cache file.
