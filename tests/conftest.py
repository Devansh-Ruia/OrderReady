"""Keep every test offline and prevent the adapter importing local credentials."""

import builtins
import importlib
import os
from pathlib import Path
import sys
from unittest.mock import Mock, patch

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
_real_open = builtins.open


def _without_credentials(file, *args, **kwargs):
    if isinstance(file, (str, bytes, os.PathLike)):
        path = Path(os.fsdecode(file))
        if path.name == ".env" or path.name.startswith(".env.") or "secrets" in path.parts:
            raise FileNotFoundError("Credentials are unavailable in offline tests")
    return _real_open(file, *args, **kwargs)


with patch("builtins.open", _without_credentials):
    model = importlib.import_module("model")


@pytest.fixture(autouse=True)
def no_live_requests(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("MODEL_ID", raising=False)
    monkeypatch.setattr(model, "HEADERS", {**model.HEADERS, "x-api-key": ""})
    monkeypatch.setattr(
        "urllib.request.urlopen",
        Mock(side_effect=AssertionError("Unexpected live HTTP request")),
    )
