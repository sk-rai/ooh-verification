-- Reset TrustCapture database password
-- Run this with: sudo -u postgres psql -f reset_db_password.sql

-- Reset password for trustcapture user
ALTER USER trustcapture WITH PASSWORD 'dev_password_123';

-- Verify user exists and has correct permissions
\du trustcapture

-- Show databases
\l trustcapture_db

-- Grant all privileges (in case they were missing)
GRANT ALL PRIVILEGES ON DATABASE trustcapture_db TO trustcapture;

-- Success message
\echo 'Password reset complete! User: trustcapture, Password: dev_password_123'
