"""Dev owns this. Eight cases. A case passes only if the app takes the expected action.
All customers and details are fictional. Deadlines assume 'today' is 2026-09-19."""

CASES = [
    # --- 4 that must extract cleanly ------------------------------------
    # this is the NORMAL case shown in the README demo — keep verbatim
    {"id": "demo-normal", "expect": "exports",
     "text": """Thirty shirts. Ten small, ten medium, ten large.
Needed 2026-10-28. - Priya, priya@example.com"""},

    {"id": "clean-prose", "expect": "exports",
     "text": """Hello! This is Marcus Webb. Looking for ten smalls, twenty mediums
and five larges for our cafe staff, 35 shirts altogether. Deadline is 2026-10-15.
My email is m.webb@example.com."""},

    {"id": "clean-phone-contact", "expect": "exports",
     "text": """Dana Okafor here — 617-555-0148. Need 12 shirts for a fundraiser:
4 small, 6 medium, 2 large. Must have them by 2026-11-02."""},

    {"id": "clean-no-stated-total", "expect": "exports",
     "text": """Hi, it's Sam Ellery, sam.ellery@example.com. Sizes: S 3, M 8, L 4.
Need them 2026-10-30 please."""},

    # --- 2 that must ASK, never guess -----------------------------------
    {"id": "vague-everything", "expect": "asks",
     "must_not_invent": ["sizes", "stated_total", "deadline"],
     "text": """hey! priya here, priya@example.com — we need about 40 shirts for
the team, mostly mediums, by the 15th. can you do it?"""},

    {"id": "two-numbers", "expect": "asks",
     "must_not_invent": ["sizes"],
     "text": """Jo Mensah here, jo.mensah@example.com. We're a group of 18 people
and we want 30 shirts so some folks get two. Need by 2026-10-20."""},

    # --- 2 that must BLOCK export ---------------------------------------
    # this is the CONTRADICTION case shown in the README demo — keep verbatim.
    # Trips three rules at once: total mismatch, yearless date, no contact.
    {"id": "demo-contradiction", "expect": "blocks",
     "reason": "stated 30, sizes sum to 25; 'September 28' has no year; no contact given",
     "must_not_invent": ["deadline", "sizes"],
     "text": """Thirty shirts. Ten small, ten medium, five large. Needed September 28."""},

    {"id": "deadline-too-soon", "expect": "blocks",
     "reason": "inside the 7-day lead time",
     "text": """Tom Reilly, t.reilly@example.com — 20 shirts, 5 S, 10 M, 5 L.
I need these by 2026-09-22, is that possible?"""},
]


def score(results):
    """results: {case_id: 'exports'|'asks'|'blocks'}  ->  'Passed X/8'"""
    passed = sum(1 for c in CASES if results.get(c["id"]) == c["expect"])
    return f"Passed {passed}/{len(CASES)} synthetic workflow cases"
