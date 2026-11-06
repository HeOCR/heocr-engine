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


if __name__ == '__main__':
    unittest.main()
