"""Deposit the first release's three models on Zenodo, one plan step at a time (release/README.md, item 8).

Each subcommand is one step of the plan and needs its own go-ahead from the maintainer:

  reserve   step 1: create the three drafts and reserve their DOIs; writes the state file
  upload    step 3: upload each card (as README.md) and its four files into its draft
  metadata  step 4: set each draft's metadata from its front matter and card body
  publish   step 6: publish each draft, then request inclusion in its communities
  status    print the drafts and DOIs in the state file (no network)
  requests  list each record's requests, e.g. community inclusion, with their status (read-only)
  accept    accept pending inclusion requests to the maintainer's own communities (heocr) only

Step 2 (putting the reserved DOIs into the cards, by PR) and step 5 (checking the previews) are done by hand.

- **Target:** the Zenodo sandbox, unless `--production` is given.
- **Tokens:** read only from the environment (`ZENODO_SANDBOX_TOKEN`, or `ZENODO_TOKEN` with `--production`). A token
  is sent only in an `Authorization: Bearer` header. It never goes into a URL, an argument list, the state file or
  any output, and it is redacted from error messages.
- **The state file:** it holds only draft ids and DOIs, and it must live outside the repository.
- **API:** Zenodo's InvenioRDM records API, because the legacy deposit API that htrmopo uses cannot reserve a DOI for
  an existing draft or mark an organisational creator. The community-inclusion call is to be confirmed on the
  sandbox before production.
- **Dependencies:** the core is the standard library only. Reading the cards needs PyYAML, rendering the description
  needs Markdown, and validating against HTRMoPo v1 needs htrmopo. They are imported only when used.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request

RELEASE = Path(__file__).resolve().parent
ROOT = RELEASE.parent
SANDBOX = "https://sandbox.zenodo.org/api"
PRODUCTION = "https://zenodo.org/api"
TOKEN_VARIABLES = {SANDBOX: "ZENODO_SANDBOX_TOKEN", PRODUCTION: "ZENODO_TOKEN"}
# Communities the maintainer owns on each target, by slug and id. `accept` acts only on requests to these; requests
# to any other community (ocr_models) are left to that community's moderators.
OWNED_COMMUNITIES = {SANDBOX: {"heocr": "c261ed63-f520-48a3-90c2-c64ed1cc0395"},
                     PRODUCTION: {"heocr": "febfcbcf-2444-4a84-8699-04cd1c44c8a7"}}
# Deposit order: the pipeline order of the cards' tables.
MODELS = ("r4d", "a1", "r3h")
# htrmopo 0.5 files models as legacy `upload_type: publication`, `publication_type: other`.
RESOURCE_TYPE = {"id": "publication-other"}
# DOI registration needs a publisher (sandbox, 2026-11-06: "Missing publisher field required for DOI registration");
# the legacy deposit API that htrmopo uses sets "Zenodo" itself.
PUBLISHER = "Zenodo"
MAX_RESPONSE_BYTES = 10_000_000
# Zenodo answers `application/json` on /api/records with its legacy serialization (no `pids`, the DOI at the top
# level); InvenioRDM's own JSON needs its media type (found on the sandbox, 2026-11-06).
RDM_JSON = "application/vnd.inveniordm.v1+json"


class DepositError(Exception):
    """A step cannot go ahead; the message never contains a token."""


def read_token(base: str, environ=os.environ) -> str:
    name = TOKEN_VARIABLES[base]
    value = environ.get(name, "")
    if not value.strip():
        raise DepositError(f"Set {name} in the environment (see release/README.md, 'Before step 1')")
    return value.strip()


class Api:
    """InvenioRDM records API with a Bearer token. `opener` is urllib's by default; tests pass a fake."""

    def __init__(self, base: str, token: str, opener=None):
        self.base, self._token = base.rstrip("/"), token
        self._open = opener or urllib.request.urlopen

    def _redact(self, text: str) -> str:
        return text.replace(self._token, "<token>") if self._token else text

    def request(self, method: str, path: str, body=None, *, data: bytes | None = None,
                content_type: str = "application/json"):
        if body is not None:
            data = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(f"{self.base}{path}", data=data, method=method)
        request.add_header("Authorization", f"Bearer {self._token}")
        request.add_header("Accept", RDM_JSON)
        if data is not None:
            request.add_header("Content-Type", content_type)
        try:
            with self._open(request, timeout=300) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as error:
            detail = error.read(2000).decode("utf-8", "replace")
            raise DepositError(self._redact(f"{method} {path}: HTTP {error.code}: {detail}")) from None
        except urllib.error.URLError as error:
            raise DepositError(self._redact(f"{method} {path}: {error.reason}")) from None
        if len(raw) > MAX_RESPONSE_BYTES:
            raise DepositError(f"{method} {path}: response too large")
        return json.loads(raw) if raw.strip() else None


def creators(authors: list[dict]) -> list[dict]:
    """HTRMoPo `authors` (with the extra `type` key) to InvenioRDM creators (release/README.md)."""
    result = []
    for author in authors:
        kind = author.get("type")
        if kind == "personal":
            family, sep, given = author["name"].partition(",")
            if not sep or not family.strip() or not given.strip():
                raise DepositError(f"Person name must be 'Family, Given': {author['name']!r}")
            person = {"type": "personal", "family_name": family.strip(), "given_name": given.strip()}
            if author.get("orcid"):
                person["identifiers"] = [{"scheme": "orcid",
                                          "identifier": author["orcid"].rstrip("/").rsplit("/", 1)[-1]}]
            result.append({"person_or_org": person})
        elif kind == "organizational":
            result.append({"person_or_org": {"type": "organizational", "name": author["name"]}})
        else:
            raise DepositError(f"Author {author.get('name')!r} needs type personal or organizational")
    return result


def record_metadata(front: dict, description_html: str, publication_date: str) -> dict:
    """InvenioRDM metadata following htrmopo 0.5's mapping: title, description, creators, licence, keywords, data."""
    metadata = {"resource_type": RESOURCE_TYPE, "title": front["summary"], "publication_date": publication_date,
                "publisher": PUBLISHER,
                "creators": creators(front["authors"]), "description": description_html,
                # SPDX ids, lower case in InvenioRDM's licence vocabulary
                "rights": [{"id": front["license"].lower()}]}
    if front.get("tags"):
        metadata["subjects"] = [{"subject": tag} for tag in front["tags"]]
    if front.get("datasets"):
        metadata["related_identifiers"] = [{"identifier": url, "scheme": "url",
                                            "relation_type": {"id": "isderivedfrom"},
                                            "resource_type": {"id": "dataset"}} for url in front["datasets"]]
    return metadata


def _inside_repository(path: Path) -> bool:
    try:
        path.resolve().relative_to(ROOT)
        return True
    except ValueError:
        return False


def load_state(path: Path, base: str) -> dict:
    if _inside_repository(path):
        raise DepositError("The state file must be outside the repository")
    if not path.exists():
        return {"api": base, "records": {}}
    state = json.loads(path.read_text(encoding="utf-8"))
    if state.get("api") != base:
        raise DepositError(f"The state file is for {state.get('api')}, not {base}")
    return state


def save_state(path: Path, state: dict) -> None:
    if _inside_repository(path):
        raise DepositError("The state file must be outside the repository")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)


def _draft(state: dict, model: str) -> dict:
    record = state["records"].get(model)
    if not record or not record.get("doi"):
        raise DepositError(f"No reserved draft for {model}; run `reserve` first (plan step 1)")
    return record


def reserve(api: Api, state: dict, fronts: dict, state_path: Path, today: str) -> dict:
    """Step 1: one draft per model, each with its DOI reserved.

    Crash-safe and resumable: a new draft's id is saved before its DOI is reserved, so a draft is never lost, and
    a rerun reserves the DOI of a saved draft that has none and skips models that are done.
    """
    for model in MODELS:
        record = state["records"].get(model)
        if record and record.get("doi"):
            continue
        if not record:
            front = fronts[model]
            draft = api.request("POST", "/records", {
                "metadata": {"resource_type": RESOURCE_TYPE, "title": front["summary"],
                             "publication_date": today, "creators": creators(front["authors"])},
                "files": {"enabled": True}, "access": {"record": "public", "files": "public"}})
            record = state["records"][model] = {"id": draft["id"]}
            save_state(state_path, state)
        reserved = api.request("POST", f"/records/{record['id']}/draft/pids/doi")
        doi = ((reserved or {}).get("pids") or {}).get("doi", {}).get("identifier")
        if not doi:
            raise DepositError(f"{model}: no pids.doi.identifier in the DOI reservation response "
                               f"(keys: {sorted(reserved or {})}); draft {record['id']} is saved without a DOI")
        record["doi"] = doi
        save_state(state_path, state)
    return state


def build_card(front: dict, body: str, doi: str, validate=None) -> str:
    """The deposit's README.md: front matter with `id`, then the card body, which must cite its DOI (step 2)."""
    if doi not in body:
        raise DepositError(f"The card body does not cite {doi}; put the reserved DOIs in the cards first (step 2)")
    front = {**front, "id": doi}
    (validate or validate_htrmopo)(front)
    import yaml  # noqa: PLC0415  (only needed for a real deposit)
    return "---\n" + yaml.safe_dump(front, sort_keys=False, allow_unicode=True) + "---\n" + body


def validate_htrmopo(front: dict) -> None:
    from jsonschema import validate  # noqa: PLC0415
    from htrmopo.util import _v1_schema  # noqa: PLC0415
    from htrmopo.publish import format_checker  # noqa: PLC0415
    validate(front, _v1_schema, format_checker=format_checker)


def deposit_files(model: str, weights: Path, release: Path = RELEASE) -> dict[str, Path]:
    """The four files beside the card, under their deposit names; the weights must match the record's sha256."""
    record_path = release / model / f"{model}_training_run.json"
    output = json.loads(record_path.read_text(encoding="utf-8"))["output"]
    digest = hashlib.sha256()
    with weights.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    if digest.hexdigest() != output["model_sha256"]:
        raise DepositError(f"{model}: {weights.name} does not match the record's model_sha256")
    return {output["release_file_name"]: weights, "LICENSE": release / model / "LICENSE",
            "NOTICE": release / model / "NOTICE", record_path.name: record_path}


def upload(api: Api, state: dict, model: str, card: str, files: dict[str, Path]) -> None:
    """Step 3: start, upload and commit the card (README.md) and each file into the model's draft."""
    record_id = _draft(state, model)["id"]
    contents = {"README.md": card.encode("utf-8"), **{name: path.read_bytes() for name, path in files.items()}}
    api.request("POST", f"/records/{record_id}/draft/files", [{"key": name} for name in contents])
    for name, data in contents.items():
        api.request("PUT", f"/records/{record_id}/draft/files/{name}/content", data=data,
                    content_type="application/octet-stream")
        api.request("POST", f"/records/{record_id}/draft/files/{name}/commit")


def set_metadata(api: Api, state: dict, model: str, metadata: dict) -> None:
    """Step 4: replace the draft's metadata, keeping its reserved DOI."""
    record_id = _draft(state, model)["id"]
    draft = api.request("GET", f"/records/{record_id}/draft")
    if draft.get("pids", {}).get("doi", {}).get("identifier") != state["records"][model]["doi"]:
        raise DepositError(f"{model}: the draft's DOI is not the reserved one")
    api.request("PUT", f"/records/{record_id}/draft", {
        "metadata": metadata, "pids": draft["pids"], "files": {"enabled": True},
        "access": {"record": "public", "files": "public"}})


def community_ids(api: Api, slugs: list[str]) -> list[str]:
    """Each community slug's id; a missing community fails here, before anything is published."""
    ids = []
    for slug in slugs:
        try:
            ids.append(api.request("GET", f"/communities/{slug}")["id"])
        except DepositError as error:
            raise DepositError(f"Community {slug!r} not found on {api.base}; nothing was published ({error})") from None
    return ids


def publish(api: Api, state: dict, model: str, communities: list[str]) -> None:
    """Step 6: resolve the communities, publish (permanent), then request inclusion in each community."""
    record_id = _draft(state, model)["id"]
    ids = community_ids(api, communities)
    published = api.request("POST", f"/records/{record_id}/draft/actions/publish")
    state["records"][model]["published"] = bool(published)
    if ids:
        # InvenioRDM inclusion requests for a published record; to be confirmed on the sandbox.
        api.request("POST", f"/records/{record_id}/communities", {"communities": [{"id": i} for i in ids]})


def accept_owned(api: Api, state: dict, model: str, owned: dict[str, str]) -> list[dict]:
    """Accept the record's submitted inclusion requests to owned communities; leave every other request alone.

    Each request is read again just before it is accepted, and accepted only if its receiver is still an owned
    community and it is still a submitted community-inclusion request.
    """
    owned_ids = {community_id: slug for slug, community_id in owned.items()}
    record_id = _draft(state, model)["id"]
    listing = api.request("GET", f"/records/{record_id}/requests")
    done = []
    for item in (listing or {}).get("hits", {}).get("hits", []):
        receiver = (item.get("receiver") or {}).get("community")
        line = {"model": model, "request": item.get("id"), "community": owned_ids.get(receiver, receiver)}
        if item.get("type") != "community-inclusion" or receiver not in owned_ids:
            done.append({**line, "action": "left for its moderators", "status": item.get("status")})
            continue
        current = api.request("GET", f"/requests/{item['id']}")
        if ((current.get("receiver") or {}).get("community") != receiver
                or current.get("type") != "community-inclusion" or current.get("status") != "submitted"):
            done.append({**line, "action": "skipped", "status": current.get("status")})
            continue
        accepted = api.request("POST", f"/requests/{item['id']}/actions/accept", {})
        done.append({**line, "action": "accepted", "status": (accepted or {}).get("status")})
    return done


def read_front(model: str, release: Path = RELEASE) -> dict:
    import yaml  # noqa: PLC0415
    return yaml.safe_load((release / model / "zenodo.yaml").read_text(encoding="utf-8"))


def description_html(body: str) -> str:
    import markdown  # noqa: PLC0415
    return markdown.markdown(body, extensions=["tables", "fenced_code"])


def _weights(values: list[str]) -> dict[str, Path]:
    weights = {}
    for value in values:
        model, sep, path = value.partition("=")
        if not sep or model not in MODELS:
            raise DepositError(f"--weights takes MODEL=PATH with MODEL in {', '.join(MODELS)}")
        weights[model] = Path(path)
    return weights


def main(argv=None, environ=os.environ, opener=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--production", action="store_true", help="zenodo.org instead of the sandbox (default)")
    parser.add_argument("--state", type=Path, required=True, help="state file outside the repository")
    parser.add_argument("--models", nargs="+", choices=MODELS, default=list(MODELS))
    parser.add_argument("--release-dir", type=Path, default=RELEASE,
                        help="folder with r4d/, a1/, r3h/ (default: this repository's release/). Sandbox only: a "
                             "production deposit uses the approved, pinned files in the repository")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("reserve")
    upload_parser = commands.add_parser("upload")
    upload_parser.add_argument("--weights", nargs="+", required=True, metavar="MODEL=PATH")
    commands.add_parser("metadata")
    commands.add_parser("publish")
    commands.add_parser("status")
    commands.add_parser("requests")
    commands.add_parser("accept")
    args = parser.parse_args(argv)
    base = PRODUCTION if args.production else SANDBOX
    release = args.release_dir.resolve()
    try:
        if args.production and release != RELEASE:
            raise DepositError("--release-dir is for the sandbox only; production uses the repository's release/")
        state = load_state(args.state, base)
        if args.command == "status":
            print(json.dumps(state, indent=2))
            return 0
        api = Api(base, read_token(base, environ), opener)
        print(f"target: {base}", file=sys.stderr)
        if args.command == "requests":
            for model in args.models:
                listing = api.request("GET", f"/records/{_draft(state, model)['id']}/requests")
                for item in (listing or {}).get("hits", {}).get("hits", []):
                    print(json.dumps({"model": model, "type": item.get("type"), "status": item.get("status"),
                                      "receiver": item.get("receiver"), "id": item.get("id")}))
            return 0
        if args.command == "accept":
            for model in args.models:
                for line in accept_owned(api, state, model, OWNED_COMMUNITIES[base]):
                    print(json.dumps(line))
            return 0
        fronts = {model: read_front(model, release) for model in MODELS}
        if args.command == "reserve":
            reserve(api, state, fronts, args.state, datetime.date.today().isoformat())
        if args.command == "publish":
            for model in args.models:
                _draft(state, model)
                community_ids(api, fronts[model].get("communities", []))
        for model in args.models if args.command != "reserve" else ():
            body = (release / model / "card_body.md").read_text(encoding="utf-8")
            doi = _draft(state, model)["doi"]
            if args.command == "upload":
                weights = _weights(args.weights)
                if model not in weights:
                    raise DepositError(f"--weights has no path for {model}")
                upload(api, state, model, build_card(fronts[model], body, doi), deposit_files(model, weights[model], release))
            elif args.command == "metadata":
                build_card(fronts[model], body, doi)
                set_metadata(api, state, model, record_metadata(fronts[model], description_html(body),
                                                                datetime.date.today().isoformat()))
            elif args.command == "publish":
                publish(api, state, model, fronts[model].get("communities", []))
                save_state(args.state, state)
        print(json.dumps({m: {"id": r["id"], "doi": r.get("doi")} for m, r in state["records"].items()}, indent=2))
        return 0
    except DepositError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
