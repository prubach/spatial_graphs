import colorsys
import io
import logging
import multiprocessing as mp
import os
import re
import threading
import time
import random
from urllib.parse import quote
import numpy as np
import networkx as nx
from dash import Dash, html, dcc, Input, Output, State, ctx, no_update
from dash.exceptions import PreventUpdate
import dash_cytoscape as cyto
import plotly.graph_objects as go
import topoly as tp
from topoly.params import OutputType, ReduceMethod
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

def build_elements(graph,pos,obs_nodes=set(),obs_edges=set(),highlight=False,cls="obstruction",knot_nodes=(),knot_edges=()):
    els=[]
    for n in graph.nodes():
        e={"data":{"id":str(n),"label":str(n)},"position":{"x":pos[n][0]*800,"y":pos[n][1]*800}}
        if highlight and n in obs_nodes: e["classes"]=cls
        if n in knot_nodes: e["classes"]="knotted"
        els.append(e)
    for u,v,data in graph.edges(data=True):
        edata={"source":str(u),"target":str(v)}
        edata.update(data)
        e={"data":edata}
        if highlight and frozenset((u,v)) in obs_edges: e["classes"]=cls
        if frozenset((u,v)) in knot_edges: e["classes"]="knotted"
        els.append(e)
    return els


EDGE_2D_SCALE = 10  # 2D edges are drawn this much thicker than the base width to resemble the 3D view


def _crossing_overlay_elements(elements, node_pos_3d, edge_thickness=1.0, edge_colors=None):
    """Add visual overpasses for crossings in a 2D drawing, ranked by interpolated z.
    The over strand is drawn in its edge's color from `edge_colors` (frozenset of str ids -> hex)."""
    edge_colors = edge_colors or {}
    positions = {}
    for element in elements:
        data = element.get("data", {})
        if "source" not in data:
            positions[data["id"]] = element["position"]

    edges = []
    for element in elements:
        data = element.get("data", {})
        if "source" in data and "target" in data:
            u, v = data["source"], data["target"]
            if u in positions and v in positions:
                edges.append((u, v))

    def cross(a, b):
        return a[0] * b[1] - a[1] * b[0]

    markers = []
    for i, (u, v) in enumerate(edges):
        if u not in node_pos_3d or v not in node_pos_3d:
            continue
        p = positions[u]
        q = positions[v]
        r = (q["x"] - p["x"], q["y"] - p["y"])
        for s_idx in range(i + 1, len(edges)):
            a, b = edges[s_idx]
            if {u, v} & {a, b} or a not in node_pos_3d or b not in node_pos_3d:
                continue
            c = positions[a]
            d = positions[b]
            s = (d["x"] - c["x"], d["y"] - c["y"])
            denominator = cross(r, s)
            if abs(denominator) < 1e-12:
                continue
            offset = (c["x"] - p["x"], c["y"] - p["y"])
            t = cross(offset, s) / denominator
            other_t = cross(offset, r) / denominator
            if not (1e-9 < t < 1 - 1e-9 and 1e-9 < other_t < 1 - 1e-9):
                continue

            z1 = node_pos_3d[u][2] + t * (node_pos_3d[v][2] - node_pos_3d[u][2])
            z2 = node_pos_3d[a][2] + other_t * (node_pos_3d[b][2] - node_pos_3d[a][2])
            if abs(z1 - z2) < 1e-9:
                continue
            over_start, over_end = (p, q) if z1 > z2 else (c, d)
            over_color = edge_colors.get(frozenset((u, v) if z1 > z2 else (a, b)), '#222')
            under_start, under_end = (c, d) if z1 > z2 else (p, q)

            def direction(start, end):
                dx, dy = end["x"] - start["x"], end["y"] - start["y"]
                length = (dx * dx + dy * dy) ** 0.5
                return (dx / length, dy / length) if length else (1.0, 0.0)

            over_dx, over_dy = direction(over_start, over_end)
            under_dx, under_dy = direction(under_start, under_end)
            svg = (
                '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">'
                f'<path d="M {12 - 7.5 * under_dx:.2f} {12 - 7.5 * under_dy:.2f} '
                f'L {12 + 7.5 * under_dx:.2f} {12 + 7.5 * under_dy:.2f}" '
                'stroke="white" stroke-width="9" stroke-linecap="round"/>'
                f'<path d="M {12 - 9 * over_dx:.2f} {12 - 9 * over_dy:.2f} '
                f'L {12 + 9 * over_dx:.2f} {12 + 9 * over_dy:.2f}" '
                f'stroke="{over_color}" stroke-width="5" stroke-linecap="round"/>'
                '</svg>'
            )
            x = p["x"] + t * r[0]
            y = p["y"] + t * r[1]
            markers.append({
                "data": {
                    "id": f"crossing-marker-{len(markers)}",
                    "image": f"data:image/svg+xml;utf8,{quote(svg, safe='')}",
                    "e1": [u, v], "e2": [a, b],
                    "z1": [node_pos_3d[u][2], node_pos_3d[v][2]],
                    "z2": [node_pos_3d[a][2], node_pos_3d[b][2]],
                    "c1": edge_colors.get(frozenset((u, v)), '#222'),
                    "c2": edge_colors.get(frozenset((a, b)), '#222'),
                },
                "position": {"x": x, "y": y},
                "style": {"width": 24 * EDGE_2D_SCALE * edge_thickness, "height": 24 * EDGE_2D_SCALE * edge_thickness},
                "classes": "crossing-marker",
                "selectable": False,
                "grabbable": False,
            })
    return markers


def node_scale_for(thickness):
    """2D node circle/label scale: grows with the thickness slider, but more slowly than the edges."""
    return max(thickness, 0.1) ** 0.5


def edge_thickness_stylesheet(thickness):
    """Return Cytoscape edge widths and node sizes scaled consistently with the 3D thickness control."""
    node_scale = node_scale_for(thickness)
    return [
        {"selector": "node", "style": {"width": 60 * node_scale, "height": 60 * node_scale}},
        {"selector": "node.obstruction", "style": {"width": 60 * node_scale, "height": 60 * node_scale}},
        {"selector": "node.knotted", "style": {"width": 60 * node_scale, "height": 60 * node_scale}},
        {"selector": "edge", "style": {"width": 5 * EDGE_2D_SCALE * thickness}},
        {"selector": "edge.obstruction", "style": {"width": 16 * EDGE_2D_SCALE * thickness}},
        {"selector": "edge.knotted", "style": {"width": 16 * EDGE_2D_SCALE * thickness}},
    ]


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
KNOT_COLOR="darkorange"
KNOT_STYLE=[
{"selector":".knotted","style":{"background-color":KNOT_COLOR,"line-color":KNOT_COLOR,"border-width":4,"border-color":"#4a148c",
                                "width":60,"height":60,}},
{"selector":"edge.knotted","style":{"background-color":KNOT_COLOR,"line-color":KNOT_COLOR,"width":16}},
]
STYLE=BASE_STYLE+OBSTRUCTION_STYLE+KNOT_STYLE

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

EDGE_THICKNESS_VALUES=[0.1,0.25,0.5,1,2,3,4,5]

NODE_FONT_SIZES=[8,10,12,14,16,18,20,24,28,32]

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

def build_3d_figure(graph,node_pos,obs_nodes=set(),obs_edges=set(),highlight=False,edge_colors=None,show_grid=False,thickness=1.0,font_size=18,hl_color="crimson",knot_nodes=(),knot_edges=()):
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
        obs=[(u,v) for u,v in graph.edges() if frozenset((u,v)) in obs_edges and frozenset((u,v)) not in knot_edges]
        if obs:
            traces.append(tube_mesh(obs,node_pos,hl_color,radius*2))
    knot=[(u,v) for u,v in graph.edges() if frozenset((u,v)) in knot_edges]
    if knot:
        traces.append(tube_mesh(knot,node_pos,KNOT_COLOR,radius*3))
    node_x,node_y,node_z,node_color,node_text=[],[],[],[],[]
    for n in graph.nodes():
        x,y,z=node_pos[n]
        node_x.append(x); node_y.append(y); node_z.append(z)
        node_color.append(KNOT_COLOR if n in knot_nodes else hl_color if highlight and n in obs_nodes else "#1976d2")
        node_text.append(str(n))
    traces.append(go.Scatter3d(x=node_x,y=node_y,z=node_z,mode="markers+text",
        text=node_text,textposition="top center",textfont=dict(size=font_size,color="#111"),
        marker=dict(size=6,color=node_color,line=dict(width=1,color="white")),
        hoverinfo="text",showlegend=False))
    fig=go.Figure(data=traces)
    if show_grid:
        axis_cfg=dict(visible=True,showgrid=True,gridcolor="#ccc",showticklabels=False,title="",
                      zeroline=False,showbackground=True,backgroundcolor="#f2f2f2")
    else:
        axis_cfg=dict(visible=False)
    fig.update_layout(showlegend=False,margin=dict(l=0,r=0,t=0,b=0),uirevision="keep",
        scene=dict(uirevision="keep",xaxis=axis_cfg,yaxis=axis_cfg,zaxis=axis_cfg,
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


def _find_multiple_kuratowski_subgraphs_sage(graph):
    """Finds distinct Kuratowski subgraphs with SageMath's Graph.is_planar(kuratowski=True),
    which returns one subgraph per call, so an edge of each found subgraph is removed before searching again."""
    try:
        from sage.graphs.graph import Graph as SageGraph
    except ImportError as e:
        raise RuntimeError("SageMath is not available in this Python environment (cannot import 'sage')") from e
    G = SageGraph([list(graph.nodes()), list(graph.edges())], format='vertices_and_edges')
    subgraphs = []
    while True:
        planar, cert = G.is_planar(kuratowski=True)
        if planar:
            break
        sub = nx.Graph()
        sub.add_edges_from((u, v) for u, v, *_ in cert.edges(sort=False))
        subgraphs.append(sub)
        G.delete_edge(*next(iter(sub.edges())))
    return subgraphs


def _sage_kuratowski_worker(conn, graph):
    try:
        from sage.all import ZZ
        from sage.graphs.graph import Graph as SageGraph
        import os
        import sys
        # print("Python:", sys.executable)
        # print("Working directory:", os.getcwd())
        # print("PYTHONPATH:", os.environ.get("PYTHONPATH"))
        # print("sys.path:", sys.path)
        conn.send((True, _find_multiple_kuratowski_subgraphs_sage(graph)))
    except Exception as e:
        conn.send((False, str(e)))
    finally:
        conn.close()


def find_multiple_kuratowski_subgraphs_sage(graph):
    """Run SageMath in a child process, where its signal handlers can be installed."""
    ctx = mp.get_context('fork')
    recv, send = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_sage_kuratowski_worker, args=(send, graph), daemon=True)
    try:
        proc.start()
        send.close()
        try:
            succeeded, result = recv.recv()
        except EOFError as e:
            raise RuntimeError(f"SageMath worker crashed (exit code {proc.exitcode})") from e
        if not succeeded:
            raise RuntimeError(f"SageMath worker failed: {result}")
        return result
    finally:
        send.close()
        if proc.is_alive():
            proc.kill()
        proc.join()
        recv.close()


def kuratowski_subgraph_type(subgraph):
    """Identify a Kuratowski subdivision by suppressing its degree-2 path vertices."""
    branch_nodes = {node for node, degree in subgraph.degree() if degree != 2}
    if not branch_nodes:
        return "unknown Kuratowski type"

    core = nx.Graph()
    core.add_nodes_from(branch_nodes)
    visited_edges = set()
    for start in branch_nodes:
        for neighbor in subgraph.neighbors(start):
            first_edge = frozenset((start, neighbor))
            if first_edge in visited_edges:
                continue
            visited_edges.add(first_edge)
            previous, current = start, neighbor
            while current not in branch_nodes:
                next_nodes = [node for node in subgraph.neighbors(current) if node != previous]
                if len(next_nodes) != 1:
                    break
                following = next_nodes[0]
                visited_edges.add(frozenset((current, following)))
                previous, current = current, following
            if current in branch_nodes:
                core.add_edge(start, current)

    if nx.is_isomorphic(core, nx.complete_graph(5)):
        return "K_5 subdivision (implies a K_5 minor)"
    if nx.is_isomorphic(core, nx.complete_bipartite_graph(3, 3)):
        return "K_3,3 subdivision (implies a K_3,3 minor)"
    return "unknown Kuratowski type"


def _find_k5_minor(graph, deadline, seen):
    """Search `graph` for a K_5 minor by exhaustive edge contraction (after removing degree <=1 vertices and
    suppressing degree-2 ones, which preserve K_5 minors). Every reduced vertex keeps the original tree edges
    of its branch set and every reduced edge the original edges of the path realizing it, so a hit can be
    mapped back. Returns the list of original edges of the minor model, or None."""
    adj = {u: {v: [(u, v)] for v in graph[u]} for u in graph}
    tree = {u: [] for u in graph}

    def rec(adj, tree):
        if time.monotonic() > deadline:
            raise TimeoutError
        adj = {u: dict(nb) for u, nb in adj.items()}
        tree = dict(tree)
        changed = True
        while changed:
            changed = False
            for n in list(adj):
                nb = adj[n]
                if len(nb) <= 1:
                    for m in nb:
                        del adj[m][n]
                    del adj[n]
                    changed = True
                elif len(nb) == 2:
                    (a, la), (b, lb) = nb.items()
                    del adj[a][n], adj[b][n], adj[n]
                    if b not in adj[a]:
                        adj[a][b] = adj[b][a] = la + lb + tree[n]
                    changed = True
        n_v = len(adj)
        if n_v < 5 or sum(map(len, adj.values())) < 20:
            return None
        if n_v == 5:
            return [e for u in adj for v in adj[u] if u < v for e in adj[u][v]] + [e for t in tree.values() for e in t] \
                if all(len(nb) == 4 for nb in adj.values()) else None
        key = frozenset(frozenset((u, v)) for u in adj for v in adj[u])
        if key in seen:
            return None
        seen.add(key)
        for u in list(adj):
            for v in list(adj[u]):
                if not (u < v):
                    continue
                h = {x: dict(nb) for x, nb in adj.items()}
                t = dict(tree)
                t[u] = t[u] + t[v] + h[u][v]
                del t[v]
                for w, lab in h[v].items():
                    del h[w][v]
                    if w != u and w not in h[u]:
                        h[u][w] = h[w][u] = lab
                del h[v]
                res = rec(h, t)
                if res:
                    return res
        return None

    return rec(adj, tree)


def find_k5_minors(graph, max_results=20, time_limit=60):
    """Return up to `max_results` subgraphs, each a K_5 minor model (5 connected branch sets plus the 10 edges
    joining them). After each hit one edge of the model is deleted so the next search finds a different one."""
    work = nx.Graph(graph)
    deadline = time.monotonic() + time_limit
    negative = set()
    results = []
    try:
        while max_results is None or len(results) < max_results:
            hit = None
            for comp in nx.biconnected_components(work):
                if len(comp) < 5:
                    continue
                sub = work.subgraph(comp)
                key = frozenset(frozenset(e) for e in sub.edges())
                if key in negative:
                    continue
                hit = _find_k5_minor(sub, deadline, set())
                if hit:
                    break
                negative.add(key)
            if not hit:
                break
            model = nx.Graph(hit)
            # contracted branch sets can keep dangling tree edges that no K_5 edge uses
            leaves = [n for n in model if model.degree(n) <= 1]
            while leaves:
                model.remove_nodes_from(leaves)
                leaves = [n for n in model if model.degree(n) <= 1]
            model.graph['kind'] = 'K_5 minor'
            results.append(model)
            work.remove_edge(*hit[0])
    except TimeoutError:
        log.warning('K_5 minor search stopped after %ss; %d found', time_limit, len(results))
    return results


def enumerate_k33_subdivisions(graph, must_contain=None, limit=100000):
    """All K_3,3 subdivisions of `graph` (OGDF/SageMath only report a few), as nx graphs.
    Each biconnected component is reduced to its topological core (chains of degree-2 nodes become single
    edges); a K_3,3 subdivision is what is left after deleting cyclomatic-4 core edges and pruning.
    `must_contain` (iterable of node pairs) keeps only subdivisions containing all those edges."""
    import time
    from itertools import combinations
    from math import comb
    required = {frozenset(e) for e in (must_contain or ())}
    results, unique = [], set()
    for block in nx.biconnected_components(graph):
        if len(block) < 6:
            continue
        H = graph.subgraph(block)
        branch = {n for n in H if H.degree(n) >= 3}
        if len(branch) < 6:
            continue
        chains, seen = [], set()
        for b in branch:
            for nb in H.neighbors(b):
                if frozenset((b, nb)) in seen:
                    continue
                path, prev, cur = [b, nb], b, nb
                while cur not in branch:
                    nxt = [x for x in H.neighbors(cur) if x != prev][0]
                    path.append(nxt)
                    prev, cur = cur, nxt
                for a, c in zip(path, path[1:]):
                    seen.add(frozenset((a, c)))
                chains.append((path[0], path[-1], path))
        if len(chains) - len(branch) + 1 < 4:
            continue
        # a chain that holds a required edge can never be deleted
        keep = [i for i, (_, _, path) in enumerate(chains)
                if any(frozenset(e) in required for e in zip(path, path[1:]))]
        deletable = [i for i in range(len(chains)) if i not in keep]
        r = len(chains) - len(branch) + 1 - 4
        total = comb(len(deletable), r)
        if total > 100000:
            _log(f'  K_3,3 enumeration: {total} edge-removal combinations in a block of {len(block)} nodes')
        last_log = time.time()
        for n_done, removed in enumerate(combinations(deletable, r)):
            if total > 100000 and time.time() - last_log > 10:
                last_log = time.time()
                _log(f'  K_3,3 enumeration: {n_done}/{total} combinations ({len(results)} found)')
            gone = set(removed)
            core = nx.MultiGraph()
            for i, (u, v, _) in enumerate(chains):
                if i not in gone:
                    core.add_edge(u, v, key=i)
            leaves = [n for n in core if core.degree(n) <= 1]
            while leaves:
                core.remove_nodes_from(leaves)
                leaves = [n for n in core if core.degree(n) <= 1]
            degrees = dict(core.degree())
            if (not core or max(degrees.values()) > 3 or sum(1 for d in degrees.values() if d == 3) != 6
                    or not nx.is_connected(core)):
                continue
            # chains were cut at the original branch nodes, so degree-2 ones need suppressing
            sg = nx.Graph()
            for _, _, key in core.edges(keys=True):
                sg.add_edges_from(zip(chains[key][2], chains[key][2][1:]))
            hubs = [n for n in sg if sg.degree(n) == 3]
            simple = nx.Graph()
            for h in hubs:
                for nb in sg.neighbors(h):
                    prev, cur = h, nb
                    while sg.degree(cur) == 2:
                        nxt = [x for x in sg.neighbors(cur) if x != prev][0]
                        prev, cur = cur, nxt
                    simple.add_edge(h, cur)
            if (simple.number_of_nodes() != 6 or simple.number_of_edges() != 9
                    or not nx.is_isomorphic(simple, nx.complete_bipartite_graph(3, 3))):
                continue
            key = frozenset(frozenset(e) for e in sg.edges())
            if key in unique:
                continue
            unique.add(key)
            sg.graph['kind'] = 'K_3,3'
            results.append(sg)
            if len(results) >= limit:
                return results
    return results


def find_knotted_k33_subgraphs(graph, node_pos_3d=None, params=None, limit=100):
    """K_3,3 subdivisions that contain a knotted loop of `graph`, smallest first (at most `limit`).
    OGDF/SageMath report only a few subdivisions, which can all be unknotted, so these are enumerated
    from the knotted loops: a subdivision is knotted when one of its cycles is."""
    found = {}
    loops = find_knotted_loops(graph, node_pos_3d, params=params)
    _log(f'Knotted K_3,3 search: {len(loops)} knotted loops to expand')
    # per-loop results are stored so an interrupted search resumes where it stopped
    path = _knot_cache_path(graph, node_pos_3d, 500, kind='k33knot', params=params)
    stored = (_read_json(path) or {}).get('loops', {})
    by_str = {str(n): n for n in graph.nodes()}
    for i, lp in enumerate(loops):
        key = ','.join(sorted(str(n) for n in lp['nodes']))
        if key in stored:
            subs = [nx.Graph([(by_str[u], by_str[v]) for u, v in edges]) for edges in stored[key]]
            for sg in subs:
                sg.graph['kind'] = 'K_3,3'
        else:
            subs = enumerate_k33_subdivisions(graph, must_contain=loop_edges(lp['nodes']))
            stored[key] = [[[str(u), str(v)] for u, v in sg.edges()] for sg in subs]
            _write_json(path, dict(params=dict(params or {}, kind='k33knot'), loops=stored))
        _log(f'Knotted K_3,3 search: loop {i + 1}/{len(loops)} ({len(lp["nodes"])} nodes) -> {len(subs)} K_3,3 subdivisions')
        for sg in subs:
            ek = frozenset(frozenset(e) for e in sg.edges())
            if ek not in found:
                sg.graph['kind'] = 'K_3,3'
                sg.graph['sources'] = ['knotted loop']
                found[ek] = sg
    return sorted(found.values(), key=lambda g: (g.number_of_nodes(), sorted(map(str, g.nodes()))))[:limit]


def find_knotted_k5_minors(graph, node_pos_3d=None, params=None, max_results=None, time_limit=120):
    """K_5 minor models that contain a knotted loop of `graph`.
    Unlike the K_3,3 case, K_5 minors cannot be enumerated from the loops, so models are searched
    until none remain or the time limit is reached."""
    loops = [frozenset(loop_edges(lp['nodes'])) for lp in find_knotted_loops(graph, node_pos_3d, params=params)]
    loops = [frozenset(frozenset(e) for e in lp) for lp in loops]
    results = []
    for model in find_k5_minors(graph, max_results=max_results, time_limit=time_limit):
        edges = {frozenset(e) for e in model.edges()}
        if any(lp <= edges for lp in loops):
            model.graph['kind'] = 'K_5 minor'
            model.graph['sources'] = ['knotted loop']
            results.append(model)
    return results


def find_k33_subgraphs(graph):
    """All K_3,3 subdivisions found by OGDF and SageMath, merged and deduplicated by edge set.
    Each subgraph records in graph['sources'] which finder(s) reported it; a finder that fails is skipped."""
    merged = {}
    errors = []
    for key, label, finder in (("ogdf", "OGDF", find_multiple_kuratowski_subgraphs_ogdf),
                               ("sage", "SageMath", find_multiple_kuratowski_subgraphs_sage)):
        try:
            found = finder(graph)
        except Exception as e:
            errors.append(f"{label}: {e}")
            continue
        for sg in found:
            if not kuratowski_subgraph_type(sg).startswith("K_3,3"):
                continue
            edges = frozenset(frozenset(e) for e in sg.edges())
            if edges not in merged:
                sg.graph['kind'] = 'K_3,3'
                sg.graph['sources'] = []
                merged[edges] = sg
            merged[edges].graph['sources'].append(label)
    if len(errors) == 2:
        raise RuntimeError("; ".join(errors))
    return list(merged.values())


def find_obstructions(graph, method="ogdf", **kwargs):
    """Return obstruction subgraphs found by `method`."""
    if method == "k33":
        return find_k33_subgraphs(graph)
    if method == "k5":
        return find_k5_minors(graph)
    if method == "k33knot":
        return find_knotted_k33_subgraphs(graph, **kwargs)
    if method == "k5knot":
        return find_knotted_k5_minors(graph, **kwargs)
    if method == "sage":
        return find_multiple_kuratowski_subgraphs_sage(graph)
    return find_multiple_kuratowski_subgraphs_ogdf(graph)


def simplify_subgraph_topoly(selected_graph, node_pos_3d=None, method='kmt'):
    """Simplify a subgraph (e.g. Kuratowski subdivision) by generating a Topoly
    Graph object from its 3D arcs and applying its reduce() method."""
    if selected_graph.number_of_edges() == 0:
        return selected_graph.copy()

    # Map reduction method string to topoly ReduceMethod if needed
    reduce_method = method
    if isinstance(method, str):
        from topoly.params import ReduceMethod
        method_upper = method.upper()
        if hasattr(ReduceMethod, method_upper):
            reduce_method = getattr(ReduceMethod, method_upper)

    branch_nodes = [n for n in selected_graph.nodes() if selected_graph.degree(n) != 2]
    visited = set()
    arcs = []
    for u in branch_nodes:
        for v in selected_graph.neighbors(u):
            e = frozenset((u, v))
            if e in visited:
                continue
            visited.add(e)
            path = [u, v]
            curr, prev = v, u
            while selected_graph.degree(curr) == 2 and curr not in branch_nodes:
                nbrs = [n for n in selected_graph.neighbors(curr) if n != prev]
                if not nbrs:
                    break
                nxt = nbrs[0]
                visited.add(frozenset((curr, nxt)))
                path.append(nxt)
                prev, curr = curr, nxt
            arcs.append(path)
    for u, v in selected_graph.edges():
        e = frozenset((u, v))
        if e in visited:
            continue
        visited.add(e)
        path = [u, v]
        curr, prev = v, u
        while curr != u:
            nbrs = [n for n in selected_graph.neighbors(curr) if n != prev]
            if not nbrs:
                break
            nxt = nbrs[0]
            visited.add(frozenset((curr, nxt)))
            path.append(nxt)
            prev, curr = curr, nxt
        arcs.append(path)

    node_to_id = {n: i for i, n in enumerate(selected_graph.nodes())}
    id_to_node = {i: n for n, i in node_to_id.items()}

    arcs_4d = []
    for p in arcs:
        arc = []
        for n in p:
            c = selected_graph.nodes[n].get('coords')
            if c is None and node_pos_3d is not None:
                c = node_pos_3d.get(n)
            if c is None:
                c = (0.0, 0.0, 0.0)
            arc.append([node_to_id[n], float(c[0]), float(c[1]), float(c[2])])
        arcs_4d.append(arc)

    try:
        tp_g = tp.Graph(arcs_4d)
        tp_g.reduce(method=reduce_method)
    except Exception:
        return selected_graph.copy()

    simp_g = nx.Graph()
    for n in selected_graph.nodes():
        idx = node_to_id[n]
        if idx in tp_g.coordinates:
            c = selected_graph.nodes[n].get('coords')
            if c is None and node_pos_3d is not None:
                c = node_pos_3d.get(n)
            if c is None:
                c = tuple(tp_g.coordinates[idx])
            simp_g.add_node(n, coords=c)

    for arc in tp_g.arcs:
        for i in range(len(arc) - 1):
            u = id_to_node.get(arc[i])
            v = id_to_node.get(arc[i+1])
            if u is None or v is None or u == v:
                continue
            if selected_graph.has_edge(u, v):
                attrs = dict(selected_graph[u][v])
            else:
                orig_path = None
                for p in arcs:
                    if u in p and v in p:
                        orig_path = p
                        break
                attrs = {}
                if orig_path:
                    iu, iv = orig_path.index(u), orig_path.index(v)
                    if iu > iv:
                        iu, iv = iv, iu
                    sub = orig_path[iu : iv + 1]
                    types = [selected_graph[sub[k]][sub[k+1]].get('type')
                             for k in range(len(sub) - 1)
                             if selected_graph.has_edge(sub[k], sub[k+1])]
                    bridges = [t for t in types if t in ('disulfide', 'covalent', 'ion', 'bridge', 'metalc', 'disulf')]
                    if bridges:
                        attrs['type'] = bridges[0]
                    elif 'side chain' in types:
                        attrs['type'] = 'side chain'
                    elif 'CA' in types:
                        attrs['type'] = 'CA'
                    elif types and types[0] is not None:
                        attrs['type'] = types[0]
                    if 'type' in attrs:
                        attrs['weight'] = 5 if attrs['type'] == 'CA' else 1
            simp_g.add_edge(u, v, **attrs)

    return simp_g


log = logging.getLogger(__name__)
HOMFLY_TIMEOUT = 1200
_HOMFLY_LOCK = threading.Lock()


def _homfly_call(conn, chain, tries):
    try:
        conn.send(tp.homfly(chain, closure=tp.Closure.CLOSED, run_parallel=False))
    except Exception:
        conn.send(None)
    conn.close()


def _isolated_homfly(chain, tries=None):
    # Loops are closed curves, so `tries` (random closure) is unused: closure=Closure.CLOSED.
    """Run tp.homfly in a fresh interpreter so a liblmpoly abort() only loses this chain.
    A subprocess (not fork) is used because forking this multithreaded process from several
    threads yields children with a corrupted heap ("malloc(): corrupted top size") or deadlocks."""
    import pickle
    import subprocess
    import sys
    worker = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'homfly_worker.py')
    try:
        proc = subprocess.run([sys.executable, worker], input=pickle.dumps((chain, tries)),
                              stdout=subprocess.PIPE, timeout=HOMFLY_TIMEOUT)
        return pickle.loads(proc.stdout) if proc.returncode == 0 and proc.stdout else None
    except Exception:
        return None


def _evaluate_subgraph_knot_worker(arcs_4d, node_coords_list, tries=500):
    loops = []
    try:
        tp_g = tp.Graph(arcs_4d)
        loops = list(tp_g.find_loops(output_type=OutputType.XYZ, arc_bridges=0))
    except Exception as e:
        log.warning(f"Failed to find loops via topoly: {e}")

    if not loops and node_coords_list:
        if len(node_coords_list) >= 3:
            try:
                res = _isolated_homfly(node_coords_list, tries)
                if res is None:
                    return '0_1', 1.0
                non_trivial = {k: v for k, v in res.items() if k not in ('0_1', 'TMC')}
                if non_trivial:
                    best_k = max(non_trivial, key=non_trivial.get)
                    return best_k, float(non_trivial[best_k])
                return '0_1', float(res.get('0_1', 1.0))
            except Exception:
                pass
        return '0_1', 1.0

    all_knots = []
    max_unknot_prob = 0.0
    for lp in loops:
        try:
            res = _isolated_homfly(lp, tries)
            if res is None:
                continue
            max_unknot_prob = max(max_unknot_prob, float(res.get('0_1', 0.0)))
            for k, prob in res.items():
                if k not in ('0_1', 'TMC') and prob > 0:
                    all_knots.append((k, float(prob)))
        except Exception as e:
            pass

    if all_knots:
        best_knot = max(all_knots, key=lambda x: x[1])
        return best_knot[0], best_knot[1]
    return '0_1', max_unknot_prob if max_unknot_prob > 0 else 1.0


def _parse_nxyz_loop(text):
    ids, coords = [], []
    for line in text.strip().splitlines():
        parts = line.split()
        if len(parts) == 4:
            ids.append(int(parts[0]))
            coords.append([float(parts[1]), float(parts[2]), float(parts[3])])
    return ids, coords


def classify_homfly(res, max_unknot=0.5, min_knot=0.48):
    """Return (knot_type, knot_prob, unknot_prob) if the HOMFLY result is knotted, else None."""
    if not res:
        return None
    unknot = float(res.get('0_1', 0.0))
    knots = {k: float(v) for k, v in res.items() if k not in ('0_1', 'TMC')}
    if not knots:
        return None
    best = max(knots, key=knots.get)
    if unknot < max_unknot and knots[best] >= min_knot:
        return best, knots[best], unknot
    return None


KNOT_CACHE_DIR = os.environ.get('KNOT_CACHE_DIR', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'knot_cache'))


def _knot_cache_path(graph, node_pos_3d, tries, kind='', params=None):
    """Cache file path: <pdbid>/<pdbid>_<source>_<within>_<subgraph index>_<nodes>n_<hash>.json.
    The hash covers the graph's edges, node coordinates and the HOMFLY settings, so graphs that
    differ only in e.g. simplification still get distinct files."""
    import hashlib
    params = params or {}
    h = hashlib.sha256(f'v4-closed|{tries}|{kind}'.encode())
    for n in sorted(graph.nodes(), key=str):
        c = graph.nodes[n].get('coords')
        if c is None and node_pos_3d is not None:
            c = node_pos_3d.get(n)
        h.update(f'{n}:{None if c is None else [round(float(x), 4) for x in c]};'.encode())
    for e in sorted(tuple(sorted((str(u), str(v)))) for u, v in graph.edges()):
        h.update(f'{e};'.encode())
    within = params.get('within') or kind or 'whole'
    if params.get('simplified'):
        within += '-simplified'
    index = params.get('subgraph_index')
    parts = [params.get('pdbid') or 'unknown', params.get('source') or 'unknown', within,
             '-' if index is None else str(index), f'{graph.number_of_nodes()}n', h.hexdigest()[:12]]
    parts = [re.sub(r'[^A-Za-z0-9.,+-]', '-', str(x)) for x in parts]
    return os.path.join(KNOT_CACHE_DIR, parts[0], '_'.join(parts) + '.json')


def _log(msg):
    """Progress line on the console (long searches otherwise look hung)."""
    import time
    print(f'[{time.strftime("%H:%M:%S")}] {msg}', flush=True)


def _read_json(path):
    import json
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _write_json(path, data):
    import json
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f'{path}.{os.getpid()}.{threading.get_ident()}.tmp'
        with open(tmp, 'w') as f:
            json.dump(data, f, indent=1)
        os.replace(tmp, path)
    except OSError:
        logging.warning('Could not write cache %s', path)


def loop_edges(nodes):
    """Edge set (frozensets) of the cycle through `nodes`, ignoring a repeated closing node."""
    nodes = list(nodes)
    if len(nodes) > 1 and nodes[0] == nodes[-1]:
        nodes = nodes[:-1]
    return {frozenset((nodes[i], nodes[(i + 1) % len(nodes)])) for i in range(len(nodes))}


def find_knotted_loops(graph, node_pos_3d=None, tries=500, workers=None, params=None):
    """Cached wrapper around _find_knotted_loops; results are stored as JSON files in KNOT_CACHE_DIR
    together with the `params` (PDB ID, source, reduction, numbering, ...) they were computed for, the
    nodes of the analyzed graph and every loop that was analyzed, also those without a knot."""
    import json
    path = _knot_cache_path(graph, node_pos_3d, tries, params=params)
    by_str = {str(n): n for n in graph.nodes()}
    try:
        with open(path) as f:
            data = json.load(f)
        loops = data['loops']
        for lp in loops:
            lp['nodes'] = [by_str[n] for n in lp['nodes']]
        return loops
    except (OSError, ValueError, KeyError, TypeError):
        pass
    analyzed = []
    loops = _find_knotted_loops(graph, node_pos_3d, tries, workers, analyzed=analyzed,
                                partial_path=path[:-len('.json')] + '.partial.json')
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f'{path}.{os.getpid()}.tmp'
        with open(tmp, 'w') as f:
            json.dump(dict(params=dict(params or {}, tries=tries, nodes=graph.number_of_nodes(),
                                       edges=graph.number_of_edges()),
                           nodes=[str(n) for n in graph.nodes()],
                           loops=[{**lp, 'nodes': [str(n) for n in lp['nodes']]} for lp in loops],
                           loops_analyzed=[{**a, 'nodes': [str(n) for n in a['nodes']]} for a in analyzed]),
                      f, indent=1)
        os.replace(tmp, path)
        try:
            os.remove(path[:-len('.json')] + '.partial.json')
        except OSError:
            pass
    except OSError:
        logging.warning('Could not write knot cache %s', path)
    return loops


def cached_subgraph_homfly(subgraph, node_pos_3d=None, tries=500, params=None):
    """File-cached test_obstruction_knot_homfly; failed/timed-out runs (knot_type None) are not cached."""
    import json
    path = _knot_cache_path(subgraph, node_pos_3d, tries, kind='subgraph', params=params)
    try:
        with open(path) as f:
            data = json.load(f)
        return data['knot_type'], data['prob']
    except (OSError, ValueError, KeyError):
        pass
    knot_type, prob = test_obstruction_knot_homfly(subgraph, node_pos_3d, tries=tries)
    if knot_type is not None:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = f'{path}.{os.getpid()}.tmp'
            with open(tmp, 'w') as f:
                json.dump(dict(params=dict(params or {}, tries=tries, nodes=subgraph.number_of_nodes(),
                                           edges=subgraph.number_of_edges()),
                               nodes=[str(n) for n in subgraph.nodes()],
                               knot_type=knot_type, prob=prob), f, indent=1)
            os.replace(tmp, path)
        except OSError:
            logging.warning('Could not write HOMFLY cache %s', path)
    return knot_type, prob


def _node_coords(graph, n, node_pos_3d):
    c = graph.nodes[n].get('coords')
    if c is None and node_pos_3d is not None:
        c = node_pos_3d.get(n)
    return [float(x) for x in c] if c is not None else (0.0, 0.0, 0.0)


def _find_knotted_loops(graph, node_pos_3d=None, tries=500, workers=None, analyzed=None, partial_path=None):
    """Enumerate loops of `graph` with Topoly and return those that HOMFLY classifies as knotted,
    as dicts with the loop's node sequence, knot type and probabilities (most probable first)."""
    from concurrent.futures import ThreadPoolExecutor
    nodes = list(graph.nodes())
    id_to_node = dict(enumerate(nodes))
    arcs = []
    for u, v in graph.edges():
        arc = []
        for n in (u, v):
            c = graph.nodes[n].get('coords')
            if c is None and node_pos_3d is not None:
                c = node_pos_3d.get(n)
            c = c if c is not None else (0.0, 0.0, 0.0)
            arc.append([nodes.index(n), float(c[0]), float(c[1]), float(c[2])])
        arcs.append(arc)
    if not arcs:
        return []
    import time
    t0 = time.time()
    partial = (_read_json(partial_path) or {}) if partial_path else {}
    _log(f'Enumerating loops of a graph with {len(nodes)} nodes and {len(arcs)} edges '
         f'(exponential in the number of independent cycles; counts are logged every 10s)...')
    # every simple cycle once; same set as Topoly's find_loops, which is far slower on larger graphs
    index = {n: i for i, n in enumerate(nodes)}
    unique, last = [], time.time()
    for cycle in nx.simple_cycles(nx.Graph(graph.edges())):
        if len(cycle) >= 3:
            ids = [index[n] for n in cycle]
            unique.append((ids, [list(_node_coords(graph, n, node_pos_3d)) for n in cycle]))
        if time.time() - last > 10:
            last = time.time()
            _log(f'  {len(unique)} loops enumerated so far ({last - t0:.0f}s)')
    _log(f'Found {len(unique)} loops in {time.time() - t0:.0f}s')

    def loop_key(names):
        return frozenset(frozenset((names[i], names[(i + 1) % len(names)])) for i in range(len(names)))

    # HOMFLY results of an earlier, interrupted run are reused
    entries = list(partial.get('analyzed', []))
    done = {loop_key(a['nodes']): a['homfly'] for a in entries}
    if done:
        _log(f'Resuming: {len(done)} loops already analyzed in {os.path.basename(partial_path)}')
    lock = threading.Lock()
    progress = dict(count=0, last_save=time.time(), last_log=0.0)
    total = len(unique)

    def evaluate(item):
        ids, coords = item
        names = [str(id_to_node[i]) for i in ids]
        key = loop_key(names)
        cached = key in done
        res = done[key] if cached else _isolated_homfly(coords, tries)
        loop_nodes = [id_to_node[i] for i in ids]
        verdict = classify_homfly(res)
        with lock:
            if analyzed is not None:
                analyzed.append(dict(nodes=loop_nodes, homfly=res, knotted=verdict is not None))
            if not cached:
                entries.append(dict(nodes=names, homfly=res))
            progress['count'] += 1
            now = time.time()
            if now - progress['last_log'] > 10 or progress['count'] == total:
                progress['last_log'] = now
                _log(f'HOMFLY: {progress["count"]}/{total} loops analyzed ({now - t0:.0f}s elapsed)')
            if partial_path and now - progress['last_save'] > 30:
                progress['last_save'] = now
                _write_json(partial_path, dict(analyzed=entries))
        if verdict is None:
            return None
        return dict(nodes=loop_nodes, knot=verdict[0], prob=verdict[1], unknot_prob=verdict[2])

    with ThreadPoolExecutor(max_workers=workers or min(8, os.cpu_count() or 1)) as pool:
        found = [r for r in pool.map(evaluate, unique) if r is not None]
    if partial_path:
        with lock:
            _write_json(partial_path, dict(analyzed=entries))
    _log(f'Loop analysis finished: {len(found)} knotted of {total} loops')
    return sorted(found, key=lambda r: -r['prob'])


def _homfly_child(conn, arcs_4d, node_coords_list, tries):
    conn.send(_evaluate_subgraph_knot_worker(arcs_4d, node_coords_list, tries))
    conn.close()


def test_obstruction_knot_homfly(subgraph, node_pos_3d=None, tries=500):
    """Test if the obstruction subgraph forms a knot using Topoly's HOMFLY algorithm with `tries` tries.
    Returns (knot_type, probability)."""
    if subgraph is None or subgraph.number_of_nodes() == 0 or subgraph.number_of_edges() == 0:
        return None, 0.0

    node_coords = {}
    for n in subgraph.nodes():
        coord = subgraph.nodes[n].get('coords')
        if coord is None and node_pos_3d and n in node_pos_3d:
            coord = node_pos_3d[n]
        if coord is not None:
            node_coords[n] = [float(coord[0]), float(coord[1]), float(coord[2])]

    branch_nodes = [n for n in subgraph.nodes() if subgraph.degree(n) != 2]
    if not branch_nodes and subgraph.number_of_nodes() > 0:
        branch_nodes = [next(iter(subgraph.nodes()))]

    visited = set()
    arcs = []
    for u in branch_nodes:
        for v in subgraph.neighbors(u):
            e = frozenset((u, v))
            if e in visited:
                continue
            visited.add(e)
            path = [u, v]
            curr, prev = v, u
            while subgraph.degree(curr) == 2 and curr not in branch_nodes:
                nbrs = [n for n in subgraph.neighbors(curr) if n != prev]
                if not nbrs:
                    break
                nxt = nbrs[0]
                visited.add(frozenset((curr, nxt)))
                path.append(nxt)
                prev, curr = curr, nxt
            arcs.append(path)

    for u, v in subgraph.edges():
        e = frozenset((u, v))
        if e not in visited:
            visited.add(e)
            path = [u, v]
            curr, prev = v, u
            while curr != u:
                nbrs = [n for n in subgraph.neighbors(curr) if n != prev]
                if not nbrs:
                    break
                nxt = nbrs[0]
                visited.add(frozenset((curr, nxt)))
                path.append(nxt)
                prev, curr = curr, nxt
            arcs.append(path)

    node_to_id = {n: i for i, n in enumerate(subgraph.nodes())}
    arcs_4d = []
    for p in arcs:
        arc_pts = []
        for n in p:
            coord = node_coords.get(n, [0.0, 0.0, 0.0])
            arc_pts.append([node_to_id[n], float(coord[0]), float(coord[1]), float(coord[2])])
        arcs_4d.append(arc_pts)

    node_coords_list = [node_coords[n] for n in subgraph.nodes() if n in node_coords]

    # Run in a child process: liblmpoly can abort() (buffer overflow) or hang on large
    # inputs, which must not take down the app.
    with _HOMFLY_LOCK:
        ctx = mp.get_context('fork')
        recv, send = ctx.Pipe(duplex=False)
        proc = ctx.Process(target=_homfly_child, args=(send, arcs_4d, node_coords_list, tries))
        try:
            proc.start()
            send.close()
            if recv.poll(HOMFLY_TIMEOUT):
                try:
                    return recv.recv()
                except EOFError:
                    log.warning(f"HOMFLY worker crashed (exit code {proc.exitcode})")
                    return None, 0.0
            log.warning(f"HOMFLY computation timed out after {HOMFLY_TIMEOUT}s")
            return None, 0.0
        except Exception as e:
            log.warning(f"HOMFLY worker failed: {e}")
            return None, 0.0
        finally:
            if proc.is_alive():
                proc.kill()
            proc.join()
            recv.close()


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

def merge_residue_nodes(G):
    """Collapse the atom nodes (<residue>_<atom>) of each residue into a single residue node.
    The edges inside a residue (side chain) disappear; bridges end up attached to the residue.
    The node keeps the CA coordinates when available. Between two residues a bridge edge wins
    over a backbone ('CA') edge."""
    def residue(n):
        return str(n).partition('_')[0]
    M=nx.Graph()
    coords={}
    for n,c in G.nodes(data='coords'):
        r=residue(n)
        if r not in coords or str(n).endswith('_CA'):
            coords[r]=c
    for r,c in coords.items():
        M.add_node(r,coords=c)
    for u,v,d in G.edges(data=True):
        ru,rv=residue(u),residue(v)
        if ru==rv:
            continue
        if M.has_edge(ru,rv) and d.get('type')=='CA':
            continue
        M.add_edge(ru,rv,**d)
    return M

def load_graph_by_id(pdbid,is_topoly,reduce=TopolyReduce.INTERNAL,numbering='auth',merge_residues=False):
    """Load a graph for a PDB id using either the topoly bridge extraction or
    the pre-simplified CSV/JSON pair. Returns (graph, source_label)."""
    chain = 'A'
    if len(pdbid)>4:
        chain = pdbid[4:].strip()
        pdbid = pdbid[:4]
    G,label=_load_graph(pdbid,chain,is_topoly,reduce,numbering)
    return (merge_residue_nodes(G) if merge_residues else G),label

def _load_graph(pdbid,chain,is_topoly,reduce,numbering):
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
        try:
            from topoly.params import ResidueIndexing
            kwargs['residue_indexing'] = ResidueIndexing.AUTH
        except (ImportError, AttributeError):
            pass
    try:
        g = tp.Graph(init_data, chain=chain, bridges_type=bridge_type, all_atoms=True, **kwargs)
    except TypeError:
        g = tp.Graph(init_data, chain=chain, bridges_type=bridge_type)
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
