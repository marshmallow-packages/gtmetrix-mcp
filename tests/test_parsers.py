"""Tests for client/parsers.py -- SERV-04, REPT-01, REPT-02, REPT-03."""
from client.parsers import unwrap_jsonapi, extract_vitals, filter_failing_audits, extract_top_resources, _truncate_url
from tests.conftest import MOCK_LIGHTHOUSE_RESPONSE, MOCK_HAR_RESPONSE


GTMETRIX_STATUS_ENVELOPE = {
    "data": {
        "type": "user",
        "id": "abc123key",
        "attributes": {
            "api_credits": 1497,
            "api_refill": 1618437519,
            "api_refill_amount": 10,
            "account_type": "Basic",
            "account_pro_analysis_options_access": False,
        },
    }
}


def test_unwrap_full_envelope():
    """Full JSON:API envelope is flattened to a plain dict."""
    result = unwrap_jsonapi(GTMETRIX_STATUS_ENVELOPE)
    assert result["id"] == "abc123key"
    assert result["type"] == "user"
    assert result["api_credits"] == 1497
    assert result["account_type"] == "Basic"
    assert result["api_refill"] == 1618437519


def test_unwrap_empty_attributes():
    """Empty attributes dict returns dict with just id and type."""
    envelope = {"data": {"type": "test", "id": "x1", "attributes": {}}}
    result = unwrap_jsonapi(envelope)
    assert result["id"] == "x1"
    assert result["type"] == "test"
    assert len(result) == 2


def test_unwrap_missing_data_key():
    """Response without 'data' key returns empty dict without raising."""
    result = unwrap_jsonapi({})
    assert result == {} or isinstance(result, dict)


def test_unwrap_status_response_has_required_fields():
    """GTMetrix /status response unwraps to dict with ACCT-01 required fields."""
    result = unwrap_jsonapi(GTMETRIX_STATUS_ENVELOPE)
    for field in ("api_credits", "account_type", "api_refill", "api_refill_amount"):
        assert field in result, f"Missing required field: {field}"


def test_no_data_wrapper_in_output():
    """The 'data' wrapper key is NOT present in the unwrapped output."""
    result = unwrap_jsonapi(GTMETRIX_STATUS_ENVELOPE)
    assert "data" not in result
    assert "attributes" not in result


# --- Phase 2: Parser function tests ---


class TestExtractVitals:
    """Tests for extract_vitals()."""

    def test_extract_vitals(self):
        """extract_vitals returns 5 CWV fields from a report dict."""
        report = {
            "performance_score": 85,
            "structure_score": 72,
            "largest_contentful_paint": 1200,
            "total_blocking_time": 150,
            "cumulative_layout_shift": 0.05,
        }
        result = extract_vitals(report)
        assert result["performance_score"] == 85
        assert result["structure_score"] == 72
        assert result["largest_contentful_paint_ms"] == 1200
        assert result["total_blocking_time_ms"] == 150
        assert result["cumulative_layout_shift"] == 0.05

    def test_extract_vitals_missing_fields(self):
        """Missing fields return None, never raises."""
        report = {"performance_score": 90}
        result = extract_vitals(report)
        assert result["performance_score"] == 90
        assert result["structure_score"] is None
        assert result["largest_contentful_paint_ms"] is None
        assert result["total_blocking_time_ms"] is None
        assert result["cumulative_layout_shift"] is None


class TestFilterFailingAudits:
    """Tests for filter_failing_audits()."""

    def test_filter_failing_audits(self):
        """Returns only audits with score < 1, excluding notApplicable."""
        result = filter_failing_audits(MOCK_LIGHTHOUSE_RESPONSE)
        assert len(result) == 1
        assert result[0]["id"] == "largest-contentful-paint"
        assert result[0]["score"] == 0.45
        assert result[0]["title"] == "Largest Contentful Paint"
        assert result[0]["displayValue"] == "3,200 ms"

    def test_filter_failing_audits_sorted(self):
        """Multiple failing audits are sorted by score ascending (worst first)."""
        lighthouse = {
            "audits": {
                "audit-a": {"id": "audit-a", "title": "A", "description": "", "score": 0.7, "scoreDisplayMode": "numeric"},
                "audit-b": {"id": "audit-b", "title": "B", "description": "", "score": 0.3, "scoreDisplayMode": "numeric"},
                "audit-c": {"id": "audit-c", "title": "C", "description": "", "score": 0.5, "scoreDisplayMode": "numeric"},
            }
        }
        result = filter_failing_audits(lighthouse)
        assert len(result) == 3
        assert result[0]["score"] == 0.3
        assert result[1]["score"] == 0.5
        assert result[2]["score"] == 0.7

    def test_filter_failing_audits_excludes_informative(self):
        """Audits with scoreDisplayMode='informative' are excluded even if score < 1."""
        lighthouse = {
            "audits": {
                "info-audit": {
                    "id": "info-audit",
                    "title": "Info",
                    "description": "",
                    "score": 0.5,
                    "scoreDisplayMode": "informative",
                },
                "real-audit": {
                    "id": "real-audit",
                    "title": "Real",
                    "description": "",
                    "score": 0.5,
                    "scoreDisplayMode": "numeric",
                },
            }
        }
        result = filter_failing_audits(lighthouse)
        assert len(result) == 1
        assert result[0]["id"] == "real-audit"


class TestExtractTopResources:
    """Tests for extract_top_resources()."""

    def test_extract_top_resources(self):
        """Returns top 10 resources sorted by duration descending from HAR with 12+ entries."""
        result = extract_top_resources(MOCK_HAR_RESPONSE)
        assert len(result) == 10
        # First result should be the highest duration
        assert result[0]["duration_ms"] >= result[1]["duration_ms"]
        # All should have url, size_bytes, duration_ms keys
        for r in result:
            assert "url" in r
            assert "size_bytes" in r
            assert "duration_ms" in r

    def test_extract_top_resources_skips_zero_time(self):
        """Entries with time <= 0 are excluded."""
        result = extract_top_resources(MOCK_HAR_RESPONSE)
        durations = [r["duration_ms"] for r in result]
        assert all(d > 0 for d in durations)

    def test_extract_top_resources_fallback_size(self):
        """When _transferSize is missing, falls back to bodySize; when both missing, size_bytes is None."""
        har = {
            "log": {
                "entries": [
                    {
                        "request": {"url": "https://example.com/a.js"},
                        "response": {"bodySize": 5000},
                        "time": 100.0,
                    },
                    {
                        "request": {"url": "https://example.com/b.js"},
                        "response": {},
                        "time": 200.0,
                    },
                ]
            }
        }
        result = extract_top_resources(har)
        assert len(result) == 2
        # First by duration (200ms) has no size
        assert result[0]["size_bytes"] is None
        # Second (100ms) falls back to bodySize
        assert result[1]["size_bytes"] == 5000


class TestTruncateUrl:
    """Tests for _truncate_url()."""

    def test_truncate_url(self):
        """URLs longer than 120 chars are truncated with '...'."""
        long_url = "https://example.com/" + "a" * 200
        result = _truncate_url(long_url)
        assert len(result) == 120
        assert result.endswith("...")

    def test_short_url_unchanged(self):
        """URLs shorter than max_length are returned as-is."""
        url = "https://example.com/short.js"
        assert _truncate_url(url) == url
