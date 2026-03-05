---
created: 2026-03-05T10:58:33.330Z
title: Add test parameter options with configurable defaults
area: api
files:
  - config.py
  - client/gtmetrix.py
  - tools/analyze.py
  - README.md
---

## Problem

`gtmetrix_analyze` currently only supports `url` and `location`. Users want to control additional test parameters:

- **Location** — already implemented, but needs configurable default (env/MCP settings)
- **Adblock** — enable/disable ad blocking during test
- **Browser** — Chrome, Firefox, etc.
- **Device** — should use simple names like "phone", "tablet", "desktop" (not raw GTMetrix device IDs)

These parameters should:
1. Have configurable defaults via `.env` or MCP server config
2. Use human-friendly names (e.g., "phone" not "iPhone 16 Pro Max")
3. Note which options require a GTMetrix PRO account (adblock, specific browsers/devices may be PRO-only)

Additionally, the README should include reference tables for available options:

| ID | Name |
|----|------|
| 1  | Dallas, USA |
| 2  | London, UK |
| ... | ... |

Same format for browsers, devices, etc.

## Solution

1. Research GTMetrix API v2.0 docs for:
   - `POST /tests` supported attributes (adblock, browser, device)
   - Which features are PRO-gated
   - Available browser/device/location IDs and names
2. Add new optional params to `start_test()` and `gtmetrix_analyze()`
3. Map simple names to GTMetrix IDs (e.g., "phone" → specific device ID)
4. Add default config in `config.py` (env vars: `GTMETRIX_DEFAULT_LOCATION`, `GTMETRIX_DEFAULT_DEVICE`, etc.)
5. Add reference tables to README.md
6. Note PRO requirements clearly in tool descriptions and README

This overlaps with deferred v2 requirements OPTS-01 (throttle), OPTS-02 (device), OPTS-03 (audit filter). Could become a new milestone phase or v2 work.
