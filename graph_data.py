"""Loading and converting the graph data used by the application."""

import os

import networkx as nx
import topoly as tp

class TopolyReduce:
    """
    Type of Topoly reduction.
    """
    NO = 0
    INTERNAL = 1
    FULL = 2


TOPOLY_REDUCE_OPTIONS = [
    {"label": "None", "value": TopolyReduce.NO},
    {"label": "Internal", "value": TopolyReduce.INTERNAL},
    {"label": "Full", "value": TopolyReduce.FULL},
]


def split_pdbid_chain(pdbid):
    """'4B56B' -> ('4B56', 'B'); a plain PDB id means chain A."""
    pdbid = (pdbid or '').strip()
    return pdbid[:4], (pdbid[4:].strip() or 'A')


def list_data_pdbids(data_dir='data'):
    """One entry per structure and chain: the PDB id with the chain appended unless it is A.
    Chains are the ones of the simplified files; structures without them are listed as chain A."""
    ids={}
    for name in os.listdir(data_dir):
        base,ext=os.path.splitext(name)
        if ext.lower() in ('.pdb','.cif'):
            ids.setdefault(base.upper(),set())
        elif name.endswith('_simplified.json'):
            pid,_,chain=name[:-len('_simplified.json')].partition('-')
            ids.setdefault(pid.upper(),set()).add(chain or 'A')
    return [pid+(chain if chain!='A' else '') for pid,chains in sorted(ids.items()) for chain in sorted(chains or {'A'})]


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
    pre-simplified JSON file. Returns (graph, source_label)."""
    pdbid,chain = split_pdbid_chain(pdbid)
    G,label=_load_graph(pdbid,chain,is_topoly,reduce,numbering)
    return (merge_residue_nodes(G) if merge_residues else G),label
def _load_graph(pdbid,chain,is_topoly,reduce,numbering):
    if is_topoly:
        #  chain='A',
        #return topoly_graph_to_networkx(f'{pdbid.upper()}.cif', chain=chain, bridge_type='all', reduce=reduce), 'Topoly'
        ext = 'cif' if os.path.exists(f'data/{pdbid.upper()}.cif') else 'pdb'
        return topoly_graph_to_networkx(f'{pdbid.upper()}.{ext}', chain=chain, bridge_type='all', reduce=reduce,
                                        numbering=numbering), 'Topoly'
    return read_simlified_graph_from_file(f"data/{pdbid.upper()}-{chain}_simplified.json",
                                           chain=chain), 'Simplified'
SIMPLIFIED_BOND_TYPES={'disulf':'disulfide','metalc':'ion'}
def read_simlified_graph_from_file(node_list_json, chain=None):
    """Read simplified bonds and atom records from JSON. Nodes are atoms named
    <residue>_<atom>, as in topoly_graph_to_networkx; covale bonds are split into
    'side chain' (inside a residue), 'CA' (simplified backbone between residues) and
    'covalent' (original bond between residues)."""
    import json
    G = nx.Graph()
    with open(node_list_json, 'r') as f:
        nodes = json.load(f)
    atom_list = {a['index']: a for a in nodes.get('atoms') or []}

    def node_of(idx, bond, number):
        atom = atom_list.get(idx)
        if atom:
            residue = atom.get('auth_residue_id', atom.get('residue_number'))
            atom_name = atom['atom']
        else:
            residue = bond.get(f'ptnr{number}_auth_residue_id')
            if residue in (None, '', '.'):
                residue = bond.get(f'ptnr{number}_residue_id')
            atom_name = bond.get(f'ptnr{number}_atom')
        name = f"{residue}_{atom_name}" if residue and atom_name else str(idx)
        if not G.has_node(name):
            coords = (atom['x'], atom['y'], atom['z']) if atom else None
            G.add_node(name, coords=coords)
        return name

    for bond in nodes.get('bonds') or []:
        if chain and not any(
            bond.get(f'ptnr{number}_auth_chain_id') == chain
            or (not bond.get(f'ptnr{number}_auth_chain_id')
                and bond.get(f'ptnr{number}_chain_id') == chain)
            for number in (1, 2)
        ):
            continue
        u_id = node_of(bond['ptnr1_id'], bond, 1)
        v_id = node_of(bond['ptnr2_id'], bond, 2)
        t = bond['conn_type']
        if t in SIMPLIFIED_BOND_TYPES:
            t = SIMPLIFIED_BOND_TYPES[t]
        elif t == 'covale':
            same_residue = u_id.partition('_')[0] == v_id.partition('_')[0]
            if same_residue:
                t = 'side chain'
            else:
                t = 'CA' if bond.get('is_simplified') else 'covalent'
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
