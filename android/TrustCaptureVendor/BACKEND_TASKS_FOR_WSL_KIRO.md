# Backend Tasks for WSL Kiro Session

## Context
The Android app now captures a full sensor suite at photo capture time. The sensor data is serialized as JSON in the `sensor_data` field of the upload payload. The backend needs to:
1. Accept and store this sensor data
2. Auto-populate expected sensor values for campaign locations
3. Compare captured vs expected values during photo verification

---

## Task A: Location Profile Auto-Population (Background Job)

When a campaign is created with a location (latitude/longitude), run a background task to auto-populate expected sensor ranges in the `location_profiles` table.

### A1: Expected Pressure Range (Priority: High, Difficulty: Low)
- Call an elevation API (e.g., Open-Meteo Elevation API — free, no key needed) with the campaign's lat/lon
- Get elevation in meters
- Compute standard atmospheric pressure using barometric formula: `P = 1013.25 * (1 - 0.0000225577 * altitude) ^ 5.25588`
- Store as `expected_pressure_min` and `expected_pressure_max` with ±15 hPa tolerance (accounts for weather variation)
- Open-Meteo endpoint: `GET https://api.open-meteo.com/v1/elevation?latitude={lat}&longitude={lon}`

### A2: Expected Magnetic Field (Priority: Medium, Difficulty: Medium)
- Use NOAA World Magnetic Model (WMM) to get expected magnetic field magnitude for a given lat/lon/altitude/date
- NOAA API: `GET https://www.ngdc.noaa.gov/geomag-web/calculators/calculateDeclination?lat1={lat}&lon1={lon}&model=WMM&resultFormat=json`
- Store expected total intensity (in µT) with ±10 µT tolerance
- This is a differentiator — proves the phone was physically at the location based on Earth's magnetic field

### A3: Expected Cell Towers (Priority: Low, Difficulty: Medium)
- Query OpenCelliD API (`https://opencellid.org/`) or Mozilla Location Service to find cell towers near the campaign coordinates
- Store expected cell tower IDs (MCC/MNC/LAC/CID) in `expected_cell_tower_ids`
- These databases are incomplete, so treat as supplementary signal, not primary
- Requires API key for OpenCelliD (free tier available)

### A4: WiFi and Light — Manual Config Only
- WiFi BSSIDs cannot be predicted from coordinates — too hyperlocal and dynamic
- Ambient light depends on indoor/outdoor, time of day, weather
- Recommendation: let the client configure these manually in the campaign creation wizard
- Alternative: implement "learning mode" where first N photos establish the baseline, then subsequent photos are compared against it

---

## Task B: Photo Upload Endpoint (`POST /api/photos/upload`)

The Android app will send this multipart payload:

```
POST /api/photos/upload
Content-Type: multipart/form-data

Fields:
- photo: JPEG file (watermarked, EXIF-corrected)
- campaign_code: string (e.g., "CAM-2026-KZF9")
- capture_timestamp: ISO 8601 string
- signature: JSON string (see schema below)
- sensor_data: JSON string (see schema below)
```

### Signature JSON Schema
```json
{
  "signature": "base64-encoded-ECDSA-signature",
  "algorithm": "ECDSA-SHA256",
  "device_id": "81bc69531e15bcec",
  "timestamp": "2026-03-15T14:30:00Z",
  "location_hash": "sha256-hex-string"
}
```

### Sensor Data JSON Schema
```json
{
  "gps": {
    "latitude": 37.4219983,
    "longitude": -122.0840000,
    "accuracy": 5.0,
    "altitude": 12.5
  },
  "wifi": {
    "networks": [
      {
        "ssid": "MyNetwork",
        "bssid": "AA:BB:CC:DD:EE:FF",
        "signal_dbm": -45,
        "frequency_mhz": 5180
      }
    ],
    "count": 1
  },
  "cell_towers": {
    "towers": [
      {
        "cell_id": 12345,
        "lac": 6789,
        "mcc": 310,
        "mnc": 260,
        "signal_dbm": -85,
        "network_type": "LTE"
      }
    ],
    "count": 1
  },
  "environmental": {
    "pressure_hpa": 1013.3,
    "altitude_meters": 12.5,
    "light_lux": 350.0,
    "magnetic_field": {
      "x": 22.5,
      "y": -5.3,
      "z": 42.1,
      "magnitude": 48.8
    },
    "tremor_detected": false
  },
  "schema_version": "1.0"
}
```

---

## Task C: Photo Verification Workflow

When a photo is uploaded, the backend should:

1. Verify the cryptographic signature using the vendor's registered public key
2. Compare GPS coordinates against campaign's expected location (Haversine distance)
3. Compare pressure against expected range (from Task A1)
4. Compare magnetic field against expected magnitude (from Task A2)
5. Match WiFi BSSIDs against expected list (if configured)
6. Match cell tower IDs against expected list (if configured)
7. Check for tremor (flag if detected)
8. Calculate overall confidence score (0-100)
9. Set verification status: verified / flagged / rejected

---

## Current Android App Status (for reference)

Completed Android tasks:
- Login/OTP with backend auth
- Campaign list from `GET /api/vendors/me/campaigns`
- CameraX photo capture with EXIF rotation fix
- Watermark generation (GPS, timestamp, campaign code, vendor ID)
- Keystore ECDSA P-256 signing + device registration
- Session persistence (auto-login)
- Full sensor suite: GPS, WiFi, cell towers, barometer, light, magnetometer, tremor detection
- Sensor data serialized as JSON for upload
- Photo signing with location hash binding

The upload currently simulates with a delay — waiting for backend `POST /api/photos/upload` to be ready.
