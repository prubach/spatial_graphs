"""Dash application and callback wiring for spatial graph visualization."""

import io
import os
import re
import threading

import networkx as nx
import numpy as np
import plotly.graph_objects as go
import dash_cytoscape as cyto
from dash import Dash, Input, Output, State, ctx, dcc, html, no_update
from dash.exceptions import PreventUpdate

from graph_algorithms import (
    HOMFLY_TIMEOUT,
    KNOT_CACHE_DIR,
    _HOMFLY_LOCK,
    _evaluate_subgraph_knot_worker,
    _find_k5_minor,
    _find_knotted_loops,
    _find_multiple_kuratowski_subgraphs_sage,
    _homfly_call,
    _homfly_child,
    _isolated_homfly,
    _knot_cache_path,
    _log,
    _node_coords,
    _parse_nxyz_loop,
    _read_json,
    _sage_kuratowski_worker,
    _write_json,
    cached_subgraph_homfly,
    classify_homfly,
    create_graph,
    enumerate_k33_subdivisions,
    find_k33_subgraphs,
    find_k5_minors,
    find_knotted_k33_subgraphs,
    find_knotted_k5_minors,
    find_knotted_loops,
    find_multiple_kuratowski_subgraphs,
    find_multiple_kuratowski_subgraphs_ogdf,
    find_multiple_kuratowski_subgraphs_sage,
    find_obstructions,
    kuratowski_subgraph_type,
    log,
    loop_edges,
    simplify_subgraph_topoly,
    test_obstruction_knot_homfly,
)
from graph_visualization import (
    BASE_STYLE,
    CATEGORICAL_PALETTE,
    EDGE_2D_SCALE,
    EDGE_THICKNESS_VALUES,
    GRID_BACKGROUND,
    KNOT_COLOR,
    KNOT_STYLE,
    NODE_FONT_SIZES,
    OBSTRUCTION_STYLE,
    SEQUENTIAL_HIGH,
    SEQUENTIAL_LOW,
    STYLE,
    _crossing_overlay_elements,
    _hex_lerp,
    _is_numeric_attr,
    build_3d_figure,
    build_elements,
    edge_attr_keys,
    edge_color_legend,
    edge_color_map,
    edge_color_stylesheet,
    edge_thickness_stylesheet,
    get_node_positions_3d,
    node_scale_for,
    rainbow_backbone_map,
    tube_mesh,
)
from graph_data import (
    SIMPLIFIED_BOND_TYPES,
    TopolyReduce,
    TOPOLY_REDUCE_OPTIONS,
    _load_graph,
    cif_label_to_auth,
    list_data_pdbids,
    load_graph_by_id,
    merge_residue_nodes,
    read_simlified_graph_from_file,
    topoly_graph_to_networkx,
)

def create_app(G=None, title="Graph Planarity Visualization", pdbid="", is_topoly=False):
    if G is None:
        if pdbid:
            G,tit=load_graph_by_id(pdbid,is_topoly)
            title=f"{pdbid}-{tit}"
        else:
            G=create_graph()

    # Mutable server-side state so the pdbid/source-switch callback can swap in a
    # new graph without redeclaring every other callback (Dash apps here are single-user).
    state={}
    def compute_obstructions(g,pos,method,**kwargs):
        planar,obs=nx.check_planarity(g,counterexample=True)
        multi_subgraphs=[]
        if not planar:
            multi_subgraphs=find_obstructions(g,method,**kwargs)
            if method in ("sage","k5","k33","k33knot","k5knot") and multi_subgraphs:
                obs=multi_subgraphs[0]
        return dict(planar=planar,obs=obs,
                    obs_nodes=set(obs.nodes()) if not planar else set(),
                    obs_edges={frozenset(e) for e in obs.edges()} if not planar else set(),
                    obs_pos={n:pos[n] for n in obs.nodes()} if not planar else {},
                    multi_subgraphs=multi_subgraphs,multi_subgraphs_simplified={},homfly_cache={})

    def recompute(g,method="ogdf",params=None):
        node_pos_3d=get_node_positions_3d(g)
        pos={n:(coord[0],coord[1]) for n,coord in node_pos_3d.items()}
        state.update(G=g,pos=pos,node_pos_3d=node_pos_3d,knotted_loops=[],within_cache={},within_job=None,obs_method=method,graph_params=params or {},
                     **compute_obstructions(g,pos,method))
    recompute(G,params=dict(pdbid=pdbid or None,source="topoly" if is_topoly else "simplified",
                            reduce=str(TopolyReduce.INTERNAL),numbering="auth",merge_residues=False))

    def get_simplified_subgraph(idx,selected_graph,method='kmt'):
        cache_key=(idx,method)
        cached=state.get('multi_subgraphs_simplified',{}).get(cache_key)
        if cached is not None:
            return cached
        simp=simplify_subgraph_topoly(selected_graph,state.get('node_pos_3d'),method=method)
        state.setdefault('multi_subgraphs_simplified',{})[cache_key]=simp
        return simp

    def make_title(t,g):
        return f"{t} - Planar: {state['planar']}, Nodes: {g.number_of_nodes()}, Edges: {g.number_of_edges()}"

    GRAPH_BOX_STYLE={"width":"100%","height":"calc(100vh - 290px)","minHeight":"500px"}
    CONTROL_GROUP={"display":"flex","alignItems":"center","gap":"6px"}

    def container_style(hidden,grid):
        style={**GRAPH_BOX_STYLE}
        if grid:
            style.update(GRID_BACKGROUND)
        if hidden:
            style["display"]="none"
        return style

    app=Dash(__name__, requests_pathname_prefix=_path_prefix(), routes_pathname_prefix=_path_prefix())
    FONT="'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
    PANEL={"background":"#f4f7fb","border":"1px solid #d5deea","borderRadius":"10px","padding":"5px 8px",
           "display":"flex","flexDirection":"column","gap":"3px","minWidth":"0","flex":"1 1 auto"}
    PANEL_TITLE={"fontWeight":"600","fontSize":"12px","letterSpacing":"0.06em","textTransform":"uppercase",
                 "color":"#1565c0","borderBottom":"2px solid #1976d2","paddingBottom":"1px"}
    ROW={"display":"flex","alignItems":"center","gap":"4px 6px","flexWrap":"wrap"}
    LABEL={"fontSize":"12px","color":"#37474f","minWidth":"0"}
    BTN={"background":"#e3eefb","color":"#0d47a1","border":"1px solid #90b4e0","borderRadius":"6px",
         "padding":"2px 8px","fontSize":"12px","cursor":"pointer"}
    BTN_PRIMARY={**BTN,"background":"#1976d2","color":"white","border":"1px solid #1565c0","fontWeight":"600"}
    OPT={"marginRight":"8px","fontSize":"12px"}

    def panel(title,*rows,style=None):
        return html.Div([html.Div(title,style=PANEL_TITLE),*rows],style={**PANEL,**(style or {})})

    THICKNESS_VALUES=EDGE_THICKNESS_VALUES
    app.layout=html.Div([
    html.H3(id="title-text",children=make_title(title,G),
            style={"margin":"2px 0","fontSize":"16px","color":"#0d47a1","fontWeight":"600"}),
    html.Div([
        panel("Data",
        html.Div([
        dcc.Dropdown(id="pdbid-input",placeholder="PDB ID",value=pdbid or None,clearable=False,
                   options=[{"label":p,"value":p} for p in list(dict.fromkeys(list_data_pdbids()+([pdbid] if pdbid else [])))],
                   style={"width":"110px","height":"26px","minHeight":"26px"}),
        dcc.RadioItems(id="source-type",inline=True,value="topoly" if is_topoly else "simplified",
        options=[{"label":"Topoly","value":"topoly"},{"label":"Simplified","value":"simplified"}],
        labelStyle=OPT),
        ],style=ROW),
        html.Div([
        html.Label("Reduction",style=LABEL),
        dcc.Dropdown(id="topoly-reduce",clearable=False,style={"width":"110px","height":"26px","minHeight":"26px"},
        value=TopolyReduce.INTERNAL,options=TOPOLY_REDUCE_OPTIONS),
        html.Label("Numbering",style=LABEL),
        dcc.RadioItems(id="topoly-numbering",inline=True,value="auth",options=[
        {"label":"Label","value":"label"},{"label":"Auth","value":"auth"}],labelStyle=OPT),
        ],id="topoly-reduce-container",style={**ROW,"display":"flex" if is_topoly else "none"}),
        html.Div([
        dcc.Checklist(id="merge-residues",options=[{"label":"Merge residue edges","value":"on"}],value=[],labelStyle=OPT),
        html.Button("Load",id="load-btn",n_clicks=0,style=BTN_PRIMARY),
        ],style=ROW)),
        panel("Find",
        html.Div([
        html.Div([
            html.Button("K_3,3",id="find-k33-btn",n_clicks=0,style=BTN_PRIMARY),
            html.Button("K_5 minor",id="find-k5-btn",n_clicks=0,style=BTN_PRIMARY),
            html.Button("Knotted K_3,3",id="find-k33knot-btn",n_clicks=0,style=BTN_PRIMARY,
                        title="K_3,3 subdivisions containing a knotted loop (may take a while)"),
            html.Button("Knotted K_5 minor",id="find-k5knot-btn",n_clicks=0,style=BTN_PRIMARY,
                        title="K_5 minors containing a knotted loop (may take a while)"),
            dcc.Loading(html.Span(id="find-message",style={"fontSize":"12px","color":"crimson"}),type="circle"),
        ],style=ROW),
        ],style=ROW),
        html.Div([
        html.Button("< Prev",id="prev-btn",n_clicks=0,style=BTN),
        html.Button("Next >",id="next-btn",n_clicks=0,style=BTN),
        html.Span(id="subgraph-info",style={"fontSize":"12px","color":"#37474f"}),
        ],style=ROW),
        html.Div([
        html.Div([
            html.Button("Knot within",id="within-btn",n_clicks=0,style=BTN_PRIMARY),
            html.Button("< Prev knot",id="within-prev-btn",n_clicks=0,style=BTN),
            html.Button("Next knot >",id="within-next-btn",n_clicks=0,style=BTN),
            html.Span(id="within-info",style={"fontSize":"13px","fontWeight":"600","color":"#e65100"}),
        ],style=ROW),
        ],style=ROW),
        html.Div([
        html.Button("Simplify",id="simplify-btn",n_clicks=0,style=BTN),
        ],style=ROW),
        html.Div("Orange = knotted loop within the shown subgraph (sign = handedness).",
                 style={"fontSize":"12px","color":"#607d8b"}),
        html.Button("Advanced \u25b8",id="advanced-btn",n_clicks=0,style={**BTN,"alignSelf":"flex-start"}),
        html.Div([
        html.Div([
        html.Label("Finder",style=LABEL),
        dcc.RadioItems(id="obstruction-method",inline=True,value="ogdf",options=[
        {"label":"OGDF","value":"ogdf"},{"label":"SageMath","value":"sage"},{"label":"K5 minor","value":"k5"}],labelStyle=OPT),
        html.Span(id="obstruction-method-error",style={"fontSize":"13px","color":"crimson"}),
        ],style=ROW),
        dcc.RadioItems(id="mode",inline=True,value="original",options=[
        {"label":"Original","value":"original"},
        {"label":"Highlight obstruction","value":"highlight"},
        {"label":"Obstruction only","value":"obstruction"},
        {"label":"Multiple obstructions","value":"multi"},
        {"label":"Knotted loops","value":"knots"}],labelStyle=OPT),
        dcc.Checklist(id="selected-obstruction-only",
                      options=[{"label":"Show selected obstruction only","value":"on"}],
                      value=[],labelStyle=OPT),
        dcc.Checklist(id="knot-in-original",
                      options=[{"label":"Highlight knot in full graph","value":"on"}],
                      value=["on"],labelStyle=OPT),
        dcc.Checklist(id="simplify-subgraph",
                      options=[{"label":"Simplify subgraph","value":"on"}],
                      value=[],labelStyle=OPT),
        html.Div([
        html.Button("Run HOMFLY",id="run-homfly-btn",n_clicks=0,style=BTN),
        html.Button("Find knotted loops",id="find-knots-btn",n_clicks=0,style=BTN_PRIMARY),
        html.Button("< Prev",id="knot-prev-btn",n_clicks=0,style=BTN),
        html.Button("Next >",id="knot-next-btn",n_clicks=0,style=BTN),
        ],style={**ROW,"flexWrap":"nowrap"}),
        html.Span(id="homfly-result",style={"fontSize":"13px","fontWeight":"600","color":"#1565c0"}),
        html.Span(id="knot-info",style={"fontSize":"13px","color":"#37474f"}),
        ],id="advanced-container",style={"display":"none","flexDirection":"column","gap":"3px"})),
        panel("Appearance",
        html.Div([
        html.Label("View",style=LABEL),
        dcc.RadioItems(id="view-dim",inline=True,value="3d",options=[
        {"label":"2D","value":"2d"},{"label":"3D","value":"3d"}],labelStyle=OPT),
        html.Span([html.Button(t,id=i,n_clicks=0,title=h,style={**BTN,"padding":"0 6px"}) for t,i,h in [
            ("◀","rot-left","Turn left (2D)"),("▶","rot-right","Turn right (2D)"),
            ("▲","rot-up","Tilt up (2D)"),("▼","rot-down","Tilt down (2D)"),
            ("⟲","rot-ccw","Rotate counter-clockwise (2D)"),("⟳","rot-cw","Rotate clockwise (2D)"),
            ("Reset","rot-reset","Reset 2D orientation")]],style={"display":"inline-flex","gap":"2px"}),
        dcc.Checklist(id="show-grid",options=[{"label":"Show grid","value":"grid"}],value=["grid"],labelStyle=OPT),
        html.Button("3D to HTML",id="export-3d-btn",n_clicks=0,title="Export 3D view to HTML",
                    style={**BTN,"whiteSpace":"nowrap"}),
        dcc.Download(id="export-3d-download"),
        html.Button("Subgraph file",id="export-sub-btn",n_clicks=0,title="Download the displayed (sub)graph as JSON, with its knot-cache data if available",
                    style={**BTN,"whiteSpace":"nowrap"}),
        dcc.Download(id="export-sub-download"),
        ],style=ROW),
        html.Div([
        html.Label("Color edges by",style=LABEL),
        dcc.Dropdown(id="edge-color-attr",clearable=False,style={"width":"110px","height":"26px","minHeight":"26px"},
        value="type" if "type" in edge_attr_keys(G) else "none",
        options=[{"label":"None","value":"none"}]+[{"label":a,"value":a} for a in edge_attr_keys(G)]),
        dcc.Checklist(id="rainbow-backbone",options=[{"label":"Rainbow backbone","value":"on"}],value=[],labelStyle=OPT),
        ],style=ROW),
        html.Div([
        html.Label("Label font size",style=LABEL),
        dcc.Dropdown(id="node-font-size",clearable=False,style={"width":"90px","height":"26px","minHeight":"26px"},value=14,
                     options=[{"label":str(v),"value":v} for v in NODE_FONT_SIZES]),
        html.Label("Edge thickness",style=LABEL),
        html.Div(dcc.Slider(id="edge-thickness",min=0,max=len(THICKNESS_VALUES)-1,step=1,value=THICKNESS_VALUES.index(1),
                            marks={i:str(v) for i,v in enumerate(THICKNESS_VALUES)},included=False),
                 style={"width":"150px","paddingBottom":"4px"}),
        ],style=ROW)),
    ],style={"display":"flex","flexWrap":"nowrap","gap":"6px","alignItems":"stretch","marginTop":"2px"}),
    html.Div(id="edge-color-legend",style={"margin":"2px 0"}),
    dcc.Store(id="graph-version",data=0),
    dcc.Store(id="rot3d",data=[0,0,0]),
    dcc.Store(id="subgraph-index",data=0),
    dcc.Store(id="knot-index",data=0),
    dcc.Store(id="knot-version",data=0),
    dcc.Store(id="within-index",data=0),
    dcc.Store(id="within-version",data=0),
    dcc.Interval(id="within-poll",interval=1500,disabled=True),
    dcc.Interval(id="knot-poll",interval=2000,disabled=True),
    cyto.Cytoscape(id="graph",layout={"name":"preset"},stylesheet=STYLE,style=container_style(False,False)),
    dcc.Graph(id="graph-3d",style=container_style(True,False),config={"displayModeBar":False}),
    ],style={"fontFamily":FONT,"padding":"4px 10px"})

    @app.callback(Output("advanced-container","style"),Output("advanced-btn","children"),Input("advanced-btn","n_clicks"))
    def toggle_advanced(n):
        show=bool(n and n%2)
        return ({"display":"flex","flexDirection":"column","gap":"3px"} if show else {"display":"none"},
                "Advanced \u25be" if show else "Advanced \u25b8")

    @app.callback(Output("topoly-reduce-container","style"),Input("source-type","value"))
    def toggle_topoly_reduce(source_type):
        return {**CONTROL_GROUP,"display":"flex" if source_type=="topoly" else "none"}

    @app.callback(Output("title-text","children"),Output("edge-color-attr","options"),
    Output("edge-color-attr","value"),Output("mode","value"),
    Output("subgraph-index","data",allow_duplicate=True),Output("graph-version","data"),
    Input("load-btn","n_clicks"),Input("pdbid-input","value"),Input("merge-residues","value"),
    State("pdbid-input","value"),State("source-type","value"),State("topoly-reduce","value"),State("topoly-numbering","value"),
    State("graph-version","data"),State("obstruction-method","value"),
    prevent_initial_call=True)
    def load_new_graph(n_clicks,pdbid_input,merge,pdbid_value,source_type,reduce_value,numbering,version,obs_method):
        if not pdbid_value:
            raise PreventUpdate
        g,tit=load_graph_by_id(pdbid_value,source_type=="topoly",reduce_value,numbering,bool(merge))
        print(f'nodes: {sorted(g.nodes())}')
        print(f'edges: {sorted(g.edges())}')
        print('--------------------------------------------')
        recompute(g,obs_method or "ogdf",dict(pdbid=pdbid_value,source=source_type,reduce=str(reduce_value),
                                               numbering=numbering,merge_residues=bool(merge)))
        options=[{"label":"None","value":"none"}]+[{"label":a,"value":a} for a in edge_attr_keys(g)]
        return make_title(f"{pdbid_value}-{tit}",g),options,"type" if "type" in edge_attr_keys(g) else "none","original",0,(version or 0)+1

    @app.callback(Output("graph-version","data",allow_duplicate=True),Output("subgraph-index","data",allow_duplicate=True),
    Output("obstruction-method-error","children"),Output("obstruction-method","value"),
    Input("obstruction-method","value"),State("graph-version","data"),prevent_initial_call=True)
    def switch_obstruction_method(method,version):
        method=method or "ogdf"
        if method==state.get('obs_method'):
            raise PreventUpdate
        try:
            res=compute_obstructions(state['G'],state['pos'],method)
        except Exception as e:
            return no_update,no_update,f"{method} failed: {e}",state.get('obs_method','ogdf')
        state.update(res,obs_method=method)
        return (version or 0)+1,0,"",no_update

    @app.callback(Output("subgraph-index","data"),
    Input("prev-btn","n_clicks"),Input("next-btn","n_clicks"),
    State("subgraph-index","data"),prevent_initial_call=True)
    def navigate(prev_clicks,next_clicks,idx):
        n=len(state['multi_subgraphs'])
        if n==0:
            return 0
        if ctx.triggered_id=="next-btn":
            return (idx+1)%n
        return (idx-1)%n

    def knot_status(idx):
        job=state.get('knot_job')
        if job and job['running']:
            return "Searching for knotted loops in the background (HOMFLY on all loops; may take a while)..."
        if job and job.get('error'):
            return f"Search failed: {job['error']}"
        loops=state.get('knotted_loops',[])
        if not loops:
            return "No knotted loops found." if job else "Click 'Find knotted loops'."
        k=loops[idx%len(loops)]
        text=(f"{len(loops)} knotted loop(s) in the whole graph (not limited to a K_5 minor/Kuratowski subgraph) - showing {idx%len(loops)+1}: {k['knot']} "
              f"(P(knot)={k['prob']:.2f}, P(unknot)={k['unknot_prob']:.2f}, {len(k['nodes'])} nodes)")
        return [text,html.Br(),html.Span(obstruction_summary(k),style={"fontSize":"12px","color":"#1565c0"})]


    OBSTRUCTION_FINDERS=(("ogdf","OGDF"),("sage","SageMath"),("k5","K5 minor"))

    def all_obstructions(graph):
        """Obstructions of `graph` from every finder (or the error text), cached per graph object."""
        cache=state.setdefault('all_obstructions',{})
        if cache.get('graph') is not graph:
            cache.clear()
            cache['graph']=graph
            planar=nx.check_planarity(graph)[0]
            for key,_ in OBSTRUCTION_FINDERS:
                try:
                    cache[key]=[] if planar and key!="k5" else find_obstructions(graph,key)
                except Exception as e:
                    cache[key]=str(e)
        return cache

    def annotate_knotted_loops(graph,loops):
        """For each loop record, per finder, which obstruction subgraphs equal it or contain all its edges."""
        obs=all_obstructions(graph)
        for lp in loops:
            edges=loop_edges(lp['nodes'])
            res={}
            for key,_ in OBSTRUCTION_FINDERS:
                subs=obs[key]
                if isinstance(subs,str):
                    res[key]={"error":subs}
                    continue
                sub_edges=[{frozenset(e) for e in sg.edges()} for sg in subs]
                res[key]={"same":[i+1 for i,se in enumerate(sub_edges) if se==edges],
                          "inside":[i+1 for i,se in enumerate(sub_edges) if edges<se],"total":len(subs)}
            lp['obstructions']=res
        return loops

    def obstruction_summary(lp):
        res=lp.get('obstructions')
        if not res:
            return ""
        parts=[]
        for key,label in OBSTRUCTION_FINDERS:
            r=res[key]
            if "error" in r:
                parts.append(f"{label}: n/a ({r['error'][:40]})")
            elif r["same"]:
                parts.append(f"{label}: identical to #{', #'.join(map(str,r['same']))}")
            elif r["inside"]:
                parts.append(f"{label}: contained in #{', #'.join(map(str,r['inside']))} of {r['total']}")
            else:
                parts.append(f"{label}: not related ({r['total']} found)")
        return "; ".join(parts)

    def run_knot_job(job,graph,node_pos_3d,params):
        try:
            loops=find_knotted_loops(graph,node_pos_3d,tries=500,params=params)
            job['result']=annotate_knotted_loops(graph,loops)
        except Exception as e:
            job['error']=str(e)
        job['running']=False

    # The search runs in a thread and is polled, so no long-running callback blocks the
    # callbacks that depend on knot-index/knot-version (Dash holds those back while an upstream callback is pending).
    @app.callback(Output("knot-index","data"),Output("knot-version","data"),
    Output("knot-poll","disabled"),Output("knot-info","children"),
    Output("mode","value",allow_duplicate=True),
    Input("find-knots-btn","n_clicks"),Input("knot-prev-btn","n_clicks"),Input("knot-next-btn","n_clicks"),
    Input("knot-poll","n_intervals"),Input("graph-version","data"),
    State("knot-index","data"),State("knot-version","data"),
    prevent_initial_call="initial_duplicate")
    def knot_controls(find_clicks,prev_clicks,next_clicks,_poll,_gv,idx,version):
        trigger=ctx.triggered_id
        idx=idx or 0
        job=state.get('knot_job')
        if trigger is None:
            return no_update,no_update,no_update,knot_status(idx),no_update
        if trigger=="find-knots-btn":
            if job and job['running']:
                raise PreventUpdate
            job={'running':True,'graph':state['G']}
            state['knot_job']=job
            threading.Thread(target=run_knot_job,args=(job,state['G'],state.get('node_pos_3d'),dict(state.get('graph_params',{}))),daemon=True).start()
            return no_update,no_update,False,knot_status(idx),"knots"
        if trigger=="knot-poll":
            if job is None or job['running']:
                return no_update,no_update,False,no_update,no_update
            if job['graph'] is state['G'] and 'result' in job:
                state['knotted_loops']=job.pop('result')
                return 0,(version or 0)+1,True,knot_status(0),"knots"
            return no_update,no_update,True,knot_status(idx),no_update
        if trigger=="graph-version":
            if job and job['graph'] is not state['G']:
                state['knot_job']=None
            return 0,no_update,True,knot_status(0),no_update
        n=len(state.get('knotted_loops',[]))
        if n==0:
            raise PreventUpdate
        idx=(idx+1)%n if trigger=="knot-next-btn" else (idx-1)%n
        return idx,no_update,no_update,knot_status(idx),no_update

    def knotted_loop_selection(idx):
        loops=state.get('knotted_loops',[])
        if not loops:
            return None
        nodes=loops[idx%len(loops)]['nodes']
        edges=loop_edges(nodes)
        edges={e for e in edges if len(e)==2 and state['G'].has_edge(*e)}
        return set(nodes),edges

    FAMILY_LABELS={"k33":"K_3,3","k5":"K_5 minor","k33knot":"Knotted K_3,3","k5knot":"Knotted K_5 minor"}

    @app.callback(Output("subgraph-info","children"),Input("subgraph-index","data"),Input("graph-version","data"))
    def update_info(idx,_version):
        method=state.get('obs_method')
        if method not in FAMILY_LABELS:
            return "Click K_3,3, K_5 minor, Knotted K_3,3 or Knotted K_5 minor."
        subgraphs=state['multi_subgraphs']
        n=len(subgraphs)
        name=FAMILY_LABELS[method]
        if n==0:
            return f"No {name} found."
        idx=(idx or 0)%n
        sources=subgraphs[idx].graph.get('sources')
        text=f"{name} {idx+1} of {n}"
        return f"{text} (found by {' and '.join(sources)})" if sources else text

    @app.callback(Output("prev-btn","children"),Output("next-btn","children"),Input("graph-version","data"))
    def update_nav_labels(_version):
        name=FAMILY_LABELS.get(state.get('obs_method'))
        return (f"< Prev {name}",f"Next {name} >") if name else ("< Prev","Next >")

    @app.callback(Output("graph-version","data",allow_duplicate=True),Output("subgraph-index","data",allow_duplicate=True),
    Output("mode","value",allow_duplicate=True),Output("selected-obstruction-only","value",allow_duplicate=True),
    Output("find-message","children"),
    Input("find-k33-btn","n_clicks"),Input("find-k5-btn","n_clicks"),Input("find-k33knot-btn","n_clicks"),Input("find-k5knot-btn","n_clicks"),
    State("graph-version","data"),prevent_initial_call=True)
    def find_family(_k33,_k5,_k33knot,_k5knot,version):
        method={"find-k33-btn":"k33","find-k33knot-btn":"k33knot","find-k5knot-btn":"k5knot"}.get(ctx.triggered_id,"k5")
        extra=dict(node_pos_3d=state.get('node_pos_3d'),params=dict(state.get('graph_params',{}))) if method in ("k33knot","k5knot") else {}
        try:
            res=compute_obstructions(state['G'],state['pos'],method,**extra)
        except Exception as e:
            return no_update,no_update,no_update,no_update,f"{FAMILY_LABELS[method]} search failed: {e}"
        state.update(res,obs_method=method,within_cache={},within_job=None)
        found=bool(res['multi_subgraphs'])
        return (version or 0)+1,0,"multi" if found else "original",["on"] if found else [],""

    @app.callback(Output("simplify-subgraph","value"),Output("selected-obstruction-only","value",allow_duplicate=True),
    Input("simplify-btn","n_clicks"),State("simplify-subgraph","value"),State("selected-obstruction-only","value"),
    prevent_initial_call=True)
    def toggle_simplify(_n,value,selected):
        # the simplified view only exists for the selected obstruction alone, so turn that on with it
        if "on" in (value or []):
            return [],no_update
        return ["on"],["on"]

    @app.callback(Output("simplify-btn","style"),Input("simplify-subgraph","value"))
    def simplify_button_style(value):
        return BTN_PRIMARY if "on" in (value or []) else BTN

    def within_key(idx,simplified,method):
        return (state.get('obs_method'),id(state['multi_subgraphs']),idx,simplified,method)

    def displayed_subgraph(idx,simplified,method):
        sub=state['multi_subgraphs'][idx]
        selected=state['G'].edge_subgraph(sub.edges())
        return get_simplified_subgraph(idx,selected,method=method) if simplified else selected

    def compute_within(idx,simplified,method):
        """Knotted loops within one K_3,3 / K_5 minor (cached per subgraph, simplification and method)."""
        cache=state.setdefault('within_cache',{})
        key=within_key(idx,simplified,method)
        if key not in cache:
            try:
                loops=find_knotted_loops(displayed_subgraph(idx,simplified,method),state.get('node_pos_3d'),tries=500,
                                         params=dict(state.get('graph_params',{}),within=state['obs_method'],
                                                     subgraph_index=idx,simplified=simplified,
                                                     simplify_method=method if simplified else None))
                cache[key]=dict(loops=loops)
            except Exception as e:
                cache[key]=dict(loops=[],error=str(e))
        return cache[key]

    def run_within_job(job,start,method):
        subs=state['multi_subgraphs']
        n=len(subs)
        order=[(i%n) for i in range(start,start+n)]
        for simplified in (False,True):
            for i in order:
                if state.get('within_job') is not job:
                    return
                compute_within(i,simplified,method)
                job['progress']+=1
        job['running']=False

    def start_within_job(start,method):
        subs=state['multi_subgraphs']
        job=state.get('within_job')
        if not subs or (job and job['subs'] is subs and job['method']==method):
            return
        job=dict(subs=subs,method=method,running=True,progress=0,total=2*len(subs))
        state['within_job']=job
        threading.Thread(target=run_within_job,args=(job,start,method),daemon=True).start()

    def within_selection(idx,simplified,method,widx):
        """(nodes, edges) of the chosen knotted loop within the shown subgraph, or None if not computed for it."""
        if not state['multi_subgraphs'] or state.get('obs_method') not in FAMILY_LABELS:
            return None
        w=state.get('within_cache',{}).get(within_key(idx,simplified,method))
        if not w or not w['loops']:
            return None
        nodes=w['loops'][widx%len(w['loops'])]['nodes']
        edges=loop_edges(nodes)
        return set(nodes),edges

    def full_graph_knot(idx,widx,enabled):
        """Knotted loop within the shown obstruction as original-graph nodes/edges (the unsimplified search
        is used because simplified subgraphs contain shortcut edges that don't exist in the graph)."""
        if "on" not in (enabled or []):
            return set(),set()
        return within_selection(idx,False,"kmt",widx or 0) or (set(),set())

    def within_status(idx,simplified,method,widx):
        name=FAMILY_LABELS.get(state.get('obs_method'))
        if not name or not state['multi_subgraphs']:
            return ""
        job=state.get('within_job')
        running=bool(job and job['subs'] is state['multi_subgraphs'] and job['running'])
        w=state.get('within_cache',{}).get(within_key(idx,simplified,method))
        bg=f" [background search running: {job['progress']}/{job['total']} subgraph views done]" if running else ""
        if not w:
            return f"Searching for knots in the background...{bg}" if running else f"Click 'Knot within' to look for knots in this {name}."
        if 'error' in w:
            return f"Knot search failed: {w['error']}"
        loops=w['loops']
        if not loops:
            return f"No knot found within this {name}.{bg}"
        k=loops[widx%len(loops)]
        knot=k['knot']
        if knot[0] not in "+-":
            knot+=" (achiral or handedness undetermined)"
        return f"Knot {widx%len(loops)+1} of {len(loops)}: {knot}, P={k['prob']:.2f}{bg}"

    @app.callback(Output("within-index","data"),Output("within-version","data"),Output("within-info","children"),
    Output("within-poll","disabled"),
    Input("within-btn","n_clicks"),Input("within-prev-btn","n_clicks"),Input("within-next-btn","n_clicks"),
    Input("subgraph-index","data"),Input("graph-version","data"),Input("simplify-subgraph","value"),
    Input("within-poll","n_intervals"),
    State("within-index","data"),State("within-version","data"),prevent_initial_call=True)
    def within_controls(_b,_p,_n,sub_idx,_gv,simplify_val,_poll,widx,version):
        simplified="on" in (simplify_val or [])
        method="kmt"
        widx=widx or 0
        trigger=ctx.triggered_id
        n_sub=len(state['multi_subgraphs'])
        in_family=state.get('obs_method') in FAMILY_LABELS
        sub_idx=(sub_idx or 0)%n_sub if n_sub else 0
        if n_sub and in_family:
            start_within_job(sub_idx,"kmt")
        job=state.get('within_job')
        running=bool(n_sub and job and job['subs'] is state['multi_subgraphs'] and job['running'])
        key=within_key(sub_idx,simplified,method)
        if trigger=="within-btn":
            if not n_sub or not in_family:
                return 0,no_update,"Find a K_3,3 or K_5 minor first.",not running
            compute_within(sub_idx,simplified,method)
            return 0,(version or 0)+1,within_status(sub_idx,simplified,method,0),not running
        if trigger=="within-poll":
            seen=state.get('within_seen')
            progress=(id(job),job['progress']) if job else None
            state['within_seen']=progress
            changed=progress!=seen
            return no_update,(version or 0)+1 if changed else no_update,within_status(sub_idx,simplified,method,widx),not running
        w=state.get('within_cache',{}).get(key)
        if trigger in ("within-prev-btn","within-next-btn"):
            if w and w['loops']:
                widx=(widx+(1 if trigger=="within-next-btn" else -1))%len(w['loops'])
                return widx,(version or 0)+1,within_status(sub_idx,simplified,method,widx),not running
            return widx,no_update,within_status(sub_idx,simplified,method,widx),not running
        return 0,(version or 0)+1,within_status(sub_idx,simplified,method,0),not running

    @app.callback(Output("graph","stylesheet"),Output("edge-color-legend","children"),
    Input("edge-color-attr","value"),Input("graph-version","data"),Input("rainbow-backbone","value"),Input("node-font-size","value"),
    Input("view-dim","value"),Input("edge-thickness","value"))
    def update_edge_colors(attr,_version,rainbow,font_size,view_dim,thickness_index):
        g=state['G']
        thickness=EDGE_THICKNESS_VALUES[thickness_index] if thickness_index is not None else 1.0
        rainbow_rules=[{"selector":f'edge[source = "{u}"][target = "{v}"]',"style":{"line-color":c}}
                       for (u,v),c in ((tuple(e),c) for e,c in rainbow_backbone_map(g).items())] if rainbow else []
        rainbow_rules+=[{"selector":f'edge[source = "{v}"][target = "{u}"]',"style":r["style"]} for r in rainbow_rules for u,v in [(r["selector"].split('"')[3],r["selector"].split('"')[1])]]
        stylesheet=BASE_STYLE+[{"selector":"node","style":{"font-size":f"{(font_size or 18)*node_scale_for(thickness):.1f}px"}},
            {"selector":".crossing-marker","style":{"width":24*EDGE_2D_SCALE,"height":24*EDGE_2D_SCALE,"shape":"rectangle",
             "background-opacity":0,"background-image":"data(image)","background-fit":"contain",
             "border-width":0}}]+edge_color_stylesheet(g,attr)+rainbow_rules+OBSTRUCTION_STYLE+KNOT_STYLE
        stylesheet+=edge_thickness_stylesheet(thickness)
        legend=[edge_color_legend(g,attr)]
        if view_dim=="2d":
            legend.append(html.Span("Crossings: dark line passes over; white gap marks under.",
                                    style={"fontSize":"12px","color":"#607d8b","marginLeft":"12px"}))
        return stylesheet,html.Div(legend)

    ROT_STEP=15
    ROT_BUTTONS={"rot-left":(0,-1),"rot-right":(0,1),"rot-up":(1,-1),"rot-down":(1,1),"rot-ccw":(2,-1),"rot-cw":(2,1)}

    @app.callback(Output("rot3d","data"),*[Input(i,"n_clicks") for i in [*ROT_BUTTONS,"rot-reset"]],
    State("rot3d","data"),prevent_initial_call=True)
    def rotate_view(*args):
        rot=list(args[-1] or [0,0,0])
        trig=ctx.triggered_id
        if trig=="rot-reset":
            return [0,0,0]
        axis,sign=ROT_BUTTONS[trig]
        rot[axis]=(rot[axis]+sign*ROT_STEP)%360
        return rot

    def rotated_positions(rot):
        """Rotate the 3D coordinates about their centroid (yaw, pitch, roll in degrees); returns (2D positions, 3D coordinates)."""
        coords=state['node_pos_3d']
        if not rot or not any(rot):
            return state['pos'],coords
        pts=np.array([coords[n] for n in coords],dtype=float)
        c=pts.mean(axis=0)
        yaw,pitch,roll=(np.radians(a) for a in rot)
        ry=np.array([[np.cos(yaw),0,np.sin(yaw)],[0,1,0],[-np.sin(yaw),0,np.cos(yaw)]])
        rx=np.array([[1,0,0],[0,np.cos(pitch),-np.sin(pitch)],[0,np.sin(pitch),np.cos(pitch)]])
        rz=np.array([[np.cos(roll),-np.sin(roll),0],[np.sin(roll),np.cos(roll),0],[0,0,1]])
        out=(pts-c)@(rz@rx@ry).T+c
        new3={n:tuple(out[i]) for i,n in enumerate(coords)}
        return {n:(v[0],v[1]) for n,v in new3.items()},new3

    @app.callback(Output("graph","elements"),
    Input("mode","value"),Input("subgraph-index","data"),Input("graph-version","data"),
    Input("selected-obstruction-only","value"),Input("simplify-subgraph","value"),
    Input("knot-index","data"),Input("knot-version","data"),
    Input("view-dim","value"),Input("edge-thickness","value"),
    Input("rainbow-backbone","value"),Input("edge-color-attr","value"),
    Input("within-index","data"),Input("within-version","data"),Input("knot-in-original","value"),Input("rot3d","data"))
    def update(mode,idx,_version,selected_obstruction_only,simplify_subgraph,knot_idx,_kv,view_dim,_thickness_index,rainbow,color_attr,widx,_wv,knot_in_full,rot):
        g=state['G']
        vpos,vpos3d=rotated_positions(rot) if view_dim=="2d" else (state['pos'],state['node_pos_3d'])
        def finalize(elements):
            if view_dim != "2d":
                return elements
            node_pos_3d={str(n): coordinates for n,coordinates in vpos3d.items()}
            thickness=EDGE_THICKNESS_VALUES[_thickness_index] if _thickness_index is not None else 1.0
            colors={**edge_color_map(g,color_attr),**(rainbow_backbone_map(g) if rainbow else {})}
            colors={frozenset(map(str,e)):c for e,c in colors.items()}
            return elements + _crossing_overlay_elements(elements,node_pos_3d,thickness,colors)
        if mode=="knots":
            sel=knotted_loop_selection(knot_idx)
            if sel is None:
                return finalize(build_elements(g,vpos))
            if "on" in (selected_obstruction_only or []):
                return finalize(build_elements(g.edge_subgraph(tuple(e) for e in sel[1]),vpos,sel[0],sel[1],True,"knotted"))
            return finalize(build_elements(g,vpos,sel[0],sel[1],True,"knotted"))
        if mode=="original":
            return finalize(build_elements(g,vpos))
        if mode=="highlight":
            return finalize(build_elements(g,vpos,state['obs_nodes'],state['obs_edges'],True))
        if mode=="multi":
            multi_subgraphs=state['multi_subgraphs']
            if not multi_subgraphs:
                return finalize(build_elements(g,vpos))
            sub=multi_subgraphs[idx]
            sub_nodes=set(sub.nodes())
            sub_edges={frozenset(e) for e in sub.edges()}
            if "on" in (selected_obstruction_only or []):
                selected_graph=g.edge_subgraph(sub.edges())
                simplified="on" in (simplify_subgraph or [])
                knot=within_selection(idx,simplified,"kmt",widx or 0) or (set(),set())
                if simplified:
                    simp_g=get_simplified_subgraph(idx,selected_graph,method="kmt")
                    return finalize(build_elements(simp_g,vpos,set(simp_g.nodes()),{frozenset(e) for e in simp_g.edges()},True,
                                                   knot_nodes=knot[0],knot_edges=knot[1]))
                return finalize(build_elements(selected_graph,vpos,sub_nodes,sub_edges,True,
                                               knot_nodes=knot[0],knot_edges=knot[1]))
            knot=full_graph_knot(idx,widx,knot_in_full)
            return finalize(build_elements(g,vpos,sub_nodes,sub_edges,True,knot_nodes=knot[0],knot_edges=knot[1]))
        return finalize(build_elements(state['obs'],state['obs_pos']))

    @app.callback(Output("graph","style"),Output("graph-3d","style"),
    Input("view-dim","value"),Input("show-grid","value"))
    def toggle_view(view,grid_value):
        grid="grid" in (grid_value or [])
        if view=="3d":
            return container_style(True,grid),container_style(False,grid)
        return container_style(False,grid),container_style(True,grid)

    @app.callback(Output("export-sub-download","data"),Input("export-sub-btn","n_clicks"),
    State("mode","value"),State("subgraph-index","data"),State("selected-obstruction-only","value"),
    State("simplify-subgraph","value"),State("knot-index","data"),State("within-index","data"),
    prevent_initial_call=True)
    def export_subgraph(_n,mode,idx,selected_only,simplify_val,knot_idx,widx):
        import json
        g=state['G']
        params=dict(state.get('graph_params',{}))
        only="on" in (selected_only or [])
        simplified="on" in (simplify_val or [])
        shown=g
        label="whole"
        highlight=set()
        if mode=="knots" and state.get('knotted_loops'):
            sel=knotted_loop_selection(knot_idx or 0)
            highlight=sel[1]
            label=f"knotted-loop-{(knot_idx or 0)%len(state['knotted_loops'])+1}"
            if only:
                shown=g.edge_subgraph(tuple(e) for e in sel[1])
        elif mode=="multi" and state.get('multi_subgraphs'):
            idx=(idx or 0)%len(state['multi_subgraphs'])
            sub=state['multi_subgraphs'][idx]
            highlight={frozenset(e) for e in sub.edges()}
            label=f"{state.get('obs_method')}-{idx+1}"
            params.update(within=state.get('obs_method'),subgraph_index=idx)
            if only:
                shown=displayed_subgraph(idx,simplified,"kmt")
                highlight=set()
                if simplified:
                    params.update(simplified=True,simplify_method="kmt")
                    label+="-simplified"
        elif mode=="highlight" and state.get('obs') is not None:
            highlight=state['obs_edges']
            label="obstruction"
        coords=state.get('node_pos_3d',{})
        def coord(n):
            c=shown.nodes[n].get('coords')
            if c is None:
                c=coords.get(n)
            return None if c is None else [float(x) for x in c]
        data=dict(params=params,view=label,
                  nodes=[dict(id=str(n),coords=coord(n)) for n in shown.nodes()],
                  edges=[{**{k:v2 for k,v2 in d.items() if isinstance(v2,(str,int,float,bool))},"source":str(u),"target":str(v)}
                         for u,v,d in shown.edges(data=True)],
                  highlighted_edges=[sorted(map(str,e)) for e in highlight])
        # same data as the knot cache file for this graph, when one exists
        try:
            with open(_knot_cache_path(shown,coords,500,params=params)) as f:
                data['knot_cache']=json.load(f)
        except (OSError,ValueError):
            pass
        pid=re.sub(r"[^A-Za-z0-9_.-]+","-",str(params.get('pdbid') or 'graph'))
        return dict(content=json.dumps(data,indent=1),filename=f"{pid}_{label}.json",type="application/json")

    @app.callback(Output("export-3d-download","data"),
    Input("export-3d-btn","n_clicks"),State("graph-3d","figure"),State("title-text","children"),
    prevent_initial_call=True)
    def export_3d(n_clicks,figure,title_text):
        if not figure:
            raise PreventUpdate
        buffer=io.StringIO()
        go.Figure(figure).write_html(buffer)
        name=re.sub(r"[^A-Za-z0-9_.-]+","_",str(title_text or "graph")).strip("_")[:80] or "graph"
        return dict(content=buffer.getvalue(),filename=f"{name}_3d.html",type="text/html")

    @app.callback(Output("graph-3d","figure"),
    Input("mode","value"),Input("subgraph-index","data"),Input("edge-color-attr","value"),
    Input("graph-version","data"),Input("show-grid","value"),
    Input("rainbow-backbone","value"),Input("edge-thickness","value"),Input("node-font-size","value"),
    Input("selected-obstruction-only","value"),Input("simplify-subgraph","value"),
    Input("knot-index","data"),Input("knot-version","data"),
    Input("within-index","data"),Input("within-version","data"),Input("knot-in-original","value"))
    def update_3d(mode,idx,attr,_version,grid_value,rainbow,thickness,font_size,selected_obstruction_only,simplify_subgraph,knot_idx,_kv,widx,_wv,knot_in_full):
        font_size=font_size or 18
        g=state['G']
        node_pos_3d=state['node_pos_3d']
        thickness=EDGE_THICKNESS_VALUES[thickness] if thickness is not None else 1.0
        rainbow_colors=rainbow_backbone_map(g) if rainbow else {}
        edge_colors={**edge_color_map(g,attr),**rainbow_colors}
        show_grid="grid" in (grid_value or [])
        if mode=="original":
            return build_3d_figure(g,node_pos_3d,edge_colors=edge_colors,show_grid=show_grid,thickness=thickness,font_size=font_size)
        if mode=="knots":
            sel=knotted_loop_selection(knot_idx)
            if sel is None:
                return build_3d_figure(g,node_pos_3d,edge_colors=edge_colors,show_grid=show_grid,thickness=thickness,font_size=font_size)
            if "on" in (selected_obstruction_only or []):
                return build_3d_figure(g.edge_subgraph(tuple(e) for e in sel[1]),node_pos_3d,sel[0],sel[1],True,edge_colors,show_grid,thickness,font_size,KNOT_COLOR)
            return build_3d_figure(g,node_pos_3d,sel[0],sel[1],True,edge_colors,show_grid,thickness,font_size,KNOT_COLOR)
        if mode=="highlight":
            return build_3d_figure(g,node_pos_3d,state['obs_nodes'],state['obs_edges'],True,edge_colors,show_grid,thickness,font_size)
        if mode=="multi":
            multi_subgraphs=state['multi_subgraphs']
            if not multi_subgraphs:
                return build_3d_figure(g,node_pos_3d,edge_colors=edge_colors,show_grid=show_grid,thickness=thickness,font_size=font_size)
            sub=multi_subgraphs[idx]
            sub_nodes=set(sub.nodes())
            sub_edges={frozenset(e) for e in sub.edges()}
            if "on" in (selected_obstruction_only or []):
                selected_graph=g.edge_subgraph(sub.edges())
                simplified="on" in (simplify_subgraph or [])
                knot=within_selection(idx,simplified,"kmt",widx or 0) or (set(),set())
                if simplified:
                    simp_g=get_simplified_subgraph(idx,selected_graph,method="kmt")
                    simp_edge_colors={**edge_color_map(simp_g,attr),**(rainbow_backbone_map(simp_g) if rainbow else {})}
                    return build_3d_figure(simp_g,node_pos_3d,set(simp_g.nodes()),{frozenset(e) for e in simp_g.edges()},True,
                                           simp_edge_colors,show_grid,thickness,font_size,knot_nodes=knot[0],knot_edges=knot[1])
                return build_3d_figure(selected_graph,node_pos_3d,sub_nodes,sub_edges,True,
                                       edge_colors,show_grid,thickness,font_size,knot_nodes=knot[0],knot_edges=knot[1])
            knot=full_graph_knot(idx,widx,knot_in_full)
            return build_3d_figure(g,node_pos_3d,sub_nodes,sub_edges,True,edge_colors,show_grid,thickness,font_size,
                                   knot_nodes=knot[0],knot_edges=knot[1])
        obs=state['obs']
        obs_pos_3d={n:node_pos_3d[n] for n in obs.nodes()} if not state['planar'] else {}
        return build_3d_figure(obs,obs_pos_3d,edge_colors={**edge_color_map(obs,attr),**rainbow_colors},show_grid=show_grid,thickness=thickness,font_size=font_size)

    @app.callback(
        Output("homfly-result","children"),
        Input("run-homfly-btn","n_clicks"),
        Input("subgraph-index","data"),
        Input("graph-version","data"),
        Input("mode","value"),
        Input("selected-obstruction-only","value"),
        Input("simplify-subgraph","value"))
    def update_homfly_knot(run_clicks,idx,_version,mode,
                           selected_obstruction_only,simplify_subgraph):
        try:
            triggered=ctx.triggered_id
        except Exception:
            triggered=None
        if triggered!="run-homfly-btn":
            return ""

        if state.get('planar'):
            return "Planar graph (no obstruction)"

        g=state.get('G')
        if not g:
            return ""

        state.setdefault('homfly_cache',{})
        multi_subgraphs=state.get('multi_subgraphs',[])
        is_simplified="on" in (simplify_subgraph or [])
        method="kmt"

        if mode=="multi" and multi_subgraphs:
            n=len(multi_subgraphs)
            actual_idx=idx%n if n>0 else 0
            sub=multi_subgraphs[actual_idx]
            sub_g=g.edge_subgraph(sub.edges())
            if is_simplified:
                target_g=get_simplified_subgraph(actual_idx,sub_g,method=method)
            else:
                target_g=sub_g
            cache_key=(_version,"multi",actual_idx,is_simplified,method)
        elif state.get('obs') is not None:
            obs_g=state['obs']
            cache_key=(_version,"obs",0,is_simplified,method)
            if state['homfly_cache'].get(cache_key) is None:
                target_g=simplify_subgraph_topoly(obs_g,state.get('node_pos_3d'),method=method) if is_simplified else obs_g
            else:
                target_g=None
        elif multi_subgraphs:
            n=len(multi_subgraphs)
            actual_idx=idx%n if n>0 else 0
            sub=multi_subgraphs[actual_idx]
            sub_g=g.edge_subgraph(sub.edges())
            if is_simplified:
                target_g=get_simplified_subgraph(actual_idx,sub_g,method=method)
            else:
                target_g=sub_g
            cache_key=(_version,"multi",actual_idx,is_simplified,method)
        else:
            return "No obstruction subgraph found"

        cached=state.setdefault('homfly_cache',{}).get(cache_key)
        if cached is not None:
            knot_type,prob=cached
        else:
            knot_type,prob=cached_subgraph_homfly(target_g,state.get('node_pos_3d'),tries=500,
                                                    params=dict(state.get('graph_params',{}),view=cache_key[1],
                                                                subgraph_index=cache_key[2],simplified=is_simplified,
                                                                simplify_method=method if is_simplified else None,
                                                                obstruction_finder=state.get('obs_method')))
            if knot_type is not None:
                state['homfly_cache'][cache_key]=(knot_type,prob)

        if knot_type is None:
            return "HOMFLY test failed (crashed, timed out or inconclusive)"
        if knot_type=='0_1':
            return f"knot_type: 0_1 (unknot), probability: {prob:.3f}"
        return f"knot_type: {knot_type}, probability: {prob:.3f}"

    return app

def _path_prefix():
    """Return the URL prefix from CONTEXT_PATH env var (default: 'spatialgraph'); empty value means root."""
    ctx = os.environ.get("CONTEXT_PATH", "spatialgraphs").strip("/")
    return f"/{ctx}/" if ctx else "/"

if __name__=="__main__":
    #os.environ['OGDF_INSTALL_DIR'] = '/usr/local'
    app=create_app(pdbid="1A8E", is_topoly=False)
    app.run(debug=True, port=8014)
