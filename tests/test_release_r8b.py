import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
R8B = ROOT / 'release' / 'r8b'
SHA = '8cb22dbeb195c3c0ffbe9c66cf956d8c2052d3b1c4a872234a85c975c4526117'
BYTES = 3633477
BASE_SHA = 'dbaa827aea6bc21215638447f17783a1004987c2d0bf5573d111fee397abdae5'
STARTER_SHA = '202272593630b4eddba57d5b09f5d3a142ed551b9550094e2885eb1b359fe037'  # the R8 starter, 73 codes
R7_SHA = '95faab81fba6fe57f854f973c1ccad2b0d1059fb951f34b17277385ceea8b303'
R7_DOI = '10.5281/zenodo.24126449'
FIGURES_SHA = '22c0305ddafe6f436599df115c1c71345fed3685feae2c3cd9198b5e989909d9'  # eval's frozen release figures
PROFILE_SHA = '2e2627104be4f27dc3204787dd3ff4f8591d95d1d96294c65833d2773041d317'  # line_fold_v1
MANIFESTS = {'bynli_lines_v2': '53dd7f1a10929ad4a60020ad7f42be62f27ee905cb7e6cfb0e319c5b2f5db7ca',
             'bynli_lines_v3': '4cba250f0f3e9207d26fd6e7415b1ed37132123c9c0c9ec961cc58ed0490994e',
             'reshumotlines_v1': 'a6de99ba6943209ba80a809b6bf64ff0e425d860b5787a5201a6d8153efc8a5c',
             'wslines_v1': '25ed7ff97d6cd1d05774de6377d4481483981ebcdc7460472d041118df988f99',
             's17a_addon_v1.1': '3f79461b6842b396d62139ddf6501554428abfe735e7e8274cd1bf8261355f1e'}
LINES_BY_SET = {'bynli_lines_v2': 95296, 'bynli_lines_v3': 62808, 'reshumotlines_v1': 19533, 'wslines_v1': 11,
                's17a_addon_v1.1': 18627}
WORD_DAWG = {'tessdata_best_heb': 'f34e9fa5165077f285ccff7c0f53a8e96b74ef37c92038e472770cfc83433171',
             'r7': 'cddcc086c241eeaf0f29b77f7955770d4fe3b2832f8fec986e53c7a0a579fcdb',
             'r8b': 'a618186eb88789a203c2475ec30fbe2277427f97d063a8bf91cc564c0a166649'}
NLI_CREDIT = 'From the collections of the National Library of Israel / מאוסף הספרייה הלאומית'
# hocrgen decision 2026-11-10-open-release-and-clean-inputs.md, item 2: the NOTICE part stands
IA_CONDITIONS = 'original conditions of each item on the Internet Archive still apply'
GOOGLE_CREDIT = 'Digitized by Google; retrieved via the Internet Archive'
NLI_TRAIN = {'990017640460205171': 6100, '990020308000205171': 6076, '990020495520205171': 6052,
             '990026910840205171': 2319, '990020522850205171': 1511, '990020466440205171': 72,
             '990019385920205171': 8, '990013538860205171': 1}
IA_NEW = {'zikhronotlebetda01reck': 6100, 'sifruthahisoriya11kaha': 6094, 'yotsrehasifrutha00zitr': 6039,
          'afahleneemaniml00fngoog': 5750, 'kolkitveylkatsen018800': 5716, 'seferhademaotmeo0000bern': 5350,
          'divreyemeolam02schuuoft': 4668, 'bioretletoldotha01gott': 4662, 'zikhronotlevetda01frie': 4150,
          'tserorperaimvehu00kovn': 3616, 'mikhtavimmiarsh00mezagoog': 3452, 'korothayehudimb00friegoog': 2968,
          'sipurim00nombuoft': 1291, 'tsitsimuferaimm00geiggoog': 633}
GOOGLE = {'afahleneemaniml00fngoog': 'University of California', 'mikhtavimmiarsh00mezagoog': 'unknown library',
          'korothayehudimb00friegoog': 'University of California', 'tsitsimuferaimm00geiggoog': 'University of California'}
SELECTION = {'kevarpirezikhron00haco': 1500, 'yediothateva06bernuoft': 1500}
LOCAL_PATH = r'/Users/|/home/|/private/|[A-Z]:\\'
HOCRSYNGEN_COMMIT = '3b55d4aff3de9f3211bc1573f2e0644748e84d63'  # the S17a generator and add-on recipe
S17A_PATH = 'experiments/learned_generation_v0/s17a_scanifier/'
PIPELINE_DOIS = ('10.5281/zenodo.24023070', '10.5281/zenodo.24023072', '10.5281/zenodo.24023074')


def read(name):
    return (R8B / name).read_text(encoding='utf-8')


def record():
    return json.loads(read('r8b_training_run.json'))


def ia_train():
    return {r['ia_identifier']: r for r in record()['data']['train'] if r['source'] == 'internet_archive'}


class R8bReleaseFilesTests(unittest.TestCase):
    def test_same_files_as_r7(self):
        self.assertEqual(sorted(p.name for p in R8B.iterdir()),
                         ['LICENSE', 'NOTICE', 'card_body.md', 'huggingface.yaml', 'r8b_training_run.json',
                          'zenodo.yaml'])
        self.assertEqual((R8B / 'LICENSE').read_bytes(), (ROOT / 'release' / 'r7' / 'LICENSE').read_bytes())

    def test_card_and_notice_credit_every_source(self):
        card, notice = read('card_body.md'), read('NOTICE')
        for name, text in (('card', card), ('NOTICE', notice)):
            text = re.sub(r'\s+', ' ', text)  # the NOTICE wraps its lines
            for needle in (SHA, 'HeOCR maintainers', 'tessdata_best', 'langdata_lstm', NLI_CREDIT, 'Internet Archive',
                           IA_CONDITIONS, GOOGLE_CREDIT, 'Project Ben-Yehuda', 'CC BY-SA 4.0',
                           'Hebrew Wikisource contributors', 'oldid=763704', 'Reshumot', 'Frank Ruhl Libre',
                           'heocr_r8b.traineddata', '0015', '0016', HOCRSYNGEN_COMMIT, S17A_PATH, *NLI_TRAIN, *IA_NEW,
                           *SELECTION):
                with self.subTest(file=name, needle=needle[:30]):
                    self.assertTrue(needle in text, f'{name} lacks {needle!r}')
            with self.subTest(file=name, check='no local paths'):
                self.assertNotRegex(text, LOCAL_PATH)
        notice = re.sub(r'\s+', ' ', notice)
        for needle in (BASE_SHA, 'modified version', 'Apache License, Version 2.0', 'No endorsement',
                       'Copyright Act 2007, section 6', 'is not asserted here', 'No word list was built from any training text',
                       'canvas 0, Google\'s usage-guidelines page, was excluded', 'no training line comes from canvas 0',
                       'legal strategy, rule 3', '3,633,477 bytes', 'CC0 1.0'):
            with self.subTest(needle=needle):
                self.assertIn(needle, notice)
        for identifier in ia_train():  # every Internet Archive training item, old and new
            with self.subTest(identifier=identifier):
                self.assertTrue(identifier in notice, identifier)

    def test_notice_credits_each_google_scan_with_its_library(self):
        notice = re.sub(r'\s+', ' ', read('NOTICE'))
        for identifier, library in GOOGLE.items():
            with self.subTest(identifier=identifier):
                entry = notice.split(f'{identifier}:', 1)[1].split(' lines.', 1)[0]
                self.assertIn(GOOGLE_CREDIT, entry)
                self.assertIn(f'contributing library: {library}', entry)

    def test_notice_names_each_reshumot_booklet(self):
        notice = re.sub(r'\s+', ' ', read('NOTICE'))
        for row in (r for r in record()['data']['train'] if r['source'] == 'reshumot_born_digital'):
            with self.subTest(booklet=row['booklet']):
                self.assertRegex(notice, rf'\b{row["booklet_number"]}\b')

    def test_card_is_honest(self):
        card = read('card_body.md')
        self.assertIn('tesseract page.png out -l heocr_r8b --tessdata-dir DIR --psm 3', card)
        self.assertIn('tesseract line.png out -l heocr_r8b --tessdata-dir DIR --psm 13', card)
        for needle in ('R8b supersedes nothing. R7 remains valid.', 'not a test score',
                       'There is no human-reviewed test score yet.', 'No human-reviewed test score yet.',
                       '0.743 against 0.635', 'small, dark and grainy', 'two independent readings confirm the label',
                       'unreleased A/B arm',
                       'line_fold_v1', PROFILE_SHA, FIGURES_SHA, STARTER_SHA, '3,633,477 bytes', '73 codes',
                       # OLB dev, all lines and the exact stratum, with intervals
                       '+0.805 [+0.665, +0.980]', '+0.585 [+0.401, +0.821]', '+0.342 [+0.154, +0.470]',
                       '+0.166 [+0.056, +0.294]', '**2.129**', '**0.735**',
                       # held-out selection books, with the optimism caveat
                       '0.757 / 3.542', '1.019 / 4.322', 'Selection optimism',
                       # report sets, and the regressions against the unreleased arm
                       '0.743 / 3.233', '0.635 / 2.616', 'Mekhilta (+0.03)', 'Bodek (+0.27)', 'Brainin IA (+0.08)',
                       'Bodek has 21 lines', '62 Brainin IA lines and 56 Mekhilta lines',
                       # the word-list check
                       '70,171 entries', '24 bracket or arrow tokens', *WORD_DAWG.values()):
            with self.subTest(needle=needle[:40]):
                self.assertTrue(needle in card, f'card lacks {needle!r}')
        self.assertIn(f'https://doi.org/{R7_DOI}', card)  # R7 is named, not replaced

    def test_card_figures_match_the_frozen_release_figures(self):
        evaluation = record()['evaluation']
        self.assertEqual(evaluation['figures_sha256'], FIGURES_SHA)
        card = read('card_body.md')
        for name, view in evaluation['olb_reshumot_dev']['views'].items():
            if name == 'exact_excluded':
                continue  # in the record, not on the card
            for model, cer in view['cer'].items():
                with self.subTest(view=name, model=model):
                    self.assertTrue(f'{cer:.3f}' in card, (name, model, cer))
        for book, models in evaluation['selection_books_held_out'].items():
            if book == 'caveat':
                continue
            for model, value in models.items():
                with self.subTest(book=book, model=model):
                    self.assertTrue(f"{value['cer']:.3f} / {value['wer']:.3f}" in card, (book, model))
        for name, models in evaluation['report_sets'].items():
            for model in ('r7', 's17a-addon', 'r8b-main-fold'):
                value = models[model]
                with self.subTest(set=name, model=model):
                    self.assertTrue(f"{value['cer']:.3f} / {value['wer']:.3f}" in card, (name, model))

    def test_card_cites_its_reserved_doi_and_links_no_pipeline_record(self):
        card = read('card_body.md')
        self.assertIn('[10.5281/zenodo.24156688](https://doi.org/10.5281/zenodo.24156688)', card)
        self.assertNotIn('DRAFT', card)
        self.assertNotIn('sharp', card.lower())  # eval: the two sharpness measures disagree on Brainin IA
        self.assertNotIn('whose labels are exact', card)  # every OLB dev line is layer-exact; 'exact' is the tier
        citation = card.split('## Citation', 1)[1]
        self.assertNotIn(R7_DOI, citation)  # R8b cites its own DOI (plan step 2)
        for doi in PIPELINE_DOIS:
            self.assertNotIn(doi, card)

    def test_release_name_is_a_tesseract_language_name(self):
        output = record()['output']
        self.assertEqual(output['release_file_name'], 'heocr_r8b.traineddata')
        self.assertRegex(output['release_file_name'], r'^[a-z0-9_]+\.traineddata$')
        self.assertEqual(output['language_name'], output['release_file_name'].removesuffix('.traineddata'))
        self.assertEqual(output['file_name'], 'heb.traineddata')

    def test_training_record_is_sanitised_and_unpublished(self):
        text = read('r8b_training_run.json')
        rec = json.loads(text)
        self.assertNotRegex(text, LOCAL_PATH)
        self.assertEqual(rec['schema_version'], 'heocr_tesseract_training_run.v1')
        self.assertEqual(rec['model'], 'R8b')
        self.assertEqual(list(rec), list(json.loads((ROOT / 'release' / 'r7' / 'r7_training_run.json')
                                                    .read_text(encoding='utf-8'))))
        self.assertEqual(rec['output']['model_sha256'], SHA)
        self.assertEqual(rec['output']['bytes'], BYTES)
        self.assertEqual(rec['init']['base_model']['sha256'], BASE_SHA)
        self.assertEqual(rec['init']['starter_traineddata']['sha256'], STARTER_SHA)
        self.assertEqual(rec['init']['output_codes'], {'base': 69, 'r7': 70, 'fine_tuned': 73})
        self.assertEqual(rec['init']['from_model']['released_model_sha256'], R7_SHA)
        self.assertEqual(rec['init']['from_model']['doi'], R7_DOI)
        self.assertEqual({s['name']: s['manifest_sha256'] for s in rec['data']['line_sets']}, MANIFESTS)
        self.assertEqual(rec['model_licence'], {'status': 'Apache-2.0', 'owner': 'maintainer',
                                                'basis': 'planning/decisions/0014-open-release-always.md',
                                                'published': False})
        self.assertTrue((ROOT / rec['model_licence']['basis']).is_file())
        self.assertTrue(all(isinstance(c, list) and all(isinstance(a, str) for a in c)
                            for c in rec['commands'].values()))
        self.assertFalse(rec['data']['labels']['niqqud'])
        self.assertEqual(rec['data']['rights_verification']['gaps'], 0)

    def test_training_record_lines_by_set_and_source(self):
        rec = record()
        train = rec['data']['train']
        by_set = {}
        for row in train:
            by_set[row['line_set']] = by_set.get(row['line_set'], 0) + row['lines']
        self.assertEqual(by_set, LINES_BY_SET)
        self.assertEqual({s['name']: s['train_lines'] for s in rec['data']['line_sets']}, LINES_BY_SET)
        self.assertEqual(sum(r['lines'] for r in train), 196275)
        self.assertEqual(rec['data']['split']['train_lines'], 196275)
        self.assertEqual(rec['data']['split']['selection_lines'], 3000)
        self.assertEqual({r['record_id']: r['lines'] for r in train if r['source'] == 'nli_free_use'}, NLI_TRAIN)
        ia = ia_train()
        self.assertEqual(len(ia), 37)
        self.assertEqual({k: v['lines'] for k, v in ia.items() if v['line_set'] == 'bynli_lines_v3'}, IA_NEW)
        self.assertEqual(len([r for r in train if r['source'] == 'reshumot_born_digital']), 48)
        self.assertEqual({r['ia_identifier']: r['lines'] for r in rec['data']['selection']}, SELECTION)

    def test_every_internet_archive_book_carries_its_rights_justifications(self):
        for identifier, item in ia_train().items():
            with self.subTest(item=identifier):
                self.assertTrue(item['pby_works'])
                for work in item['pby_works']:
                    self.assertRegex(work['rights_justification_id'], rf'^rj:{re.escape(identifier)}:[0-9a-f]{{12}}$')
                self.assertTrue(item['contributing_library'])
                self.assertTrue(item['israel_status'].startswith('pd_il'))
                self.assertLess(max(item['death_years']), 2026 - 70)
                if identifier in GOOGLE:
                    self.assertEqual(item['source_class'], 'ia_google_digitized_scan')
                    self.assertEqual(item['digitizer'], GOOGLE_CREDIT)
                    self.assertEqual(item['contributing_library'], GOOGLE[identifier])
                    self.assertEqual(item['google']['lines_from_canvas_0'], 0)
                    self.assertIn('canvas 0', item['google']['hygiene'])
                    self.assertIn('0015-legal-strategy.md', item['google']['basis'])
                    self.assertIn('rule 3', item['google']['basis'])
                else:
                    self.assertEqual(item['source_class'], 'ia_library_scan_no_licence_field')
                    self.assertNotIn('google', item['digitizer'].lower())

    def test_reshumot_and_wikisource_rows(self):
        train = record()['data']['train']
        for row in (r for r in train if r['source'] == 'reshumot_born_digital'):
            with self.subTest(booklet=row['booklet']):
                self.assertIn(row['series'], ('sefer_hachukim', 'kovetz_hatakanot'))
                self.assertTrue(row['licence'].startswith('PD-IL'))
                self.assertRegex(row['pdf_sha256'], r'^[0-9a-f]{64}$')
                self.assertTrue(row['publisher_url'].startswith('https://'))
        synthetic = [r for r in train if r['source'] == 'synthetic']
        self.assertEqual(len(synthetic), 1)
        self.assertEqual(synthetic[0]['code'] | {'covers': None},
                         {'repository': 'https://github.com/HeOCR/hocrsyngen', 'commit': HOCRSYNGEN_COMMIT,
                          'path': S17A_PATH, 'covers': None})
        ws = [r for r in train if r['source'] == 'wikimedia_commons']
        self.assertEqual(len(ws), 1)
        self.assertEqual((ws[0]['text_licence'], ws[0]['lines']), ('CC BY-SA 4.0', 11))

    def test_word_list_and_overlap_checks_are_recorded(self):
        evaluation = record()['evaluation']
        words = evaluation['word_list_check']
        self.assertEqual(words['lstm_word_dawg_sha256'], WORD_DAWG)
        self.assertEqual(words['entries'], {'tessdata_best_heb': 70171, 'r7': 70171, 'r8b': 70171})
        self.assertTrue(words['r8b_equals_r7'])
        self.assertEqual(words['entries_from_training_text'], 0)
        overlap = evaluation['text_overlap_check']
        self.assertEqual(overlap['eval_check_train_overlap']['lines_sharing_a_6gram'],
                         {'pmod_eval_pages': 0, 'wave1': 0, 'line_verify': 0, 'tenders': 0,
                          'rseries_dev_report': 158, 'olb_reshumot_dev': 13, 'line_verify_units_by_path': 0,
                          'rseries_dev_units_by_path': 0})
        self.assertEqual(overlap['audit2_references']['labels_sharing_a_6gram'], 1)
        self.assertEqual(evaluation['profile']['sha256'], PROFILE_SHA)

    def test_metadata_files(self):
        zenodo = read('zenodo.yaml').splitlines()
        hf = read('huggingface.yaml').splitlines()
        settings = [line for line in zenodo if not line.lstrip().startswith('#')]
        self.assertIn('communities:', settings)
        self.assertEqual(settings[settings.index('communities:') + 1:], ['  - heocr'])
        self.assertNotIn('ocr_models', '\n'.join(settings))
        self.assertNotIn('software_hints:', settings)
        self.assertIn('license: Apache-2.0', settings)
        self.assertIn(f'  - identifier: https://doi.org/{R7_DOI}', settings)  # derived from R7
        first = (ROOT / 'release' / 'r3h' / 'zenodo.yaml').read_text(encoding='utf-8')
        authors = re.search(r'^authors:\n(?:  .*\n)+', first, re.M)[0]
        self.assertIn(authors, read('zenodo.yaml'))
        self.assertEqual(hf[0], '# Hugging Face repository: HeOCR/heocr-r8b-tesseract-heb (the HeOCR organisation).')
        for line in ('license: apache-2.0', 'base_model: HeOCR/heocr-r7-tesseract-heb', '  - he', '  - tesseract',
                     '  - ocr', '  - hebrew'):
            with self.subTest(line=line):
                self.assertIn(line, hf)


if __name__ == '__main__':
    unittest.main()
