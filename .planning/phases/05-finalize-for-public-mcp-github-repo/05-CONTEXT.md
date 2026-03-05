# Phase 5: Finalize for public MCP GitHub repo - Context

**Gathered:** 2026-03-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Prepare the existing functional MCP server for public release on GitHub. This covers repo metadata, README polish, cleanup of internal artifacts, CI setup, and licensing. No new features or tool changes.

</domain>

<decisions>
## Implementation Decisions

### Repo metadata & packaging
- Fix pyproject.toml project name from `gtmetrix-mcp-serer` to `gtmetrix-mcp-server`
- MIT license
- Full metadata in pyproject.toml: classifiers (Python version, license, topic), author info, project URLs (homepage, repo, issues)

### README & first impressions
- Add GitHub badges (tests, Python version, license) at the top
- Add a contributing section (how to run tests, submit PRs)
- Replace `<repo-url>` with actual GitHub URL: `https://github.com/marshmallow-packages/gtmetrix-mcp.git`
- Keep generic `/path/to/gtmetrix-mcp-server` in MCP config example

### Cleanup
- Add `.planning/` to `.gitignore` and `git rm --cached` to remove from tracking
- Local folder name typo is irrelevant — skip
- Keep `uv.lock` tracked (reproducible installs)
- No other cleanup needed — `.gitignore` already covers `__pycache__`, `.env`, etc.

### CI & quality gates
- GitHub Actions CI: run pytest + ruff check
- Python version matrix: 3.11, 3.12, 3.13
- Trigger on PRs and pushes to main only
- No pre-commit config — CI catches issues, contributors aren't forced into local tools

### Claude's Discretion
- pyproject.toml description wording (something concise)
- Author/branding approach in README and metadata
- Exact badge format and placement
- Contributing section depth and wording
- GitHub Actions workflow details (job names, caching strategy)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `pyproject.toml`: Already has ruff config, pytest config, dependency groups — extend with metadata fields
- `.gitignore`: Python-appropriate, just needs `.planning/` addition
- `README.md`: Complete with tools table, install, config, reference tables, example response — extend, don't rewrite
- `CHANGELOG.md`: Keep a Changelog format already established with v1.0.0 entry

### Established Patterns
- `uv` as package manager throughout (install, run, sync)
- `ruff` for linting (already in dev dependencies, line-length=100)
- `pytest` with asyncio_mode=auto
- 74 existing tests in `tests/` directory

### Integration Points
- `.github/workflows/` — new directory for CI workflow file
- `pyproject.toml` — metadata additions
- `README.md` — badges at top, contributing section, clone URL fix
- `.gitignore` — add `.planning/`
- `LICENSE` — new file (MIT)

</code_context>

<specifics>
## Specific Ideas

- GitHub remote is already set: `marshmallow-packages/gtmetrix-mcp`
- Project has 74 tests — CI should be straightforward
- The repo name on GitHub is correct (`gtmetrix-mcp`), only pyproject.toml has the typo

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 05-finalize-for-public-mcp-github-repo*
*Context gathered: 2026-03-05*
