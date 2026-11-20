"""Configuration boundary checks; standard Python, no Blender or task data."""

import copy
import importlib.util
import json
from pathlib import Path
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('hair_rebuild', PACKAGE / 'scripts/rebuild_from_scene.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((PACKAGE / 'references/config_example.json').read_text())

    def test_import_and_validation_do_not_mutate_config(self):
        original = copy.deepcopy(self.config)
        self.assertIs(module.validate_config(self.config), self.config)
        self.assertEqual(original, self.config)

    def test_rejects_invalid_numeric_contracts(self):
        for key, value in [('width', 0), ('offset', float('nan')), ('segments', 0),
                           ('columns', True), ('stride', -1), ('lanes', []), ('lanes', [8])]:
            with self.subTest(key=key, value=value):
                config = copy.deepcopy(self.config)
                config['layers'][0][key] = value
                with self.assertRaises(ValueError):
                    module.validate_config(config)

    def test_rejects_input_output_collision(self):
        self.config['layers'][0]['name'] = self.config['layers'][0]['guides'][0]
        with self.assertRaises(ValueError):
            module.validate_config(self.config)

    def test_rejects_non_object_config_and_layers(self):
        with self.assertRaises(ValueError):
            module.validate_config([])
        self.config['layers'] = ['invalid']
        with self.assertRaises(ValueError):
            module.validate_config(self.config)

    def test_rejects_duplicate_output_names(self):
        self.config['layers'].append(copy.deepcopy(self.config['layers'][0]))
        with self.assertRaises(ValueError):
            module.validate_config(self.config)

    def test_arbitrary_equal_width_atlas_columns(self):
        self.config['atlas_columns'] = 3
        self.config['layers'][0]['lanes'] = [0, 2]
        module.validate_config(self.config)

    def test_guides_reject_unused_contact_and_invalid_sections(self):
        for key, value in [('head', 'Head'), ('surface_clearance', .01), ('placement', 'typo')]:
            config = copy.deepcopy(self.config)
            config[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                module.validate_config(config)
        for key, value in [('root_normal', [0, 0, 0]), ('root_normal', [0, 1]),
                           ('root_normal', [0, float('nan'), 1]),
                           ('section_angles_degrees', []), ('section_angles_degrees', [0, 0]),
                           ('section_angles_degrees', [-180, 180]),
                           ('section_angles_degrees', [0, float('inf')]),
                           ('section_angles_degrees', [True]), ('section_angles_degrees', [181])]:
            config = copy.deepcopy(self.config)
            config['layers'][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                module.validate_config(config)

    def test_legacy_config_still_requires_head_and_single_section(self):
        config = copy.deepcopy(self.config)
        del config['placement']
        del config['layers'][0]['root_normal']
        del config['layers'][0]['section_angles_degrees']
        config.update(head='Head', surface_clearance=.002)
        module.validate_config(config)
        config['layers'][0]['section_angles_degrees'] = [0, 80]
        with self.assertRaises(ValueError):
            module.validate_config(config)
        config['layers'][0]['section_angles_degrees'] = [0]
        del config['head']
        with self.assertRaises(ValueError):
            module.validate_config(config)


if __name__ == '__main__':
    unittest.main()
