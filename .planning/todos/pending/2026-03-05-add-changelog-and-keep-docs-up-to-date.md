---
created: 2026-03-05T10:56:02.889Z
title: Add changelog and keep docs up to date
area: docs
files:
  - README.md
  - CHANGELOG.md
---

## Problem

The project has no CHANGELOG.md yet. The README.md and install instructions should be kept current as features are added or changed. Currently 3 MCP tools exist (check_status, analyze, list_locations) — future changes need to be reflected in both the changelog and README.

## Solution

- Create a CHANGELOG.md following Keep a Changelog format
- Backfill v1.0 entries from the 3 phases already completed
- Update README.md tool table and example response when tools change
- Make this part of the workflow: update docs when adding/changing tools
