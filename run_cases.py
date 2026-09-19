"""Acceptance runner. Produces the README's "Passed X/8" number from live calls.

Usage: ANTHROPIC_API_KEY=... python3 run_cases.py

Every call is live. There is no caching, no retry and no stored-response
fallback, so the number this prints is the number the provider actually earned.
Exit status is 0 only when all eight cases take the expected action and the
evidence gate leaked nothing.
"""
import sys

import fixtures
import model
from model import extract_order
from order_logic import validate

WIDTH = max(len(c["id"]) for c in fixtures.CASES)


def verdict(r):
    """Map a validation result onto the action the app would take.

    'blocks' is tested before 'asks': a case can be both incomplete and
    self-contradictory, and the contradiction is the stronger signal.
    """
    if r["ok"]:
        return "exports"
    if r["blocks"]:
        return "blocks"
    return "asks"


def invented(case, e):
    """Fields the case forbids inventing that came back with a value anyway."""
    leaks = []
    for name in case.get("must_not_invent") or []:
        got = (e["fields"].get(name) or {}).get("value")
        if got is not None:
            leaks.append((name, got))
    return leaks


def main():
    print(f"OrderReady acceptance run — model: {model.MODEL}")
    print("=" * 60)

    results, leaked = {}, []
    for case in fixtures.CASES:
        cid, expect = case["id"], case["expect"]
        try:
            e = extract_order(case["text"])
        except Exception as exc:                 # extract_order shouldn't raise
            print(f"ERROR {cid:<{WIDTH}}  expected {expect:<7}  "
                  f"{type(exc).__name__}: {exc}")
            continue
        if e["error"]:
            print(f"ERROR {cid:<{WIDTH}}  expected {expect:<7}  {e['error']}")
            continue

        r = validate(e)
        got = verdict(r)
        results[cid] = got
        status = "PASS" if got == expect else "FAIL"
        print(f"{status}  {cid:<{WIDTH}}  expected {expect:<7}  actual {got}")
        if status == "FAIL":
            print(f"        blocks   : {r['blocks']}")
            print(f"        missing  : {r['missing']}")
            print(f"        questions: {r['questions']}")

        for name, value in invented(case, e):
            leaked.append((cid, name, value))
            print(f"  !! INVENTED  {cid}: {name} = {value!r} "
                  f"(must_not_invent — the evidence gate leaked)")

    print("=" * 60)
    print(fixtures.score(results))

    if leaked:
        print(f"\n{len(leaked)} invented value(s) — the evidence gate leaked:")
        for cid, name, value in leaked:
            print(f"  {cid}: {name} = {value!r}")

    all_passed = all(results.get(c["id"]) == c["expect"] for c in fixtures.CASES)
    return 0 if all_passed and not leaked else 1


if __name__ == "__main__":
    sys.exit(main())
