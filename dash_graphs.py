
import random
import networkx as nx
from dash import Dash, html, dcc, Input, Output
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

G=create_graph()
planar,obs=nx.check_planarity(G,counterexample=True)
pos=nx.spring_layout(G,seed=1)
obs_nodes=set(obs.nodes()) if not planar else set()
obs_edges={frozenset(e) for e in obs.edges()} if not planar else set()
obs_pos={n:pos[n] for n in obs.nodes()} if not planar else {}

app=Dash(__name__)
app.layout=html.Div([
html.H2(f"Planar: {planar}"),
dcc.RadioItems(id="mode",inline=True,value="original",options=[
{"label":"Original","value":"original"},
{"label":"Highlight obstruction","value":"highlight"},
{"label":"Obstruction only","value":"obstruction"}]),
cyto.Cytoscape(id="graph",layout={"name":"preset"},stylesheet=STYLE,
style={"width":"100%","height":"900px"})
])

@app.callback(Output("graph","elements"),Input("mode","value"))
def update(mode):
    if mode=="original":
        return build_elements(G,pos)
    if mode=="highlight":
        return build_elements(G,pos,obs_nodes,obs_edges,True)
    return build_elements(obs,obs_pos)

if __name__=="__main__":
    app.run(debug=True)
