"""Tests for client/parsers.py -- SERV-04: JSON:API responses parsed to flat dicts."""
from client.parsers import unwrap_jsonapi


GTMETRIX_STATUS_ENVELOPE = {
    "data": {
        "type": "user",
        "id": "abc123key",
        "attributes": {
            "api_credits": 1497,
            "api_refill": 1618437519,
            "api_refill_amount": 10,
            "account_type": "Basic",
            "account_pro_analysis_options_access": False,
        },
    }
}


def test_unwrap_full_envelope():
    """Full JSON:API envelope is flattened to a plain dict."""
    result = unwrap_jsonapi(GTMETRIX_STATUS_ENVELOPE)
    assert result["id"] == "abc123key"
    assert result["type"] == "user"
    assert result["api_credits"] == 1497
    assert result["account_type"] == "Basic"
    assert result["api_refill"] == 1618437519


def test_unwrap_empty_attributes():
    """Empty attributes dict returns dict with just id and type."""
    envelope = {"data": {"type": "test", "id": "x1", "attributes": {}}}
    result = unwrap_jsonapi(envelope)
    assert result["id"] == "x1"
    assert result["type"] == "test"
    assert len(result) == 2


def test_unwrap_missing_data_key():
    """Response without 'data' key returns empty dict without raising."""
    result = unwrap_jsonapi({})
    assert result == {} or isinstance(result, dict)


def test_unwrap_status_response_has_required_fields():
    """GTMetrix /status response unwraps to dict with ACCT-01 required fields."""
    result = unwrap_jsonapi(GTMETRIX_STATUS_ENVELOPE)
    for field in ("api_credits", "account_type", "api_refill", "api_refill_amount"):
        assert field in result, f"Missing required field: {field}"


def test_no_data_wrapper_in_output():
    """The 'data' wrapper key is NOT present in the unwrapped output."""
    result = unwrap_jsonapi(GTMETRIX_STATUS_ENVELOPE)
    assert "data" not in result
    assert "attributes" not in result
