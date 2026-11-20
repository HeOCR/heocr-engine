"""The public-authored text split is deterministic and isolated."""
import importlib.util
from pathlib import Path
import unittest
import sys


class CorpusSplitTest(unittest.TestCase):
    def test_text_groups_are_disjoint_and_stable(self):
        path = Path(__file__).parents[1] / 'research/printed_line_transfer/setup.py'
        spec = importlib.util.spec_from_file_location('research_setup', path)
        module = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(path.parent))
        try:
            spec.loader.exec_module(module)
        finally:
            sys.path.pop(0)
        groups = module.corpora()
        self.assertEqual([len(groups[k]) for k in ('train', 'validation', 'test')], [128, 32, 32])
        self.assertFalse(set(groups['train']) & set(groups['validation']))
        self.assertFalse(set(groups['train']) & set(groups['test']))
        self.assertFalse(set(groups['validation']) & set(groups['test']))
        self.assertEqual(groups, module.corpora())

class IntegrityTest(unittest.TestCase):
    def setUp(self):
        import hashlib
        import json
        import tempfile
        from unittest.mock import patch
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        root = Path(__file__).parents[1] / 'research/printed_line_transfer'
        sys.path.insert(0, str(root))
        self.addCleanup(sys.path.pop, 0)
        import integrity
        self.integrity = integrity
        self.addCleanup(self.tmp.cleanup)
        fontdir = self.root / 'inputs/fonts'
        fontdir.mkdir(parents=True)
        fonts = {}
        for name in ('alef', 'noto'):
            f = fontdir / (name + '.ttf')
            f.write_text(name)
            fonts[name] = hashlib.sha256(f.read_bytes()).hexdigest()
        self.fontpatch = patch.object(integrity, 'FONTS', fonts)
        self.fontpatch.start()
        self.addCleanup(self.fontpatch.stop)
        groups = {}
        for name in ('train', 'validation', 'test'):
            folder = self.root / 'lines' / name
            folder.mkdir(parents=True)
            image, label = folder / 'line.png', folder / 'line.gt.txt'
            image.write_text('image-' + name)
            label.write_text('text-' + name)
            H = lambda f: hashlib.sha256(f.read_bytes()).hexdigest()
            groups[name] = [{'image': str(image.relative_to(self.root)), 'label': str(label.relative_to(self.root)), 'image_sha256': H(image), 'label_sha256': H(label)}]
            (self.root / (name + '.lst')).write_text(str(image) + '\n')
        freeze = self.root / 'line-freeze.json'
        freeze.write_text(json.dumps({'splits': groups}))
        digest = hashlib.sha256(freeze.read_bytes()).hexdigest()
        (self.root / 'line-freeze.sha256').write_text(digest + '\n')
        self.freezepatch = patch.object(integrity, 'LINE_FREEZE_SHA', digest)
        self.freezepatch.start()
        self.addCleanup(self.freezepatch.stop)

    def test_rejects_mutated_reference_or_extra_image(self):
        self.integrity.verify(self.root)
        label = self.root / 'lines/test/line.gt.txt'
        old = label.read_text()
        label.write_text('changed')
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.integrity.verify(self.root)
        label.write_text(old)
        (self.root / 'lines/test/extra.png').write_text('extra')
        with self.assertRaisesRegex(ValueError, 'set or list'):
            self.integrity.verify(self.root)

    def test_rejects_wrong_split_list_and_font(self):
        (self.root / 'test.lst').write_text('wrong\n')
        with self.assertRaisesRegex(ValueError, 'set or list'):
            self.integrity.verify(self.root)
        (self.root / 'inputs/fonts/noto.ttf').write_text('other')
        with self.assertRaisesRegex(ValueError, 'font hash'):
            self.integrity.verify(self.root)

    def test_aggregate_has_no_partial_score(self):
        import evaluate
        row = {'status': 'ok', 'word_edits': 1, 'reference_words': 3, 'char_edits': 2, 'reference_chars': 9}
        self.assertNotIn('word_edits', evaluate.aggregate([row], 0, 2))
        self.assertNotIn('word_edits', evaluate.aggregate([row], 1, 1))
        good = evaluate.aggregate([row], 0, 1)
        self.assertEqual(good['word_edits'], 1)
        paired = {'base': good, 'candidate': evaluate.aggregate([row], 0, 2)}
        self.assertTrue(evaluate.finalize(paired))
        self.assertNotIn('word_edits', paired['base'])

    def test_multiple_text_equivalents_rejected(self):
        import evaluate
        f = self.root / 'multiple.xml'
        f.write_text('<PcGts xmlns="urn:p"><TextLine><TextEquiv><Unicode>a</Unicode></TextEquiv><TextEquiv><Unicode>b</Unicode></TextEquiv></TextLine></PcGts>')
        with self.assertRaisesRegex(ValueError, 'one text equivalent'):
            evaluate.read_line(f)


if __name__ == '__main__':
    unittest.main()
