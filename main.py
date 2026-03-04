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

from contextlib import asynccontextmanager
from mcp.server.fastmcp import FastMCP
from client.gtmetrix import GTMetrixClient
from config import settings
import tools.account as account_tools


@asynccontextmanager
async def lifespan(server):
    """Manage GTMetrixClient lifecycle.

    Opens a single shared httpx.AsyncClient at startup and closes it on shutdown.
    All tools access the client via ctx.request_context.lifespan_context["client"].
    """
    logger.info("GTMetrix MCP server starting — connecting HTTP client")
    async with GTMetrixClient(api_key=settings.gtmetrix_api_key) as client:
        yield {"client": client}
    logger.info("GTMetrix MCP server stopped — HTTP client closed")


mcp = FastMCP("gtmetrix", lifespan=lifespan)

# Register all tool modules
account_tools.register(mcp)

if __name__ == "__main__":
    mcp.run(transport="stdio")
