Test Topoly with graph libraries to find K_3,3 or K_5 subgraphs


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
- "Next/Prev" steps through the results.
- "Knot within" looks for knotted loops inside the shown K_3,3 / K_5 minor and highlights one in orange with its knot type and handedness (e.g. +3_1 vs -3_1). "Next knot" / "Prev knot" step through them.
- "Simplify" shows the simplified subgraph (method selectable); "Knot within" then works on the simplified subgraph.

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
