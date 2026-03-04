"""GTMetrix API HTTP client.

Wraps httpx.AsyncClient with authentication, JSON:API headers, and
response parsing. Use as an async context manager -- never instantiate
AsyncClient per request.
"""
import logging
import httpx
from client.parsers import unwrap_jsonapi

logger = logging.getLogger(__name__)

GTMETRIX_BASE_URL = "https://gtmetrix.com/api/2.0"
JSONAPI_HEADERS = {
    "Content-Type": "application/vnd.api+json",
    "Accept": "application/vnd.api+json",
}


class GTMetrixClient:
    """Async HTTP client for the GTMetrix REST API v2.0.

    Use as an async context manager via FastMCP's lifespan pattern:
        async with GTMetrixClient(api_key=settings.gtmetrix_api_key) as client:
            yield {"client": client}
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "GTMetrixClient":
        self._client = httpx.AsyncClient(
            base_url=GTMETRIX_BASE_URL,
            auth=(self._api_key, ""),      # HTTP Basic: key as username, empty password
            headers=JSONAPI_HEADERS,
            follow_redirects=True,         # Required for Phase 2 303 redirects
            timeout=30.0,
        )
        return self

    async def __aexit__(self, *args) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get_status(self) -> dict:
        """Fetch GTMetrix account status.

        Returns a flat dict with api_credits, account_type, api_refill,
        api_refill_amount, and other account fields.

        Raises:
            httpx.HTTPStatusError: On non-2xx responses (tool layer catches this).
        """
        assert self._client is not None, "GTMetrixClient must be used as async context manager"
        response = await self._client.get("/status")
        response.raise_for_status()
        return unwrap_jsonapi(response.json())

    async def start_test(self, url: str) -> dict:
        """Start a new GTMetrix test for the given URL.

        Sends POST /tests with a JSON:API body. Returns unwrapped test data
        including 'id', 'state', and 'credits_left' from the meta block.

        Raises:
            httpx.HTTPStatusError: On non-2xx responses (e.g. 402 no credits).
        """
        assert self._client is not None, "GTMetrixClient must be used as async context manager"
        payload = {
            "data": {
                "type": "test",
                "attributes": {"url": url},
            }
        }
        response = await self._client.post("/tests", json=payload)
        response.raise_for_status()
        raw = response.json()
        result = unwrap_jsonapi(raw)
        # Include credits_left from meta block if present
        meta = raw.get("meta", {})
        if "credits_left" in meta:
            result["credits_left"] = meta["credits_left"]
        return result

    async def get_test(self, test_id: str) -> dict:
        """Get current test status.

        Returns unwrapped test or report data (type may be 'test' or 'report'
        if the 303 redirect to the report was followed).

        Raises:
            httpx.HTTPStatusError: On non-2xx responses.
        """
        assert self._client is not None, "GTMetrixClient must be used as async context manager"
        response = await self._client.get(f"/tests/{test_id}")
        response.raise_for_status()
        return unwrap_jsonapi(response.json())

    async def get_report(self, report_id: str) -> dict:
        """Fetch a completed report's data including Core Web Vitals.

        Returns unwrapped report dict with performance_score, structure_score,
        largest_contentful_paint, total_blocking_time, cumulative_layout_shift.

        Raises:
            httpx.HTTPStatusError: On non-2xx responses.
        """
        assert self._client is not None, "GTMetrixClient must be used as async context manager"
        response = await self._client.get(f"/reports/{report_id}")
        response.raise_for_status()
        return unwrap_jsonapi(response.json())

    async def get_resource(self, report_id: str, resource_name: str) -> dict:
        """Fetch a report sub-resource (lighthouse, har, etc.).

        Returns the raw JSON response directly -- sub-resources are NOT
        wrapped in JSON:API envelopes.

        Raises:
            httpx.HTTPStatusError: On non-2xx responses.
        """
        assert self._client is not None, "GTMetrixClient must be used as async context manager"
        response = await self._client.get(
            f"/reports/{report_id}/resources/{resource_name}"
        )
        response.raise_for_status()
        return response.json()
