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


# --- Phase 2: Test lifecycle methods ---

from tests.conftest import (
    MOCK_TEST_RESPONSE,
    MOCK_TEST_COMPLETED_RESPONSE,
    MOCK_REPORT_RESPONSE,
    MOCK_LIGHTHOUSE_RESPONSE,
    MOCK_LOCATIONS_RESPONSE,
)
import json


@pytest.mark.asyncio
async def test_start_test():
    """start_test() sends POST /tests with JSON:API body and returns unwrapped dict."""
    captured_request = {}

    with patch("client.gtmetrix.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value = mock_http
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_TEST_RESPONSE
        mock_response.raise_for_status = MagicMock()

        async def capture_post(url, **kwargs):
            captured_request["url"] = url
            captured_request["json"] = kwargs.get("json")
            return mock_response

        mock_http.post = AsyncMock(side_effect=capture_post)

        async with GTMetrixClient(api_key="test_key") as client:
            result = await client.start_test("https://example.com")

        # Verify correct endpoint and JSON:API body
        assert captured_request["url"] == "/tests"
        body = captured_request["json"]
        assert body["data"]["type"] == "test"
        assert body["data"]["attributes"]["url"] == "https://example.com"

        # Verify unwrapped result
        assert result["id"] == "KtbMoPEq"
        assert result["state"] == "queued"
        assert "credits_left" in result


@pytest.mark.asyncio
async def test_get_test():
    """get_test() sends GET /tests/{id} and returns unwrapped dict."""
    with patch("client.gtmetrix.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value = mock_http
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_TEST_COMPLETED_RESPONSE
        mock_response.raise_for_status = MagicMock()
        mock_http.get = AsyncMock(return_value=mock_response)

        async with GTMetrixClient(api_key="test_key") as client:
            result = await client.get_test("KtbMoPEq")

        mock_http.get.assert_called_once_with("/tests/KtbMoPEq")
        assert result["id"] == "KtbMoPEq"
        assert result["type"] == "test"


@pytest.mark.asyncio
async def test_get_report():
    """get_report() sends GET /reports/{id} and returns unwrapped dict with CWV fields."""
    with patch("client.gtmetrix.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value = mock_http
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_REPORT_RESPONSE
        mock_response.raise_for_status = MagicMock()
        mock_http.get = AsyncMock(return_value=mock_response)

        async with GTMetrixClient(api_key="test_key") as client:
            result = await client.get_report("KtbMoPEq")

        mock_http.get.assert_called_once_with("/reports/KtbMoPEq")
        assert result["performance_score"] == 85
        assert result["structure_score"] == 72
        assert result["largest_contentful_paint"] == 1200
        assert result["total_blocking_time"] == 150
        assert result["cumulative_layout_shift"] == 0.05


@pytest.mark.asyncio
async def test_get_resource():
    """get_resource() sends GET /reports/{id}/resources/{name} and returns raw JSON."""
    with patch("client.gtmetrix.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value = mock_http
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_LIGHTHOUSE_RESPONSE
        mock_response.raise_for_status = MagicMock()
        mock_http.get = AsyncMock(return_value=mock_response)

        async with GTMetrixClient(api_key="test_key") as client:
            result = await client.get_resource("KtbMoPEq", "lighthouse")

        mock_http.get.assert_called_once_with("/reports/KtbMoPEq/resources/lighthouse")
        # Raw JSON, NOT unwrapped -- should have "audits" key directly
        assert "audits" in result
        assert "id" not in result  # Not unwrapped


@pytest.mark.asyncio
async def test_start_test_http_error():
    """start_test() raises HTTPStatusError on non-2xx response."""
    with patch("client.gtmetrix.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value = mock_http
        mock_response = MagicMock()
        request = MagicMock(spec=httpx.Request)
        request.url = "https://gtmetrix.com/api/2.0/tests"
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "402 Payment Required", request=request, response=mock_response
            )
        )
        mock_http.post = AsyncMock(return_value=mock_response)

        async with GTMetrixClient(api_key="test_key") as client:
            with pytest.raises(httpx.HTTPStatusError):
                await client.start_test("https://example.com")


# --- Phase 3: Location and test parameter tests ---


@pytest.mark.asyncio
async def test_list_locations():
    """list_locations() returns flat list of location dicts from JSON:API response."""
    with patch("client.gtmetrix.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value = mock_http
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_LOCATIONS_RESPONSE
        mock_response.raise_for_status = MagicMock()
        mock_http.get = AsyncMock(return_value=mock_response)

        async with GTMetrixClient(api_key="test_key") as client:
            result = await client.list_locations()

        assert len(result) == 3
        assert result[0]["id"] == "1"
        assert result[0]["name"] == "Vancouver, Canada"
        mock_http.get.assert_called_once_with("/locations")


@pytest.mark.asyncio
async def test_list_locations_cached():
    """list_locations() caches result; second call does not make another HTTP request."""
    with patch("client.gtmetrix.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value = mock_http
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_LOCATIONS_RESPONSE
        mock_response.raise_for_status = MagicMock()
        mock_http.get = AsyncMock(return_value=mock_response)

        async with GTMetrixClient(api_key="test_key") as client:
            result1 = await client.list_locations()
            result2 = await client.list_locations()

        assert result1 == result2
        assert mock_http.get.call_count == 1


@pytest.mark.asyncio
async def test_start_test_with_location():
    """start_test() with location parameter includes location in JSON:API body."""
    captured_request = {}

    with patch("client.gtmetrix.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value = mock_http
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_TEST_RESPONSE
        mock_response.raise_for_status = MagicMock()

        async def capture_post(url, **kwargs):
            captured_request["url"] = url
            captured_request["json"] = kwargs.get("json")
            return mock_response

        mock_http.post = AsyncMock(side_effect=capture_post)

        async with GTMetrixClient(api_key="test_key") as client:
            await client.start_test("https://example.com", location="2")

    body = captured_request["json"]
    assert body["data"]["attributes"]["url"] == "https://example.com"
    assert body["data"]["attributes"]["location"] == "2"


@pytest.mark.asyncio
async def test_start_test_without_location():
    """start_test() without location parameter does not include location in body."""
    captured_request = {}

    with patch("client.gtmetrix.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value = mock_http
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_TEST_RESPONSE
        mock_response.raise_for_status = MagicMock()

        async def capture_post(url, **kwargs):
            captured_request["url"] = url
            captured_request["json"] = kwargs.get("json")
            return mock_response

        mock_http.post = AsyncMock(side_effect=capture_post)

        async with GTMetrixClient(api_key="test_key") as client:
            await client.start_test("https://example.com")

    body = captured_request["json"]
    assert body["data"]["attributes"]["url"] == "https://example.com"
    assert "location" not in body["data"]["attributes"]


# --- Phase 4: New start_test parameters ---


@pytest.mark.asyncio
async def test_start_test_with_browser():
    """start_test(url, browser='3') includes browser in attributes."""
    captured_request = {}

    with patch("client.gtmetrix.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value = mock_http
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_TEST_RESPONSE
        mock_response.raise_for_status = MagicMock()

        async def capture_post(url, **kwargs):
            captured_request["json"] = kwargs.get("json")
            return mock_response

        mock_http.post = AsyncMock(side_effect=capture_post)

        async with GTMetrixClient(api_key="test_key") as client:
            await client.start_test("https://example.com", browser="3")

    attrs = captured_request["json"]["data"]["attributes"]
    assert attrs["browser"] == "3"


@pytest.mark.asyncio
async def test_start_test_with_adblock():
    """start_test(url, adblock=1) includes adblock in attributes."""
    captured_request = {}

    with patch("client.gtmetrix.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value = mock_http
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_TEST_RESPONSE
        mock_response.raise_for_status = MagicMock()

        async def capture_post(url, **kwargs):
            captured_request["json"] = kwargs.get("json")
            return mock_response

        mock_http.post = AsyncMock(side_effect=capture_post)

        async with GTMetrixClient(api_key="test_key") as client:
            await client.start_test("https://example.com", adblock=1)

    attrs = captured_request["json"]["data"]["attributes"]
    assert attrs["adblock"] == 1


@pytest.mark.asyncio
async def test_start_test_with_simulate_device():
    """start_test(url, simulate_device='iphone_16') includes simulate_device in attributes."""
    captured_request = {}

    with patch("client.gtmetrix.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value = mock_http
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_TEST_RESPONSE
        mock_response.raise_for_status = MagicMock()

        async def capture_post(url, **kwargs):
            captured_request["json"] = kwargs.get("json")
            return mock_response

        mock_http.post = AsyncMock(side_effect=capture_post)

        async with GTMetrixClient(api_key="test_key") as client:
            await client.start_test("https://example.com", simulate_device="iphone_16")

    attrs = captured_request["json"]["data"]["attributes"]
    assert attrs["simulate_device"] == "iphone_16"


@pytest.mark.asyncio
async def test_start_test_omits_none_params():
    """Params that are None are NOT included in attributes dict."""
    captured_request = {}

    with patch("client.gtmetrix.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value = mock_http
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_TEST_RESPONSE
        mock_response.raise_for_status = MagicMock()

        async def capture_post(url, **kwargs):
            captured_request["json"] = kwargs.get("json")
            return mock_response

        mock_http.post = AsyncMock(side_effect=capture_post)

        async with GTMetrixClient(api_key="test_key") as client:
            await client.start_test("https://example.com", browser=None, adblock=None, simulate_device=None)

    attrs = captured_request["json"]["data"]["attributes"]
    assert "browser" not in attrs
    assert "adblock" not in attrs
    assert "simulate_device" not in attrs
