"""Dev owns this file. Contract: extract_order(text) -> Extraction."""
import json, os, re, urllib.request, urllib.error

# ---- SWAP POINT: change these three lines for a different provider -------
API_URL = "https://api.anthropic.com/v1/messages"
HEADERS = {
    "content-type": "application/json",
    "x-api-key": os.environ.get("ANTHROPIC_API_KEY", ""),
    "anthropic-version": "2023-06-01",
}
MODEL = "claude-sonnet-5"
# -------------------------------------------------------------------------

FIELDS = ["customer_name", "contact", "sizes", "deadline", "stated_total"]

PROMPT = """You read a customer inquiry for a custom T-shirt shop and extract ONLY what is explicitly stated.

Return a single JSON object. No preamble, no markdown fences, no explanation.

Shape:
{
  "customer_name": {"value": <string|null>, "evidence": <exact substring|null>},
  "contact":       {"value": <string|null>, "evidence": <exact substring|null>},
  "sizes":         {"value": {"S": <int>, "M": <int>, "L": <int>}|null, "evidence": <exact substring|null>},
  "deadline":      {"value": <"YYYY-MM-DD"|null>, "evidence": <exact substring|null>},
  "stated_total":  {"value": <int|null>, "evidence": <exact substring|null>},
  "ambiguities":   [<short string>, ...]
}

HARD RULES:
- "evidence" must be an EXACT substring copied from the inquiry. Never paraphrase it.
- If a detail is not stated, value is null. Never estimate, complete, or infer.
- "mostly mediums", "a few larges", "some smalls" are NOT size counts. sizes.value = null.
- "about 40", "around 40", "~40", "40ish", "roughly 40" are NOT counts. stated_total.value = null.
- A date with no month or no year is NOT a deadline. deadline.value = null.
- If you set a value to null but the inquiry mentioned the topic, still fill "evidence"
  with the words that mentioned it, and add a line to "ambiguities".
- Never output prices, garment types, print locations, or any field not listed above.

Inquiry:
---
{inquiry}
---"""

VAGUE_QTY = re.compile(r"\b(about|around|roughly|approx\w*|~|\d+\s*ish)\b", re.I)


def _call(text, timeout=20):
    body = json.dumps({
        "model": MODEL,
        "max_tokens": 1000,
        "messages": [{"role": "user", "content": PROMPT.replace("{inquiry}", text)}],
    }).encode()
    req = urllib.request.Request(API_URL, data=body, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


def _parse(raw):
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?|\n?```$", "", raw)
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in response")
    return json.loads(raw[start:end + 1])


def _gate(fields, text):
    """THE EVIDENCE GATE. A value with no verbatim evidence in the source is dropped."""
    low = text.lower()
    dropped = []
    for name in FIELDS:
        f = fields.setdefault(name, {"value": None, "evidence": None})
        if not isinstance(f, dict):
            fields[name] = {"value": None, "evidence": None}
            continue
        ev = (f.get("evidence") or "").strip()
        if f.get("value") is not None and (not ev or ev.lower() not in low):
            f["value"] = None
            dropped.append(name)
    # belt and braces: the model sometimes accepts an approximate count anyway
    st = fields["stated_total"]
    if st.get("value") is not None and VAGUE_QTY.search(st.get("evidence") or ""):
        st["value"] = None
        dropped.append("stated_total")
    return dropped


def extract_order(text):
    """Returns {fields, ambiguities, dropped, error}. Never raises."""
    empty = {n: {"value": None, "evidence": None} for n in FIELDS}
    if not text or not text.strip():
        return {"fields": empty, "ambiguities": [], "dropped": [], "error": "empty input"}
    try:
        parsed = _parse(_call(text))
    except Exception as e:                      # timeout, auth, bad JSON, anything
        return {"fields": empty, "ambiguities": [], "dropped": [],
                "error": f"{type(e).__name__}: {e}"}
    fields = {n: parsed.get(n) or {"value": None, "evidence": None} for n in FIELDS}
    dropped = _gate(fields, text)
    ambig = [str(a) for a in (parsed.get("ambiguities") or [])][:6]
    return {"fields": fields, "ambiguities": ambig, "dropped": dropped, "error": None}
