"""Offline domain and HTTP boundary tests. Active UI coverage is in test_frontend."""

import json
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPSHandler, build_opener
from urllib.response import addinfourl
from unittest.mock import MagicMock, Mock

import pytest
from pydantic import ValidationError

from orderready import extraction, samples
from orderready.export import NONCOMMITMENT, SERVICE, build_ticket
from orderready.models import ExtractionResult, OrderDraft
from orderready.validation import QUANTITY_FIELDS, computed_total, parse_quantity, validate_order


CONTRADICTION = "Thirty shirts. Ten small, ten medium, five large. Needed September 28."
INQUIRY_B = "Blue shirts: 25 total, 10 small, 10 medium, 5 large, needed 2026-10-28."


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    # Never load credentials or allow a real provider request from any test.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("MODEL_ID", raising=False)
    monkeypatch.setattr(extraction, "load_dotenv", Mock(return_value=False))
    monkeypatch.setattr("urllib.request.urlopen", Mock(side_effect=AssertionError("Unexpected live HTTP request")))
    client = Mock(side_effect=AssertionError("Unexpected provider client"))
    monkeypatch.setattr(extraction, "build_opener", client)
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
    return {
        "id": "msg_offline", "type": "message", "role": "assistant",
        "model": "explicit-test-model", "stop_reason": "end_turn",
        "content": [{"type": "text", "text": draft.model_dump_json()}],
    }


def fake_transport(monkeypatch, *, draft=None, failure=None):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "offline-test-key")
    monkeypatch.setenv("MODEL_ID", "explicit-test-model")
    response = MagicMock()
    response.__enter__.return_value = response
    response.getcode.return_value = 200
    response.read.return_value = json.dumps(response_for(draft if draft is not None else OrderDraft())).encode()
    client = Mock()
    client.open.return_value = response
    client.open.side_effect = failure
    constructor = Mock(return_value=client)
    monkeypatch.setattr(extraction, "build_opener", constructor)
    return constructor, client


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
    monkeypatch.setenv("ANTHROPIC_API_KEY", key)
    monkeypatch.setenv("MODEL_ID", model)
    result = extraction.extract_inquiry(INQUIRY_B)
    assert result.status == "unavailable" and result.draft is None
    assert result.message == extraction.UNAVAILABLE_MESSAGE
    offline.assert_not_called()
    extraction.load_dotenv.assert_called_once()
    assert extraction.load_dotenv.call_args.kwargs == {"override": False}


def test_configuration_respects_explicit_environment(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", " existing-key ")
    monkeypatch.setenv("MODEL_ID", " chosen-model ")
    assert extraction._configuration() == ("existing-key", "chosen-model")
    assert extraction.load_dotenv.call_args.kwargs["override"] is False


@pytest.mark.parametrize("failure", [PermissionError("private configuration path"),
                                     UnicodeDecodeError("utf-8", bytes([255]), 0, 1, "private configuration content")])
def test_broken_optional_configuration_keeps_manual_intake_usable(monkeypatch, offline, failure):
    monkeypatch.setattr(extraction, "load_dotenv", Mock(side_effect=failure))
    result = extraction.extract_inquiry(INQUIRY_B)
    assert result.status == "unavailable" and result.message == extraction.UNAVAILABLE_MESSAGE
    offline.assert_not_called()


def test_broken_optional_configuration_preserves_process_environment(monkeypatch, valid):
    _, client = fake_transport(monkeypatch, draft=valid)
    monkeypatch.setattr(extraction, "load_dotenv", Mock(side_effect=OSError("private path")))
    assert extraction.live_ai_configured()
    assert extraction.extract_inquiry(INQUIRY_B).status == "success"
    client.open.assert_called_once()


def test_old_provider_configuration_does_not_enable_live_ai(monkeypatch, offline):
    monkeypatch.setenv("OPENAI_API_KEY", "offline-old-provider-key")
    monkeypatch.setenv("OPENAI_MODEL", "old-model")
    assert not extraction.live_ai_configured()
    assert extraction.extract_inquiry(INQUIRY_B).status == "unavailable"
    offline.assert_not_called()


def test_blank_inquiry_never_calls_provider(monkeypatch):
    constructor, _ = fake_transport(monkeypatch)
    assert extraction.extract_inquiry("  ").status == "error"
    constructor.assert_not_called()


@pytest.mark.parametrize("kind", ["authentication", "timeout", "rate_limit", "network", "malformed"])
def test_extraction_failures_are_safe_and_never_retried(monkeypatch, caplog, capsys, kind):
    failures = {
        "authentication": HTTPError("https://api.anthropic.com/v1/messages", 401, "sensitive inquiry", {}, None),
        "timeout": TimeoutError("sensitive inquiry"),
        "rate_limit": HTTPError("https://api.anthropic.com/v1/messages", 429, "sensitive inquiry", {}, None),
        "network": URLError("sensitive inquiry"),
        "malformed": ValueError("sensitive inquiry"),
    }
    constructor, client = fake_transport(monkeypatch, failure=failures[kind])
    result = extraction.extract_inquiry("sensitive inquiry")
    assert result.status == "error" and result.draft is None
    assert result.message == extraction.ERROR_MESSAGE
    constructor.assert_called_once()
    assert isinstance(constructor.call_args.args[0], extraction._NoRedirects)
    client.open.assert_called_once()
    assert client.open.call_args.kwargs == {"timeout": 30.0}
    captured = capsys.readouterr()
    assert "sensitive inquiry" not in caplog.text + captured.out + captured.err + result.message


@pytest.mark.parametrize("kind", [
    "refusal", "incomplete", "error", "no_content", "wrong_type", "bad_quantity", "broken_envelope",
    "wrong_role", "empty_text", "invalid_json", "missing_field", "extra_field", "bad_content_type", "http_error",
])
def test_malformed_or_incomplete_responses_fail_safely(monkeypatch, valid, kind):
    _, client = fake_transport(monkeypatch, draft=valid)
    response = response_for(valid)
    if kind == "refusal":
        response["stop_reason"] = "refusal"
    elif kind == "incomplete":
        response["stop_reason"] = "max_tokens"
    elif kind == "error":
        response["error"] = {"message": "sensitive provider error"}
    elif kind == "no_content":
        response["content"] = []
    elif kind == "wrong_type":
        response["type"] = "error"
    elif kind == "bad_quantity":
        values = valid.model_dump()
        values["size_s"] = True
        response["content"][0]["text"] = json.dumps(values)
    elif kind == "wrong_role":
        response["role"] = "user"
    elif kind == "empty_text":
        response["content"][0]["text"] = ""
    elif kind == "invalid_json":
        response["content"][0]["text"] = "not JSON"
    elif kind in {"missing_field", "extra_field"}:
        values = valid.model_dump()
        if kind == "missing_field":
            del values["requested_total"]
        else:
            values["invented"] = "unrecognized field"
        response["content"][0]["text"] = json.dumps(values)
    elif kind == "bad_content_type":
        response["content"][0]["type"] = "tool_use"
    elif kind == "http_error":
        client.open.return_value.getcode.return_value = 500
    else:
        response = []
    client.open.return_value.read.return_value = json.dumps(response).encode()
    result = extraction.extract_inquiry(INQUIRY_B)
    assert result.status == "error" and result.message == extraction.ERROR_MESSAGE
    client.open.assert_called_once()


def test_successful_extraction_is_only_a_proposal(monkeypatch, contradiction):
    constructor, client = fake_transport(monkeypatch, draft=contradiction)
    result = extraction.extract_inquiry(CONTRADICTION)
    assert result.status == "success"
    assert result.draft == contradiction
    assert result.draft.requested_total == 30
    assert (result.draft.size_s, result.draft.size_m, result.draft.size_l) == (10, 10, 5)
    assert result.draft.deadline_raw == "September 28" and result.draft.deadline_iso is None
    assert validate_order(result.draft)
    request = client.open.call_args.args[0]
    body = json.loads(request.data)
    assert body["messages"] == [{"role": "user", "content": CONTRADICTION}]
    assert body["system"] == extraction.INSTRUCTIONS
    assert CONTRADICTION not in body["system"]
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert body["model"] == "explicit-test-model"
    assert body["max_tokens"] == 2048
    assert constructor.call_count == client.open.call_count == 1


def test_missing_total_and_explicit_zero_stay_unchanged_after_extraction(monkeypatch, valid):
    valid.requested_total = None
    valid.size_l = 0
    fake_transport(monkeypatch, draft=valid)
    draft = extraction.extract_inquiry("10 small, 10 medium, zero large, blue, 2026-10-28").draft
    assert draft.requested_total is None
    assert (draft.size_s, draft.size_m, draft.size_l) == (10, 10, 0)
    assert computed_total(draft) == 20
    assert validate_order(draft)


def mocked_http_response(request, body, *, code=200, headers=None):
    response = addinfourl(BytesIO(json.dumps(body).encode()), headers or {}, request.full_url, code=code)
    response.msg = "Offline response"
    return response


def test_real_http_serialization_and_parsing_use_one_mock_request(monkeypatch, contradiction):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "offline-test-key")
    monkeypatch.setenv("MODEL_ID", "explicit-test-model")
    requests = []

    def respond(handler, request):
        requests.append(request)
        return mocked_http_response(request, response_for(contradiction))

    monkeypatch.setattr(HTTPSHandler, "https_open", respond)
    monkeypatch.setattr(extraction, "build_opener", build_opener)
    result = extraction.extract_inquiry(CONTRADICTION)
    assert result.status == "success" and result.draft == contradiction
    assert len(requests) == 1
    request = requests[0]
    assert request.full_url == "https://api.anthropic.com/v1/messages"
    assert request.get_method() == "POST"
    assert request.get_header("X-api-key") == "offline-test-key"
    assert request.get_header("Anthropic-version") == "2023-06-01"
    assert request.get_header("Content-type") == "application/json"
    body = json.loads(request.data)
    assert body["messages"][0]["content"] == CONTRADICTION
    schema = body["output_config"]["format"]["schema"]
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(OrderDraft.model_fields)
    assert request.timeout == 30.0


@pytest.mark.parametrize("code", [301, 302, 303, 307, 308, 401, 429, 500])
def test_real_http_transport_never_redirects_or_retries(monkeypatch, code):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "offline-test-key")
    monkeypatch.setenv("MODEL_ID", "explicit-test-model")
    requests = []

    def respond(handler, request):
        requests.append(request)
        return mocked_http_response(request, {"error": "private provider body"}, code=code,
                                    headers={"Location": "https://other-host.invalid/collect"})

    monkeypatch.setattr(HTTPSHandler, "https_open", respond)
    monkeypatch.setattr(extraction, "build_opener", build_opener)
    result = extraction.extract_inquiry(INQUIRY_B)
    assert result.status == "error" and result.message == extraction.ERROR_MESSAGE
    assert len(requests) == 1
    assert requests[0].full_url == "https://api.anthropic.com/v1/messages"


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


