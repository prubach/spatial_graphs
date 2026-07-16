
import random
import networkx as nx
from dash import Dash, html, dcc, Input, Output, State, ctx
import dash_cytoscape as cyto
import topoly as tp

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
{"selector":"edge","style":{"line-color":"#999","width":2}},
]
OBSTRUCTION_STYLE=[
{"selector":".obstruction","style":{"background-color":"crimson","line-color":"crimson","border-width":4,"border-color":"gold",
                                    "width":60,"height":60,}},
{"selector":"edge.obstruction","style":{"background-color":"crimson","line-color":"crimson","border-width":4,"border-color":"gold",
                                    "width":10}},
]
STYLE=BASE_STYLE+OBSTRUCTION_STYLE

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

def find_multiple_kuratowski_subgraphs(graph):
    """Finds distinct Kuratowski subgraphs by breaking found structures."""
    G_copy = graph.copy()
    subgraphs = []

    while True:
        is_planar, certificate = nx.check_planarity(G_copy, counterexample=True)
        if is_planar:
            break

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


def create_app(G=None, title="Graph Planarity Visualization", num_nodes=None, num_edges=None):
    if G is None:
        G=create_graph()
    planar,obs=nx.check_planarity(G,counterexample=True)
    pos=nx.spring_layout(G,seed=1)
    obs_nodes=set(obs.nodes()) if not planar else set()
    obs_edges={frozenset(e) for e in obs.edges()} if not planar else set()
    obs_pos={n:pos[n] for n in obs.nodes()} if not planar else {}
    multi_subgraphs=find_multiple_kuratowski_subgraphs(G) if not planar else []

    app=Dash(__name__)
    app.layout=html.Div([
    html.H3(f"{title} - Planar: {planar}, Nodes: {num_nodes}, Edges: {num_edges}"),
    dcc.RadioItems(id="mode",inline=True,value="original",options=[
    {"label":"Original","value":"original"},
    {"label":"Highlight obstruction","value":"highlight"},
    {"label":"Obstruction only","value":"obstruction"},
    {"label":"Multiple obstructions","value":"multi"}]),
    html.Div([
    html.Button("< Prev",id="prev-btn",n_clicks=0),
    html.Button("Next >",id="next-btn",n_clicks=0),
    html.Span(id="subgraph-info",style={"marginLeft":"10px"}),
    ],style={"marginTop":"8px"}),
    html.Div([
    html.Label("Color edges by: ",style={"marginRight":"6px"}),
    dcc.Dropdown(id="edge-color-attr",clearable=False,style={"width":"220px","display":"inline-block"},
    value="none",
    options=[{"label":"None","value":"none"}]+[{"label":a,"value":a} for a in edge_attr_keys(G)]),
    html.Div(id="edge-color-legend"),
    ],style={"marginTop":"8px"}),
    dcc.Store(id="subgraph-index",data=0),
    cyto.Cytoscape(id="graph",layout={"name":"preset"},stylesheet=STYLE,
    style={"width":"100%","height":"750px"})
    ])

    @app.callback(Output("subgraph-index","data"),
    Input("prev-btn","n_clicks"),Input("next-btn","n_clicks"),
    State("subgraph-index","data"),prevent_initial_call=True)
    def navigate(prev_clicks,next_clicks,idx):
        n=len(multi_subgraphs)
        if n==0:
            return 0
        if ctx.triggered_id=="next-btn":
            return (idx+1)%n
        return (idx-1)%n

    @app.callback(Output("subgraph-info","children"),Input("subgraph-index","data"))
    def update_info(idx):
        n=len(multi_subgraphs)
        if n==0:
            return "No additional Kuratowski subgraphs found."
        return f"Found {n} Kuratowski subgraph(s) - showing {idx+1} of {n}"

    @app.callback(Output("graph","stylesheet"),Output("edge-color-legend","children"),
    Input("edge-color-attr","value"))
    def update_edge_colors(attr):
        stylesheet=BASE_STYLE+edge_color_stylesheet(G,attr)+OBSTRUCTION_STYLE
        return stylesheet,edge_color_legend(G,attr)

    @app.callback(Output("graph","elements"),Input("mode","value"),Input("subgraph-index","data"))
    def update(mode,idx):
        if mode=="original":
            return build_elements(G,pos)
        if mode=="highlight":
            return build_elements(G,pos,obs_nodes,obs_edges,True)
        if mode=="multi":
            if not multi_subgraphs:
                return build_elements(G,pos)
            sub=multi_subgraphs[idx]
            sub_nodes=set(sub.nodes())
            sub_edges={frozenset(e) for e in sub.edges()}
            return build_elements(G,pos,sub_nodes,sub_edges,True)
        return build_elements(obs,obs_pos)
    return app

def read_simlified_graph_from_file(file_path, node_list_json=None):
    G = nx.Graph()
    atoms = None
    atom_list = None
    if node_list_json:
        import json
        with open(node_list_json, 'r') as f:
            nodes = json.load(f)
            atoms = nodes.get('atoms')
            atom_list = { a['index'] : a for a in atoms } if atoms else {}
            #G.add_nodes_from(nodes)
    with open(file_path, 'r') as f:
        for line in f:
            if line.startswith('#') or not line.strip():
                continue  # Skip comments and empty lines
            parts = line.strip().split(',')
            if len(parts) == 3:
                t, u, v = parts
                if atom_list:
                    u = atom_list.get(int(u), {}).get('auth_residue_id', u)
                    v = atom_list.get(int(v), {}).get('auth_residue_id', v)
                G.add_edge(u, v, type=t)
    return G


def topoly_graph_to_networkx(input_file, chain='A', bridge_type='all'):
    g = tp.Graph('data/' + input_file, chain=chain, bridges_type=bridge_type)
    edges = []
    for n in range(len(g.arcs) - 1):
        arc = g.arcs[n]
        #if [arc[0], arc[-1]] not in g.bridges:
        edges.append([arc[0], arc[-1], 'CA'])
    for br in g.bridges_disulfide:
        edges.append([br[0], br[1], 'disulfide'])
    for br in g.bridges_covalent:
        edges.append([br[0], br[1], 'covalent'])
    for br in g.bridges_ion:
        edges.append([br[0], br[1], 'ion'])
    print(input_file + ' ' + bridge_type + ": ", end="")
    print(edges)
    G = nx.Graph()
    for edge in edges:
        G.add_edge(f'{edge[0]}', f'{edge[1]}', weight=5 if edge[2] == 'CA' else 1, type=edge[2])
    return G

if __name__=="__main__":
    pdbid = "1A8E"
    #G = create_graph()
    #G = topoly_graph_to_networkx("1AOZ.pdb", chain='A', bridge_type='all')
    G = topoly_graph_to_networkx(f'{pdbid.lower()}.pdb', chain='A', bridge_type='all')
    app = create_app(G, title=f"{pdbid}-Topoly", num_nodes=len(G.nodes()), num_edges=len(G.edges()))
    app.run(debug=True, port=8051)

    #G = read_simlified_graph_from_file(f"data/{pdbid}-A_simplified_bonds.csv", f"data/{pdbid}-A_simplified.json")
    #app=create_app(G, title=f"{pdbid}-A Simplified Graph", num_nodes=len(G.nodes()), num_edges=len(G.edges()))
    #app.run(debug=True, port=8050)
