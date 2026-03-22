# Audit Logger Integration Instructions

## Step 1: Add Imports to photos.py

Add these imports after the existing service imports (around line 26):

```python
from app.services.audit_logger import audit_logger, AuditFlag
import logging

logger = logging.getLogger(__name__)
```

## Step 2: Add Audit Logging to upload_photo Function

Add this code after `await db.commit()` and before the `return PhotoUploadResponse(...)` statement (around line 401):

```python
    # Log to audit trail (non-blocking)
    try:
        # Determine audit flags
        audit_flags = []
        
        # Check GPS accuracy
        if sensor_data_obj.gps.accuracy and sensor_data_obj.gps.accuracy > 50:
            audit_flags.append(AuditFlag.LOW_GPS_ACCURACY)
        
        # Check location mismatch
        if location_match_result and location_match_result.get('match_score', 100) < 50:
            audit_flags.append(AuditFlag.LOCATION_MISMATCH)
        
        # Check SafetyNet (if provided in device info)
        # Note: This would come from the client in a real implementation
        
        # Prepare device info
        device_info_dict = {
            'device_id': signature_obj.device_id,
            'model': 'Unknown',  # Would come from client
            'os_version': 'Unknown',  # Would come from client
            'app_version': 'Unknown'  # Would come from client
        }
        
        # Log audit record
        audit_id = audit_logger.log_photo_capture(
            photo_id=str(photo_id),
            vendor_id=vendor.vendor_id,
            campaign_code=campaign_code,
            sensor_data=sensor_data_dict,
            signature=signature_dict,
            device_info=device_info_dict,
            flags=audit_flags
        )
        
        if audit_id:
            logger.info(f"Audit log created: {audit_id} for photo {photo_id}")
        else:
            logger.warning(f"Failed to create audit log for photo {photo_id}")
            
    except Exception as e:
        # Log error but don't block photo upload
        logger.error(f"Audit logging failed for photo {photo_id}: {e}")
```

## Complete Integration Example

Here's what the end of the `upload_photo` function should look like:

```python
    db.add(signature_record)

    # Commit transaction
    await db.commit()

    # Log to audit trail (non-blocking)
    try:
        # Determine audit flags
        audit_flags = []
        
        # Check GPS accuracy
        if sensor_data_obj.gps.accuracy and sensor_data_obj.gps.accuracy > 50:
            audit_flags.append(AuditFlag.LOW_GPS_ACCURACY)
        
        # Check location mismatch
        if location_match_result and location_match_result.get('match_score', 100) < 50:
            audit_flags.append(AuditFlag.LOCATION_MISMATCH)
        
        # Prepare device info
        device_info_dict = {
            'device_id': signature_obj.device_id,
            'model': 'Unknown',
            'os_version': 'Unknown',
            'app_version': 'Unknown'
        }
        
        # Log audit record
        audit_id = audit_logger.log_photo_capture(
            photo_id=str(photo_id),
            vendor_id=vendor.vendor_id,
            campaign_code=campaign_code,
            sensor_data=sensor_data_dict,
            signature=signature_dict,
            device_info=device_info_dict,
            flags=audit_flags
        )
        
        if audit_id:
            logger.info(f"Audit log created: {audit_id} for photo {photo_id}")
        else:
            logger.warning(f"Failed to create audit log for photo {photo_id}")
            
    except Exception as e:
        # Log error but don't block photo upload
        logger.error(f"Audit logging failed for photo {photo_id}: {e}")

    # Return response
    return PhotoUploadResponse(
        photo_id=photo_id,
        verification_status=verification_status.value,
        signature_valid=signature_valid,
        location_match_score=location_match_result['match_score'] if location_match_result else None,
        distance_from_expected=location_match_result['distance_meters'] if location_match_result else None,
        s3_url=photo_url,
        thumbnail_url=thumbnail_url,
        message=f"Photo uploaded and {verification_status.value}"
    )
```

## Verification

After integration, verify the audit logging works:

1. Start DynamoDB Local:
   ```bash
   docker run -d -p 8000:8000 amazon/dynamodb-local
   ```

2. Create the audit table:
   ```bash
   python scripts/create_audit_table.py
   ```

3. Upload a photo via the API

4. Check audit logs:
   ```python
   from app.services.audit_logger import audit_logger
   
   logs = audit_logger.get_vendor_audit_logs("VND001", limit=10)
   print(f"Found {len(logs)} audit records")
   
   # Verify chain integrity
   is_valid, error = audit_logger.verify_chain_integrity("VND001")
   print(f"Chain valid: {is_valid}")
   ```
