"""Session-local proposal cache. Only original successful proposals belong here."""

from copy import deepcopy
import hashlib
import json
import time

CACHE_LIMIT = 5
CACHE_TTL = 15 * 60


def extraction_key(source, provider, model, settings, fingerprint):
    payload = [source, provider, model, settings, fingerprint]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def cache_get(cache, key, now=None):
    now = time.monotonic() if now is None else now
    for expired in [k for k, item in cache.items() if now - item['inserted'] >= CACHE_TTL]:
        del cache[expired]
    item = cache.get(key)
    return deepcopy(item['proposal']) if item else None


def cache_put(cache, key, proposal, now=None):
    if proposal.get('error'):
        return
    now = time.monotonic() if now is None else now
    cache_get(cache, key, now)
    cache.pop(key, None)
    cache[key] = {'inserted': now, 'proposal': deepcopy(proposal)}
    while len(cache) > CACHE_LIMIT:
        del cache[next(iter(cache))]
