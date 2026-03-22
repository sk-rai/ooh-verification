#!/usr/bin/env python3
"""Test the subscription endpoint directly."""

import asyncio
import httpx
import sys

async def test_subscription():
    base_url = "http://localhost:8000"
    tenant_id = "e27c6c7a-7f5b-43df-bdc4-abd76ebb99aa"
    
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        # Register a new user
        email = f"subtest_{asyncio.get_event_loop().time()}@example.com"
        reg_data = {
            "email": email,
            "password": "Test123!@#",
            "company_name": "Sub Test Co",
            "phone_number": "+1234567890"
        }
        
        print(f"1. Registering user: {email}")
        reg_resp = await client.post(
            "/api/auth/register",
            json=reg_data,
            headers={"X-Tenant-ID": tenant_id}
        )
        print(f"   Status: {reg_resp.status_code}")
        if reg_resp.status_code != 201:
            print(f"   Error: {reg_resp.text}")
            return False
        
        # Login
        print(f"\n2. Logging in...")
        login_resp = await client.post(
            "/api/auth/login",
            json={"email": email, "password": "Test123!@#"},
            headers={"X-Tenant-ID": tenant_id}
        )
        print(f"   Status: {login_resp.status_code}")
        if login_resp.status_code != 200:
            print(f"   Error: {login_resp.text}")
            return False
        
        token = login_resp.json()["access_token"]
        print(f"   Token: {token[:20]}...")
        
        # Get subscription
        print(f"\n3. Getting subscription...")
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Tenant-ID": tenant_id
        }
        
        sub_resp = await client.get("/api/subscriptions/current", headers=headers)
        print(f"   Status: {sub_resp.status_code}")
        print(f"   Response: {sub_resp.text[:500]}")
        
        if sub_resp.status_code == 200:
            data = sub_resp.json()
            print(f"\n4. Checking fields...")
            print(f"   Has 'tier': {'tier' in data}")
            print(f"   Has 'photos_quota': {'photos_quota' in data}")
            print(f"   Has 'vendors_quota': {'vendors_quota' in data}")
            print(f"   Has 'campaigns_quota': {'campaigns_quota' in data}")
            
            if 'photos_quota' in data:
                print(f"\n✓ SUCCESS! Subscription endpoint returns quota fields")
                return True
            else:
                print(f"\n✗ FAIL: Missing quota fields")
                return False
        else:
            print(f"\n✗ FAIL: Subscription endpoint returned {sub_resp.status_code}")
            return False

if __name__ == "__main__":
    result = asyncio.run(test_subscription())
    sys.exit(0 if result else 1)
