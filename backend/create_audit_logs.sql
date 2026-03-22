-- Create audit_logs table
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

-- Create immutability triggers
CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Audit logs are immutable and cannot be modified or deleted';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_log_immutable_update
    BEFORE UPDATE ON audit_logs
    FOR EACH ROW
    EXECUTE FUNCTION prevent_audit_log_modification();

CREATE TRIGGER audit_log_immutable_delete
    BEFORE DELETE ON audit_logs
    FOR EACH ROW
    EXECUTE FUNCTION prevent_audit_log_modification();
