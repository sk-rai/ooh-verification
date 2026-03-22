-- Manual SQL to add campaign_locations table
-- Run this if alembic migration fails

-- Create campaign_locations table
CREATE TABLE IF NOT EXISTS campaign_locations (
    location_id UUID NOT NULL,
    campaign_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    address VARCHAR(500) NOT NULL,
    city VARCHAR(100),
    state VARCHAR(100),
    country VARCHAR(100),
    postal_code VARCHAR(20),
    latitude FLOAT NOT NULL,
    longitude FLOAT NOT NULL,
    verification_radius_meters INTEGER DEFAULT 100 NOT NULL,
    geocoding_accuracy VARCHAR(50),
    place_id VARCHAR(255),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (location_id),
    FOREIGN KEY(campaign_id) REFERENCES campaigns (campaign_id) ON DELETE CASCADE
);

-- Create indexes
CREATE INDEX IF NOT EXISTS ix_campaign_locations_location_id ON campaign_locations(location_id);
CREATE INDEX IF NOT EXISTS ix_campaign_locations_campaign_id ON campaign_locations(campaign_id);
CREATE INDEX IF NOT EXISTS ix_campaign_locations_latitude ON campaign_locations(latitude);
CREATE INDEX IF NOT EXISTS ix_campaign_locations_longitude ON campaign_locations(longitude);
CREATE INDEX IF NOT EXISTS ix_campaign_locations_coords ON campaign_locations(latitude, longitude);

-- Update alembic version
UPDATE alembic_version SET version_num = '004_campaign_locations';

-- Verify
SELECT 'campaign_locations table created successfully!' as status;
SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename='campaign_locations';
