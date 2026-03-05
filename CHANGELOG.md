# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-03-05

### Added
- `gtmetrix_analyze(url)` tool -- full performance analysis returning Core Web Vitals, failing Lighthouse audits, and top 10 slowest resources
- `gtmetrix_check_status()` tool -- API credits remaining, account type, and refill date
- `gtmetrix_list_locations()` tool -- available test locations with in-memory caching
- Location parameter for `gtmetrix_analyze` with validation against available locations
- Browser, device, and adblock parameters for `gtmetrix_analyze`
- Configurable parameter defaults via `GTMETRIX_DEFAULT_*` environment variables
- Device aliases: `phone`, `tablet`, `desktop` (or pass raw GTMetrix device IDs)
- Automatic test polling (3-second intervals, 5-minute timeout)
- Structured error responses with actionable hints for all failure modes
- JSON:API response parsing for all GTMetrix API v2.0 endpoints
- Configuration via MCP host environment variables (Claude Code `env` block or Claude Desktop config)
- GitHub Actions CI workflow with Python 3.11/3.12/3.13 matrix
- stdio transport for Claude Code and Claude Desktop MCP integration
