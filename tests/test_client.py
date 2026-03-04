"""Tests for client/gtmetrix.py -- SERV-03 (async client) and SERV-05 partial."""
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch, call
from client.gtmetrix import GTMetrixClient, GTMETRIX_BASE_URL, JSONAPI_HEADERS


MOCK_STATUS_JSON = {
    "data": {
        "type": "user",
        "id": "test_key",
        "attributes": {
            "api_credits": 500,
            "api_refill": 1618437519,
            "api_refill_amount": 10,
            "account_type": "Basic",
            "account_pro_analysis_options_access": False,
            "account_pro_locations_access": False,
            "account_whitelabel_pdf_access": False,
        },
    }
}


@pytest.mark.asyncio
async def test_client_is_async_context_manager():
    """GTMetrixClient works as an async context manager without errors."""
    with patch("client.gtmetrix.httpx.AsyncClient") as mock_async_client_cls:
        mock_instance = AsyncMock()
        mock_async_client_cls.return_value = mock_instance
        async with GTMetrixClient(api_key="test_key") as client:
            assert client is not None
        mock_instance.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_get_status_returns_flat_dict():
    """get_status() returns a flat dict with api_credits and account_type."""
    with patch("client.gtmetrix.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value = mock_http
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_STATUS_JSON
        mock_response.raise_for_status = MagicMock()
        mock_http.get = AsyncMock(return_value=mock_response)

        async with GTMetrixClient(api_key="test_key") as client:
            status = await client.get_status()

        assert status["api_credits"] == 500
        assert status["account_type"] == "Basic"
        assert status["api_refill"] == 1618437519
        assert "data" not in status
        assert "attributes" not in status


@pytest.mark.asyncio
async def test_get_status_calls_correct_endpoint():
    """get_status() calls GET /status on the httpx client."""
    with patch("client.gtmetrix.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value = mock_http
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_STATUS_JSON
        mock_response.raise_for_status = MagicMock()
        mock_http.get = AsyncMock(return_value=mock_response)

        async with GTMetrixClient(api_key="test_key") as client:
            await client.get_status()

        mock_http.get.assert_called_once_with("/status")


@pytest.mark.asyncio
async def test_client_uses_basic_auth():
    """AsyncClient is constructed with HTTP Basic auth (api_key, '')."""
    with patch("client.gtmetrix.httpx.AsyncClient") as mock_cls:
        mock_instance = AsyncMock()
        mock_cls.return_value = mock_instance

        async with GTMetrixClient(api_key="my_secret_key") as client:
            pass

        _, kwargs = mock_cls.call_args
        assert kwargs.get("auth") == ("my_secret_key", "")


@pytest.mark.asyncio
async def test_client_sets_follow_redirects():
    """AsyncClient is constructed with follow_redirects=True."""
    with patch("client.gtmetrix.httpx.AsyncClient") as mock_cls:
        mock_instance = AsyncMock()
        mock_cls.return_value = mock_instance

        async with GTMetrixClient(api_key="key") as client:
            pass

        _, kwargs = mock_cls.call_args
        assert kwargs.get("follow_redirects") is True


def test_jsonapi_headers_content_type():
    """JSONAPI_HEADERS contains correct Content-Type and Accept for JSON:API."""
    assert JSONAPI_HEADERS["Content-Type"] == "application/vnd.api+json"
    assert JSONAPI_HEADERS["Accept"] == "application/vnd.api+json"
