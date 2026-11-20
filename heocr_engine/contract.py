"""Identifiers for the heocr_engine_prediction.v1 contract (docs/prediction_contract.md)."""

SCHEMA_ID = "heocr_engine_prediction.v1"
# Output of PR #1; read as v1 with track "open" and no pipeline.
LEGACY_SCHEMA_VERSIONS = frozenset({"1.0"})
TRACKS = ("open", "proprietary")
STAGE_KINDS = ("preprocess", "segment", "recognize", "postcorrect")
