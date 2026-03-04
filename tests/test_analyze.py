"""Tests for the gtmetrix_analyze orchestrator tool."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from tests.conftest import (
    MOCK_HAR_RESPONSE,
    MOCK_LIGHTHOUSE_RESPONSE,
    MOCK_REPORT_RESPONSE,
)
from client.parsers import unwrap_jsonapi


# Pre-unwrapped report for use in tests
UNWRAPPED_REPORT = unwrap_jsonapi(MOCK_REPORT_RESPONSE)


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
