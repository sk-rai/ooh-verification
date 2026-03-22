#!/usr/bin/env python3
"""
Manual test script for authentication endpoints.

Run this after starting the server with: uvicorn app.main:app --reload
"""
import requests
import json

BASE_URL = "http://localhost:8000"


def test_health():
    """Test health check endpoint."""
    print("\n🔍 Testing health check...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200
    print("✅ Health check passed")


def test_client_registration():
    """Test client registration."""
    print("\n🔍 Testing client registration...")
    
    data = {
        "email": "test@example.com",
        "password": "SecurePass123",
        "company_name": "Test Company",
        "phone_number": "+1234567890"
    }
    
    response = requests.post(f"{BASE_URL}/api/auth/register", json=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 201:
        print("✅ Client registration successful")
        return response.json()
    elif response.status_code == 400 and "already registered" in response.json().get("detail", ""):
        print("ℹ️  Client already exists, continuing...")
        return None
    else:
        print(f"❌ Registration failed: {response.json()}")
        return None


def test_client_login():
    """Test client login."""
    print("\n🔍 Testing client login...")
    
    data = {
        "email": "test@example.com",
        "password": "SecurePass123"
    }
    
    response = requests.post(f"{BASE_URL}/api/auth/login", json=data)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Login successful")
        print(f"Token: {result['access_token'][:50]}...")
        print(f"Expires in: {result['expires_in']} seconds")
        return result['access_token']
    else:
        print(f"❌ Login failed: {response.json()}")
        return None


def test_vendor_otp_flow():
    """Test vendor OTP flow (requires vendor in database)."""
    print("\n🔍 Testing vendor OTP flow...")
    print("ℹ️  This requires a vendor to exist in the database")
    print("ℹ️  Run: python scripts/db_setup.py seed")
    
    # Step 1: Request OTP
    print("\n📱 Step 1: Requesting OTP...")
    data = {
        "phone_number": "+1234567891",
        "vendor_id": "ABC123"
    }
    
    response = requests.post(f"{BASE_URL}/api/auth/vendor/request-otp", json=data)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        print(f"✅ OTP requested successfully")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        print("\n⚠️  Check server console for OTP (development mode)")
        
        # In production, OTP would be sent via SMS
        # For testing, you'd need to check the server logs
        otp = input("\nEnter OTP from server logs: ")
        
        # Step 2: Verify OTP
        print("\n🔐 Step 2: Verifying OTP...")
        verify_data = {
            "phone_number": "+1234567891",
            "vendor_id": "ABC123",
            "otp": otp,
            "device_id": "test-device-123"
        }
        
        response = requests.post(f"{BASE_URL}/api/auth/vendor/verify-otp", json=verify_data)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ OTP verification successful")
            print(f"Token: {result['access_token'][:50]}...")
            return result['access_token']
        else:
            print(f"❌ OTP verification failed: {response.json()}")
            return None
    else:
        print(f"❌ OTP request failed: {response.json()}")
        return None


def main():
    """Run all tests."""
    print("=" * 60)
    print("TrustCapture Authentication Tests")
    print("=" * 60)
    
    try:
        # Test health
        test_health()
        
        # Test client flow
        test_client_registration()
        client_token = test_client_login()
        
        if client_token:
            print(f"\n✅ Client authentication flow working!")
        
        # Test vendor flow (optional, requires seeded data)
        print("\n" + "=" * 60)
        test_vendor = input("\nTest vendor OTP flow? (requires seeded data) [y/N]: ")
        if test_vendor.lower() == 'y':
            vendor_token = test_vendor_otp_flow()
            if vendor_token:
                print(f"\n✅ Vendor authentication flow working!")
        
        print("\n" + "=" * 60)
        print("✅ All tests completed!")
        print("=" * 60)
        
    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Could not connect to server")
        print("Make sure the server is running:")
        print("  uvicorn app.main:app --reload")
    except Exception as e:
        print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    main()
