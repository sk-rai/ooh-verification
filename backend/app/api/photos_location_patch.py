"""
Patch to add location verification to photos.py

Add this import after line 28:
from app.services.location_verification_service import get_location_verification_service

Add this code after line 295 (after location_match_result calculation):
"""

# IMPORT TO ADD (after line 28):
# from app.services.location_verification_service import get_location_verification_service

# CODE TO ADD (after location_match_result calculation, around line 295):
"""
    # Verify against campaign locations (if defined)
    campaign_location_verification = None
    if sensor_data_obj.gps.latitude and sensor_data_obj.gps.longitude:
        location_verifier = get_location_verification_service()
        campaign_location_verification = await location_verifier.verify_location(
            db,
            str(campaign.campaign_id),
            sensor_data_obj.gps.latitude,
            sensor_data_obj.gps.longitude
        )
        
        # If campaign has locations defined and photo is outside radius, flag it
        if campaign_location_verification and not campaign_location_verification.is_valid:
            # Add to audit flags
            if 'audit_flags' not in locals():
                audit_flags = []
            audit_flags.append(AuditFlag.LOCATION_MISMATCH.value)
"""

# UPDATE determine_verification_status call to include campaign location:
"""
    # Determine verification status (update this line around line 298)
    verification_status = determine_verification_status(
        signature_valid, 
        location_match_result,
        campaign_location_verification
    )
"""

# UPDATE determine_verification_status function (around line 142):
"""
def determine_verification_status(
    signature_valid: bool,
    location_match_result: Optional[dict] = None,
    campaign_location_verification: Optional[any] = None
) -> VerificationStatus:
    '''
    Determine overall verification status based on signature and location checks.
    
    Priority:
    1. Signature must be valid
    2. Location profile match (if exists)
    3. Campaign location verification (if locations defined)
    
    Returns:
        VerificationStatus enum value
    '''
    # Signature is primary verification
    if not signature_valid:
        return VerificationStatus.REJECTED
    
    # Check location profile match if exists
    if location_match_result:
        match_score = location_match_result.get('match_score', 0)
        if match_score >= 80:
            status_from_profile = VerificationStatus.VERIFIED
        elif match_score >= 50:
            status_from_profile = VerificationStatus.FLAGGED
        else:
            status_from_profile = VerificationStatus.REJECTED
    else:
        status_from_profile = VerificationStatus.VERIFIED  # No profile = pass
    
    # Check campaign location verification if exists
    if campaign_location_verification:
        if not campaign_location_verification.is_valid:
            # Photo is outside acceptable radius
            if campaign_location_verification.distance_meters > 1000:  # > 1km
                return VerificationStatus.REJECTED
            else:
                return VerificationStatus.FLAGGED
    
    return status_from_profile
"""

# UPDATE PhotoUploadResponse to include campaign location info (around line 490):
"""
    return PhotoUploadResponse(
        photo_id=photo_id,
        verification_status=verification_status.value,
        signature_valid=signature_valid,
        location_match_score=location_match_result['match_score'] if location_match_result else None,
        distance_from_expected=location_match_result['distance_meters'] if location_match_result else None,
        campaign_location_distance=campaign_location_verification.distance_meters if campaign_location_verification else None,
        campaign_location_valid=campaign_location_verification.is_valid if campaign_location_verification else None,
        s3_url=photo_url,
        thumbnail_url=thumbnail_url,
        message=f"Photo uploaded and {verification_status.value}"
    )
"""

print("This is a reference file showing what changes need to be made to photos.py")
print("Manual integration required due to complex function structure")
