"""GTMetrix MCP Server entry point.

CRITICAL: logging must be configured to stderr BEFORE any other imports.
Any print() or stdout write corrupts the stdio JSON-RPC stream.
"""
import logging
import sys

# Configure logging to stderr FIRST — before any other import that might emit output
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

logger = logging.getLogger(__name__)

from contextlib import asynccontextmanager  # noqa: E402
from mcp.server.fastmcp import FastMCP  # noqa: E402
from client.gtmetrix import GTMetrixClient  # noqa: E402
from config import get_settings  # noqa: E402
import tools.account as account_tools  # noqa: E402
import tools.analyze as analyze_tools  # noqa: E402


@asynccontextmanager
async def lifespan(server):
    """Manage GTMetrixClient lifecycle.

    Opens a single shared httpx.AsyncClient at startup and closes it on shutdown.
    All tools access the client via ctx.request_context.lifespan_context["client"].
    """
    logger.info("GTMetrix MCP server starting — connecting HTTP client")
    async with GTMetrixClient(api_key=get_settings().gtmetrix_api_key) as client:
        yield {"client": client}
    logger.info("GTMetrix MCP server stopped — HTTP client closed")


mcp = FastMCP("gtmetrix", lifespan=lifespan)

# Register all tool modules
account_tools.register(mcp)
analyze_tools.register(mcp)

if __name__ == "__main__":
    mcp.run(transport="stdio")
