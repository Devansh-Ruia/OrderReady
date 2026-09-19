"""Isolated browser harness. Model extraction is mocked and HTTP is blocked."""
import builtins
from copy import deepcopy
import json
import os
from pathlib import Path
import runpy
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
_real_open = builtins.open


def without_credentials(file, *args, **kwargs):
    if isinstance(file, (str, bytes, os.PathLike)):
        path = Path(os.fsdecode(file))
        if path.name == '.env' or path.name.startswith('.env.') or path.name == 'secrets.toml' or 'secrets' in path.parts:
            raise FileNotFoundError('Credentials unavailable in offline browser checks')
    return _real_open(file, *args, **kwargs)


with patch('builtins.open', without_credentials):
    import model

os.environ['ANTHROPIC_API_KEY'] = 'offline-placeholder'
model.HEADERS = {**model.HEADERS, 'x-api-key': ''}
MOCK_SOURCE = 'Jordan Rivera, jordan@example.com. We need 30 shirts. S 10, M 10, L 5. Needed September 28'
MOCK_PROPOSAL = {
    'fields': {
        'customer_name': {'value': 'Jordan Rivera', 'evidence': 'Jordan Rivera'},
        'contact': {'value': 'jordan@example.com', 'evidence': 'jordan@example.com'},
        'sizes': {'value': {'S': 10, 'M': 10, 'L': 5}, 'evidence': 'S 10, M 10, L 5'},
        'deadline': {'value': None, 'evidence': 'Needed September 28'},
        'stated_total': {'value': 30, 'evidence': 'We need 30 shirts'},
    },
    'ambiguities': ['Confirm whether 30 shirts or the size sum of 25 is correct.', 'Which year is the deadline?', 'Confirm the artwork with the customer.'],
    'dropped': ['deadline'], 'error': None,
}


def mocked_extract(source):
    assert source == MOCK_SOURCE, 'Only the declared synthetic inquiry is supported'
    with (ROOT / 'artifacts' / 'repair-mock-calls.jsonl').open('a') as out:
        out.write(json.dumps({'mocked': True, 'source': source}) + '\n')
    return deepcopy(MOCK_PROPOSAL)


def block_http(*args, **kwargs):
    raise AssertionError('Live HTTP is disabled in browser verification')


model.extract_order = mocked_extract
baseline = Path.cwd().resolve() == ROOT / 'artifacts' / 'repair-baseline'
app = ROOT / 'artifacts' / 'repair-baseline' / 'app.py.before' if baseline else ROOT / 'app.py'
with patch('urllib.request.urlopen', block_http):
    runpy.run_path(str(app), run_name='__main__')
