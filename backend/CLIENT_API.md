# Client Management API Documentation

## Overview

The Client Management API provides endpoints for managing client profiles and subscriptions in the TrustCapture system.

## Base URL

```
http://localhost:8000/api/clients
```

## Authentication

All endpoints require JWT authentication. Include the token in the Authorization header:

```
Authorization: Bearer <your_jwt_token>
```

## Endpoints

### Get Current Client Profile

Retrieve the authenticated client's profile information.

**Endpoint:** `GET /api/clients/me`

**Authentication:** Required (Client JWT)

**Response:** `200 OK`

```json
{
  "client_id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "client@example.com",
  "company_name": "Acme Corporation",
  "phone_number": "+1234567890",
  "subscription_tier": "pro",
  "subscription_status": "active",
  "created_at": "2026-03-04T12:00:00Z",
  "updated_at": "2026-03-04T12:00:00Z"
}
```

**Requirements Covered:**
- Req 1.1: Client profile access
- Req 1.2: Subscription information

---

### Update Client Profile

Update the authenticated client's profile information.

**Endpoint:** `PATCH /api/clients/me`

**Authentication:** Required (Client JWT)

**Request Body:**

```json
{
  "company_name": "Updated Company Name",
  "phone_number": "+1987654321"
}
```

**Note:** All fields are optional. Only provided fields will be updated.

**Response:** `200 OK`

```json
{
  "client_id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "client@example.com",
  "company_name": "Updated Company Name",
  "phone_number": "+1987654321",
  "subscription_tier": "pro",
  "subscription_status": "active",
  "created_at": "2026-03-04T12:00:00Z",
  "updated_at": "2026-03-04T14:30:00Z"
}
```

**Requirements Covered:**
- Req 1.1: Client profile management

---

### Get Current Subscription

Retrieve the authenticated client's subscription details including usage statistics.

**Endpoint:** `GET /api/clients/me/subscription`

**Authentication:** Required (Client JWT)

**Response:** `200 OK`

```json
{
  "subscription_id": "550e8400-e29b-41d4-a716-446655440001",
  "client_id": "550e8400-e29b-41d4-a716-446655440000",
  "tier": "pro",
  "status": "active",
  "photos_quota": -1,
  "photos_used": 150,
  "current_period_start": "2026-03-01T00:00:00Z",
  "current_period_end": "2026-04-01T00:00:00Z",
  "stripe_subscription_id": "sub_1234567890",
  "stripe_customer_id": "cus_1234567890",
  "created_at": "2026-03-01T00:00:00Z",
  "updated_at": "2026-03-04T12:00:00Z"
}
```

**Subscription Tiers:**
- `free`: 50 photos/month quota
- `pro`: Unlimited photos (quota = -1)
- `enterprise`: Unlimited photos (quota = -1)

**Requirements Covered:**
- Req 1.2: Subscription tier information
- Usage tracking and quota management

---

## Error Responses

### 401 Unauthorized

```json
{
  "detail": "Could not validate credentials"
}
```

### 403 Forbidden

```json
{
  "detail": "Client subscription is suspended"
}
```

### 404 Not Found

```json
{
  "detail": "Subscription not found"
}
```

---

## Example Usage

### Using cURL

```bash
# Get client profile
curl -X GET http://localhost:8000/api/clients/me \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Update client profile
curl -X PATCH http://localhost:8000/api/clients/me \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"company_name": "New Company Name"}'

# Get subscription details
curl -X GET http://localhost:8000/api/clients/me/subscription \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Using Python (requests)

```python
import requests

BASE_URL = "http://localhost:8000"
token = "YOUR_JWT_TOKEN"
headers = {"Authorization": f"Bearer {token}"}

# Get client profile
response = requests.get(f"{BASE_URL}/api/clients/me", headers=headers)
client = response.json()
print(f"Client: {client['email']}")

# Update profile
update_data = {"company_name": "New Company Name"}
response = requests.patch(
    f"{BASE_URL}/api/clients/me",
    headers=headers,
    json=update_data
)
updated_client = response.json()
print(f"Updated: {updated_client['company_name']}")

# Get subscription
response = requests.get(
    f"{BASE_URL}/api/clients/me/subscription",
    headers=headers
)
subscription = response.json()
print(f"Tier: {subscription['tier']}, Used: {subscription['photos_used']}/{subscription['photos_quota']}")
```

---

## Testing

To test these endpoints, first obtain a JWT token by logging in:

```bash
# Login to get token
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "client@example.com",
    "password": "SecurePass123"
  }'
```

The response will include an `access_token` that you can use for authenticated requests.

---

## Related Documentation

- [Authentication API](AUTH_IMPLEMENTATION.md) - Login and registration endpoints
- [Database Schema](DATABASE.md) - Client and subscription table structures
- [Quick Start Guide](QUICKSTART.md) - Setup and development guide
