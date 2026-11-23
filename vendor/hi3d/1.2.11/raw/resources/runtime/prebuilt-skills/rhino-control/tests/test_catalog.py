"""Offline contract/range regressions; these tests do not run a Rhino kernel."""
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import catalog
import docs


class CatalogContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = {major: catalog.index_rows(major) for major in catalog.MAJORS}

    def test_all_xml_members_and_public_python_functions_are_indexed(self):
        official = catalog.ROOT / 'references/official'
        expected = catalog.rs_records(official)
        actual = {(major, row['variant'], row['id']) for major, rows in self.rows.items()
                  for row in rows if row['kind'] == 'rs'}
        self.assertEqual(actual, {(row['major'], row['variant'], row['id']) for row in expected})
        for major in catalog.MAJORS:
            with zipfile.ZipFile(official / ('rhinocommon-%d.zip' % major)) as archive:
                for name in archive.namelist():
                    if name.lower().endswith('.xml'):
                        members = ET.fromstring(archive.read(name)).findall('./members/member')
                        expected_ids = {member.attrib['name'] for member in members}
                        actual_ids = {row['id'] for row in self.rows[major]
                                      if row['kind'] == 'rc' and row['variant'] == name.split('/')[1]}
                        self.assertEqual(actual_ids, expected_ids)

    def test_every_range_selects_exactly_one_complete_contract(self):
        with zipfile.ZipFile(catalog.CATALOG) as archive:
            documents = {name: archive.read(name).decode('utf-8').splitlines()
                         for name in archive.namelist() if name.endswith('.md')}
        locations = {}
        for rows in self.rows.values():
            for row in rows:
                if row['kind'] == 'guide':
                    continue
                key = (row['path'], row['start'], row['end'])
                locations[key] = row['id']
                lines = documents[row['path']]
                self.assertGreaterEqual(row['start'], 1)
                self.assertLessEqual(row['end'], len(lines))
                excerpt = lines[row['start'] - 1:row['end']]
                self.assertEqual(excerpt[0], '## ' + row['id'])
                self.assertFalse(any(line.startswith('## ') for line in excerpt[1:]))
                if row['kind'] == 'rc':
                    self.assertIn('</member>', '\n'.join(excerpt))
        # Every physical contract has an index, with no unindexed generated tail.
        count = sum(sum(line.startswith('## ') for line in lines) for lines in documents.values())
        self.assertEqual(len(locations), count)

    def test_common_contracts_cover_every_archived_variant(self):
        variants = defaultdict(set)
        common = defaultdict(set)
        for major, rows in self.rows.items():
            for row in rows:
                if row['kind'] == 'guide':
                    continue
                variants[row['kind']].add((major, row['variant']))
                if row['path'].startswith('common/'):
                    common[(row['kind'], row['id'])].add((major, row['variant']))
        for (kind, identity), present in common.items():
            with self.subTest(id=identity):
                self.assertEqual(present, variants[kind])

    def test_same_prose_different_wrappers_require_a_variant(self):
        # These archived implementations actually differ in output/input rules,
        # although their docstrings are identical within the major version.
        for major, identity, variants in (
            (5, 'rs.DocumentPath', ('rhino-5', 'mac-rhino-5.0')),
            (8, 'rs.AddPictureFrame', ('rhino-8.0', 'rhino-8.30')),
        ):
            with self.subTest(major=major), catalog.Catalog(major) as reader:
                with self.assertRaisesRegex(ValueError, 'choose --variant'):
                    reader.section(identity)
                rows = reader.lookup(identity, kind='rs')['matches']
                self.assertEqual(len(rows), 2)
                self.assertNotEqual(rows[0]['start'], rows[1]['start'])
                for variant in variants:
                    result = reader.section(identity, variant)
                    self.assertEqual(result['variants'], [variant])
                    self.assertIn('Wrapper difference:', result['text'])
                    self.assertIn('references/official/rhinoscriptsyntax-', result['text'])

    def test_partial_platform_coverage_never_silently_selects_mac(self):
        with catalog.Catalog(5) as reader:
            for identity in ('rs.LockedObjects', 'rs.PointArrayBoundingBox'):
                with self.assertRaisesRegex(ValueError, 'Incomplete variant coverage'):
                    reader.section(identity)
                self.assertEqual(reader.section(identity, 'mac-rhino-5.0')['variants'], ['mac-rhino-5.0'])
                with self.assertRaisesRegex(ValueError, 'snapshot absence'):
                    reader.section(identity, 'rhino-5')

    def test_per_kind_variants_cover_all_archived_platforms_and_frameworks(self):
        for major, python_variants, frameworks in (
            (5, ('rhino-5', 'mac-rhino-5.0'), ('net35',)),
            (6, ('rhino-6.0',), ('net45',)),
            (7, ('rhino-7.0',), ('net48',)),
            (8, ('rhino-8.0', 'rhino-8.30'), ('net48', 'net7.0')),
        ):
            for rs_variant in python_variants:
                for rc_variant in frameworks:
                    with self.subTest(major=major, rs=rs_variant, rc=rc_variant), catalog.Catalog(
                            major, rs_variant=rs_variant, rc_variant=rc_variant) as reader:
                        api = reader.lookup('rs.AddBox', kind='rs')['matches'][0]
                        self.assertEqual(api['variants'], [rs_variant])
                        rc = reader.lookup('T:Rhino.Geometry.Point3d', kind='rc')['matches'][0]
                        self.assertEqual(rc['variants'], [rc_variant])
                        guide = next(row['id'] for row in reader.rows if row['id'].startswith('guide:%d:' % major))
                        results = reader.sections(['rs.AddBox', rc['id'], guide], with_notes=True)
                        self.assertEqual([row['variants'] for row in results],
                                         [[rs_variant], ['all'], [rc_variant], ['all']])
        for kwargs in ({'rs_variant': 'rhino-8.30'}, {'rc_variant': 'net7.0'}):
            with self.assertRaisesRegex(ValueError, 'is not archived'):
                with catalog.Catalog(5, **kwargs):
                    pass
        with catalog.Catalog(8, rs_variant='rhino-8.30') as reader:
            with self.assertRaisesRegex(ValueError, 'Conflicting'):
                reader.section('rs.AddBox', 'rhino-8.0')

    def test_cli_mixed_branch_framework_and_guide_batch(self):
        cli = catalog.ROOT / 'scripts/docs.py'
        args = [sys.executable, str(cli), 'section', '--major', '8', '--rs-variant', 'rhino-8.30',
                '--rc-variant', 'net7.0', '--with-notes', '--id', 'rs.ClosedCurveOrientation',
                '--id', 'rs.AddBox', '--id', 'M:Rhino.RhinoDoc.WriteFile(System.String,Rhino.FileIO.FileWriteOptions)',
                '--id', 'guide:8:运行时、SR 与 MCP']
        output = subprocess.check_output(args, text=True)
        for marker in ('[rhino-8.30]', '[net7.0]', '[all]', '8 点'):
            self.assertIn(marker, output)
        failure = subprocess.run(args + ['--id', 'missing-api'], text=True, capture_output=True)
        self.assertEqual(failure.returncode, 1)
        self.assertEqual(failure.stdout, '')
        filtered = json.loads(subprocess.check_output([sys.executable, str(cli), 'lookup', '--major', '5',
            '--rs-variant', 'rhino-5', '--kind', 'rs', '--query', 'rs.LockedObjects'], text=True))
        self.assertEqual(filtered['total'], 0)

    def test_lookup_and_read_are_bounded_and_version_aware(self):
        found = catalog.lookup(8, 'rs.AddBox', kind='rs')
        self.assertEqual(found['total'], 1)
        self.assertEqual(found['matches'][0]['variants'], ['rhino-8.0', 'rhino-8.30'])
        result = catalog.section(5, 'rs.AddBox')
        self.assertIn('AddBox(corners)', result['text'])
        self.assertIn('Returns:', result['text'])
        self.assertNotIn('AddCone', result['text'])
        self.assertNotIn('str:', catalog.lookup(5, 'rs.ExeVersion')['matches'][0]['summary'])
        self.assertLess(len(result['text']), 1000)
        self.assertFalse(catalog.lookup(5, 'ScriptEditor', 'guide')['matches'])
        self.assertTrue(catalog.lookup(8, 'execute_rhinoscript_python_code', 'guide')['matches'])
        for major in catalog.MAJORS:
            # Pick an actual ambiguous contract, rather than assuming a specific
            # API changes forever as upstream snapshots are maintained.
            by_id = defaultdict(set)
            for row in self.rows[major]:
                by_id[row['id']].add((row['path'], row['start'], row['end']))
            identity = next((key for key, values in by_id.items() if len(values) > 1), None)
            if identity:
                with self.assertRaisesRegex(ValueError, 'choose --variant'):
                    catalog.section(major, identity)
                row = next(row for row in self.rows[major] if row['id'] == identity)
                self.assertTrue(catalog.section(major, identity, row['variant'])['text'])
        with self.assertRaises(ValueError):
            catalog.lookup(9, 'AddBox')
        with self.assertRaises(ValueError):
            catalog.lookup(5, limit=0)
        with self.assertRaises(ValueError):
            catalog.section(5, 'M:Missing.Member')

    def test_changed_body_types_defaults_and_indent_are_not_shared(self):
        def row(major, source):
            item = next(catalog.python_contracts(source))
            return dict(item, major=major, kind='rs', variant='rhino-' + str(major) + ('.30' if major == 8 else ''), source='fixture.py')
        base = 'def Example(value=1):\n    """Convert value.\n    Returns:\n      int: result\n    """\n    return value\n'
        for modified in (base.replace('return value', 'return [value]'),
                         base.replace('value=1', 'value=2'), base.replace('int: result', 'str: result')):
            rows = [row(major, modified if major == 8 else base) for major in catalog.MAJORS]
            files = catalog.assemble(rows, [])
            self.assertNotIn('common/rs.md', files)
        self.assertNotEqual(catalog.wrapper_tokens('def X():\n    if flag:\n        return 1\n    return 2\n'),
                            catalog.wrapper_tokens('def X():\n    if flag:\n        return 1\n        return 2\n'))

    def test_parser_preserves_literals_and_ignores_definitions_in_docstrings(self):
        source = ('def Example(text="a  b",\n            count=2):\n'
                  '    """Convert text.\ndef Fake():\n    ignored\n'
                  '    Parameters:\n      text = input\n    Returns:\n      text\n    """\n'
                  '    return text\n\ndef Missing():\n    return None\n')
        rows = list(catalog.python_contracts(source))
        self.assertEqual([row['id'] for row in rows], ['rs.Example', 'rs.Missing'])
        self.assertIn('"a  b"', rows[0]['signature'])
        self.assertEqual(source.splitlines()[rows[0]['end']], 'def Missing():')
        self.assertIn('return None', rows[1]['body'])
        self.assertFalse(rows[1]['shareable'])

    def test_reviewed_exception_expires_when_source_or_contract_changes(self):
        rows = [row for row in catalog.rs_records(catalog.ROOT / 'references/official')
                if row['id'] == 'rs.AddBox']
        self.assertTrue(catalog.shared_python(rows))
        changed = [dict(row) for row in rows]
        changed[-1]['body'] += '\nNotes:\n    Rhino 8 requires custom units.'
        self.assertFalse(catalog.shared_python(changed))
        self.assertNotIn('common/rs.md', catalog.assemble(changed, []))
        # Even a source/example change omitted from the short body invalidates
        # the manual exception, pending another review of the original source.
        changed = [dict(row) for row in rows]
        changed[-1]['source_hash'] = 'changed-source'
        self.assertFalse(catalog.shared_python(changed))
        last = rows[-1]
        filename, member = last['source'].split('!', 1)
        with zipfile.ZipFile(catalog.ROOT / 'references/official' / filename) as archive:
            source = archive.read(member).decode('utf-8-sig')
        injected = source.replace('def AddBox(', '@outer\n@new_contract(\n    mode="new"\n)\ndef AddBox(', 1)
        decorated = next(row for row in catalog.python_contracts(injected) if row['id'] == 'rs.AddBox')
        self.assertEqual(injected.splitlines()[decorated['start'] - 1], '@outer')
        self.assertNotEqual(last['source_hash'], decorated['source_hash'])
        self.assertFalse(decorated['shareable'])
        self.assertFalse(catalog.shared_python(rows[:-1] + [dict(last, **decorated)]))

    def test_notes_after_examples_and_quoted_values_remain_contracts(self):
        template = ('def Example(value):\n    """Return exactly `{literal}`.\n'
                    '    Example:\n        Example(1)\n'
                    '    Notes:\n        Requires custom units.\n'
                    '    See Also:\n        OtherFunction\n'
                    '    Raises:\n        ValueError on negative input.\n'
                    '    """\n    return value\n')
        rows = [dict(next(catalog.python_contracts(template.format(literal=literal))), variant=str(i))
                for i, literal in enumerate(('a b', 'a  b'))]
        body = rows[0]['body']
        self.assertIn('Requires custom units.', body)
        self.assertIn('ValueError on negative input.', body)
        self.assertNotIn('OtherFunction', body)
        self.assertNotIn('Example(1)', body)
        self.assertFalse(catalog.shared_python(rows))
        for heading in ('Notes (Rhino 8):', 'Version 8:', 'Notes: Requires Rhino 8.'):
            doc = 'Example:\n    if id:\n        print(id)\n' + heading + '\n    Requires custom units.'
            kept = catalog.contract_text(doc)
            self.assertIn(heading, kept)
            self.assertIn('Requires custom units.', kept)
            self.assertNotIn('print(id)', kept)
        for quote in ('"', "'", '`'):
            for prefix in ('', 'r', 'b', 'u', 'f', 'rb', 'fr'):
                before = 'Return exactly ' + prefix + quote + 'a b' + quote + '.'
                after = before.replace('a b', 'a  b')
                self.assertNotEqual(catalog.prose_key(before), catalog.prose_key(after))

    def test_batch_reads_each_index_and_document_once_without_persistent_cache(self):
        reads = []
        original = zipfile.ZipFile.read
        def counted(archive, name, *args, **kwargs):
            reads.append(name)
            return original(archive, name, *args, **kwargs)
        with patch.object(zipfile.ZipFile, 'read', counted):
            with catalog.Catalog(8) as reader:
                for name in ('rs.AddBox', 'rs.SurfaceVolume', 'rs.AddBox'):
                    self.assertEqual(reader.lookup(name)['matches'][0]['id'], name)
                    self.assertIn('Returns:', reader.section(name)['text'])
            self.assertEqual(reads, ['8/index.jsonl', 'common/rs.md'])
            self.assertIsNone(reader.archive.fp)
            catalog.section(8, 'rs.AddBox')
            self.assertEqual(reads, ['8/index.jsonl', 'common/rs.md'] * 2)

    def test_stale_guide_fails_instead_of_returning_wrong_lines(self):
        row = next(row for row in self.rows[8] if row['kind'] == 'guide')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / row['path']
            target.parent.mkdir(parents=True)
            target.write_text((catalog.ROOT / row['path']).read_text(), encoding='utf-8')
            self.assertTrue(catalog.section(8, row['id'], root=root)['text'])
            target.write_text('inserted line\n' + target.read_text(), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Stale'):
                catalog.section(8, row['id'], root=root)

    def test_cli_batch_and_original_source_line_read(self):
        cli = catalog.ROOT / 'scripts/docs.py'
        found = json.loads(subprocess.check_output([sys.executable, str(cli), 'lookup', '--major', '7',
            '--query', 'rs.AddBox', '--query', 'rs.SurfaceVolume'], text=True))
        self.assertEqual([row['query'] for row in found], ['rs.AddBox', 'rs.SurfaceVolume'])
        self.assertEqual(found[0]['matches'][0]['id'], 'rs.AddBox')
        compact = subprocess.check_output([sys.executable, str(cli), 'lookup', '--major', '7',
            '--query', 'rs.AddBox', '--query', 'missing-api', '--format', 'text', '--sources'], text=True)
        self.assertIn('total=0 | truncated=false', compact)
        row = found[0]['matches'][0]
        self.assertIn('%s | %s:%d-%d | %s | %s' % (row['id'], row['path'], row['start'],
            row['end'], ','.join(row['variants']), row['summary']), compact)
        self.assertIn('rhinoscriptsyntax-5-7.zip!', compact)
        output = subprocess.check_output([sys.executable, str(cli), 'section', '--major', '7',
                                          '--id', 'rs.AddBox', '--id', 'rs.CapPlanarHoles'], text=True)
        self.assertIn('common/rs.md:', output)
        self.assertIn('CapPlanarHoles(surface_id)', output)
        failed = subprocess.run([sys.executable, str(cli), 'section', '--major', '7',
            '--id', 'rs.AddBox', '--id', 'missing-api'], text=True, capture_output=True)
        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual(failed.stdout, '')
        self.assertNotIn('Traceback', failed.stderr)
        self.assertIn('No indexed contract', failed.stderr)
        row = next(row for row in self.rows[7] if row['id'] == 'rs.AddBox')
        filename, path = row['source'].split('!', 1)
        output = subprocess.check_output([sys.executable, str(cli), 'read',
            str(catalog.ROOT / 'references/official' / filename), path[5:-4],
            '--start-line', str(row['source_start']), '--end-line', str(row['source_end'])], text=True)
        self.assertTrue(output.startswith('def AddBox(corners):'))
        self.assertNotIn('def AddCone', output)

    def test_api_notes_follow_exact_ids_and_are_complete_deduplicated_ranges(self):
        for major in catalog.MAJORS:
            with catalog.Catalog(major) as reader:
                notes = [row for row in reader.rows if row.get('apis')]
                known_ids = {row['id'] for row in reader.rows if row['kind'] == 'rs'}
                self.assertTrue(notes)
                for note in notes:
                    self.assertTrue(set(note['apis']) <= known_ids)
                    for identity in note['apis']:
                        result = reader.lookup(identity, kind='guide', limit=100)
                        self.assertIn(note['id'], {row['id'] for row in result['matches']})
                    # Every note is also an ordinary exact, hash-checked guide range.
                    self.assertTrue(reader.section(note['id'])['text'])
                result = reader.sections(['rs.AddBox', 'rs.AddSphere', 'rs.SurfaceVolume'], with_notes=True)
                self.assertEqual(len(result), 5)
                self.assertIn('8 点', result[1]['text'])
                self.assertIn('IsObjectSolid', result[-1]['text'])
                self.assertNotIn('单轨扫掠', '\n'.join(row['text'] for row in result))
                plain = reader.sections(['rs.AddBox', 'rs.AddSphere'])
                self.assertEqual(plain, [reader.section('rs.AddBox'), reader.section('rs.AddSphere')])
                explicit_note = result[1]['id']
                self.assertEqual(len(reader.sections(['rs.AddBox', explicit_note], with_notes=True)), 2)
                # A partial name must not return only a note without a contract.
                with self.assertRaises(ValueError):
                    reader.sections(['rs.AddBo'], with_notes=True)
        with catalog.Catalog(8) as reader:
            result = reader.sections(['rs.AddBox'], variant='rhino-8.30', with_notes=True)
            self.assertEqual(result[0]['variants'], ['rhino-8.30'])
            self.assertEqual(result[1]['variants'], ['all'])

    def test_cli_notes_and_short_errors_are_atomic(self):
        cli = catalog.ROOT / 'scripts/docs.py'
        args = [sys.executable, str(cli), 'section', '--major', '8', '--with-notes', '--id', 'rs.AddBox']
        output = subprocess.check_output(args, text=True)
        self.assertIn('AddBox(corners)', output)
        self.assertIn('8 点', output)
        failed = subprocess.run(args + ['--id', 'rs.ClosedCurveOrientation'], text=True, capture_output=True)
        self.assertEqual(failed.returncode, 1)
        self.assertEqual(failed.stdout, '')
        self.assertIn('choose --variant', failed.stderr)
        self.assertNotIn('Traceback', failed.stderr)
        invalid = subprocess.run([sys.executable, str(cli), 'lookup', '--major', '8', '--limit', '0'],
                                 text=True, capture_output=True)
        self.assertEqual(invalid.returncode, 1)
        self.assertEqual(invalid.stdout, '')
        self.assertIn('limit must be', invalid.stderr)
        self.assertNotIn('Traceback', invalid.stderr)

    def test_mcp_tools_and_archived_constraints_are_version_scoped(self):
        import re
        with zipfile.ZipFile(catalog.ROOT / 'references/official/rhinomcp-docs.zip') as archive:
            expected = set()
            for line in archive.read('README.md').decode().splitlines():
                if line.startswith('| `'):
                    expected.update(re.findall(r'`([a-z][a-z0-9_]+)`', line.strip('|').split('|')[0]))
        actual = {row['id'][4:] for row in self.rows[8] if row['id'].startswith('mcp:')}
        self.assertEqual(actual, expected)
        self.assertIn('create_object', actual)
        for major in (5, 6, 7):
            self.assertFalse(catalog.lookup(major, 'create_object', 'mcp')['matches'])
        self.assertIn('tools/list', catalog.section(8, 'mcp:create_object')['text'])
        self.assertEqual(catalog.lookup(8, 'create_object')['matches'][0]['id'], 'mcp:create_object')
        self.assertTrue(catalog.lookup(8, 'get_object_attributes', 'mcp')['matches'])

    def test_unindexed_text_archives_and_binary_rejection(self):
        for filename, member in [('rhinocommon-5.zip', 'lib/net35/RhinoCommon.XML'),
                                 ('rhinomcp-docs.zip', 'README.md')]:
            with zipfile.ZipFile(catalog.ROOT / 'references/official' / filename) as archive:
                self.assertIn(member, [row['path'] for row in docs.archive_rows(archive)])
                text = docs.read_topic(archive, member)['text']
                self.assertEqual(text, archive.read(member).decode('utf-8-sig'))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'test.zip'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('bad.txt', b'binary\x00content')
                archive.writestr('../bad.md', b'bad path')
            with zipfile.ZipFile(path) as archive:
                for member in ('bad.txt', '../bad.md'):
                    with self.assertRaises(ValueError):
                        docs.read_topic(archive, member)


if __name__ == '__main__':
    unittest.main()
