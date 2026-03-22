-- Create a test client for API testing
INSERT INTO clients (
    client_id,
    email,
    password_hash,
    company_name,
    phone_number,
    subscription_tier,
    subscription_status,
    created_at,
    updated_at
) VALUES (
    '00000000-0000-0000-0000-000000000001',
    'test@trustcapture.com',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYzS3MebfeW',
    'Test Company',
    '+919876543210',
    'free',
    'active',
    NOW(),
    NOW()
) ON CONFLICT (client_id) DO NOTHING;

-- Create subscription for test client
INSERT INTO subscriptions (
    subscription_id,
    client_id,
    tier,
    status,
    billing_cycle,
    amount,
    currency,
    auto_renew,
    photos_quota,
    photos_used,
    vendors_quota,
    vendors_used,
    campaigns_quota,
    campaigns_used,
    storage_quota_mb,
    storage_used_mb,
    current_period_start,
    current_period_end,
    created_at,
    updated_at
) VALUES (
    '00000000-0000-0000-0000-000000000002',
    '00000000-0000-0000-0000-000000000001',
    'free',
    'active',
    'monthly',
    0,
    'INR',
    1,
    50,
    0,
    2,
    0,
    1,
    0,
    500,
    0,
    NOW(),
    NOW() + INTERVAL '30 days',
    NOW(),
    NOW()
) ON CONFLICT (subscription_id) DO NOTHING;

SELECT 'Test client created successfully!' as message;
