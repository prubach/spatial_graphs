"""Graph-to-view formatting and visualization helpers."""

import colorsys
from urllib.parse import quote

import networkx as nx
import numpy as np
import plotly.graph_objects as go
from dash import html

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
GRID_BACKGROUND={
    "backgroundImage":"linear-gradient(to right, #ddd 1px, transparent 1px),"
                       "linear-gradient(to bottom, #ddd 1px, transparent 1px)",
    "backgroundSize":"25px 25px",
}
SEQUENTIAL_LOW="#cde2fb"
SEQUENTIAL_HIGH="#0d366b"
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
