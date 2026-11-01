import re
import unittest
from pathlib import Path

from heocr_engine.contract import SCHEMA_ID, STAGE_KINDS, TRACKS

ROOT = Path(__file__).resolve().parent.parent


class PlanningTests(unittest.TestCase):
    def test_planning_links_resolve(self):
        index = (ROOT / 'planning' / 'README.md').read_text(encoding='utf-8')
        links = re.findall(r'\]\(([^)]+\.md)\)', index)
        self.assertTrue(links)
        for link in links:
            with self.subTest(link=link):
                self.assertTrue((ROOT / 'planning' / link).is_file())

    def test_decision_records_are_numbered_and_accepted(self):
        records = sorted((ROOT / 'planning' / 'decisions').glob('*.md'))
        numbers = [int(path.name[:4]) for path in records]
        self.assertEqual(numbers, list(range(1, len(records) + 1)))
        for path in records:
            with self.subTest(record=path.name):
                self.assertIn('- Status: ', path.read_text(encoding='utf-8'))

    def test_contract_doc_matches_constants(self):
        doc = (ROOT / 'docs' / 'prediction_contract.md').read_text(encoding='utf-8')
        for value in (SCHEMA_ID, *STAGE_KINDS, *TRACKS):
            with self.subTest(value=value):
                self.assertIn(f'`{value}`', doc)


if __name__ == '__main__':
    unittest.main()
