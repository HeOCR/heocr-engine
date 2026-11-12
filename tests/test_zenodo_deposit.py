import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
import urllib.error

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location('zenodo_deposit', ROOT / 'release' / 'zenodo_deposit.py')
zd = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(zd)

TOKEN = 'secret-token-123'
FRONT = {
    'summary': 'A model', 'license': 'Apache-2.0', 'tags': ['hebrew', 'kraken_pytorch'],
    'datasets': ['https://github.com/HeOCR/hocrsyngen/tree/bb14cd0/src/hocrsyngen/data/synthetic/texts'],
    'authors': [{'name': 'Palachy Affek, Shay', 'type': 'personal', 'orcid': 'https://orcid.org/0000-0002-1459-9320'},
                {'name': 'HeOCR maintainers', 'type': 'organizational'}],
    'communities': ['heocr', 'ocr_models'],
}


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeZenodo:
    """Records every request; answers like InvenioRDM. No network."""

    def __init__(self, fail=None):
        self.requests, self.fail, self.next_id = [], fail, 0

    def __call__(self, request, timeout=None):
        url, method = request.full_url, request.get_method()
        self.requests.append({'method': method, 'url': url, 'headers': dict(request.header_items()),
                              'data': request.data})
        if self.fail and self.fail in url:
            raise urllib.error.HTTPError(url, 403, 'Forbidden', {},
                                         io.BytesIO(f'bad token {TOKEN}'.encode()))
        path = url.split('/api', 1)[1]
        if method == 'POST' and path == '/records':
            self.next_id += 1
            body = {'id': f'rec{self.next_id}'}
        elif path.endswith('/draft/pids/doi'):
            body = {'pids': {'doi': {'identifier': f'10.5072/zenodo.{path.split("/")[2][3:]}00'}}}
        elif method == 'GET' and path.endswith('/draft'):
            body = {'pids': {'doi': {'identifier': '10.5072/zenodo.100', 'provider': 'datacite'}}}
        elif method == 'GET' and path.startswith('/communities/'):
            body = {'id': 'uuid-' + path.rsplit('/', 1)[1]}
        else:
            body = {'ok': True}
        return FakeResponse(json.dumps(body).encode())

    def calls(self):
        return [(r['method'], r['url'].split('/api', 1)[1]) for r in self.requests]


@contextlib.contextmanager
def outside_repository():
    with tempfile.TemporaryDirectory() as directory:
        yield Path(directory)


class TokenAndTargetTests(unittest.TestCase):
    def test_token_only_from_the_environment_and_only_in_a_header(self):
        with self.assertRaisesRegex(zd.DepositError, 'ZENODO_SANDBOX_TOKEN'):
            zd.read_token(zd.SANDBOX, {})
        with self.assertRaisesRegex(zd.DepositError, 'ZENODO_TOKEN'):
            zd.read_token(zd.PRODUCTION, {'ZENODO_SANDBOX_TOKEN': TOKEN})
        fake = FakeZenodo()
        zd.Api(zd.SANDBOX, TOKEN, fake).request('GET', '/records/rec1/draft')
        sent = fake.requests[0]
        self.assertEqual(sent['headers']['Authorization'], f'Bearer {TOKEN}')
        # InvenioRDM's own JSON; Zenodo answers plain application/json with its legacy serialization
        self.assertEqual(sent['headers']['Accept'], 'application/vnd.inveniordm.v1+json')
        self.assertNotIn(TOKEN, sent['url'])
        self.assertNotIn('access_token', sent['url'])

    def test_errors_redact_the_token(self):
        api = zd.Api(zd.SANDBOX, TOKEN, FakeZenodo(fail='/draft'))
        with self.assertRaises(zd.DepositError) as caught:
            api.request('GET', '/records/rec1/draft')
        self.assertIn('HTTP 403', str(caught.exception))
        self.assertNotIn(TOKEN, str(caught.exception))
        self.assertIn('<token>', str(caught.exception))

    def test_sandbox_is_the_default_and_the_token_is_never_printed(self):
        with outside_repository() as directory:
            state = directory / 'state.json'
            zd.save_state(state, {'api': zd.SANDBOX, 'records': {'r4d': {'id': 'rec1', 'doi': '10.5072/zenodo.100'}}})
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                self.assertEqual(zd.main(['--state', str(state), 'status'], {'ZENODO_SANDBOX_TOKEN': TOKEN}), 0)
                # the sandbox state file cannot be used against production
                self.assertEqual(zd.main(['--production', '--state', str(state), 'status'],
                                         {'ZENODO_TOKEN': TOKEN}), 1)
            self.assertNotIn(TOKEN, out.getvalue() + err.getvalue())
            self.assertIn('not https://zenodo.org/api', err.getvalue())


class ReleaseDirTests(unittest.TestCase):
    def test_release_dir_is_sandbox_only(self):
        with outside_repository() as directory:
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code = zd.main(['--production', '--release-dir', str(directory), '--state',
                                str(directory / 'state.json'), 'reserve'], {'ZENODO_TOKEN': TOKEN}, FakeZenodo())
            self.assertEqual(code, 1)
            self.assertIn('sandbox only', err.getvalue())

    def test_reserve_reads_the_given_release_dir(self):
        try:
            import yaml  # noqa: F401
        except ImportError:
            self.skipTest('PyYAML is not installed')
        with outside_repository() as directory:
            release = directory / 'sandbox-release'
            for model in zd.MODELS:
                (release / model).mkdir(parents=True)
                front = dict(FRONT, summary=f'copy of {model}')
                (release / model / 'zenodo.yaml').write_text(json.dumps(front))  # JSON is valid YAML
            fake = FakeZenodo()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = zd.main(['--release-dir', str(release), '--state', str(directory / 'state.json'), 'reserve'],
                               {'ZENODO_SANDBOX_TOKEN': TOKEN}, fake)
            self.assertEqual(code, 0)
            titles = [json.loads(r['data'])['metadata']['title'] for r in fake.requests if r['url'].endswith('/records')]
            self.assertEqual(titles, ['copy of r4d', 'copy of a1', 'copy of r3h'])

    def test_requests_lists_each_records_requests(self):
        class WithRequests(FakeZenodo):
            def __call__(self, request, timeout=None):
                if request.full_url.endswith('/requests'):
                    self.requests.append({'method': 'GET', 'url': request.full_url, 'headers': {}, 'data': None})
                    return FakeResponse(json.dumps({'hits': {'hits': [
                        {'id': 'q1', 'type': 'community-inclusion', 'status': 'submitted',
                         'receiver': {'community': 'uuid-ocr_models'}}]}}).encode())
                return super().__call__(request, timeout)
        with outside_repository() as directory:
            state = directory / 'state.json'
            zd.save_state(state, {'api': zd.SANDBOX, 'records': {'r3h': {'id': 'rec3', 'doi': '10.5072/zenodo.300'}}})
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                code = zd.main(['--models', 'r3h', '--state', str(state), 'requests'],
                               {'ZENODO_SANDBOX_TOKEN': TOKEN}, WithRequests())
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(out.getvalue())['status'], 'submitted')


class StateTests(unittest.TestCase):
    def test_state_file_must_be_outside_the_repository(self):
        for path in (ROOT / 'state.json', ROOT / 'release' / 'state.json'):
            with self.subTest(path=path.name):
                with self.assertRaisesRegex(zd.DepositError, 'outside the repository'):
                    zd.load_state(path, zd.SANDBOX)
                with self.assertRaisesRegex(zd.DepositError, 'outside the repository'):
                    zd.save_state(path, {'api': zd.SANDBOX, 'records': {}})

    def test_state_is_private_and_holds_no_token(self):
        with outside_repository() as directory:
            path = directory / 'state.json'
            zd.save_state(path, {'api': zd.SANDBOX, 'records': {}})
            self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)


class MappingTests(unittest.TestCase):
    def test_creators(self):
        self.assertEqual(zd.creators(FRONT['authors']), [
            {'person_or_org': {'type': 'personal', 'family_name': 'Palachy Affek', 'given_name': 'Shay',
                               'identifiers': [{'scheme': 'orcid', 'identifier': '0000-0002-1459-9320'}]}},
            {'person_or_org': {'type': 'organizational', 'name': 'HeOCR maintainers'}}])
        for bad in ([{'name': 'Shay Palachy Affek', 'type': 'personal'}], [{'name': 'HeOCR maintainers'}]):
            with self.subTest(bad=bad):
                with self.assertRaises(zd.DepositError):
                    zd.creators(bad)

    def test_record_metadata_follows_htrmopo(self):
        metadata = zd.record_metadata(FRONT, '<p>card</p>', '2026-11-06')
        self.assertEqual(metadata['title'], 'A model')
        self.assertEqual(metadata['resource_type'], {'id': 'publication-other'})
        self.assertEqual(metadata['rights'], [{'id': 'apache-2.0'}])
        self.assertEqual(metadata['publisher'], 'Zenodo')  # required for DOI registration
        self.assertEqual(metadata['subjects'], [{'subject': 'hebrew'}, {'subject': 'kraken_pytorch'}])
        self.assertEqual(metadata['related_identifiers'][0]['relation_type'], {'id': 'isderivedfrom'})
        self.assertEqual(metadata['description'], '<p>card</p>')

    def test_card_must_cite_its_reserved_doi(self):
        with self.assertRaisesRegex(zd.DepositError, 'step 2'):
            zd.build_card(FRONT, 'no doi here', '10.5072/zenodo.100', validate=lambda front: None)
        seen = []
        try:
            card = zd.build_card(FRONT, 'cite 10.5072/zenodo.100', '10.5072/zenodo.100', validate=seen.append)
        except ImportError:
            self.skipTest('PyYAML is not installed')
        self.assertEqual(seen[0]['id'], '10.5072/zenodo.100')
        self.assertTrue(card.startswith('---\n') and card.endswith('cite 10.5072/zenodo.100'))

    def test_weights_must_match_the_record(self):
        with outside_repository() as directory:
            release = directory / 'release'
            (release / 'a1').mkdir(parents=True)
            weights = directory / 'w.safetensors'
            weights.write_bytes(b'weights')
            record = {'output': {'model_sha256': hashlib.sha256(b'weights').hexdigest(),
                                 'release_file_name': 'heocr-a1-reading-order.safetensors'}}
            (release / 'a1' / 'a1_training_run.json').write_text(json.dumps(record))
            files = zd.deposit_files('a1', weights, release)
            self.assertEqual(sorted(files), ['LICENSE', 'NOTICE', 'a1_training_run.json',
                                             'heocr-a1-reading-order.safetensors'])
            weights.write_bytes(b'other')
            with self.assertRaisesRegex(zd.DepositError, 'does not match'):
                zd.deposit_files('a1', weights, release)


class StepTests(unittest.TestCase):
    def test_reserve_creates_three_drafts_with_dois_and_resumes(self):
        fake = FakeZenodo()
        api = zd.Api(zd.SANDBOX, TOKEN, fake)
        with outside_repository() as directory:
            path = directory / 'state.json'
            state = zd.reserve(api, {'api': zd.SANDBOX, 'records': {}}, {m: FRONT for m in zd.MODELS}, path,
                               '2026-11-06')
            self.assertEqual(list(state['records']), ['r4d', 'a1', 'r3h'])
            self.assertEqual(fake.calls(), [('POST', '/records'), ('POST', '/records/rec1/draft/pids/doi'),
                                            ('POST', '/records'), ('POST', '/records/rec2/draft/pids/doi'),
                                            ('POST', '/records'), ('POST', '/records/rec3/draft/pids/doi')])
            self.assertEqual(json.loads(path.read_text())['records']['r4d'],
                             {'id': 'rec1', 'doi': '10.5072/zenodo.100'})
            created = json.loads(fake.requests[0]['data'])
            self.assertEqual(created['metadata']['creators'][1]['person_or_org']['type'], 'organizational')
            self.assertNotIn(TOKEN, path.read_text())
            zd.reserve(api, state, {m: FRONT for m in zd.MODELS}, path, '2026-11-06')
            self.assertEqual(len(fake.requests), 6)
            self.assertTrue(all(r['url'].startswith(zd.SANDBOX) for r in fake.requests))

    def test_reserve_survives_a_crash_between_draft_and_doi(self):
        fronts = {m: FRONT for m in zd.MODELS}
        with outside_repository() as directory:
            path = directory / 'state.json'
            crashing = FakeZenodo(fail='/pids/doi')
            with self.assertRaises(zd.DepositError):
                zd.reserve(zd.Api(zd.SANDBOX, TOKEN, crashing), {'api': zd.SANDBOX, 'records': {}}, fronts, path,
                           '2026-11-06')
            # the draft was saved before the DOI call, so it is not lost
            saved = json.loads(path.read_text())
            self.assertEqual(saved['records'], {'r4d': {'id': 'rec1'}})
            fake = FakeZenodo()
            fake.next_id = 1
            state = zd.reserve(zd.Api(zd.SANDBOX, TOKEN, fake), zd.load_state(path, zd.SANDBOX), fronts, path,
                               '2026-11-06')
            # the resume reserves rec1's DOI without creating a second r4d draft, then does a1 and r3h
            self.assertEqual(fake.calls(), [('POST', '/records/rec1/draft/pids/doi'),
                                            ('POST', '/records'), ('POST', '/records/rec2/draft/pids/doi'),
                                            ('POST', '/records'), ('POST', '/records/rec3/draft/pids/doi')])
            self.assertEqual({m: r['id'] for m, r in state['records'].items()},
                             {'r4d': 'rec1', 'a1': 'rec2', 'r3h': 'rec3'})
            self.assertTrue(all(r.get('doi') for r in json.loads(path.read_text())['records'].values()))

    def test_a_legacy_shaped_doi_response_is_a_clear_error(self):
        class Legacy(FakeZenodo):
            def __call__(self, request, timeout=None):
                if request.full_url.endswith('/pids/doi'):
                    self.requests.append({'method': 'POST', 'url': request.full_url, 'headers': {}, 'data': None})
                    return FakeResponse(json.dumps({'id': 635063, 'doi': '10.5072/zenodo.635063'}).encode())
                return super().__call__(request, timeout)
        with outside_repository() as directory:
            path = directory / 'state.json'
            with self.assertRaisesRegex(zd.DepositError, r'no pids\.doi\.identifier.*saved without a DOI'):
                zd.reserve(zd.Api(zd.SANDBOX, TOKEN, Legacy()), {'api': zd.SANDBOX, 'records': {}},
                           {m: FRONT for m in zd.MODELS}, path, '2026-11-06')
            self.assertEqual(json.loads(path.read_text())['records'], {'r4d': {'id': 'rec1'}})
            # later steps refuse a draft that has no DOI yet
            with self.assertRaisesRegex(zd.DepositError, 'step 1'):
                zd.publish(zd.Api(zd.SANDBOX, TOKEN, FakeZenodo()), zd.load_state(path, zd.SANDBOX), 'r4d', [])

    def test_upload_starts_uploads_and_commits_each_file(self):
        fake = FakeZenodo()
        state = {'api': zd.SANDBOX, 'records': {'a1': {'id': 'rec7', 'doi': '10.5072/zenodo.700'}}}
        with outside_repository() as directory:
            licence = directory / 'LICENSE'
            licence.write_text('Apache')
            zd.upload(zd.Api(zd.SANDBOX, TOKEN, fake), state, 'a1', '---\nid: x\n---\nbody', {'LICENSE': licence})
        self.assertEqual(fake.calls(), [
            ('POST', '/records/rec7/draft/files'),
            ('PUT', '/records/rec7/draft/files/README.md/content'), ('POST', '/records/rec7/draft/files/README.md/commit'),
            ('PUT', '/records/rec7/draft/files/LICENSE/content'), ('POST', '/records/rec7/draft/files/LICENSE/commit')])
        self.assertEqual(json.loads(fake.requests[0]['data']), [{'key': 'README.md'}, {'key': 'LICENSE'}])
        self.assertEqual(fake.requests[3]['data'], b'Apache')

    def test_metadata_keeps_the_reserved_doi(self):
        fake = FakeZenodo()
        api = zd.Api(zd.SANDBOX, TOKEN, fake)
        state = {'api': zd.SANDBOX, 'records': {'r4d': {'id': 'rec1', 'doi': '10.5072/zenodo.100'}}}
        zd.set_metadata(api, state, 'r4d', {'title': 'A model'})
        sent = json.loads(fake.requests[1]['data'])
        self.assertEqual(sent['pids']['doi']['identifier'], '10.5072/zenodo.100')
        state['records']['r4d']['doi'] = '10.5072/zenodo.999'
        with self.assertRaisesRegex(zd.DepositError, 'not the reserved one'):
            zd.set_metadata(api, state, 'r4d', {'title': 'A model'})

    def test_publish_then_request_inclusion_in_each_community(self):
        fake = FakeZenodo()
        state = {'api': zd.SANDBOX, 'records': {'r3h': {'id': 'rec3', 'doi': '10.5072/zenodo.300'}}}
        zd.publish(zd.Api(zd.SANDBOX, TOKEN, fake), state, 'r3h', ['heocr', 'ocr_models'])
        self.assertEqual(fake.calls(), [('GET', '/communities/heocr'), ('GET', '/communities/ocr_models'),
                                        ('POST', '/records/rec3/draft/actions/publish'),
                                        ('POST', '/records/rec3/communities')])
        self.assertEqual(json.loads(fake.requests[3]['data']),
                         {'communities': [{'id': 'uuid-heocr'}, {'id': 'uuid-ocr_models'}]})

    def test_a_missing_community_stops_before_publishing(self):
        fake = FakeZenodo(fail='/communities/heocr')
        state = {'api': zd.SANDBOX, 'records': {'r3h': {'id': 'rec3', 'doi': '10.5072/zenodo.300'}}}
        with self.assertRaisesRegex(zd.DepositError, "'heocr' not found.*nothing was published"):
            zd.publish(zd.Api(zd.SANDBOX, TOKEN, fake), state, 'r3h', ['heocr', 'ocr_models'])
        self.assertNotIn('publish', ' '.join(path for _, path in fake.calls()))
        self.assertNotIn('published', state['records']['r3h'])

    def test_steps_need_a_reserved_draft(self):
        with self.assertRaisesRegex(zd.DepositError, 'step 1'):
            zd.publish(zd.Api(zd.SANDBOX, TOKEN, FakeZenodo()), {'api': zd.SANDBOX, 'records': {}}, 'r3h', [])


HEOCR_SANDBOX = 'c261ed63-f520-48a3-90c2-c64ed1cc0395'
OCR_MODELS = 'a980b106-f79b-4681-ae4c-d42737701217'


class Requests(FakeZenodo):
    """A record with inclusion requests; `current` overrides what GET /requests/{id} returns."""

    def __init__(self, hits, current=None):
        super().__init__()
        self.hits, self.current = hits, current or {}

    def __call__(self, request, timeout=None):
        url, method = request.full_url, request.get_method()
        path = url.split('/api', 1)[1]
        self.requests.append({'method': method, 'url': url, 'headers': dict(request.header_items()),
                              'data': request.data})
        if path.endswith('/requests'):
            body = {'hits': {'hits': self.hits}}
        elif path.startswith('/requests/') and method == 'GET':
            rid = path.split('/')[2]
            body = self.current.get(rid) or next(h for h in self.hits if h['id'] == rid)
        elif path.endswith('/actions/accept'):
            body = {'status': 'accepted', 'is_closed': True}
        else:
            body = {}
        return FakeResponse(json.dumps(body).encode())


def inclusion(rid, community, status='submitted'):
    return {'id': rid, 'type': 'community-inclusion', 'status': status, 'receiver': {'community': community}}


class AcceptTests(unittest.TestCase):
    STATE = {'api': zd.SANDBOX, 'records': {'r4d': {'id': 'rec1', 'doi': '10.5072/zenodo.100'}}}

    def test_accepts_only_the_owned_community(self):
        fake = Requests([inclusion('q-ocr', OCR_MODELS), inclusion('q-heocr', HEOCR_SANDBOX)])
        lines = zd.accept_owned(zd.Api(zd.SANDBOX, TOKEN, fake), self.STATE, 'r4d', zd.OWNED_COMMUNITIES[zd.SANDBOX])
        self.assertEqual([(l['request'], l['action']) for l in lines],
                         [('q-ocr', 'left for its moderators'), ('q-heocr', 'accepted')])
        self.assertEqual(fake.calls(), [('GET', '/records/rec1/requests'), ('GET', '/requests/q-heocr'),
                                        ('POST', '/requests/q-heocr/actions/accept')])
        self.assertNotIn('q-ocr', ' '.join(path for _, path in fake.calls()[1:]))

    def test_skips_what_is_not_still_a_submitted_owned_request(self):
        changed = {**inclusion('q-moved', HEOCR_SANDBOX), 'receiver': {'community': OCR_MODELS}}
        fake = Requests([inclusion('q-done', HEOCR_SANDBOX, 'accepted'), inclusion('q-moved', HEOCR_SANDBOX)],
                        current={'q-moved': changed})
        lines = zd.accept_owned(zd.Api(zd.SANDBOX, TOKEN, fake), self.STATE, 'r4d', zd.OWNED_COMMUNITIES[zd.SANDBOX])
        self.assertEqual([l['action'] for l in lines], ['skipped', 'skipped'])
        self.assertFalse([p for m, p in fake.calls() if p.endswith('/actions/accept')])

    def test_each_target_has_its_own_owned_community(self):
        production = zd.OWNED_COMMUNITIES[zd.PRODUCTION]['heocr']
        self.assertEqual(production, 'febfcbcf-2444-4a84-8699-04cd1c44c8a7')
        # the sandbox heocr id is not owned on production, so nothing is accepted there
        fake = Requests([inclusion('q-heocr', HEOCR_SANDBOX)])
        lines = zd.accept_owned(zd.Api(zd.PRODUCTION, TOKEN, fake), self.STATE, 'r4d',
                                zd.OWNED_COMMUNITIES[zd.PRODUCTION])
        self.assertEqual(lines[0]['action'], 'left for its moderators')
        self.assertEqual(len(fake.requests), 1)

    def test_accept_command(self):
        with outside_repository() as directory:
            state = directory / 'state.json'
            zd.save_state(state, self.STATE)
            fake = Requests([inclusion('q-ocr', OCR_MODELS), inclusion('q-heocr', HEOCR_SANDBOX)])
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                code = zd.main(['--models', 'r4d', '--state', str(state), 'accept'],
                               {'ZENODO_SANDBOX_TOKEN': TOKEN}, fake)
            self.assertEqual(code, 0)
            actions = [json.loads(line)['action'] for line in out.getvalue().splitlines()]
            self.assertEqual(actions, ['left for its moderators', 'accepted'])
            self.assertNotIn(TOKEN, out.getvalue())


class ReleaseFrontMatterTests(unittest.TestCase):
    def test_release_front_matter_maps_cleanly(self):
        try:
            fronts = {model: zd.read_front(model) for model in zd.MODELS}
        except ImportError:
            self.skipTest('PyYAML is not installed')
        for model, front in fronts.items():
            with self.subTest(model=model):
                metadata = zd.record_metadata(front, '<p></p>', '2026-11-06')
                self.assertEqual(metadata['rights'], [{'id': 'apache-2.0'}])
                self.assertEqual(len(metadata['creators']), 2)
                self.assertEqual(front['communities'], ['heocr', 'ocr_models'])



R6_DOI = '10.5072/zenodo.600'


def _need_yaml(test):
    try:
        import yaml  # noqa: F401
    except ImportError:
        test.skipTest('PyYAML is not installed')


class NoNetwork:
    """An opener that fails the test if any request is made."""

    def __call__(self, request, timeout=None):
        raise AssertionError(f'network request: {request.get_method()} {request.full_url}')


@contextlib.contextmanager
def r6_release_copy():
    """A release/ copy whose R6 card cites R6_DOI, with fake weights matching R6's copied record."""
    import shutil
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
        yield directory, release, weights


def run_main(argv, environ, opener):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = zd.main(argv, environ, opener)
    return code, out.getvalue(), err.getvalue()


class R6Tests(unittest.TestCase):
    """R6 (Tesseract) is a release of its own: plain card, heocr only, own state file; R4d/A1/R3h unchanged."""

    def test_r6_is_selectable_but_not_a_default(self):
        self.assertEqual(zd.MODELS, ('r4d', 'a1', 'r3h'))
        self.assertIn('r6', zd.CHOICES)
        self.assertEqual(zd.release_of('r3h'), 'first')
        self.assertEqual(zd.release_of('r6'), 'r6')

    def test_validators_by_model(self):
        for model in zd.MODELS:
            self.assertIs(zd.validate_front(model), zd.validate_htrmopo)
        self.assertIs(zd.validate_front('r6'), zd.validate_plain)
        front = dict(FRONT, communities=['heocr'], id=R6_DOI)
        zd.validate_plain(front)
        for bad, message in ((dict(front, communities=['heocr', 'ocr_models']), 'ocr_models'),
                             ({k: v for k, v in front.items() if k != 'id'}, 'lacks id'),
                             (dict(front, license='CC-BY-NC-4.0'), 'Apache-2.0'),
                             (dict(front, authors=[{'name': 'HeOCR maintainers'}]), 'type')):
            with self.subTest(message=message):
                with self.assertRaisesRegex(zd.DepositError, message):
                    zd.validate_plain(bad)

    def test_r6_front_matter_maps_with_its_own_links_and_the_same_creators(self):
        _need_yaml(self)
        front, first = zd.read_front('r6'), zd.read_front('r3h')
        self.assertEqual(front['communities'], ['heocr'])
        self.assertEqual(front['authors'], first['authors'])
        metadata = zd.record_metadata(front, '<p></p>', '2026-11-10')
        self.assertEqual(metadata['creators'], zd.record_metadata(first, '<p></p>', '2026-11-10')['creators'])
        self.assertEqual(metadata['rights'], [{'id': 'apache-2.0'}])
        self.assertEqual(metadata['resource_type'], {'id': 'publication-other'})
        links = {(r['identifier'], r['resource_type']['id']) for r in metadata['related_identifiers']}
        self.assertIn(('https://github.com/tesseract-ocr/tessdata_best/blob/e12c65a915945e4c28e237a9b52bc4a8f39a0cec/'
                       'heb.traineddata', 'software'), links)
        for record in ('990020308000205171', '990020495520205171', '990020522850205171', '990019385920205171',
                       '990013538860205171'):
            self.assertIn((f'https://iiif.nli.org.il/IIIFv21/{record}/manifest', 'image'), links)
        self.assertTrue(all(r['relation_type'] == {'id': 'isderivedfrom'} for r in metadata['related_identifiers']))
        self.assertIn({'subject': 'tesseract'}, metadata['subjects'])

    def test_record_metadata_without_related_is_unchanged(self):
        # the kraken front matter has no `related`, so its mapping is exactly what it was
        self.assertEqual(zd.record_metadata(FRONT, '<p>card</p>', '2026-11-06')['related_identifiers'],
                         [{'identifier': FRONT['datasets'][0], 'scheme': 'url',
                           'relation_type': {'id': 'isderivedfrom'}, 'resource_type': {'id': 'dataset'}}])

    def test_r6_is_never_mixed_with_the_first_release(self):
        with self.assertRaisesRegex(zd.DepositError, 'release of its own'):
            zd.check_one_release(['r6', 'r3h'])
        with self.assertRaisesRegex(zd.DepositError, 'own state file'):
            zd.check_one_release(['r6'], {'r4d': {'id': 'rec1'}})
        zd.check_one_release(['r6'], {'r6': {'id': 'rec9'}})
        zd.check_one_release(list(zd.MODELS), {'r4d': {'id': 'rec1'}})
        with outside_repository() as directory:
            state = directory / 'state.json'
            zd.save_state(state, {'api': zd.SANDBOX, 'records': {'r4d': {'id': 'rec1', 'doi': '10.5072/zenodo.100'}}})
            code, _, err = run_main(['--models', 'r6', '--state', str(state), 'publish'],
                                    {'ZENODO_SANDBOX_TOKEN': TOKEN}, NoNetwork())
            self.assertEqual(code, 1)
            self.assertIn('own state file', err)
            code, _, err = run_main(['--models', 'r6', 'r3h', '--state', str(directory / 'new.json'), 'reserve'],
                                    {'ZENODO_SANDBOX_TOKEN': TOKEN}, NoNetwork())
            self.assertEqual(code, 1)
            self.assertIn('release of its own', err)
            # status of any single-release state file still works
            self.assertEqual(run_main(['--state', str(state), 'status'], {}, NoNetwork())[0], 0)

    def test_reserve_r6_alone(self):
        fake = FakeZenodo()
        with outside_repository() as directory:
            path = directory / 'r6-state.json'
            state = zd.reserve(zd.Api(zd.SANDBOX, TOKEN, fake), {'api': zd.SANDBOX, 'records': {}},
                               {'r6': dict(FRONT, communities=['heocr'])}, path, '2026-11-10', ('r6',))
        self.assertEqual(list(state['records']), ['r6'])
        self.assertEqual(fake.calls(), [('POST', '/records'), ('POST', '/records/rec1/draft/pids/doi')])

    def test_reserve_command_honours_models(self):
        _need_yaml(self)
        with outside_repository() as directory:
            fake = FakeZenodo()
            code, _, err = run_main(['--models', 'r6', '--state', str(directory / 's.json'), 'reserve'],
                                    {'ZENODO_SANDBOX_TOKEN': TOKEN}, fake)
            self.assertEqual(code, 0, err)
            self.assertEqual(len(fake.requests), 2)
            sent = json.loads(fake.requests[0]['data'])['metadata']
            self.assertTrue(sent['title'].startswith('Hebrew printed-text recognition for Tesseract'))
            self.assertEqual(len(sent['creators']), 2)

    def test_upload_r6_sends_the_plain_card_and_its_four_files(self):
        _need_yaml(self)
        with r6_release_copy() as (directory, release, weights):
            state = directory / 'state' / 'r6.json'
            zd.save_state(state, {'api': zd.SANDBOX, 'records': {'r6': {'id': 'rec6', 'doi': R6_DOI}}})
            original = zd.validate_htrmopo
            zd.validate_htrmopo = lambda front: self.fail('R6 must not be HTRMoPo-validated')
            try:
                fake = FakeZenodo()
                code, _, err = run_main(['--models', 'r6', '--release-dir', str(release), '--state', str(state),
                                         'upload', '--weights', f'r6={weights}'], {'ZENODO_SANDBOX_TOKEN': TOKEN}, fake)
            finally:
                zd.validate_htrmopo = original
        self.assertEqual(code, 0, err)
        self.assertEqual([k['key'] for k in json.loads(fake.requests[0]['data'])],
                         ['README.md', 'heocr_r6.traineddata', 'LICENSE', 'NOTICE', 'r6_training_run.json'])
        readme = fake.requests[1]['data'].decode('utf-8')
        self.assertTrue(readme.startswith('---\n'))
        self.assertIn(f'id: {R6_DOI}', readme)
        self.assertNotIn('ocr_models', readme.split('\n---\n', 1)[0])

    def test_publish_r6_requests_heocr_only(self):
        _need_yaml(self)
        with outside_repository() as directory:
            state = directory / 'r6.json'
            zd.save_state(state, {'api': zd.SANDBOX, 'records': {'r6': {'id': 'rec6', 'doi': R6_DOI}}})
            fake = FakeZenodo()
            code, _, err = run_main(['--models', 'r6', '--state', str(state), 'publish'],
                                    {'ZENODO_SANDBOX_TOKEN': TOKEN}, fake)
        self.assertEqual(code, 0, err)
        self.assertEqual(fake.calls(), [('GET', '/communities/heocr'), ('GET', '/communities/heocr'),
                                        ('POST', '/records/rec6/draft/actions/publish'),
                                        ('POST', '/records/rec6/communities')])
        self.assertEqual(json.loads(fake.requests[3]['data']), {'communities': [{'id': 'uuid-heocr'}]})

    def test_plan_needs_no_network_and_no_token(self):
        _need_yaml(self)
        try:
            import markdown  # noqa: F401
        except ImportError:
            self.skipTest('Markdown is not installed')
        with r6_release_copy() as (directory, release, weights):
            # before step 1: no state file and no DOI yet
            code, out, err = run_main(['--models', 'r6', '--release-dir', str(release), '--state',
                                       str(directory / 'none.json'), 'plan', '--weights', f'r6={weights}'],
                                      {}, NoNetwork())
            self.assertEqual(code, 0, err)
            planned = json.loads(out)
            self.assertEqual(planned['card']['format'], 'plain (not HTRMoPo)')
            self.assertIsNone(planned['card']['doi'])
            self.assertEqual(planned['communities'], ['heocr'])
            self.assertEqual([f['key'] for f in planned['files']],
                             ['README.md', 'heocr_r6.traineddata', 'LICENSE', 'NOTICE', 'r6_training_run.json'])
            self.assertEqual(planned['files'][1]['sha256'], hashlib.sha256(b'r6 weights').hexdigest())
            self.assertNotIn('description', planned['metadata'])
            self.assertFalse((directory / 'none.json').exists())  # plan never writes the state file
            # with a reserved DOI, the card's citation is checked as upload would
            state = directory / 'state' / 'r6.json'
            zd.save_state(state, {'api': zd.SANDBOX, 'records': {'r6': {'id': 'rec6', 'doi': '10.5072/zenodo.999'}}})
            code, _, err = run_main(['--models', 'r6', '--release-dir', str(release), '--state', str(state), 'plan'],
                                    {}, NoNetwork())
            self.assertEqual(code, 1)
            self.assertIn('step 2', err)
            # tampered weights are refused, as upload would
            weights.write_bytes(b'other')
            code, _, err = run_main(['--models', 'r6', '--release-dir', str(release), '--state',
                                     str(directory / 'none.json'), 'plan', '--weights', f'r6={weights}'], {}, NoNetwork())
            self.assertEqual(code, 1)
            self.assertIn('does not match', err)


R7_DOI = '10.5072/zenodo.700'
R7_NLI = ('990017640460205171', '990020308000205171', '990020495520205171', '990020522850205171',
          '990020466440205171', '990019385920205171', '990013538860205171')


@contextlib.contextmanager
def r7_release_copy():
    """A release/ copy whose R7 card cites R7_DOI, with fake weights matching R7's copied record."""
    import shutil
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
        yield directory, release, weights


class R7Tests(unittest.TestCase):
    """R7 (Tesseract) is a release of its own, like R6: plain card, heocr only, own state file."""

    def test_r7_is_selectable_but_not_a_default(self):
        self.assertEqual(zd.MODELS, ('r4d', 'a1', 'r3h'))
        self.assertEqual(zd.SEPARATE_RELEASES[:2], ('r6', 'r7'))  # later releases follow
        self.assertEqual(zd.release_of('r7'), 'r7')
        self.assertIs(zd.validate_front('r7'), zd.validate_plain)

    def test_r7_front_matter_maps_with_its_own_links_and_the_same_creators(self):
        _need_yaml(self)
        front, r6 = zd.read_front('r7'), zd.read_front('r6')
        self.assertEqual(front['communities'], ['heocr'])
        self.assertEqual(front['authors'], r6['authors'])
        zd.validate_plain(dict(front, id=R7_DOI))
        metadata = zd.record_metadata(front, '<p></p>', '2026-11-11')
        self.assertEqual(metadata['creators'], zd.record_metadata(r6, '<p></p>', '2026-11-11')['creators'])
        self.assertEqual(metadata['rights'], [{'id': 'apache-2.0'}])
        links = [(r['identifier'], r['resource_type']['id']) for r in metadata['related_identifiers']]
        self.assertEqual(len(links), len(set(links)))
        self.assertIn(('https://github.com/tesseract-ocr/tessdata_best/blob/e12c65a915945e4c28e237a9b52bc4a8f39a0cec/'
                       'heb.traineddata', 'software'), links)
        self.assertIn(('https://github.com/projectbenyehuda/public_domain_dump', 'dataset'), links)
        for record in R7_NLI:
            self.assertIn((f'https://iiif.nli.org.il/IIIFv21/{record}/manifest', 'image'), links)
        record = json.loads((ROOT / 'release' / 'r7' / 'r7_training_run.json').read_text(encoding='utf-8'))
        ia = [r['ia_identifier'] for r in record['data']['train'] if r['source'] == 'internet_archive']
        self.assertEqual(len(ia), 23)
        for identifier in ia:
            self.assertIn((f'https://archive.org/details/{identifier}', 'image'), links)
        self.assertEqual(len(links), 1 + len(R7_NLI) + len(ia) + 1)
        self.assertTrue(all(r['relation_type'] == {'id': 'isderivedfrom'} for r in metadata['related_identifiers']))
        # R7 is not derived from R6, and the script maps every `related` link to isDerivedFrom: no R6 link
        self.assertFalse([i for i, _ in links if '24109989' in i])

    def test_r6_and_r7_are_separate_releases(self):
        for models, state in ((['r7', 'r6'], {}), (['r7', 'r3h'], {}), (['r7'], {'r6': {'id': 'rec6'}}),
                              (['r6'], {'r7': {'id': 'rec7'}}), (list(zd.MODELS), {'r7': {'id': 'rec7'}})):
            with self.subTest(models=models, state=list(state)):
                with self.assertRaisesRegex(zd.DepositError, 'release of its own.*own state file'):
                    zd.check_one_release(models, state)
        zd.check_one_release(['r7'], {'r7': {'id': 'rec7'}})
        zd.check_one_release(['r6'], {'r6': {'id': 'rec6'}})
        with outside_repository() as directory:
            state = directory / 'r6.json'
            zd.save_state(state, {'api': zd.SANDBOX, 'records': {'r6': {'id': 'rec6', 'doi': '10.5072/zenodo.600'}}})
            code, _, err = run_main(['--models', 'r7', '--state', str(state), 'publish'],
                                    {'ZENODO_SANDBOX_TOKEN': TOKEN}, NoNetwork())
            self.assertEqual(code, 1)
            self.assertIn('own state file', err)

    def test_reserve_r7_alone(self):
        _need_yaml(self)
        with outside_repository() as directory:
            fake = FakeZenodo()
            code, _, err = run_main(['--models', 'r7', '--state', str(directory / 'r7.json'), 'reserve'],
                                    {'ZENODO_SANDBOX_TOKEN': TOKEN}, fake)
            self.assertEqual(code, 0, err)
            self.assertEqual(fake.calls(), [('POST', '/records'), ('POST', '/records/rec1/draft/pids/doi')])
            sent = json.loads(fake.requests[0]['data'])['metadata']
            self.assertTrue(sent['title'].startswith('Hebrew printed-text recognition for Tesseract'))
            self.assertTrue(sent['title'].endswith('(HeOCR R7)'))
            self.assertEqual(list(json.loads((directory / 'r7.json').read_text())['records']), ['r7'])

    def test_upload_r7_sends_the_plain_card_and_its_four_files(self):
        _need_yaml(self)
        with r7_release_copy() as (directory, release, weights):
            state = directory / 'state' / 'r7.json'
            zd.save_state(state, {'api': zd.SANDBOX, 'records': {'r7': {'id': 'rec7', 'doi': R7_DOI}}})
            original = zd.validate_htrmopo
            zd.validate_htrmopo = lambda front: self.fail('R7 must not be HTRMoPo-validated')
            try:
                fake = FakeZenodo()
                code, _, err = run_main(['--models', 'r7', '--release-dir', str(release), '--state', str(state),
                                         'upload', '--weights', f'r7={weights}'], {'ZENODO_SANDBOX_TOKEN': TOKEN}, fake)
            finally:
                zd.validate_htrmopo = original
        self.assertEqual(code, 0, err)
        self.assertEqual([k['key'] for k in json.loads(fake.requests[0]['data'])],
                         ['README.md', 'heocr_r7.traineddata', 'LICENSE', 'NOTICE', 'r7_training_run.json'])
        readme = fake.requests[1]['data'].decode('utf-8')
        self.assertIn(f'id: {R7_DOI}', readme)
        self.assertNotIn('ocr_models', readme.split('\n---\n', 1)[0])

    def test_publish_r7_requests_heocr_only(self):
        _need_yaml(self)
        with outside_repository() as directory:
            state = directory / 'r7.json'
            zd.save_state(state, {'api': zd.SANDBOX, 'records': {'r7': {'id': 'rec7', 'doi': R7_DOI}}})
            fake = FakeZenodo()
            code, _, err = run_main(['--models', 'r7', '--state', str(state), 'publish'],
                                    {'ZENODO_SANDBOX_TOKEN': TOKEN}, fake)
        self.assertEqual(code, 0, err)
        self.assertEqual(fake.calls(), [('GET', '/communities/heocr'), ('GET', '/communities/heocr'),
                                        ('POST', '/records/rec7/draft/actions/publish'),
                                        ('POST', '/records/rec7/communities')])

    def test_plan_r7_offline_and_the_draft_card_is_refused_once_a_doi_exists(self):
        _need_yaml(self)
        try:
            import markdown  # noqa: F401
        except ImportError:
            self.skipTest('Markdown is not installed')
        with outside_repository() as directory:
            # the repository's own card, before step 1: no DOI yet, so the DRAFT citation is fine
            code, out, err = run_main(['--models', 'r7', '--state', str(directory / 'none.json'), 'plan'],
                                      {}, NoNetwork())
            self.assertEqual(code, 0, err)
            planned = json.loads(out)
            self.assertEqual(planned['release'], 'r7')
            self.assertEqual(planned['card']['format'], 'plain (not HTRMoPo)')
            self.assertEqual(planned['communities'], ['heocr'])
            self.assertEqual(planned['files'][1], {'key': 'heocr_r7.traineddata', 'weights': 'not given',
                                                   'sha256': '95faab81fba6fe57f854f973c1ccad2b0d1059fb951f34b17277385ceea8b303'})
            self.assertEqual(len(planned['metadata']['related_identifiers']), 32)
            self.assertFalse((directory / 'none.json').exists())
            # after step 1 the card must cite the reserved DOI (step 2), and the draft card does not
            state = directory / 'r7.json'
            zd.save_state(state, {'api': zd.SANDBOX, 'records': {'r7': {'id': 'rec7', 'doi': R7_DOI}}})
            code, _, err = run_main(['--models', 'r7', '--state', str(state), 'plan'], {}, NoNetwork())
            self.assertEqual(code, 1)
            self.assertIn('step 2', err)
        with r7_release_copy() as (directory, release, weights):
            code, out, err = run_main(['--models', 'r7', '--release-dir', str(release), '--state',
                                       str(directory / 'none.json'), 'plan', '--weights', f'r7={weights}'],
                                      {}, NoNetwork())
            self.assertEqual(code, 0, err)
            self.assertEqual([f['key'] for f in json.loads(out)['files']],
                             ['README.md', 'heocr_r7.traineddata', 'LICENSE', 'NOTICE', 'r7_training_run.json'])


R8B_DOI = '10.5072/zenodo.800'
R8B_NLI = ('990017640460205171', '990020308000205171', '990020495520205171', '990026910840205171',
           '990020522850205171', '990020466440205171', '990019385920205171', '990013538860205171')
R8B_SHA = '8cb22dbeb195c3c0ffbe9c66cf956d8c2052d3b1c4a872234a85c975c4526117'
R8B_FILES = ['README.md', 'heocr_r8b.traineddata', 'LICENSE', 'NOTICE', 'r8b_training_run.json']


@contextlib.contextmanager
def r8b_release_copy():
    """A release/ copy whose R8b card cites R8B_DOI, with fake weights matching R8b's copied record."""
    import shutil
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
        yield directory, release, weights


class R8bTests(unittest.TestCase):
    """R8b (Tesseract) is a release of its own, like R6 and R7: plain card, heocr only, own state file."""

    def test_r8b_is_selectable_but_not_a_default(self):
        self.assertEqual(zd.MODELS, ('r4d', 'a1', 'r3h'))
        self.assertEqual(zd.SEPARATE_RELEASES, ('r6', 'r7', 'r8b'))
        self.assertEqual(zd.release_of('r8b'), 'r8b')
        self.assertIs(zd.validate_front('r8b'), zd.validate_plain)

    def test_r8b_front_matter_maps_with_its_own_links_and_the_same_creators(self):
        _need_yaml(self)
        front, r7 = zd.read_front('r8b'), zd.read_front('r7')
        self.assertEqual(front['communities'], ['heocr'])
        self.assertEqual(front['authors'], r7['authors'])
        zd.validate_plain(dict(front, id=R8B_DOI))
        metadata = zd.record_metadata(front, '<p></p>', '2026-11-12')
        self.assertEqual(metadata['creators'], zd.record_metadata(r7, '<p></p>', '2026-11-12')['creators'])
        self.assertEqual(metadata['rights'], [{'id': 'apache-2.0'}])
        links = [(r['identifier'], r['resource_type']['id']) for r in metadata['related_identifiers']]
        self.assertEqual(len(links), len(set(links)))
        self.assertIn(('https://github.com/tesseract-ocr/tessdata_best/blob/e12c65a915945e4c28e237a9b52bc4a8f39a0cec/'
                       'heb.traineddata', 'software'), links)
        self.assertIn(('https://doi.org/10.5281/zenodo.24126449', 'software'), links)  # continued from R7
        self.assertIn(('https://github.com/projectbenyehuda/public_domain_dump', 'dataset'), links)
        for record in R8B_NLI:
            self.assertIn((f'https://iiif.nli.org.il/IIIFv21/{record}/manifest', 'image'), links)
        record = json.loads((ROOT / 'release' / 'r8b' / 'r8b_training_run.json').read_text(encoding='utf-8'))
        ia = [r['ia_identifier'] for r in record['data']['train'] if r['source'] == 'internet_archive']
        self.assertEqual(len(ia), 37)
        for identifier in ia:
            self.assertIn((f'https://archive.org/details/{identifier}', 'image'), links)
        commons = [i for i, kind in links if i.startswith('https://commons.wikimedia.org/') and kind == 'image']
        self.assertEqual(len(commons), 1)
        self.assertEqual(len(links), 2 + len(R8B_NLI) + len(ia) + 1 + 1)
        self.assertTrue(all(r['relation_type'] == {'id': 'isderivedfrom'} for r in metadata['related_identifiers']))

    def test_r7_and_r8b_are_separate_releases(self):
        for models, state in ((['r8b', 'r7'], {}), (['r8b', 'r6'], {}), (['r8b', 'r3h'], {}),
                              (['r8b'], {'r7': {'id': 'rec7'}}), (['r7'], {'r8b': {'id': 'rec8'}}),
                              (list(zd.MODELS), {'r8b': {'id': 'rec8'}})):
            with self.subTest(models=models, state=list(state)):
                with self.assertRaisesRegex(zd.DepositError, 'release of its own.*own state file'):
                    zd.check_one_release(models, state)
        zd.check_one_release(['r8b'], {'r8b': {'id': 'rec8'}})
        zd.check_one_release(['r7'], {'r7': {'id': 'rec7'}})
        with outside_repository() as directory:
            state = directory / 'r7.json'
            zd.save_state(state, {'api': zd.SANDBOX, 'records': {'r7': {'id': 'rec7', 'doi': '10.5072/zenodo.700'}}})
            code, _, err = run_main(['--models', 'r8b', '--state', str(state), 'publish'],
                                    {'ZENODO_SANDBOX_TOKEN': TOKEN}, NoNetwork())
            self.assertEqual(code, 1)
            self.assertIn('own state file', err)

    def test_reserve_r8b_alone(self):
        _need_yaml(self)
        with outside_repository() as directory:
            fake = FakeZenodo()
            code, _, err = run_main(['--models', 'r8b', '--state', str(directory / 'r8b.json'), 'reserve'],
                                    {'ZENODO_SANDBOX_TOKEN': TOKEN}, fake)
            self.assertEqual(code, 0, err)
            self.assertEqual(fake.calls(), [('POST', '/records'), ('POST', '/records/rec1/draft/pids/doi')])
            sent = json.loads(fake.requests[0]['data'])['metadata']
            self.assertTrue(sent['title'].startswith('Hebrew printed-text recognition for Tesseract'))
            self.assertTrue(sent['title'].endswith('(HeOCR R8b)'))
            self.assertEqual(list(json.loads((directory / 'r8b.json').read_text())['records']), ['r8b'])

    def test_upload_r8b_sends_the_plain_card_and_its_four_files(self):
        _need_yaml(self)
        with r8b_release_copy() as (directory, release, weights):
            state = directory / 'state' / 'r8b.json'
            zd.save_state(state, {'api': zd.SANDBOX, 'records': {'r8b': {'id': 'rec8', 'doi': R8B_DOI}}})
            original = zd.validate_htrmopo
            zd.validate_htrmopo = lambda front: self.fail('R8b must not be HTRMoPo-validated')
            try:
                fake = FakeZenodo()
                code, _, err = run_main(['--models', 'r8b', '--release-dir', str(release), '--state', str(state),
                                         'upload', '--weights', f'r8b={weights}'], {'ZENODO_SANDBOX_TOKEN': TOKEN},
                                        fake)
            finally:
                zd.validate_htrmopo = original
        self.assertEqual(code, 0, err)
        self.assertEqual([k['key'] for k in json.loads(fake.requests[0]['data'])], R8B_FILES)
        readme = fake.requests[1]['data'].decode('utf-8')
        self.assertIn(f'id: {R8B_DOI}', readme)
        self.assertNotIn('ocr_models', readme.split('\n---\n', 1)[0])

    def test_publish_r8b_requests_heocr_only(self):
        _need_yaml(self)
        with outside_repository() as directory:
            state = directory / 'r8b.json'
            zd.save_state(state, {'api': zd.SANDBOX, 'records': {'r8b': {'id': 'rec8', 'doi': R8B_DOI}}})
            fake = FakeZenodo()
            code, _, err = run_main(['--models', 'r8b', '--state', str(state), 'publish'],
                                    {'ZENODO_SANDBOX_TOKEN': TOKEN}, fake)
        self.assertEqual(code, 0, err)
        self.assertEqual(fake.calls(), [('GET', '/communities/heocr'), ('GET', '/communities/heocr'),
                                        ('POST', '/records/rec8/draft/actions/publish'),
                                        ('POST', '/records/rec8/communities')])

    def test_plan_r8b_offline_and_the_draft_card_is_refused_once_a_doi_exists(self):
        _need_yaml(self)
        try:
            import markdown  # noqa: F401
        except ImportError:
            self.skipTest('Markdown is not installed')
        with outside_repository() as directory:
            # the repository's own card, before step 1: no DOI yet, so the DRAFT citation is fine
            code, out, err = run_main(['--models', 'r8b', '--state', str(directory / 'none.json'), 'plan'],
                                      {}, NoNetwork())
            self.assertEqual(code, 0, err)
            planned = json.loads(out)
            self.assertEqual(planned['release'], 'r8b')
            self.assertEqual(planned['card']['format'], 'plain (not HTRMoPo)')
            self.assertEqual(planned['communities'], ['heocr'])
            self.assertEqual(planned['files'][1], {'key': 'heocr_r8b.traineddata', 'weights': 'not given',
                                                   'sha256': R8B_SHA})
            self.assertEqual(len(planned['metadata']['related_identifiers']), 49)
            self.assertFalse((directory / 'none.json').exists())
            # after step 1 the card must cite the reserved DOI (step 2), and the draft card does not
            state = directory / 'r8b.json'
            zd.save_state(state, {'api': zd.SANDBOX, 'records': {'r8b': {'id': 'rec8', 'doi': R8B_DOI}}})
            code, _, err = run_main(['--models', 'r8b', '--state', str(state), 'plan'], {}, NoNetwork())
            self.assertEqual(code, 1)
            self.assertIn('step 2', err)
        with r8b_release_copy() as (directory, release, weights):
            code, out, err = run_main(['--models', 'r8b', '--release-dir', str(release), '--state',
                                       str(directory / 'none.json'), 'plan', '--weights', f'r8b={weights}'],
                                      {}, NoNetwork())
            self.assertEqual(code, 0, err)
            self.assertEqual([f['key'] for f in json.loads(out)['files']], R8B_FILES)


if __name__ == '__main__':
    unittest.main()
