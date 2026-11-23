"""Synthetic bookkeeping tests, not an end-to-end modeling validation."""
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('chain_budget', Path(__file__).with_name('hi3d-chain-budget.py'))
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


class Planning(unittest.TestCase):
    def data(self, **change):
        data = {'baseline_quads': 24000, 'target_quads': 2400, 'preserved_quads': 120,
                'core_closed': True, 'protected_core_vertices': 24, 'core_euler_characteristic': 2}
        data.update(change); return data

    def test_closed_core_plan_distinguishes_geometry_and_quad_count(self):
        result = module.plan(self.data())
        self.assertEqual(result['planned_core_triangles'], 760)
        self.assertEqual(result['planned_quad_count'], 2400)
        self.assertEqual(result['planned_triangulated_preview_count'], 4800)
        self.assertFalse(result['geometry_quality_verified'])

    def test_closed_parity_budget_never_exceeds_requested_count(self):
        result = module.plan(self.data(target_quads=2402))
        self.assertEqual(result['planned_core_triangles'] % 2, 0)
        self.assertLessEqual(result['planned_quad_count'], 2402)

    def test_count_conflict_does_not_claim_feasibility(self):
        result = module.plan(self.data(preserved_quads=2400))
        self.assertFalse(result['count_bounds_feasible'])
        self.assertEqual(result['action'], 'resolve_constraints')

    def test_locked_vertices_and_genus_have_a_necessary_lower_bound(self):
        result = module.plan(self.data(protected_core_vertices=500, core_euler_characteristic=-4))
        self.assertEqual(result['count_lower_bound_triangles'], 1008)
        self.assertFalse(result['count_bounds_feasible'])

    def test_boolean_or_fractional_counts_are_rejected(self):
        for value in [True, 12.5, '2400', None]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                module.plan(self.data(target_quads=value))

    def test_ratio_nan_and_ambiguous_targets_rejected(self):
        with self.assertRaises(ValueError): module.plan(self.data(remaining_ratio=0.1))
        data = self.data(); data.pop('target_quads'); data['remaining_ratio'] = float('nan')
        with self.assertRaises(ValueError): module.plan(data)


class Chains(unittest.TestCase):
    def data(self):
        return {'vertices': [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]],
                'faces': [[0, 1, 2, 3]], 'chains': [{'id': 'rim', 'closed': True, 'vertices': [0, 1, 2, 3]}]}

    def test_real_edge_cycle_valid_but_does_not_certify_surface(self):
        result = module.verify_chains(self.data())
        self.assertTrue(result['all_required_chains_valid'])
        self.assertFalse(result['full_surface_quality_verified'])

    def test_missing_closing_edge_is_detected(self):
        data = self.data(); data['chains'][0]['vertices'] = [0, 1, 2]
        result = module.verify_chains(data)
        self.assertFalse(result['all_required_chains_valid'])
        self.assertEqual(result['chains'][0]['missing_edges'], [[2, 0]])

    def test_open_path_does_not_require_closure(self):
        data = self.data(); data['chains'][0].update(closed=False, vertices=[0, 1, 2])
        self.assertTrue(module.verify_chains(data)['all_required_chains_valid'])

    def test_marker_drift_fails_with_valid_connectivity(self):
        data = self.data(); data['chains'][0]['reference_markers'] = [{'vertex': 0, 'position': [0.01, 0, 0]}]
        result = module.verify_chains(data)
        self.assertFalse(result['all_required_chains_valid'])
        self.assertAlmostEqual(result['chains'][0]['maximum_marker_displacement'], .01)

    def test_false_or_out_of_range_vertex_indices_rejected(self):
        for value in [False, 8]:
            data = self.data(); data['chains'][0]['vertices'][0] = value
            with self.subTest(value=value), self.assertRaises(ValueError): module.verify_chains(data)

    def test_no_chain_and_duplicate_vertices_are_not_a_valid_cycle(self):
        data = self.data(); data['chains'] = []
        with self.assertRaises(ValueError): module.verify_chains(data)
        data = self.data(); data['chains'][0]['vertices'] = [0, 1, 2, 1]
        self.assertFalse(module.verify_chains(data)['all_required_chains_valid'])

    def test_optional_only_does_not_claim_required_constraints_passed(self):
        data = self.data(); data['chains'][0]['required'] = False
        result = module.verify_chains(data)
        self.assertEqual(result['required_chain_count'], 0)
        self.assertFalse(result['all_required_chains_valid'])


if __name__ == '__main__':
    unittest.main()
