"""Build and query a deterministic, versioned line index over the bundled docs.

Only documented contracts equal in every archived variant of Rhino 5–8 are
shared. Original archives remain the source of provenance and implementation.
"""
import ast
import hashlib
import io
import json
import re
import textwrap
import tokenize
import warnings
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'references/catalog.zip'
MAJORS = (5, 6, 7, 8)

# Reviewed prose exceptions are pinned to the complete frozen source functions
# and variants, including docstrings/examples. Any source change invalidates the
# exception; review the new contract before updating its fingerprint. Equal prose
# still requires unchanged executable tokens and compatible explicit type labels.
REVIEWED_RS = {
    'rs.AddArc': '84bf366b231b84d4c19977ea3ad2c2dda9af53ba39bba477d6f54eed7e2126a2',
    'rs.AddBox': '60ed9db43aa942e3ba37e2c2ffbc3320d3154f101cdf14816885e850fc32bd2e',
    'rs.AddCylinder': 'f279ae0b50921316a34b136f06c9faa5db5ac337c614886f5b30ae13214fc077',
    'rs.AddGroup': '9c9ed3aa45ffb42f6b4253dda0642201253c2c3131b7523389ca94329f058e3c',
    'rs.AddInterpCurve': '392c3129fe78a6edbd56fb356652a0c608ee50d47afa21012fa17e50a7e17767',
    'rs.AddLine': '3d5e270dc75378719a6ee1091f5d27da9182383e0f4d78d98e83f36c00fbfe3c',
    'rs.AddLoftSrf': '782ee6772a1ba35c8ba77876890c6c9600057f61a5baa722f2c543646e2a4fab',
    'rs.AddMesh': '27e0e56672b1bc44948a797e229562677c94eb3d6f394c556a139763c9ccaca0',
    'rs.AddSweep1': '164d1f0ee0f74536ecd6d18e66dd05bf8a7ea4e9fe2181614cab69c68a3bfd20',
    'rs.AllObjects': 'd117eb791bfa6515dc8101164df0d1a771701aa152b06f1959edfb0f805ea0c4',
    'rs.BooleanDifference': '884f7949c0d85badf11034aa03011a066333d7dad9ce26f5f4b2163257818cd5',
    'rs.BooleanIntersection': 'a1d80a1197b2563f8b70cc6750111df663e92b327dc11d2bb90af3fe6053880a',
    'rs.BooleanUnion': '85510f5e11d0e989863b63d359e267e7bd91f8b81dbb9d31c1cf1f09c974f5e7',
    'rs.CapPlanarHoles': 'a0ca021814c7fd40dc089f75085e258344c0e3c83477ec8c8e855c245faeb1b5',
    'rs.CircleRadius': 'ff77c25814af5a2f4d9da762e9239219245aa16974a646752fb8331f4a6141a0',
    'rs.CopyObject': 'c056fba3fbb051d606d91d06d90c12ca1cf7792cec37ec88a57173e50eb13656',
    'rs.CurveClosestPoint': '61c81a7dfde23a9a978223ec8772d9a25c91d8baa050250e89bd8d9176f98408',
    'rs.CurveDegree': '881e0572a6c73e3a73ca53cad5c319f336fcce8253b93a983a2d4baf333e1abe',
    'rs.CurveLength': '11059c4c23e1eaa0cbe167383e40495bf236c252184c91b4c07eebba2095daeb',
    'rs.EnableRedraw': '7dc838cfc91c011e3aaf25dac41300ffc0dea8315df827f773f33ac4809b7a6b',
    'rs.EvaluateCurve': '0afac6dc791eb2b9f50dc8315a927c36f44242322de07ed810197b7f1185beff',
    'rs.ExeVersion': '5a0c73e0a05f4ea5a9c00a51567cbf344b72af19becb887cd3e55ef93c451587',
    'rs.ExtrudeCurveStraight': '6435fbec38df5404c263f2e6a0a1fb0d507a37d911eab0d101af405b370db72d',
    'rs.GetUserText': 'ddd19ca5723e9ae2424a156223c407439480b31c4eee60bacd4b0526f0bc91f8',
    'rs.IsMeshClosed': '62aab55011c82cd17da43ed18946118b669665555614152de6cafda86527803b',
    'rs.MeshFaceCount': 'f14627af458eb2344b24d15db19cd9c6cfce04b8ddb153e4bbe8424e88f761cd',
    'rs.MeshVertexCount': '18d025c633d0861233b759d13c5ad83f2437c945e12178045c0b74200da82764',
    'rs.MeshVolume': '75e73807baef9fa7682631ff738bbfc74ee7c7860d581a9edb8e81137709a29a',
    'rs.MoveObject': '0cbc341b94ef24555958ba587e019f50aaaee618bf72a57f0b550b2ba7ce4512',
    'rs.MoveObjects': 'f5560f60043f793288bf9efb47c66d7c7855fd6eaf5290cd342b150d2cfab332',
    'rs.ObjectLayer': '3eebfe357f8918b0b423d5fa024f3a9bfdc561112ae1979b9ac68561a03ee3c5',
    'rs.ObjectName': '196b6eaba2da00cff55aeb5d2922f4e573226b40fae95430fc222a9364c592a1',
    'rs.RotateObject': '39de4fa1f07dfb34b56a7631f12ca853ac1f4cdb8416ce6fb64e35728c096616',
    'rs.ScaleObject': 'ffeb0820a041c4f55ec78ce979233edefb52e5a16f07ded4ae4cdf4abfeda56a',
    'rs.SetUserText': '01adbab1e6491fa3d3aee10f3ee6c41893003b846f41946330f8fd766a87b999',
    'rs.SurfaceArea': '75ed19369ce044aba9b88aed41267944616c3b21495105d55fcb1a007798c9b6',
    'rs.SurfaceVolume': 'c61cd3039cdf2f1fd31f4de582d8bc81d92e9587a545b6763b2420bccafe831b',
    'rs.SurfaceVolumeCentroid': 'ebd600475ce9beba9aaf69cf8de4424a620c9f2c1d4a2e1bf1f386c3ee43094d',
    'rs.UnitSystem': '4c6ad0d6c7b47180259220708dc44ef76b0800809f906a63d78b549033439b53',
    'rs.ViewDisplayMode': '7d742da5b940f135365e2b50d010f57c7ddc58ca62bc0fecb4da945775d9a8fd',
    'rs.WorldXYPlane': '3c9482971bf27ce171527d5c34e9088bf0f42496232a1ecd13a28664f47dd0a3',
}


def wrapper_tokens(source):
    """Compare executable wrapper tokens, keeping literal values and defaults."""
    tokens = [(token.type, '' if token.type in (tokenize.INDENT, tokenize.DEDENT) else token.string)
              for token in tokenize.generate_tokens(io.StringIO(source).readline)
              if token.type not in (tokenize.COMMENT, tokenize.NL, tokenize.ENDMARKER)]
    # Function signature defaults in these archives do not contain a lambda;
    # locate its colon with balanced brackets rather than assuming the first colon.
    depth = 0
    for i, (kind, value) in enumerate(tokens):
        if kind == tokenize.OP:
            if value in ('(', '[', '{'):
                depth += 1
            elif value in (')', ']', '}'):
                depth -= 1
            elif value == ':' and depth == 0:
                j = i + 1
                while j < len(tokens) and tokens[j][0] in (tokenize.NEWLINE, tokenize.INDENT):
                    j += 1
                if j < len(tokens) and tokens[j][0] == tokenize.STRING:
                    tokens.pop(j)
                break
    return tokens


def prose_key(body):
    """Ignore only old/new parameter-label notation; implementation must also match.

    Preserve declared type labels separately so an explicit int→str change never
    becomes equal merely because both labels were removed from prose.
    """
    labels = {}
    def parameter(match):
        labels.setdefault(match[1], []).append(compact(match[2]))
        return match[1] + ' '
    body = re.sub(r'^\s*(\w+)\s*\(([^\n:]*)\)\s*:\s*', parameter, body, flags=re.M)
    body = re.sub(r'^\s*(\w+)\s*(?:\[opt\])?\s*=\s*', r'\1 ', body, flags=re.M)
    def result(match):
        labels.setdefault('return', []).append(match[1])
        return ''
    body = re.sub(r'^\s*(guid|list\[guid\]|number|int|bool|str|tuple|list\[str\]|point|float):\s*', result, body, flags=re.M)
    # Whitespace inside quoted/backticked values may be part of an I/O contract.
    # Prose layout can vary, but these literals must still compare byte-for-byte.
    literals = tuple(match[0] for match in re.finditer(
        r'''(?<!\w)(?:[rRbBuUfF]{1,2})?(["'`])(?:\\.|(?!\1).)*\1(?!\w)''', body, re.S))
    return (compact(body), literals), {key: tuple(values) for key, values in labels.items()}


def corrected_body(identity, body):
    """Correct known annotation typos against the frozen executable wrappers."""
    corrections = {
        'rs.AddArc': [('plane (str):', 'plane (plane):')],
        'rs.CurveClosestPoint': [('point (point): sampling point', 'test_point (point): sampling point')],
        'rs.ExeVersion': [('str: the major version number', 'int: the major version number')],
        'rs.RotateObject': [('axis (plane, optional):', 'axis (vector, optional):')],
        'rs.SurfaceArea': [('list(number, number):', 'tuple(number, number):')],
        'rs.SurfaceVolume': [('list(number, tuple(X, Y, Z):', 'tuple(number, number):')],
        'rs.SurfaceVolumeCentroid': [('list(point, tuple(X, Y, Z):', 'tuple(Point3d, Vector3d):')],
        'rs.ViewDisplayMode': [('str: If mode', 'str or Guid (return_name): If mode')],
    }
    changed = False
    for old, new in corrections.get(identity, []):
        if old in body:
            body = body.replace(old, new)
            changed = True
    if changed:
        body += '\n\nAnnotation corrected from the archived wrapper implementation; consult the indexed source range for the original docstring.'
    return body


def shared_python(rows):
    """Require unchanged executable wrappers as well as reviewed/equal prose."""
    if any(not row.get('shareable', True) for row in rows):
        return False
    if len({json.dumps(row['tokens']) for row in rows}) != 1:
        return False
    normalized = [prose_key(row['body']) for row in rows]
    labels = defaultdict(set)
    for _, fields in normalized:
        for name, value in fields.items():
            labels[name].add(value)
    if any(len(values) > 1 for values in labels.values()):
        return False
    return (len({key for key, _ in normalized}) == 1
            or REVIEWED_RS.get(rows[0]['id']) == review_fingerprint(rows))


def review_fingerprint(rows):
    """Bind prose exceptions to reviewed variants and their entire source functions."""
    payload = sorted((row['variant'], row['body'], row.get('source_hash', '')) for row in rows)
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False,
        separators=(',', ':')).encode('utf-8')).hexdigest()


def contract_text(doc):
    """Omit example/link sections, retaining subsequent notes or other constraints."""
    kept, skipped_indent = [], None
    for line in doc.splitlines():
        heading = re.match(r'^([ \t]*)([A-Z][A-Za-z0-9 ()/_.-]*):(?:[ \t].*)?$', line)
        if heading:
            indent = len(heading[1].expandtabs())
            if skipped_indent is None or indent <= skipped_indent:
                skipped_indent = indent if heading[2].strip() in ('Example', 'Examples', 'See Also') else None
        if skipped_indent is None:
            kept.append(line)
    return '\n'.join(kept).rstrip()


def compact(text):
    return ' '.join(text.split())


def synopsis(text):
    """Use a first-sentence preview, visibly bounded for pathological XML tables."""
    text = compact(text)
    text = re.split(r'(?<=[.!?。])\s+', text, maxsplit=1)[0]
    if len(text) > 180:
        text = text[:177].rsplit(' ', 1)[0] + '…'
    return text or 'No summary in archived source; inspect contract.'


def python_contracts(source):
    """Read real top-level Python 2/3 functions, never definitions inside strings."""
    lines = source.splitlines()
    tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    ignored = (tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT,
               tokenize.COMMENT, tokenize.ENDMARKER)
    top_lines = sorted({token.start[0] for token in tokens
                        if token.start[1] == 0 and token.type not in ignored})
    for position, token in enumerate(tokens):
        if token.type != tokenize.NAME or token.string != 'def' or token.start[1] != 0:
            continue
        name = tokens[position + 1].string
        if not name[0].isupper():
            continue
        start = token.start[0]
        # Walk preceding logical statements, so multiline/chained decorators
        # are included in provenance and cannot bypass a reviewed fingerprint.
        source_start, cursor = start, position - 1
        while cursor >= 0:
            while cursor >= 0 and tokens[cursor].type in ignored:
                cursor -= 1
            stop = cursor + 1
            while cursor >= 0 and tokens[cursor].type != tokenize.NEWLINE:
                cursor -= 1
            statement = [item for item in tokens[cursor + 1:stop] if item.type not in ignored]
            if not statement or statement[0].string != '@' or statement[0].start[1] != 0:
                break
            source_start = statement[0].start[0]
        decorated = source_start != start
        depth = 0
        for i in range(position, len(tokens)):
            current = tokens[i]
            if current.type != tokenize.OP:
                continue
            if current.string in ('(', '[', '{'):
                depth += 1
            elif current.string in (')', ']', '}'):
                depth -= 1
            elif current.string == ':' and depth == 0:
                break
        else:
            raise ValueError('Missing function signature: ' + name)
        signature_lines = lines[start - 1:current.end[0]]
        signature_lines[-1] = signature_lines[-1][:current.end[1] - 1]
        signature = ' '.join(line.strip() for line in signature_lines)[4:]
        # Do not treat continuation lines in a multi-line signature as a new
        # top-level statement. Triple-quoted strings are single tokenizer items.
        end = next((line - 1 for line in top_lines if line > current.end[0]), len(lines))
        doc = None
        for current in tokens[i + 1:]:
            if current.type in ignored:
                continue
            if current.type == tokenize.STRING:
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore', (SyntaxWarning, DeprecationWarning))
                    doc = textwrap.dedent(ast.literal_eval(current.string)).strip()
            break
        contract = contract_text(doc or '')
        function_source = '\n'.join(lines[source_start - 1:end]).rstrip()
        body = '```python\n' + signature + '\n```\n\n' + contract
        if decorated:
            body += '\n\nDecorated function; inspect the indexed source and decorator contract in the target runtime.'
        if not doc:
            body = ('Archived function has no docstring; inspect this implementation and target runtime.\n\n'
                    '```python\n' + function_source + '\n```')
        yield {'id': 'rs.' + name, 'signature': signature,
               'body': body, 'shareable': bool(doc) and not decorated, 'tokens': wrapper_tokens(function_source),
               'source_hash': hashlib.sha256(function_source.encode('utf-8')).hexdigest(),
               'summary': synopsis(re.split(r'^\s*(?:Parameters|Paramters|Returns):', contract,
                                             maxsplit=1, flags=re.M)[0]), 'start': source_start, 'end': end}


def rs_records(official):
    records = []
    for filename in ('rhinoscriptsyntax-5-7.zip', 'rhinoscriptsyntax-8.zip'):
        with zipfile.ZipFile(official / filename) as archive:
            for item in json.loads(archive.read('index.json')):
                path = item['path']
                if '/Scripts/rhinoscript/' not in path or not path.endswith('.py'):
                    continue
                branch = path.split('/')[0]
                major = 5 if branch.startswith('mac-') else int(branch.split('-')[1].split('.')[0])
                source = archive.read('text/' + path + '.txt').decode('utf-8-sig')
                for row in python_contracts(source):
                    records.append(dict(row, major=major, kind='rs', variant=branch,
                                        source=filename + '!text/' + path + '.txt'))
    return records


def xml_records(official):
    records = []
    for major in MAJORS:
        filename = 'rhinocommon-%d.zip' % major
        with zipfile.ZipFile(official / filename) as archive:
            for path in sorted(archive.namelist()):
                if not path.lower().endswith('.xml'):
                    continue
                source = archive.read(path).decode('utf-8-sig')
                offset, line_number = 0, 1
                for match in re.finditer(r'<member\s+name="[^"]+"\s*>.*?</member>', source, re.S):
                    line_number += source[offset:match.start()].count('\n')
                    start_line = line_number
                    line_number += match.group().count('\n')
                    offset = match.end()
                    member = ET.fromstring(match.group())
                    for node in member.iter():
                        if node.text and not node.text.strip():
                            node.text = None
                        if node.tail and not node.tail.strip():
                            node.tail = None
                    summary = member.find('summary')
                    summary_text = ''.join(summary.itertext()) if summary is not None else ''
                    ET.indent(member, space='  ')
                    body = ET.tostring(member, encoding='unicode')
                    records.append({'id': member.attrib['name'], 'major': major,
                                    'kind': 'rc', 'variant': path.split('/')[1],
                                    'body': '```xml\n' + body + '\n```',
                                    'summary': synopsis(summary_text),
                                    'source': filename + '!' + path,
                                    'start': start_line, 'end': line_number})
    return records


def guide_records(root):
    """Index existing Markdown sections; no second copy of hand-maintained rules."""
    refs = root / 'references'
    files = [(refs / name, MAJORS) for name in
             ('python.md', 'api-notes.md', 'computer-use.md', 'validation.md', 'documentation.md')]
    files += [(refs / 'versions' / ('%d.md' % major), (major,)) for major in MAJORS]
    files += [(refs / 'versions/8-mcp.md', (8,))]
    records = []
    for path, majors in files:
        lines = path.read_text(encoding='utf-8').splitlines()
        headings = [(i, line.lstrip('# ').strip()) for i, line in enumerate(lines)
                    if line.startswith('## ') or (i == 0 and line.startswith('# '))]
        for pos, (start, title) in enumerate(headings):
            end = headings[pos + 1][0] if pos + 1 < len(headings) else len(lines)
            while end > start and not lines[end - 1].strip():
                end -= 1
            if end == start + 1:
                continue
            apis = re.findall(r'\brs\.[A-Z]\w*\b', title) if path.name == 'api-notes.md' else []
            for major in majors:
                records.append({'id': 'guide:' + path.stem + ':' + title,
                                'major': major, 'kind': 'guide', 'variant': 'all',
                                'path': path.relative_to(root).as_posix(),
                                'start': start + 1, 'end': end, 'summary': title,
                                **({'apis': apis} if apis else {}),
                                'sha256': hashlib.sha256('\n'.join(lines[start:end]).encode('utf-8')).hexdigest()})
    return records


def mcp_records(official):
    """Index the archived tool table and every Markdown section, Rhino 8 only."""
    records = []
    filename = 'rhinomcp-docs.zip'
    with zipfile.ZipFile(official / filename) as archive:
        for path in sorted(archive.namelist()):
            if not path.endswith('.md'):
                continue
            lines = archive.read(path).decode('utf-8-sig').splitlines()
            headings = []
            fence = None
            for i, line in enumerate(lines):
                marker = re.match(r'^\s*(`{3,}|~{3,})', line)
                if marker:
                    if fence is None:
                        fence = marker[1][0]
                    elif marker[1][0] == fence:
                        fence = None
                if fence is None and re.match(r'^#{1,6} ', line):
                    headings.append((i, line.lstrip('# ').strip()))
                if path == 'README.md' and line.startswith('| `'):
                    cells = line.strip('|').split('|')
                    for name in re.findall(r'`([a-z][a-z0-9_]+)`', cells[0]):
                        records.append({'id': 'mcp:' + name, 'kind': 'mcp', 'major': 8,
                            'variant': 'archived', 'body': 'Tool: `' + name + '`\n\n' + cells[1].strip()
                            + '\n\nArchived purpose only; obtain input/output schema from live tools/list before calling.',
                            'summary': synopsis(cells[1]), 'source': filename + '!' + path,
                            'start': i + 1, 'end': i + 1, 'shareable': False})
            for position, (start, title) in enumerate(headings):
                end = headings[position + 1][0] if position + 1 < len(headings) else len(lines)
                content = '\n'.join(lines[start + 1:end]).strip()
                if not content:
                    continue
                records.append({'id': 'mcp-guide:' + path + ':' + str(start + 1) + ':' + title,
                    'kind': 'mcp', 'major': 8, 'variant': 'archived',
                    'body': ('Archived upstream section; package safety/version rules and live tools/list take precedence.\n\n'
                             + content), 'summary': synopsis(title),
                    'keywords': ' '.join(re.findall(r'\b[a-z]+(?:_[a-z0-9]+)+\b', content)),
                    'source': filename + '!' + path, 'start': start + 1, 'end': end, 'shareable': False})
    return records


def assemble(records, guides):
    """Share only all-variant/all-major equal contracts, otherwise keep deltas."""
    grouped = defaultdict(list)
    variants = defaultdict(set)
    for row in records:
        grouped[(row['kind'], row['id'])].append(row)
        variants[row['kind']].add((row['major'], row['variant']))
    documents = defaultdict(list)
    indexes = {major: [] for major in MAJORS}
    for (kind, identity), rows in sorted(grouped.items()):
        equal = (len({row['body'] for row in rows}) == 1
                 and (kind != 'rs' or shared_python(rows)))
        universal = ({(row['major'], row['variant']) for row in rows} == variants[kind]
                     and {row['major'] for row in rows} == set(MAJORS)
                     and all(row.get('shareable', True) for row in rows))
        if kind == 'rs' and universal and shared_python(rows):
            # Use the latest archived, typed explanation of the verified common
            # wrapper; original examples and prose remain in each source archive.
            canonical = next(row for row in rows if row['variant'] == 'rhino-8.30')
            rows = [dict(row, body=canonical['body'], summary=canonical['summary']) for row in rows]
            equal = True
        wrappers = defaultdict(set)
        if kind == 'rs':
            rows = [dict(row, body=corrected_body(identity, row['body'])) for row in rows]
            for row in rows:
                wrappers[(row['major'], row['body'])].add(json.dumps(row['tokens']))
        partitions = defaultdict(list)
        for row in rows:
            if kind == 'rs':
                if len(wrappers[(row['major'], row['body'])]) > 1:
                    # Identical docstrings can hide changed input/return behavior.
                    # Keep these variants distinct even inside one major's docs.
                    note = ('\n\nWrapper difference: Rhino %d / %s. This prose is shared with a different '
                            'executable wrapper; before coding, inspect this variant\'s source contract: '
                            '`references/official/%s`, lines %d–%d (inclusive).'
                            % (row['major'], row['variant'], row['source'], row['start'], row['end']))
                    row = dict(row, body=row['body'] + note)
            directory = 'common' if equal and universal else str(row['major'])
            partitions[(directory, row['body'])].append(row)
        for (directory, _), group in partitions.items():
            path = directory + '/' + kind + '.md'
            doc = documents[path]
            if not doc:
                doc.extend(['# ' + directory + ' / ' + kind, '',
                            'Generated from bundled official snapshots; read target runtime/SR constraints first.',
                            'Source archives retain implementations, examples and licenses. Documentation equality is not binary compatibility proof.', ''])
            start = len(doc) + 1
            doc.extend(['## ' + identity, ''] + group[0]['body'].splitlines() + [''])
            end = len(doc) - 1
            for row in group:
                indexes[row['major']].append({'id': identity, 'kind': kind, 'variant': row['variant'],
                    'path': path, 'start': start, 'end': end, 'summary': row['summary'],
                    'source': row['source'], 'source_start': row['start'], 'source_end': row['end'],
                    **({'keywords': row['keywords']} if row.get('keywords') else {})})
    for row in guides:
        indexes[row['major']].append({k: v for k, v in row.items() if k != 'major'})
    files = {path: '\n'.join(lines).rstrip() + '\n' for path, lines in documents.items()}
    for major, rows in indexes.items():
        rows.sort(key=lambda row: (row['kind'], row['id'], row['variant']))
        files[str(major) + '/index.jsonl'] = ''.join(json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n' for row in rows)
    return files


def build(root=ROOT):
    """Return deterministic derived docs; no file/network/application mutation."""
    official = root / 'references/official'
    return assemble(rs_records(official) + xml_records(official) + mcp_records(official), guide_records(root))


def write_catalog(files, output):
    """Write a newly named archive; callers choose whether to replace a reviewed copy."""
    with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, body in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, body.encode('utf-8'))


class Catalog:
    """One command's read snapshot; no persistent cache or cross-call state.

    Read one version index and lazily decompress each needed document once.
    Callers must use a context manager; later commands reopen current resources.
    """
    def __init__(self, major, catalog=CATALOG, root=ROOT, rs_variant=None, rc_variant=None):
        if major not in MAJORS:
            raise ValueError('Rhino major must be 5, 6, 7 or 8')
        self.major, self.path, self.root = major, catalog, Path(root)
        self.selections = {kind: value for kind, value in
                           (('rs', rs_variant), ('rc', rc_variant)) if value is not None}

    def __enter__(self):
        self.archive = zipfile.ZipFile(self.path)
        try:
            self.rows = [json.loads(line) for line in self.archive.read(
                '%d/index.jsonl' % self.major).decode('utf-8').splitlines()]
            self.by_id, self.variants = defaultdict(list), defaultdict(set)
            for row in self.rows:
                self.by_id[row['id']].append(row)
                self.variants[row['kind']].add(row['variant'])
            for kind, variant in self.selections.items():
                self.validate_variant(kind, variant)
            self.documents = {}
        except BaseException:
            self.archive.close()
            raise
        return self

    def __exit__(self, *exc):
        self.archive.close()
        self.rows = []
        self.by_id.clear()
        self.variants.clear()
        self.documents.clear()

    def validate_variant(self, kind, variant):
        if variant not in self.variants[kind]:
            raise ValueError('Rhino %d %s variant %r is not archived; choose: %s'
                             % (self.major, kind, variant, ', '.join(sorted(self.variants[kind]))))

    def lookup(self, query='', kind=None, limit=12, sources=False):
        if not 1 <= limit <= 100:
            raise ValueError('limit must be 1–100')
        terms = query.casefold().split()
        matches = [row for row in self.rows
                   if (kind is None or row['kind'] == kind)
                   and (row['kind'] not in self.selections
                        or row['variant'] == self.selections[row['kind']])
                   and all(term in (row['id'] + ' ' + row['summary'] + ' ' + row.get('keywords', '')).casefold() for term in terms)]
        grouped = {}
        for row in matches:
            key = (row['id'], row['path'], row['start'], row['end'])
            if key not in grouped:
                grouped[key] = {field: row[field] for field in ('id', 'path', 'start', 'end', 'summary')}
                grouped[key]['variants'] = []
                if sources:
                    grouped[key]['sources'] = []
            grouped[key]['variants'].append(row['variant'])
            if sources and 'source' in row:
                grouped[key]['sources'].append({field: row[field] for field in
                    ('variant', 'source', 'source_start', 'source_end')})
        matches = list(grouped.values())
        def order(row):
            identity = row['id'].casefold()
            names = {identity}
            if identity.startswith('mcp:'):
                names.add(identity[4:])
            elif identity.startswith('rs.'):
                names.add(identity[3:])
            return (query.casefold() not in names, row['id'], row['variants'])
        matches.sort(key=order)
        return {'major': self.major, 'total': len(matches), 'truncated': len(matches) > limit,
                'matches': matches[:limit]}

    def section(self, identity, variant=None):
        rows = self.by_id.get(identity, [])
        if not rows:
            raise ValueError('No indexed contract for this version/id/variant')
        kind = rows[0]['kind']
        selected = self.selections.get(kind)
        if variant is not None and selected is not None and variant != selected:
            raise ValueError('Conflicting --variant and --%s-variant' % kind)
        variant = variant if variant is not None else selected
        present = {row['variant'] for row in rows}
        if variant is not None:
            self.validate_variant(kind, variant)
            rows = [row for row in rows if row['variant'] == variant]
            if not rows:
                raise ValueError('No indexed contract for Rhino %d %s %s in %s; snapshot absence '
                                 'is not proof of runtime absence. Recorded variants: %s'
                                 % (self.major, kind, identity, variant, ', '.join(sorted(present))))
        elif present != self.variants[kind]:
            raise ValueError('Incomplete variant coverage; choose --variant or --%s-variant: %s. '
                             'Snapshot absence is not proof of runtime absence.'
                             % (kind, ', '.join(sorted(present))))
        locations = {(row['path'], row['start'], row['end']) for row in rows}
        if len(locations) != 1:
            choice = '--variant' + (' or --%s-variant' % kind if kind in ('rs', 'rc') else '')
            raise ValueError('Different contracts; choose %s: %s'
                             % (choice, ', '.join(row['variant'] for row in rows)))
        path, start, end = locations.pop()
        key = (rows[0]['kind'] == 'guide', path)
        if key not in self.documents:
            if key[0]:
                target = (self.root / path).resolve()
                if not target.is_relative_to(self.root.resolve()):
                    raise ValueError('Guide path escapes package')
                text = target.read_text(encoding='utf-8')
            else:
                text = self.archive.read(path).decode('utf-8')
            self.documents[key] = text.splitlines()
        lines = self.documents[key]
        if not 1 <= start <= end <= len(lines):
            raise ValueError('Stale line index; rebuild catalog')
        excerpt = '\n'.join(lines[start - 1:end])
        if rows[0]['kind'] == 'guide' and hashlib.sha256(excerpt.encode('utf-8')).hexdigest() != rows[0]['sha256']:
            raise ValueError('Stale guide index; rebuild catalog')
        return {'major': self.major, 'id': identity, 'variants': [row['variant'] for row in rows],
                'path': path, 'start': start, 'end': end,
                'text': excerpt}

    def sections(self, identities, variant=None, with_notes=False):
        """Resolve a whole batch, optionally adding each exact API note once.

        Notes come from this version's index; their all-version variant must not
        be filtered by a Python branch/framework selected for the API contract.
        Explicitly requested guide IDs keep their requested position.
        """
        results, emitted = [], set(identities)
        for identity in identities:
            results.append(self.section(identity, variant))
            if with_notes:
                for row in self.rows:
                    if identity in row.get('apis', []) and row['id'] not in emitted:
                        results.append(self.section(row['id']))
                        emitted.add(row['id'])
        return results


def index_rows(major, catalog=CATALOG):
    with Catalog(major, catalog) as reader:
        return reader.rows


def lookup(major, query='', kind=None, limit=12, catalog=CATALOG, sources=False,
           rs_variant=None, rc_variant=None):
    with Catalog(major, catalog, rs_variant=rs_variant, rc_variant=rc_variant) as reader:
        return reader.lookup(query, kind, limit, sources)


def section(major, identity, variant=None, catalog=CATALOG, root=ROOT,
            rs_variant=None, rc_variant=None):
    with Catalog(major, catalog, root, rs_variant, rc_variant) as reader:
        return reader.section(identity, variant)


def check(root=ROOT, catalog=CATALOG):
    """Regenerate all ranges/contracts and reject stale or incomplete artifacts."""
    expected = build(root)
    with zipfile.ZipFile(catalog) as archive:
        if set(archive.namelist()) != set(expected):
            raise ValueError('Catalog file set is stale')
        for path, body in expected.items():
            if archive.read(path) != body.encode('utf-8'):
                raise ValueError('Catalog is stale: ' + path)
    return {'valid': True, 'documents': len(expected)}
