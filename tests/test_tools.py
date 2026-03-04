"""Tests for tools/account.py — SERV-05 (structured errors) and ACCT-01 (status data)."""
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock


# We test the tool logic directly by calling the inner function,
# bypassing FastMCP's decorator to keep tests fast and dependency-free.
# The register() function is tested for importability only.


async def _call_check_status(mock_client):
    """Helper: simulate what the MCP framework does when a tool is called."""
    # Import the logic function directly from the module
    from tools.account import _check_status_impl
    return await _check_status_impl(mock_client)


@pytest.fixture
def success_client():
    client = AsyncMock()
    client.get_status = AsyncMock(return_value={
        "id": "test_key",
        "type": "user",
        "api_credits": 1497,
        "api_refill": 1618437519,
        "api_refill_amount": 10,
        "account_type": "Basic",
    })
    return client


@pytest.fixture
def http_error_client():
    client = AsyncMock()
    request = MagicMock(spec=httpx.Request)
    request.url = "https://gtmetrix.com/api/2.0/status"
    response = MagicMock(spec=httpx.Response)
    response.status_code = 401
    client.get_status = AsyncMock(
        side_effect=httpx.HTTPStatusError("401 Unauthorized", request=request, response=response)
    )
    return client


@pytest.fixture
def generic_error_client():
    client = AsyncMock()
    client.get_status = AsyncMock(side_effect=Exception("Connection refused"))
    return client


@pytest.mark.asyncio
async def test_check_status_success_returns_required_fields(success_client):
    """Successful status check returns api_credits, account_type, api_refill_timestamp."""
    result = await _call_check_status(success_client)
    assert result["api_credits"] == 1497
    assert result["account_type"] == "Basic"
    assert result["api_refill_timestamp"] == 1618437519
    assert result["api_refill_amount"] == 10


@pytest.mark.asyncio
async def test_check_status_success_has_no_error_key(success_client):
    """Successful result does not contain an 'error' key."""
    result = await _call_check_status(success_client)
    assert "error" not in result


@pytest.mark.asyncio
async def test_check_status_raw_timestamp_not_formatted(success_client):
    """api_refill_timestamp is returned as raw Unix integer, not ISO string."""
    result = await _call_check_status(success_client)
    assert isinstance(result["api_refill_timestamp"], int)


@pytest.mark.asyncio
async def test_check_status_http_error_returns_structured_dict(http_error_client):
    """HTTP error returns structured dict with 'error' and 'hint', does not raise."""
    result = await _call_check_status(http_error_client)
    assert "error" in result
    assert "hint" in result
    assert "api_credits" not in result


@pytest.mark.asyncio
async def test_check_status_generic_error_returns_detail(generic_error_client):
    """Generic exception returns 'error', 'hint', and 'detail' keys."""
    result = await _call_check_status(generic_error_client)
    assert "error" in result
    assert "hint" in result
    assert "detail" in result


def test_register_is_importable():
    """tools.account.register is callable without error when imported."""
    from tools.account import register
    assert callable(register)
