import random
import networkx as nx

from dash import Dash, html
import dash_cytoscape as cyto


# ==========================================================
# Graph generation
# ==========================================================

def create_graph(
    n_cliques=15,
    n_bicliques=20,
    n_random_edges=80,
    seed=42,
):
    random.seed(seed)

    G = nx.Graph()

    next_node = 0

    def new_nodes(n):
        nonlocal next_node
        nodes = list(range(next_node, next_node + n))
        next_node += n
        return nodes

    # ------------------------------------------------------
    # Overlapping K5's
    # ------------------------------------------------------

    cliques = []

    shared = new_nodes(3)

    for i in range(n_cliques):

        if i == 0:
            clique = shared + new_nodes(2)
        else:
            clique = random.sample(cliques[-1], 3) + new_nodes(2)

        cliques.append(clique)

        for u in clique:
            for v in clique:
                if u < v:
                    G.add_edge(u, v)

    # ------------------------------------------------------
    # K3,3 graphs
    # ------------------------------------------------------

    for _ in range(n_bicliques):

        left = random.sample(random.choice(cliques), 3)

        if random.random() < 0.5:
            right = random.sample(list(G.nodes()), 2) + new_nodes(1)
        else:
            right = new_nodes(3)

        for u in left:
            for v in right:
                G.add_edge(u, v)

    # ------------------------------------------------------
    # Random bridges
    # ------------------------------------------------------

    nodes = list(G.nodes())

    for _ in range(n_random_edges):
        u, v = random.sample(nodes, 2)
        G.add_edge(u, v)

    return G


# ==========================================================
# Planarity
# ==========================================================

def find_obstruction(G):
    planar, obstruction = nx.check_planarity(
        G,
        counterexample=True
    )

    return planar, obstruction


# ==========================================================
# Cytoscape conversion
# ==========================================================

def cytoscape_elements(graph):

    elements = []

    for node in graph.nodes():

        elements.append({
            "data": {
                "id": str(node),
                "label": str(node),
                "degree": graph.degree[node]
            }
        })

    for u, v in graph.edges():

        elements.append({
            "data": {
                "source": str(u),
                "target": str(v)
            }
        })

    return elements


# ==========================================================
# Cytoscape style
# ==========================================================

DEFAULT_STYLE = [

    {
        "selector": "node",
        "style": {
            "label": "data(label)",
            "width": "mapData(degree,1,15,15,40)",
            "height": "mapData(degree,1,15,15,40)",
            "background-color": "#1976d2",
            "color": "white",
            "text-valign": "center",
            "text-halign": "center",
            "font-size": "10px",
        },
    },

    {
        "selector": "edge",
        "style": {
            "curve-style": "bezier",
            "width": 2,
            "line-color": "#999",
        },
    },

    {
        "selector": ":selected",
        "style": {
            "background-color": "crimson",
            "line-color": "crimson",
        },
    }

]

OBSTRUCTION_STYLE = [

    {
        "selector": "node",
        "style": {
            "label": "data(label)",
            "background-color": "crimson",
            "width": 35,
            "height": 35,
            "color": "white",
            "text-valign": "center",
        },
    },

    {
        "selector": "edge",
        "style": {
            "width": 4,
            "line-color": "crimson",
        },
    }

]


# ==========================================================
# Viewer
# ==========================================================

def graph_view(title, graph, stylesheet):

    return html.Div(

        [

            html.H3(
                f"{title} "
                f"({graph.number_of_nodes()} nodes, "
                f"{graph.number_of_edges()} edges)"
            ),

            cyto.Cytoscape(

                elements=cytoscape_elements(graph),

                layout={
                    "name": "fcose",
                    "quality": "proof",
                    "animate": True,
                },

                stylesheet=stylesheet,

                style={
                    "width": "100%",
                    "height": "850px",
                },

            )

        ],

        style={
            "flex": 1,
            "padding": "10px",
        },

    )


# ==========================================================
# Dash application
# ==========================================================

def create_app(show_obstruction=True):

    G = create_graph()
    planar, obstruction = find_obstruction(G)

    print("Planar:", planar)
    cyto.load_extra_layouts()

    app = Dash(__name__)

    children = [
        graph_view(
            "Original graph",
            G,
            DEFAULT_STYLE,
        )
    ]

    if (not planar) and show_obstruction:

        children.append(

            graph_view(
                "Kuratowski obstruction",
                obstruction,
                OBSTRUCTION_STYLE,
            )

        )

    app.layout = html.Div(

        [

            html.H2(
                f"Planarity: {'PLANAR' if planar else 'NON-PLANAR'}"
            ),

            html.Div(

                children,

                style={
                    "display": "flex",
                    "flexDirection": "row",
                },

            )

        ]

    )

    return app


# ==========================================================
# Main
# ==========================================================

if __name__ == "__main__":

    app = create_app(show_obstruction=True)

    app.run(debug=True)