import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
R6 = ROOT / 'release' / 'r6'
SHA = '73eb18e03f8793dff9c03699db0845779f6b5db4897824bcd61787245ec66e10'
BASE_SHA = 'dbaa827aea6bc21215638447f17783a1004987c2d0bf5573d111fee397abdae5'
NLI_CREDIT = 'From the collections of the National Library of Israel / מאוסף הספרייה הלאומית'
TRAIN_RECORDS = {'990020308000205171': 6076, '990020495520205171': 6052, '990020522850205171': 1511,
                 '990019385920205171': 8, '990013538860205171': 1}
SELECTION_RECORDS = {'990020250940205171': 3046, '990018546440205171': 4046}
LOCAL_PATH = r'/Users/|/home/|/private/|[A-Z]:\\'
# The kraken pipeline's version DOIs: R6 is a release of its own and links to none of them.
PIPELINE_DOIS = ('10.5281/zenodo.24023070', '10.5281/zenodo.24023072', '10.5281/zenodo.24023074')
# heocr_tesseract_training_run.v1 (release/README.md, "R6"): the sections every record has.
RECORD_SECTIONS = ('schema_version', 'schema_note', 'model', 'task', 'engine', 'trainer', 'init', 'data',
                   'truth_order', 'commands', 'hyperparameters', 'run', 'outcome', 'evaluation', 'output',
                   'model_licence')


def read(name):
    return (R6 / name).read_text(encoding='utf-8')


class R6ReleaseFilesTests(unittest.TestCase):
    def test_same_files_as_the_first_release(self):
        self.assertEqual(sorted(p.name for p in R6.iterdir()),
                         ['LICENSE', 'NOTICE', 'card_body.md', 'huggingface.yaml', 'r6_training_run.json',
                          'zenodo.yaml'])
        self.assertEqual((R6 / 'LICENSE').read_bytes(), (ROOT / 'release' / 'r3h' / 'LICENSE').read_bytes())

    def test_card_and_notice_credit_every_source(self):
        card, notice = read('card_body.md'), read('NOTICE')
        for name, text in (('card', card), ('NOTICE', notice)):
            for needle in (SHA, 'HeOCR maintainers', 'tessdata_best', NLI_CREDIT, 'Project Ben-Yehuda',
                           'CC BY-SA', 'heocr_r6.traineddata', *TRAIN_RECORDS, *SELECTION_RECORDS):
                with self.subTest(file=name, needle=needle[:30]):
                    self.assertIn(needle, text)
            with self.subTest(file=name, check='no local paths'):
                self.assertNotRegex(text, LOCAL_PATH)
        self.assertIn(BASE_SHA, notice)
        self.assertIn('modified version', notice)
        self.assertIn('Apache License, Version 2.0', notice)
        self.assertIn('only to score', notice)
        self.assertIn('never for training', notice)

    def test_card_usage_evaluation_and_no_pipeline_links(self):
        card = read('card_body.md')
        self.assertIn('tesseract page.png out -l heocr_r6 --tessdata-dir DIR --psm 3', card)
        self.assertIn('tesseract line.png out -l heocr_r6 --tessdata-dir DIR --psm 13', card)
        for needle in ('0.209', '0.226', '0.225', '−0.016 [−0.023, −0.010]', '0.383', '0.384', 'No gain on the hardest'):
            with self.subTest(needle=needle):
                self.assertIn(needle, card)
        self.assertIn('<!-- DRAFT: R6\'s reserved version DOI', card)
        for doi in PIPELINE_DOIS:
            self.assertNotIn(doi, card)

    def test_release_name_is_a_tesseract_language_name(self):
        record = json.loads(read('r6_training_run.json'))
        name = record['output']['release_file_name']
        self.assertRegex(name, r'^[a-z0-9_]+\.traineddata$')  # no hyphen, as tessdata names
        self.assertEqual(record['output']['language_name'], name.removesuffix('.traineddata'))
        self.assertEqual(record['output']['file_name'], 'heb.traineddata')

    def test_training_record_is_sanitised_and_unpublished(self):
        text = read('r6_training_run.json')
        record = json.loads(text)
        self.assertNotRegex(text, LOCAL_PATH)
        self.assertEqual(record['schema_version'], 'heocr_tesseract_training_run.v1')
        for section in RECORD_SECTIONS:
            with self.subTest(section=section):
                self.assertIn(section, record)
        self.assertEqual(record['output']['model_sha256'], SHA)
        self.assertEqual(record['init']['base_model']['sha256'], BASE_SHA)
        self.assertEqual(record['model_licence'], {'status': 'Apache-2.0', 'owner': 'maintainer',
                                                   'basis': 'planning/decisions/0014-open-release-always.md',
                                                   'published': False})
        self.assertTrue((ROOT / record['model_licence']['basis']).is_file())
        self.assertEqual({r['record_id']: r['lines'] for r in record['data']['train']}, TRAIN_RECORDS)
        self.assertEqual({r['record_id']: r['lines'] for r in record['data']['selection']}, SELECTION_RECORDS)
        self.assertEqual(record['data']['split'], {'unit': 'record (whole book)', 'train_lines': 13648,
                                                   'selection_lines': 7092})
        self.assertFalse(record['data']['labels']['niqqud'])
        self.assertTrue(all(isinstance(c, list) and all(isinstance(a, str) for a in c)
                            for c in record['commands'].values()))
        self.assertEqual(record['evaluation']['text_overlap_check']['training_labels_vs_references'], 0)

    def test_metadata_files(self):
        zenodo = read('zenodo.yaml').splitlines()
        hf = read('huggingface.yaml').splitlines()
        settings = [line for line in zenodo if not line.lstrip().startswith('#')]
        self.assertIn('communities:', settings)
        self.assertEqual(settings[settings.index('communities:') + 1:], ['  - heocr'])
        self.assertNotIn('ocr_models', '\n'.join(settings))
        self.assertNotIn('software_hints:', settings)
        self.assertIn('license: Apache-2.0', settings)
        first = (ROOT / 'release' / 'r3h' / 'zenodo.yaml').read_text(encoding='utf-8')
        authors = re.search(r'^authors:\n(?:  .*\n)+', first, re.M)[0]
        self.assertIn(authors, read('zenodo.yaml'))  # the creators exactly as the first release's records
        self.assertEqual(hf[0], '# Hugging Face repository: HeOCR/heocr-r6-tesseract-heb (the HeOCR organisation).')
        for line in ('license: apache-2.0', '  - he', '  - tesseract', '  - ocr', '  - hebrew'):
            with self.subTest(line=line):
                self.assertIn(line, hf)

    def test_no_weights_in_the_repository(self):
        suffixes = {'.traineddata', '.lstm', '.checkpoint', '.lstmf'}
        self.assertFalse([p for p in (ROOT / 'release').rglob('*') if p.suffix in suffixes])


if __name__ == '__main__':
    unittest.main()
