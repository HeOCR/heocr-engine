"""The public-authored text split is deterministic and isolated."""
import importlib.util
from pathlib import Path
import unittest


class CorpusSplitTest(unittest.TestCase):
    def test_text_groups_are_disjoint_and_stable(self):
        path = Path(__file__).parents[1] / 'research/printed_line_transfer/setup.py'
        spec = importlib.util.spec_from_file_location('research_setup', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        groups = module.corpora()
        self.assertEqual([len(groups[k]) for k in ('train', 'validation', 'test')], [128, 32, 32])
        self.assertFalse(set(groups['train']) & set(groups['validation']))
        self.assertFalse(set(groups['train']) & set(groups['test']))
        self.assertFalse(set(groups['validation']) & set(groups['test']))
        self.assertEqual(groups, module.corpora())


if __name__ == '__main__':
    unittest.main()
