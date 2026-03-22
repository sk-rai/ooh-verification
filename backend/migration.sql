INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Generating static SQL
INFO  [alembic.runtime.migration] Will assume transactional DDL.
BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

INFO  [alembic.runtime.migration] Running upgrade  -> 001_initial, Initial database schema
-- Running upgrade  -> 001_initial

CREATE TYPE subscriptiontier AS ENUM ('free', 'pro', 'enterprise');

CREATE TYPE subscriptionstatus AS ENUM ('active', 'cancelled', 'expired', 'past_due');

CREATE TABLE clients (
    client_id UUID NOT NULL, 
    email VARCHAR(255) NOT NULL, 
    password_hash VARCHAR(255) NOT NULL, 
    company_name VARCHAR(255) NOT NULL, 
    phone_number VARCHAR(20) NOT NULL, 
    subscription_tier subscriptiontier NOT NULL, 
    subscription_status subscriptionstatus NOT NULL, 
    stripe_customer_id VARCHAR(255), 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (client_id), 
    UNIQUE (email), 
    UNIQUE (stripe_customer_id)
);

CREATE INDEX idx_clients_email ON clients (email);

CREATE INDEX idx_clients_subscription ON clients (subscription_tier, subscription_status);

CREATE TYPE vendorstatus AS ENUM ('active', 'inactive');

CREATE TABLE vendors (
    vendor_id VARCHAR(6) NOT NULL, 
    name VARCHAR(255) NOT NULL, 
    phone_number VARCHAR(20) NOT NULL, 
    email VARCHAR(255), 
    status vendorstatus NOT NULL, 
    created_by_client_id UUID NOT NULL, 
    device_id VARCHAR(255), 
    public_key VARCHAR, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    last_login_at TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (vendor_id), 
    FOREIGN KEY(created_by_client_id) REFERENCES clients (client_id) ON DELETE CASCADE, 
    UNIQUE (device_id)
);

CREATE INDEX idx_vendors_client ON vendors (created_by_client_id);

CREATE INDEX idx_vendors_phone ON vendors (phone_number);

CREATE INDEX idx_vendors_status ON vendors (status);

CREATE TYPE campaigntype AS ENUM ('ooh', 'construction', 'insurance', 'delivery', 'healthcare', 'property_management');

CREATE TYPE campaignstatus AS ENUM ('active', 'completed', 'cancelled');

CREATE TABLE campaigns (
    campaign_id UUID NOT NULL, 
    campaign_code VARCHAR(50) NOT NULL, 
    name VARCHAR(255) NOT NULL, 
    campaign_type campaigntype NOT NULL, 
    client_id UUID NOT NULL, 
    start_date TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    end_date TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    status campaignstatus NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (campaign_id), 
    FOREIGN KEY(client_id) REFERENCES clients (client_id) ON DELETE CASCADE, 
    UNIQUE (campaign_code)
);

CREATE INDEX idx_campaigns_client ON campaigns (client_id);

CREATE INDEX idx_campaigns_code ON campaigns (campaign_code);

CREATE INDEX idx_campaigns_dates ON campaigns (start_date, end_date);

CREATE TABLE location_profiles (
    profile_id UUID NOT NULL, 
    campaign_id UUID NOT NULL, 
    expected_latitude FLOAT(10) NOT NULL, 
    expected_longitude FLOAT(10) NOT NULL, 
    tolerance_meters FLOAT NOT NULL, 
    expected_wifi_bssids VARCHAR[], 
    expected_cell_tower_ids INTEGER[], 
    expected_pressure_min FLOAT, 
    expected_pressure_max FLOAT, 
    expected_light_min FLOAT, 
    expected_light_max FLOAT, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (profile_id), 
    FOREIGN KEY(campaign_id) REFERENCES campaigns (campaign_id) ON DELETE CASCADE, 
    UNIQUE (campaign_id)
);

CREATE INDEX idx_location_profiles_campaign ON location_profiles (campaign_id);

CREATE TABLE campaign_vendor_assignments (
    assignment_id UUID NOT NULL, 
    campaign_id UUID NOT NULL, 
    vendor_id VARCHAR(6) NOT NULL, 
    assigned_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (assignment_id), 
    FOREIGN KEY(campaign_id) REFERENCES campaigns (campaign_id) ON DELETE CASCADE, 
    FOREIGN KEY(vendor_id) REFERENCES vendors (vendor_id) ON DELETE CASCADE, 
    CONSTRAINT uq_campaign_vendor UNIQUE (campaign_id, vendor_id)
);

CREATE INDEX idx_assignments_campaign ON campaign_vendor_assignments (campaign_id);

CREATE INDEX idx_assignments_vendor ON campaign_vendor_assignments (vendor_id);

CREATE TABLE subscriptions (
    subscription_id UUID NOT NULL, 
    client_id UUID NOT NULL, 
    tier subscriptiontier NOT NULL, 
    status subscriptionstatus NOT NULL, 
    stripe_subscription_id VARCHAR(255), 
    current_period_start TIMESTAMP WITHOUT TIME ZONE, 
    current_period_end TIMESTAMP WITHOUT TIME ZONE, 
    photos_quota INTEGER NOT NULL, 
    photos_used INTEGER NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (subscription_id), 
    FOREIGN KEY(client_id) REFERENCES clients (client_id) ON DELETE CASCADE, 
    UNIQUE (client_id), 
    UNIQUE (stripe_subscription_id)
);

CREATE INDEX idx_subscriptions_client ON subscriptions (client_id);

CREATE TYPE verificationstatus AS ENUM ('pending', 'verified', 'flagged', 'rejected');

CREATE TABLE photos (
    photo_id UUID NOT NULL, 
    campaign_id UUID NOT NULL, 
    vendor_id VARCHAR(6) NOT NULL, 
    capture_timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    upload_timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    s3_key VARCHAR(500) NOT NULL, 
    thumbnail_s3_key VARCHAR(500), 
    verification_status verificationstatus NOT NULL, 
    signature_valid BOOLEAN, 
    location_match_score FLOAT, 
    distance_from_expected FLOAT, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (photo_id), 
    FOREIGN KEY(campaign_id) REFERENCES campaigns (campaign_id) ON DELETE CASCADE, 
    FOREIGN KEY(vendor_id) REFERENCES vendors (vendor_id) ON DELETE CASCADE
);

CREATE INDEX idx_photos_campaign ON photos (campaign_id);

CREATE INDEX idx_photos_vendor ON photos (vendor_id);

CREATE INDEX idx_photos_timestamp ON photos (capture_timestamp);

CREATE INDEX idx_photos_status ON photos (verification_status);

CREATE TABLE sensor_data (
    sensor_data_id UUID NOT NULL, 
    photo_id UUID NOT NULL, 
    gps_latitude FLOAT(10), 
    gps_longitude FLOAT(10), 
    gps_altitude FLOAT, 
    gps_accuracy FLOAT, 
    gps_provider VARCHAR(20), 
    gps_satellite_count INTEGER, 
    wifi_networks JSONB, 
    cell_towers JSONB, 
    barometer_pressure FLOAT, 
    barometer_altitude FLOAT, 
    ambient_light_lux FLOAT, 
    magnetic_field_x FLOAT, 
    magnetic_field_y FLOAT, 
    magnetic_field_z FLOAT, 
    magnetic_field_magnitude FLOAT, 
    hand_tremor_frequency FLOAT, 
    hand_tremor_is_human BOOLEAN, 
    hand_tremor_confidence FLOAT, 
    location_hash VARCHAR(64), 
    confidence_score FLOAT, 
    schema_version VARCHAR(10) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (sensor_data_id), 
    FOREIGN KEY(photo_id) REFERENCES photos (photo_id) ON DELETE CASCADE, 
    UNIQUE (photo_id)
);

CREATE INDEX idx_sensor_data_photo ON sensor_data (photo_id);

CREATE INDEX idx_sensor_data_gps ON sensor_data (gps_latitude, gps_longitude);

CREATE TABLE photo_signatures (
    signature_id UUID NOT NULL, 
    photo_id UUID NOT NULL, 
    signature_data VARCHAR NOT NULL, 
    algorithm VARCHAR(50) NOT NULL, 
    device_id VARCHAR(255) NOT NULL, 
    timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    location_hash VARCHAR(64) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (signature_id), 
    FOREIGN KEY(photo_id) REFERENCES photos (photo_id) ON DELETE CASCADE, 
    UNIQUE (photo_id)
);

CREATE INDEX idx_signatures_photo ON photo_signatures (photo_id);

INSERT INTO alembic_version (version_num) VALUES ('001_initial') RETURNING alembic_version.version_num;

INFO  [alembic.runtime.migration] Running upgrade 001_initial -> 002_audit_logs, Add audit_logs table with immutability triggers
-- Running upgrade 001_initial -> 002_audit_logs

CREATE TABLE audit_logs (
    audit_id UUID NOT NULL, 
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL, 
    vendor_id VARCHAR(6) NOT NULL, 
    photo_id UUID NOT NULL, 
    campaign_code VARCHAR(50) NOT NULL, 
    sensor_data JSONB NOT NULL, 
    signature JSONB NOT NULL, 
    device_info JSONB NOT NULL, 
    previous_record_hash VARCHAR(64), 
    record_hash VARCHAR(64) NOT NULL, 
    audit_flags TEXT[], 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (audit_id)
);

CREATE INDEX idx_audit_logs_vendor_id ON audit_logs (vendor_id);

CREATE INDEX idx_audit_logs_photo_id ON audit_logs (photo_id);

CREATE INDEX idx_audit_logs_campaign_code ON audit_logs (campaign_code);

CREATE INDEX idx_audit_logs_vendor_timestamp ON audit_logs (vendor_id, timestamp DESC);

CREATE INDEX idx_audit_logs_campaign_timestamp ON audit_logs (campaign_code, timestamp DESC);

CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'Audit logs are immutable and cannot be modified or deleted';
        END;
        $$ LANGUAGE plpgsql;;

CREATE TRIGGER audit_log_immutable_update
            BEFORE UPDATE ON audit_logs
            FOR EACH ROW
            EXECUTE FUNCTION prevent_audit_log_modification();;

CREATE TRIGGER audit_log_immutable_delete
            BEFORE DELETE ON audit_logs
            FOR EACH ROW
            EXECUTE FUNCTION prevent_audit_log_modification();;

UPDATE alembic_version SET version_num='002_audit_logs' WHERE alembic_version.version_num = '001_initial';

INFO  [alembic.runtime.migration] Running upgrade 002_audit_logs -> 003_subscription_enhancements, subscription enhancements for razorpay and stripe
-- Running upgrade 002_audit_logs -> 003_subscription_enhancements

ALTER TABLE subscriptions ADD COLUMN payment_gateway VARCHAR(20);

ALTER TABLE subscriptions ADD COLUMN gateway_subscription_id VARCHAR(255);

ALTER TABLE subscriptions ADD COLUMN gateway_customer_id VARCHAR(255);

ALTER TABLE subscriptions ADD COLUMN billing_cycle VARCHAR(20) DEFAULT 'monthly' NOT NULL;

ALTER TABLE subscriptions ADD COLUMN amount INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE subscriptions ADD COLUMN currency VARCHAR(3) DEFAULT 'INR' NOT NULL;

ALTER TABLE subscriptions ADD COLUMN auto_renew INTEGER DEFAULT '1' NOT NULL;

ALTER TABLE subscriptions ADD COLUMN trial_end_date TIMESTAMP WITHOUT TIME ZONE;

ALTER TABLE subscriptions ADD COLUMN cancellation_date TIMESTAMP WITHOUT TIME ZONE;

ALTER TABLE subscriptions ADD COLUMN vendors_quota INTEGER DEFAULT '2' NOT NULL;

ALTER TABLE subscriptions ADD COLUMN vendors_used INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE subscriptions ADD COLUMN campaigns_quota INTEGER DEFAULT '1' NOT NULL;

ALTER TABLE subscriptions ADD COLUMN campaigns_used INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE subscriptions ADD COLUMN storage_quota_mb INTEGER DEFAULT '500' NOT NULL;

ALTER TABLE subscriptions ADD COLUMN storage_used_mb INTEGER DEFAULT '0' NOT NULL;

CREATE UNIQUE INDEX ix_subscriptions_gateway_subscription_id ON subscriptions (gateway_subscription_id);

UPDATE subscriptions 
        SET vendors_quota = CASE 
            WHEN tier = 'free' THEN 2
            WHEN tier = 'pro' THEN 10
            WHEN tier = 'enterprise' THEN 999999
        END,
        campaigns_quota = CASE 
            WHEN tier = 'free' THEN 1
            WHEN tier = 'pro' THEN 5
            WHEN tier = 'enterprise' THEN 999999
        END,
        storage_quota_mb = CASE 
            WHEN tier = 'free' THEN 500
            WHEN tier = 'pro' THEN 10240
            WHEN tier = 'enterprise' THEN 102400
        END
        WHERE tier IN ('free', 'pro', 'enterprise');

UPDATE alembic_version SET version_num='003_subscription_enhancements' WHERE alembic_version.version_num = '002_audit_logs';

COMMIT;

