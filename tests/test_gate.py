"""Tests for the evidence gate: a value survives only if the exact words it
claims to come from really appear in the customer's inquiry."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model import _gate  # noqa: E402


def valid_fields(text):
    """Five fields whose evidence is all genuinely quoted from `text`."""
    return {
        "customer_name": {"value": "Anya", "evidence": "Anya here"},
        "contact": {"value": "anya@shop.com", "evidence": "anya@shop.com"},
        "sizes": {"value": {"S": 10, "M": 20, "L": 5},
                  "evidence": "10 S, 20 M, 5 L"},
        "deadline": {"value": "2026-10-02", "evidence": "by October 2, 2026"},
        "stated_total": {"value": 35, "evidence": "35 shirts"},
    }


VALID_TEXT = ("Anya here, reach me at anya@shop.com. I need 10 S, 20 M, 5 L, "
              "35 shirts total, by October 2, 2026.")


def test_fabricated_evidence_is_dropped():
    """A made-up name is thrown away because its quote is not in the inquiry."""
    fields = {"customer_name": {"value": "Priya", "evidence": "Priya here"}}
    dropped = _gate(fields, "Anya here, I need shirts.")

    assert fields["customer_name"]["value"] is None
    assert fields["customer_name"]["evidence"] == "Priya here"
    assert dropped == ["customer_name"]


def test_honest_evidence_survives():
    """A name really written in the inquiry is kept exactly as extracted."""
    fields = {"customer_name": {"value": "Anya", "evidence": "Anya here"}}
    dropped = _gate(fields, "Anya here, I need shirts.")

    assert fields["customer_name"]["value"] == "Anya"
    assert dropped == []


@pytest.mark.parametrize("evidence", [None, ""])
def test_value_with_no_evidence_is_dropped(evidence):
    """A value that cites nothing at all is thrown away."""
    fields = {"customer_name": {"value": "Anya", "evidence": evidence}}
    dropped = _gate(fields, "Anya here, I need shirts.")

    assert fields["customer_name"]["value"] is None
    assert dropped == ["customer_name"]


@pytest.mark.parametrize("evidence", ["about 40", "around 40", "~40", "40ish",
                                      "roughly 40"])
def test_vague_quantity_is_dropped_even_when_truly_quoted(evidence):
    """A fuzzy count like "about 40" is thrown away even though the customer
    really wrote those words, because it is a guess, not an order."""
    fields = {"stated_total": {"value": 40, "evidence": evidence}}
    dropped = _gate(fields, f"I need {evidence} shirts.")

    assert fields["stated_total"]["value"] is None
    assert dropped == ["stated_total"]


def test_exact_count_survives_the_vague_filter():
    """A plain, definite count is kept — the fuzzy-count filter does not
    catch numbers the customer stated outright."""
    fields = {"stated_total": {"value": 40, "evidence": "40 shirts"}}
    dropped = _gate(fields, "I need 40 shirts.")

    assert fields["stated_total"]["value"] == 40
    assert dropped == []


def test_evidence_survives_a_relocated_line_break():
    """A quote that is word-for-word right but breaks the line in a different
    place still counts — this is the wrapped-prose case from the demo fixtures."""
    fields = {"sizes": {"value": {"S": 10, "M": 20, "L": 5},
                        "evidence": "ten smalls,\ntwenty mediums\nand five larges"}}
    dropped = _gate(fields, "ten smalls, twenty mediums\nand five larges")

    assert fields["sizes"]["value"] == {"S": 10, "M": 20, "L": 5}
    assert dropped == []


def test_fabricated_quote_still_dies_after_normalisation():
    """Forgiving spacing does not forgive made-up words: a wrong name is still
    thrown away even when its quote is neatly spaced."""
    fields = {"customer_name": {"value": "Priya", "evidence": "Priya   here"}}
    dropped = _gate(fields, "Anya here, I need shirts.")

    assert fields["customer_name"]["value"] is None
    assert dropped == ["customer_name"]


def test_evidence_matching_ignores_capitalisation():
    """Shouty capitals in the quote still count as a match."""
    fields = {"customer_name": {"value": "Priya", "evidence": "PRIYA"}}
    dropped = _gate(fields, "priya here, I need shirts.")

    assert fields["customer_name"]["value"] == "Priya"
    assert dropped == []


def test_missing_field_is_filled_in_rather_than_crashing():
    """A field the model forgot entirely comes back blank instead of an error."""
    fields = {"customer_name": {"value": "Anya", "evidence": "Anya here"}}
    dropped = _gate(fields, "Anya here, I need shirts.")

    assert fields["contact"] == {"value": None, "evidence": None}
    assert "contact" not in dropped


def test_sizes_survive_as_a_dictionary():
    """A verified size breakdown stays a per-size breakdown, unchanged."""
    fields = {"sizes": {"value": {"S": 10, "M": 20, "L": 5},
                        "evidence": "10 S, 20 M, 5 L"}}
    dropped = _gate(fields, "I need 10 S, 20 M, 5 L for the team.")

    assert fields["sizes"]["value"] == {"S": 10, "M": 20, "L": 5}
    assert dropped == []


def test_fully_supported_extraction_drops_nothing():
    """When every value is genuinely quoted, nothing is thrown away."""
    fields = valid_fields(VALID_TEXT)
    dropped = _gate(fields, VALID_TEXT)

    assert fields == valid_fields(VALID_TEXT)
    assert dropped == []
