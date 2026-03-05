# Phase 5: Finalize for Public MCP GitHub Repo - Research

**Researched:** 2026-03-05
**Domain:** Open-source Python project packaging, CI/CD, repo hygiene
**Confidence:** HIGH

## Summary

Phase 5 is a non-feature phase focused on repo cleanup and public release readiness. All the code is complete (77 tests passing, all v1 requirements met). The work involves: fixing the pyproject.toml typo, adding MIT license, enriching metadata, adding GitHub Actions CI, polishing the README with badges and contributing section, and removing `.planning/` from git tracking.

The ecosystem is well-established: `astral-sh/setup-uv@v7` is the official GitHub Action for uv-based projects, shields.io provides standard badge formats, and PEP 639 defines the modern license metadata approach for pyproject.toml.

**Primary recommendation:** Keep this phase minimal and mechanical. Every task has a clear, well-documented pattern. No custom logic or complex decisions needed.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Fix pyproject.toml project name from `gtmetrix-mcp-serer` to `gtmetrix-mcp-server`
- MIT license
- Full metadata in pyproject.toml: classifiers (Python version, license, topic), author info, project URLs (homepage, repo, issues)
- Add GitHub badges (tests, Python version, license) at the top
- Add a contributing section (how to run tests, submit PRs)
- Replace `<repo-url>` with actual GitHub URL: `https://github.com/marshmallow-packages/gtmetrix-mcp.git`
- Keep generic `/path/to/gtmetrix-mcp-server` in MCP config example
- Add `.planning/` to `.gitignore` and `git rm --cached` to remove from tracking
- Keep `uv.lock` tracked (reproducible installs)
- No other cleanup needed
- GitHub Actions CI: run pytest + ruff check
- Python version matrix: 3.11, 3.12, 3.13
- Trigger on PRs and pushes to main only
- No pre-commit config

### Claude's Discretion
- pyproject.toml description wording (something concise)
- Author/branding approach in README and metadata
- Exact badge format and placement
- Contributing section depth and wording
- GitHub Actions workflow details (job names, caching strategy)

### Deferred Ideas (OUT OF SCOPE)
None
</user_constraints>

## Standard Stack

### Core
| Tool/Service | Version | Purpose | Why Standard |
|-------------|---------|---------|--------------|
| astral-sh/setup-uv | v7 | Install uv in GitHub Actions | Official Astral action, built-in caching |
| actions/checkout | v6 | Checkout repo in CI | Standard GitHub action |
| shields.io | N/A | README badges | Industry standard for GitHub badges |

### Supporting
| Tool | Purpose | When to Use |
|------|---------|-------------|
| `uv sync --locked --dev` | Install deps in CI | Every CI job, ensures lockfile integrity |
| `uv run pytest` | Run tests in CI | Test job |
| `uv run ruff check .` | Lint in CI | Lint job (or combined) |

## Architecture Patterns

### GitHub Actions Workflow Structure
```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v6
      - uses: astral-sh/setup-uv@v7
        with:
          python-version: ${{ matrix.python-version }}
          enable-cache: true
      - run: uv sync --locked --dev
      - run: uv run ruff check .
      - run: uv run pytest tests/ -v
```

**Key details:**
- `enable-cache: true` is default on GitHub-hosted runners but explicit is clearer
- `--locked` fails if lockfile is out of date (good for CI)
- Single job with lint + test is fine for a small project (no need for separate jobs)
- Python version must be quoted in YAML (`"3.11"` not `3.11`, or YAML interprets as float)

### pyproject.toml Metadata Pattern (PEP 639)
```toml
[project]
name = "gtmetrix-mcp-server"
version = "1.0.0"
description = "MCP server for GTMetrix website performance analysis"
readme = "README.md"
license = "MIT"
requires-python = ">=3.11"
authors = [
    { name = "Marshmallow", email = "info@marshmallow.dev" },
]
classifiers = [
    "Development Status :: 5 - Production/Stable",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Software Development :: Testing",
    "Topic :: Internet :: WWW/HTTP",
]

[project.urls]
Homepage = "https://github.com/marshmallow-packages/gtmetrix-mcp"
Repository = "https://github.com/marshmallow-packages/gtmetrix-mcp.git"
Issues = "https://github.com/marshmallow-packages/gtmetrix-mcp/issues"
```

**Note on PEP 639:** Modern pyproject.toml uses `license = "MIT"` (SPDX string), not the older `license = { text = "MIT" }` table format. The `License ::` classifiers are technically deprecated but still widely used and recognized.

### README Badge Pattern
```markdown
[![CI](https://img.shields.io/github/actions/workflow/status/marshmallow-packages/gtmetrix-mcp/ci.yml?branch=main&label=tests)](https://github.com/marshmallow-packages/gtmetrix-mcp/actions)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://github.com/marshmallow-packages/gtmetrix-mcp)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
```

**Note:** The workflow status badge URL uses the workflow **filename** (e.g., `ci.yml`), not the workflow name.

### MIT License File
Standard MIT license text. Year: 2025-2026 (project started 2026). Copyright holder: Marshmallow (matching the GitHub org `marshmallow-packages`).

### Contributing Section Pattern
Keep it short for a small project:
```markdown
## Contributing

1. Fork the repository
2. Create a feature branch
3. Run tests: `uv run pytest tests/ -v`
4. Run linting: `uv run ruff check .`
5. Submit a pull request
```

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CI workflow | Custom scripts | GitHub Actions with setup-uv | Maintained, cached, standard |
| Badge images | Static images | shields.io dynamic badges | Auto-update, industry standard |
| License text | Custom wording | Standard MIT text | Legal precision matters |

## Common Pitfalls

### Pitfall 1: Workflow filename in badge URL
**What goes wrong:** Badge shows "not found" because URL uses workflow name instead of filename
**How to avoid:** Use the filename (`ci.yml`) in the shields.io URL path, not the `name:` field from the YAML

### Pitfall 2: Python version as float in YAML matrix
**What goes wrong:** `3.10` becomes `3.1` in YAML
**How to avoid:** Always quote Python versions in matrix: `"3.11"`, `"3.12"`, `"3.13"`

### Pitfall 3: git rm --cached .planning/ order
**What goes wrong:** Adding to .gitignore after removing means the files briefly show as deleted in git status
**How to avoid:** Add `.planning/` to `.gitignore` first, then `git rm -r --cached .planning/`

### Pitfall 4: uv sync without --locked in CI
**What goes wrong:** CI silently updates lockfile, masking dependency drift
**How to avoid:** Always use `--locked` in CI to fail if lockfile is out of date

### Pitfall 5: Forgetting to bump version
**What goes wrong:** pyproject.toml still says `0.1.0` when project is at `1.0.0`
**How to avoid:** Update version to `1.0.0` to match CHANGELOG.md

## Code Examples

### Complete CI Workflow File
```yaml
# .github/workflows/ci.yml
# Source: https://docs.astral.sh/uv/guides/integration/github/
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v6
      - uses: astral-sh/setup-uv@v7
        with:
          python-version: ${{ matrix.python-version }}
          enable-cache: true
      - name: Install dependencies
        run: uv sync --locked --dev
      - name: Lint
        run: uv run ruff check .
      - name: Test
        run: uv run pytest tests/ -v
```

### MIT License Text
```
MIT License

Copyright (c) 2026 Marshmallow

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### .gitignore Addition
```
# Planning docs (internal)
.planning/
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `license = { text = "MIT" }` | `license = "MIT"` (SPDX) | PEP 639 (2024) | Simpler, standardized |
| `pip install` in CI | `uv sync --locked` | 2024-2025 | 10-50x faster CI |
| `actions/setup-python` | `astral-sh/setup-uv` | 2024-2025 | Handles both uv + Python |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/ -x` |
| Full suite command | `uv run pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| N/A | CI workflow runs pytest | manual-only | Push to GitHub and check Actions tab | N/A |
| N/A | Ruff check passes | smoke | `uv run ruff check .` | N/A |
| N/A | All 77 existing tests still pass | regression | `uv run pytest tests/ -v` | Yes |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -x && uv run ruff check .`
- **Per wave merge:** `uv run pytest tests/ -v`
- **Phase gate:** Full suite green + ruff clean before verify

### Wave 0 Gaps
None -- existing test infrastructure covers all phase requirements. This phase creates no new code that needs testing; it is metadata, config, and documentation only.

## Open Questions

1. **Author email in pyproject.toml**
   - What we know: GitHub org is `marshmallow-packages`
   - What's unclear: Exact email to use for author field
   - Recommendation: Use a generic contact email or omit email field

2. **GitHub Actions runner version pinning**
   - What we know: `ubuntu-latest` is standard
   - What's unclear: Whether to pin `ubuntu-24.04` for reproducibility
   - Recommendation: Use `ubuntu-latest` -- this is a small project, no need to pin

## Sources

### Primary (HIGH confidence)
- [uv GitHub Actions guide](https://docs.astral.sh/uv/guides/integration/github/) - workflow patterns, setup-uv usage
- [astral-sh/setup-uv](https://github.com/astral-sh/setup-uv) - v7, caching, Python version input
- [PEP 639](https://peps.python.org/pep-0639/) - modern license metadata in pyproject.toml

### Secondary (MEDIUM confidence)
- [shields.io](https://shields.io/badges/git-hub-actions-workflow-status) - badge URL format for GitHub Actions
- [Python Packaging Guide](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/) - pyproject.toml metadata fields

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - official Astral docs and actions verified
- Architecture: HIGH - well-established patterns, small scope
- Pitfalls: HIGH - documented common issues with known solutions

**Research date:** 2026-03-05
**Valid until:** 2026-04-05 (stable domain, 30 days)
