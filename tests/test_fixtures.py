"""Tests to verify shared fixtures work correctly."""

import httpx
import pytest


async def test_mock_client_returns_status(mock_client):
    """mock_client fixture should return a dict with expected keys."""
    result = await mock_client.get_status()
    assert isinstance(result, dict)
    assert "api_credits" in result
    assert "account_type" in result
    assert result["account_type"] == "Basic"


async def test_error_client_raises_401(error_client):
    """error_client fixture should raise HTTPStatusError with 401."""
    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await error_client.get_status()
    assert exc_info.value.response.status_code == 401
