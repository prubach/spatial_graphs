import colorsys
import io
import os
import re
import random
import numpy as np
import networkx as nx
from dash import Dash, html, dcc, Input, Output, State, ctx
from dash.exceptions import PreventUpdate
import dash_cytoscape as cyto
import plotly.graph_objects as go
import topoly as tp
from ogdf_python import *



def create_graph(seed=42,n_cliques=5,n_bicliques=6,n_random_edges=10):
    random.seed(seed)
    G=nx.Graph()
    nxt=0
    def new_nodes(n):
        nonlocal nxt
        r=list(range(nxt,nxt+n)); nxt+=n; return r
    cliques=[]
    shared=new_nodes(3)
    for i in range(n_cliques):
        clique=shared+new_nodes(2) if i==0 else random.sample(cliques[-1],3)+new_nodes(2)
        cliques.append(clique)
        for a in range(len(clique)):
            for b in range(a+1,len(clique)):
                G.add_edge(clique[a],clique[b])
    for _ in range(n_bicliques):
        left=random.sample(random.choice(cliques),3)
        right=(random.sample(list(G.nodes()),2)+new_nodes(1)) if random.random()<0.5 else new_nodes(3)
        for u in left:
            for v in right:
                G.add_edge(u,v)
    nodes=list(G.nodes())
    for _ in range(n_random_edges):
        u,v=random.sample(nodes,2); G.add_edge(u,v)
    return G

def build_elements(graph,pos,obs_nodes=set(),obs_edges=set(),highlight=False):
    els=[]
    for n in graph.nodes():
        e={"data":{"id":str(n),"label":str(n)},"position":{"x":pos[n][0]*800,"y":pos[n][1]*800}}
        if highlight and n in obs_nodes: e["classes"]="obstruction"
        els.append(e)
    for u,v,data in graph.edges(data=True):
        edata={"source":str(u),"target":str(v)}
        edata.update(data)
        e={"data":edata}
        if highlight and frozenset((u,v)) in obs_edges: e["classes"]="obstruction"
        els.append(e)
    return els

BASE_STYLE=[
#{"selector":"node","style":{"label":"data(label)","background-color":"#1976d2","color":"white","width":40,"height":40,"font-size":"10px"}},
{"selector": "node",
"style": {
    "label": "data(label)",
    "width":60,
    "height":60,
    #"width": "mapData(degree,1,15,15,40)",
    #"height": "mapData(degree,1,15,15,40)",
    "background-color": "#1976d2",
    "color": "white",
    "text-valign": "center",
    "text-halign": "center",
    "font-size": "20px",
}},
{"selector":"edge","style":{"line-color":"#999","width":5}},
]
OBSTRUCTION_STYLE=[
{"selector":".obstruction","style":{"background-color":"crimson","line-color":"crimson","border-width":4,"border-color":"gold",
                                    "width":60,"height":60,}},
{"selector":"edge.obstruction","style":{"background-color":"crimson","line-color":"crimson","border-width":4,"border-color":"gold",
                                    "width":16}},
]
STYLE=BASE_STYLE+OBSTRUCTION_STYLE

# CSS grid background, toggled behind the 2D/3D graph views.
GRID_BACKGROUND={
    "backgroundImage":"linear-gradient(to right, #ddd 1px, transparent 1px),"
                       "linear-gradient(to bottom, #ddd 1px, transparent 1px)",
    "backgroundSize":"25px 25px",
}

# Sequential blue ramp (light -> dark) for continuous edge attributes such as weight.
SEQUENTIAL_LOW="#cde2fb"
SEQUENTIAL_HIGH="#0d366b"
# Fixed-order categorical palette for discrete edge attributes such as bond type.
CATEGORICAL_PALETTE=["#2a78d6","#008300","#e87ba4","#eda100","#1baf7a","#eb6834","#4a3aa7","#e34948"]

def edge_attr_keys(graph):
    """All edge data keys present anywhere on the graph, e.g. weight, type."""
    keys=set()
    for _,_,data in graph.edges(data=True):
        keys.update(data.keys())
    return sorted(keys)

def _is_numeric_attr(graph,attr):
    values=[d[attr] for _,_,d in graph.edges(data=True) if attr in d]
    return bool(values) and all(isinstance(v,(int,float)) and not isinstance(v,bool) for v in values)

def edge_color_stylesheet(graph,attr):
    """Cytoscape style rules coloring edges by a data attribute.

    Numeric attributes (e.g. weight) get a continuous sequential ramp;
    non-numeric attributes (e.g. bond type CA/B) get a fixed categorical palette.
    """
    if not attr or attr=="none":
        return []
    if _is_numeric_attr(graph,attr):
        values=[d[attr] for _,_,d in graph.edges(data=True) if attr in d]
        lo,hi=min(values),max(values)
        if lo==hi: hi=lo+1
        return [{"selector":"edge","style":{
            "line-color":f"mapData({attr},{lo},{hi},{SEQUENTIAL_LOW},{SEQUENTIAL_HIGH})"}}]
    values=sorted({d[attr] for _,_,d in graph.edges(data=True) if attr in d},key=str)
    return [{"selector":f'edge[{attr} = "{val}"]',"style":{"line-color":CATEGORICAL_PALETTE[i%len(CATEGORICAL_PALETTE)]}}
            for i,val in enumerate(values)]

def edge_color_legend(graph,attr):
    """A small legend Div matching edge_color_stylesheet's color assignment."""
    if not attr or attr=="none":
        return None
    if _is_numeric_attr(graph,attr):
        values=[d[attr] for _,_,d in graph.edges(data=True) if attr in d]
        lo,hi=min(values),max(values)
        return html.Div([
            html.Span(f"{attr}: ",style={"fontWeight":"bold"}),
            html.Span(str(lo)),
            html.Div(style={"display":"inline-block","width":"120px","height":"12px","margin":"0 6px",
                             "background":f"linear-gradient(to right, {SEQUENTIAL_LOW}, {SEQUENTIAL_HIGH})",
                             "verticalAlign":"middle"}),
            html.Span(str(hi)),
        ],style={"marginTop":"6px"})
    values=sorted({d[attr] for _,_,d in graph.edges(data=True) if attr in d},key=str)
    swatches=[html.Span(f"{attr}: ",style={"fontWeight":"bold"})]
    for i,val in enumerate(values):
        color=CATEGORICAL_PALETTE[i%len(CATEGORICAL_PALETTE)]
        swatches.append(html.Span([
            html.Span(style={"display":"inline-block","width":"12px","height":"12px",
                              "backgroundColor":color,"marginRight":"4px","verticalAlign":"middle"}),
            html.Span(str(val),style={"marginRight":"12px"}),
        ]))
    return html.Div(swatches,style={"marginTop":"6px"})

def _hex_lerp(c1,c2,t):
    c1,c2=c1.lstrip('#'),c2.lstrip('#')
    r1,g1,b1=int(c1[0:2],16),int(c1[2:4],16),int(c1[4:6],16)
    r2,g2,b2=int(c2[0:2],16),int(c2[2:4],16),int(c2[4:6],16)
    return f"#{round(r1+(r2-r1)*t):02x}{round(g1+(g2-g1)*t):02x}{round(b1+(b2-b1)*t):02x}"

def edge_color_map(graph,attr):
    """Edge (frozenset) -> hex color, mirroring edge_color_stylesheet but as a lookup table for Plotly."""
    if not attr or attr=="none":
        return {}
    if _is_numeric_attr(graph,attr):
        values=[d[attr] for _,_,d in graph.edges(data=True) if attr in d]
        lo,hi=min(values),max(values)
        if lo==hi: hi=lo+1
        return {frozenset((u,v)):_hex_lerp(SEQUENTIAL_LOW,SEQUENTIAL_HIGH,(d[attr]-lo)/(hi-lo))
                for u,v,d in graph.edges(data=True) if attr in d}
    values=sorted({d[attr] for _,_,d in graph.edges(data=True) if attr in d},key=str)
    palette={val:CATEGORICAL_PALETTE[i%len(CATEGORICAL_PALETTE)] for i,val in enumerate(values)}
    return {frozenset((u,v)):palette[d[attr]] for u,v,d in graph.edges(data=True) if attr in d}

def rainbow_backbone_map(graph):
    """Backbone ('CA') edge -> rainbow hex color following the residue order along the chain."""
    def res(n):
        head=str(n).partition('_')[0]
        return int(head) if head.lstrip('-').isdigit() else None
    edges=[(u,v) for u,v,d in graph.edges(data=True) if d.get("type")=="CA" and res(u) is not None and res(v) is not None]
    if not edges:
        return {}
    pos={e:(res(e[0])+res(e[1]))/2 for e in edges}
    lo,hi=min(pos.values()),max(pos.values())
    span=(hi-lo) or 1
    colors={}
    for e,p in pos.items():
        r,g,b=colorsys.hsv_to_rgb(0.78*(1-(p-lo)/span),0.9,0.95)
        colors[frozenset(e)]="#%02x%02x%02x"%(round(r*255),round(g*255),round(b*255))
    return colors

def get_node_positions_3d(graph,seed=1):
    """Node -> (x,y,z), taken from each node's 'coords' attribute (set from PDB/topoly
    coordinates or from the JSON atom records); falls back to a 3D spring layout when
    coordinates aren't available for every node."""
    if graph.number_of_nodes() and all(graph.nodes[n].get('coords') is not None for n in graph.nodes()):
        return {n:tuple(graph.nodes[n]['coords']) for n in graph.nodes()}
    return nx.spring_layout(graph,dim=3,seed=seed)

def tube_mesh(edges,node_pos,color,radius,sides=8):
    """Shaded cylinders for the edges, so that overlapping edges are occluded properly and
    their relative depth is visible."""
    verts,faces=[],[]
    angles=np.linspace(0,2*np.pi,sides,endpoint=False)
    for u,v in edges:
        p0=np.array(node_pos[u],dtype=float); p1=np.array(node_pos[v],dtype=float)
        d=p1-p0
        length=np.linalg.norm(d)
        if length==0:
            continue
        d/=length
        a=np.array([1.0,0,0]) if abs(d[0])<0.9 else np.array([0,1.0,0])
        e1=np.cross(d,a); e1/=np.linalg.norm(e1)
        e2=np.cross(d,e1)
        base=len(verts)
        ring=[radius*(np.cos(t)*e1+np.sin(t)*e2) for t in angles]
        verts.extend(p0+r for r in ring)
        verts.extend(p1+r for r in ring)
        for i in range(sides):
            j=(i+1)%sides
            faces.append((base+i,base+j,base+sides+j))
            faces.append((base+i,base+sides+j,base+sides+i))
    if not verts:
        return go.Mesh3d(x=[],y=[],z=[])
    vs=np.array(verts); fs=np.array(faces)
    return go.Mesh3d(x=vs[:,0],y=vs[:,1],z=vs[:,2],i=fs[:,0],j=fs[:,1],k=fs[:,2],color=color,
        flatshading=False,lighting=dict(ambient=0.45,diffuse=0.8,specular=0.3,roughness=0.5),
        hoverinfo="none",showlegend=False)

def build_3d_figure(graph,node_pos,obs_nodes=set(),obs_edges=set(),highlight=False,edge_colors=None,show_grid=False,thickness=1.0):
    edge_colors=edge_colors or {}
    by_color={}
    for u,v in graph.edges():
        if highlight and frozenset((u,v)) in obs_edges:
            continue
        by_color.setdefault(edge_colors.get(frozenset((u,v)),"#999"),[]).append((u,v))
    traces=[]
    pts=np.array([node_pos[n] for n in graph.nodes()]) if graph.number_of_nodes() else np.zeros((1,3))
    extent=float(np.max(pts.max(axis=0)-pts.min(axis=0))) or 1.0
    radius=extent*0.004*thickness
    for color,edges in by_color.items():
        traces.append(tube_mesh(edges,node_pos,color,radius))
    if highlight and obs_edges:
        obs=[(u,v) for u,v in graph.edges() if frozenset((u,v)) in obs_edges]
        traces.append(tube_mesh(obs,node_pos,"crimson",radius*2))
    node_x,node_y,node_z,node_color,node_text=[],[],[],[],[]
    for n in graph.nodes():
        x,y,z=node_pos[n]
        node_x.append(x); node_y.append(y); node_z.append(z)
        node_color.append("crimson" if highlight and n in obs_nodes else "#1976d2")
        node_text.append(str(n))
    traces.append(go.Scatter3d(x=node_x,y=node_y,z=node_z,mode="markers+text",
        text=node_text,textposition="top center",textfont=dict(size=22,color="#111"),
        marker=dict(size=6,color=node_color,line=dict(width=1,color="white")),
        hoverinfo="text",showlegend=False))
    fig=go.Figure(data=traces)
    if show_grid:
        axis_cfg=dict(visible=True,showgrid=True,gridcolor="#ccc",showticklabels=False,title="",
                      zeroline=False,showbackground=True,backgroundcolor="#f2f2f2")
    else:
        axis_cfg=dict(visible=False)
    fig.update_layout(showlegend=False,margin=dict(l=0,r=0,t=0,b=0),
        scene=dict(xaxis=axis_cfg,yaxis=axis_cfg,zaxis=axis_cfg,
        aspectmode="data"))
    return fig

def find_multiple_kuratowski_subgraphs(graph):
    """Finds distinct Kuratowski subgraphs by breaking found structures."""
    G_copy = graph.copy()
    subgraphs = []

    while True:
        is_planar, certificate = nx.check_planarity(G_copy, counterexample=True)
        if is_planar:
            break
        print("Found a Kuratowski subgraph:")
        nodes = sorted(certificate.nodes(), key=lambda e: int(e))
        print(f'nodes: {nodes}')
        edges = sorted(certificate.edges(), key=lambda e: int(e[0]) * 1000 + int(e[1]))
        print(f'edges: {edges}')

        print("Full graph:")
        nodes = sorted(G_copy.nodes(), key=lambda e: int(e))
        print(f'nodes: {nodes}')
        #edges = sorted(G_copy.edges(), key=lambda e: int(e[0]) * 1000 + int(e[1]))
        edges = G_copy.edges()
        print(f'edges: {edges}')

        #for e in certificate.edges():
        #    print(f'edge: {e}')
        # Save the found subgraph
        subgraphs.append(certificate)
        # Remove an edge from the identified subgraph to force the algorithm
        # to look for a different non-planar structure in the next iteration

        edges_to_remove = list(certificate.edges())
        if edges_to_remove:
            G_copy.remove_edge(*edges_to_remove[0])
        else:
            break
    return subgraphs


def find_multiple_kuratowski_subgraphs_ogdf(graph):
    """Extracts all Kuratowski (K5/K3,3) subdivisions from `graph` using OGDF's
    Boyer-Myrvold planarity test, which finds them all in a single linear-time pass
    instead of repeatedly re-running planarity checks like the networkx-only version."""
    cppinclude("ogdf/planarity/BoyerMyrvold.h")

    G = ogdf.Graph()
    node_to_ogdf = {}
    ogdf_index_to_node = {}
    for node in graph.nodes():
        onode = G.newNode()
        node_to_ogdf[node] = onode
        ogdf_index_to_node[onode.index()] = node
    for u, v in graph.edges():
        G.newEdge(node_to_ogdf[u], node_to_ogdf[v])

    bm = ogdf.BoyerMyrvold()
    kuratowski_list = ogdf.SList[ogdf.KuratowskiWrapper]()
    # embeddingGrade=-1 (doFindUnlimited) extracts every subdivision instead of
    # stopping at the first one; avoidE2Minors=True keeps the results unique.
    is_planar = bm.planarEmbed(G, kuratowski_list, -1, False, False, False, True)
    if is_planar:
        return []

    subgraphs = []
    for wrapper in kuratowski_list:
        sub = nx.Graph()
        for e in wrapper.edgeList:
            u = ogdf_index_to_node[e.source().index()]
            v = ogdf_index_to_node[e.target().index()]
            sub.add_edge(u, v)
        subgraphs.append(sub)
    return subgraphs


class TopolyReduce:
    """
    Type of Topoly reduction.
    """
    NO = 0
    INTERNAL = 1
    FULL = 2

TOPOLY_REDUCE_OPTIONS=[
    {"label":"None","value":TopolyReduce.NO},
    {"label":"Internal","value":TopolyReduce.INTERNAL},
    {"label":"Full","value":TopolyReduce.FULL},
]

def list_data_pdbids(data_dir='data'):
    """PDB ids (with the chain appended when a simplified file names a chain other than A)
    for the structures available in the data folder."""
    ids={}
    for name in os.listdir(data_dir):
        base,ext=os.path.splitext(name)
        if ext.lower() in ('.pdb','.cif'):
            ids.setdefault(base.upper(),'')
        elif name.endswith('_simplified_bonds.csv'):
            pid,_,chain=name[:-len('_simplified_bonds.csv')].partition('-')
            ids[pid.upper()]=chain
    return [pid+(chain if chain and chain!='A' else '') for pid,chain in sorted(ids.items())]

def load_graph_by_id(pdbid,is_topoly,reduce=TopolyReduce.INTERNAL,numbering='auth'):
    """Load a graph for a PDB id using either the topoly bridge extraction or
    the pre-simplified CSV/JSON pair. Returns (graph, source_label)."""
    chain = 'A'
    if len(pdbid)>4:
        chain = pdbid[4:].strip()
        pdbid = pdbid[:4]
    if is_topoly:
        #  chain='A',
        #return topoly_graph_to_networkx(f'{pdbid.upper()}.cif', chain=chain, bridge_type='all', reduce=reduce), 'Topoly'
        ext = 'cif' if os.path.exists(f'data/{pdbid.upper()}.cif') else 'pdb'
        return topoly_graph_to_networkx(f'{pdbid.upper()}.{ext}', chain=chain, bridge_type='all', reduce=reduce,
                                        numbering=numbering), 'Topoly'
    return read_simlified_graph_from_file(f"data/{pdbid.upper()}-{chain}_simplified_bonds.csv",
                                           f"data/{pdbid.upper()}-{chain}_simplified.json"), 'Simplified'

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
    def recompute(g):
        planar,obs=nx.check_planarity(g,counterexample=True)
        pos=nx.spring_layout(g,seed=1)
        obs_nodes=set(obs.nodes()) if not planar else set()
        obs_edges={frozenset(e) for e in obs.edges()} if not planar else set()
        obs_pos={n:pos[n] for n in obs.nodes()} if not planar else {}

        #multi_subgraphs=find_multiple_kuratowski_subgraphs(g) if not planar else []
        multi_subgraphs = find_multiple_kuratowski_subgraphs_ogdf(g) if not planar else []

        node_pos_3d=get_node_positions_3d(g)
        state.update(G=g,planar=planar,obs=obs,pos=pos,obs_nodes=obs_nodes,obs_edges=obs_edges,
                     obs_pos=obs_pos,multi_subgraphs=multi_subgraphs,node_pos_3d=node_pos_3d)
    recompute(G)

    def make_title(t,g):
        return f"{t} - Planar: {state['planar']}, Nodes: {g.number_of_nodes()}, Edges: {g.number_of_edges()}"

    GRAPH_BOX_STYLE={"width":"100%","height":"750px"}
    CONTROL_GROUP={"display":"flex","alignItems":"center","gap":"6px"}

    def container_style(hidden,grid):
        style={**GRAPH_BOX_STYLE}
        if grid:
            style.update(GRID_BACKGROUND)
        if hidden:
            style["display"]="none"
        return style

    app=Dash(__name__, requests_pathname_prefix=_path_prefix(), routes_pathname_prefix=_path_prefix())
    app.layout=html.Div([
    html.H3(id="title-text",children=make_title(title,G)),
    html.Div([
        html.Div([
        dcc.Dropdown(id="pdbid-input",placeholder="PDB ID",value=pdbid or None,clearable=False,
                   options=[{"label":p,"value":p} for p in list(dict.fromkeys(list_data_pdbids()+([pdbid] if pdbid else [])))],
                   style={"width":"130px"}),
        dcc.RadioItems(id="source-type",inline=True,value="topoly" if is_topoly else "simplified",
        options=[{"label":"Topoly","value":"topoly"},{"label":"Simplified","value":"simplified"}]),
        html.Div([
        html.Label("Reduction: "),
        dcc.Dropdown(id="topoly-reduce",clearable=False,style={"width":"110px"},
        value=TopolyReduce.INTERNAL,options=TOPOLY_REDUCE_OPTIONS),
        html.Label("Numbering: "),
        dcc.RadioItems(id="topoly-numbering",inline=True,value="auth",options=[
        {"label":"Label","value":"label"},{"label":"Auth","value":"auth"}]),
        ],id="topoly-reduce-container",style={**CONTROL_GROUP,"display":"flex" if is_topoly else "none"}),
        html.Button("Load",id="load-btn",n_clicks=0),
        ],style=CONTROL_GROUP),
        html.Div([
        dcc.RadioItems(id="mode",inline=True,value="original",options=[
        {"label":"Original","value":"original"},
        {"label":"Highlight obstruction","value":"highlight"},
        {"label":"Obstruction only","value":"obstruction"},
        {"label":"Multiple obstructions","value":"multi"}]),
        ],style=CONTROL_GROUP),
        html.Div([
        html.Button("< Prev",id="prev-btn",n_clicks=0),
        html.Button("Next >",id="next-btn",n_clicks=0),
        html.Span(id="subgraph-info"),
        ],style=CONTROL_GROUP),
        html.Div([
        html.Label("Color edges by: "),
        dcc.Dropdown(id="edge-color-attr",clearable=False,style={"width":"180px"},
        value="type" if "type" in edge_attr_keys(G) else "none",
        options=[{"label":"None","value":"none"}]+[{"label":a,"value":a} for a in edge_attr_keys(G)]),
        ],style=CONTROL_GROUP),
        html.Div([
        html.Label("View: "),
        dcc.RadioItems(id="view-dim",inline=True,value="3d",options=[
        {"label":"2D","value":"2d"},{"label":"3D","value":"3d"}]),
        ],style=CONTROL_GROUP),
        html.Div([
        dcc.Checklist(id="show-grid",options=[{"label":"Show grid","value":"grid"}],value=["grid"]),
        dcc.Checklist(id="rainbow-backbone",options=[{"label":"Rainbow backbone","value":"on"}],value=[]),
        html.Div([html.Label("Edge thickness: "),
        html.Div(dcc.Slider(id="edge-thickness",min=0.5,max=5,step=0.5,value=1,
                            marks={0.5:"0.5",1:"1",2:"2",3:"3",4:"4",5:"5"}),style={"width":"220px"}),
        ],style=CONTROL_GROUP),
        html.Button("Export 3D to HTML",id="export-3d-btn",n_clicks=0),
        dcc.Download(id="export-3d-download"),
        ],style=CONTROL_GROUP),
    ],style={"display":"flex","flexWrap":"wrap","gap":"20px","alignItems":"center","marginTop":"8px"}),
    html.Div(id="edge-color-legend"),
    dcc.Store(id="graph-version",data=0),
    dcc.Store(id="subgraph-index",data=0),
    cyto.Cytoscape(id="graph",layout={"name":"preset"},stylesheet=STYLE,style=container_style(False,False)),
    dcc.Graph(id="graph-3d",style=container_style(True,False),config={"displayModeBar":False}),
    ])

    @app.callback(Output("topoly-reduce-container","style"),Input("source-type","value"))
    def toggle_topoly_reduce(source_type):
        return {**CONTROL_GROUP,"display":"flex" if source_type=="topoly" else "none"}

    @app.callback(Output("title-text","children"),Output("edge-color-attr","options"),
    Output("edge-color-attr","value"),Output("mode","value"),
    Output("subgraph-index","data",allow_duplicate=True),Output("graph-version","data"),
    Input("load-btn","n_clicks"),Input("pdbid-input","value"),
    State("pdbid-input","value"),State("source-type","value"),State("topoly-reduce","value"),State("topoly-numbering","value"),
    State("graph-version","data"),
    prevent_initial_call=True)
    def load_new_graph(n_clicks,pdbid_input,pdbid_value,source_type,reduce_value,numbering,version):
        if not pdbid_value:
            raise PreventUpdate
        g,tit=load_graph_by_id(pdbid_value,source_type=="topoly",reduce_value,numbering)
        print(f'nodes: {sorted(g.nodes())}')
        print(f'edges: {sorted(g.edges())}')
        print('--------------------------------------------')
        recompute(g)
        options=[{"label":"None","value":"none"}]+[{"label":a,"value":a} for a in edge_attr_keys(g)]
        return make_title(f"{pdbid_value}-{tit}",g),options,"type" if "type" in edge_attr_keys(g) else "none","original",0,(version or 0)+1

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

    @app.callback(Output("subgraph-info","children"),Input("subgraph-index","data"))
    def update_info(idx):
        n=len(state['multi_subgraphs'])
        if n==0:
            return "No additional Kuratowski subgraphs found."
        return f"Found {n} Kuratowski subgraph(s) - showing {idx+1} of {n}"

    @app.callback(Output("graph","stylesheet"),Output("edge-color-legend","children"),
    Input("edge-color-attr","value"),Input("graph-version","data"),Input("rainbow-backbone","value"))
    def update_edge_colors(attr,_version,rainbow):
        g=state['G']
        rainbow_rules=[{"selector":f'edge[source = "{u}"][target = "{v}"]',"style":{"line-color":c}}
                       for (u,v),c in ((tuple(e),c) for e,c in rainbow_backbone_map(g).items())] if rainbow else []
        rainbow_rules+=[{"selector":f'edge[source = "{v}"][target = "{u}"]',"style":r["style"]} for r in rainbow_rules for u,v in [(r["selector"].split('"')[3],r["selector"].split('"')[1])]]
        stylesheet=BASE_STYLE+edge_color_stylesheet(g,attr)+rainbow_rules+OBSTRUCTION_STYLE
        return stylesheet,edge_color_legend(g,attr)

    @app.callback(Output("graph","elements"),
    Input("mode","value"),Input("subgraph-index","data"),Input("graph-version","data"))
    def update(mode,idx,_version):
        g=state['G']
        if mode=="original":
            return build_elements(g,state['pos'])
        if mode=="highlight":
            return build_elements(g,state['pos'],state['obs_nodes'],state['obs_edges'],True)
        if mode=="multi":
            multi_subgraphs=state['multi_subgraphs']
            if not multi_subgraphs:
                return build_elements(g,state['pos'])
            sub=multi_subgraphs[idx]
            sub_nodes=set(sub.nodes())
            sub_edges={frozenset(e) for e in sub.edges()}
            return build_elements(g,state['pos'],sub_nodes,sub_edges,True)
        return build_elements(state['obs'],state['obs_pos'])

    @app.callback(Output("graph","style"),Output("graph-3d","style"),
    Input("view-dim","value"),Input("show-grid","value"))
    def toggle_view(view,grid_value):
        grid="grid" in (grid_value or [])
        if view=="3d":
            return container_style(True,grid),container_style(False,grid)
        return container_style(False,grid),container_style(True,grid)

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
    Input("rainbow-backbone","value"),Input("edge-thickness","value"))
    def update_3d(mode,idx,attr,_version,grid_value,rainbow,thickness):
        g=state['G']
        node_pos_3d=state['node_pos_3d']
        thickness=thickness or 1.0
        rainbow_colors=rainbow_backbone_map(g) if rainbow else {}
        edge_colors={**edge_color_map(g,attr),**rainbow_colors}
        show_grid="grid" in (grid_value or [])
        if mode=="original":
            return build_3d_figure(g,node_pos_3d,edge_colors=edge_colors,show_grid=show_grid,thickness=thickness)
        if mode=="highlight":
            return build_3d_figure(g,node_pos_3d,state['obs_nodes'],state['obs_edges'],True,edge_colors,show_grid,thickness)
        if mode=="multi":
            multi_subgraphs=state['multi_subgraphs']
            if not multi_subgraphs:
                return build_3d_figure(g,node_pos_3d,edge_colors=edge_colors,show_grid=show_grid,thickness=thickness)
            sub=multi_subgraphs[idx]
            sub_nodes=set(sub.nodes())
            sub_edges={frozenset(e) for e in sub.edges()}
            return build_3d_figure(g,node_pos_3d,sub_nodes,sub_edges,True,edge_colors,show_grid,thickness)
        obs=state['obs']
        obs_pos_3d={n:node_pos_3d[n] for n in obs.nodes()} if not state['planar'] else {}
        return build_3d_figure(obs,obs_pos_3d,edge_colors={**edge_color_map(obs,attr),**rainbow_colors},show_grid=show_grid,thickness=thickness)
    return app

SIMPLIFIED_BOND_TYPES={'disulf':'disulfide','metalc':'ion'}

def read_simlified_graph_from_file(file_path, node_list_json=None):
    """Read a simplified bonds CSV (+ JSON with atom records). Nodes are atoms named
    <residue>_<atom>, as in topoly_graph_to_networkx; covale bonds are split into
    'side chain' (inside a residue), 'CA' (simplified backbone between residues) and
    'covalent' (original bond between residues)."""
    import json
    G = nx.Graph()
    atom_list = {}
    simplified = {}
    if node_list_json:
        with open(node_list_json, 'r') as f:
            nodes = json.load(f)
        atom_list = {a['index']: a for a in nodes.get('atoms') or []}
        simplified = {(b['ptnr1_id'], b['ptnr2_id']): b.get('is_simplified', False) for b in nodes.get('bonds') or []}

    def node_of(idx):
        atom = atom_list.get(idx)
        if not atom:
            return str(idx)
        name = f"{atom.get('auth_residue_id', atom.get('residue_number'))}_{atom['atom']}"
        if not G.has_node(name):
            G.add_node(name, coords=(atom['x'], atom['y'], atom['z']))
        return name

    with open(file_path, 'r') as f:
        for line in f:
            if line.startswith('#') or not line.strip():
                continue  # Skip comments and empty lines
            parts = line.strip().split(',')
            if len(parts) != 3:
                continue
            t, u, v = parts
            u, v = int(u), int(v)
            u_id, v_id = node_of(u), node_of(v)
            if t in SIMPLIFIED_BOND_TYPES:
                t = SIMPLIFIED_BOND_TYPES[t]
            elif t == 'covale':
                same_residue = u_id.partition('_')[0] == v_id.partition('_')[0]
                if same_residue:
                    t = 'side chain'
                elif simplified.get((u, v), simplified.get((v, u), True)):
                    t = 'CA'
                else:
                    t = 'covalent'
            G.add_edge(u_id, v_id, type=t, weight=5 if t == 'CA' else 1)
    return G


def cif_label_to_auth(path, chain):
    """Map label_seq_id -> auth_seq_id for the given label_asym_id chain of an mmCIF file."""
    import gemmi
    block = gemmi.cif.read(path).sole_block()
    mapping = {}
    for asym, label, auth in block.find('_atom_site.', ['label_asym_id', 'label_seq_id', 'auth_seq_id']):
        if asym == chain and label.isdigit() and auth.lstrip('-').isdigit():
            mapping.setdefault(int(label), int(auth))
    return mapping


def topoly_graph_to_networkx(input_file, chain='A', bridge_type='all', reduce=TopolyReduce.FULL, numbering='auth'):
    init_data = init_data_path = 'data/' + input_file
    kwargs = {}
    if input_file.lower().endswith('.cif'):
        # AUTH indexing numbers ligands/ions (no label_seq_id) consistently, so their metalc bridges are kept
        from topoly.params import ResidueIndexing
        kwargs['residue_indexing'] = ResidueIndexing.AUTH
    g = tp.Graph(init_data, chain=chain, bridges_type=bridge_type, all_atoms=True, **kwargs)
    if reduce == TopolyReduce.INTERNAL:
        g.reduce()

    def atom_node(atom):
        return f'{atom[0]}_{atom[1]}'

    edges = []
    res_nodes = {}
    atom_coords = {}

    def add_bridges(bridges, bridges_atoms, btype):
        for br, br_atoms in zip(bridges, bridges_atoms):
            u, v = br_atoms[0], br_atoms[1]
            for atom in (u, v):
                nodes = res_nodes.setdefault(atom[0], [])
                if atom_node(atom) not in nodes:
                    nodes.append(atom_node(atom))
                atom_coords[atom_node(atom)] = g.atoms.get((atom[0], atom[1]))
            edges.append([atom_node(u), atom_node(v), btype])

    add_bridges(g.bridges_disulfide, g.bridges_disulfide_atoms, 'disulfide')
    add_bridges(g.bridges_covalent, g.bridges_covalent_atoms, 'covalent')
    if g.bridges_ion:
        add_bridges(g.bridges_ion, g.bridges_ion_atoms, 'ion')
    elif not (g.bridges_disulfide or g.bridges_covalent):
        add_bridges(g.bridges, g.bridges_atoms, 'bridge')

    # the side-chain atoms forming a bridge hang off the CA of their residue
    for res, nodes in res_nodes.items():
        if (res, 'CA') in g.atoms:
            for node in nodes:
                if node != atom_node((res, 'CA')):
                    edges.append([atom_node((res, 'CA')), node, 'side chain'])

    arcs = g.arcs[:-1] if reduce == TopolyReduce.FULL else g.arcs
    for arc in arcs:
        if [arc[0], arc[-1]] in g.bridges:
            continue
        seq = []
        for res in arc:
            if res in res_nodes and (res, 'CA') not in g.atoms:
                seq.extend(res_nodes[res])
            elif res in res_nodes or reduce != TopolyReduce.FULL or res in (arc[0], arc[-1]):
                seq.append(atom_node((res, 'CA')))
        for n in range(len(seq) - 1):
            if seq[n] != seq[n + 1]:
                edges.append([seq[n], seq[n + 1], 'CA'])
    G = nx.Graph()
    nodes = set(e for edge in edges for e in edge[:2])
    for n in nodes:
        res, _, atom = n.partition('_')
        coords = atom_coords.get(n) or g.atoms.get((int(res), atom))
        G.add_node(n, coords=coords)
    for edge in edges:
        G.add_edge(edge[0], edge[1], weight=5 if edge[2] == 'CA' else 1, type=edge[2])
    if numbering == 'label' and input_file.lower().endswith('.cif'):
        to_label = {auth: label for label, auth in cif_label_to_auth(init_data_path, chain).items()}
        def relabel(name):
            res, _, atom = name.partition('_')
            new = to_label.get(int(res), res)
            return f'{new}_{atom}' if atom else f'{new}'
        G = nx.relabel_nodes(G, {n: relabel(n) for n in G.nodes()})
    return G

def _path_prefix():
    """Return the URL prefix from CONTEXT_PATH env var (default: 'spatialgraph'); empty value means root."""
    ctx = os.environ.get("CONTEXT_PATH", "spatialgraphs").strip("/")
    return f"/{ctx}/" if ctx else "/"

if __name__=="__main__":
    #os.environ['OGDF_INSTALL_DIR'] = '/usr/local'
    app=create_app(pdbid="1A8E", is_topoly=False)
    app.run(debug=True, port=8014)
