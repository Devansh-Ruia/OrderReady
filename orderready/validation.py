"""Deterministic validation; never repairs or mutates a proposal."""

import re
from datetime import date

from orderready.models import OrderDraft, ValidationIssue


QUANTITY_FIELDS = ("requested_total", "size_s", "size_m", "size_l")


def parse_quantity(text: str, field: str) -> tuple[int | None, list[ValidationIssue]]:
    value = text.strip()
    if not value:
        return None, []
    if re.fullmatch(r"[+-]?[0-9]+", value):
        try:
            return int(value), []
        except ValueError:
            pass
    return None, [ValidationIssue(field=field, message="Enter a whole number, or leave blank if unknown.")]


def computed_total(draft: OrderDraft) -> int | None:
    quantities = (draft.size_s, draft.size_m, draft.size_l)
    if all(type(value) is int and value >= 0 for value in quantities):
        return sum(quantities)
    return None


def validate_order(draft: OrderDraft) -> list[ValidationIssue]:
    issues = []
    if not isinstance(draft.color, str) or not draft.color.strip():
        issues.append(ValidationIssue(field="color", message="Confirm the shirt color."))

    for field in QUANTITY_FIELDS:
        value = getattr(draft, field)
        if value is None:
            message = "Enter the requested total." if field == "requested_total" else "Enter a quantity, including 0 when none are needed."
        elif type(value) is not int:
            message = "Quantity must be a whole number."
        elif field == "requested_total" and value <= 0:
            message = "Requested total must be positive."
        elif value < 0:
            message = "Size quantities cannot be negative."
        else:
            continue
        issues.append(ValidationIssue(field=field, message=message))

    total = computed_total(draft)
    if total is not None and type(draft.requested_total) is int and total != draft.requested_total:
        issues.append(ValidationIssue(
            field="requested_total",
            message=f"Requested total is {draft.requested_total}; S/M/L quantities add up to {total}. Confirm the correct numbers.",
        ))

    deadline = draft.deadline_iso
    if not deadline:
        issues.append(ValidationIssue(field="deadline_iso", message="Confirm a complete deadline in YYYY-MM-DD format."))
    else:
        try:
            if not isinstance(deadline, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", deadline):
                raise ValueError
            date.fromisoformat(deadline)
        except ValueError:
            issues.append(ValidationIssue(field="deadline_iso", message="Enter a real calendar date in YYYY-MM-DD format, including the year."))

    for issue in draft.unresolved_issues:
        issues.append(ValidationIssue(field="unresolved_issues", message=issue))
    return issues
