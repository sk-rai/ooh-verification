#!/bin/bash
# Install payment gateway SDKs for Task 15

echo "📦 Installing Payment Gateway SDKs..."
echo ""

# Install Razorpay
echo "Installing Razorpay SDK..."
pip install razorpay==1.4.1

# Stripe should already be installed, but verify
echo "Verifying Stripe SDK..."
pip install stripe==7.11.0

echo ""
echo "✅ Payment SDKs installed successfully!"
echo ""
echo "Next steps:"
echo "1. Set up Razorpay account at https://razorpay.com"
echo "2. Create subscription plans in Razorpay dashboard"
echo "3. Add credentials to .env file"
echo "4. Configure webhooks"
echo ""
echo "See backend/RAZORPAY_SETUP.md for detailed instructions"
