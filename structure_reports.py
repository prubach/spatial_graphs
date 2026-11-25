"""Persistent, graph-specific reports produced by the precomputation process."""

import fcntl
import hashlib
import json
import os
import re
import tempfile
from collections import Counter
from datetime import datetime, timezone
from xml.sax.saxutils import escape

import graph_algorithms as ga
from graph_data import TopolyReduce


VERSION = 1
PDF_VERSION = 4
SECTIONS = {
    'knotted_loops': ('Knotted loops', 'All simple cycles are tested using closed-loop HOMFLY.'),
    'k33': ('K_3,3 subdivisions', 'Results from the available OGDF and SageMath finders.'),
    'k33knot': ('Knotted K_3,3 subdivisions', 'At most 100 results, enumerated from knotted loops.'),
    'k5': ('K_5 minor models (legacy)', 'Up to 20 models from the legacy edge-deletion search.'),
    'k5knot': ('Knotted K_5 minor models (legacy)', 'Models enumerated from knotted original loops.'),
    'k5contracted': ('Contracted K_5 minors', 'Up to 20 endpoint-replacement drawings; knot preservation is not guaranteed.'),
    'k5knotcontracted': ('Knotted contracted K_5 minors', 'Up to 1,000 candidates and one contraction per model; classification disagreements are excluded.'),
    'theta': ('Theta curves', 'Up to 20 curves, at most one per branch-vertex pair; the search is not exhaustive.'),
}


def graph_identity(graph, positions, params):
    """Include the full geometry, topology, node types and input settings in the identity."""
    nodes = sorted(graph, key=lambda n: (type(n).__module__, type(n).__qualname__, repr(n)))
    keys = [(type(n).__module__, type(n).__qualname__, repr(n)) for n in nodes]
    if len(set(keys)) != len(keys) or len({str(n) for n in nodes}) != len(nodes):
        raise ValueError('Report requires uniquely identifiable node IDs')
    index = {n: i for i, n in enumerate(nodes)}
    coordinates = []
    for node in nodes:
        coords = graph.nodes[node].get('coords')
        if coords is None and positions is not None:
            coords = positions.get(node)
        if coords is None or len(coords) != 3:
            raise ValueError(f'Missing 3D coordinates for report node {node}')
        coordinates.append([float(c) for c in coords])
    settings = {key: params.get(key) for key in ('pdbid', 'chain', 'source', 'reduce', 'numbering', 'merge_residues')}
    if not settings['pdbid'] or not settings['chain'] or settings['source'] not in ('simplified', 'topoly'):
        return None
    identity = [VERSION, settings, keys, coordinates,
                sorted((min(index[u], index[v]), max(index[u], index[v]),
                        str(data.get('type')), str(data.get('weight')))
                       for u, v, data in graph.edges(data=True))]
    raw = json.dumps(identity, separators=(',', ':'), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def graph_data(graph):
    nodes = []
    for n, data in graph.nodes(data=True):
        item = {'id': str(n)}
        if data.get('coords') is not None:
            item['coords'] = [float(c) for c in data['coords']]
        if 'branch_set' in data:
            item['branch_set'] = [str(x) for x in data['branch_set']]
        nodes.append(item)
    edges = []
    for u, v, data in graph.edges(data=True):
        item = {'source': str(u), 'target': str(v)}
        for key in ('type', 'weight', 'points'):
            if key in data:
                item[key] = data[key]
        if 'source_edges' in data:
            item['source_edges'] = [[str(a), str(b)] for a, b in data['source_edges']]
        edges.append(item)
    result = {'nodes': nodes, 'edges': edges}
    for key in ('kind', 'sources', 'contraction', 'contraction_disagreements', 'contraction_disagreement_pairs',
                'theta_classification', 'theta_classification_error'):
        if key in graph.graph:
            result[key] = graph.graph[key]
    if 'source_edges' in graph.graph:
        result['source_edges'] = [[str(a), str(b)] for a, b in graph.graph['source_edges']]
    if 'knotted_loops' in graph.graph:
        expanded = ga.expand_k5_embedding(graph)
        result['knotted_loops'] = [loop_data(loop, expanded) for loop in graph.graph['knotted_loops']]
    return result


def loop_data(loop, graph=None):
    result = {**loop, 'nodes': [str(n) for n in loop['nodes']]}
    if graph is not None and graph.graph.get('strict_homfly'):
        result['original_nodes'] = [str(n) for n in ga._original_k5_cycle(graph, loop['nodes'])]
    return result


def report_location(graph, positions, params):
    digest = graph_identity(graph, positions, params)
    if digest is None:
        return None
    name = re.sub(r'[^A-Za-z0-9_-]', '_', f"{params['pdbid']}_{params['chain']}")
    return os.path.join(ga.KNOT_CACHE_DIR, 'reports', f'{name}_{digest}')


def _atomic_write(path, data):
    directory = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(prefix='.report-', dir=directory)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _subgraph_knot_summary(analyses):
    """Count subgraphs containing each type, without counting duplicate loops twice."""
    counts = Counter()
    without_knots = 0
    loop_count = 0
    for analysis in analyses:
        loops = analysis['knotted_loops']
        loop_count += len(loops)
        if not loops:
            without_knots += 1
        counts.update({loop['knot'] for loop in loops})
    return counts, loop_count, without_knots


def _pdf_status_style(status):
    """Return foreground and background colors for report and analysis statuses."""
    if status == 'complete':
        return '#17633a', '#e3f3e8'
    if status in ('partial', 'in_progress', 'running'):
        return '#765600', '#fff2bf'
    if status in ('not_precomputed', 'none', 'failed', 'skipped'):
        return '#9b2727', '#fae5e5'
    return '#475569', '#edf1f5'


def _pdf_bytes(report):
    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    buffer = BytesIO()
    styles = getSampleStyleSheet()
    body_style = ParagraphStyle('ReportBody', parent=styles['BodyText'], fontSize=9, leading=13,
                                textColor=colors.HexColor('#253449'), spaceAfter=2)
    title_style = ParagraphStyle('ReportTitle', parent=styles['Title'], fontSize=20, leading=24,
                                 textColor=colors.HexColor('#173b65'), alignment=0, spaceAfter=4)
    heading_style = ParagraphStyle('ReportHeading', parent=body_style, fontName='Helvetica-Bold',
                                   fontSize=10.5, leading=14, textColor=colors.HexColor('#173b65'))
    note_style = ParagraphStyle('ReportNote', parent=body_style, fontName='Helvetica-Oblique',
                                fontSize=8, leading=11, textColor=colors.HexColor('#526277'))
    badge_style = ParagraphStyle('ReportBadge', parent=body_style, fontName='Helvetica-Bold',
                                fontSize=8, leading=11, alignment=1)
    document = SimpleDocTemplate(buffer, title='Spatial graph report', leftMargin=36, rightMargin=36,
                                 topMargin=32, bottomMargin=38)

    def paragraph(label, value):
        return Paragraph(f'<b>{escape(label)}</b> {escape(value)}', body_style)

    def status_text(status):
        return escape(str(status).replace('_', ' '))

    def status_label(status):
        fg, _ = _pdf_status_style(status)
        return f'<font color="{fg}"><b>{status_text(status)}</b></font>'

    structure = report['structure']
    reduction = ('Internal' if str(structure['reduce']) == str(TopolyReduce.INTERNAL)
                 else str(structure['reduce']))
    body = [
        Paragraph('Spatial graph report', title_style),
        Paragraph(escape(f"{structure['pdbid']}  |  Chain {structure['chain']}"), heading_style),
        Spacer(1, 5),
        paragraph('Generated:', report['generated_at']),
        paragraph('Input:', f"Source: {structure['source']}; reduction: {reduction}; "
                           f"numbering: {structure['numbering']}; "
                           f"merged residues: {'yes' if structure['merge_residues'] else 'no'}"),
        paragraph('Graph:', f"{report['graph']['nodes']} nodes, {report['graph']['edges']} edges"),
        Spacer(1, 5),
        Paragraph('<b>Status:</b> ' + status_label('complete') + ' &nbsp; | &nbsp; '
                  + status_label('partial') + ' &nbsp; | &nbsp; ' + status_label('not_precomputed')
                  + ' / ' + status_label('failed') + ' / ' + status_label('skipped'), body_style),
        Paragraph('A completed search may have zero results. Partial or missing sections do not imply '
                  'that no results exist.', note_style),
        Paragraph('The JSON report contains the full results and subgraph data. Knot-type counts count each '
                  'subgraph once per type; a subgraph can contain multiple types. Contracted K_5 knot labels '
                  'describe original cycles, not necessarily the drawing.', note_style),
        Spacer(1, 8),
    ]
    for key, section in report['sections'].items():
        fg, bg = _pdf_status_style(section['status'])
        header = Table([[Paragraph(escape(section['title']), heading_style),
                         Paragraph(f'<font color="{fg}">{status_text(section["status"])}</font>', badge_style)]],
                       colWidths=[document.width - 115, 115], hAlign='LEFT')
        header.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#eef3f8')),
            ('BACKGROUND', (1, 0), (1, 0), colors.HexColor(bg)),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 7),
            ('RIGHTPADDING', (0, 0), (-1, -1), 7),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        header.keepWithNext = True
        body.extend([Spacer(1, 6), header, Paragraph(escape(section['limitations']), note_style)])
        if 'error' in section:
            body.append(Paragraph(f'<font color="#9b2727"><b>Error:</b> {escape(str(section["error"]))}</font>',
                                  body_style))
        if 'results' not in section:
            continue
        results = section['results']
        body.append(paragraph('Results found:', str(len(results))))
        if key == 'knotted_loops':
            labels = Counter(loop['knot'] for loop in results)
            if labels:
                body.append(paragraph('Knot types:', ', '.join(
                    f'{label}: {count}' for label, count in sorted(labels.items()))))
        elif key == 'theta':
            classifications = Counter()
            for entry in results:
                graph = entry['graph']
                if 'theta_classification_error' in graph:
                    label = 'classification failed'
                elif 'theta_classification' not in graph:
                    label = 'not classified'
                else:
                    classification = graph['theta_classification']
                    name = classification.get('name') or 'unlisted'
                    label = (classification.get('chirality') or '') + name
                classifications[label] += 1
            if classifications:
                body.append(paragraph('Theta classifications:', ', '.join(
                    f'{label}: {count}' for label, count in sorted(classifications.items()))))
        if key != 'knotted_loops' and results:
            for view in ('original', 'simplified'):
                statuses = Counter(entry.get('analysis', {}).get(view, {}).get('status', 'not_precomputed')
                                   for entry in results)
                body.append(Paragraph(f"<b>{view.capitalize()} analyses:</b> " + ', '.join(
                    f"{status_label(status)}: {count}" for status, count in sorted(statuses.items())),
                    body_style))
                analyses = [entry.get('analysis', {}).get(view, {}) for entry in results]
                completed = [analysis for analysis in analyses
                             if analysis.get('status') in ('complete', 'partial') and 'knotted_loops' in analysis]
                if completed:
                    counts, loop_count, without_knots = _subgraph_knot_summary(completed)
                    types = ', '.join(f'{label}: {count}' for label, count in sorted(counts.items())) or 'none'
                    summary = (f"{view.capitalize()} knot analysis ({len(completed)} analyzed): "
                               f"{loop_count} knotted loops; {without_knots} without knotted loops. "
                               f"Subgraphs by knot type: {types}.")
                    body.append(Paragraph(escape(summary), body_style))
            if key == 'k5knotcontracted':
                search_loops = [entry['graph']['knotted_loops'] for entry in results
                                if 'knotted_loops' in entry.get('graph', {})]
                if search_loops:
                    counts, _, _ = _subgraph_knot_summary([{'knotted_loops': loops} for loops in search_loops])
                    types = ', '.join(f'{label}: {count}' for label, count in sorted(counts.items())) or 'none'
                    body.append(Paragraph(escape(f"Search-time original-cycle knot types "
                                                 f"({len(search_loops)} analyzed): {types}."), body_style))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor('#d9e2ec'))
        canvas.line(doc.leftMargin, 27, doc.pagesize[0] - doc.rightMargin, 27)
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor('#64748b'))
        canvas.drawString(doc.leftMargin, 16, 'Spatial graph report')
        canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, 16, f'Page {doc.page}')
        canvas.restoreState()

    document.build(body, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


def _update_section(graph, positions, params, key, update):
    if key not in SECTIONS:
        raise ValueError(f'Unknown report section: {key}')
    location = report_location(graph, positions, params)
    if location is None:
        raise ValueError('Reports require a structure and chain with a supported source and reduction')
    os.makedirs(location, exist_ok=True)
    with open(os.path.join(location, '.lock'), 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        report = load_report(graph, positions, params)
        if report is None:
            report = {
                'version': VERSION, 'graph_identity': graph_identity(graph, positions, params),
                'structure': {k: params.get(k) for k in ('pdbid', 'chain', 'source', 'reduce', 'numbering', 'merge_residues')},
                'graph': {'nodes': graph.number_of_nodes(), 'edges': graph.number_of_edges()},
                'sections': {name: {'title': title, 'status': 'not_precomputed', 'limitations': limits}
                             for name, (title, limits) in SECTIONS.items()},
            }
        title, limits = SECTIONS[key]
        section = update(report['sections'][key])
        report['sections'][key] = {'title': title, 'limitations': limits, **section}
        report['generated_at'] = datetime.now(timezone.utc).isoformat()
        json_bytes = json.dumps(report, indent=2, ensure_ascii=True, allow_nan=False).encode('utf-8')
        pdf_bytes = _pdf_bytes(report)
        digest = hashlib.sha256(json_bytes).hexdigest()
        _atomic_write(os.path.join(location, digest + '.json'), json_bytes)
        _atomic_write(os.path.join(location, f'{digest}.v{PDF_VERSION}.pdf'), pdf_bytes)
        _atomic_write(os.path.join(location, 'latest.json'),
                      json.dumps({'version': VERSION, 'digest': digest, 'pdf_version': PDF_VERSION}).encode())

def publish_section(graph, positions, params, key, section):
    """Atomically publish a JSON/PDF pair, merging previously completed sections."""
    _update_section(graph, positions, params, key, lambda _: section)


def _result_key(data):
    """Match the same embedded subgraph independent of node/edge iteration order."""
    nodes = sorted(json.dumps(node, sort_keys=True) for node in data['nodes'])
    edges = []
    for edge in data['edges']:
        edge = dict(edge)
        edge['source'], edge['target'] = sorted((edge['source'], edge['target']))
        edges.append(json.dumps(edge, sort_keys=True))
    return json.dumps([data.get('kind'), nodes, sorted(edges)], sort_keys=True)


def publish_found(graph, positions, params, key, subgraphs):
    """Record an interactive family search while retaining analyses of matching results."""
    entries = [{'index': i + 1, 'graph': graph_data(sub),
                'analysis': {'original': {'status': 'not_precomputed'},
                             'simplified': {'status': 'not_precomputed'}}}
               for i, sub in enumerate(subgraphs)]
    def merge(old):
        previous = {_result_key(entry['graph']): entry for entry in old.get('results', [])}
        matched = set()
        for entry in entries:
            key = _result_key(entry['graph'])
            prior = previous.get(key)
            if prior:
                matched.add(key)
                entry['analysis'] = prior.get('analysis', entry['analysis'])
                for attr in ('theta_classification', 'theta_classification_error'):
                    if attr in prior['graph'] and attr not in entry['graph']:
                        entry['graph'][attr] = prior['graph'][attr]
        entries.extend(entry for key, entry in previous.items() if key not in matched)
        for i, entry in enumerate(entries):
            entry['index'] = i + 1
        complete = not entries or all(
            all(entry['analysis'].get(view, {}).get('status') == 'complete'
                for view in ('original', 'simplified')) for entry in entries)
        return {'status': 'complete' if complete else 'partial', 'results': entries}
    _update_section(graph, positions, params, key, merge)


def update_found(graph, positions, params, key, subgraph, view=None, detail=None, classification=None):
    """Merge a later analysis into the matching result, under the report lock."""
    result_key = _result_key(graph_data(subgraph))
    def merge(section):
        for entry in section.get('results', []):
            if _result_key(entry['graph']) != result_key:
                continue
            if classification is not None:
                entry['graph']['theta_classification'] = classification
                entry['graph'].pop('theta_classification_error', None)
            if view is not None:
                current = entry['analysis'].get(view, {'status': 'not_precomputed'})
                entry['analysis'][view] = {**current, **detail}
                if current.get('status') == 'complete' and detail.get('status') == 'partial':
                    entry['analysis'][view]['status'] = 'complete'
                if 'knotted_loops' in entry['analysis'][view] and 'homfly' in entry['analysis'][view]:
                    entry['analysis'][view]['status'] = 'complete'
            section['status'] = ('complete' if all(
                all(item.get('analysis', {}).get(v, {}).get('status') == 'complete'
                    for v in ('original', 'simplified')) for item in section['results']) else 'partial')
            break
        return section
    _update_section(graph, positions, params, key, merge)


def _report_manifest(graph, positions, params):
    location = report_location(graph, positions, params)
    if location is None:
        return None
    try:
        with open(os.path.join(location, 'latest.json'), encoding='utf-8') as f:
            manifest = json.load(f)
        digest = manifest['digest']
        if manifest['version'] != VERSION or not re.fullmatch(r'[0-9a-f]{64}', digest):
            raise ValueError('Invalid report manifest')
        return location, manifest
    except FileNotFoundError:
        return None


def report_paths(graph, positions, params):
    found = _report_manifest(graph, positions, params)
    if found is None:
        return None
    location, manifest = found
    if manifest.get('pdf_version') != PDF_VERSION:
        return None
    digest = manifest['digest']
    paths = {'json': os.path.join(location, digest + '.json'),
             'pdf': os.path.join(location, f'{digest}.v{PDF_VERSION}.pdf')}
    if not all(os.path.isfile(path) for path in paths.values()):
        raise ValueError('Incomplete report files')
    return paths


def report_json_path(graph, positions, params):
    found = _report_manifest(graph, positions, params)
    if found is None:
        return None
    location, manifest = found
    return os.path.join(location, manifest['digest'] + '.json')


def load_report(graph, positions, params):
    found = _report_manifest(graph, positions, params)
    if found is None:
        return None
    location, manifest = found
    with open(os.path.join(location, manifest['digest'] + '.json'), 'rb') as f:
        raw = f.read()
    if hashlib.sha256(raw).hexdigest() != manifest['digest']:
        raise ValueError('Report JSON does not match its manifest')
    report = json.loads(raw)
    if report['version'] != VERSION or report['graph_identity'] != graph_identity(graph, positions, params):
        raise ValueError('Report does not match the loaded graph')
    return report


def refresh_pdf(graph, positions, params):
    """Upgrade an existing report's PDF without recomputing or changing its JSON."""
    location = report_location(graph, positions, params)
    if location is None or not os.path.isdir(location):
        return False
    with open(os.path.join(location, '.lock'), 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        report = load_report(graph, positions, params)
        if report is None:
            return False
        _, manifest = _report_manifest(graph, positions, params)
        digest = manifest['digest']
        _atomic_write(os.path.join(location, f'{digest}.v{PDF_VERSION}.pdf'), _pdf_bytes(report))
        manifest['pdf_version'] = PDF_VERSION
        _atomic_write(os.path.join(location, 'latest.json'), json.dumps(manifest).encode())
        return True
