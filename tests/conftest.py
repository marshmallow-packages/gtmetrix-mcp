"""Shared pytest fixtures for gtmetrix-mcp-server tests."""

import pytest
from unittest.mock import AsyncMock, MagicMock

import httpx


MOCK_STATUS_RESPONSE = {
    "id": "test_api_key",
    "type": "user",
    "api_credits": 1497,
    "api_refill": 1618437519,
    "api_refill_amount": 10,
    "account_type": "Basic",
    "account_pro_analysis_options_access": False,
    "account_pro_locations_access": False,
    "account_whitelabel_pdf_access": False,
}


@pytest.fixture
def mock_client():
    """GTMetrixClient mock that returns a successful status response."""
    client = AsyncMock()
    client.get_status = AsyncMock(return_value=MOCK_STATUS_RESPONSE)
    return client


@pytest.fixture
def error_client():
    """GTMetrixClient mock that raises an HTTP 401 error on get_status."""
    client = AsyncMock()
    request = MagicMock(spec=httpx.Request)
    request.url = "https://gtmetrix.com/api/2.0/status"
    response = MagicMock(spec=httpx.Response)
    response.status_code = 401
    response.text = "Unauthorized"
    client.get_status = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            "401 Unauthorized", request=request, response=response
        )
    )
    return client
