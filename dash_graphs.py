
import random
import networkx as nx
from dash import Dash, html, dcc, Input, Output, State, ctx
import dash_cytoscape as cyto

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
    for u,v in graph.edges():
        e={"data":{"source":str(u),"target":str(v)}}
        if highlight and frozenset((u,v)) in obs_edges: e["classes"]="obstruction"
        els.append(e)
    return els

STYLE=[
{"selector":"node","style":{"label":"data(label)","background-color":"#1976d2","color":"white","width":20,"height":20,"font-size":"9px"}},
{"selector":"edge","style":{"line-color":"#999","width":2}},
{"selector":".obstruction","style":{"background-color":"crimson","line-color":"crimson","border-width":4,"border-color":"gold","width":5}},
]

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


def create_app(G=None):
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
    html.H2(f"Planar: {planar}"),
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
    dcc.Store(id="subgraph-index",data=0),
    cyto.Cytoscape(id="graph",layout={"name":"preset"},stylesheet=STYLE,
    style={"width":"100%","height":"900px"})
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


if __name__=="__main__":
    G = create_graph()
    app=create_app(G)
    app.run(debug=True)
