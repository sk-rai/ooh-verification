# Razorpay Integration Setup Guide

## Overview
This guide explains how to set up Razorpay for accepting payments from Indian customers via UPI, cards, wallets, and net banking.

## Prerequisites
- Razorpay account (sign up at https://razorpay.com)
- Business verification completed (for live mode)
- Bank account linked

## Step 1: Get API Credentials

### Test Mode (for development)
1. Log in to Razorpay Dashboard
2. Go to Settings → API Keys
3. Generate Test API Keys
4. Copy Key ID and Key Secret

### Live Mode (for production)
1. Complete business verification
2. Go to Settings → API Keys
3. Generate Live API Keys
4. Copy Key ID and Key Secret

## Step 2: Create Subscription Plans

### In Razorpay Dashboard:
1. Go to Subscriptions → Plans
2. Create the following plans:

#### Pro Monthly Plan
- Plan Name: TrustCapture Pro Monthly
- Plan ID: `plan_pro_monthly`
- Billing Interval: Monthly
- Amount: ₹999
- Currency: INR

#### Pro Yearly Plan
- Plan Name: TrustCapture Pro Yearly
- Plan ID: `plan_pro_yearly`
- Billing Interval: Yearly
- Amount: ₹9,990 (2 months free)
- Currency: INR

#### Enterprise Monthly Plan
- Plan Name: TrustCapture Enterprise Monthly
- Plan ID: `plan_enterprise_monthly`
- Billing Interval: Monthly
- Amount: ₹4,999
- Currency: INR

#### Enterprise Yearly Plan
- Plan Name: TrustCapture Enterprise Yearly
- Plan ID: `plan_enterprise_yearly`
- Billing Interval: Yearly
- Amount: ₹49,990 (2 months free)
- Currency: INR

## Step 3: Configure Environment Variables

Add to your `.env` file:

```bash
# Razorpay Configuration
RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxxxxx
RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxxxxxxx
RAZORPAY_WEBHOOK_SECRET=xxxxxxxxxxxxxxxxxxxxx

# Plan IDs (optional - defaults to plan_xxx format)
RAZORPAY_PLAN_PRO_MONTHLY=plan_pro_monthly
RAZORPAY_PLAN_PRO_YEARLY=plan_pro_yearly
RAZORPAY_PLAN_ENTERPRISE_MONTHLY=plan_enterprise_monthly
RAZORPAY_PLAN_ENTERPRISE_YEARLY=plan_enterprise_yearly
```

## Step 4: Set Up Webhooks

### Configure Webhook URL:
1. Go to Settings → Webhooks
2. Add Webhook URL: `https://yourdomain.com/api/webhooks/razorpay`
3. Select Events:
   - `subscription.activated`
   - `subscription.charged`
   - `subscription.completed`
   - `subscription.cancelled`
   - `subscription.paused`
   - `subscription.resumed`
   - `payment.failed`
4. Copy Webhook Secret and add to `.env`

### Test Webhook:
```bash
curl -X POST https://yourdomain.com/api/webhooks/razorpay \
  -H "Content-Type: application/json" \
  -H "X-Razorpay-Signature: test_signature" \
  -d '{"event": "subscription.activated", "payload": {}}'
```

## Step 5: Install Dependencies

```bash
cd backend
pip install razorpay==1.4.1
```

Or add to requirements.txt:
```
razorpay==1.4.1
```

## Step 6: Test Integration

### Test Subscription Creation:
```python
from app.services.razorpay_service import get_razorpay_service
from app.models.client import SubscriptionTier

razorpay_service = get_razorpay_service()

# Create subscription
result = await razorpay_service.create_subscription(
    db=db,
    client_id=client_id,
    tier=SubscriptionTier.PRO,
    billing_cycle="monthly"
)

print(f"Payment link: {result['short_url']}")
```

### Test Payment Methods:

#### UPI Payment:
- Use test UPI ID: `success@razorpay`
- This will simulate successful payment

#### Card Payment:
Test cards:
- Success: `4111 1111 1111 1111`
- Failure: `4000 0000 0000 0002`
- CVV: Any 3 digits
- Expiry: Any future date

#### Net Banking:
- Select any bank
- Use test credentials provided by Razorpay

## Step 7: Go Live

### Checklist:
- [ ] Business verification completed
- [ ] Bank account verified
- [ ] Live API keys generated
- [ ] Live plans created
- [ ] Webhook URL updated to production
- [ ] Environment variables updated with live keys
- [ ] Test all payment methods in live mode
- [ ] Set up monitoring and alerts

### Update Environment:
```bash
# Production .env
RAZORPAY_KEY_ID=rzp_live_xxxxxxxxxxxxx
RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxxxxxxx
RAZORPAY_WEBHOOK_SECRET=xxxxxxxxxxxxxxxxxxxxx
```

## Payment Flow

### 1. Customer Selects Plan
```
Client → API → Create Subscription → Razorpay
```

### 2. Customer Pays
```
Razorpay Payment Page → UPI/Card/Wallet/NetBanking → Payment Success
```

### 3. Webhook Notification
```
Razorpay → Webhook → Update Database → Activate Subscription
```

### 4. Subscription Active
```
Customer can now use Pro/Enterprise features
```

## Supported Payment Methods

### UPI (Unified Payments Interface)
- Google Pay
- PhonePe
- Paytm
- BHIM
- Any UPI app

### Cards
- Credit Cards: Visa, Mastercard, RuPay, American Express
- Debit Cards: Visa, Mastercard, RuPay, Maestro

### Wallets
- Paytm
- PhonePe
- Mobikwik
- Freecharge
- Ola Money

### Net Banking
- All major Indian banks
- 50+ banks supported

## Pricing

### Transaction Fees:
- Domestic payments: 2%
- International payments: 3% + ₹2
- No setup fees
- No annual fees

### Settlement:
- T+3 days to Indian bank accounts
- Automatic settlement daily

## Security

### PCI DSS Compliance:
- Razorpay is PCI DSS Level 1 certified
- No card data stored on your servers
- All transactions encrypted

### Fraud Detection:
- Built-in fraud detection
- 3D Secure authentication
- Risk scoring

## Troubleshooting

### Common Issues:

#### 1. Invalid API Key
```
Error: Authentication failed
Solution: Check RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in .env
```

#### 2. Plan Not Found
```
Error: Plan ID not found
Solution: Verify plan IDs in Razorpay dashboard match .env configuration
```

#### 3. Webhook Signature Verification Failed
```
Error: Invalid signature
Solution: Check RAZORPAY_WEBHOOK_SECRET matches dashboard configuration
```

#### 4. Payment Failed
```
Error: Payment declined
Solution: Use test cards/UPI for testing, check customer's payment method in production
```

## Support

### Razorpay Support:
- Email: support@razorpay.com
- Phone: +91-80-6890-6890
- Documentation: https://razorpay.com/docs/

### Integration Support:
- Check logs: `tail -f logs/razorpay.log`
- Test webhook: Use Razorpay webhook tester
- Contact: your-support-email@trustcapture.com

## References

- Razorpay API Documentation: https://razorpay.com/docs/api/
- Subscriptions Guide: https://razorpay.com/docs/subscriptions/
- Webhook Events: https://razorpay.com/docs/webhooks/
- Test Cards: https://razorpay.com/docs/payments/payments/test-card-details/
