"""Upload HeOCR's released models to Hugging Face Hub (release/README.md, plan step 7).

Each model gets its own public repository under the HeOCR organisation. Its `README.md` is the model's
`huggingface.yaml` front matter between `---` lines, followed by its `card_body.md`. Beside the card go the weights
under their release name, `LICENSE`, `NOTICE` and the training record, as in the Zenodo deposit.

- **Production DOIs only.** A real upload takes each model's DOI from the production Zenodo state file
  (`zenodo_deposit.py --production`), and refuses a card body that does not cite it.
- **Weights:** refused unless their sha256 matches the record's `model_sha256`.
- **Dry run:** `--dry-run` prints the planned repositories and files and makes no network call. It accepts a sandbox
  state file, so the plan can be checked before production exists.
- **Token:** `HF_TOKEN` is read from the environment only. It is passed to huggingface_hub directly, and never goes
  into an argument list or any output; it is redacted from errors.
- **Releases:** the default `--models` is the first release, R4d + A1 + R3h. R6 and R7 (Tesseract) are each a release
  of their own: `--models r6` or `--models r7`, each with its own Zenodo state file. One run never mixes two releases.
- **Dependencies:** huggingface_hub is imported only for a real upload.

No per-upload go-ahead is needed since decision 0014.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

RELEASE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("zenodo_deposit", RELEASE / "zenodo_deposit.py")
zenodo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(zenodo)
DepositError = zenodo.DepositError
MODELS = zenodo.MODELS
CHOICES = zenodo.CHOICES
# One public repository per model under the HeOCR organisation (item 7; decision 0011's note; R6, R7: decision 0014).
HF_REPOS = {"r4d": "HeOCR/heocr-r4d-segmentation", "a1": "HeOCR/heocr-a1-reading-order",
            "r3h": "HeOCR/heocr-r3h-recognition", "r6": "HeOCR/heocr-r6-tesseract-heb",
            "r7": "HeOCR/heocr-r7-tesseract-heb"}


def read_token(environ=os.environ) -> str:
    value = environ.get("HF_TOKEN", "").strip()
    if not value:
        raise DepositError("Set HF_TOKEN in the environment (see release/README.md, 'Before step 1')")
    return value


def dois(state_path: Path, *, dry_run: bool, models=MODELS) -> dict[str, str]:
    """Each model's DOI from a Zenodo state file: production only, unless this is a dry run."""
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("api") != zenodo.PRODUCTION and not dry_run:
        raise DepositError(f"The state file is for {state.get('api')}; a real upload needs the production DOIs")
    records = state.get("records", {})
    zenodo.check_one_release(models, records)
    missing = [model for model in models if not records.get(model, {}).get("doi")]
    if missing:
        raise DepositError(f"No DOI in the state file for {', '.join(missing)}")
    return {model: records[model]["doi"] for model in models}


def build_card(model: str, doi: str, release: Path = RELEASE) -> str:
    """README.md: the Hugging Face front matter (without its comment lines), then the card body citing `doi`."""
    body = (release / model / "card_body.md").read_text(encoding="utf-8")
    if doi not in body:
        raise DepositError(f"{model}: the card body does not cite {doi}; put the DOIs in the cards first (step 2)")
    front = [line for line in (release / model / "huggingface.yaml").read_text(encoding="utf-8").splitlines()
             if line.strip() and not line.lstrip().startswith("#")]
    return "---\n" + "\n".join(front) + "\n---\n" + body


def plan(model: str, weights: Path, doi: str, release: Path = RELEASE) -> dict:
    """The repository and the files for one model, after the DOI and sha256 checks."""
    card = build_card(model, doi, release)
    files = zenodo.deposit_files(model, weights, release)
    return {"repo_id": HF_REPOS[model], "card": card, "files": files}


def describe(model: str, planned: dict) -> dict:
    entries = [{"path": "README.md", "bytes": len(planned["card"].encode("utf-8"))}]
    for name, path in planned["files"].items():
        data = path.read_bytes()
        entries.append({"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    return {"model": model, "repo_id": planned["repo_id"], "public": True, "files": entries}


def upload(api, planned: dict, model: str, add=None) -> None:
    """Create the public repository if needed, then add the card and the four files in one commit."""
    if add is None:
        from huggingface_hub import CommitOperationAdd as add  # noqa: PLC0415, N813  (only for a real upload)
    api.create_repo(planned["repo_id"], repo_type="model", private=False, exist_ok=True)
    operations = [add(path_in_repo="README.md", path_or_fileobj=planned["card"].encode("utf-8"))]
    operations += [add(path_in_repo=name, path_or_fileobj=str(path)) for name, path in planned["files"].items()]
    api.create_commit(planned["repo_id"], operations, repo_type="model",
                      commit_message=f"Release {model}: card, weights, LICENSE, NOTICE and training record")


def _weights(values: list[str]) -> dict[str, Path]:
    weights = {}
    for value in values:
        model, sep, path = value.partition("=")
        if not sep or model not in CHOICES:
            raise DepositError(f"--weights takes MODEL=PATH with MODEL in {', '.join(CHOICES)}")
        weights[model] = Path(path)
    return weights


def main(argv=None, environ=os.environ, api_factory=None, add=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--zenodo-state", type=Path, required=True,
                        help="the Zenodo state file with the reserved DOIs (production for a real upload)")
    parser.add_argument("--weights", nargs="+", required=True, metavar="MODEL=PATH")
    parser.add_argument("--models", nargs="+", choices=CHOICES, default=list(MODELS),
                        help="default: the first release, r4d a1 r3h. r6 and r7 are each a release of their own: "
                             "give one alone")
    parser.add_argument("--release-dir", type=Path, default=RELEASE, help="dry run only: a copy of release/")
    parser.add_argument("--dry-run", action="store_true", help="print the plan; no network")
    args = parser.parse_args(argv)
    token = None
    try:
        release = args.release_dir.resolve()
        if release != RELEASE and not args.dry_run:
            raise DepositError("--release-dir is for dry runs only; an upload uses the repository's release/")
        found, weights = dois(args.zenodo_state, dry_run=args.dry_run, models=args.models), _weights(args.weights)
        missing = [model for model in args.models if model not in weights]
        if missing:
            raise DepositError(f"--weights has no path for {', '.join(missing)}")
        planned = {model: plan(model, weights[model], found[model], release) for model in args.models}
        if args.dry_run:
            for model in args.models:
                print(json.dumps(describe(model, planned[model])))
            return 0
        token = read_token(environ)
        if api_factory is None:
            from huggingface_hub import HfApi  # noqa: PLC0415
            api_factory = HfApi
        api = api_factory(token=token)
        for model in args.models:
            upload(api, planned[model], model, add)
            print(json.dumps({"model": model, "repo_id": planned[model]["repo_id"], "uploaded": True}))
        return 0
    except DepositError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except Exception as error:  # huggingface_hub errors: report without the token
        message = f"{type(error).__name__}: {error}"
        print("error: " + (message.replace(token, "<token>") if token else message), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
