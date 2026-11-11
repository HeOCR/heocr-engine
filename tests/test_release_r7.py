import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
R7 = ROOT / 'release' / 'r7'
SHA = '95faab81fba6fe57f854f973c1ccad2b0d1059fb951f34b17277385ceea8b303'
BASE_SHA = 'dbaa827aea6bc21215638447f17783a1004987c2d0bf5573d111fee397abdae5'
STARTER_SHA = '8b9d798a456bd1d4cd8bdf71b3d7b9d7579cea6cbd51302accd57f521669b846'  # R6's starter, byte for byte
MANIFEST_SHA = '53dd7f1a10929ad4a60020ad7f42be62f27ee905cb7e6cfb0e319c5b2f5db7ca'  # bynli_lines_v2
R6_DOI = '10.5281/zenodo.24109989'
NLI_CREDIT = 'From the collections of the National Library of Israel / מאוסף הספרייה הלאומית'
# The wording decided for Internet Archive scans published without an explicit licence (hocrgen decision
# 2026-11-10-open-release-and-clean-inputs.md, item 2; the F8f R7 hand-off's release notice).
IA_CONDITIONS = 'original conditions of each item on the Internet Archive still apply'
NLI_TRAIN = {'990017640460205171': 6100, '990020308000205171': 6076, '990020495520205171': 6052,
             '990020522850205171': 1511, '990020466440205171': 72, '990019385920205171': 8, '990013538860205171': 1}
IA_TRAIN = {'kolsifreperetsbe03smoluoft': 6100, 'sifrehazikhronot00mont': 6100, 'kolsifreperetsbe01smoluoft': 6096,
            'kolsifreperetsbe05smoluoft': 5489, 'miyarketetevel008800': 4760, 'ldpd_15772050_000': 4639,
            'mabeothayehudims00raff': 4135, 'atn3681.0001.001.umich.edu': 4027, 'maloketravseadya00bornuoft': 3643,
            'mimitsrayimhusef00fran': 3529, 'ademataidibruivr00benyuoft': 2980, 'agadothatanaim11bach': 2977,
            'motsaegolahzikhr00rabbuoft': 2836, 'peereakhmemedina00gree': 2776, 'imanuelharomimon0000tche': 2572,
            'mishnatrishonimt0000klat': 2553, 'igrothaasirmeiha00drey': 2487, 'masaleeretsyirae00lewi': 1917,
            'sepherhayyeyehud01mode': 1491, 'reginahashkenazi00ginsuoft': 1304, 'anshekayruan00pozn': 1218,
            'maamarmagenetsin00mode': 1145, 'hegyoneshpinozah00rubi': 557}
SELECTION_RECORDS = {'990018546440205171': 4046, '990020250940205171': 3046, '990010684570205171': 21}
LOCAL_PATH = r'/Users/|/home/|/private/|[A-Z]:\\'
PIPELINE_DOIS = ('10.5281/zenodo.24023070', '10.5281/zenodo.24023072', '10.5281/zenodo.24023074')
RECORD_SECTIONS = ('schema_version', 'schema_note', 'model', 'task', 'engine', 'trainer', 'init', 'data',
                   'truth_order', 'commands', 'hyperparameters', 'run', 'outcome', 'evaluation', 'output',
                   'model_licence')


def read(name):
    return (R7 / name).read_text(encoding='utf-8')


class R7ReleaseFilesTests(unittest.TestCase):
    def test_same_files_as_r6(self):
        self.assertEqual(sorted(p.name for p in R7.iterdir()),
                         ['LICENSE', 'NOTICE', 'card_body.md', 'huggingface.yaml', 'r7_training_run.json',
                          'zenodo.yaml'])
        self.assertEqual((R7 / 'LICENSE').read_bytes(), (ROOT / 'release' / 'r6' / 'LICENSE').read_bytes())

    def test_card_and_notice_credit_every_source(self):
        card, notice = read('card_body.md'), read('NOTICE')
        for name, text in (('card', card), ('NOTICE', notice)):
            text = re.sub(r'\s+', ' ', text)  # the NOTICE wraps its lines
            for needle in (SHA, 'HeOCR maintainers', 'tessdata_best', 'langdata_lstm', NLI_CREDIT, 'Internet Archive',
                           IA_CONDITIONS, 'Project Ben-Yehuda', 'CC BY-SA', 'heocr_r7.traineddata', *NLI_TRAIN,
                           *IA_TRAIN, *SELECTION_RECORDS):
                with self.subTest(file=name, needle=needle[:30]):
                    self.assertIn(needle, text)
            with self.subTest(file=name, check='no local paths'):
                self.assertNotRegex(text, LOCAL_PATH)
        notice = re.sub(r'\s+', ' ', notice)
        self.assertIn(BASE_SHA, notice)
        self.assertIn('modified version', notice)
        self.assertIn('Apache License, Version 2.0', notice)
        self.assertIn('only to score', notice)
        self.assertIn('never for training', notice)
        self.assertIn('No endorsement', notice)
        self.assertIn('None was digitized by Google', notice)

    def test_notice_names_each_internet_archive_library(self):
        notice = re.sub(r'\s+', ' ', read('NOTICE'))
        for library in ('Robarts - University of Toronto', 'University of Toronto, Downsview', 'University of Michigan',
                        'Columbia University Libraries', 'Duke University Libraries', 'Brandeis University Libraries',
                        'University of Illinois Urbana-Champaign', 'The Ohio State University',
                        'University of Florida, George A. Smathers Libraries'):
            with self.subTest(library=library):
                self.assertIn(library, notice)

    def test_card_is_honest_about_r6(self):
        card = read('card_body.md')
        self.assertIn('tesseract page.png out -l heocr_r7 --tessdata-dir DIR --psm 3', card)
        self.assertIn('tesseract line.png out -l heocr_r7 --tessdata-dir DIR --psm 13', card)
        for needle in ('R7 supersedes nothing. R6 remains valid.', 'no measured page-level gain over R6',
                       'Against R6: a tie.', 'No gain on the hardest pages.',
                       '−0.0005 [−0.0072, +0.0061]', '−0.0168 [−0.0285, −0.0058]', '−0.0135 [−0.0273, +0.0004]',
                       '+0.0108 [−0.0011, +0.0186]', '+0.0091 [−0.0041, +0.0246]', '0.2089', '0.2094',
                       '1.567%', '2.056%', 'No text overlap with training.'):
            with self.subTest(needle=needle):
                self.assertIn(needle, card)
        self.assertIn(f'https://doi.org/{R6_DOI}', card)  # R6 is named, not replaced

    def test_card_doi_is_still_a_draft_and_links_no_pipeline_record(self):
        card = read('card_body.md')
        self.assertIn("<!-- DRAFT: R7's reserved version DOI", card)
        citation = card.split('## Citation', 1)[1]
        self.assertNotIn(R6_DOI, citation)  # R7 cites its own DOI, once reserved (plan step 2)
        for doi in PIPELINE_DOIS:
            self.assertNotIn(doi, card)

    def test_release_name_is_a_tesseract_language_name(self):
        record = json.loads(read('r7_training_run.json'))
        name = record['output']['release_file_name']
        self.assertEqual(name, 'heocr_r7.traineddata')
        self.assertRegex(name, r'^[a-z0-9_]+\.traineddata$')
        self.assertEqual(record['output']['language_name'], name.removesuffix('.traineddata'))
        self.assertEqual(record['output']['file_name'], 'heb.traineddata')

    def test_training_record_is_sanitised_and_unpublished(self):
        text = read('r7_training_run.json')
        record = json.loads(text)
        self.assertNotRegex(text, LOCAL_PATH)
        self.assertEqual(record['schema_version'], 'heocr_tesseract_training_run.v1')
        self.assertEqual(record['model'], 'R7')
        for section in RECORD_SECTIONS:
            with self.subTest(section=section):
                self.assertIn(section, record)
        self.assertEqual(list(record), list(json.loads((ROOT / 'release' / 'r6' / 'r6_training_run.json')
                                                       .read_text(encoding='utf-8'))))
        self.assertEqual(record['output']['model_sha256'], SHA)
        self.assertEqual(record['output']['bytes'], 3628595)
        self.assertEqual(record['init']['base_model']['sha256'], BASE_SHA)
        self.assertEqual(record['init']['starter_traineddata']['sha256'], STARTER_SHA)
        self.assertEqual(record['data']['manifest_sha256'], MANIFEST_SHA)
        self.assertEqual(record['model_licence'], {'status': 'Apache-2.0', 'owner': 'maintainer',
                                                   'basis': 'planning/decisions/0014-open-release-always.md',
                                                   'published': False})
        self.assertTrue((ROOT / record['model_licence']['basis']).is_file())
        self.assertTrue(all(isinstance(c, list) and all(isinstance(a, str) for a in c)
                            for c in record['commands'].values()))
        self.assertFalse(record['data']['labels']['niqqud'])

    def test_training_record_lines_and_routes(self):
        record = json.loads(read('r7_training_run.json'))
        train = record['data']['train']
        self.assertEqual({r['record_id']: r['lines'] for r in train if r['source'] == 'nli_free_use'}, NLI_TRAIN)
        self.assertEqual({r['ia_identifier']: r['lines'] for r in train if r['source'] == 'internet_archive'}, IA_TRAIN)
        self.assertEqual({r['source'] for r in train}, {'nli_free_use', 'internet_archive'})
        self.assertEqual({r['record_id']: r['lines'] for r in record['data']['selection']}, SELECTION_RECORDS)
        self.assertTrue(all(r['source'] == 'nli_free_use' for r in record['data']['selection']))
        self.assertEqual(sum(r['lines'] for r in train), 95151)
        self.assertEqual(record['data']['split']['train_lines'], 95151)
        self.assertEqual(record['data']['split']['selection_lines'], 7113)
        self.assertEqual({s['route'] for s in record['data']['scans']}, {'nli_free_use', 'internet_archive'})

    def test_every_internet_archive_book_carries_its_rights_justifications(self):
        record = json.loads(read('r7_training_run.json'))
        for item in (r for r in record['data']['train'] if r['source'] == 'internet_archive'):
            with self.subTest(item=item['ia_identifier']):
                self.assertTrue(item['pby_works'])
                for work in item['pby_works']:
                    self.assertRegex(work['rights_justification_id'],
                                     rf'^rj:{re.escape(item["ia_identifier"])}:[0-9a-f]{{12}}$')
                self.assertTrue(item['contributing_library'])
                self.assertNotIn('google', item['contributing_library'].lower())
                self.assertTrue(item['israel_status'].startswith('pd_il'))
                self.assertLess(max(item['death_years']), 2026 - 70)

    def test_training_record_evaluation(self):
        evaluation = json.loads(read('r7_training_run.json'))['evaluation']
        r38, r10 = evaluation['results']['38'], evaluation['results']['10']
        self.assertEqual(r38['r7'], {'cer': 0.2089, 'wer': 0.3933})
        self.assertEqual(r38['r6'], {'cer': 0.2094, 'wer': 0.4068})
        self.assertEqual(r38['r7_minus_r6_cer']['page_95'], [-0.0072, 0.0061])
        self.assertEqual(r10['r7_minus_r6_cer']['delta'], 0.0108)
        overlap = evaluation['text_overlap_check']
        self.assertEqual(overlap['training_labels_vs_references'], 0)
        self.assertEqual(overlap['training_labels_concatenated_per_work_vs_references'], 0)
        self.assertEqual(overlap['training_books_full_text_vs_references']['in_training_labels'], 0)

    def test_metadata_files(self):
        zenodo = read('zenodo.yaml').splitlines()
        hf = read('huggingface.yaml').splitlines()
        settings = [line for line in zenodo if not line.lstrip().startswith('#')]
        self.assertIn('communities:', settings)
        self.assertEqual(settings[settings.index('communities:') + 1:], ['  - heocr'])
        self.assertNotIn('ocr_models', '\n'.join(settings))
        self.assertNotIn('software_hints:', settings)
        self.assertNotIn(R6_DOI, '\n'.join(settings))  # no relation to R6: see the comment in zenodo.yaml
        self.assertIn('license: Apache-2.0', settings)
        first = (ROOT / 'release' / 'r3h' / 'zenodo.yaml').read_text(encoding='utf-8')
        authors = re.search(r'^authors:\n(?:  .*\n)+', first, re.M)[0]
        self.assertIn(authors, read('zenodo.yaml'))
        self.assertEqual(hf[0], '# Hugging Face repository: HeOCR/heocr-r7-tesseract-heb (the HeOCR organisation).')
        for line in ('license: apache-2.0', '  - he', '  - tesseract', '  - ocr', '  - hebrew'):
            with self.subTest(line=line):
                self.assertIn(line, hf)


if __name__ == '__main__':
    unittest.main()
