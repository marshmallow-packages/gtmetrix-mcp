---
phase: 1
slug: server-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-04
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio (not yet installed — Wave 0) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` section |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 0 | SERV-01 | smoke | `uv run python -c "from server import mcp; assert mcp"` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01 | 0 | SERV-02 | unit | `uv run pytest tests/test_config.py -x` | ❌ W0 | ⬜ pending |
| 1-01-03 | 01 | 0 | SERV-03 | unit | `uv run pytest tests/test_client.py::test_uses_async_client -x` | ❌ W0 | ⬜ pending |
| 1-01-04 | 01 | 0 | SERV-04 | unit | `uv run pytest tests/test_parsers.py -x` | ❌ W0 | ⬜ pending |
| 1-01-05 | 01 | 0 | SERV-05 | unit | `uv run pytest tests/test_tools.py::test_status_error_handling -x` | ❌ W0 | ⬜ pending |
| 1-01-06 | 01 | 0 | SERV-06 | lint | grep for print statements | ❌ W0 | ⬜ pending |
| 1-01-07 | 01 | 0 | ACCT-01 | unit+integration | `uv run pytest tests/test_tools.py::test_check_status -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/__init__.py` — package marker
- [ ] `tests/conftest.py` — shared fixtures (mock GTMetrixClient, mock httpx responses)
- [ ] `tests/test_config.py` — covers SERV-02
- [ ] `tests/test_client.py` — covers SERV-03
- [ ] `tests/test_parsers.py` — covers SERV-04
- [ ] `tests/test_tools.py` — covers SERV-05, ACCT-01
- [ ] `pyproject.toml` `[tool.pytest.ini_options]` section
- [ ] Framework install: `uv add --dev pytest pytest-asyncio`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Claude Code connects via stdio and lists tools | SERV-01 | Requires live Claude Code session | Add server to claude_desktop_config.json, restart, verify tools listed |
| No stdout except MCP protocol | SERV-06 | Needs end-to-end MCP transport check | Run server with stdio, observe no corruption |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
