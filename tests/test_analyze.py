"""Tests for the gtmetrix_analyze orchestrator tool."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from tests.conftest import (
    MOCK_HAR_RESPONSE,
    MOCK_LIGHTHOUSE_RESPONSE,
    MOCK_LOCATIONS_RESPONSE,
    MOCK_REPORT_RESPONSE,
)
from client.parsers import unwrap_jsonapi, unwrap_jsonapi_list


# Pre-unwrapped report for use in tests
UNWRAPPED_REPORT = unwrap_jsonapi(MOCK_REPORT_RESPONSE)

# Pre-unwrapped locations for use in tests
UNWRAPPED_LOCATIONS = unwrap_jsonapi_list(MOCK_LOCATIONS_RESPONSE)


def _make_client(**overrides):
    """Build an AsyncMock GTMetrixClient with sensible defaults for the happy path."""
    client = AsyncMock()
    client.start_test = AsyncMock(
        return_value=overrides.get(
            "start_test", {"id": "T1", "type": "test", "state": "queued"}
        )
    )
    client.get_test = overrides.get(
        "get_test",
        AsyncMock(return_value={"type": "test", "state": "completed", "id": "T1"}),
    )
    client.get_report = AsyncMock(return_value=overrides.get("get_report", UNWRAPPED_REPORT))
    client.get_resource = AsyncMock(
        side_effect=overrides.get(
            "get_resource_side_effect",
            lambda rid, name: MOCK_LIGHTHOUSE_RESPONSE if name == "lighthouse" else MOCK_HAR_RESPONSE,
        )
    )
    return client


def _noop_sleep(_seconds):
    """Replacement for asyncio.sleep that returns immediately."""
    f = asyncio.Future()
    f.set_result(None)
    return f


@pytest.mark.asyncio
async def test_analyze_full_flow():
    """Happy path: start -> poll (immediate complete) -> fetch -> parse -> combined dict."""
    from tools.analyze import _analyze_impl

    client = _make_client()

    with patch("tools.analyze.asyncio.sleep", new=_noop_sleep):
        result = await _analyze_impl(client, "https://example.com")

    assert result["url"] == "https://example.com"
    assert result["test_id"] == "T1"
    assert result["report_id"] == "T1"
    assert result["performance_score"] == 85
    assert result["structure_score"] == 72
    assert result["largest_contentful_paint_ms"] == 1200
    assert result["total_blocking_time_ms"] == 150
    assert result["cumulative_layout_shift"] == 0.05
    assert isinstance(result["failing_audits"], list)
    assert isinstance(result["top_resources"], list)
    assert len(result["failing_audits"]) > 0  # LCP audit has score 0.45
    assert len(result["top_resources"]) > 0


@pytest.mark.asyncio
async def test_analyze_polls_until_complete():
    """Polls get_test multiple times before completing."""
    from tools.analyze import _analyze_impl

    get_test_mock = AsyncMock(
        side_effect=[
            {"type": "test", "state": "started", "id": "T1"},
            {"type": "test", "state": "started", "id": "T1"},
            {"type": "test", "state": "completed", "id": "T1"},
        ]
    )
    client = _make_client(get_test=get_test_mock)

    with patch("tools.analyze.asyncio.sleep", new=_noop_sleep):
        result = await _analyze_impl(client, "https://example.com")

    assert "error" not in result
    assert result["test_id"] == "T1"
    assert get_test_mock.call_count == 3


@pytest.mark.asyncio
async def test_analyze_redirect_to_report():
    """When get_test returns type='report', use it directly as the report."""
    from tools.analyze import _analyze_impl

    redirect_report = {**UNWRAPPED_REPORT, "type": "report", "id": "R1"}
    get_test_mock = AsyncMock(return_value=redirect_report)
    client = _make_client(get_test=get_test_mock)

    with patch("tools.analyze.asyncio.sleep", new=_noop_sleep):
        result = await _analyze_impl(client, "https://example.com")

    assert result["report_id"] == "R1"
    assert result["performance_score"] == 85
    # get_report should NOT have been called — the redirect gave us the report
    client.get_report.assert_not_called()


@pytest.mark.asyncio
async def test_analyze_timeout():
    """Returns error dict when polling exceeds timeout."""
    from tools.analyze import _analyze_impl

    get_test_mock = AsyncMock(
        return_value={"type": "test", "state": "started", "id": "T1"}
    )
    client = _make_client(get_test=get_test_mock)

    # Simulate time passing beyond deadline: first call returns 0, second returns 301
    monotonic_values = iter([0, 301])

    with (
        patch("tools.analyze.asyncio.sleep", new=_noop_sleep),
        patch("tools.analyze.time.monotonic", side_effect=lambda: next(monotonic_values)),
    ):
        result = await _analyze_impl(client, "https://example.com")

    assert "error" in result
    assert "timed out" in result["error"].lower() or "timeout" in result["error"].lower()


@pytest.mark.asyncio
async def test_analyze_test_error_state():
    """Returns error dict when test enters error state."""
    from tools.analyze import _analyze_impl

    get_test_mock = AsyncMock(
        return_value={"type": "test", "state": "error", "id": "T1", "error": "DNS failure"}
    )
    client = _make_client(get_test=get_test_mock)

    with patch("tools.analyze.asyncio.sleep", new=_noop_sleep):
        result = await _analyze_impl(client, "https://example.com")

    assert "error" in result
    assert "DNS failure" in result["error"]


@pytest.mark.asyncio
async def test_analyze_http_402():
    """Returns credits-exhausted error on HTTP 402."""
    from tools.analyze import _analyze_impl

    request = MagicMock(spec=httpx.Request)
    request.url = "https://gtmetrix.com/api/2.0/tests"
    response = MagicMock(spec=httpx.Response)
    response.status_code = 402

    client = _make_client()
    client.start_test = AsyncMock(
        side_effect=httpx.HTTPStatusError("402 Payment Required", request=request, response=response)
    )

    result = await _analyze_impl(client, "https://example.com")

    assert "error" in result
    assert "credit" in result["error"].lower()
    assert "hint" in result


@pytest.mark.asyncio
async def test_analyze_http_429():
    """Returns concurrent-limit error on HTTP 429."""
    from tools.analyze import _analyze_impl

    request = MagicMock(spec=httpx.Request)
    request.url = "https://gtmetrix.com/api/2.0/tests"
    response = MagicMock(spec=httpx.Response)
    response.status_code = 429

    client = _make_client()
    client.start_test = AsyncMock(
        side_effect=httpx.HTTPStatusError("429 Too Many Requests", request=request, response=response)
    )

    result = await _analyze_impl(client, "https://example.com")

    assert "error" in result
    assert "concurrent" in result["error"].lower() or "limit" in result["error"].lower()
    assert "hint" in result


@pytest.mark.asyncio
async def test_analyze_unexpected_error():
    """Returns generic error dict on unexpected exception."""
    from tools.analyze import _analyze_impl

    client = _make_client()
    client.start_test = AsyncMock(side_effect=RuntimeError("Something broke"))

    result = await _analyze_impl(client, "https://example.com")

    assert "error" in result
    assert "detail" in result
    assert "Something broke" in result["detail"]


# --- Location tests ---


def _make_location_client(**overrides):
    """Build an AsyncMock GTMetrixClient with location support for the happy path."""
    client = _make_client(**overrides)
    client.list_locations = AsyncMock(
        return_value=overrides.get("list_locations", UNWRAPPED_LOCATIONS)
    )
    return client


@pytest.mark.asyncio
async def test_analyze_with_location():
    """Passing location='2' sends it to start_test and completes normally."""
    from tools.analyze import _analyze_impl

    client = _make_location_client()

    with patch("tools.analyze.asyncio.sleep", new=_noop_sleep):
        result = await _analyze_impl(client, "https://example.com", location="2")

    assert "error" not in result
    assert result["url"] == "https://example.com"
    _, kwargs = client.start_test.call_args
    assert kwargs.get("location") == "2"


@pytest.mark.asyncio
async def test_analyze_invalid_location():
    """Invalid location returns error with accessible locations only (Mumbai filtered out)."""
    from tools.analyze import _analyze_impl

    client = _make_location_client()

    result = await _analyze_impl(client, "https://example.com", location="99")

    assert "error" in result
    assert "Invalid location" in result["error"]
    assert len(result["available_locations"]) == 2
    location_ids = [loc["id"] for loc in result["available_locations"]]
    assert "1" in location_ids
    assert "2" in location_ids
    assert "5" not in location_ids  # Mumbai not accessible
    client.start_test.assert_not_called()


@pytest.mark.asyncio
async def test_analyze_location_string_coercion():
    """Integer location=2 is coerced to string '2' and succeeds."""
    from tools.analyze import _analyze_impl

    client = _make_location_client()

    with patch("tools.analyze.asyncio.sleep", new=_noop_sleep):
        result = await _analyze_impl(client, "https://example.com", location=2)

    assert "error" not in result
    _, kwargs = client.start_test.call_args
    assert kwargs.get("location") == "2"


@pytest.mark.asyncio
async def test_list_locations_impl():
    """Returns only accessible locations with count."""
    from tools.analyze import _list_locations_impl

    client = AsyncMock()
    client.list_locations = AsyncMock(return_value=UNWRAPPED_LOCATIONS)

    result = await _list_locations_impl(client)

    assert result["count"] == 2
    assert len(result["locations"]) == 2
    location_ids = [loc["id"] for loc in result["locations"]]
    assert "1" in location_ids
    assert "2" in location_ids
    assert "5" not in location_ids  # Mumbai not accessible


@pytest.mark.asyncio
async def test_list_locations_impl_error():
    """Returns error dict when list_locations raises HTTPStatusError."""
    from tools.analyze import _list_locations_impl

    client = AsyncMock()
    request = MagicMock(spec=httpx.Request)
    request.url = "https://gtmetrix.com/api/2.0/locations"
    response = MagicMock(spec=httpx.Response)
    response.status_code = 500
    client.list_locations = AsyncMock(
        side_effect=httpx.HTTPStatusError("500 Server Error", request=request, response=response)
    )

    result = await _list_locations_impl(client)

    assert "error" in result
    assert "Failed to fetch locations" in result["error"]


# --- Phase 4: New parameters, device aliases, config defaults ---


def _make_param_client(**overrides):
    """Build an AsyncMock client for parameter tests (immediate completion, no sub-resources needed)."""
    client = AsyncMock()
    client.start_test = AsyncMock(
        return_value=overrides.get(
            "start_test", {"id": "T1", "type": "test", "state": "queued"}
        )
    )
    client.get_test = AsyncMock(
        return_value={"type": "test", "state": "completed", "id": "T1"}
    )
    client.get_report = AsyncMock(return_value=UNWRAPPED_REPORT)
    client.get_resource = AsyncMock(
        side_effect=lambda rid, name: MOCK_LIGHTHOUSE_RESPONSE if name == "lighthouse" else MOCK_HAR_RESPONSE
    )
    client.list_locations = AsyncMock(return_value=UNWRAPPED_LOCATIONS)
    return client


def _mock_config(**kwargs):
    """Create a mock config object with optional defaults."""
    from types import SimpleNamespace
    defaults = {
        "gtmetrix_default_location": None,
        "gtmetrix_default_browser": None,
        "gtmetrix_default_device": None,
        "gtmetrix_default_adblock": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


@pytest.mark.asyncio
async def test_analyze_with_browser():
    """_analyze_impl with browser='3' passes browser='3' to start_test."""
    from tools.analyze import _analyze_impl

    client = _make_param_client()
    cfg = _mock_config()

    with patch("tools.analyze.asyncio.sleep", new=_noop_sleep):
        result = await _analyze_impl(client, "https://example.com", browser="3", config=cfg)

    assert "error" not in result
    _, kwargs = client.start_test.call_args
    assert kwargs.get("browser") == "3"


@pytest.mark.asyncio
async def test_analyze_with_adblock():
    """_analyze_impl with adblock='1' passes adblock=1 (int) to start_test."""
    from tools.analyze import _analyze_impl

    client = _make_param_client()
    cfg = _mock_config()

    with patch("tools.analyze.asyncio.sleep", new=_noop_sleep):
        result = await _analyze_impl(client, "https://example.com", adblock="1", config=cfg)

    assert "error" not in result
    _, kwargs = client.start_test.call_args
    assert kwargs.get("adblock") == 1


@pytest.mark.asyncio
async def test_analyze_with_device_phone():
    """_analyze_impl with device='phone' resolves to simulate_device='iphone_16'."""
    from tools.analyze import _analyze_impl

    client = _make_param_client()
    cfg = _mock_config()

    with patch("tools.analyze.asyncio.sleep", new=_noop_sleep):
        result = await _analyze_impl(client, "https://example.com", device="phone", config=cfg)

    assert "error" not in result
    _, kwargs = client.start_test.call_args
    assert kwargs.get("simulate_device") == "iphone_16"


@pytest.mark.asyncio
async def test_analyze_with_device_tablet():
    """_analyze_impl with device='tablet' resolves to simulate_device='ipad_air'."""
    from tools.analyze import _analyze_impl

    client = _make_param_client()
    cfg = _mock_config()

    with patch("tools.analyze.asyncio.sleep", new=_noop_sleep):
        result = await _analyze_impl(client, "https://example.com", device="tablet", config=cfg)

    assert "error" not in result
    _, kwargs = client.start_test.call_args
    assert kwargs.get("simulate_device") == "ipad_air"


@pytest.mark.asyncio
async def test_analyze_with_device_desktop():
    """_analyze_impl with device='desktop' resolves to simulate_device=None (not sent)."""
    from tools.analyze import _analyze_impl

    client = _make_param_client()
    cfg = _mock_config()

    with patch("tools.analyze.asyncio.sleep", new=_noop_sleep):
        result = await _analyze_impl(client, "https://example.com", device="desktop", config=cfg)

    assert "error" not in result
    _, kwargs = client.start_test.call_args
    assert kwargs.get("simulate_device") is None


@pytest.mark.asyncio
async def test_analyze_with_device_raw_id():
    """_analyze_impl with device='samsung_s24' passes through as simulate_device='samsung_s24'."""
    from tools.analyze import _analyze_impl

    client = _make_param_client()
    cfg = _mock_config()

    with patch("tools.analyze.asyncio.sleep", new=_noop_sleep):
        result = await _analyze_impl(client, "https://example.com", device="samsung_s24", config=cfg)

    assert "error" not in result
    _, kwargs = client.start_test.call_args
    assert kwargs.get("simulate_device") == "samsung_s24"


@pytest.mark.asyncio
async def test_analyze_default_from_config():
    """When no explicit param but config has default, uses config value."""
    from tools.analyze import _analyze_impl

    client = _make_param_client()
    cfg = _mock_config(gtmetrix_default_browser="3", gtmetrix_default_adblock="1")

    with patch("tools.analyze.asyncio.sleep", new=_noop_sleep):
        result = await _analyze_impl(client, "https://example.com", config=cfg)

    assert "error" not in result
    _, kwargs = client.start_test.call_args
    assert kwargs.get("browser") == "3"
    assert kwargs.get("adblock") == 1


@pytest.mark.asyncio
async def test_analyze_explicit_overrides_config():
    """Explicit param takes precedence over config default."""
    from tools.analyze import _analyze_impl

    client = _make_param_client()
    cfg = _mock_config(gtmetrix_default_browser="1")

    with patch("tools.analyze.asyncio.sleep", new=_noop_sleep):
        result = await _analyze_impl(client, "https://example.com", browser="3", config=cfg)

    assert "error" not in result
    _, kwargs = client.start_test.call_args
    assert kwargs.get("browser") == "3"


@pytest.mark.asyncio
async def test_analyze_no_default_no_param():
    """When both None, param is not sent to start_test."""
    from tools.analyze import _analyze_impl

    client = _make_param_client()
    cfg = _mock_config()

    with patch("tools.analyze.asyncio.sleep", new=_noop_sleep):
        result = await _analyze_impl(client, "https://example.com", config=cfg)

    assert "error" not in result
    _, kwargs = client.start_test.call_args
    assert kwargs.get("browser") is None
    assert kwargs.get("adblock") is None
    assert kwargs.get("simulate_device") is None


@pytest.mark.asyncio
async def test_analyze_default_location_from_config():
    """When no explicit location param and config has gtmetrix_default_location='2', start_test is called with location='2'."""
    from tools.analyze import _analyze_impl

    client = _make_param_client()
    cfg = _mock_config(gtmetrix_default_location="2")

    with patch("tools.analyze.asyncio.sleep", new=_noop_sleep):
        result = await _analyze_impl(client, "https://example.com", config=cfg)

    assert "error" not in result
    _, kwargs = client.start_test.call_args
    assert kwargs.get("location") == "2"


@pytest.mark.asyncio
async def test_analyze_explicit_location_overrides_config_default():
    """Explicit location='1' overrides config default of '2'."""
    from tools.analyze import _analyze_impl

    client = _make_param_client()
    cfg = _mock_config(gtmetrix_default_location="2")

    with patch("tools.analyze.asyncio.sleep", new=_noop_sleep):
        result = await _analyze_impl(client, "https://example.com", location="1", config=cfg)

    assert "error" not in result
    _, kwargs = client.start_test.call_args
    assert kwargs.get("location") == "1"


@pytest.mark.asyncio
async def test_analyze_no_default_location_no_param():
    """When no explicit location and config has gtmetrix_default_location=None, no location sent."""
    from tools.analyze import _analyze_impl

    client = _make_param_client()
    cfg = _mock_config()

    with patch("tools.analyze.asyncio.sleep", new=_noop_sleep):
        result = await _analyze_impl(client, "https://example.com", config=cfg)

    assert "error" not in result
    _, kwargs = client.start_test.call_args
    assert kwargs.get("location") is None
