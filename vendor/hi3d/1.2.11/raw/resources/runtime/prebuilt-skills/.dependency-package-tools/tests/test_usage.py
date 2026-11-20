"""Synthetic, offline tests for usage coverage, provenance and commit drift."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import usage


class UsageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name).resolve()
        (self.repo / 'doc').mkdir()
        self.declarations([])
        self.entry('tools/helper')
        self.entry('skills/atom')
        self.entry('workflows/result')

    def entry(self, owner, files=None, requires=None, body=''):
        path = self.repo / owner
        path.mkdir(parents=True, exist_ok=True)
        (path / 'SKILL.md').write_text('---\nname: ' + path.name + '\ndescription: Synthetic fixture\n---\n' + body)
        (path / 'package.json').write_text(json.dumps({'schema': 1, 'files': files or {}, 'requires': requires or []}))
        if not owner.startswith('tools/'):
            self._pcg(path)
        return path

    def _pcg(self, path):
        name = path.name
        kind = 'agent_workflow' if 'workflows/' in str(path.relative_to(self.repo)) else 'agent_skill'
        sys.path.insert(0, str(SCRIPTS))
        from pcg_yaml import dump
        from pcg_architecture import architecture_from_routes
        (path / 'pcg').mkdir(exist_ok=True)
        routes = {
            'kind': kind, 'partition': 'software', 'entry': 'SKILL.md',
            'ui': {'option_buttons': True},
            'checkpoints': [
                {'id': 'input', 'say': '确认输入', 'rollback_to': None, 'load': ['SKILL.md'], 'irreversible': []},
                {'id': 'run', 'say': '执行能力', 'rollback_to': 'input', 'load': ['SKILL.md'], 'irreversible': []},
                {'id': 'review', 'say': '核对产物', 'rollback_to': 'run', 'load': ['SKILL.md'], 'irreversible': []},
            ],
            'routes': [{'id': 'main', 'summary': 'fixture', 'nodes': ['input', 'run', 'review']},
                       {'id': 'review_only', 'summary': 'fixture review', 'nodes': ['input', 'review']}],
            'choices_example': [
                {'id': 'do_run', 'title': '按输入执行', 'route': 'main'},
                {'id': 'skip_run', 'title': '只核对产物', 'route': 'review_only'},
            ],
        }
        (path / 'pcg' / 'routes.yaml').write_text(dump(routes))
        (path / 'pcg' / 'ops.lock.json').write_text(json.dumps({
            'schema': 'pcg.ops.lock.v1', 'skill': name, 'kind': kind,
            'blueprint_pcg_ops': [], 'unmapped': ['input', 'run', 'review'],
        }))
        (path / 'pcg' / 'architecture.yaml').write_text(dump(architecture_from_routes(name, kind, routes)))

    def declarations(self, rows):
        (self.repo / usage.DECLARATIONS).write_text(json.dumps({'schema': 1, 'relations': rows}))

    def test_distinguishes_materialization_documentation_and_required_entry(self):
        atom = self.repo / 'skills/atom'
        (atom / 'op.py').write_text('raise RuntimeError("must never be imported")\n')
        (atom / 'guide.md').write_text('Usage details\n')
        self.entry('workflows/result', files={'op.py': 'skills/atom/op.py', 'guide.md': 'skills/atom/guide.md'},
                   requires=['helper'], body='[Reference](../../tools/helper/SKILL.md)\n')
        entries, edges = usage.collect(self.repo)
        for provider, kind in [('atom', 'code'), ('atom', 'resource'), ('helper', 'requires'), ('helper', 'link')]:
            self.assertIn(('result', provider, kind), edges)
        self.assertNotIn(('result', 'helper', 'call'), edges)
        self.assertIn(('workflows/result/package.json', 'op.py ← skills/atom/op.py'), edges['result', 'atom', 'code'])
        self.assertEqual(len(entries), 3)

    def test_new_entry_and_changed_relationship_invalidate_document(self):
        usage.update(self.repo, write=True)
        before = (self.repo / usage.DOCUMENT).read_bytes()
        usage.update(self.repo)
        self.assertEqual(before, (self.repo / usage.DOCUMENT).read_bytes())
        self.entry('skills/unused')
        with self.assertRaisesRegex(ValueError, 'stale'):
            usage.update(self.repo)
        usage.update(self.repo, write=True)
        self.assertIn('[unused](../skills/unused/SKILL.md)', (self.repo / usage.DOCUMENT).read_text())
        self.entry('workflows/result', requires=['unused'])
        with self.assertRaisesRegex(ValueError, 'stale'):
            usage.update(self.repo)

    def test_incomplete_capability_directory_cannot_escape_the_index(self):
        usage.update(self.repo, write=True)
        before = (self.repo / usage.DOCUMENT).read_bytes()
        for category in ('tools', 'skills', 'workflows'):
            with self.subTest(category=category):
                pending = self.repo / category / 'unlisted'
                pending.mkdir()
                with self.assertRaisesRegex(ValueError, 'missing SKILL.md'):
                    usage.update(self.repo, write=True)
                self.assertEqual(before, (self.repo / usage.DOCUMENT).read_bytes())
                pending.rmdir()

    def test_nested_or_layer_root_entry_cannot_escape_the_index(self):
        usage.update(self.repo, write=True)
        for relative in ('skills/SKILL.md', 'skills/atom/nested/SKILL.md'):
            with self.subTest(relative=relative):
                entry = self.repo / relative
                entry.parent.mkdir(parents=True, exist_ok=True)
                entry.write_text('---\nname: hidden-entry\ndescription: fixture\n---\n')
                with self.assertRaisesRegex(ValueError, 'direct child|Nested entry'):
                    usage.update(self.repo)
                entry.unlink()

    def test_materialized_nested_entry_is_rejected(self):
        self.entry('workflows/result', files={'nested/SKILL.md': 'skills/atom/SKILL.md'})
        with self.assertRaisesRegex(ValueError, 'Nested entry'):
            usage.collect(self.repo)

    def test_bare_mentions_need_classification_and_stale_evidence_fails(self):
        self.entry('workflows/result', body='Only when needed, call helper.\n')
        with self.assertRaisesRegex(ValueError, 'Unclassified'):
            usage.collect(self.repo)
        row = {'consumer': 'result', 'provider': 'helper', 'kind': 'call',
               'evidence': 'workflows/result/SKILL.md', 'quote': 'Only when needed, call helper.'}
        self.declarations([row])
        self.assertIn(('result', 'helper', 'call'), usage.collect(self.repo)[1])
        self.entry('workflows/result', body='Do not use helper.\n')
        with self.assertRaisesRegex(ValueError, 'Stale declaration'):
            usage.collect(self.repo)

    def test_context_is_not_a_consumer_and_file_cycles_do_not_become_calls(self):
        a = self.entry('skills/atom', files={'guide.md': 'tools/helper/guide.md'}, body='helper is only a comparison.\n')
        (a / 'local.md').write_text('Atom contract\n')
        helper = self.entry('tools/helper', files={'guide-copy.md': 'skills/atom/local.md'})
        (helper / 'guide.md').write_text('Helper contract\n')
        self.declarations([{'consumer': 'result', 'provider': 'atom', 'kind': 'context',
                            'evidence': 'workflows/result/SKILL.md', 'quote': 'No atom dependency.'}])
        self.entry('workflows/result', body='No atom dependency.\n')
        entries, edges = usage.collect(self.repo)
        self.assertIn(('result', 'atom', 'context'), edges)
        table = usage.render(entries, edges).split('## 关系证据')[0]
        self.assertNotIn('[result]', table)
        self.assertFalse(any(key[2] in ('call', 'requires') for key in edges))

    def test_alias_links_point_back_to_canonical_owner(self):
        (self.repo / 'skills/atom/guide.md').write_text('Contract\n')
        self.entry('workflows/result', files={'refs/guide.md': 'skills/atom/guide.md'}, body='[Alias](refs/guide.md)\n')
        self.assertIn(('result', 'atom', 'link'), usage.collect(self.repo)[1])

    def test_integration_separates_orphans_instructions_and_workflow_calls(self):
        entries = {'helper': 'tools/helper', 'other': 'tools/other',
                   'atom': 'skills/atom', 'rules': 'skills/rules',
                   'unused': 'skills/unused', 'result': 'workflows/result'}
        edges = {('other', 'unused', 'code'): set(),
                 ('result', 'unused', 'context'): set(),
                 ('atom', 'helper', 'handoff'): set(),
                 ('result', 'rules', 'link'): set(),
                 ('result', 'atom', 'call'): set()}
        status = usage.integration_status(entries, edges)
        self.assertEqual(status['unused']['users'], [])
        self.assertEqual(status['helper'], dict(users=['atom'], executable=[], workflows=[]))
        self.assertEqual(status['rules'], dict(users=['result'], executable=[], workflows=['result']))
        self.assertEqual(status['atom']['executable'], ['result'])
        self.assertNotIn('result', status)
        edges['result', 'unused', 'code'] = set()
        self.assertEqual(usage.integration_status(entries, edges)['unused']['executable'], ['result'])

    def test_directory_link_and_markdown_evidence_keep_correct_provenance(self):
        self.entry('workflows/result', body='[Contract](../../skills/atom)\n')
        entries, edges = usage.collect(self.repo)
        self.assertIn(('result', 'atom', 'link'), edges)
        quote = 'Call atom after [review](notes.md).'
        self.entry('workflows/result', body=quote)
        (self.repo / 'workflows/result/notes.md').write_text('Review conditions.\n')
        self.declarations([{'consumer': 'result', 'provider': 'atom', 'kind': 'call',
                            'evidence': 'workflows/result/SKILL.md', 'quote': quote}])
        document = usage.render(*usage.collect(self.repo))
        self.assertNotIn('[review](notes.md)', document)
        self.assertIn('&#91;review&#93;', document)

    def test_reference_only_mentions_and_missing_layer_are_not_silently_ignored(self):
        (self.repo / 'workflows/result/guide.md').write_text('Only in this branch, call atom.')
        with self.assertRaisesRegex(ValueError, 'Unclassified'):
            usage.collect(self.repo)
        (self.repo / 'workflows/result/guide.md').unlink()
        (self.repo / 'tools').rename(self.repo / 'missing-tools')
        with self.assertRaisesRegex(ValueError, 'directory'):
            usage.collect(self.repo)

    def test_unknown_deleted_and_duplicate_evidence_are_rejected(self):
        self.entry('workflows/result', requires=['missing'])
        with self.assertRaises(ValueError):
            usage.collect(self.repo)
        self.entry('workflows/result', body='Call atom.\n')
        row = {'consumer': 'result', 'provider': 'atom', 'kind': 'call',
               'evidence': 'workflows/result/SKILL.md', 'quote': 'Call atom.'}
        self.declarations([row, row])
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            usage.collect(self.repo)
        self.declarations([dict(row, provider='deleted')])
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            usage.collect(self.repo)

    def test_symlink_evidence_and_output_are_not_followed(self):
        outside = self.repo / 'outside.md'
        outside.write_text('Call atom.\n')
        (self.repo / 'workflows/result/evidence.md').symlink_to(outside)
        with self.assertRaises(ValueError):
            usage.collect(self.repo)
        (self.repo / 'workflows/result/evidence.md').unlink()
        (self.repo / usage.DOCUMENT).symlink_to(outside)
        with self.assertRaises(ValueError):
            usage.update(self.repo, write=True)
        self.assertEqual(outside.read_text(), 'Call atom.\n')

    def test_precommit_rejects_mixed_snapshot_and_runs_check_on_staged_tree(self):
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        # A harmless checker lets this fixture observe whether the hook reaches it.
        script = self.repo / 'tools/package-tools/scripts/usage.py'
        script.parent.mkdir(parents=True)
        script.write_text('print("fixture-check-reached")\n')
        hook = SCRIPTS.parent / 'hooks/pre-commit'
        result = subprocess.run(['sh', str(hook)], cwd=self.repo, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        subprocess.run(['git', 'add', '.'], cwd=self.repo, check=True)
        result = subprocess.run(['sh', str(hook)], cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('fixture-check-reached', result.stdout)
        (self.repo / 'skills/atom/SKILL.md').write_text('unstaged change')
        result = subprocess.run(['sh', str(hook)], cwd=self.repo, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('fixture-check-reached', result.stdout)


if __name__ == '__main__':
    unittest.main()
