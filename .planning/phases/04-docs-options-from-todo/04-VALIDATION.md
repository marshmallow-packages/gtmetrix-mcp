---
phase: 4
slug: docs-options-from-todo
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-05
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=9.0.2 + pytest-asyncio >=1.3.0 |
| **Config file** | `pyproject.toml` [tool.pytest.ini_options] |
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
| 04-01-01 | 01 | 1 | (none) | unit | `uv run pytest tests/test_config.py -x` | Partial | ⬜ pending |
| 04-01-02 | 01 | 1 | (none) | unit | `uv run pytest tests/test_analyze.py -x -k adblock` | ❌ W0 | ⬜ pending |
| 04-01-03 | 01 | 1 | (none) | unit | `uv run pytest tests/test_analyze.py -x -k browser` | ❌ W0 | ⬜ pending |
| 04-01-04 | 01 | 1 | (none) | unit | `uv run pytest tests/test_analyze.py -x -k device` | ❌ W0 | ⬜ pending |
| 04-01-05 | 01 | 1 | (none) | unit | `uv run pytest tests/test_analyze.py -x -k default` | ❌ W0 | ⬜ pending |
| 04-01-06 | 01 | 1 | (none) | unit | `uv run pytest tests/test_analyze.py -x -k override` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_analyze.py` — new tests for browser, device, adblock params (extend existing file)
- [ ] `tests/test_config.py` — test new optional config fields (extend existing file)
- [ ] No new test files needed — extend existing test infrastructure

*Existing infrastructure covers test framework and fixtures.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| README reference tables accurate | (none) | Content correctness | Review tables against GTMetrix docs |
| CHANGELOG entries complete | (none) | Content completeness | Review against git log |
| .env.example has new vars | (none) | File content check | Inspect .env.example |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
