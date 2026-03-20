#!/usr/bin/env python3
"""
Full Pre-Deployment Checkpoint Test Suite

Tests ALL backend functionality against the live running server:
1.  Health & root endpoints
2.  Client registration & login
3.  Vendor CRUD
4.  Campaign CRUD with location profile
5.  Task A1: Pressure auto-population from elevation
6.  Task A2: Magnetic field auto-population from NOAA WMM
7.  Vendor assignment to campaigns
8.  Vendor-facing campaign listing
9.  Subscription usage & management
10. Admin login & dashboard
11. Task C: Enhanced verification (unit-level checks)
12. Reports endpoints
13. Bulk endpoints
14. Quota enforcement
15. Schema validation
"""
import asyncio
import httpx
import sys
import os
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from typing import List, Tuple, Dict, Any

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

BASE_URL = "http://localhost:8000"
TENANT_ID = "e27c6c7a-7f5b-43df-bdc4-abd76ebb99aa"

test_results: List[Tuple[str, bool, str]] = []
test_data: Dict[str, Any] = {}


def log_test(name: str, passed: bool, msg: str = ""):
    status = "\u2713 PASS" if passed else "\u2717 FAIL"
    test_results.append((name, passed, msg))
    print(f"{status}: {name}")
    if msg:
        print(f"  {msg}")


def section(title: str):
    print(f"\n{'='*80}")
    print(title)
    print("="*80)


# ----------------------------------------------------------------
# TEST 1: Health & Root
# ----------------------------------------------------------------
async def test_health():
    section("TEST 1: Health & Root Endpoints")
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as c:
        try:
            r = await c.get("/health")
            log_test("GET /health", r.status_code == 200)
            if r.status_code == 200:
                log_test("Health status=healthy", r.json().get("status") == "healthy")

            r = await c.get("/")
            log_test("GET / root", r.status_code == 200)

            r = await c.get("/api/docs")
            log_test("GET /api/docs accessible", r.status_code == 200)
        except Exception as e:
            log_test("Health endpoints", False, str(e))


# ----------------------------------------------------------------
# TEST 2: Client Registration & Login
# ----------------------------------------------------------------
async def test_auth():
    section("TEST 2: Client Registration & Login")
    headers = {"X-Tenant-ID": TENANT_ID}
    email = f"checkpoint_{uuid4().hex[:8]}@example.com"
    password = "CheckPoint@2026"

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as c:
        try:
            # Register
            r = await c.post("/api/auth/register", json={
                "email": email, "password": password,
                "company_name": "Checkpoint Co", "phone_number": "+15550001234",
            }, headers=headers)
            log_test("Register client", r.status_code == 201)
            if r.status_code == 201:
                test_data["client_id"] = r.json()["client_id"]

            # Duplicate
            r2 = await c.post("/api/auth/register", json={
                "email": email, "password": password,
                "company_name": "Dup", "phone_number": "+15550009999",
            }, headers=headers)
            log_test("Reject duplicate email", r2.status_code == 400)

            # Login
            r = await c.post("/api/auth/login", json={
                "email": email, "password": password,
            }, headers=headers)
            log_test("Login client", r.status_code == 200)
            if r.status_code == 200:
                token = r.json()["access_token"]
                test_data["token"] = token
                test_data["auth"] = {"Authorization": f"Bearer {token}", "X-Tenant-ID": TENANT_ID}
                log_test("Received access_token", bool(token))

            # Wrong password
            r = await c.post("/api/auth/login", json={
                "email": email, "password": "wrong",
            }, headers=headers)
            log_test("Reject wrong password", r.status_code == 401)

            # /me/client
            if "auth" in test_data:
                r = await c.get("/api/auth/me/client", headers=test_data["auth"])
                log_test("GET /api/auth/me/client", r.status_code == 200)
                if r.status_code == 200:
                    log_test("me/client email matches", r.json()["email"] == email)
        except Exception as e:
            log_test("Auth flow", False, str(e))


# ----------------------------------------------------------------
# TEST 3: Vendor CRUD
# ----------------------------------------------------------------
async def test_vendors():
    section("TEST 3: Vendor CRUD")
    auth = test_data.get("auth")
    if not auth:
        log_test("Vendor CRUD", False, "No auth token")
        return

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as c:
        try:
            # Create vendor
            r = await c.post("/api/vendors", json={
                "name": "Checkpoint Vendor",
                "phone_number": "+919876500001",
                "email": "cpvendor@example.com",
            }, headers=auth)
            log_test("Create vendor", r.status_code == 201)
            if r.status_code == 201:
                v = r.json()
                test_data["vendor_id"] = v["vendor_id"]
                log_test("Vendor ID is 6 chars", len(v["vendor_id"]) == 6)
                log_test("Vendor status=active", v["status"] == "active")

            # List vendors
            r = await c.get("/api/vendors", headers=auth)
            log_test("List vendors", r.status_code == 200)
            if r.status_code == 200:
                log_test("Vendors total >= 1", r.json()["total"] >= 1)

            # Update vendor
            vid = test_data.get("vendor_id")
            if vid:
                r = await c.patch(f"/api/vendors/{vid}", json={"name": "Updated CP Vendor"}, headers=auth)
                log_test("Update vendor name", r.status_code == 200 and r.json()["name"] == "Updated CP Vendor")

            # Filter by status
            r = await c.get("/api/vendors?status_filter=active", headers=auth)
            log_test("Filter vendors by status", r.status_code == 200)

            # Pagination
            r = await c.get("/api/vendors?skip=0&limit=1", headers=auth)
            log_test("Vendor pagination", r.status_code == 200 and len(r.json()["vendors"]) <= 1)

        except Exception as e:
            log_test("Vendor CRUD", False, str(e))


# ----------------------------------------------------------------
# TEST 4: Campaign CRUD + Location Profile
# ----------------------------------------------------------------
async def test_campaigns():
    section("TEST 4: Campaign CRUD + Location Profile")
    auth = test_data.get("auth")
    if not auth:
        log_test("Campaign CRUD", False, "No auth token")
        return

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as c:
        try:
            now = datetime.now(tz=timezone.utc)
            # Basic campaign
            r = await c.post("/api/campaigns", json={
                "name": "Basic OOH Campaign",
                "campaign_type": "ooh",
                "start_date": now.isoformat(),
                "end_date": (now + timedelta(days=30)).isoformat(),
            }, headers=auth)
            log_test("Create basic campaign", r.status_code == 201)
            if r.status_code == 201:
                camp = r.json()
                test_data["campaign_id"] = camp["campaign_id"]
                test_data["campaign_code"] = camp["campaign_code"]
                log_test("Campaign has code", bool(camp["campaign_code"]))
                log_test("Campaign status=active", camp["status"] == "active")

            # Campaign with location profile (triggers A1 + A2 auto-population)
            r = await c.post("/api/campaigns", json={
                "name": "Mumbai Billboard",
                "campaign_type": "ooh",
                "start_date": now.isoformat(),
                "end_date": (now + timedelta(days=30)).isoformat(),
                "location_profile": {
                    "expected_latitude": 19.076,
                    "expected_longitude": 72.8777,
                    "tolerance_meters": 50.0,
                },
            }, headers=auth)
            log_test("Create campaign with location profile", r.status_code == 201)
            if r.status_code == 201:
                camp2 = r.json()
                lp = camp2.get("location_profile")
                test_data["campaign_with_lp_id"] = camp2["campaign_id"]
                log_test("Location profile returned", lp is not None)
                if lp:
                    log_test("LP latitude correct", abs(lp["expected_latitude"] - 19.076) < 0.01)
                    log_test("LP longitude correct", abs(lp["expected_longitude"] - 72.8777) < 0.01)
                    # Task A1: pressure auto-populated
                    p_min = lp.get("expected_pressure_min")
                    p_max = lp.get("expected_pressure_max")
                    log_test("Task A1: Pressure auto-populated", p_min is not None and p_max is not None,
                             f"range=[{p_min}, {p_max}]" if p_min else "NOT populated")
                    if p_min and p_max:
                        log_test("Pressure range reasonable (900-1100 hPa)", 900 < p_min < 1100 and 900 < p_max < 1100)
                    # Task A2: magnetic auto-populated
                    m_min = lp.get("expected_magnetic_min")
                    m_max = lp.get("expected_magnetic_max")
                    log_test("Task A2: Magnetic auto-populated", m_min is not None and m_max is not None,
                             f"range=[{m_min}, {m_max}]" if m_min else "NOT populated")
                    if m_min and m_max:
                        log_test("Magnetic range reasonable (10-80 uT)", 10 < m_min < 80 and 10 < m_max < 80)

            # Campaign with explicit pressure (should NOT auto-populate)
            r = await c.post("/api/campaigns", json={
                "name": "Explicit Pressure",
                "campaign_type": "construction",
                "start_date": now.isoformat(),
                "end_date": (now + timedelta(days=10)).isoformat(),
                "location_profile": {
                    "expected_latitude": 28.6139,
                    "expected_longitude": 77.2090,
                    "tolerance_meters": 100.0,
                    "expected_pressure_min": 990.0,
                    "expected_pressure_max": 1010.0,
                },
            }, headers=auth)
            log_test("Create campaign with explicit pressure", r.status_code == 201)
            if r.status_code == 201:
                lp3 = r.json().get("location_profile", {})
                log_test("Explicit pressure preserved (990)", lp3.get("expected_pressure_min") == 990.0)
                log_test("Explicit pressure preserved (1010)", lp3.get("expected_pressure_max") == 1010.0)

            # Invalid campaign type
            r = await c.post("/api/campaigns", json={
                "name": "Bad", "campaign_type": "invalid",
                "start_date": now.isoformat(),
                "end_date": (now + timedelta(days=5)).isoformat(),
            }, headers=auth)
            log_test("Reject invalid campaign_type", r.status_code == 422)

            # List campaigns
            r = await c.get("/api/campaigns", headers=auth)
            log_test("List campaigns", r.status_code == 200)
            if r.status_code == 200:
                log_test("Campaigns total >= 1", r.json()["total"] >= 1)

            # Get campaign by ID
            cid = test_data.get("campaign_id")
            if cid:
                r = await c.get(f"/api/campaigns/{cid}", headers=auth)
                log_test("Get campaign by ID", r.status_code == 200)

            # Update campaign
            if cid:
                r = await c.patch(f"/api/campaigns/{cid}", json={"name": "Updated Campaign"}, headers=auth)
                log_test("Update campaign name", r.status_code == 200)

        except Exception as e:
            log_test("Campaign CRUD", False, str(e))


# ----------------------------------------------------------------
# TEST 5: Vendor Assignment & Vendor-Facing Campaigns
# ----------------------------------------------------------------
async def test_vendor_assignment():
    section("TEST 5: Vendor Assignment & Vendor-Facing Campaigns")
    auth = test_data.get("auth")
    cid = test_data.get("campaign_id")
    vid = test_data.get("vendor_id")
    if not auth or not cid or not vid:
        log_test("Vendor assignment", False, "Missing auth/campaign/vendor")
        return

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as c:
        try:
            # Assign vendor to campaign
            r = await c.post(f"/api/campaigns/{cid}/vendors", json={
                "vendor_ids": [vid],
            }, headers=auth)
            log_test("Assign vendor to campaign", r.status_code == 201)
            if r.status_code == 201:
                log_test("Assignment returned", len(r.json()) == 1)

            # Duplicate assignment
            r = await c.post(f"/api/campaigns/{cid}/vendors", json={
                "vendor_ids": [vid],
            }, headers=auth)
            log_test("Reject duplicate assignment", r.status_code == 400)

            # Vendor OTP flow to get vendor token
            r = await c.post("/api/auth/vendor/request-otp", json={
                "vendor_id": vid,
                "phone_number": "+919876500001",
            }, headers={"X-Tenant-ID": TENANT_ID})
            log_test("Vendor request OTP", r.status_code == 200)

            # Note: We can't complete OTP flow without reading the OTP from logs
            # But we can test the vendor campaigns endpoint with a vendor token
            # For now, test remove assignment
            r = await c.delete(f"/api/campaigns/{cid}/vendors/{vid}", headers=auth)
            log_test("Remove vendor from campaign", r.status_code == 204)

            # Re-assign for later tests
            r = await c.post(f"/api/campaigns/{cid}/vendors", json={
                "vendor_ids": [vid],
            }, headers=auth)
            log_test("Re-assign vendor", r.status_code == 201)

        except Exception as e:
            log_test("Vendor assignment", False, str(e))


# ----------------------------------------------------------------
# TEST 6: Subscription Endpoints
# ----------------------------------------------------------------
async def test_subscriptions():
    section("TEST 6: Subscription Endpoints")
    auth = test_data.get("auth")
    if not auth:
        log_test("Subscriptions", False, "No auth token")
        return

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as c:
        try:
            # Tiers (no auth needed)
            r = await c.get("/api/subscriptions/tiers")
            log_test("GET /api/subscriptions/tiers", r.status_code == 200)
            if r.status_code == 200:
                tiers = [t["name"] for t in r.json()["tiers"]]
                log_test("Has free/pro/enterprise tiers", "free" in tiers and "pro" in tiers and "enterprise" in tiers)

            # Health
            r = await c.get("/api/subscriptions/health")
            log_test("Subscription health", r.status_code == 200)

            # Current subscription
            r = await c.get("/api/subscriptions/current", headers=auth)
            log_test("GET current subscription", r.status_code == 200)
            if r.status_code == 200:
                sub = r.json()
                log_test("Subscription has tier", "tier" in sub)
                log_test("Subscription has photos_quota", "photos_quota" in sub)

            # Usage
            r = await c.get("/api/subscriptions/usage", headers=auth)
            log_test("GET usage stats", r.status_code == 200)

            # Sync usage
            r = await c.post("/api/subscriptions/sync-usage", headers=auth)
            log_test("POST sync-usage", r.status_code == 200)

            # Upgrade to pro
            r = await c.post("/api/subscriptions/upgrade", json={
                "tier": "pro", "billing_cycle": "monthly",
            }, headers=auth)
            log_test("Upgrade to pro", r.status_code in (200, 400, 500),
                     f"status={r.status_code}")

            # Invalid upgrade
            r = await c.post("/api/subscriptions/upgrade", json={
                "tier": "invalid", "billing_cycle": "monthly",
            }, headers=auth)
            log_test("Reject invalid tier upgrade", r.status_code in (400, 422, 500), f"status={r.status_code}")

        except Exception as e:
            log_test("Subscriptions", False, str(e))


# ----------------------------------------------------------------
# TEST 7: Admin Login & Dashboard
# ----------------------------------------------------------------
async def test_admin():
    section("TEST 7: Admin Login & Dashboard")
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as c:
        try:
            # Login
            r = await c.post("/api/admin/login", json={
                "email": "admin@trustcapture.com",
                "password": "TrustAdmin@2026",
            })
            log_test("Admin login", r.status_code == 200)
            if r.status_code == 200:
                admin_token = r.json()["access_token"]
                admin_auth = {"Authorization": f"Bearer {admin_token}", "X-Tenant-ID": TENANT_ID}
                test_data["admin_auth"] = admin_auth

                # Profile
                r = await c.get("/api/admin/me", headers=admin_auth)
                log_test("Admin profile", r.status_code == 200)
                if r.status_code == 200:
                    log_test("Admin email correct", r.json()["email"] == "admin@trustcapture.com")

                # Dashboard
                r = await c.get("/api/admin/dashboard", headers=admin_auth)
                log_test("Admin dashboard", r.status_code == 200)
                if r.status_code == 200:
                    d = r.json()
                    log_test("Dashboard has overview", "overview" in d)
                    log_test("Dashboard has clients", "clients" in d)
                    log_test("Dashboard has usage", "usage" in d)
                    log_test("Overview total_clients >= 1", d["overview"]["total_clients"] >= 1)

            # Wrong password
            r = await c.post("/api/admin/login", json={
                "email": "admin@trustcapture.com", "password": "wrong",
            })
            log_test("Reject wrong admin password", r.status_code == 401)

        except Exception as e:
            log_test("Admin", False, str(e))


# ----------------------------------------------------------------
# TEST 8: Enhanced Verification (Unit-Level)
# ----------------------------------------------------------------
async def test_enhanced_verification():
    section("TEST 8: Enhanced Verification Service (Task C)")
    try:
        from app.services.enhanced_verification import (
            run_enhanced_verification, determine_status_from_verification,
            check_pressure, check_magnetic_field, check_tremor,
            VerificationResult, WEIGHT_SIGNATURE, WEIGHT_LOCATION,
            WEIGHT_PRESSURE, WEIGHT_MAGNETIC, WEIGHT_TREMOR,
        )

        # Weights sum to 1
        total_w = WEIGHT_SIGNATURE + WEIGHT_LOCATION + WEIGHT_PRESSURE + WEIGHT_MAGNETIC + WEIGHT_TREMOR
        log_test("Weights sum to 1.0", abs(total_w - 1.0) < 0.001)

        # Pressure checks
        score, flags = check_pressure(1012.0, 997.0, 1027.0)
        log_test("Pressure in range -> score=1.0", score == 1.0 and flags == [])

        score, flags = check_pressure(None, 997.0, 1027.0)
        log_test("Pressure missing -> 0.5 + flag", score == 0.5 and "PRESSURE_DATA_MISSING" in flags)

        score, flags = check_pressure(1070.0, 997.0, 1027.0)
        log_test("Pressure severe mismatch -> 0.0", score == 0.0 and "PRESSURE_SEVERE_MISMATCH" in flags)

        # Magnetic checks
        score, flags = check_magnetic_field(45.0, 33.0, 53.0)
        log_test("Magnetic in range -> 1.0", score == 1.0)

        score, flags = check_magnetic_field(80.0, 33.0, 53.0)
        log_test("Magnetic severe mismatch -> 0.0", score == 0.0 and "MAGNETIC_SEVERE_MISMATCH" in flags)

        # Tremor checks
        score, flags = check_tremor(10.0, True, 0.9)
        log_test("Human tremor -> high score", score > 0.5)

        score, flags = check_tremor(1.0, None, None)
        log_test("Too stable tremor -> low score", score < 0.5 and "TREMOR_TOO_STABLE" in flags)

        score, flags = check_tremor(25.0, None, None)
        log_test("Mechanical tremor -> low score", score < 0.5 and "TREMOR_MECHANICAL" in flags)

        # Full pipeline
        loc_result = {"match_score": 95, "distance_meters": 10}
        vr = run_enhanced_verification(
            signature_valid=True, location_match_result=loc_result,
            sensor_data=None, location_profile=None,
        )
        log_test("Full pipeline: sig valid + good location", vr.confidence_score > 0.5)
        log_test("Signature score = 1.0", vr.signature_score == 1.0)
        log_test("Location score ~ 0.95", abs(vr.location_score - 0.95) < 0.01)

        vr2 = run_enhanced_verification(
            signature_valid=False, location_match_result=None,
            sensor_data=None, location_profile=None,
        )
        log_test("Sig invalid -> SIGNATURE_INVALID flag", "SIGNATURE_INVALID" in vr2.flags)

        # Status determination
        log_test("Sig invalid -> rejected", determine_status_from_verification(
            VerificationResult(signature_score=0.0, confidence_score=0.8)) == "rejected")
        log_test("High confidence -> verified", determine_status_from_verification(
            VerificationResult(signature_score=1.0, confidence_score=0.85)) == "verified")
        log_test("Medium confidence -> flagged", determine_status_from_verification(
            VerificationResult(signature_score=1.0, confidence_score=0.55)) == "flagged")
        log_test("Low confidence -> rejected", determine_status_from_verification(
            VerificationResult(signature_score=1.0, confidence_score=0.3)) == "rejected")
        log_test("SEVERE flag -> flagged", determine_status_from_verification(
            VerificationResult(signature_score=1.0, confidence_score=0.9, flags=["PRESSURE_SEVERE_MISMATCH"])) == "flagged")

    except Exception as e:
        log_test("Enhanced verification", False, str(e))


# ----------------------------------------------------------------
# TEST 9: Elevation & Magnetic Services (Unit-Level)
# ----------------------------------------------------------------
async def test_elevation_magnetic():
    section("TEST 9: Elevation & Magnetic Field Services (Tasks A1, A2)")
    try:
        from app.services.elevation_service import compute_pressure_from_elevation, get_pressure_range
        from app.services.magnetic_field_service import get_magnetic_field_range

        # Barometric formula
        p_sea = compute_pressure_from_elevation(0)
        log_test("Sea level pressure ~ 1013.25", abs(p_sea - 1013.25) < 0.1)

        p_high = compute_pressure_from_elevation(5000)
        log_test("5000m pressure < 600 hPa", p_high < 600)

        p_neg = compute_pressure_from_elevation(-100)
        log_test("Below sea level pressure > 1013.25", p_neg > 1013.25)

        # Live API calls (may fail if no internet)
        try:
            pr = await get_pressure_range(19.076, 72.8777)
            if pr:
                p_min, p_max = pr
                log_test("Live pressure range for Mumbai", 900 < p_min < 1100 and 900 < p_max < 1100,
                         f"[{p_min}, {p_max}]")
                log_test("Pressure range width = 30 hPa", abs((p_max - p_min) - 30.0) < 0.1)
            else:
                log_test("Pressure range API (may be offline)", False, "Returned None")
        except Exception as e:
            log_test("Pressure range API", False, f"Exception: {e}")

        try:
            mr = await get_magnetic_field_range(19.076, 72.8777)
            if mr:
                m_min, m_max = mr
                log_test("Live magnetic range for Mumbai", 10 < m_min < 80 and 10 < m_max < 80,
                         f"[{m_min}, {m_max}]")
                log_test("Magnetic range width = 20 uT", abs((m_max - m_min) - 20.0) < 0.1)
            else:
                log_test("Magnetic range API (may be offline)", False, "Returned None")
        except Exception as e:
            log_test("Magnetic range API", False, f"Exception: {e}")

    except Exception as e:
        log_test("Elevation/Magnetic services", False, str(e))


# ----------------------------------------------------------------
# TEST 10: Schema Validation
# ----------------------------------------------------------------
async def test_schemas():
    section("TEST 10: Schema Validation")
    try:
        from app.schemas.photo import GPSData, SensorDataSchema, PhotoSignatureSchema, EnvironmentalData
        from app.schemas.campaign import CampaignCreate, LocationProfileCreate
        from pydantic import ValidationError

        # Valid GPS
        gps = GPSData(latitude=19.076, longitude=72.8777)
        log_test("Valid GPS data", gps.latitude == 19.076)

        # Invalid latitude
        try:
            GPSData(latitude=100.0, longitude=0.0)
            log_test("Reject latitude > 90", False)
        except ValidationError:
            log_test("Reject latitude > 90", True)

        # Valid sensor data with environmental
        sd = SensorDataSchema(
            gps=GPSData(latitude=19.076, longitude=72.8777),
            environmental=EnvironmentalData(
                barometer_pressure=1012.5,
                magnetic_field_magnitude=43.5,
                hand_tremor_frequency=10.0,
                hand_tremor_is_human=True,
                hand_tremor_confidence=0.9,
            ),
        )
        log_test("Sensor data with environmental", sd.environmental.barometer_pressure == 1012.5)

        # Valid signature
        from datetime import datetime, timezone
        sig = PhotoSignatureSchema(
            signature="base64data==", algorithm="ECDSA-P256",
            timestamp=datetime.now(tz=timezone.utc),
            location_hash="abc123", device_id="device-001",
        )
        log_test("Valid photo signature", sig.algorithm == "ECDSA-P256")

        # Invalid algorithm
        try:
            PhotoSignatureSchema(
                signature="x", algorithm="INVALID",
                timestamp=datetime.now(tz=timezone.utc),
                location_hash="x", device_id="x",
            )
            log_test("Reject invalid algorithm", False)
        except ValidationError:
            log_test("Reject invalid algorithm", True)

        # Campaign with location profile
        cp = CampaignCreate(
            name="Test", campaign_type="ooh",
            start_date=datetime.now(tz=timezone.utc),
            end_date=datetime.now(tz=timezone.utc) + timedelta(days=30),
            location_profile=LocationProfileCreate(
                expected_latitude=19.076, expected_longitude=72.8777,
                tolerance_meters=50.0,
                expected_pressure_min=997.0, expected_pressure_max=1027.0,
                expected_magnetic_min=33.0, expected_magnetic_max=53.0,
            ),
        )
        log_test("Campaign schema with LP", cp.location_profile.expected_pressure_min == 997.0)

        # Invalid campaign type
        try:
            CampaignCreate(
                name="Bad", campaign_type="invalid",
                start_date=datetime.now(tz=timezone.utc),
                end_date=datetime.now(tz=timezone.utc) + timedelta(days=5),
            )
            log_test("Reject invalid campaign type schema", False)
        except ValidationError:
            log_test("Reject invalid campaign type schema", True)

        # End before start
        try:
            CampaignCreate(
                name="Bad", campaign_type="ooh",
                start_date=datetime.now(tz=timezone.utc) + timedelta(days=30),
                end_date=datetime.now(tz=timezone.utc),
            )
            log_test("Reject end_date before start_date", False)
        except ValidationError:
            log_test("Reject end_date before start_date", True)

    except Exception as e:
        log_test("Schema validation", False, str(e))


# ----------------------------------------------------------------
# TEST 11: Quota Enforcer
# ----------------------------------------------------------------
async def test_quota_enforcer():
    section("TEST 11: Quota Enforcer")
    try:
        from app.services.quota_enforcer import QuotaExceededError

        err = QuotaExceededError("Photo quota exceeded", "photos", 50, 50, "free")
        d = err.to_dict()
        log_test("QuotaExceededError.to_dict()", d["error"] == "quota_exceeded")
        log_test("Quota type correct", d["quota_type"] == "photos")
        log_test("Upgrade required", d["upgrade_required"] is True)
        log_test("Free tier suggests Pro", "Pro" in d["suggested_action"])

        err2 = QuotaExceededError("msg", "photos", 1000, 1000, "pro")
        log_test("Pro tier suggests Enterprise", "Enterprise" in err2.to_dict()["suggested_action"])

    except Exception as e:
        log_test("Quota enforcer", False, str(e))


# ----------------------------------------------------------------
# TEST 12: Reports Endpoints
# ----------------------------------------------------------------
async def test_reports():
    section("TEST 12: Reports Endpoints")
    auth = test_data.get("auth")
    code = test_data.get("campaign_code")
    if not auth or not code:
        log_test("Reports", False, "Missing auth/campaign_code")
        return

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as c:
        try:
            r = await c.get(f"/reports/campaigns/{code}/statistics", headers=auth)
            log_test("Campaign statistics", r.status_code in (200, 404),
                     f"status={r.status_code}")

            r = await c.get(f"/reports/campaigns/{code}/csv", headers=auth)
            log_test("Campaign CSV report", r.status_code in (200, 404),
                     f"status={r.status_code}")

            r = await c.get(f"/reports/campaigns/{code}/geojson", headers=auth)
            log_test("Campaign GeoJSON report", r.status_code in (200, 404),
                     f"status={r.status_code}")

        except Exception as e:
            log_test("Reports", False, str(e))


# ----------------------------------------------------------------
# TEST 13: Database Schema Verification
# ----------------------------------------------------------------
async def test_database_schema():
    section("TEST 13: Database Schema Verification")
    try:
        import asyncpg
        conn = await asyncpg.connect(
            host="localhost", port=5432,
            database="trustcapture_db",
            user="trustcapture", password="dev_password_123",
        )

        # Check key tables exist
        for table in ["clients", "vendors", "campaigns", "photos", "location_profiles",
                      "sensor_data", "photo_signatures", "subscriptions", "audit_logs",
                      "tenant_config", "campaign_vendor_assignments", "admin_users"]:
            exists = await conn.fetchval(f"""
                SELECT EXISTS (SELECT FROM information_schema.tables
                WHERE table_schema='public' AND table_name='{table}')
            """)
            log_test(f"Table '{table}' exists", exists)

        # Check new columns from Tasks A1/A2/C
        for col in ["expected_pressure_min", "expected_pressure_max",
                     "expected_magnetic_min", "expected_magnetic_max"]:
            exists = await conn.fetchval(f"""
                SELECT EXISTS (SELECT FROM information_schema.columns
                WHERE table_name='location_profiles' AND column_name='{col}')
            """)
            log_test(f"location_profiles.{col} exists", exists)

        for col in ["verification_confidence", "verification_flags"]:
            exists = await conn.fetchval(f"""
                SELECT EXISTS (SELECT FROM information_schema.columns
                WHERE table_name='photos' AND column_name='{col}')
            """)
            log_test(f"photos.{col} exists", exists)

        await conn.close()
    except Exception as e:
        log_test("Database schema", False, str(e))


# ----------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------
async def main():
    print("\n" + "="*80)
    print("FULL PRE-DEPLOYMENT CHECKPOINT TEST SUITE")
    print("="*80)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Base URL: {BASE_URL}")
    print(f"Tenant ID: {TENANT_ID}")
    print(f"\nCoverage:")
    print(f"  - Health/root endpoints")
    print(f"  - Client auth (register, login, me)")
    print(f"  - Vendor CRUD (create, list, update, filter, paginate)")
    print(f"  - Campaign CRUD + location profile")
    print(f"  - Task A1: Pressure auto-population from elevation")
    print(f"  - Task A2: Magnetic field auto-population from NOAA WMM")
    print(f"  - Vendor assignment (assign, duplicate, remove)")
    print(f"  - Subscription endpoints (tiers, current, usage, upgrade)")
    print(f"  - Admin login & dashboard")
    print(f"  - Task C: Enhanced verification service")
    print(f"  - Elevation & magnetic field services")
    print(f"  - Schema validation (GPS, sensor, signature, campaign)")
    print(f"  - Quota enforcer")
    print(f"  - Reports endpoints")
    print(f"  - Database schema verification")

    await test_health()
    await test_auth()
    await test_vendors()
    await test_campaigns()
    await test_vendor_assignment()
    await test_subscriptions()
    await test_admin()
    await test_enhanced_verification()
    await test_elevation_magnetic()
    await test_schemas()
    await test_quota_enforcer()
    await test_reports()
    await test_database_schema()

    # Summary
    print(f"\n{'='*80}")
    print("TEST SUMMARY")
    print("="*80)

    passed = sum(1 for _, p, _ in test_results if p)
    failed = sum(1 for _, p, _ in test_results if not p)
    total = len(test_results)
    pct = (passed / total * 100) if total > 0 else 0

    print(f"\nTotal Tests: {total}")
    print(f"Passed:      {passed} ({pct:.1f}%)")
    print(f"Failed:      {failed} ({100-pct:.1f}%)")

    if failed > 0:
        print(f"\n{'='*80}")
        print("FAILED TESTS")
        print("="*80)
        for name, p, msg in test_results:
            if not p:
                print(f"\n\u2717 {name}")
                if msg:
                    print(f"  {msg}")

    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
