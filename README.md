[![CI](https://img.shields.io/github/actions/workflow/status/marshmallow-packages/gtmetrix-mcp/ci.yml?branch=main&label=tests)](https://github.com/marshmallow-packages/gtmetrix-mcp/actions)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://github.com/marshmallow-packages/gtmetrix-mcp)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

# GTMetrix MCP Server

An MCP server that lets Claude analyze website performance using the [GTMetrix API](https://gtmetrix.com/api/). Scan any URL and get back structured Core Web Vitals, failing Lighthouse audits, and resource waterfall data that Claude can reason about to suggest code-level fixes.

## Tools

| Tool | Description |
|------|-------------|
| `gtmetrix_analyze(url, location?, browser?, device?, adblock?)` | Run a full performance test. Returns Core Web Vitals (LCP, TBT, CLS), failing Lighthouse audits, and the 10 slowest resources. Polls automatically until complete (3s intervals, 5min timeout). |
| `gtmetrix_check_status()` | Check API credits remaining, account type, and credit refill date. |
| `gtmetrix_list_locations()` | List available test locations (geographic regions). Results are cached in memory. |

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- A GTMetrix API key — get one at https://gtmetrix.com/api/

## Installation

```bash
git clone https://github.com/marshmallow-packages/gtmetrix-mcp.git gtmetrix-mcp-server
cd gtmetrix-mcp-server
uv sync
```

## Usage with Claude Code

Add to your Claude Code MCP settings (`~/.claude/settings.json` or project `.mcp.json`):

```json
{
  "mcpServers": {
    "gtmetrix": {
      "command": "/path/to/uv",
      "args": ["run", "--directory", "/path/to/gtmetrix-mcp-server", "python", "main.py"],
      "env": {
        "GTMETRIX_API_KEY": "your_api_key_here",
        "GTMETRIX_DEFAULT_LOCATION": "1",
        "GTMETRIX_DEFAULT_BROWSER": "3"
      }
    }
  }
}
```

> **Tip:** Use the full path to `uv` (e.g. `/opt/homebrew/bin/uv`). MCP hosts like the VS Code extension don't inherit your shell's `$PATH`, so a bare `uv` will fail with "Executable not found". Run `which uv` to find the path.

Then ask Claude things like:

- "Analyze the performance of https://example.com"
- "What are my GTMetrix API credits?"
- "Test https://example.com from a server in London"
- "Analyze https://example.com with adblock enabled"
- "Test https://example.com on a phone from London"
- "What locations can I test from?"

## Usage with Claude Desktop

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "gtmetrix": {
      "command": "/path/to/uv",
      "args": ["run", "--directory", "/path/to/gtmetrix-mcp-server", "python", "main.py"],
      "env": {
        "GTMETRIX_API_KEY": "your_api_key_here",
        "GTMETRIX_DEFAULT_LOCATION": "1",
        "GTMETRIX_DEFAULT_BROWSER": "3"
      }
    }
  }
}
```

## Usage with MCP Inspector

```bash
GTMETRIX_API_KEY=your_key uv run mcp dev main.py
```

## Running Tests

```bash
uv run pytest tests/ -v
```

## Configuration

Set these in the `env` block of your MCP client config. See setup examples above. All values must be **strings** (quoted in JSON).

Explicit tool parameters always override defaults.

| Environment Variable | Description | Example |
|---------------------|-------------|---------|
| `GTMETRIX_API_KEY` | **Required.** Your GTMetrix API key | `abc123` |
| `GTMETRIX_DEFAULT_LOCATION` | Default test location ID | `1` |
| `GTMETRIX_DEFAULT_BROWSER` | Default browser ID | `3` |
| `GTMETRIX_DEFAULT_DEVICE` | Default device (`phone`, `tablet`, `desktop`, or raw ID) | `phone` |
| `GTMETRIX_DEFAULT_ADBLOCK` | Enable adblock by default (`0` or `1`) | `0` |

## Project Structure

```
main.py              # FastMCP server with lifespan client management
config.py            # Settings loaded from environment variables via pydantic-settings
client/
  gtmetrix.py        # Async HTTP client (httpx) with auth and API methods
  parsers.py         # JSON:API response parsers and report data extractors
tools/
  account.py         # gtmetrix_check_status tool
  analyze.py         # gtmetrix_analyze and gtmetrix_list_locations tools
tests/               # pytest suite (78 tests)
```

## Reference

### Device Aliases

| Alias | GTMetrix Device ID | Description |
|-------|-------------------|-------------|
| `phone` | `iphone_16` | Modern smartphone viewport (PRO) |
| `tablet` | `ipad_air` | Tablet viewport (PRO) |
| `desktop` | _(default)_ | No simulated device |

Simulated devices require a GTMetrix PRO account. You can also pass any raw GTMetrix device ID directly.

### Common Browser IDs

| ID | Browser |
|----|---------|
| `3` | Chrome (Desktop) |

Use `gtmetrix_list_locations()` to see which browsers are available per location. Browser IDs may vary by account.

### Common Locations

Use `gtmetrix_list_locations()` to see all available locations for your account. Some common location IDs:

**Europe:**

| ID | Location |
|----|----------|
| `13` | Amsterdam, Netherlands |
| `15` | Frankfurt, Germany |
| `2` | London, UK |
| `14` | Paris, France |
| `23` | Madrid, Spain |
| `16` | Stockholm, Sweden |

**North America:**

| ID | Location |
|----|----------|
| `4` | San Antonio, TX |
| `9` | San Francisco, CA |
| `11` | Chicago, IL |
| `24` | Seattle, WA |
| `8` | Quebec City, Canada |
| `10` | Cheyenne, WY |
| `12` | Danville, VA |
| `25` | Mexico City, Mexico |

Additional locations are available in Asia Pacific, Latin America, Africa, and Middle East.

## Example Response

Calling `gtmetrix_analyze("https://example.com")` returns:

```json
{
  "url": "https://example.com",
  "test_id": "abc123",
  "report_id": "def456",
  "performance_score": 92,
  "structure_score": 88,
  "largest_contentful_paint_ms": 1200,
  "total_blocking_time_ms": 150,
  "cumulative_layout_shift": 0.05,
  "failing_audits": [
    {
      "id": "render-blocking-resources",
      "title": "Eliminate render-blocking resources",
      "description": "Resources are blocking the first paint...",
      "score": 0.45,
      "displayValue": "Potential savings of 350 ms"
    }
  ],
  "top_resources": [
    {
      "url": "https://example.com/bundle.js",
      "size_bytes": 245000,
      "duration_ms": 820
    }
  ]
}
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Run tests: `uv run pytest tests/ -v`
4. Run linting: `uv run ruff check .`
5. Submit a pull request
