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

# --- Phase 2 mock responses ---

MOCK_TEST_RESPONSE = {
    "data": {
        "type": "test",
        "id": "KtbMoPEq",
        "attributes": {
            "source": "api",
            "state": "queued",
            "created": 1617680457,
        },
    },
    "meta": {
        "credits_left": 121.2,
        "credits_used": 2.8,
    },
}

MOCK_TEST_COMPLETED_RESPONSE = {
    "data": {
        "type": "test",
        "id": "KtbMoPEq",
        "attributes": {
            "source": "api",
            "state": "completed",
            "created": 1617680457,
        },
        "links": {
            "report": "/api/2.0/reports/KtbMoPEq",
        },
    },
}

MOCK_REPORT_RESPONSE = {
    "data": {
        "type": "report",
        "id": "KtbMoPEq",
        "attributes": {
            "performance_score": 85,
            "structure_score": 72,
            "largest_contentful_paint": 1200,
            "total_blocking_time": 150,
            "cumulative_layout_shift": 0.05,
            "first_contentful_paint": 800,
            "speed_index": 1500,
        },
    },
}

MOCK_LIGHTHOUSE_RESPONSE = {
    "audits": {
        "first-contentful-paint": {
            "id": "first-contentful-paint",
            "title": "First Contentful Paint",
            "description": "First Contentful Paint marks the time...",
            "score": 1,
            "scoreDisplayMode": "numeric",
            "displayValue": "0.8 s",
        },
        "largest-contentful-paint": {
            "id": "largest-contentful-paint",
            "title": "Largest Contentful Paint",
            "description": "Largest Contentful Paint marks the time...",
            "score": 0.45,
            "scoreDisplayMode": "numeric",
            "displayValue": "3,200 ms",
        },
        "uses-responsive-images": {
            "id": "uses-responsive-images",
            "title": "Properly size images",
            "description": "Serve images that are appropriately-sized...",
            "score": None,
            "scoreDisplayMode": "notApplicable",
        },
    },
}

MOCK_HAR_RESPONSE = {
    "log": {
        "version": "1.2",
        "entries": [
            {
                "request": {"url": f"https://example.com/resource-{i}.js", "method": "GET"},
                "response": {
                    "status": 200,
                    "_transferSize": 5000 + i * 1000,
                    "bodySize": 4500 + i * 1000,
                },
                "time": 100.0 + i * 50,
            }
            for i in range(1, 12)
        ]
        + [
            # Entry with time=0 (cached resource)
            {
                "request": {"url": "https://example.com/cached.js", "method": "GET"},
                "response": {"status": 200, "_transferSize": 1000, "bodySize": 900},
                "time": 0,
            },
            # Entry missing _transferSize
            {
                "request": {"url": "https://example.com/no-transfer-size.js", "method": "GET"},
                "response": {"status": 200, "bodySize": 3200},
                "time": 250.0,
            },
        ],
    },
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
