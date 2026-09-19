"""Run with: python -m streamlit run app.py."""

import streamlit as st

from orderready.export import NONCOMMITMENT, SERVICE, build_ticket
from orderready.extraction import UNAVAILABLE_MESSAGE, extract_inquiry, live_ai_configured
from orderready.models import OrderDraft
from orderready.samples import load_samples
from orderready.validation import QUANTITY_FIELDS, computed_total, parse_quantity, validate_order


FIELDS = {
    "color": "Shirt color",
    "requested_total": "Requested total",
    "size_s": "Size S",
    "size_m": "Size M",
    "size_l": "Size L",
    "deadline_raw": "Original deadline wording",
    "deadline_iso": "Confirmed deadline (YYYY-MM-DD)",
}


def initialize() -> None:
    defaults = {
        "source_text": "", "mode": None, "draft_source": None, "stale": False,
        "reviewed": False, "prepared": None, "history": [],
        "active_history": None, "active_issues": [], "issue_generation": 0,
        "extraction_status": None, "extraction_message": None, "prepare_error": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)
    for field in FIELDS:
        st.session_state.setdefault(f"edit_{field}", "")


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


def current_draft():
    values, parse_issues = {}, []
    for field in FIELDS:
        raw = st.session_state[f"edit_{field}"]
        if field in QUANTITY_FIELDS:
            values[field], errors = parse_quantity(raw, field)
            parse_issues.extend(errors)
        else:
            values[field] = raw if raw.strip() else None
    values["unresolved_issues"] = [
        issue for index, issue in enumerate(st.session_state.active_issues)
        if st.session_state.get(issue_key(index)) is not True
    ]
    return OrderDraft(**values), parse_issues


def snapshot(draft: OrderDraft) -> dict:
    state = st.session_state
    return {
        "source_text": state.source_text, "draft": draft.model_dump(), "mode": state.mode,
        "editor": {field: state[f"edit_{field}"] for field in FIELDS},
    }


def begin_draft(draft: OrderDraft, mode: str) -> None:
    state = st.session_state
    invalidate()
    state.mode = mode
    state.draft_source = state.source_text
    state.stale = False
    state.issue_generation += 1
    state.active_issues = list(draft.unresolved_issues)
    for field in FIELDS:
        value = getattr(draft, field)
        state[f"edit_{field}"] = "" if value is None else str(value)


def start_manual() -> None:
    state = st.session_state
    if state.prepared or not state.source_text.strip():
        return
    # Switching modes for the same inquiry cannot erase known model conflicts.
    issues = list(state.active_issues) if state.draft_source == state.source_text else []
    begin_draft(OrderDraft(unresolved_issues=issues), "manual")
    state.active_history = None
    state.extraction_status = None
    state.extraction_message = None


def run_extraction() -> None:
    state = st.session_state
    if state.prepared or not state.source_text.strip():
        return
    invalidate()
    source = state.source_text
    with st.spinner("Reading the inquiry..."):
        result = extract_inquiry(source)
    state.extraction_status = result.status
    state.extraction_message = result.message
    if result.status == "success" and result.draft is not None:
        state.history.append({"source_text": source, "draft": result.draft.model_dump()})
        begin_draft(result.draft, "live_ai")
        state.active_history = len(state.history) - 1


def load_sample(samples: list[dict[str, str]]) -> None:
    if st.session_state.prepared:
        return
    st.session_state.source_text = samples[st.session_state.sample_choice]["input"]
    source_changed()


def acknowledgment_changed() -> None:
    st.session_state.prepared = None
    st.session_state.prepare_error = None


def prepare_ticket() -> None:
    state = st.session_state
    draft, errors = current_draft()
    if errors or state.stale or state.draft_source != state.source_text:
        invalidate()
        state.prepare_error = "Resolve the current intake before preparing a ticket."
        return
    try:
        ticket = build_ticket(draft, source_text=state.source_text, mode=state.mode, reviewed=state.reviewed)
    except ValueError:
        state.prepared = None
        state.prepare_error = "Complete the fields and human review before preparing a ticket."
        return
    state.prepared = {"snapshot": snapshot(draft), "ticket": ticket}
    state.prepare_error = None


def main() -> None:
    st.set_page_config(page_title="OrderReady", page_icon="📋", layout="centered")
    initialize()
    state = st.session_state

    # Defend against changed state even when no widget callback ran.
    if state.mode is not None and state.source_text != state.draft_source:
        state.stale = True
        invalidate()
    draft, parse_issues = current_draft()
    if state.prepared and (
        state.prepared["snapshot"] != snapshot(draft)
        or state.reviewed is not True or state.stale
        or parse_issues or validate_order(draft)
    ):
        invalidate()
    locked = state.prepared is not None

    st.title("OrderReady")
    st.write("Turn a customer message into a checked intake ticket.")
    st.info(f"Demonstration service: {SERVICE}")
    st.caption("Use synthetic inquiries. Live extraction sends the inquiry to OpenAI. Intake stays in this app session; provider retention is not verified.")

    st.header("1. Customer inquiry")
    samples, samples_warning = load_samples()
    if samples_warning:
        st.warning(samples_warning)
    if samples:
        st.selectbox("Optional sample inquiry", range(len(samples)),
                     format_func=lambda i: samples[i]["label"], key="sample_choice",
                     disabled=locked, on_change=invalidate)
        st.button("Load sample", key="load_sample", on_click=load_sample, args=(samples,), disabled=locked)
    st.text_area("Customer message", key="source_text", height=150,
                 disabled=locked, on_change=source_changed)
    configured = live_ai_configured()
    if not configured:
        st.warning(UNAVAILABLE_MESSAGE)
        st.caption("Choose Start manual entry to begin. Live extraction requires OPENAI_API_KEY and OPENAI_MODEL.")
    left, right = st.columns(2)
    left.button("Extract with live AI", key="extract", on_click=run_extraction,
                disabled=locked or not configured or not state.source_text.strip())
    right.button("Start manual entry", key="manual", on_click=start_manual,
                 disabled=locked or not state.source_text.strip())
    if state.extraction_message:
        if state.extraction_status == "success":
            st.info(state.extraction_message)
        else:
            st.warning(state.extraction_message)
            st.button("Retry live extraction", key="retry", on_click=run_extraction,
                      disabled=locked or not configured or not state.source_text.strip())

    st.header("2. Review and correct")
    if state.mode is None:
        st.info("Paste an inquiry, then explicitly extract it or start manual entry.")
    else:
        st.write("Intake mode: " + ("Live AI proposal with human review" if state.mode == "live_ai" else "Manual entry"))
        if state.stale:
            st.error("The inquiry changed. This draft is stale. Extract the current inquiry or explicitly start manual entry.")
        errors = parse_issues + [issue for issue in validate_order(draft)
                                if issue.field not in {error.field for error in parse_issues}]
        for field, label in FIELDS.items():
            st.text_input(label, key=f"edit_{field}", disabled=locked, on_change=invalidate)
            for issue in errors:
                if issue.field == field:
                    st.error(issue.message)
        total = computed_total(draft)
        if total is not None:
            st.metric("Computed S/M/L total", total)
        else:
            st.caption("The size total appears once all three size quantities are valid. Unknown is different from 0.")
        if state.active_issues:
            st.write("Resolve each AI-reported issue after confirming it with the customer:")
            for index, issue in enumerate(state.active_issues):
                st.text(issue)
                st.checkbox(f"I resolved issue {index + 1}", key=issue_key(index),
                            disabled=locked, on_change=invalidate)
        st.checkbox("I reviewed this inquiry, confirmed all fields and resolved all conflicts.",
                    key="reviewed", disabled=locked or state.stale,
                    on_change=acknowledgment_changed)

    for index, original in enumerate(state.history):
        is_current = index == state.active_history and not state.stale and original["source_text"] == state.source_text
        label = "Original AI proposal for this inquiry" if is_current else "Earlier extraction (historical comparison only)"
        with st.expander(f"{label} #{index + 1}"):
            st.write("Inquiry used for this extraction:")
            st.text(original["source_text"])
            st.json(original["draft"])

    st.header("3. Intake ticket")
    errors = parse_issues + validate_order(draft)
    missing = {field for field in FIELDS if getattr(draft, field) is None}
    needs_correction = state.stale or bool(parse_issues) or any(issue.field not in missing for issue in errors)
    if locked:
        st.success("Ready for intake")
        st.code(state.prepared["ticket"], language=None, wrap_lines=True)
        st.download_button("Download intake ticket", state.prepared["ticket"],
                           file_name="orderready-intake.txt", mime="text/plain", key="download",
                           on_click="ignore")
        st.button("Edit intake", key="edit_intake", on_click=invalidate)
    else:
        if needs_correction:
            st.error("Needs correction")
        else:
            st.info("Needs information")
        if state.mode is not None and not errors and not state.stale:
            st.caption("Acknowledge your review, then prepare the intake ticket.")
        st.button("Prepare intake ticket", key="prepare", on_click=prepare_ticket,
                  disabled=state.mode is None or bool(errors) or state.stale or state.reviewed is not True)
        if state.prepare_error:
            st.error(state.prepare_error)
    st.caption(NONCOMMITMENT)


if __name__ == "__main__":
    main()
