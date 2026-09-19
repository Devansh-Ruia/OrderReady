"""Read optional teammate-owned samples without consuming expected outputs."""

import json
from pathlib import Path


SAMPLES_PATH = Path(__file__).resolve().parents[1] / "samples.json"


def load_samples() -> tuple[list[dict[str, str]], str | None]:
    try:
        records = json.loads(SAMPLES_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [], None
    except (OSError, UnicodeError, ValueError, RecursionError):
        return [], "Optional samples could not be loaded. Paste an inquiry to continue."
    if not isinstance(records, list):
        return [], "Optional samples must be a JSON array. Paste an inquiry to continue."
    samples = []
    malformed = False
    for record in records:
        if (
            isinstance(record, dict)
            and isinstance(record.get("label"), str)
            and record["label"].strip()
            and isinstance(record.get("input"), str)
            and record["input"].strip()
        ):
            samples.append({"label": record["label"], "input": record["input"]})
        else:
            malformed = True
    warning = "Some optional samples were malformed and skipped." if malformed else None
    return samples, warning
