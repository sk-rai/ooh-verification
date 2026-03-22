"""Tests for quota enforcement service."""
import pytest
from app.services.quota_enforcer import QuotaExceededError


class TestQuotaExceededError:
    """Test QuotaExceededError formatting."""

    def test_to_dict(self):
        err = QuotaExceededError(
            message="Photo quota exceeded",
            quota_type="photos",
            current=50,
            limit=50,
            tier="free",
        )
        d = err.to_dict()
        assert d["error"] == "quota_exceeded"
        assert d["quota_type"] == "photos"
        assert d["current_usage"] == 50
        assert d["quota_limit"] == 50
        assert d["upgrade_required"] is True

    def test_suggested_action_free(self):
        err = QuotaExceededError("msg", "photos", 50, 50, "free")
        assert "Pro" in err.to_dict()["suggested_action"]

    def test_suggested_action_pro(self):
        err = QuotaExceededError("msg", "photos", 1000, 1000, "pro")
        assert "Enterprise" in err.to_dict()["suggested_action"]

    def test_suggested_action_enterprise(self):
        err = QuotaExceededError("msg", "photos", 0, 0, "enterprise")
        assert "support" in err.to_dict()["suggested_action"].lower()
