-- Direct SQL setup for TrustCapture database
-- This bypasses Alembic to avoid caching issues

-- Drop existing types if they exist
DROP TYPE IF EXISTS subscriptiontier CASCADE;
DROP TYPE IF EXISTS subscriptionstatus CASCADE;
DROP TYPE IF EXISTS vendorstatus CASCADE;
DROP TYPE IF EXISTS campaigntype CASCADE;
DROP TYPE IF EXISTS campaignstatus CASCADE;
DROP TYPE IF EXISTS verificationstatus CASCADE;

-- Create enum types
CREATE TYPE subscriptiontier AS ENUM ('free', 'pro', 'enterprise');
CREATE TYPE subscriptionstatus AS ENUM ('active', 'cancelled', 'expired', 'past_due');
CREATE TYPE vendorstatus AS ENUM ('active', 'inactive');
CREATE TYPE campaigntype AS ENUM ('ooh', 'construction', 'insurance', 'delivery', 'healthcare', 'property_management');
CREATE TYPE campaignstatus AS ENUM ('active', 'completed', 'cancelled');
CREATE TYPE verificationstatus AS ENUM ('pending', 'verified', 'flagged', 'rejected');

-- Now stamp Alembic to mark migrations as applied
-- Run this after: python3 -m alembic stamp head
