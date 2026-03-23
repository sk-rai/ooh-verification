"""Enhanced Verification Service.

Task C: Compares captured sensor data against location profile expectations.
- Pressure comparison against expected range
- Magnetic field comparison against expected range  
- Tremor analysis (human-like tremor detection)
- Overall confidence score computation
"""
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """Result of enhanced verification analysis."""
    confidence_score: float = 0.0  # 0.0 to 1.0
    flags: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)
    
    # Component scores (0.0 to 1.0 each)
    signature_score: float = 0.0
    location_score: float = 0.0
    pressure_score: float = 0.0
    magnetic_score: float = 0.0
    tremor_score: float = 0.0


# Weights for confidence score (total = 1.0)
WEIGHT_SIGNATURE = 0.30
WEIGHT_LOCATION = 0.25
WEIGHT_PRESSURE = 0.15
WEIGHT_MAGNETIC = 0.15
WEIGHT_TREMOR = 0.15


def check_pressure(
    captured_pressure: Optional[float],
    expected_min: Optional[float],
    expected_max: Optional[float],
) -> tuple[float, List[str]]:
    """Compare captured pressure against expected range.
    
    Args:
        captured_pressure: Barometer reading in hPa.
        expected_min: Minimum expected pressure in hPa.
        expected_max: Maximum expected pressure in hPa.
    
    Returns:
        Tuple of (score 0-1, list of flags).
    """
    flags = []
    
    if captured_pressure is None:
        return 0.5, ["PRESSURE_DATA_MISSING"]
    
    if expected_min is None or expected_max is None:
        # No expected range configured, neutral score
        return 0.5, []
    
    if expected_min <= captured_pressure <= expected_max:
        return 1.0, []
    
    # Calculate how far outside the range
    if captured_pressure < expected_min:
        deviation = expected_min - captured_pressure
    else:
        deviation = captured_pressure - expected_max
    
    range_size = expected_max - expected_min
    if range_size > 0:
        deviation_ratio = deviation / range_size
    else:
        deviation_ratio = 1.0
    
    # Score degrades with deviation
    score = max(0.0, 1.0 - deviation_ratio)
    
    if deviation > 30:  # More than 30 hPa off
        flags.append("PRESSURE_SEVERE_MISMATCH")
        score = 0.0
    elif deviation > 15:  # More than 15 hPa off
        flags.append("PRESSURE_MISMATCH")
    else:
        flags.append("PRESSURE_SLIGHT_DEVIATION")
    
    logger.info(
        f"Pressure check: captured={captured_pressure}, "
        f"expected=[{expected_min}, {expected_max}], "
        f"deviation={deviation:.1f}, score={score:.2f}"
    )
    
    return score, flags


def check_magnetic_field(
    captured_magnitude: Optional[float],
    expected_min: Optional[float],
    expected_max: Optional[float],
) -> tuple[float, List[str]]:
    """Compare captured magnetic field magnitude against expected range.
    
    Args:
        captured_magnitude: Magnetic field magnitude in uT.
        expected_min: Minimum expected magnitude in uT.
        expected_max: Maximum expected magnitude in uT.
    
    Returns:
        Tuple of (score 0-1, list of flags).
    """
    flags = []
    
    if captured_magnitude is None:
        return 0.5, ["MAGNETIC_DATA_MISSING"]
    
    if expected_min is None or expected_max is None:
        return 0.5, []
    
    if expected_min <= captured_magnitude <= expected_max:
        return 1.0, []
    
    if captured_magnitude < expected_min:
        deviation = expected_min - captured_magnitude
    else:
        deviation = captured_magnitude - expected_max
    
    range_size = expected_max - expected_min
    if range_size > 0:
        deviation_ratio = deviation / range_size
    else:
        deviation_ratio = 1.0
    
    score = max(0.0, 1.0 - deviation_ratio)
    
    if deviation > 20:  # More than 20 uT off
        flags.append("MAGNETIC_SEVERE_MISMATCH")
        score = 0.0
    elif deviation > 10:
        flags.append("MAGNETIC_MISMATCH")
    else:
        flags.append("MAGNETIC_SLIGHT_DEVIATION")
    
    logger.info(
        f"Magnetic check: captured={captured_magnitude}, "
        f"expected=[{expected_min}, {expected_max}], "
        f"deviation={deviation:.1f}, score={score:.2f}"
    )
    
    return score, flags


def check_tremor(
    tremor_frequency: Optional[float],
    tremor_is_human: Optional[bool],
    tremor_confidence: Optional[float],
) -> tuple[float, List[str]]:
    """Analyze hand tremor data for human presence verification.
    
    Human hand tremor is typically 8-12 Hz. Absence of tremor or
    mechanical vibration patterns suggest a mounted/fake device.
    
    Args:
        tremor_frequency: Detected tremor frequency in Hz.
        tremor_is_human: Whether tremor is in human range.
        tremor_confidence: Confidence of tremor detection (0-1).
    
    Returns:
        Tuple of (score 0-1, list of flags).
    """
    flags = []
    
    if tremor_frequency is None and tremor_is_human is None:
        return 0.5, ["TREMOR_DATA_MISSING"]
    
    # If Android already classified it
    if tremor_is_human is not None:
        if tremor_is_human:
            confidence = tremor_confidence if tremor_confidence is not None else 0.7
            return min(1.0, 0.5 + confidence * 0.5), []
        else:
            flags.append("TREMOR_NOT_HUMAN")
            confidence = tremor_confidence if tremor_confidence is not None else 0.7
            return max(0.0, 0.5 - confidence * 0.5), flags
    
    # Analyze frequency directly
    if tremor_frequency is not None:
        if 6.0 <= tremor_frequency <= 14.0:
            # Human range
            return 0.9, []
        elif tremor_frequency < 2.0:
            # Too stable - possibly mounted device
            flags.append("TREMOR_TOO_STABLE")
            return 0.2, flags
        elif tremor_frequency > 20.0:
            # Mechanical vibration
            flags.append("TREMOR_MECHANICAL")
            return 0.1, flags
        else:
            # Borderline
            flags.append("TREMOR_UNUSUAL_FREQUENCY")
            return 0.4, flags
    
    return 0.5, []



def check_delivery_window(
    capture_timestamp,
    delivery_window_start,
    delivery_window_end,
) -> tuple[float, list[str]]:
    """Check if capture timestamp falls within the delivery time window.

    Args:
        capture_timestamp: When the photo was captured.
        delivery_window_start: Earliest allowed capture time.
        delivery_window_end: Latest allowed capture time.

    Returns:
        Tuple of (score 0-1, list of flags).
    """
    flags = []

    if capture_timestamp is None:
        return 0.5, ["CAPTURE_TIMESTAMP_MISSING"]

    if delivery_window_start is None and delivery_window_end is None:
        # No delivery window configured, neutral
        return 1.0, []

    from datetime import timezone

    # Make timestamps timezone-aware for comparison
    ts = capture_timestamp
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    if delivery_window_start is not None:
        ws = delivery_window_start
        if ws.tzinfo is None:
            ws = ws.replace(tzinfo=timezone.utc)
        if ts < ws:
            flags.append("OUTSIDE_DELIVERY_WINDOW")
            # How far outside? Score degrades
            diff_minutes = (ws - ts).total_seconds() / 60
            if diff_minutes > 60:
                return 0.0, flags
            return max(0.0, 1.0 - diff_minutes / 60), flags

    if delivery_window_end is not None:
        we = delivery_window_end
        if we.tzinfo is None:
            we = we.replace(tzinfo=timezone.utc)
        if ts > we:
            flags.append("OUTSIDE_DELIVERY_WINDOW")
            diff_minutes = (ts - we).total_seconds() / 60
            if diff_minutes > 60:
                return 0.0, flags
            return max(0.0, 1.0 - diff_minutes / 60), flags

    return 1.0, []

def run_enhanced_verification(
    signature_valid: bool,
    location_match_result: Optional[Dict[str, Any]],
    sensor_data: Optional[Any],
    location_profile: Optional[Any],
    campaign: Optional[Any] = None,
    capture_timestamp=None,
) -> VerificationResult:
    """Run the full enhanced verification pipeline.
    
    Args:
        signature_valid: Whether the photo signature is valid.
        location_match_result: Result from LocationProfileMatcher (or None).
        sensor_data: SensorDataSchema object with captured sensor readings.
        location_profile: LocationProfile model with expected ranges.
    
    Returns:
        VerificationResult with confidence score, flags, and details.
    """
    result = VerificationResult()
    
    # 1. Signature score
    result.signature_score = 1.0 if signature_valid else 0.0
    if not signature_valid:
        result.flags.append("SIGNATURE_INVALID")
    
    # 2. Location score (from existing matcher)
    if location_match_result is not None:
        raw_score = location_match_result.get("match_score", 0)
        result.location_score = min(1.0, raw_score / 100.0)
        distance = location_match_result.get("distance_meters", 0)
        if distance > 1000:
            result.flags.append("LOCATION_FAR_FROM_EXPECTED")
        elif distance > 200:
            result.flags.append("LOCATION_MODERATE_DEVIATION")
    else:
        result.location_score = 0.5  # No profile, neutral
    
    # 3. Pressure check
    captured_pressure = None
    expected_p_min = None
    expected_p_max = None
    
    if sensor_data and hasattr(sensor_data, "environmental") and sensor_data.environmental:
        captured_pressure = sensor_data.environmental.barometer_pressure
    
    if location_profile:
        expected_p_min = location_profile.expected_pressure_min
        expected_p_max = location_profile.expected_pressure_max
    
    p_score, p_flags = check_pressure(captured_pressure, expected_p_min, expected_p_max)
    result.pressure_score = p_score
    result.flags.extend(p_flags)
    
    # 4. Magnetic field check
    captured_mag = None
    expected_m_min = None
    expected_m_max = None
    
    if sensor_data and hasattr(sensor_data, "environmental") and sensor_data.environmental:
        captured_mag = sensor_data.environmental.magnetic_field_magnitude
    
    if location_profile:
        expected_m_min = location_profile.expected_magnetic_min
        expected_m_max = location_profile.expected_magnetic_max
    
    m_score, m_flags = check_magnetic_field(captured_mag, expected_m_min, expected_m_max)
    result.magnetic_score = m_score
    result.flags.extend(m_flags)
    
    # 5. Tremor check
    tremor_freq = None
    tremor_human = None
    tremor_conf = None
    
    if sensor_data and hasattr(sensor_data, "environmental") and sensor_data.environmental:
        env = sensor_data.environmental
        tremor_freq = env.hand_tremor_frequency
        tremor_human = env.hand_tremor_is_human
        tremor_conf = env.hand_tremor_confidence
    
    t_score, t_flags = check_tremor(tremor_freq, tremor_human, tremor_conf)
    result.tremor_score = t_score
    result.flags.extend(t_flags)
    
    # 6. Delivery time-window check
    dw_score = 1.0
    dw_flags = []
    if location_profile and capture_timestamp:
        dw_start = getattr(location_profile, 'delivery_window_start', None)
        dw_end = getattr(location_profile, 'delivery_window_end', None)
        if dw_start or dw_end:
            dw_score, dw_flags = check_delivery_window(
                capture_timestamp, dw_start, dw_end
            )
            result.flags.extend(dw_flags)
            # If outside delivery window, penalize confidence
            if dw_flags:
                result.details['delivery_window_score'] = dw_score

    # 7. Compute weighted confidence score
    base_confidence = round(
        WEIGHT_SIGNATURE * result.signature_score
        + WEIGHT_LOCATION * result.location_score
        + WEIGHT_PRESSURE * result.pressure_score
        + WEIGHT_MAGNETIC * result.magnetic_score
        + WEIGHT_TREMOR * result.tremor_score,
        4,
    )
    # Apply delivery window penalty (multiplicative — outside window tanks the score)
    result.confidence_score = round(base_confidence * dw_score, 4)
    
    # Store details
    result.details = {
        "signature_score": result.signature_score,
        "location_score": result.location_score,
        "pressure_score": result.pressure_score,
        "magnetic_score": result.magnetic_score,
        "tremor_score": result.tremor_score,
        "weights": {
            "signature": WEIGHT_SIGNATURE,
            "location": WEIGHT_LOCATION,
            "pressure": WEIGHT_PRESSURE,
            "magnetic": WEIGHT_MAGNETIC,
            "tremor": WEIGHT_TREMOR,
        },
        "captured_pressure": captured_pressure,
        "expected_pressure_range": [expected_p_min, expected_p_max] if expected_p_min else None,
        "captured_magnetic": captured_mag,
        "expected_magnetic_range": [expected_m_min, expected_m_max] if expected_m_min else None,
        "tremor_frequency": tremor_freq,
        "tremor_is_human": tremor_human,
    }
    
    logger.info(
        f"Enhanced verification: confidence={result.confidence_score}, "
        f"flags={result.flags}, scores=[sig={result.signature_score}, "
        f"loc={result.location_score}, pres={result.pressure_score}, "
        f"mag={result.magnetic_score}, tremor={result.tremor_score}]"
    )
    
    return result


def determine_status_from_verification(vr: VerificationResult) -> str:
    """Determine verification status from enhanced verification result.
    
    Logic:
    - Signature invalid -> rejected
    - Confidence >= 0.75 -> verified
    - Confidence >= 0.45 -> flagged
    - Confidence < 0.45 -> rejected
    - Any SEVERE flag -> flagged (even if score is high)
    
    Returns:
        Status string: "verified", "flagged", or "rejected"
    """
    if not vr.signature_score:
        return "rejected"
    
    severe_flags = [f for f in vr.flags if "SEVERE" in f or f == "OUTSIDE_DELIVERY_WINDOW"]
    if severe_flags:
        return "flagged"
    
    if vr.confidence_score >= 0.75:
        return "verified"
    elif vr.confidence_score >= 0.45:
        return "flagged"
    else:
        return "rejected"
