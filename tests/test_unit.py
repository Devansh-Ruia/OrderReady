"""Offline domain, SDK boundary, and Streamlit workflow tests."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import httpx2 as httpx
import pytest
from openai import APITimeoutError, AuthenticationError, OpenAI, RateLimitError
from pydantic import ValidationError
from streamlit.testing.v1 import AppTest

from orderready import extraction, samples
from orderready.export import NONCOMMITMENT, SERVICE, build_ticket
from orderready.models import ExtractionResult, OrderDraft
from orderready.validation import QUANTITY_FIELDS, computed_total, parse_quantity, validate_order


APP = Path(__file__).resolve().parents[1] / "app.py"
CONTRADICTION = "Thirty shirts. Ten small, ten medium, five large. Needed September 28."
INQUIRY_B = "Blue shirts: 25 total, 10 small, 10 medium, 5 large, needed 2026-10-28."


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    # Never load credentials or allow a real provider request from any test.
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.setattr(extraction, "load_dotenv", Mock(return_value=False))
    client = Mock(side_effect=AssertionError("Unexpected provider client"))
    monkeypatch.setattr(extraction, "OpenAI", client)
    monkeypatch.setattr(samples, "load_samples", lambda: ([], None))
    return client


@pytest.fixture
def valid():
    return OrderDraft(color="blue", requested_total=25, size_s=10, size_m=10, size_l=5,
                      deadline_raw="2026-10-28", deadline_iso="2026-10-28")


@pytest.fixture
def contradiction():
    return OrderDraft(requested_total=30, size_s=10, size_m=10, size_l=5,
                      deadline_raw="September 28", unresolved_issues=[
                          "Confirm whether the total is 30 or the size split is 25.",
                          "Which year is September 28?",
                      ])


def response_for(draft):
    return SimpleNamespace(status="completed", error=None, incomplete_details=None,
                           output=[SimpleNamespace(type="message", status="completed", content=[])],
                           output_parsed=draft)


def fake_sdk(monkeypatch, *, draft=None, failure=None):
    monkeypatch.setenv("OPENAI_API_KEY", "offline-test-key")
    monkeypatch.setenv("OPENAI_MODEL", "explicit-test-model")
    client = MagicMock()
    client.__enter__.return_value = client
    client.responses.parse.return_value = response_for(draft if draft is not None else OrderDraft())
    client.responses.parse.side_effect = failure
    constructor = Mock(return_value=client)
    monkeypatch.setattr(extraction, "OpenAI", constructor)
    return constructor, client


def new_app():
    at = AppTest.from_file(str(APP), default_timeout=10).run()
    assert not at.exception
    return at


def begin_manual(at, source=INQUIRY_B):
    at.text_area(key="source_text").set_value(source).run()
    at.button(key="manual").click().run()
    assert not at.exception
    return at


def fill_fields(at, **overrides):
    values = dict(color="blue", requested_total="25", size_s="10", size_m="10", size_l="5",
                  deadline_raw="2026-10-28", deadline_iso="2026-10-28")
    values.update(overrides)
    for field, value in values.items():
        at.text_input(key=f"edit_{field}").set_value(value)
    at.run()
    assert not at.exception


def acknowledge_and_prepare(at):
    at.checkbox(key="reviewed").check().run()
    assert not at.button(key="prepare").disabled
    at.button(key="prepare").click().run()
    assert not at.exception
    assert len(at.download_button) == 1


def test_contract_defaults_extras_and_business_rules_are_separate():
    first, second = OrderDraft(), OrderDraft()
    first.unresolved_issues.append("An issue")
    assert not second.unresolved_issues
    assert all(getattr(second, field) is None for field in OrderDraft.model_fields if field != "unresolved_issues")
    with pytest.raises(ValidationError):
        OrderDraft(unknown="value")
    assert OrderDraft(size_s=-1).size_s == -1
    assert ExtractionResult(status="unavailable", message="safe").draft is None


@pytest.mark.parametrize("field", QUANTITY_FIELDS)
@pytest.mark.parametrize("value", [True, False, 1.0, 1.5, "1"])
def test_models_reject_non_strict_quantities(field, value):
    with pytest.raises(ValidationError):
        OrderDraft(**{field: value})


@pytest.mark.parametrize("text,value", [("", None), ("  ", None), ("0", 0), ("10", 10), (" -2 ", -2), ("+3", 3)])
def test_quantity_parser_preserves_unknown_and_integer_values(text, value):
    assert parse_quantity(text, "size_s") == (value, [])


@pytest.mark.parametrize("text", ["True", "1.0", "1.5", "ten", "1e2", "1,000", "NaN", "9" * 5000])
def test_quantity_parser_reports_malformed_values(text):
    value, issues = parse_quantity(text, "size_s")
    assert value is None
    assert len(issues) == 1 and issues[0].field == "size_s"


def test_missing_fields_and_zero_are_distinct(valid):
    assert {issue.field for issue in validate_order(OrderDraft())} == {
        "color", "requested_total", "size_s", "size_m", "size_l", "deadline_iso",
    }
    valid.size_l = 0
    valid.requested_total = 20
    assert validate_order(valid) == []
    valid.size_l = None
    assert computed_total(valid) is None
    assert [issue.field for issue in validate_order(valid)] == ["size_l"]


@pytest.mark.parametrize("field,value", [("color", "  "), ("requested_total", 0),
                                        ("requested_total", -1), ("size_s", -1),
                                        ("size_m", True), ("size_l", 1.5)])
def test_validation_rejects_invalid_values_even_after_unchecked_assignment(valid, field, value):
    setattr(valid, field, value)
    assert field in {issue.field for issue in validate_order(valid)}


@pytest.mark.parametrize("deadline", ["September 28", "2026-09", "2026-9-28", "20260928",
                                     "2026-02-29", "2026-04-31", "0000-01-01",
                                     "2026-13-01", "2026-10-28T00:00:00", " 2026-10-28"])
def test_invalid_or_incomplete_dates(valid, deadline):
    valid.deadline_iso = deadline
    assert "deadline_iso" in {issue.field for issue in validate_order(valid)}


def test_calendar_valid_leap_day(valid):
    valid.deadline_iso = "2028-02-29"
    assert validate_order(valid) == []


def test_contradiction_validation_never_repairs_or_mutates(contradiction):
    original = contradiction.model_dump()
    issues = validate_order(contradiction)
    assert contradiction.model_dump() == original
    assert computed_total(contradiction) == 25
    assert any("30" in issue.message and "25" in issue.message for issue in issues)
    assert {issue.field for issue in issues} == {"color", "requested_total", "deadline_iso", "unresolved_issues"}
    with pytest.raises(ValueError):
        build_ticket(contradiction, source_text=CONTRADICTION, mode="live_ai", reviewed=True)


@pytest.mark.parametrize("reviewed", [False, None, 1, "yes"])
def test_ticket_requires_literal_true(valid, reviewed):
    with pytest.raises(ValueError):
        build_ticket(valid, source_text=INQUIRY_B, mode="manual", reviewed=reviewed)


@pytest.mark.parametrize("mode", ["cached", "demo", "LIVE_AI", "", None])
def test_ticket_rejects_unsupported_modes(valid, mode):
    with pytest.raises(ValueError):
        build_ticket(valid, source_text=INQUIRY_B, mode=mode, reviewed=True)


def test_ticket_revalidates_and_requires_source(valid):
    with pytest.raises(ValueError):
        build_ticket(valid, source_text=" ", mode="manual", reviewed=True)
    valid.size_l = 10
    with pytest.raises(ValueError):
        build_ticket(valid, source_text=INQUIRY_B, mode="manual", reviewed=True)
    valid.size_l = 5
    valid.unresolved_issues.append("Customer requested unsupported XL shirts.")
    with pytest.raises(ValueError):
        build_ticket(valid, source_text=INQUIRY_B, mode="manual", reviewed=True)


@pytest.mark.parametrize("mode", ["live_ai", "manual"])
def test_ticket_contents(valid, mode):
    ticket = build_ticket(valid, source_text=INQUIRY_B, mode=mode, reviewed=True)
    for expected in [SERVICE, NONCOMMITMENT, INQUIRY_B, f"Mode: {mode}", "Human reviewed: Yes",
                     "Shirt color: blue", "Requested total: 25", "Size S: 10", "Size M: 10", "Size L: 5",
                     "Computed size total: 25", "Deadline wording: 2026-10-28",
                     "Confirmed deadline: 2026-10-28", "Unresolved issues: None"]:
        assert expected in ticket


@pytest.mark.parametrize("key,model", [("", ""), ("key", ""), ("", "model"), (" ", "model")])
def test_missing_configuration_is_unavailable_without_client(monkeypatch, offline, key, model):
    monkeypatch.setenv("OPENAI_API_KEY", key)
    monkeypatch.setenv("OPENAI_MODEL", model)
    result = extraction.extract_inquiry(INQUIRY_B)
    assert result.status == "unavailable" and result.draft is None
    assert result.message == extraction.UNAVAILABLE_MESSAGE
    offline.assert_not_called()
    extraction.load_dotenv.assert_called_once()
    assert extraction.load_dotenv.call_args.kwargs == {"override": False}


def test_configuration_respects_explicit_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", " existing-key ")
    monkeypatch.setenv("OPENAI_MODEL", " chosen-model ")
    assert extraction._configuration() == ("existing-key", "chosen-model")
    assert extraction.load_dotenv.call_args.kwargs["override"] is False


@pytest.mark.parametrize("failure", [PermissionError("private configuration path"),
                                     UnicodeDecodeError("utf-8", bytes([255]), 0, 1, "private configuration content")])
def test_broken_optional_configuration_keeps_manual_intake_usable(monkeypatch, offline, failure):
    monkeypatch.setattr(extraction, "load_dotenv", Mock(side_effect=failure))
    result = extraction.extract_inquiry(INQUIRY_B)
    assert result.status == "unavailable" and result.message == extraction.UNAVAILABLE_MESSAGE
    at = new_app()
    assert extraction.UNAVAILABLE_MESSAGE in [item.value for item in at.warning]
    begin_manual(at)
    fill_fields(at)
    acknowledge_and_prepare(at)
    assert "Mode: manual" in at.session_state.prepared["ticket"]
    offline.assert_not_called()


def test_broken_optional_configuration_preserves_process_environment(monkeypatch, valid):
    _, client = fake_sdk(monkeypatch, draft=valid)
    monkeypatch.setattr(extraction, "load_dotenv", Mock(side_effect=OSError("private path")))
    assert extraction.live_ai_configured()
    assert extraction.extract_inquiry(INQUIRY_B).status == "success"
    client.responses.parse.assert_called_once()


def test_missing_parsing_capability_is_unavailable(monkeypatch):
    _, client = fake_sdk(monkeypatch)
    client.responses.parse = None
    assert extraction.extract_inquiry(INQUIRY_B).status == "unavailable"


def test_blank_inquiry_never_calls_provider(monkeypatch):
    constructor, _ = fake_sdk(monkeypatch)
    assert extraction.extract_inquiry("  ").status == "error"
    constructor.assert_not_called()


@pytest.mark.parametrize("kind", ["authentication", "timeout", "rate_limit", "malformed"])
def test_extraction_failures_are_safe_and_never_retried(monkeypatch, caplog, capsys, kind):
    request = httpx.Request("POST", "https://example.test/v1/responses")
    failures = {
        "authentication": AuthenticationError("sensitive inquiry", response=httpx.Response(401, request=request), body=None),
        "timeout": APITimeoutError(request=request),
        "rate_limit": RateLimitError("sensitive inquiry", response=httpx.Response(429, request=request), body=None),
        "malformed": ValueError("sensitive inquiry"),
    }
    constructor, client = fake_sdk(monkeypatch, failure=failures[kind])
    result = extraction.extract_inquiry("sensitive inquiry")
    assert result.status == "error" and result.draft is None
    assert result.message == extraction.ERROR_MESSAGE
    constructor.assert_called_once_with(api_key="offline-test-key", timeout=30.0, max_retries=0)
    client.responses.parse.assert_called_once()
    assert "sensitive inquiry" not in caplog.text + capsys.readouterr().out + result.message


@pytest.mark.parametrize("kind", ["refusal", "incomplete", "error", "no_parsed", "wrong_type", "bad_quantity", "broken_envelope"])
def test_malformed_or_incomplete_responses_fail_safely(monkeypatch, valid, kind):
    _, client = fake_sdk(monkeypatch, draft=valid)
    response = client.responses.parse.return_value
    if kind == "refusal":
        response.output[0].content = [SimpleNamespace(type="refusal")]
    elif kind == "incomplete":
        response.status = "incomplete"
    elif kind == "error":
        response.error = {"message": "sensitive provider error"}
    elif kind == "no_parsed":
        response.output_parsed = None
    elif kind == "wrong_type":
        response.output_parsed = {"color": "blue"}
    elif kind == "bad_quantity":
        response.output_parsed = OrderDraft.model_construct(size_s=True)
    else:
        client.responses.parse.return_value = SimpleNamespace()
    result = extraction.extract_inquiry(INQUIRY_B)
    assert result.status == "error" and result.message == extraction.ERROR_MESSAGE
    client.responses.parse.assert_called_once()


def test_successful_extraction_is_only_a_proposal(monkeypatch, contradiction):
    constructor, client = fake_sdk(monkeypatch, draft=contradiction)
    result = extraction.extract_inquiry(CONTRADICTION)
    assert result.status == "success"
    assert result.draft == contradiction
    assert result.draft.requested_total == 30
    assert (result.draft.size_s, result.draft.size_m, result.draft.size_l) == (10, 10, 5)
    assert result.draft.deadline_raw == "September 28" and result.draft.deadline_iso is None
    assert validate_order(result.draft)
    kwargs = client.responses.parse.call_args.kwargs
    assert kwargs["input"] == [{"role": "user", "content": CONTRADICTION}]
    assert kwargs["instructions"] == extraction.INSTRUCTIONS
    assert CONTRADICTION not in kwargs["instructions"]
    assert kwargs["text_format"] is OrderDraft and kwargs["model"] == "explicit-test-model"
    assert kwargs["store"] is False
    assert constructor.call_count == client.responses.parse.call_count == 1


def test_missing_total_stays_unknown_after_extraction(monkeypatch, valid):
    valid.requested_total = None
    fake_sdk(monkeypatch, draft=valid)
    draft = extraction.extract_inquiry("10 small, 10 medium, 5 large, blue, 2026-10-28").draft
    assert draft.requested_total is None
    assert computed_total(draft) == 25
    assert validate_order(draft)


def test_real_sdk_serialization_and_parsing_use_one_mock_http_request(monkeypatch, contradiction):
    monkeypatch.setenv("OPENAI_API_KEY", "offline-test-key")
    monkeypatch.setenv("OPENAI_MODEL", "explicit-test-model")
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={
            "id": "resp_offline", "object": "response", "created_at": 0,
            "model": "explicit-test-model", "status": "completed", "error": None,
            "incomplete_details": None, "parallel_tool_calls": False, "tools": [],
            "tool_choice": "auto", "output": [{
                "type": "message", "id": "msg_offline", "role": "assistant", "status": "completed",
                "content": [{"type": "output_text", "text": contradiction.model_dump_json(), "annotations": []}],
            }],
        })

    def client_factory(**kwargs):
        return OpenAI(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(respond)))

    monkeypatch.setattr(extraction, "OpenAI", client_factory)
    result = extraction.extract_inquiry(CONTRADICTION)
    assert result.status == "success" and result.draft == contradiction
    assert len(requests) == 1
    body = json.loads(requests[0].content)
    assert body["input"][0]["content"] == CONTRADICTION
    assert body["text"]["format"]["strict"] is True
    schema = body["text"]["format"]["schema"]
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(OrderDraft.model_fields)
    assert requests[0].extensions["timeout"]["read"] == 30.0


def test_app_requires_explicit_manual_start_and_blank_fields(offline):
    at = new_app()
    assert extraction.UNAVAILABLE_MESSAGE in [warning.value for warning in at.warning]
    assert at.session_state.mode is None and len(at.text_input) == 0
    at.text_area(key="source_text").set_value(INQUIRY_B).run()
    assert at.session_state.mode is None
    at.button(key="manual").click().run()
    assert at.session_state.mode == "manual"
    assert all(widget.value == "" for widget in at.text_input)
    assert at.button(key="prepare").disabled
    assert "Needs information" in [item.value for item in at.info]
    offline.assert_not_called()


def test_app_edit_persistence_and_malformed_values(offline):
    at = begin_manual(new_app())
    fill_fields(at, size_m="1.5")
    at.run()
    assert at.text_input(key="edit_size_m").value == "1.5"
    assert at.text_input(key="edit_color").value == "blue"
    assert not at.metric and not at.download_button
    assert "Needs correction" in [item.value for item in at.error]
    assert any("whole number" in item.value for item in at.error)
    at.text_input(key="edit_size_m").set_value("10").run()
    assert at.metric[0].value == "25"
    assert at.button(key="prepare").disabled
    at.checkbox(key="reviewed").check().run()
    at.text_input(key="edit_color").set_value("navy").run()
    assert at.checkbox(key="reviewed").value is False
    offline.assert_not_called()


def test_app_preparation_freezes_controls_and_download_has_no_requests(monkeypatch, valid):
    _, client = fake_sdk(monkeypatch, draft=valid)
    at = new_app()
    at.text_area(key="source_text").set_value(INQUIRY_B).run()
    at.button(key="extract").click().run()
    assert client.responses.parse.call_count == 1
    at.run()
    at.checkbox(key="reviewed").check().run()
    assert client.responses.parse.call_count == 1
    at.button(key="prepare").click().run()
    assert not at.exception
    assert all(widget.disabled for widget in at.text_input)
    assert at.text_area(key="source_text").disabled
    assert at.checkbox(key="reviewed").disabled
    assert at.button(key="extract").disabled and at.button(key="manual").disabled
    ticket = at.session_state.prepared["ticket"]
    assert "Mode: live_ai" in ticket
    at.download_button(key="download").click().run()
    assert at.session_state.prepared["ticket"] == ticket
    assert client.responses.parse.call_count == 1
    at.button(key="edit_intake").click().run()
    assert not at.download_button
    assert not at.checkbox(key="reviewed").value
    assert not at.text_area(key="source_text").disabled
    assert at.text_input(key="edit_size_s").value == "10"


def test_app_contradiction_needs_deliberate_correction_and_each_issue_resolved(monkeypatch, contradiction):
    _, client = fake_sdk(monkeypatch, draft=contradiction)
    at = new_app()
    at.text_area(key="source_text").set_value(CONTRADICTION).run()
    at.button(key="extract").click().run()
    assert at.text_input(key="edit_requested_total").value == "30"
    assert [at.text_input(key=f"edit_size_{size}").value for size in "sml"] == ["10", "10", "5"]
    assert at.metric[0].value == "25"
    assert at.text_input(key="edit_deadline_raw").value == "September 28"
    assert at.text_input(key="edit_deadline_iso").value == ""
    assert at.button(key="prepare").disabled and not at.download_button
    original = at.session_state.history[0]["draft"].copy()
    fill_fields(at, deadline_raw="September 28", deadline_iso="2026-09-28")
    assert len(at.session_state.active_issues) == 2
    at.checkbox(key="reviewed").check().run()
    assert at.button(key="prepare").disabled
    at.checkbox(key="resolved_1_0").check().run()
    assert not at.checkbox(key="reviewed").value
    at.checkbox(key="reviewed").check().run()
    assert at.button(key="prepare").disabled
    at.checkbox(key="resolved_1_1").check().run()
    assert not at.checkbox(key="reviewed").value
    acknowledge_and_prepare(at)
    assert at.session_state.history[0]["draft"] == original
    assert "Requested total: 25" in at.session_state.prepared["ticket"]
    assert client.responses.parse.call_count == 1


def test_source_change_and_failed_extraction_preserve_edits_and_provenance(monkeypatch, valid):
    _, client = fake_sdk(monkeypatch, draft=valid)
    at = new_app()
    at.text_area(key="source_text").set_value("Inquiry A").run()
    at.button(key="extract").click().run()
    at.text_input(key="edit_color").set_value("navy").run()
    at.checkbox(key="reviewed").check().run()
    at.text_area(key="source_text").set_value(INQUIRY_B).run()
    assert at.session_state.stale and not at.session_state.reviewed
    assert at.button(key="prepare").disabled
    client.responses.parse.side_effect = RuntimeError("private request details")
    at.button(key="extract").click().run()
    assert at.text_input(key="edit_color").value == "navy"
    assert at.session_state.mode == "live_ai" and at.session_state.draft_source == "Inquiry A"
    assert at.session_state.history[0]["source_text"] == "Inquiry A"
    assert at.session_state.stale and not at.session_state.reviewed
    assert "Earlier extraction" in at.expander[0].label
    assert "Inquiry A" in [item.value for item in at.text]
    assert at.button(key="retry")
    at.run()
    assert client.responses.parse.call_count == 2
    at.button(key="retry").click().run()
    assert client.responses.parse.call_count == 3
    at.button(key="manual").click().run()
    assert at.session_state.mode == "manual" and not at.session_state.stale
    assert all(widget.value == "" for widget in at.text_input)
    fill_fields(at)
    acknowledge_and_prepare(at)
    ticket = at.session_state.prepared["ticket"]
    assert INQUIRY_B in ticket and "Inquiry A" not in ticket
    assert "Mode: manual" in ticket and "Manual entry" in ticket
    assert at.session_state.history[0]["source_text"] == "Inquiry A"
    assert "Earlier extraction" in at.expander[0].label
    assert client.responses.parse.call_count == 3


def test_switching_to_manual_same_source_keeps_known_issues(monkeypatch, contradiction):
    fake_sdk(monkeypatch, draft=contradiction)
    at = new_app()
    at.text_area(key="source_text").set_value(CONTRADICTION).run()
    at.button(key="extract").click().run()
    at.button(key="manual").click().run()
    assert at.session_state.mode == "manual"
    assert at.session_state.active_issues == contradiction.unresolved_issues
    fill_fields(at)
    at.checkbox(key="reviewed").check().run()
    assert at.button(key="prepare").disabled


@pytest.mark.parametrize("key,value", [("source_text", "changed source"), ("edit_color", "red"),
                                       ("mode", "live_ai"), ("reviewed", False)])
def test_prepared_snapshot_rejects_state_changes_even_without_callbacks(key, value):
    at = begin_manual(new_app())
    fill_fields(at)
    acknowledge_and_prepare(at)
    at.session_state[key] = value
    at.run()
    assert not at.exception
    assert at.session_state.prepared is None and not at.download_button
    assert not at.session_state.reviewed


def test_sample_loading_uses_only_input_and_requires_explicit_start(monkeypatch):
    monkeypatch.setattr(samples, "load_samples", lambda: ([
        {"label": "First", "input": CONTRADICTION}, {"label": "Second", "input": INQUIRY_B},
    ], None))
    at = new_app()
    at.selectbox(key="sample_choice").set_value(1).run()
    assert at.text_area(key="source_text").value == ""
    at.button(key="load_sample").click().run()
    assert at.text_area(key="source_text").value == INQUIRY_B
    assert at.session_state.mode is None
    at.button(key="manual").click().run()
    fill_fields(at)
    acknowledge_and_prepare(at)
    assert at.selectbox(key="sample_choice").disabled
    assert at.button(key="load_sample").disabled
    at.button(key="edit_intake").click().run()
    at.checkbox(key="reviewed").check().run()
    at.selectbox(key="sample_choice").set_value(0).run()
    assert not at.session_state.reviewed
    at.button(key="load_sample").click().run()
    assert at.session_state.stale and at.button(key="prepare").disabled


@pytest.mark.parametrize("records", ["not JSON", "{}", '[{"label": "x"}]', '[null, 3]', '\ufeff[]'])
def test_malformed_sample_fixtures_are_safe(monkeypatch, records):
    # Mock file reads so tests never persist any inquiry fixture.
    from importlib import reload
    reload(samples)
    monkeypatch.setattr(Path, "read_text", lambda *args, **kwargs: records)
    loaded, warning = samples.load_samples()
    assert loaded == [] and warning


def test_samples_ignore_expected_outputs(monkeypatch):
    from importlib import reload
    reload(samples)
    record = {"label": "Example", "input": CONTRADICTION, "expected": {"requested_total": 999}}
    monkeypatch.setattr(Path, "read_text", lambda *args, **kwargs: json.dumps([record]))
    loaded, warning = samples.load_samples()
    assert loaded == [{"label": "Example", "input": CONTRADICTION}]
    assert warning is None


def test_sample_warning_does_not_crash_app(monkeypatch):
    monkeypatch.setattr(samples, "load_samples", lambda: ([], "Optional samples could not be loaded."))
    at = new_app()
    assert any("Optional samples" in item.value for item in at.warning)
    begin_manual(at)
    assert not at.exception
