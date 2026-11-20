"""Offline behavior tests for explicit, independent skill materialization."""
import importlib.util
from pathlib import Path
import json
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('bundle', Path(__file__).resolve().parents[1] / 'scripts/bundle.py')
bundle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bundle)


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.repo = self.root / 'source'
        for category in bundle.CATEGORIES:
            (self.repo / category).mkdir(parents=True)
        self.entry('skills/a', {'schema': 1, 'files': {}, 'requires': []})

    def entry(self, owner, manifest):
        p = self.repo / owner
        p.mkdir(parents=True, exist_ok=True)
        (p / 'SKILL.md').write_text('---\nname: ' + p.name + '\ndescription: Synthetic package fixture\n---\n')
        (p / 'package.json').write_text(json.dumps(manifest))
        return p

    def test_materialized_alias_runs_without_source_tree(self):
        p = self.repo / 'skills/a'
        (p / 'operation.py').write_text('def increment(x):\n    return x + 1\n')
        self.entry('workflows/result', {'schema': 1, 'files': {'scripts/op.py': 'skills/a/operation.py'}, 'requires': []})
        output = self.root / 'distribution'
        bundle.build(self.repo, ['result'], output)
        self.repo.rename(self.root / 'hidden-source')
        spec = importlib.util.spec_from_file_location('isolated', output / 'workflows/result/scripts/op.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.increment(4), 5)

    def test_no_overwrite_and_no_output_inside_source(self):
        output = self.root / 'existing'
        output.mkdir()
        sentinel = output / 'keep.txt'
        sentinel.write_text('keep')
        with self.assertRaises(FileExistsError):
            bundle.build(self.repo, ['a'], output)
        self.assertEqual(sentinel.read_text(), 'keep')
        with self.assertRaises(ValueError):
            bundle.build(self.repo, ['a'], self.repo / 'generated')
        self.assertFalse((self.repo / 'generated').exists())

    def test_dependency_cycle_unknown_and_missing_source(self):
        self.entry('skills/a', {'schema': 1, 'files': {}, 'requires': ['b']})
        with self.assertRaises(ValueError):
            bundle.dependency_order(self.repo, ['a'])
        self.entry('skills/b', {'schema': 1, 'files': {}, 'requires': ['a']})
        with self.assertRaises(ValueError):
            bundle.dependency_order(self.repo, ['a'])
        self.entry('skills/a', {'schema': 1, 'files': {'file.py': 'skills/b/missing.py'}, 'requires': []})
        with self.assertRaises(FileNotFoundError):
            bundle.build(self.repo, ['a'], self.root / 'missing')
        self.assertFalse((self.root / 'missing').exists())

    def test_rejects_traversal_symlinks_and_shadowing(self):
        with self.assertRaises(ValueError):
            bundle.safe_relative('../escape')
        with self.assertRaises(ValueError):
            bundle.safe_relative('/absolute')
        p = self.repo / 'skills/a'
        (p / 'real.txt').write_text('fixture')
        (p / 'alias').symlink_to(p / 'real.txt')
        with self.assertRaises(ValueError):
            bundle.source_file(self.repo, 'skills/a/alias')
        (p / 'alias').unlink()
        self.entry('skills/a', {'schema': 1, 'files': {'real.txt': 'skills/a/SKILL.md'}, 'requires': []})
        with self.assertRaises(ValueError):
            bundle.package_files(self.repo, 'skills/a')

    def test_partial_distribution_has_no_false_navigation_targets(self):
        self.entry('skills/b', {'schema': 1, 'files': {}, 'requires': []})
        docs = self.repo / 'doc'
        docs.mkdir()
        (docs / 'index.md').write_text('[Provided](../skills/a/SKILL.md) [Optional](../skills/b/SKILL.md)')
        output = self.root / 'partial'
        bundle.build(self.repo, ['a'], output)
        self.assertFalse((output / 'skills/b').exists())
        self.assertIn('[Provided](../skills/a/SKILL.md)', (output / 'doc/index.md').read_text())
        self.assertIn('本次未打包', (output / 'doc/index.md').read_text())
        self.assertNotIn('skills/b/SKILL.md)', (output / 'README.md').read_text())

    def test_credential_paths_are_excluded_without_reading_contents(self):
        p = self.repo / 'skills/a'
        (p / '.env').write_text('SYNTHETIC_NOT_A_CREDENTIAL')
        self.assertNotIn('.env', bundle.package_files(self.repo, 'skills/a'))
        with self.assertRaises(ValueError):
            bundle.source_file(self.repo, 'skills/a/.env')

    def test_markdown_alias_points_to_installed_neighbor(self):
        text = '[API](operation.py#entry)'
        rewritten = bundle.rewrite_links(text, 'skills/a/guide.md', 'workflows/result/references/guide.md', {
            'workflows/result/references/guide.md': 'skills/a/guide.md',
            'workflows/result/scripts/op.py': 'skills/a/operation.py',
        })
        self.assertEqual(rewritten, '[API](../scripts/op.py#entry)')


if __name__ == '__main__':
    unittest.main()
