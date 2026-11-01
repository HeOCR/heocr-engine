"""A minimal heocr_engine_stage.v1 subprocess stage used by the offline tests."""
import json
import sys

request = json.load(sys.stdin)
assert request["protocol"] == "heocr_engine_stage.v1"
mode = request["config"].get("mode")
if request["kind"] == "preprocess":
    response = {"image_base64": request["page"]["image_base64"]}
elif request["kind"] == "recognize":
    response = {"text": "שלום עולם\n", "words": [{"text": "שלום", "confidence": None,
                                                 "bbox": [1, 1, 4, 3], "geometry_status": "valid"}],
                "details": {"mode": mode}}
else:
    response = {"text": request["text"].replace("עולם", "עולם!"), "words": request["words"]}
if mode == "bad-json":
    sys.stdout.write("not json")
elif mode == "crash-after-output":
    # Write a valid response, then exit non-zero, as Kraken 7.0.2 sometimes does on macOS.
    json.dump(response, sys.stdout, ensure_ascii=False)
    sys.stdout.flush()
    sys.exit(134)
else:
    json.dump(response, sys.stdout, ensure_ascii=False)
