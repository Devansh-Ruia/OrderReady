"""Render only reviewed, valid intake tickets."""

from orderready.models import OrderDraft
from orderready.validation import computed_total, validate_order


SERVICE = "Custom T-shirt printing: one shirt color, sizes S/M/L, one front print."
NONCOMMITMENT = "This intake ticket is not a quote, a confirmed order, or a promise that the deadline can be met."


def build_ticket(
    draft: OrderDraft,
    *,
    source_text: str,
    mode: str,
    reviewed: bool,
) -> str:
    if mode not in ("live_ai", "manual"):
        raise ValueError("Unsupported intake mode.")
    if reviewed is not True:
        raise ValueError("Human review is required.")
    if validate_order(draft):
        raise ValueError("Resolve all validation issues before preparing a ticket.")
    if not isinstance(source_text, str) or not source_text.strip():
        raise ValueError("An inquiry is required.")

    provenance = "Live AI proposal, reviewed and corrected by a human" if mode == "live_ai" else "Manual entry, reviewed by a human"
    return "\n".join([
        "OrderReady intake ticket",
        "Status: Ready for intake",
        f"Demonstration service: {SERVICE}",
        f"Mode: {mode}",
        f"Provenance: {provenance}",
        "Human reviewed: Yes",
        "",
        f"Shirt color: {draft.color}",
        f"Requested total: {draft.requested_total}",
        f"Size S: {draft.size_s}",
        f"Size M: {draft.size_m}",
        f"Size L: {draft.size_l}",
        f"Computed size total: {computed_total(draft)}",
        f"Deadline wording: {draft.deadline_raw or '(not supplied)'}",
        f"Confirmed deadline: {draft.deadline_iso}",
        "Unresolved issues: None",
        "",
        NONCOMMITMENT,
        "",
        "Original inquiry (verbatim):",
        source_text,
        "",
    ])
