---
phase: 03
slug: location-and-test-parameters
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-04
---

# Phase 03 — Validation Strategy

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
| 03-01-01 | 01 | 1 | TEST-04 | unit | `uv run pytest tests/test_parsers.py -k jsonapi_list` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | TEST-04 | unit | `uv run pytest tests/test_client.py -k locations` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 2 | TEST-04, TEST-05 | unit | `uv run pytest tests/test_analyze.py -k location` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Existing `tests/conftest.py` covers shared fixtures
- [ ] Existing pytest infrastructure from Phase 1 covers framework needs

*No new test infrastructure needed — extends existing test files.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live location fetch | TEST-04 | Requires GTMetrix API key | Set `.env`, call `gtmetrix_list_locations()` or `gtmetrix_analyze(url, location="...")`, verify locations returned |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 2s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
