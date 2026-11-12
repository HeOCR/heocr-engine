import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location('hf_upload', ROOT / 'release' / 'hf_upload.py')
hf = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hf)

TOKEN = 'hf_secret_token_456'
DOIS = {'r4d': '10.5281/zenodo.111', 'a1': '10.5281/zenodo.222', 'r3h': '10.5281/zenodo.333'}


class Add:
    def __init__(self, path_in_repo, path_or_fileobj):
        self.path_in_repo, self.path_or_fileobj = path_in_repo, path_or_fileobj


class FakeHfApi:
    def __init__(self, token=None):
        self.token, self.calls = token, []

    def create_repo(self, repo_id, **kwargs):
        self.calls.append(('create_repo', repo_id, kwargs))

    def create_commit(self, repo_id, operations, **kwargs):
        self.calls.append(('create_commit', repo_id, [op.path_in_repo for op in operations], kwargs))


@contextlib.contextmanager
def release_copy(api=None):
    """A temporary release/ copy whose cards cite DOIS, fake weights matching copied records, and a state file."""
    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory)
        release = directory / 'release'
        weights = {}
        for model in hf.MODELS:
            shutil.copytree(ROOT / 'release' / model, release / model)
            body = release / model / 'card_body.md'
            body.write_text(body.read_text(encoding='utf-8') + f'\nCite {DOIS[model]}.\n', encoding='utf-8')
            data = f'weights of {model}'.encode()
            weights[model] = directory / f'{model}.safetensors'
            weights[model].write_bytes(data)
            record_path = release / model / f'{model}_training_run.json'
            record = json.loads(record_path.read_text(encoding='utf-8'))
            record['output']['model_sha256'] = hashlib.sha256(data).hexdigest()
            record_path.write_text(json.dumps(record), encoding='utf-8')
        state = directory / 'state.json'
        state.write_text(json.dumps({'api': api or hf.zenodo.PRODUCTION,
                                     'records': {m: {'id': m, 'doi': d} for m, d in DOIS.items()}}))
        yield release, weights, state


def weights_args(weights):
    return ['--weights', *(f'{m}={p}' for m, p in weights.items())]


def run(argv, environ=None, api_factory=None):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = hf.main(argv, environ or {}, api_factory, Add)
    return code, out.getvalue(), err.getvalue()


class HfUploadTests(unittest.TestCase):
    def test_repos_match_the_release_files(self):
        for model, repo in hf.HF_REPOS.items():
            first = (ROOT / 'release' / model / 'huggingface.yaml').read_text(encoding='utf-8').splitlines()[0]
            self.assertIn(repo, first)

    def test_card_is_front_matter_then_body_and_cites_its_doi(self):
        with release_copy() as (release, _, _):
            card = hf.build_card('a1', DOIS['a1'], release)
            front, body = card.split('\n---\n', 1)
            self.assertTrue(front.startswith('---\nlicense: apache-2.0'))
            self.assertNotIn('#', front)
            self.assertIn(DOIS['a1'], body)
            with self.assertRaisesRegex(hf.DepositError, 'step 2'):
                hf.build_card('a1', '10.5281/zenodo.999', release)

    def test_dry_run_plans_without_network_or_token(self):
        imported_before = 'huggingface_hub' in sys.modules
        with release_copy(api=hf.zenodo.SANDBOX) as (release, weights, state):
            code, out, err = run(['--dry-run', '--release-dir', str(release), '--zenodo-state', str(state),
                                  *weights_args(weights)], api_factory=None)
        self.assertEqual(code, 0, err)
        planned = [json.loads(line) for line in out.splitlines()]
        self.assertEqual([p['repo_id'] for p in planned], [hf.HF_REPOS[m] for m in hf.MODELS])
        self.assertTrue(all(p['public'] for p in planned))
        self.assertEqual(sorted(f['path'] for f in planned[0]['files']),
                         sorted(['README.md', 'heocr-r4d-segmentation.safetensors', 'LICENSE', 'NOTICE',
                                 'r4d_training_run.json']))
        if not imported_before:
            self.assertNotIn('huggingface_hub', sys.modules)  # a dry run never loads it

    def test_weights_must_match_the_record(self):
        with release_copy() as (release, weights, state):
            weights['r3h'].write_bytes(b'tampered')
            code, _, err = run(['--dry-run', '--release-dir', str(release), '--zenodo-state', str(state),
                                *weights_args(weights)])
        self.assertEqual(code, 1)
        self.assertIn('does not match', err)

    def test_real_upload_needs_production_dois_the_repository_release_and_a_token(self):
        with release_copy(api=hf.zenodo.SANDBOX) as (release, weights, state):
            code, _, err = run(['--zenodo-state', str(state), *weights_args(weights)], {'HF_TOKEN': TOKEN})
            self.assertEqual(code, 1)
            self.assertIn('production DOIs', err)
        with release_copy() as (release, weights, state):
            code, _, err = run(['--release-dir', str(release), '--zenodo-state', str(state),
                                *weights_args(weights)], {'HF_TOKEN': TOKEN})
            self.assertEqual(code, 1)
            self.assertIn('dry runs only', err)

    def test_upload_creates_public_repos_and_one_commit_each(self):
        with release_copy() as (release, weights, state):
            fake = FakeHfApi()
            planned = {m: hf.plan(m, weights[m], DOIS[m], release) for m in hf.MODELS}
            for model in hf.MODELS:
                hf.upload(fake, planned[model], model, Add)
        self.assertEqual([c[:2] for c in fake.calls],
                         [(kind, hf.HF_REPOS[m]) for m in hf.MODELS for kind in ('create_repo', 'create_commit')])
        create = fake.calls[0][2]
        self.assertEqual((create['private'], create['exist_ok'], create['repo_type']), (False, True, 'model'))
        self.assertEqual(fake.calls[1][2], ['README.md', 'heocr-r4d-segmentation.safetensors', 'LICENSE', 'NOTICE',
                                            'r4d_training_run.json'])

    def test_token_only_from_the_environment_and_never_printed(self):
        with self.assertRaisesRegex(hf.DepositError, 'HF_TOKEN'):
            hf.read_token({})

        class Failing(FakeHfApi):
            def create_repo(self, repo_id, **kwargs):
                raise RuntimeError(f'401 for token {self.token}')

        with release_copy() as (_, weights, state):
            seen = []

            def factory(token):
                seen.append(token)
                return Failing(token)

            original = hf.RELEASE
            try:
                # a real upload reads the repository's release/, so point RELEASE at the copy for this test
                hf.RELEASE = (state.parent / 'release').resolve()
                code, out, err = run(['--release-dir', str(hf.RELEASE), '--zenodo-state', str(state),
                                      *weights_args(weights)], {'HF_TOKEN': TOKEN}, factory)
            finally:
                hf.RELEASE = original
        self.assertEqual(seen, [TOKEN])
        self.assertEqual(code, 1)
        self.assertNotIn(TOKEN, out + err)
        self.assertIn('<token>', err)



R6_DOI = '10.5281/zenodo.666'


@contextlib.contextmanager
def r6_release_copy(api=None, records=None):
    """A release/ copy with R6 only: its card cites R6_DOI, fake weights match its record; an R6-only state file."""
    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory)
        release = directory / 'release'
        shutil.copytree(ROOT / 'release' / 'r6', release / 'r6')
        body = release / 'r6' / 'card_body.md'
        body.write_text(body.read_text(encoding='utf-8') + f'\nCite {R6_DOI}.\n', encoding='utf-8')
        weights = directory / 'heb.traineddata'
        weights.write_bytes(b'r6 weights')
        record_path = release / 'r6' / 'r6_training_run.json'
        record = json.loads(record_path.read_text(encoding='utf-8'))
        record['output']['model_sha256'] = hashlib.sha256(b'r6 weights').hexdigest()
        record_path.write_text(json.dumps(record), encoding='utf-8')
        state = directory / 'r6-state.json'
        state.write_text(json.dumps({'api': api or hf.zenodo.PRODUCTION,
                                     'records': records or {'r6': {'id': 'rec6', 'doi': R6_DOI}}}))
        yield release, weights, state


class R6HfTests(unittest.TestCase):
    def test_r6_repository_and_default_models(self):
        self.assertEqual(hf.HF_REPOS['r6'], 'HeOCR/heocr-r6-tesseract-heb')
        self.assertEqual(hf.MODELS, ('r4d', 'a1', 'r3h'))  # the default run is the first release, unchanged

    def test_r6_dry_run_plans_one_public_repo_without_network_or_token(self):
        with r6_release_copy(api=hf.zenodo.SANDBOX) as (release, weights, state):
            code, out, err = run(['--dry-run', '--models', 'r6', '--release-dir', str(release),
                                  '--zenodo-state', str(state), '--weights', f'r6={weights}'])
        self.assertEqual(code, 0, err)
        planned = json.loads(out)
        self.assertEqual((planned['repo_id'], planned['public']), ('HeOCR/heocr-r6-tesseract-heb', True))
        self.assertEqual([f['path'] for f in planned['files']],
                         ['README.md', 'heocr_r6.traineddata', 'LICENSE', 'NOTICE', 'r6_training_run.json'])

    def test_r6_card_front_matter(self):
        with r6_release_copy() as (release, _, _):
            card = hf.build_card('r6', R6_DOI, release)
        front = card.split('\n---\n', 1)[0]
        self.assertTrue(front.startswith('---\nlicense: apache-2.0'))
        for line in ('  - he', '  - tesseract', '  - ocr', '  - hebrew'):
            self.assertIn(line, front.splitlines())
        self.assertNotIn('#', front)

    def test_r6_needs_its_own_state_file(self):
        with r6_release_copy(records={m: {'id': m, 'doi': d} for m, d in DOIS.items()}) as (release, weights, state):
            code, _, err = run(['--dry-run', '--models', 'r6', '--release-dir', str(release),
                                '--zenodo-state', str(state), '--weights', f'r6={weights}'])
        self.assertEqual(code, 1)
        self.assertIn('own state file', err)
        with release_copy() as (release, weights, state):
            code, _, err = run(['--dry-run', '--models', 'r3h', 'r6', '--release-dir', str(release),
                                '--zenodo-state', str(state), *weights_args(weights)])
        self.assertEqual(code, 1)
        self.assertIn('release of its own', err)

    def test_r6_upload_is_one_commit_to_its_repo(self):
        with r6_release_copy() as (release, weights, _):
            fake = FakeHfApi()
            hf.upload(fake, hf.plan('r6', weights, R6_DOI, release), 'r6', Add)
        self.assertEqual([c[:2] for c in fake.calls], [('create_repo', 'HeOCR/heocr-r6-tesseract-heb'),
                                                       ('create_commit', 'HeOCR/heocr-r6-tesseract-heb')])
        self.assertEqual(fake.calls[1][2], ['README.md', 'heocr_r6.traineddata', 'LICENSE', 'NOTICE',
                                            'r6_training_run.json'])


R7_DOI = '10.5281/zenodo.777'


@contextlib.contextmanager
def r7_release_copy(api=None, records=None):
    """A release/ copy with R7 only: its card cites R7_DOI, fake weights match its record; an R7-only state file."""
    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory)
        release = directory / 'release'
        shutil.copytree(ROOT / 'release' / 'r7', release / 'r7')
        body = release / 'r7' / 'card_body.md'
        body.write_text(body.read_text(encoding='utf-8') + f'\nCite {R7_DOI}.\n', encoding='utf-8')
        weights = directory / 'heb.traineddata'
        weights.write_bytes(b'r7 weights')
        record_path = release / 'r7' / 'r7_training_run.json'
        record = json.loads(record_path.read_text(encoding='utf-8'))
        record['output']['model_sha256'] = hashlib.sha256(b'r7 weights').hexdigest()
        record_path.write_text(json.dumps(record), encoding='utf-8')
        state = directory / 'r7-state.json'
        state.write_text(json.dumps({'api': api or hf.zenodo.PRODUCTION,
                                     'records': records or {'r7': {'id': 'rec7', 'doi': R7_DOI}}}))
        yield release, weights, state


class R7HfTests(unittest.TestCase):
    def test_r7_repository(self):
        self.assertEqual(hf.HF_REPOS['r7'], 'HeOCR/heocr-r7-tesseract-heb')
        self.assertEqual(hf.HF_REPOS['r6'], 'HeOCR/heocr-r6-tesseract-heb')  # R6's repository is unchanged
        self.assertEqual(hf.MODELS, ('r4d', 'a1', 'r3h'))

    def test_r7_dry_run_plans_one_public_repo_without_network_or_token(self):
        with r7_release_copy(api=hf.zenodo.SANDBOX) as (release, weights, state):
            code, out, err = run(['--dry-run', '--models', 'r7', '--release-dir', str(release),
                                  '--zenodo-state', str(state), '--weights', f'r7={weights}'])
        self.assertEqual(code, 0, err)
        planned = json.loads(out)
        self.assertEqual((planned['repo_id'], planned['public']), ('HeOCR/heocr-r7-tesseract-heb', True))
        self.assertEqual([f['path'] for f in planned['files']],
                         ['README.md', 'heocr_r7.traineddata', 'LICENSE', 'NOTICE', 'r7_training_run.json'])

    def test_r7_card_front_matter(self):
        with r7_release_copy() as (release, _, _):
            card = hf.build_card('r7', R7_DOI, release)
        front = card.split('\n---\n', 1)[0]
        self.assertTrue(front.startswith('---\nlicense: apache-2.0'))
        for line in ('  - he', '  - tesseract', '  - ocr', '  - hebrew'):
            self.assertIn(line, front.splitlines())
        self.assertNotIn('#', front)

    def test_the_repository_card_is_refused_until_it_cites_its_doi(self):
        with self.assertRaisesRegex(hf.DepositError, 'step 2'):
            hf.build_card('r7', R7_DOI)

    def test_r7_needs_its_own_state_file(self):
        with r7_release_copy(records={'r6': {'id': 'rec6', 'doi': '10.5281/zenodo.24109989'}}) as (release, weights,
                                                                                                    state):
            code, _, err = run(['--dry-run', '--models', 'r7', '--release-dir', str(release),
                                '--zenodo-state', str(state), '--weights', f'r7={weights}'])
        self.assertEqual(code, 1)
        self.assertIn('own state file', err)
        with r7_release_copy() as (release, weights, state):
            code, _, err = run(['--dry-run', '--models', 'r6', 'r7', '--release-dir', str(release),
                                '--zenodo-state', str(state), '--weights', f'r7={weights}', f'r6={weights}'])
        self.assertEqual(code, 1)
        self.assertIn('release of its own', err)

    def test_r7_upload_is_one_commit_to_its_repo(self):
        with r7_release_copy() as (release, weights, _):
            fake = FakeHfApi()
            hf.upload(fake, hf.plan('r7', weights, R7_DOI, release), 'r7', Add)
        self.assertEqual([c[:2] for c in fake.calls], [('create_repo', 'HeOCR/heocr-r7-tesseract-heb'),
                                                       ('create_commit', 'HeOCR/heocr-r7-tesseract-heb')])
        self.assertEqual(fake.calls[1][2], ['README.md', 'heocr_r7.traineddata', 'LICENSE', 'NOTICE',
                                            'r7_training_run.json'])


R8B_DOI = '10.5281/zenodo.888'
R8B_FILES = ['README.md', 'heocr_r8b.traineddata', 'LICENSE', 'NOTICE', 'r8b_training_run.json']


@contextlib.contextmanager
def r8b_release_copy(api=None, records=None):
    """A release/ copy with R8b only: its card cites R8B_DOI, fake weights match its record; an R8b-only state file."""
    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory)
        release = directory / 'release'
        shutil.copytree(ROOT / 'release' / 'r8b', release / 'r8b')
        body = release / 'r8b' / 'card_body.md'
        body.write_text(body.read_text(encoding='utf-8') + f'\nCite {R8B_DOI}.\n', encoding='utf-8')
        weights = directory / 'heb.traineddata'
        weights.write_bytes(b'r8b weights')
        record_path = release / 'r8b' / 'r8b_training_run.json'
        record = json.loads(record_path.read_text(encoding='utf-8'))
        record['output']['model_sha256'] = hashlib.sha256(b'r8b weights').hexdigest()
        record_path.write_text(json.dumps(record), encoding='utf-8')
        state = directory / 'r8b-state.json'
        state.write_text(json.dumps({'api': api or hf.zenodo.PRODUCTION,
                                     'records': records or {'r8b': {'id': 'rec8', 'doi': R8B_DOI}}}))
        yield release, weights, state


class R8bHfTests(unittest.TestCase):
    def test_r8b_repository(self):
        self.assertEqual(hf.HF_REPOS['r8b'], 'HeOCR/heocr-r8b-tesseract-heb')
        self.assertEqual(hf.HF_REPOS['r7'], 'HeOCR/heocr-r7-tesseract-heb')  # R7's repository is unchanged
        self.assertEqual(hf.MODELS, ('r4d', 'a1', 'r3h'))

    def test_r8b_dry_run_plans_one_public_repo_without_network_or_token(self):
        with r8b_release_copy(api=hf.zenodo.SANDBOX) as (release, weights, state):
            code, out, err = run(['--dry-run', '--models', 'r8b', '--release-dir', str(release),
                                  '--zenodo-state', str(state), '--weights', f'r8b={weights}'])
        self.assertEqual(code, 0, err)
        planned = json.loads(out)
        self.assertEqual((planned['repo_id'], planned['public']), ('HeOCR/heocr-r8b-tesseract-heb', True))
        self.assertEqual([f['path'] for f in planned['files']], R8B_FILES)

    def test_r8b_card_front_matter_names_r7_as_its_base(self):
        with r8b_release_copy() as (release, _, _):
            card = hf.build_card('r8b', R8B_DOI, release)
        front = card.split('\n---\n', 1)[0]
        self.assertTrue(front.startswith('---\nlicense: apache-2.0'))
        for line in ('base_model: HeOCR/heocr-r7-tesseract-heb', 'base_model_relation: finetune', '  - he',
                     '  - tesseract', '  - ocr', '  - hebrew'):
            self.assertIn(line, front.splitlines())
        self.assertNotIn('#', front)

    def test_the_r8b_repository_card_is_refused_until_it_cites_its_doi(self):
        with self.assertRaisesRegex(hf.DepositError, 'step 2'):
            hf.build_card('r8b', R8B_DOI)

    def test_r8b_needs_its_own_state_file(self):
        with r8b_release_copy(records={'r7': {'id': 'rec7', 'doi': '10.5281/zenodo.24126449'}}) as (release, weights,
                                                                                                    state):
            code, _, err = run(['--dry-run', '--models', 'r8b', '--release-dir', str(release),
                                '--zenodo-state', str(state), '--weights', f'r8b={weights}'])
        self.assertEqual(code, 1)
        self.assertIn('own state file', err)
        with r8b_release_copy() as (release, weights, state):
            code, _, err = run(['--dry-run', '--models', 'r7', 'r8b', '--release-dir', str(release),
                                '--zenodo-state', str(state), '--weights', f'r8b={weights}', f'r7={weights}'])
        self.assertEqual(code, 1)
        self.assertIn('release of its own', err)

    def test_r8b_upload_is_one_commit_to_its_repo(self):
        with r8b_release_copy() as (release, weights, _):
            fake = FakeHfApi()
            hf.upload(fake, hf.plan('r8b', weights, R8B_DOI, release), 'r8b', Add)
        self.assertEqual([c[:2] for c in fake.calls], [('create_repo', 'HeOCR/heocr-r8b-tesseract-heb'),
                                                       ('create_commit', 'HeOCR/heocr-r8b-tesseract-heb')])
        self.assertEqual(fake.calls[1][2], R8B_FILES)


if __name__ == '__main__':
    unittest.main()
