import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import plan_layouts
import overflow_check
import write_html


class PromoPlanTests(unittest.TestCase):
    def setUp(self):
        self.layout = plan_layouts.load_layouts(ROOT / 'references' / 'layouts.json')

    def test_text_only_plan(self):
        brief = {
            'schemaVersion': 1,
            'brand': '示例品牌',
            'title': '中文长标题用于检查',
            'body': '正文',
            'textOnly': True,
            'formats': ['square'],
        }
        plan = plan_layouts.plan(brief, self.layout)
        self.assertEqual(plan['sizes'][0]['width'], 1080)
        self.assertEqual(plan['sizes'][0]['svg']['operations'][1]['text'], brief['title'])

    def test_product_required_without_flag(self):
        brief = {
            'schemaVersion': 1,
            'brand': 'A',
            'title': 'T',
            'body': '',
        }
        with self.assertRaises(ValueError):
            plan_layouts.validate_brief(brief)

    def test_overflow_short_text_ok(self):
        boxes = [{
            'id': 'title', 'text': 'Hi', 'x': 0, 'y': 0,
            'width': 1000, 'height': 200, 'fontSize': 12,
        }]
        report = overflow_check.check_boxes(1080, 1080, boxes)
        self.assertTrue(report['ok'])

    def test_html_keeps_text_nodes(self):
        size = {
            'width': 100, 'height': 100,
            'regions': self.layout['regions']['square'],
        }
        html = write_html.render(
            size,
            {'title': '标题', 'body': '正文', 'colors': {'background': '#000', 'title': '#fff', 'body': '#ccc'}},
            'product.png',
        )
        self.assertIn('<p class="title">标题</p>', html)
        self.assertIn('src="product.png"', html)


if __name__ == '__main__':
    unittest.main()
