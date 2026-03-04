"""GTMetrix account status tool.

Provides gtmetrix_check_status() MCP tool which returns API credits
remaining, account type, and credit refill date.
"""
import logging
import httpx

logger = logging.getLogger(__name__)


async def _check_status_impl(client) -> dict:
    """Core logic for gtmetrix_check_status. Accepts a GTMetrixClient instance.

    Separated from the MCP decorator for testability.
    """
    try:
        status = await client.get_status()
        return {
            "api_credits": status.get("api_credits"),
            "account_type": status.get("account_type"),
            "api_refill_timestamp": status.get("api_refill"),
            "api_refill_amount": status.get("api_refill_amount"),
        }
    except httpx.HTTPStatusError as exc:
        logger.error("GTMetrix status HTTP error: %s %s", exc.response.status_code, exc)
        return {
            "error": "Failed to fetch GTMetrix account status",
            "hint": (
                "Verify GTMETRIX_API_KEY in your .env file is correct. "
                f"HTTP {exc.response.status_code} received."
            ),
        }
    except Exception as exc:
        logger.error("GTMetrix status check failed: %s", exc, exc_info=True)
        return {
            "error": "Failed to fetch GTMetrix account status",
            "hint": "Verify GTMETRIX_API_KEY in .env and that the GTMetrix API is reachable",
            "detail": str(exc),
        }


def register(mcp) -> None:
    """Register account tools with the FastMCP server instance."""
    from mcp.server.fastmcp import Context

    @mcp.tool()
    async def gtmetrix_check_status(ctx: Context) -> dict:
        """Check GTMetrix account status.

        Returns API credits remaining, account type, and next credit refill date.
        Use this before running tests to verify your API key is valid and you have
        sufficient credits.
        """
        client = ctx.request_context.lifespan_context["client"]
        return await _check_status_impl(client)
