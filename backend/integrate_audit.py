#!/usr/bin/env python3
"""
Script to integrate audit logging into photo upload API.
"""

# Read the current photos.py file
with open('app/api/photos.py', 'r') as f:
    content = f.read()

# Find the location to insert audit logging code
marker = "    # Commit transaction\n    await db.commit()"

# The audit logging code to insert
audit_code = """    # Commit transaction
    await db.commit()

    # Log to audit trail (non-blocking - don't fail upload if audit logging fails)
    try:
        audit_logger = AuditLogger(db)
        
        # Determine audit flags
        audit_flags = []
        
        # Flag if location mismatch (score < 80)
        if location_match_result and location_match_result.get('match_score', 100) < 80:
            audit_flags.append(AuditFlag.LOCATION_MISMATCH.value)
        
        # Flag if GPS accuracy is low (> 50 meters)
        if sensor_data_obj.gps.accuracy and sensor_data_obj.gps.accuracy > 50:
            audit_flags.append(AuditFlag.LOW_GPS_ACCURACY.value)
        
        # Prepare device info
        device_info = {
            'device_id': signature_obj.device_id,
            'vendor_id': vendor.vendor_id
        }
        
        # Prepare sensor data for audit
        audit_sensor_data = {
            'gps': {
                'latitude': sensor_data_obj.gps.latitude,
                'longitude': sensor_data_obj.gps.longitude,
                'altitude': sensor_data_obj.gps.altitude,
                'accuracy': sensor_data_obj.gps.accuracy,
                'provider': sensor_data_obj.gps.provider,
                'satellite_count': sensor_data_obj.gps.satellite_count
            },
            'wifi_networks': [w.model_dump() for w in sensor_data_obj.wifi_networks] if sensor_data_obj.wifi_networks else [],
            'cell_towers': [c.model_dump() for c in sensor_data_obj.cell_towers] if sensor_data_obj.cell_towers else [],
            'location_hash': sensor_data_obj.location_hash,
            'confidence_score': sensor_data_obj.confidence_score
        }
        
        # Add environmental data if available
        if sensor_data_obj.environmental:
            audit_sensor_data['environmental'] = sensor_data_obj.environmental.model_dump()
        
        # Prepare signature data for audit
        audit_signature_data = {
            'signature': signature_obj.signature,
            'algorithm': signature_obj.algorithm,
            'timestamp': signature_obj.timestamp,
            'location_hash': signature_obj.location_hash,
            'valid': signature_valid
        }
        
        # Log the photo capture event
        await audit_logger.log_photo_capture(
            photo_id=str(photo_id),
            vendor_id=vendor.vendor_id,
            campaign_code=campaign_code,
            sensor_data=audit_sensor_data,
            signature=audit_signature_data,
            device_info=device_info,
            flags=audit_flags if audit_flags else None
        )
    except Exception as e:
        # Log error but don't fail the upload
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Audit logging failed (non-critical): {str(e)}")"""

# Replace the marker with the audit code
if marker in content:
    content = content.replace(marker, audit_code)
    
    # Write the updated content
    with open('app/api/photos.py', 'w') as f:
        f.write(content)
    
    print("✅ Successfully integrated audit logging into photo upload API")
else:
    print("❌ Could not find the marker in photos.py")
    print("Marker:", repr(marker))
