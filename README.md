Test Topoly with graph libraries to find K_3,3 or K_5 subgraphs


npm install cytoscape-cola
## Context path

The app is served at `/spatialgraph/` by default. Override with the `CONTEXT_PATH` env var (e.g. `CONTEXT_PATH=myapp python dash_graphs.py`); set it to an empty string to serve at `/`.

## Running with mod_wsgi-express

`wsgi.py` exposes the `application` object. Start it with the Dash prefix handling the context path (do not also pass `--mount-point`):

    mod_wsgi-express start-server wsgi.py --port 8014

The app is then available at `http://host:8014/spatialgraph/`.


## Knotted loops vs "Run HOMFLY" button/"Test knot (HOMFLY 500)" checkbox

Knotted loops are detected on the whole loaded graph, that may be the simplified version selected in the "Simplification" dropdown. The result appears in the "Knotted loops" section of the right panel.
Knotted loops are detected automatically when the graph is loaded or changed, and the result appears in the "Knotted loops" section of the right panel.

"Run HOMFLY" vs "Test knot (HOMFLY 500)": both run the same 500-try HOMFLY test on the currently shown obstruction subgraph, and the result appears in the same place.
- "Test knot" checkbox: runs automatically whenever the shown subgraph changes. That covers switching mode, moving to the previous or next subgraph, changing simplification, and loading a graph.
- "Run HOMFLY" button: runs it once on demand when the checkbox is off. The result then clears on the next change.

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