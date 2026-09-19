"""Run with: python -m streamlit run app.py.

Wired to the tested implementation: model.extract_order (evidence gate) and
order_logic.validate (deterministic rules). The orderready/ package is left
in place as a fallback but is no longer imported.
"""

import os
import re

import streamlit as st

import fixtures
from model import FIELDS, extract_order
from order_logic import GARMENT, LABEL, PRINT_LOCATION, SIZES, render_ticket, ticket_json, validate


SERVICE = f"Custom T-shirt printing: {GARMENT.lower()}, sizes S/M/L, {PRINT_LOCATION.lower()} print."
NONCOMMITMENT = ("This intake ticket is not a quote, a confirmed order, or a promise "
                 "that the deadline can be met.")
UNAVAILABLE_MESSAGE = "Live AI unavailable — manual intake mode"

# Display label per extracted field. Sizes is ONE field holding a dict.
FIELD_LABEL = {
    "customer_name": "Customer name",
    "contact": "Email or phone",
    "sizes": "Size breakdown (S/M/L)",
    "deadline": "Deadline (YYYY-MM-DD)",
    "stated_total": "Stated total",
}
# Editor keys: sizes is typed as three boxes but travels as one dict.
EDIT_KEYS = ["customer_name", "contact", "size_S", "size_M", "size_L",
             "deadline", "stated_total"]

_NUMS = re.compile(r"\d+")


def empty_extraction() -> dict:
    return {"fields": {n: {"value": None, "evidence": None} for n in FIELDS},
            "ambiguities": [], "dropped": [], "error": None}


def live_ai_configured() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _norm(s: str) -> str:
    return " ".join(str(s).split()).lower()


def _topic(text: str) -> str | None:
    """Classify an issue so a block and a question about the same thing can be
    recognised as one issue, however the model happened to word it."""
    t = _norm(text)
    mismatch = any(k in t for k in ("add up", "adds up", "sum", "match", "differ",
                                    "disagree", "conflict", "inconsistent", "equal"))
    if mismatch and any(k in t for k in ("size", "total", "shirt")):
        return "total_mismatch"
    if any(k in t for k in ("deadline", "date", "year", "lead time")):
        return "deadline"
    if any(k in t for k in ("size", "small", "medium", "large")):
        return "sizes"
    if any(k in t for k in ("email", "phone", "contact")):
        return "contact"
    if "name" in t:
        return "customer_name"
    return None


def dedupe_questions(blocks: list[str], questions: list[str]) -> list[str]:
    """When a block and a question state the same issue — the 30-vs-25 mismatch
    being the one that matters — show it once, as the block. Blocks are the
    stronger signal, so the question is the one that gets dropped."""
    block_norms = {_norm(b) for b in blocks}
    block_topics = {t for t in (_topic(b) for b in blocks) if t}
    block_numbers = {tuple(sorted(_NUMS.findall(b))) for b in blocks if _NUMS.search(b)}
    out, seen = [], set()
    for q in questions:
        norm = _norm(q)
        if norm in block_norms or norm in seen:
            continue
        topic = _topic(q)
        if topic and topic in block_topics:
            continue
        numbers = tuple(sorted(_NUMS.findall(q)))
        if numbers and numbers in block_numbers:
            continue
        seen.add(norm)
        out.append(q)
    return out


def initialize() -> None:
    defaults = {
        "source_text": "", "mode": None, "draft_source": None, "stale": False,
        "reviewed": False, "prepared": None, "history": [],
        "active_history": None, "active_issues": [], "issue_generation": 0,
        "extraction": empty_extraction(), "extraction_error": None,
        "prepare_error": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)
    for key in EDIT_KEYS:
        st.session_state.setdefault(f"edit_{key}", "")


def invalidate() -> None:
    st.session_state.reviewed = False
    st.session_state.prepared = None
    st.session_state.prepare_error = None


def source_changed() -> None:
    invalidate()
    if st.session_state.mode is not None:
        st.session_state.stale = True


def issue_key(index: int) -> str:
    return f"resolved_{st.session_state.issue_generation}_{index}"


def current_overrides() -> tuple[dict, list[str]]:
    """Founder-typed values beat the model. Blank means 'no override'."""
    overrides, errors = {}, []
    for name in ("customer_name", "contact", "deadline"):
        raw = st.session_state[f"edit_{name}"].strip()
        if raw:
            overrides[name] = raw

    raw_total = st.session_state["edit_stated_total"].strip()
    if raw_total:
        try:
            overrides["stated_total"] = int(raw_total)
        except ValueError:
            errors.append(f"{FIELD_LABEL['stated_total']} must be a whole number.")

    counts, typed = {}, False
    for size in SIZES:
        raw = st.session_state[f"edit_size_{size}"].strip()
        if not raw:
            continue
        typed = True
        try:
            counts[size] = int(raw)
        except ValueError:
            errors.append(f"Size {size} must be a whole number.")
    if typed and not errors:
        overrides["sizes"] = counts
    return overrides, errors


def founder_edits(extraction: dict, typed: dict) -> dict:
    """Editors are prefilled from the extraction, so a value only counts as a
    founder override once it actually differs from what the model proposed."""
    edits = {}
    for name, value in typed.items():
        extracted = (extraction["fields"].get(name) or {}).get("value")
        if name == "sizes" and isinstance(extracted, dict):
            if {s: int(extracted.get(s, 0)) for s in SIZES} == {s: int(value.get(s, 0)) for s in SIZES}:
                continue
        elif extracted is not None and str(extracted) == str(value):
            continue
        edits[name] = value
    return edits


def snapshot() -> dict:
    state = st.session_state
    return {"source_text": state.source_text, "mode": state.mode,
            "editor": {key: state[f"edit_{key}"] for key in EDIT_KEYS}}


def begin_draft(extraction: dict, mode: str) -> None:
    state = st.session_state
    invalidate()
    state.mode = mode
    state.extraction = extraction
    state.draft_source = state.source_text
    state.stale = False
    state.issue_generation += 1
    state.active_issues = list(extraction.get("ambiguities") or [])
    for key in EDIT_KEYS:
        state[f"edit_{key}"] = ""
    for name in FIELDS:
        value = (extraction["fields"].get(name) or {}).get("value")
        if value is None:
            continue
        if name == "sizes" and isinstance(value, dict):
            for size in SIZES:
                state[f"edit_size_{size}"] = str(value.get(size, 0))
        elif name != "sizes":
            state[f"edit_{name}"] = str(value)


def start_manual() -> None:
    state = st.session_state
    if state.prepared or not state.source_text.strip():
        return
    # Switching modes for the same inquiry cannot erase known model conflicts.
    issues = list(state.active_issues) if state.draft_source == state.source_text else []
    blank = empty_extraction()
    blank["ambiguities"] = issues
    begin_draft(blank, "manual")
    state.active_history = None
    state.extraction_error = None


def run_extraction() -> None:
    state = st.session_state
    if state.prepared or not state.source_text.strip():
        return
    invalidate()
    source = state.source_text
    with st.spinner("Reading the inquiry..."):
        extraction = extract_order(source)
    state.extraction_error = extraction["error"]
    if extraction["error"]:
        # Gate produced nothing trustworthy; fall back to manual, keep the app usable.
        begin_draft(empty_extraction(), "manual")
        state.active_history = None
        return
    state.history.append({"source_text": source, "extraction": extraction})
    begin_draft(extraction, "live_ai")
    state.active_history = len(state.history) - 1


def load_sample(samples: list[dict]) -> None:
    if st.session_state.prepared:
        return
    st.session_state.source_text = samples[st.session_state.sample_choice]["input"]
    source_changed()


def acknowledgment_changed() -> None:
    st.session_state.prepared = None
    st.session_state.prepare_error = None


def prepare_ticket() -> None:
    state = st.session_state
    typed, errors = current_overrides()
    overrides = founder_edits(state.extraction, typed)
    if errors or state.stale or state.draft_source != state.source_text:
        invalidate()
        state.prepare_error = "Resolve the current intake before preparing a ticket."
        return
    result = validate(state.extraction, overrides)
    if not result["ok"] or state.reviewed is not True:
        state.prepared = None
        state.prepare_error = "Complete the fields and human review before preparing a ticket."
        return
    state.prepared = {"snapshot": snapshot(),
                      "ticket": render_ticket(result, state.source_text),
                      "json": ticket_json(result, state.source_text)}
    state.prepare_error = None


def render_evidence(name: str, extraction: dict, overridden: bool) -> None:
    """THE DEMO: every value shown next to the verbatim words it came from."""
    field = extraction["fields"].get(name) or {}
    value, evidence = field.get("value"), field.get("evidence")
    if value is not None:
        st.markdown(f"**{value}**")
        st.caption(f'Quoted from the inquiry: "{evidence}"' if evidence
                   else "Founder-entered — no quote from the inquiry.")
    elif evidence:
        # Mentioned, but too vague to use. Different from never mentioned.
        st.markdown("_Not specific enough_")
        st.caption(f'The inquiry only says: "{evidence}"')
    else:
        st.markdown("_Not stated_")
        st.caption("Nothing in the inquiry mentions this.")
    if overridden:
        st.caption("Overridden by you below.")


def main() -> None:
    st.set_page_config(page_title="OrderReady", page_icon="📋", layout="centered")
    initialize()
    state = st.session_state

    # Defend against changed state even when no widget callback ran.
    if state.mode is not None and state.source_text != state.draft_source:
        state.stale = True
        invalidate()

    typed, parse_errors = current_overrides()
    overrides = founder_edits(state.extraction, typed)
    result = validate(state.extraction, overrides)
    if state.prepared and (state.prepared["snapshot"] != snapshot()
                           or state.reviewed is not True or state.stale
                           or parse_errors or not result["ok"]):
        invalidate()
    locked = state.prepared is not None

    st.title("OrderReady")
    st.write("Turn a customer message into a checked intake ticket.")
    st.info(f"Demonstration service: {SERVICE}")
    st.caption("Use synthetic inquiries. Live extraction sends the inquiry to Anthropic. "
               "Intake stays in this app session; provider retention is not verified.")

    st.header("1. Customer inquiry")
    samples = [{"label": case["id"], "input": case["text"]} for case in fixtures.CASES]
    if samples:
        st.selectbox("Optional sample inquiry", range(len(samples)),
                     format_func=lambda i: samples[i]["label"], key="sample_choice",
                     disabled=locked, on_change=invalidate)
        st.button("Load sample", key="load_sample", on_click=load_sample,
                  args=(samples,), disabled=locked)
    st.text_area("Customer message", key="source_text", height=150,
                 disabled=locked, on_change=source_changed)
    configured = live_ai_configured()
    if not configured:
        st.warning(UNAVAILABLE_MESSAGE)
        st.caption("Choose Start manual entry to begin. Live extraction requires ANTHROPIC_API_KEY.")
    left, right = st.columns(2)
    left.button("Extract with live AI", key="extract", on_click=run_extraction,
                disabled=locked or not configured or not state.source_text.strip())
    right.button("Start manual entry", key="manual", on_click=start_manual,
                 disabled=locked or not state.source_text.strip())
    if state.extraction_error:
        st.warning(UNAVAILABLE_MESSAGE)
        st.caption(state.extraction_error)
        st.button("Retry live extraction", key="retry", on_click=run_extraction,
                  disabled=locked or not configured or not state.source_text.strip())

    st.header("2. Review and correct")
    if state.mode is None:
        st.info("Paste an inquiry, then explicitly extract it or start manual entry.")
    else:
        st.write("Intake mode: " + ("Live AI proposal with human review"
                                    if state.mode == "live_ai" else "Manual entry"))
        if state.stale:
            st.error("The inquiry changed. This draft is stale. Extract the current "
                     "inquiry or explicitly start manual entry.")

        st.caption("Left: what the AI found and the exact words it came from. "
                   "Right: your correction, which always wins.")
        for name in FIELDS:
            st.markdown(f"**{FIELD_LABEL[name]}**")
            shown, editor = st.columns(2)
            with shown:
                render_evidence(name, state.extraction, name in overrides)
            with editor:
                if name == "sizes":
                    for size, column in zip(SIZES, st.columns(len(SIZES))):
                        column.text_input(size, key=f"edit_size_{size}",
                                          disabled=locked, on_change=invalidate)
                else:
                    st.text_input("Correction", key=f"edit_{name}", disabled=locked,
                                  on_change=invalidate, label_visibility="collapsed")
            st.divider()

        for error in parse_errors:
            st.error(error)
        for block in result["blocks"]:
            st.error(block)
        for label in result["missing"]:
            st.warning(f"Still needed: {label}")

        if result["total"] is not None:
            st.metric("Computed S/M/L total", result["total"])
        else:
            st.caption("The size total appears once the size breakdown is valid. "
                       "Unknown is different from 0.")

        questions = dedupe_questions(result["blocks"], result["questions"])
        if questions:
            st.write("Ask the customer before committing:")
            for index, question in enumerate(questions):
                st.text(question)
                st.checkbox(f"I resolved issue {index + 1}", key=issue_key(index),
                            disabled=locked, on_change=invalidate)
        st.checkbox("I reviewed this inquiry, confirmed all fields and resolved all conflicts.",
                    key="reviewed", disabled=locked or state.stale,
                    on_change=acknowledgment_changed)

    for index, original in enumerate(state.history):
        is_current = (index == state.active_history and not state.stale
                      and original["source_text"] == state.source_text)
        label = ("Original AI proposal for this inquiry" if is_current
                 else "Earlier extraction (historical comparison only)")
        with st.expander(f"{label} #{index + 1}"):
            st.write("Inquiry used for this extraction:")
            st.text(original["source_text"])
            st.json(original["extraction"])

    st.header("3. Intake ticket")
    unresolved = [index for index in range(len(dedupe_questions(result["blocks"], result["questions"])))
                  if st.session_state.get(issue_key(index)) is not True]
    if locked:
        st.success("Ready for intake")
        st.code(state.prepared["ticket"], language=None, wrap_lines=True)
        st.download_button("Download intake ticket", state.prepared["ticket"],
                           file_name="orderready-intake.txt", mime="text/plain",
                           key="download", on_click="ignore")
        with st.expander("Ticket as JSON"):
            st.json(state.prepared["json"])
        st.button("Edit intake", key="edit_intake", on_click=invalidate)
    else:
        if result["blocks"] or parse_errors:
            st.error("Needs correction")
        else:
            st.info("Needs information")
        if state.mode is not None and result["ok"] and not state.stale:
            st.caption("Acknowledge your review, then prepare the intake ticket.")
        # Export is gated on validate() ok=True. Nothing else unlocks it.
        st.button("Prepare intake ticket", key="prepare", on_click=prepare_ticket,
                  disabled=(state.mode is None or not result["ok"] or state.stale
                            or bool(parse_errors) or state.reviewed is not True
                            or bool(unresolved)))
        if state.prepare_error:
            st.error(state.prepare_error)
    st.caption(NONCOMMITMENT)


if __name__ == "__main__":
    main()
