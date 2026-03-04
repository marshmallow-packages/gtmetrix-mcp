---
phase: 02
slug: core-analyze-workflow
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-04
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x with pytest-asyncio |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -v` |
| **Estimated runtime** | ~1 second |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 2 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | TEST-01 | unit | `uv run pytest tests/test_analyze.py -k start_test` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | TEST-02 | unit | `uv run pytest tests/test_analyze.py -k poll` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 1 | TEST-03 | unit | `uv run pytest tests/test_analyze.py -k timeout` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 2 | REPT-01, REPT-02 | unit | `uv run pytest tests/test_report_parser.py -k vitals` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 2 | REPT-03 | unit | `uv run pytest tests/test_report_parser.py -k audits` | ❌ W0 | ⬜ pending |
| 02-02-03 | 02 | 2 | REPT-04 | unit | `uv run pytest tests/test_report_parser.py -k resources` | ❌ W0 | ⬜ pending |
| 02-03-01 | 03 | 3 | TEST-01 | integration | `uv run pytest tests/test_tools.py -k analyze` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_analyze.py` — stubs for TEST-01, TEST-02, TEST-03
- [ ] `tests/test_report_parser.py` — stubs for REPT-01 through REPT-04
- [ ] Existing `tests/conftest.py` covers shared fixtures

*Existing pytest infrastructure from Phase 1 covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live API end-to-end | TEST-01 | Requires GTMetrix API key and real URL | Set `.env`, call `gtmetrix_analyze("https://example.com")`, verify response structure |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 2s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
