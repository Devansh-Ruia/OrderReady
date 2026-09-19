"""Devansh owns this file. No model calls in here. Pure functions only."""
from datetime import date, datetime, timedelta

GARMENT = "Heavyweight cotton tee"
PRINT_LOCATION = "Front centre"
LEAD_DAYS = 7
SIZES = ("S", "M", "L")
REQUIRED = ("customer_name", "contact", "sizes", "deadline")
LABEL = {"customer_name": "customer name", "contact": "email or phone",
         "sizes": "size breakdown (S/M/L)", "deadline": "deadline"}


def _merge(extraction, overrides):
    """Founder-typed overrides beat anything the model produced."""
    out = {}
    for name, f in extraction["fields"].items():
        out[name] = {"value": f.get("value"), "evidence": f.get("evidence"),
                     "source": "extracted" if f.get("value") is not None else None}
    for name, val in (overrides or {}).items():
        if val not in (None, "", {}):
            out.setdefault(name, {})
            out[name] = {"value": val, "evidence": None, "source": "founder"}
    return out


def _check_sizes(v):
    if not isinstance(v, dict):
        return None, "size breakdown is not a valid S/M/L set"
    try:
        counts = {s: int(v.get(s, 0)) for s in SIZES}
    except (TypeError, ValueError):
        return None, "size counts must be whole numbers"
    if any(c < 0 for c in counts.values()):
        return None, "size counts cannot be negative"
    if sum(counts.values()) == 0:
        return None, "size breakdown totals zero"
    return counts, None


def _check_deadline(v, today=None):
    today = today or date.today()
    try:
        d = datetime.strptime(str(v), "%Y-%m-%d").date()
    except ValueError:
        return None, "deadline is not a real date (YYYY-MM-DD)"
    earliest = today + timedelta(days=LEAD_DAYS)
    if d < earliest:
        return None, (f"deadline {d.isoformat()} is inside the {LEAD_DAYS}-day "
                      f"lead time — earliest is {earliest.isoformat()}")
    return d, None


def validate(extraction, overrides=None, today=None):
    """Returns {ok, fields, missing, blocks, questions, total}."""
    fields = _merge(extraction, overrides)
    missing, blocks = [], []
    questions = list(extraction.get("ambiguities") or [])

    counts = None
    if fields["sizes"]["value"] is not None:
        counts, err = _check_sizes(fields["sizes"]["value"])
        if err:
            blocks.append(err)
            fields["sizes"]["value"] = None

    if fields["deadline"]["value"] is not None:
        parsed, err = _check_deadline(fields["deadline"]["value"], today)
        if err:
            blocks.append(err)
            fields["deadline"]["value"] = None

    for name in REQUIRED:
        if fields[name]["value"] is None:
            missing.append(LABEL[name])

    total = sum(counts.values()) if counts else None
    stated = fields.get("stated_total", {}).get("value")
    if total is not None and stated is not None and int(stated) != total:
        blocks.append(f"customer said {stated} shirts, sizes add up to {total}")

    # turn each dropped field into a question rather than a silent gap
    for name in extraction.get("dropped") or []:
        ev = (extraction["fields"].get(name) or {}).get("evidence")
        if ev:
            questions.append(f'"{ev}" is not specific enough for {LABEL.get(name, name)}')

    ok = not missing and not blocks
    return {"ok": ok, "fields": fields, "missing": missing,
            "blocks": blocks, "questions": questions, "total": total}


def render_ticket(result, source_text=None):
    """source_text is the verbatim inquiry. Optional so older callers still work."""
    if not result["ok"]:
        raise ValueError("render_ticket called on an invalid result")
    f, counts = result["fields"], result["fields"]["sizes"]["value"]
    lines = [
        "INTAKE TICKET",
        "=" * 34,
        f"Customer : {f['customer_name']['value']}",
        f"Contact  : {f['contact']['value']}",
        f"Garment  : {GARMENT}",
        f"Print    : {PRINT_LOCATION}",
        f"Deadline : {f['deadline']['value']}",
        "",
        "Sizes",
    ]
    lines += [f"  {s} x {counts[s]}" for s in SIZES]
    lines += ["", f"TOTAL    : {result['total']} shirts", ""]
    # Export only fires after the founder ticks the review box, so this is a
    # record of what already happened, not a claim we cannot back up.
    lines += ["Reviewed by founder: yes", ""]
    lines += ["Original inquiry:", source_text if source_text else "(not recorded)", ""]
    lines += ["Intake only — no pricing or artwork review."]
    return "\n".join(lines)


def ticket_json(result, source_text=None):
    f, counts = result["fields"], result["fields"]["sizes"]["value"]
    return {"customer_name": f["customer_name"]["value"],
            "contact": f["contact"]["value"],
            "garment": GARMENT, "print_location": PRINT_LOCATION,
            "deadline": f["deadline"]["value"],
            "sizes": counts, "total_quantity": result["total"],
            "reviewed_by_founder": True,
            "original_inquiry": source_text}
