import random
import networkx as nx

from dash import Dash, html
import dash_cytoscape as cyto
from networkx.readwrite.json_graph import cytoscape

random.seed(42)

# --------------------------------------------------------
# Generate graph
# --------------------------------------------------------

G = nx.Graph()

next_node = 0


def new_nodes(n):
    global next_node
    nodes = list(range(next_node, next_node + n))
    next_node += n
    return nodes


# -----------------------
# Overlapping K5 cliques
# -----------------------

cliques = []

shared = new_nodes(3)

for i in range(5):

    if i == 0:
        clique = shared + new_nodes(2)
    else:
        clique = random.sample(cliques[-1], 3) + new_nodes(2)

    cliques.append(clique)

    for u in clique:
        for v in clique:
            if u < v:
                G.add_edge(u, v)

# -----------------------
# K3,3 graphs
# -----------------------

for _ in range(5):

    left = random.sample(random.choice(cliques), 3)

    if random.random() < 0.5:
        right = random.sample(list(G.nodes()), 2) + new_nodes(1)
    else:
        right = new_nodes(3)

    for u in left:
        for v in right:
            G.add_edge(u, v)

# -----------------------
# Extra random edges
# -----------------------

nodes = list(G.nodes())

for _ in range(80):
    u, v = random.sample(nodes, 2)
    G.add_edge(u, v)

print(f"{G.number_of_nodes()} nodes")
print(f"{G.number_of_edges()} edges")


# --------------------------------------------------------
# Convert to Cytoscape elements
# --------------------------------------------------------

elements = []

for node in G.nodes():
    elements.append({
        "data": {
            "id": str(node),
            "label": str(node),
            "degree": G.degree[node]
        }
    })

def find_non_planar_subgraph(G):
    # Check if graph is planar
    is_planar, obstruction = nx.check_planarity(G, counterexample=True)
    if is_planar:
        return "The graph is planar. No non-planar subgraphs exist."
    else:
        print("The graph is non-planar. The Kuratowski subgraph is:")
        return obstruction

#
# obstruction_elements = []
#
# for node in obstruction.nodes():
#     obstruction_elements.append({
#         "data": {
#             "id": str(node),
#             "label": str(node),
#             "degree": obstruction.degree[node],
#         }
#     })
#
# for u, v in obstruction.edges():
#     obstruction_elements.append({
#         "data": {
#             "source": str(u),
#             "target": str(v),
#         }
#     })


for u, v in G.edges():
    elements.append({
        "data": {
            "id": str(node),
            "label": str(node),
            #"obstruction": node in obstruction_nodes,
        }
    })




# --------------------------------------------------------
# Dash
# --------------------------------------------------------


P = find_non_planar_subgraph(G)
#print(G)
#if P:
#    print(P.get_data())

app = Dash(__name__)
#cyto.use()
cyto.load_extra_layouts()
stylesheet = [

    {
        "selector": "node",
        "style": {
            "label": "data(label)",
            "width": "mapData(degree, 1, 15, 15, 45)",
            "height": "mapData(degree, 1, 15, 15, 45)",
            "background-color": "#1976d2",
            "color": "white",
            "font-size": "10px",
            "text-valign": "center",
            "text-halign": "center",
        },
    },

    {
        "selector": "edge",
        "style": {
            "width": 2,
            "line-color": "#999",
            "curve-style": "bezier",
            "opacity": 0.7,
        },
    },

    {
        "selector": ":selected",
        "style": {
            "background-color": "red",
            "line-color": "red",
            "target-arrow-color": "red",
            "source-arrow-color": "red",
        },
    },
]

app.layout = html.Div(
    [
        html.H2("Overlapping K5 and K3,3 Graph"),

        cyto.Cytoscape(
            id="graph",
            elements=elements,
            layout={
                "name": "cola",
                "quality": "proof",
                "randomize": True,
                "animate": True,
            },
            stylesheet=stylesheet,
            style={
                "width": "100%",
                "height": "900px",
            },
        ),
    ]
)

if __name__ == "__main__":
    app.run(debug=True)