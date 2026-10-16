
If a knot is found using the "find knotted loops" option, highlight it in the "Knotted loops" view using a different color. Cache these results in a file since they take long to compute

## Objective
- Add file-based caching for slow “find knotted loops” computations in the spatial_graphs Dash app.
- Highlight any knot found via the “find knotted loops” option in the “Knotted loops” view using a different color.

## Important Details
- App is a Python Dash application, main entrypoint appears to be `/home/pol/dev/ilbsm/spatial_graphs/dash_graphs.py`.
- README states the app is served at `/spatialgraph/` by default and can be overridden with `CONTEXT_PATH`.
- `wsgi.py` exposes `application` for `mod_wsgi-express`, e.g. `mod_wsgi-express start-server wsgi.py --port 8014`.
- Existing code uses `dash`, `dash_cytoscape`, `plotly`, `networkx`, `numpy`, `topoly`, and `ogdf_python`.
- Caching is required because knot/loop computation is slow.
- Highlighting should occur in the “Knotted loops” view, not merely the input graph view.

## Work State
### Completed
- Read `/home/pol/dev/ilbsm/spatial_graphs/README.md`.
- Listed repository tree and identified main Python files.
- Started reading `/home/pol/dev/ilbsm/spatial_graphs/dash_graphs.py`, but the visible excerpt was truncated before the relevant UI/callback code.

### Active
- Locating the “find knotted loops” option in `dash_graphs.py`.
- Locating the “Knotted loops” view/callback that renders loops.
- Determining where computed knot/loop results are stored or passed between callbacks.
- Designing a file cache key and highlight mechanism for found knots.

### Blocked
- None.

## Next Move
1. Search `/home/pol/dev/ilbsm/spatial_graphs/dash_graphs.py` for `knotted`, `knot`, `loop`, `find`, and related callback IDs.
2. Identify the exact data structure returned by the “find knotted loops” computation and the layout/classes used by the “Knotted loops” view.
3. Add file-based caching around the slow computation, using a cache key derived from input graph/data/parameters.
4. Apply a distinct color/class to highlighted knot edges or nodes in the “Knotted loops” view.

## Relevant Files
- `/home/pol/dev/ilbsm/spatial_graphs/dash_graphs.py`: main Dash app containing UI, callbacks, graph generation, and likely knot-finding logic.
- `/home/pol/dev/ilbsm/spatial_graphs/wsgi.py`: WSGI entrypoint for `mod_wsgi-express`; may need unchanged unless deployment changes.
- `/home/pol/dev/ilbsm/spatial_graphs/README.md`: context path and run instructions.
- `/home/pol/dev/ilbsm/spatial_graphs/data/`: graph/PDB/JSON input data possibly used by the app and relevant to cache key design.
- `/home/pol/dev/ilbsm/spatial_graphs/other/`: auxiliary Dash scripts that may contain related examples or prior implementations.

## Objective
- Add file-based caching for the slow “find knotted loops” / knot-testing computation in the spatial_graphs Dash app.
- Highlight any knot found via that option in the “Knotted loops” view with a distinct color.

## Important Details
- Main app file: `/home/pol/dev/ilbsm/spatial_graphs/dash_graphs.py`.
- App is served at `/spatialgraph/` by default, overridable with `CONTEXT_PATH`; `wsgi.py` is the WSGI entrypoint for `mod_wsgi-express`.
- Existing dependencies include `dash`, `dash_cytoscape`, `plotly`, `networkx`, `numpy`, `topoly`, and `ogdf_python`.
- Knot logic is Topoly-based:
  - `_evaluate_subgraph_knot_worker(arcs_4d, node_coords_list, tries=500)` at line 469.
  - It creates `tp.Graph(arcs_4d)` and calls `find_loops(output_type=OutputType.XYZ, arc_bridges=0)`.
  - If no loops are found and node coordinates exist, it falls back to `tp.homfly(node_coords_list, tries=tries, run_parallel=False)`.
  - Returns `(knot_type, probability)`; unknot is `'0_1'`.
- `test_obstruction_knot_homfly(subgraph, node_pos_3d=None, tries=500)` at line 513 returns `(knot_type, probability)`.
- Existing process/timeout machinery:
  - `HOMFLY_TIMEOUT = 120`
  - `_HOMFLY_LOCK = threading.Lock()`
  - Uses a forked multiprocessing `Pipe` with `_homfly_child`.
  - Timeouts or crashes return `(None, 0.0)`.
- Existing in-memory caching already exists:
  - Callback `update_homfly_knot(run_clicks, homfly_test_val, idx, _version, mode, ...)` at line 991.
  - Uses `state['homfly_cache'][cache_key]`.
  - Calls `test_obstruction_knot_homfly(target_g, state.get('node_pos_3d'), tries=500)`.
  - Returns text strings such as `knot_type: 0_1 (unknot), probability: ...`.
- UI context:
  - Obstruction mode radio options: `original`, `highlight`, `obstruction`, `multi`.
  - Checklists include “Show selected obstruction only” and “Simplify subgraph”.
  - `simplify-method` options include `kmt`, `reidemeister`, `easy`.
  - Line 800 contains the knot-test checklist option label: `Test knot (HOMFLY 500)`.
- Graph construction around lines 1138–1178 builds `tp.Graph`, handles bridges (`disulfide`, `covalent`, `ion`, `bridge`), side-chain edges, and arcs.
- The “Knotted loops” view itself has not yet been located in the visible code.

## Work State
### Completed
- Read `/home/pol/dev/ilbsm/spatial_graphs/README.md` and identified deployment/context-path details.
- Listed the repository and identified the main Python files.
- Searched `/home/pol/dev/ilbsm/spatial_graphs/dash_graphs.py` for knot/loop code.
- Identified the core knot-testing worker, HOMFLY timeout wrapper, UI option, and existing in-memory `state['homfly_cache']`.
- Read the relevant portions of `dash_graphs.py` around:
  - lines 440–560
  - lines 580–760
  - lines 760–880
  - lines 880–1140
  - lines 1138 onward

### Active
- Read the missing sections around `test_obstruction_knot_homfly`, `_homfly_child`, and the full `update_homfly_knot` callback, especially:
  - how `cache_key` is built
  - what `target_g` is
  - what the callback outputs are
  - where `state['node_pos_3d']` and `state['homfly_cache']` are initialized
- Locate the “Knotted loops” view/layout/callback and the exact Cytoscape elements/stylesheet it uses.
- Design a file-based cache key from the input graph/data and relevant parameters, then integrate it with the existing in-memory HOMFLY cache.
- Implement a distinct highlight color/class for a found knot in the “Knotted loops” view.

### Blocked
- None.

## Next Move
1. Read `/home/pol/dev/ilbsm/spatial_graphs/dash_graphs.py` around lines 506–580 and 960–1080 to capture:
   - `test_obstruction_knot_homfly`
   - `_homfly_child`
   - the full `update_homfly_knot` callback
   - `cache_key` construction
   - callback outputs and related `state` keys
2. Grep/read for `Knotted loops`, loop-view IDs, and `build_elements` / stylesheet usage to find where the loop/knot view is rendered.
3. Add a file-based cache around the slow knot computation, likely wrapping `test_obstruction_knot_homfly` or the computation inside `update_homfly_knot`.
4. Modify the “Knotted loops” view elements/stylesheet so a non-`'0_1'` knot result is highlighted with a different color.

## Relevant Files
- `/home/pol/dev/ilbsm/spatial_graphs/dash_graphs.py`: main Dash app; contains knot worker, HOMFLY callback, UI controls, graph building, and likely loop-view code.
- `/home/pol/dev/ilbsm/spatial_graphs/wsgi.py`: WSGI entrypoint for `mod_wsgi-express`; likely unchanged unless deployment changes.
- `/home/pol/dev/ilbsm/spatial_graphs/README.md`: context path, run instructions, and deployment context.
- `/home/pol/dev/ilbsm/spatial_graphs/data/`: input structures/graphs likely needed for a stable cache key.
- `/home/pol/dev/ilbsm/spatial_graphs/other/`: auxiliary Dash scripts that may contain related prior implementations or examples.

## Objective
- Add persistent file-based caching for the slow HOMFLY/knotted-loop computation in the spatial_graphs Dash app.
- Highlight any found knot (non-`0_1`) in the “Knotted loops” view with a distinct color.

## Important Details
- Main app file: `/home/pol/dev/ilbsm/spatial_graphs/dash_graphs.py`.
- App is served at `/spatialgraph/` by default, overridable with `CONTEXT_PATH`; `wsgi.py` is the WSGI entrypoint for `mod_wsgi-express`.
- Existing dependencies include `dash`, `dash_cytoscape`, `plotly`, `networkx`, `numpy`, `topoly`, and `ogdf_python`.
- Knot-testing path:
  - `_evaluate_subgraph_knot_worker(arcs_4d, node_coords_list, tries=500)` around line 469 creates `tp.Graph(arcs_4d)`, calls `find_loops(output_type=OutputType.XYZ, arc_bridges=0)`, and falls back to `tp.homfly(node_coords_list, tries=tries, run_parallel=False)`.
  - It returns `(knot_type, probability)`; unknot is `'0_1'`.
  - `test_obstruction_knot_homfly(subgraph, node_pos_3d=None, tries=500)` around line 513 returns `(knot_type, probability)`.
- Existing process/timeout machinery:
  - `HOMFLY_TIMEOUT = 120`
  - `_HOMFLY_LOCK = threading.Lock()`
  - Uses a forked multiprocessing `Pipe` with `_homfly_child`.
  - Timeouts or crashes return `(None, 0.0)`.
- Existing in-memory caching:
  - Callback `update_homfly_knot(...)` around line 991 uses `state['homfly_cache']`.
  - `cache_key = (_version, 'multi'/'obs', idx, is_simplified, method)`.
  - It runs `test_obstruction_knot_homfly(target_g, state.get('node_pos_3d'), tries=500)` and writes a text result to `homfly-result`.
- UI controls:
  - `run-homfly-btn`: Run HOMFLY button.
  - `homfly-test`: checklist option labeled “Test knot (HOMFLY 500)”.
  - `homfly-result`: result display.
  - Obstruction mode radio options: `original`, `highlight`, `obstruction`, `multi`.
  - Checklists include “Show selected obstruction only” and “Simplify subgraph”.
  - `simplify-method` options include `kmt`, `reidemeister`, `easy`.
- Views:
  - 2D graph uses Cytoscape with `id="graph"`.
  - 3D view uses Plotly with `id="graph-3d"`.
  - No explicit “Knotted loops” view/layout has been located yet; need to determine whether the user means the obstruction/multi view or requires a new loop/knot view.
- Graph construction around lines 1138–1178 builds `tp.Graph`, handles bridge types (`disulfide`, `covalent`, `ion`, `bridge`), side-chain edges, and arcs.

## Work State
### Completed
- Read `/home/pol/dev/ilbsm/spatial_graphs/README.md` and identified deployment/context-path details.
- Listed the repository and identified the main Python files.
- Searched `/home/pol/dev/ilbsm/spatial_graphs/dash_graphs.py` for knot/loop/HOMFLY code.
- Identified the core knot-testing worker, HOMFLY timeout wrapper, UI option, existing in-memory `state['homfly_cache']`, and cache key structure.
- Read relevant portions of `dash_graphs.py`:
  - lines 1–300
  - lines 300–440
  - lines 440–560
  - lines 580–760
  - lines 760–880
  - lines 880–1140
  - lines 1139 onward
- Confirmed exact UI identifiers: `run-homfly-btn`, `homfly-test`, `homfly-result`, `update_homfly_knot`, and obstruction view IDs.

### Active
- Locate or define the “Knotted loops” view/layout/callback and the exact Cytoscape/Plotly elements/stylesheet used for loop/knot highlighting.
- Read remaining sections around `test_obstruction_knot_homfly`, `_homfly_child`, and the full `update_homfly_knot` callback to confirm `target_g`, callback outputs, state initialization, and exact cache flow.
- Design a stable file-based cache key from input graph/data and relevant parameters, likely including version, mode, obstruction index, simplification method, and graph/coordinate hash.
- Implement file-based caching around the slow computation, integrated with the existing in-memory `state['homfly_cache']`.
- Add a distinct highlight color/class for a found knot, preferably when `knot_type != '0_1'`.

### Blocked
- None.

## Next Move
1. Grep/read `/home/pol/dev/ilbsm/spatial_graphs/dash_graphs.py` for `Knotted`, `knotted`, `loop`, `graph`, `graph-3d`, `build_elements`, and stylesheet/class usage, and read lines 506–580 and 960–1080 to confirm the HOMFLY worker, child process, full `update_homfly_knot` callback, and cache flow.
2. Implement the file-based cache and a distinct knot highlight once the loop/knot rendering path is identified.

## Relevant Files
- `/home/pol/dev/ilbsm/spatial_graphs/dash_graphs.py`: main Dash app; contains knot worker, HOMFLY callback, UI controls, graph building, and likely loop-view code.
- `/home/pol/dev/ilbsm/spatial_graphs/wsgi.py`: WSGI entrypoint for `mod_wsgi-express`; likely unchanged unless deployment changes.
- `/home/pol/dev/ilbsm/spatial_graphs/README.md`: context path, run instructions, and deployment context.
- `/home/pol/dev/ilbsm/spatial_graphs/data/`: input structures/graphs likely needed for a stable cache key.
- `/home/pol/dev/ilbsm/spatial_graphs/other/`: auxiliary Dash scripts that may contain related prior implementations or examples.

## Objective
- Add persistent file-based caching for the slow HOMFLY/knotted-loop computation in the spatial_graphs Dash app.
- Highlight any found knot, i.e. `knot_type != '0_1'`, in the “Knotted loops” view with a distinct color.

## Important Details
- Main app file: `/home/pol/dev/ilbsm/spatial_graphs/dash_graphs.py`.
- App is served at `/spatialgraph/` by default, overridable with `CONTEXT_PATH`; `wsgi.py` is the WSGI entrypoint for `mod_wsgi-express`.
- Existing dependencies include `dash`, `dash_cytoscape`, `plotly`, `networkx`, `numpy`, `topoly`, and `ogdf_python`.
- Confirmed imports in `dash_graphs.py` include:
  - `multiprocessing as mp`, `threading`, `os`, `io`, `logging`, `re`, `random`, `colorsys`.
  - `dash`, `dash.exceptions.PreventUpdate`, `dash_cytoscape`, `plotly.graph_objects`, `topoly`, `topoly.params.OutputType`, `topoly.params.ReduceMethod`, `ogdf_python`.
- Knot-testing path:
  - `_evaluate_subgraph_knot_worker(arcs_4d, node_coords_list, tries=500)` around line 469 creates `tp.Graph(arcs_4d)`, calls `find_loops(output_type=OutputType.XYZ, arc_bridges=0)`, and falls back to `tp.homfly(node_coords_list, tries=tries, run_parallel=False)`.
  - It returns `(knot_type, probability)`; unknot is `'0_1'`.
  - Around line 505, the worker returns `'0_1'` with `max_unknot_prob if max_unknot_prob > 0 else 1.0`.
  - `_homfly_child(conn, arcs_4d, node_coords_list, tries)` at lines 508–510 sends the worker result over `conn` and closes it.
- `test_obstruction_knot_homfly(subgraph, node_pos_3d=None, tries=500)` starts around line 513:
  - Returns `(None, 0.0)` for empty subgraphs.
  - Builds `node_coords` from subgraph node attribute `coords`, falling back to `node_pos_3d`.
  - Chooses branch nodes as nodes with `subgraph.degree(n) != 2`; if none exist but nodes exist, uses the first node.
  - Begins traversing degree-2 chains to build arcs; only partially read so far.
- Existing process/timeout machinery:
  - `HOMFLY_TIMEOUT = 120`.
  - `_HOMFLY_LOCK = threading.Lock()`.
  - Uses a forked multiprocessing `Pipe` with `_homfly_child`.
  - Timeouts or crashes return `(None, 0.0)`.
- Existing in-memory caching:
  - Callback `update_homfly_knot(...)` around line 991 uses `state['homfly_cache']`.
  - `cache_key = (_version, 'multi'/'obs', idx, is_simplified, method)`.
  - It runs `test_obstruction_knot_homfly(target_g, state.get('node_pos_3d'), tries=500)` and writes a text result to `homfly-result`.
  - Full `update_homfly_knot` body still needs to be read/confirmed.
- State/layout details newly confirmed:
  - Around lines 705–707, state initialization includes `multi_subgraphs`, `node_pos_3d`, `multi_subgraphs_simplified={}`, and `homfly_cache={}`, followed by `recompute(G)`.
  - `get_simplified_subgraph(idx, selected_graph, method='kmt')` caches simplifications in `state['multi_subgraphs_simplified']` using key `(idx, method)`.
  - Simplification uses `simplify_subgraph_topoly(selected_graph, state.get('node_pos_3d'), method=method)`.
  - `app = Dash(__name__, requests_pathname_prefix=_path_prefix(), routes_pathname_prefix=_path_prefix())`.
- Callbacks newly confirmed:
  - `update_edge_colors` around lines 887–895:
    - Outputs: `("graph", "stylesheet")`, `("edge-color-legend", "children")`.
    - Inputs: `edge-color-attr`, `graph-version` data, `rainbow-backbone`, `node-font-size`.
    - Builds stylesheet from `BASE_STYLE`, node font-size rule, `edge_color_stylesheet(g, attr)`, rainbow rules, and `OBSTRUCTION_STYLE`.
  - `update` around lines 897–910:
    - Output: `("graph", "elements")`.
    - Inputs: `mode`, `subgraph-index` data, `graph-version` data, `selected-obstruction-only`, `simplify-subgraph`, `simplify-method`.
    - Modes:
      - `original`: `build_elements(g, state['pos'])`.
      - `highlight`: `build_elements(g, state['pos'], state['obs_nodes'], state['obs_edges'], True)`.
      - `multi`: uses `state['multi_subgraphs']`; body truncated after start.
- UI controls:
  - `run-homfly-btn`: Run HOMFLY button.
  - `homfly-test`: checklist option labeled “Test knot (HOMFLY 500)”.
  - `homfly-result`: result display.
  - Obstruction mode radio options: `original`, `highlight`, `obstruction`, `multi`.
  - Checklists include “Show selected obstruction only” and “Simplify subgraph”.
  - `simplify-method` options include `kmt`, `reidemeister`, `easy`.
- Views:
  - 2D graph uses Cytoscape with `id="graph"`.
  - 3D view uses Plotly with `id="graph-3d"`.
  - No explicit “Knotted loops” view/layout has been located yet; need to determine whether the user means the obstruction/multi view or requires a new loop/knot view.
- Graph construction around lines 1138–1178 builds `tp.Graph`, handles bridge types (`disulfide`, `covalent`, `ion`, `bridge`), side-chain edges, and arcs.

## Work State
### Completed
- Read `/home/pol/dev/ilbsm/spatial_graphs/README.md` and identified deployment/context-path details.
- Listed the repository and identified the main Python files.
- Searched `/home/pol/dev/ilbsm/spatial_graphs/dash_graphs.py` for knot/loop/HOMFLY code.
- Identified the core knot-testing worker, HOMFLY timeout wrapper, UI option, existing in-memory `state['homfly_cache']`, and cache key structure.
- Read relevant portions of `dash_graphs.py`:
  - lines 1–300
  - lines 300–440
  - lines 440–560
  - lines 580–760
  - lines 760–880
  - lines 880–1140
  - lines 1139 onward
  - lines 1–53
  - lines 505–704
  - lines 705–739
  - lines 884–910
- Confirmed exact UI identifiers: `run-homfly-btn`, `homfly-test`, `homfly-result`, `update_homfly_knot`, and obstruction view IDs.
- Confirmed `_homfly_child` behavior and the beginning of `test_obstruction_knot_homfly`.
- Confirmed state includes `multi_subgraphs_simplified` and `homfly_cache`, and that simplified subgraphs are cached by `(idx, method)`.
- Confirmed `update_edge_colors` and `update` callback signatures and the beginning of their logic.
- No code edits have been made yet.

### Active
- Read the remainder of `test_obstruction_knot_homfly`, especially around lines 548–705, to confirm how arcs and coordinates are passed to the HOMFLY worker.
- Read the rest of the `update` callback, especially after the `multi` branch, to understand how obstruction/multi subgraphs and simplification affect rendered elements.
- Read the full `update_homfly_knot` callback, especially around lines 960–1080 or 991 onward, to confirm `target_g`, outputs, cache reads/writes, and result formatting.
- Locate or define the “Knotted loops” view/layout/callback and the exact Cytoscape/Plotly elements/stylesheet used for loop/knot highlighting.
- Design a stable file-based cache key from input graph/data and relevant parameters, likely including version, mode, obstruction index, simplification method, and graph/coordinate hash.
- Implement file-based caching around the slow computation, integrated with the existing in-memory `state['homfly_cache']`.
- Add a distinct highlight color/class for a found knot, preferably when `knot_type != '0_1'`.

### Blocked
- None.

## Next Move
1. Read `/home/pol/dev/ilbsm/spatial_graphs/dash_graphs.py` around lines 548–705 and 910–1214, and grep for `Knotted`, `knotted`, `loop`, `homfly`, `OBSTRUCTION_STYLE`, `classes`, and `stylesheet` to locate the full HOMFLY callback and any loop/knot rendering path.
2. Once the rendering path is identified, implement a persistent cache around `test_obstruction_knot_homfly` or `_evaluate_subgraph_knot_worker` and add a Cytoscape class/stylesheet rule for `knot_type != '0_1'`.

## Relevant Files
- `/home/pol/dev/ilbsm/spatial_graphs/dash_graphs.py`: main Dash app; contains knot worker, HOMFLY callback, UI controls, graph building, state caches, and likely loop-view code.
- `/home/pol/dev/ilbsm/spatial_graphs/wsgi.py`: WSGI entrypoint for `mod_wsgi-express`; likely unchanged unless deployment changes.
- `/home/pol/dev/ilbsm/spatial_graphs/README.md`: context path, run instructions, and deployment context.
- `/home/pol/dev/ilbsm/spatial_graphs/data/`: input structures/graphs likely needed for a stable cache key.
- `/home/pol/dev/ilbsm/spatial_graphs/other/`: auxiliary Dash scripts that may contain related prior implementations or examples.

## Objective
- Add persistent file-based caching for the slow HOMFLY/knotted-loop computation in the spatial_graphs Dash app.
- Highlight any found knot, i.e. `knot_type != '0_1'`, in the “Knotted loops” view with a distinct color.

## Important Details
- Main app file: `/home/pol/dev/ilbsm/spatial_graphs/dash_graphs.py`.
- App is served at `/spatialgraph/` by default, overridable with `CONTEXT_PATH`; `wsgi.py` is the WSGI entrypoint for `mod_wsgi-express`.
- Existing dependencies include `dash`, `dash_cytoscape`, `plotly`, `networkx`, `numpy`, `topoly`, and `ogdf_python`.
- Confirmed imports in `dash_graphs.py` include:
  - `multiprocessing as mp`, `threading`, `os`, `io`, `logging`, `re`, `random`, `colorsys`.
  - `dash`, `dash.exceptions.PreventUpdate`, `dash_cytoscape`, `plotly.graph_objects`, `topoly`, `topoly.params.OutputType`, `topoly.params.ReduceMethod`, `ogdf_python`.
- Knot-testing path:
  - `_evaluate_subgraph_knot_worker(arcs_4d, node_coords_list, tries=500)` around line 469 creates `tp.Graph(arcs_4d)`, calls `find_loops(output_type=OutputType.XYZ, arc_bridges=0)`, and falls back to `tp.homfly(node_coords_list, tries=tries, run_parallel=False)`.
  - It returns `(knot_type, probability)`; unknot is `'0_1'`.
  - Around line 505, the worker returns `'0_1'` with `max_unknot_prob if max_unknot_prob > 0 else 1.0`.
  - `_homfly_child(conn, arcs_4d, node_coords_list, tries)` at lines 508–510 sends the worker result over `conn` and closes it.
  - `test_obstruction_knot_homfly(subgraph, node_pos_3d=None, tries=500)` starts around line 513:
    - Returns `(None, 0.0)` for empty subgraphs.
    - Builds `node_coords` from subgraph node attribute `coords`, falling back to `node_pos_3d`.
    - Chooses branch nodes as nodes with `subgraph.degree(n) != 2`; if none exist but nodes exist, uses the first node.
    - Traverses degree-2 chains to build arcs.
    - Newly confirmed around lines 548–576:
      - Remaining unvisited edges are also traversed into `arcs`.
      - Builds `node_to_id = {n: i for i, n in enumerate(subgraph.nodes())}`.
      - Builds `arcs_4d` as lists of `[node_id, float(coord[0]), float(coord[1]), float(coord[2])]`.
      - Builds `node_coords_list = [node_coords[n] for n in subgraph.nodes() if n in node_coords]`.
- Existing process/timeout machinery:
  - `HOMFLY_TIMEOUT = 120` at line 465.
  - `_HOMFLY_LOCK = threading.Lock()` at line 466.
  - Newly confirmed lines 580–592:
    - Comment states `liblmpoly` can `abort()` or hang on large inputs and must not take down the app.
    - Uses `with _HOMFLY_LOCK:`.
    - Uses `ctx = mp.get_context('fork')`.
    - Uses `recv, send = ctx.Pipe(duplex=False)`.
    - Starts `proc = ctx.Process(target=_homfly_child, args=(send, arcs_4d, node_coords_list, tries), daemon=True)`.
    - Calls `proc.start()`, `send.close()`.
    - If `recv.poll(HOMFLY_TIMEOUT)` succeeds, returns `recv.recv()`.
    - On `EOFError`, logs `"HOMFLY worker crashed (exit code {proc.exitcode})"` and returns `(None, 0.0)`.
- Existing in-memory caching:
  - Callback `update_homfly_knot(...)` around line 991 uses `state['homfly_cache']`.
  - `cache_key = (_version, 'multi'/'obs', idx, is_simplified, method)`.
  - It runs `test_obstruction_knot_homfly(target_g, state.get('node_pos_3d'), tries=500)` and writes a text result to `homfly-result`.
  - Full `update_homfly_knot` body still needs to be read/confirmed.
- State/layout details:
  - Around lines 705–707, state initialization includes `multi_subgraphs`, `node_pos_3d`, `multi_subgraphs_simplified={}`, and `homfly_cache={}`, followed by `recompute(G)`.
  - `get_simplified_subgraph(idx, selected_graph, method='kmt')` caches simplifications in `state['multi_subgraphs_simplified']` using key `(idx, method)`.
  - Simplification uses `simplify_subgraph_topoly(selected_graph, state.get('node_pos_3d'), method=method)`.
  - `app = Dash(__name__, requests_pathname_prefix=_path_prefix(), routes_pathname_prefix=_path_prefix())`.
- Callbacks confirmed:
  - `update_edge_colors` around lines 887–895:
    - Outputs: `("graph", "stylesheet")`, `("edge-color-legend", "children")`.
    - Inputs: `edge-color-attr`, `graph-version` data, `rainbow-backbone`, `node-font-size`.
    - Builds stylesheet from `BASE_STYLE`, node font-size rule, `edge_color_stylesheet(g, attr)`, rainbow rules, and `OBSTRUCTION_STYLE`.
  - `update` around lines 897–921:
    - Output: `("graph", "elements")`.
    - Inputs: `mode`, `subgraph-index` data, `graph-version` data, `selected-obstruction-only`, `simplify-subgraph`, `simplify-method`.
    - Modes:
      - `original`: `build_elements(g, state['pos'])`.
      - `highlight`: `build_elements(g, state['pos'], state['obs_nodes'], state['obs_edges'], True)`.
      - `multi`:
        - `sub = multi_subgraphs[idx]`
        - `sub_nodes = set(sub.nodes())`
        - `sub_edges = {frozenset(e) for e in sub.edges()}`
        - If `"on" in (selected_obstruction_only or [])`:
          - `selected_graph = g.edge_subgraph(sub.edges())`
          - If `"on" in (simplify_subgraph or [])`:
            - `simp_g = get_simplified_subgraph(idx, selected_graph, method=simplify_method or "kmt")`
            - Returns `build_elements(simp_g, state['pos'], set(simp_g.nodes()), {frozenset(e) for e in simp_g.edges()}, True)`
          - Else returns `build_elements(selected_graph, state['pos'], sub_nodes, sub_edges, True)`
        - Else returns `build_elements(g, state['pos'], sub_nodes, sub_edges, True)`
      - Final branch returns `build_elements(state['obs'], state['obs_pos'])`, likely for obstruction-only mode.
  - `toggle_view` lines 923–929:
    - Outputs: `("graph", "style")`, `("graph-3d", "style")`.
    - Inputs: `view-dim`, `show-grid`.
    - Toggles visibility with `container_style(True, grid)` / `container_style(False, grid)`.
  - `export_3d` lines 931–940:
    - Output: `("export-3d-download", "data")`.
    - Inputs: `export-3d-btn` `n_clicks`, `graph-3d` `figure`, `title-text` `children`.
    - `prevent_initial_call=True`.
    - If no figure, `raise PreventUpdate`.
    - Writes Plotly figure HTML to `io.StringIO()`.
    - Filename is sanitized `title_text` or `"graph"` plus `_3d.html`.
- UI controls:
  - `run-homfly-btn`: Run HOMFLY button.
  - `homfly-test`: checklist option labeled “Test knot (HOMFLY 500)”.
  - `homfly-result`: result display.
  - Obstruction mode radio options: `original`, `highlight`, `obstruction`, `multi`.
  - Checklists include “Show selected obstruction only” and “Simplify subgraph”.
  - `simplify-method` options include `kmt`, `reidemeister`, `easy`.
- Views:
  - 2D graph uses Cytoscape with `id="graph"`.
  - 3D view uses Plotly with `id="graph-3d"`.
  - No explicit “Knotted loops” view/layout has been located yet; need to determine whether the user means the obstruction/multi view or requires a new loop/knot view.
- Styling/stylesheet facts:
  - `OBSTRUCTION_STYLE` is defined at line 78.
  - `STYLE = BASE_STYLE + OBSTRUCTION_STYLE` at line 84.
  - Obstruction class is assigned at lines 51 and 57:
    - Node: `if highlight and n in obs_nodes: e["classes"] = "obstruction"`
    - Edge: `if highlight and frozenset((u, v)) in obs_edges: e["classes"] = "obstruction"`
  - `edge_color_stylesheet(graph, attr)` is at line 110.
  - A small legend Div matching edge color assignment is around line 129.
  - An edge frozenset to hex color lookup for Plotly is around line 161.
  - Grep found related `OBSTRUCTION_STYLE` examples in:
    - `/home/pol/dev/ilbsm/spatial_graphs/other/dash_generate_subgraphs_obstruction.py`
    - `/home/pol/dev/ilbsm/spatial_graphs/other/dash_generate_subgraphs.py`
    - `/home/pol/dev/ilbsm/spatial_graphs/other/dash_obstruction.py`
    - stylesheet example in `/home/pol/dev/ilbsm/spatial_graphs/other/dash_test_k33_k5.py`
- Graph construction around lines 1138–1178 builds `tp.Graph`, handles bridge types (`disulfide`, `covalent`, `ion`, `bridge`), side-chain edges, and arcs.
- No code edits have been made yet.

## Work State
### Completed
- Read `/home/pol/dev/ilbsm/spatial_graphs/README.md` and identified deployment/context-path details.
- Listed the repository and identified the main Python files.
- Searched `/home/pol/dev/ilbsm/spatial_graphs/dash_graphs.py` for knot/loop/HOMFLY code.
- Identified the core knot-testing worker, HOMFLY timeout wrapper, UI option, existing in-memory `state['homfly_cache']`, and cache key structure.
- Read relevant portions of `dash_graphs.py`:
  - lines 1–300
  - lines 300–440
  - lines 440–560
  - lines 548–760 partially, specifically through line 592
  - lines 580–760
  - lines 760–880
  - lines 880–1140
  - lines 1139 onward
  - lines 1–53
  - lines 505–704
  - lines 705–739
  - lines 884–910
  - lines 910–1214 partially, specifically through line 942
- Confirmed exact UI identifiers: `run-homfly-btn`, `homfly-test`, `homfly-result`, `update_homfly_knot`, and obstruction view IDs.
- Confirmed `_homfly_child` behavior and the beginning of `test_obstruction_knot_homfly`.
- Confirmed state includes `multi_subgraphs_simplified` and `homfly_cache`, and that simplified subgraphs are cached by `(idx, method)`.
- Confirmed `update_edge_colors`, `update`, `toggle_view`, and `export_3d` callback signatures and logic.
- Confirmed exact `arcs_4d` construction and forked child-process invocation for HOMFLY.
- Confirmed `OBSTRUCTION_STYLE`, obstruction class assignment, and related stylesheet helpers.
- No code edits have been made yet.

### Active
- Finish reading `test_obstruction_knot_homfly` after line 592, especially timeout/termination/cleanup behavior.
- Read the full `update_homfly_knot` callback, especially around lines 960–1080 or 991 onward, to confirm `target_g`, outputs, cache reads/writes, and result formatting.
- Locate or define the “Knotted loops” view/layout/callback and the exact Cytoscape/Plotly elements/stylesheet used for loop/knot highlighting.
- Design a stable file-based cache key from input graph/data and relevant parameters, likely including version, mode, obstruction index, simplification method, and graph/coordinate hash.
- Implement file-based caching around the slow computation, integrated with the existing in-memory `state['homfly_cache']`.
- Add a distinct highlight color/class for a found knot, preferably when `knot_type != '0_1'`.

### Blocked
- None.

## Next Move
1. Read `/home/pol/dev/ilbsm/spatial_graphs/dash_graphs.py` lines 593–705 to finish `test_obstruction_knot_homfly`, including timeout handling, process cleanup, and exact return paths.
2. Read `/home/pol/dev/ilbsm/spatial_graphs/dash_graphs.py` lines 940–1214 and grep for `update_homfly_knot`, `run-homfly-btn`, `homfly-test`, `homfly-result`, and `knotted` to confirm the HOMFLY callback, UI layout, and rendering path before implementing file-based caching and knot highlighting.

## Relevant Files
- `/home/pol/dev/ilbsm/spatial_graphs/dash_graphs.py`: main Dash app; contains knot worker, HOMFLY callback, UI controls, graph building, state caches, stylesheet classes, and likely loop-view code.
- `/home/pol/dev/ilbsm/spatial_graphs/wsgi.py`: WSGI entrypoint for `mod_wsgi-express`; likely unchanged unless deployment changes.
- `/home/pol/dev/ilbsm/spatial_graphs/README.md`: context path, run instructions, and deployment context.
- `/home/pol/dev/ilbsm/spatial_graphs/data/`: input structures/graphs likely needed for a stable cache key.
- `/home/pol/dev/ilbsm/spatial_graphs/other/`: auxiliary Dash scripts that may contain related prior implementations or examples, including `OBSTRUCTION_STYLE` and stylesheet patterns.

## Objective
- Add persistent file-based caching for the slow HOMFLY/knotted-loop computation in the spatial_graphs Dash app.
- Highlight a detected non-unknot knot, i.e. `knot_type != '0_1'`, in the relevant graph/obstruction view with a distinct color.

## Important Details
- Main app file: `/home/pol/dev/ilbsm/spatial_graphs/dash_graphs.py`.
- Deployment context remains relevant but is not the current edit focus: app is served under a context path, with `wsgi.py` as the WSGI entrypoint.
- No explicit “Knotted loops” view/layout has been found; proceed by treating the obstruction/multi graph view as the place to highlight the found knot.
- Existing dependencies already include `dash`, `dash_cytoscape`, `plotly`, `networkx`, `numpy`, `topoly`, and `ogdf_python`.
- Need to add imports for file caching: `hashlib` and `json`.
- Existing HOMFLY machinery:
  - `HOMFLY_TIMEOUT = 120` around line 465.
  - `_HOMFLY_LOCK = threading.Lock()` around line 466.
  - `_evaluate_subgraph_knot_worker(arcs_4d, node_coords_list, tries=500)` around line 469.
  - Worker returns `(knot_type, probability)`; unknot is `'0_1'`.
  - `test_obstruction_knot_homfly(subgraph, node_pos_3d=None, tries=500)` starts around line 513 and builds `node_coords` before constructing arcs and launching the forked child process.
- Existing in-memory HOMFLY cache:
  - `state['homfly_cache']` is initialized in `recompute(g)` around line 706.
  - `update_homfly_knot` uses `cache_key = (_version, "multi"/"obs", idx, is_simplified, method)`.
- Confirmed actual `update_homfly_knot` target/cache logic around lines 1010–1051:
  - If planar, returns `"Planar graph (no obstruction)"`.
  - `multi_subgraphs = state.get('multi_subgraphs', [])`.
  - `is_simplified = "on" in (simplify_subgraph or [])`.
  - `method = simplify_method or "kmt"`.
  - If `mode == "multi" and multi_subgraphs`:
    - `actual_idx = idx % n`
    - target is selected subgraph, optionally simplified.
    - `cache_key = (_version, "multi", actual_idx, is_simplified, method)`.
  - Else if `state.get('obs') is not None`:
    - target is `state['obs']`, optionally simplified.
    - `cache_key = (_version, "obs", 0, is_simplified, method)`.
  - Else if `multi_subgraphs`:
    - same multi target/cache behavior as above.
  - Else returns `"No obstruction subgraph found"`.
- Corrected assumption: original/highlight modes with an existing `state['obs']` use the `"obs"` branch, not the first multi subgraph, because the `elif state.get('obs') is not None` branch precedes the `elif multi_subgraphs` branch.
- `update` callback around lines 897–921:
  - Output: `("graph", "elements")`.
  - Inputs: `mode`, `subgraph-index` data, `graph-version` data, `selected-obstruction-only`, `simplify-subgraph`, `simplify-method`.
  - `original`: `build_elements(g, state['pos'])`.
  - `highlight`: `build_elements(g, state['pos'], state['obs_nodes'], state['obs_edges'], True)`.
  - `multi`: uses selected subgraph nodes/edges; if selected obstruction only and simplification enabled, uses simplified subgraph.
  - Final obstruction branch: `build_elements(state['obs'], state['obs_pos'])`.
- `update_edge_colors` around lines 887–895:
  - Outputs: `("graph", "stylesheet")` and `("edge-color-legend", "children")`.
  - Builds stylesheet from base styles, edge-color rules, rainbow rules, and `OBSTRUCTION_STYLE`.
- Styling facts:
  - `OBSTRUCTION_STYLE` defined around line 78.
  - `STYLE = BASE_STYLE + OBSTRUCTION_STYLE` around line 84.
  - `build_elements` currently assigns only `"obstruction"` class when `highlight` is true and node/edge belongs to the obstruction.
  - Need add a distinct `KNOT_STYLE`, likely after `OBSTRUCTION_STYLE`, and include it in the static stylesheet so no additional `graph.stylesheet` callback is required.
- Dash constraint: one output property can only be produced by one callback. Therefore do not add `graph.stylesheet` output to the HOMFLY callback. Instead:
  - Make `update` depend on `Input("homfly-result", "children")`.
  - Store the latest HOMFLY result in server-side state.
  - Use that state in `update` to add a `knot` class to the relevant target elements.
- Planned file-cache design:
  - Cache directory: `.homfly_cache` next to `dash_graphs.py`, e.g. `os.path.join(os.path.dirname(os.path.abspath(__file__)), ".homfly_cache")`.
  - One JSON file per content hash, e.g. `{key}.json`.
  - JSON payload: `{"knot_type": ..., "probability": ...}`.
  - Do not cache failures/timeouts where result is `(None, 0.0)`.
  - Use atomic write, e.g. temporary file then `os.replace`.
  - Cache key should be content-based and stable, likely derived from:
    - sorted subgraph node labels,
    - sorted undirected edge pairs,
    - node coordinates used by HOMFLY,
    - `tries`,
    - optionally a list/flag for missing coordinates.
  - Compute key after `node_coords` is built in `test_obstruction_knot_homfly`, before arcs/child process.
  - Check/load cache under `_HOMFLY_LOCK` to avoid duplicate long computations.
- Planned highlight design:
  - In `update_homfly_knot`, store `state['homfly_result'] = (cache_key, knot_type, probability)` on success, and `None` for no obstruction/planar/failure as appropriate.
  - In `update`, add `Input("homfly-result", "children")` solely to trigger re-render when HOMFLY result changes.
  - Recompute the same `cache_key` using the exact `update_homfly_knot` logic.
  - If stored key matches and `knot_type` is not `None`, `'0_1'`, or `'TMC'`, set knot highlight.
  - For `"obs"` key: highlight `state['obs']` nodes/edges, preferably using `state['obs_nodes']` and `state['obs_edges']`.
  - For `"multi"` key: highlight selected subgraph nodes/edges; if the current view is showing the selected obstruction only and simplification was used, highlight the simplified subgraph nodes/edges.
  - Modify `build_elements` to accept optional `knot_nodes`, `knot_edges`, and `knot` flag, and combine classes such as `"obstruction knot"`.

## Work State
### Completed
- Read and confirmed deployment/context-path context from `README.md` and repository layout.
- Identified main file: `/home/pol/dev/ilbsm/spatial_graphs/dash_graphs.py`.
- Read relevant sections of `dash_graphs.py`, including:
  - lines 1–130,
  - lines 300–440,
  - lines 440–560,
  - lines 455–514,
  - lines 548–760 partially,
  - lines 580–760,
  - lines 680–760,
  - lines 758–917,
  - lines 884–910,
  - lines 918–1014,
  - lines 1010–1051,
  - lines 1139 onward partially.
- Confirmed HOMFLY worker, timeout wrapper, child-process launch pattern, and existing `_HOMFLY_LOCK`.
- Confirmed `state` includes `multi_subgraphs`, `node_pos_3d`, `multi_subgraphs_simplified`, and `homfly_cache`.
- Confirmed `get_simplified_subgraph(idx, selected_graph, method='kmt')` caches simplifications by `(idx, method)`.
- Confirmed UI identifiers:
  - `run-homfly-btn`,
  - `homfly-test`,
  - `homfly-result`,
  - obstruction `mode` radio options: `original`, `highlight`, `obstruction`, `multi`,
  - `selected-obstruction-only`,
  - `simplify-subgraph`,
  - `simplify-method`.
- Confirmed `update` and `update_edge_colors` callback signatures and behavior.
- Confirmed exact `update_homfly_knot` target/cache-key logic around lines 1010–1051.
- Corrected prior assumption about mode remapping and `"obstruction"` cache label: actual code uses `"obs"` and the `state['obs']` branch before the fallback multi branch.
- Designed likely implementation approach for file caching and knot highlighting.
- No code edits have been made yet.

### Active
- Read remaining exact tail of `test_obstruction_knot_homfly` after line 592 to see timeout, termination, cleanup, and exact return paths.
- Read remaining `update_homfly_knot` body after line 1051 to confirm:
  - in-memory cache read/write,
  - call to `test_obstruction_knot_homfly`,
  - exact result strings,
  - where to store `state['homfly_result']`.
- Implement file-based caching helpers and integrate them into `test_obstruction_knot_homfly`.
- Add `KNOT_STYLE` and update stylesheet assembly.
- Extend `build_elements` to support `knot` classes.
- Modify `update` to:
  - accept `homfly-result` as an input,
  - recompute the HOMFLY cache key exactly as `update_homfly_knot` does,
  - determine target knot nodes/edges,
  - pass knot highlight information to `build_elements`.
- Modify `update_homfly_knot` to store the latest result/key in state for highlighting.
- Decide whether to also highlight knots in the 3D Plotly view; current plan is to implement the 2D Cytoscape highlight first because that is where class-based stylesheet highlighting naturally applies.

### Blocked
- None.

## Next Move
1. Read `/home/pol/dev/ilbsm/spatial_graphs/dash_graphs.py` lines 593–705 to finish confirming `test_obstruction_knot_homfly`, especially the child-process timeout/termination/cleanup and exact return points.
2. Read `/home/pol/dev/ilbsm/spatial_graphs/dash_graphs.py` lines 1051–1120 to finish confirming `update_homfly_knot`, especially in-memory cache handling, result formatting, and where to store `state['homfly_result']`.

## Relevant Files
- `/home/pol/dev/ilbsm/spatial_graphs/dash_graphs.py`: main Dash app; contains HOMFLY worker, `test_obstruction_knot_homfly`, `update_homfly_knot`, `update`, `update_edge_colors`, `build_elements`, state caches, UI controls, and stylesheet classes.
- `/home/pol/dev/ilbsm/spatial_graphs/wsgi.py`: WSGI entrypoint; likely unchanged unless deployment behavior changes.
- `/home/pol/dev/ilbsm/spatial_graphs/README.md`: context path, run instructions, and deployment context.
- `/home/pol/dev/ilbsm/spatial_graphs/data/`: input structures/graphs that may affect cache-key stability.
- `/home/pol/dev/ilbsm/spatial_graphs/other/`: auxiliary Dash scripts with related prior implementations and stylesheet examples, including `OBSTRUCTION_STYLE` patterns.