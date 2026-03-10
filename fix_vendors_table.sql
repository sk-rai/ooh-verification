-- Fix vendors table - add missing timestamp columns
-- This adds created_at, updated_at, and last_login_at columns that are defined in the model

-- Add created_at column
ALTER TABLE vendors ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW();

-- Add updated_at column
ALTER TABLE vendors ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();

-- Add last_login_at column
ALTER TABLE vendors ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMP;

-- Update existing rows to have proper timestamps
UPDATE vendors SET created_at = NOW() WHERE created_at IS NULL;
UPDATE vendors SET updated_at = NOW() WHERE updated_at IS NULL;

-- Make created_at and updated_at NOT NULL
ALTER TABLE vendors ALTER COLUMN created_at SET NOT NULL;
ALTER TABLE vendors ALTER COLUMN updated_at SET NOT NULL;

-- Verify the changes
\d vendors
