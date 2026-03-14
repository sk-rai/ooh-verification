#!/usr/bin/env python3
"""
TrustCapture E2E Platform Test Suite
Tests all major API endpoints against a running backend (localhost:8000).
"""
import requests, json, io, random, sys

BASE = "http://localhost:8000"
UNIQUE = str(random.randint(100000, 999999))
passed = 0
failed = 0
failures = []

def test(name, condition, detail=""):
    global passed, failed
    if condition:
        print("  \u2705 " + name)
        passed += 1
    else:
        print("  \u274c " + name + " \u2014 " + detail)
        failed += 1
        failures.append(name + ": " + detail)

def safe_get(resp, key, default=None):
    try:
        data = resp.json()
        if isinstance(data, dict):
            return data.get(key, default)
    except Exception:
        pass
    return default

def resp_list_len(resp):
    try:
        data = resp.json()
        if isinstance(data, list):
            return len(data)
    except Exception:
        pass
    return -1

def api_post(path, json_data=None, headers=None, files=None):
    return requests.post(BASE + path, json=json_data, headers=headers, files=files)

def api_get(path, headers=None):
    return requests.get(BASE + path, headers=headers)

def api_patch(path, json_data=None, headers=None):
    return requests.patch(BASE + path, json=json_data, headers=headers)


def api_delete(path, headers=None):
    return requests.delete(BASE + path, headers=headers)

print("=" * 60)
print("TrustCapture E2E Platform Test Suite")
print("Unique suffix: " + UNIQUE)
print("=" * 60)

# ============================================================
# 1. AUTH TESTS
# ============================================================
print("\n" + "=" * 60)
print("1. Authentication Tests")
print("=" * 60)

email = "e2e_" + UNIQUE + "@test.com"
r = api_post("/api/auth/register", {
    "email": email, "password": "TestPass123!",
    "company_name": "E2E Company " + UNIQUE, "phone_number": "+1555" + UNIQUE
})
test("1.1 Register client", r.status_code == 201, str(r.status_code) + ": " + r.text[:200])

r = api_post("/api/auth/login", {"email": email, "password": "TestPass123!"})
test("1.2 Login", r.status_code == 200, str(r.status_code))
token = safe_get(r, "access_token", "")
auth = {"Authorization": "Bearer " + token} if token else {}

r = api_post("/api/auth/login", {"email": email, "password": "wrong"})
test("1.3 Reject wrong password", r.status_code == 401, str(r.status_code))

r = api_get("/api/auth/me/client")
test("1.4 Reject no token", r.status_code in (401, 403), str(r.status_code))

r = api_post("/api/auth/register", {
    "email": email, "password": "TestPass123!",
    "company_name": "Dup Company", "phone_number": "+15551111111"
})
test("1.5 Reject duplicate email", r.status_code == 400, str(r.status_code))

# ============================================================
# 2. CAMPAIGN TESTS
# ============================================================
print("\n" + "=" * 60)
print("2. Campaign Tests")
print("=" * 60)

r = api_post("/api/campaigns", {
    "name": "E2E Campaign " + UNIQUE, "campaign_type": "ooh",
    "start_date": "2026-04-01T00:00:00", "end_date": "2026-06-30T23:59:59"
}, headers=auth)
test("2.1 Create campaign", r.status_code == 201, str(r.status_code) + ": " + r.text[:200])
campaign_id = safe_get(r, "campaign_id")
campaign_code = safe_get(r, "campaign_code")

r = api_get("/api/campaigns", headers=auth)
test("2.2 List campaigns", r.status_code == 200 and safe_get(r, "total", 0) >= 1,
     str(r.status_code) + ": total=" + str(safe_get(r, "total", 0)))

if campaign_id:
    r = api_get("/api/campaigns/" + str(campaign_id), headers=auth)
    test("2.3 Get campaign by ID", r.status_code == 200, str(r.status_code))
else:
    test("2.3 Get campaign by ID", False, "No campaign_id")

r = api_post("/api/campaigns", {
    "name": "Bad Type", "campaign_type": "invalid_type",
    "start_date": "2026-04-01T00:00:00", "end_date": "2026-06-30T23:59:59"
}, headers=auth)
test("2.4 Reject invalid campaign type", r.status_code == 422, str(r.status_code))

r = api_post("/api/campaigns", {
    "name": "E2E Campaign B " + UNIQUE, "campaign_type": "construction",
    "start_date": "2026-05-01T00:00:00", "end_date": "2026-12-31T23:59:59"
}, headers=auth)
test("2.5 Create second campaign", r.status_code == 201, str(r.status_code) + ": " + r.text[:200])
campaign_id_2 = safe_get(r, "campaign_id")


# ============================================================
# 3. VENDOR TESTS
# ============================================================
print("\n" + "=" * 60)
print("3. Vendor Tests")
print("=" * 60)

r = api_post("/api/vendors", {
    "name": "E2E Vendor " + UNIQUE,
    "phone_number": "+1666" + UNIQUE,
    "email": "vendor_" + UNIQUE + "@test.com"
}, headers=auth)
test("3.1 Create vendor", r.status_code == 201, str(r.status_code) + ": " + r.text[:200])
vendor_id = safe_get(r, "vendor_id")

r = api_post("/api/vendors", {
    "name": "E2E Vendor B " + UNIQUE,
    "phone_number": "+1777" + UNIQUE,
    "email": "vendorb_" + UNIQUE + "@test.com"
}, headers=auth)
test("3.2 Create second vendor", r.status_code == 201, str(r.status_code) + ": " + r.text[:200])
vendor_id_2 = safe_get(r, "vendor_id")

r = api_get("/api/vendors", headers=auth)
test("3.3 List vendors", r.status_code == 200 and safe_get(r, "total", 0) >= 2,
     str(r.status_code) + ": total=" + str(safe_get(r, "total", 0)))

if vendor_id:
    r = api_patch("/api/vendors/" + vendor_id, {"name": "Updated Vendor " + UNIQUE}, headers=auth)
    test("3.4 Update vendor", r.status_code == 200, str(r.status_code))
else:
    test("3.4 Update vendor", False, "No vendor_id")

# ============================================================
# 4. SINGLE ASSIGNMENT TESTS
# ============================================================
print("\n" + "=" * 60)
print("4. Single Assignment Tests")
print("=" * 60)

# Assign endpoint returns a plain JSON list, not wrapped in {"assignments": [...]}
# Duplicate assign returns 400 with {"detail": "..."}

if campaign_id and vendor_id:
    r = api_post("/api/campaigns/" + str(campaign_id) + "/vendors",
                 {"vendor_ids": [vendor_id]}, headers=auth)
    test("4.1 Assign vendor to campaign", r.status_code == 201 and resp_list_len(r) >= 1,
         str(r.status_code) + ": " + r.text[:200])
else:
    test("4.1 Assign vendor to campaign", False, "Missing campaign_id or vendor_id")

if campaign_id and vendor_id_2:
    r = api_post("/api/campaigns/" + str(campaign_id) + "/vendors", {
        "vendor_ids": [vendor_id_2],
        "location": {"address": "123 Test St, New York, NY",
                     "latitude": 40.7128, "longitude": -74.0060, "name": "Test Location"}
    }, headers=auth)
    test("4.2 Assign with location", r.status_code == 201 and resp_list_len(r) >= 1,
         str(r.status_code) + ": " + r.text[:200])
else:
    test("4.2 Assign with location", False, "Missing campaign_id or vendor_id_2")

if campaign_id and vendor_id:
    r = api_post("/api/campaigns/" + str(campaign_id) + "/vendors",
                 {"vendor_ids": [vendor_id]}, headers=auth)
    test("4.3 Duplicate assignment prevention", r.status_code == 400,
         str(r.status_code) + ": " + r.text[:200])
else:
    test("4.3 Duplicate assignment prevention", False, "Missing campaign_id or vendor_id")

if campaign_id:
    r = api_get("/api/campaigns/" + str(campaign_id) + "/vendors", headers=auth)
    test("4.4 Query by campaign", r.status_code == 200 and safe_get(r, "total", 0) >= 2,
         str(r.status_code) + ": total=" + str(safe_get(r, "total", 0)))
else:
    test("4.4 Query by campaign", False, "Missing campaign_id")

if vendor_id:
    r = api_get("/api/vendors/" + vendor_id + "/campaigns", headers=auth)
    test("4.5 Query by vendor", r.status_code == 200 and safe_get(r, "total", 0) >= 1,
         str(r.status_code) + ": total=" + str(safe_get(r, "total", 0)))
else:
    test("4.5 Query by vendor", False, "Missing vendor_id")

if campaign_id and vendor_id_2:
    r = api_delete("/api/campaigns/" + str(campaign_id) + "/vendors/" + vendor_id_2, headers=auth)
    test("4.6 Unassign vendor", r.status_code == 204, str(r.status_code))
else:
    test("4.6 Unassign vendor", False, "Missing campaign_id or vendor_id_2")

vid = vendor_id if vendor_id else "AAAAAA"
r = api_post("/api/campaigns/00000000-0000-0000-0000-000000000000/vendors",
             {"vendor_ids": [vid]}, headers=auth)
test("4.7 Reject non-existent campaign", r.status_code == 404, str(r.status_code))


# ============================================================
# 5. BULK UPLOAD TESTS
# ============================================================
print("\n" + "=" * 60)
print("5. Bulk Upload Tests")
print("=" * 60)

r = api_get("/api/bulk/campaigns/template", headers=auth)
test("5.1 Campaign template download", r.status_code == 200, str(r.status_code))

r = api_get("/api/bulk/vendors/template", headers=auth)
test("5.2 Vendor template download", r.status_code == 200, str(r.status_code))

r = api_get("/api/bulk/assignments/template", headers=auth)
test("5.3 Assignment template download", r.status_code == 200, str(r.status_code))

csv_c = "name,campaign_type,start_date,end_date\nBulk Camp A " + UNIQUE + ",ooh,2026-07-01,2026-09-30\nBulk Camp B " + UNIQUE + ",construction,2026-08-01,2026-10-31\n"
files = {"file": ("campaigns.csv", io.BytesIO(csv_c.encode()), "text/csv")}
r = api_post("/api/bulk/campaigns", headers=auth, files=files)
test("5.4 Bulk campaign upload", r.status_code == 200 and safe_get(r, "successful", 0) == 2,
     str(r.status_code) + ": " + r.text[:300])
bulk_camp_data = r.json() if r.status_code == 200 else {}

csv_dup = "name,campaign_type,start_date,end_date\nBulk Camp A " + UNIQUE + ",ooh,2026-07-01,2026-09-30\n"
files = {"file": ("campaigns.csv", io.BytesIO(csv_dup.encode()), "text/csv")}
r = api_post("/api/bulk/campaigns", headers=auth, files=files)
test("5.5 Bulk campaign duplicates", r.status_code == 200 and safe_get(r, "failed", 0) >= 1,
     str(r.status_code) + ": " + r.text[:300])

csv_v = "name,phone_number,email\nBulk Vendor A " + UNIQUE + ",+1888" + UNIQUE + ",bva_" + UNIQUE + "@test.com\nBulk Vendor B " + UNIQUE + ",+1999" + UNIQUE + ",bvb_" + UNIQUE + "@test.com\n"
files = {"file": ("vendors.csv", io.BytesIO(csv_v.encode()), "text/csv")}
r = api_post("/api/bulk/vendors", headers=auth, files=files)
test("5.6 Bulk vendor upload", r.status_code == 200 and safe_get(r, "successful", 0) == 2,
     str(r.status_code) + ": " + r.text[:300])

bulk_vendor_ids = []
if r.status_code == 200:
    for row in r.json().get("results", []):
        if row.get("status") == "success" and row.get("data", {}).get("vendor_id"):
            bulk_vendor_ids.append(row["data"]["vendor_id"])

bulk_camp_codes = []
if isinstance(bulk_camp_data, dict):
    for row in bulk_camp_data.get("results", []):
        if row.get("status") == "success" and row.get("data", {}).get("campaign_code"):
            bulk_camp_codes.append(row["data"]["campaign_code"])

if len(bulk_camp_codes) >= 1 and len(bulk_vendor_ids) >= 1:
    csv_a = "campaign_code,vendor_id\n" + bulk_camp_codes[0] + "," + bulk_vendor_ids[0] + "\n"
    files = {"file": ("assignments.csv", io.BytesIO(csv_a.encode()), "text/csv")}
    r = api_post("/api/bulk/assignments", headers=auth, files=files)
    test("5.7 Bulk assignment upload", r.status_code == 200 and safe_get(r, "successful", 0) >= 1,
         str(r.status_code) + ": " + r.text[:300])
else:
    test("5.7 Bulk assignment upload", False,
         "Missing bulk data: camps=" + str(len(bulk_camp_codes)) + " vendors=" + str(len(bulk_vendor_ids)))

csv_bad = "name,phone_number,email\n,badphone,notanemail\n"
files = {"file": ("vendors.csv", io.BytesIO(csv_bad.encode()), "text/csv")}
r = api_post("/api/bulk/vendors", headers=auth, files=files)
test("5.8 Bulk validation errors", r.status_code == 200 and safe_get(r, "failed", 0) >= 1,
     str(r.status_code) + ": " + r.text[:300])

files = {"file": ("data.txt", io.BytesIO(b"not a csv"), "text/plain")}
r = api_post("/api/bulk/campaigns", headers=auth, files=files)
test("5.9 Reject non-CSV file", r.status_code == 400, str(r.status_code))


# ============================================================
# 6. ADMIN DASHBOARD TESTS
# ============================================================
print("\n" + "=" * 60)
print("6. Admin Dashboard Tests")
print("=" * 60)

r = api_post("/api/admin/login", {"email": "admin@trustcapture.com", "password": "TrustAdmin@2026"})
test("6.1 Admin login", r.status_code == 200 and safe_get(r, "access_token"),
     str(r.status_code))
admin_token = safe_get(r, "access_token", "")
admin_auth = {"Authorization": "Bearer " + admin_token} if admin_token else {}

r = api_post("/api/admin/login", {"email": "admin@trustcapture.com", "password": "wrong"})
test("6.2 Reject wrong admin password", r.status_code == 401, str(r.status_code))

r = api_get("/api/admin/dashboard", headers=admin_auth)
overview = safe_get(r, "overview", {})
test("6.3 Admin dashboard metrics",
     r.status_code == 200 and overview.get("total_clients", 0) > 0,
     str(r.status_code) + ": clients=" + str(overview.get("total_clients", 0)))

r = api_get("/api/admin/me", headers=admin_auth)
test("6.4 Admin profile",
     r.status_code == 200 and safe_get(r, "email") == "admin@trustcapture.com",
     str(r.status_code))

r = api_get("/api/admin/dashboard", headers=auth)
test("6.5 Client token rejected on admin", r.status_code == 401, str(r.status_code))

# ============================================================
# 7. ERROR HANDLING TESTS
# ============================================================
print("\n" + "=" * 60)
print("7. Error Handling Tests")
print("=" * 60)

r = requests.post(BASE + "/api/auth/login", data="not json", headers={"Content-Type": "application/json"})
test("7.1 Reject invalid JSON", r.status_code == 422, str(r.status_code))

r = api_post("/api/campaigns", {"name": "No dates"}, headers=auth)
test("7.2 Reject missing required fields", r.status_code == 422, str(r.status_code))

r = api_get("/api/campaigns/not-a-uuid", headers=auth)
test("7.3 Reject invalid UUID in path", r.status_code == 422, str(r.status_code))

r = api_get("/api/auth/me/client", headers={"Authorization": "Bearer invalid.token.here"})
test("7.4 Reject invalid JWT token", r.status_code == 401, str(r.status_code))

# ============================================================
# 8. DATABASE INTEGRITY TESTS
# ============================================================
print("\n" + "=" * 60)
print("8. Database Integrity Tests")
print("=" * 60)

r = api_get("/api/campaigns", headers=auth)
total = safe_get(r, "total", 0)
test("8.1 Campaign count", r.status_code == 200 and total >= 4,
     "Expected >= 4, got " + str(total))

r = api_get("/api/vendors", headers=auth)
total = safe_get(r, "total", 0)
test("8.2 Vendor count", r.status_code == 200 and total >= 4,
     "Expected >= 4, got " + str(total))

# ============================================================
print("\n" + "=" * 60)
print("TEST RESULTS")
print("Passed: " + str(passed))
print("Failed: " + str(failed))
print("Total:  " + str(passed + failed))
print("=" * 60)

if failures:
    print("\nFailed tests:")
    for f in failures:
        print("  \u274c " + f)

sys.exit(0 if failed == 0 else 1)
