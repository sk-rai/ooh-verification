"""Tests for enhanced verification service (Task C)."""
import pytest
from app.services.enhanced_verification import (
    run_enhanced_verification, determine_status_from_verification,
    check_pressure, check_magnetic_field, check_tremor,
    VerificationResult, WEIGHT_SIGNATURE, WEIGHT_LOCATION,
    WEIGHT_PRESSURE, WEIGHT_MAGNETIC, WEIGHT_TREMOR,
)


class TestCheckPressure:
    """Test pressure comparison logic."""

    def test_pressure_in_range(self):
        score, flags = check_pressure(1012.0, 997.0, 1027.0)
        assert score == 1.0
        assert flags == []

    def test_pressure_missing(self):
        score, flags = check_pressure(None, 997.0, 1027.0)
        assert score == 0.5
        assert "PRESSURE_DATA_MISSING" in flags

    def test_pressure_no_expected(self):
        score, flags = check_pressure(1012.0, None, None)
        assert score == 0.5
        assert flags == []

    def test_pressure_slight_deviation(self):
        score, flags = check_pressure(1030.0, 997.0, 1027.0)
        assert 0.0 < score < 1.0
        assert "PRESSURE_SLIGHT_DEVIATION" in flags

    def test_pressure_mismatch(self):
        score, flags = check_pressure(1050.0, 997.0, 1027.0)
        assert "PRESSURE_MISMATCH" in flags

    def test_pressure_severe_mismatch(self):
        score, flags = check_pressure(1070.0, 997.0, 1027.0)
        assert score == 0.0
        assert "PRESSURE_SEVERE_MISMATCH" in flags


class TestCheckMagneticField:
    """Test magnetic field comparison logic."""

    def test_magnetic_in_range(self):
        score, flags = check_magnetic_field(45.0, 33.0, 53.0)
        assert score == 1.0
        assert flags == []

    def test_magnetic_missing(self):
        score, flags = check_magnetic_field(None, 33.0, 53.0)
        assert score == 0.5
        assert "MAGNETIC_DATA_MISSING" in flags

    def test_magnetic_no_expected(self):
        score, flags = check_magnetic_field(45.0, None, None)
        assert score == 0.5

    def test_magnetic_severe_mismatch(self):
        score, flags = check_magnetic_field(80.0, 33.0, 53.0)
        assert score == 0.0
        assert "MAGNETIC_SEVERE_MISMATCH" in flags


class TestCheckTremor:
    """Test tremor analysis logic."""

    def test_human_tremor(self):
        score, flags = check_tremor(10.0, True, 0.9)
        assert score > 0.5
        assert flags == []

    def test_no_tremor_data(self):
        score, flags = check_tremor(None, None, None)
        assert score == 0.5
        assert "TREMOR_DATA_MISSING" in flags

    def test_not_human_tremor(self):
        score, flags = check_tremor(10.0, False, 0.9)
        assert score < 0.5
        assert "TREMOR_NOT_HUMAN" in flags

    def test_too_stable(self):
        score, flags = check_tremor(1.0, None, None)
        assert score < 0.5
        assert "TREMOR_TOO_STABLE" in flags

    def test_mechanical_vibration(self):
        score, flags = check_tremor(25.0, None, None)
        assert score < 0.5
        assert "TREMOR_MECHANICAL" in flags

    def test_human_frequency_range(self):
        score, flags = check_tremor(10.0, None, None)
        assert score == 0.9
        assert flags == []


class TestRunEnhancedVerification:
    """Test the full enhanced verification pipeline."""

    def test_all_good(self):
        """Signature valid, good location, all sensors in range."""
        location_result = {"match_score": 95, "distance_meters": 10}
        result = run_enhanced_verification(
            signature_valid=True,
            location_match_result=location_result,
            sensor_data=None,
            location_profile=None,
        )
        assert result.signature_score == 1.0
        assert result.location_score == pytest.approx(0.95, abs=0.01)
        assert result.confidence_score > 0.5

    def test_signature_invalid(self):
        result = run_enhanced_verification(
            signature_valid=False,
            location_match_result=None,
            sensor_data=None,
            location_profile=None,
        )
        assert result.signature_score == 0.0
        assert "SIGNATURE_INVALID" in result.flags

    def test_no_location_profile(self):
        result = run_enhanced_verification(
            signature_valid=True,
            location_match_result=None,
            sensor_data=None,
            location_profile=None,
        )
        assert result.location_score == 0.5

    def test_weights_sum_to_one(self):
        total = WEIGHT_SIGNATURE + WEIGHT_LOCATION + WEIGHT_PRESSURE + WEIGHT_MAGNETIC + WEIGHT_TREMOR
        assert total == pytest.approx(1.0)


class TestDetermineStatus:
    """Test status determination from verification result."""

    def test_signature_invalid_rejected(self):
        vr = VerificationResult(signature_score=0.0, confidence_score=0.8)
        assert determine_status_from_verification(vr) == "rejected"

    def test_high_confidence_verified(self):
        vr = VerificationResult(signature_score=1.0, confidence_score=0.85)
        assert determine_status_from_verification(vr) == "verified"

    def test_medium_confidence_flagged(self):
        vr = VerificationResult(signature_score=1.0, confidence_score=0.55)
        assert determine_status_from_verification(vr) == "flagged"

    def test_low_confidence_rejected(self):
        vr = VerificationResult(signature_score=1.0, confidence_score=0.3)
        assert determine_status_from_verification(vr) == "rejected"

    def test_severe_flag_forces_flagged(self):
        vr = VerificationResult(
            signature_score=1.0, confidence_score=0.9,
            flags=["PRESSURE_SEVERE_MISMATCH"],
        )
        assert determine_status_from_verification(vr) == "flagged"
