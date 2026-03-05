"""GTMetrix analyze orchestrator tool.

Provides gtmetrix_analyze(url) MCP tool which runs the full workflow:
start test -> poll until complete -> fetch report + lighthouse + HAR ->
parse and return a combined performance dict.
"""
import asyncio
import logging
import time

import httpx

from client.parsers import extract_top_resources, extract_vitals, filter_failing_audits

logger = logging.getLogger(__name__)

POLL_INTERVAL = 3  # seconds between poll requests
DEFAULT_TIMEOUT = 300  # 5 minutes hard timeout

DEVICE_ALIASES = {
    "phone": "iphone_16",
    "tablet": "ipad_air",
    "desktop": None,  # No simulate_device = desktop (default)
}


def resolve_device(device_input: str | None) -> str | None:
    """Resolve a device alias to a GTMetrix device ID, or pass through raw IDs."""
    if device_input is None:
        return None
    if device_input.lower() in DEVICE_ALIASES:
        return DEVICE_ALIASES[device_input.lower()]
    return device_input  # Raw GTMetrix device ID passthrough


async def _analyze_impl(
    client,
    url: str,
    *,
    location: str | None = None,
    browser: str | None = None,
    device: str | None = None,
    adblock: str | None = None,
    config=None,
) -> dict:
    """Core logic for gtmetrix_analyze. Accepts a GTMetrixClient instance.

    Orchestrates: start_test -> poll get_test -> fetch report/lighthouse/HAR ->
    parse vitals, failing audits, top resources -> return combined dict.

    Separated from the MCP decorator for testability.
    """
    try:
        # Resolve defaults from config
        from config import settings as default_settings
        cfg = config or default_settings
        effective_location = location if location is not None else cfg.gtmetrix_default_location
        effective_browser = browser if browser is not None else cfg.gtmetrix_default_browser
        effective_device = device if device is not None else cfg.gtmetrix_default_device
        effective_adblock = adblock if adblock is not None else cfg.gtmetrix_default_adblock

        # Validate location if provided
        if effective_location is not None:
            effective_location = str(effective_location)  # Coerce int to string
            locations = await client.list_locations()
            valid_ids = {loc["id"] for loc in locations}
            if effective_location not in valid_ids:
                accessible = [
                    {"id": loc["id"], "name": loc.get("name", ""), "region": loc.get("region", "")}
                    for loc in locations
                    if loc.get("account_has_access", False)
                ]
                return {
                    "error": f"Invalid location: '{effective_location}'",
                    "hint": "Use one of the available location IDs listed below, or call gtmetrix_list_locations() to see all options",
                    "available_locations": accessible,
                }
        resolved_device = resolve_device(effective_device)
        adblock_int = int(effective_adblock) if effective_adblock is not None else None

        # Start the test
        test = await client.start_test(
            url,
            location=effective_location,
            browser=effective_browser,
            adblock=adblock_int,
            simulate_device=resolved_device,
        )
        test_id = test.get("id")
        if not test_id:
            return {
                "error": "GTMetrix did not return a test ID",
                "hint": "The API response was unexpected. Try again.",
            }

        # Poll until completion or timeout
        deadline = time.monotonic() + DEFAULT_TIMEOUT
        report = None
        report_id = None

        while time.monotonic() < deadline:
            result = await client.get_test(test_id)

            # 303 redirect was followed — response is the report itself
            if result.get("type") == "report":
                report = result
                report_id = result["id"]
                break

            state = result.get("state")

            if state == "completed":
                report_id = test_id
                report = await client.get_report(report_id)
                break

            if state == "error":
                error_msg = result.get("error", "Unknown test error")
                return {
                    "error": f"GTMetrix test failed: {error_msg}",
                    "hint": "Check that the URL is reachable and publicly accessible.",
                }

            # Still running — wait and poll again
            await asyncio.sleep(POLL_INTERVAL)
        else:
            # Loop completed without break — timeout
            return {
                "error": "GTMetrix test timed out after 5 minutes",
                "hint": "The test did not complete in time. Try again or check the URL.",
            }

        # Fetch sub-resources
        lighthouse_json = await client.get_resource(report_id, "lighthouse")
        har_json = await client.get_resource(report_id, "har")

        # Parse
        vitals = extract_vitals(report)
        failing_audits = filter_failing_audits(lighthouse_json)
        top_resources = extract_top_resources(har_json)

        return {
            "url": url,
            "test_id": test_id,
            "report_id": report_id,
            **vitals,
            "failing_audits": failing_audits,
            "top_resources": top_resources,
        }

    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status == 402:
            return {
                "error": "GTMetrix API credits exhausted",
                "hint": "Use gtmetrix_check_status() to see when credits refill.",
            }
        if status == 429:
            return {
                "error": "GTMetrix concurrent test limit reached",
                "hint": "Wait for your current test to finish before starting another.",
            }
        logger.error("GTMetrix analyze HTTP error: %s %s", status, exc)
        return {
            "error": f"GTMetrix API error (HTTP {status})",
            "hint": "Check your API key and try again.",
            "detail": str(exc),
        }
    except Exception as exc:
        logger.error("GTMetrix analyze failed: %s", exc, exc_info=True)
        return {
            "error": "GTMetrix analysis failed unexpectedly",
            "hint": "Check server logs for details.",
            "detail": str(exc),
        }


async def _list_locations_impl(client) -> dict:
    """Core logic for gtmetrix_list_locations. Accepts a GTMetrixClient instance."""
    try:
        locations = await client.list_locations()
        accessible = [
            {"id": loc["id"], "name": loc.get("name", ""), "region": loc.get("region", "")}
            for loc in locations
            if loc.get("account_has_access", False)
        ]
        return {"locations": accessible, "count": len(accessible)}
    except httpx.HTTPStatusError as exc:
        return {"error": "Failed to fetch locations", "hint": f"HTTP {exc.response.status_code}"}
    except Exception as exc:
        return {"error": "Failed to fetch locations", "detail": str(exc)}


def register(mcp) -> None:
    """Register analyze tools with the FastMCP server instance."""
    from mcp.server.fastmcp import Context

    @mcp.tool()
    async def gtmetrix_analyze(
        url: str,
        location: str | None = None,
        browser: str | None = None,
        device: str | None = None,
        adblock: str | None = None,
        *, ctx: Context,
    ) -> dict:
        """Analyze a URL's web performance with GTMetrix.

        Starts a GTMetrix test, waits for completion (polling every 3s, 5-minute
        timeout), then fetches and parses the report, Lighthouse audits, and HAR
        resource timing.

        Args:
            url: The URL to analyze.
            location: Optional location ID to run the test from. Use
                gtmetrix_list_locations() to discover available IDs.
            browser: Optional browser ID (e.g. "1" for Chrome, "3" for Firefox).
            device: Optional device alias ("phone", "tablet", "desktop") or raw
                GTMetrix device ID (e.g. "iphone_16", "samsung_s24"). Simulated
                devices require a PRO account.
            adblock: Optional adblock flag ("0" to disable, "1" to enable).

        Returns a single dict with:
        - Core Web Vitals (performance_score, LCP, TBT, CLS)
        - Failing Lighthouse audits with scores and descriptions
        - Top 10 slowest resources with sizes and durations

        Use gtmetrix_check_status() first to verify you have API credits.
        """
        client = ctx.request_context.lifespan_context["client"]
        return await _analyze_impl(
            client, url,
            location=location,
            browser=browser,
            device=device,
            adblock=adblock,
        )

    @mcp.tool()
    async def gtmetrix_list_locations(ctx: Context) -> dict:
        """List available GTMetrix test locations.

        Returns location IDs, names, and regions. Use the ID when specifying
        a location in gtmetrix_analyze(). Only locations accessible to your
        account are included.
        """
        client = ctx.request_context.lifespan_context["client"]
        return await _list_locations_impl(client)
