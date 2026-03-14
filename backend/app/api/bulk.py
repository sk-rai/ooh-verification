"""
Bulk Operations API endpoints for CSV uploads.

Requirements:
- Req 2.1-2.6: Bulk campaign operations
- Req 3.1-3.10: Bulk vendor operations
- Req 4.1-4.11: Bulk assignment operations
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from typing import List
from datetime import datetime
import logging

from app.core.database import get_db
from app.core.deps import get_current_active_client
from app.core.security import generate_campaign_code, generate_vendor_id
from app.models.client import Client
from app.models.campaign import Campaign, CampaignType, CampaignStatus
from app.models.vendor import Vendor, VendorStatus
from app.models.campaign_vendor_assignment import CampaignVendorAssignment
from app.schemas.assignment import BulkOperationResponse, BulkOperationRow
from app.services.csv_processor import CSVProcessor
from app.core.error_codes import ErrorCode
from app.core.sms import sms_service
from app.services.geocoding_service import get_geocoding_service, GeocodingError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/bulk", tags=["bulk-operations"])


@router.post("/campaigns", response_model=BulkOperationResponse)
async def bulk_create_campaigns(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_client: Client = Depends(get_current_active_client)
):
    """
    Bulk create campaigns from CSV file.
    
    CSV Format:
    name,campaign_type,start_date,end_date,address,latitude,longitude,location_name
    
    Requirements:
    - Req 2.1: Bulk campaign import
    - Req 2.2: CSV column validation
    - Req 2.3: Intra-file duplicate detection
    - Req 2.4: Inter-file duplicate detection
    - Req 2.5: Partial success handling
    - Req 2.6: Operation report structure
    - Property 6: Bulk import correctness
    """
    csv_processor = CSVProcessor()
    
    # Validate file type
    is_valid, error = csv_processor.validate_file_type(file)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": error, "code": ErrorCode.CSV_INVALID_FILE_TYPE}
        )
    
    # Validate CSV structure
    is_valid, error, rows = await csv_processor.validate_csv_structure(
        file,
        required_columns=csv_processor.CAMPAIGN_REQUIRED_COLUMNS,
        optional_columns=csv_processor.CAMPAIGN_OPTIONAL_COLUMNS
    )
    
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )
    
    # Check row count limit
    if len(rows) > csv_processor.MAX_ROWS_CAMPAIGNS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Too many rows. Maximum {csv_processor.MAX_ROWS_CAMPAIGNS} campaigns allowed per upload"
        )
    
    # Detect duplicates within CSV (by name)
    duplicates = csv_processor.detect_duplicates_in_csv(rows, 'name')
    
    results = []
    successful = 0
    failed = 0
    
    for row in rows:
        row_num = row['row_number']
        data = row['data']
        
        try:
            # Check if this row is a duplicate
            if data['name'] in duplicates and row_num in duplicates[data['name']][1:]:
                results.append(csv_processor.create_error_row(
                    row_num,
                    f"Duplicate campaign name in CSV: {data['name']}"
                ))
                failed += 1
                continue
            
            # Validate required fields
            if not data.get('name'):
                results.append(csv_processor.create_error_row(row_num, "Campaign name is required"))
                failed += 1
                continue
            
            if not data.get('campaign_type'):
                results.append(csv_processor.create_error_row(row_num, "Campaign type is required"))
                failed += 1
                continue
            
            # Validate campaign type
            try:
                campaign_type = CampaignType(data['campaign_type'].lower())
            except ValueError:
                valid_types = [t.value for t in CampaignType]
                results.append(csv_processor.create_error_row(
                    row_num,
                    f"Invalid campaign type: {data['campaign_type']}. Must be one of: {', '.join(valid_types)}"
                ))
                failed += 1
                continue
            
            # Validate dates
            is_valid, error, start_date = csv_processor.validate_date_format(data.get('start_date'))
            if not is_valid:
                results.append(csv_processor.create_error_row(row_num, f"Start date: {error}"))
                failed += 1
                continue
            
            is_valid, error, end_date = csv_processor.validate_date_format(data.get('end_date'))
            if not is_valid:
                results.append(csv_processor.create_error_row(row_num, f"End date: {error}"))
                failed += 1
                continue
            
            # Validate date range
            is_valid, error = csv_processor.validate_date_range(start_date, end_date)
            if not is_valid:
                results.append(csv_processor.create_error_row(row_num, error))
                failed += 1
                continue
            
            # Validate coordinates if provided
            is_valid, error, lat, lon = csv_processor.validate_coordinates(
                data.get('latitude'),
                data.get('longitude')
            )
            if not is_valid:
                results.append(csv_processor.create_error_row(row_num, error))
                failed += 1
                continue
            
            # Check for existing campaign with same name for this client
            result = await db.execute(
                select(Campaign).where(
                    Campaign.client_id == current_client.client_id,
                    Campaign.name == data['name']
                )
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                results.append(csv_processor.create_error_row(
                    row_num,
                    f"Campaign with name '{data['name']}' already exists"
                ))
                failed += 1
                continue
            
            # Generate campaign code
            campaign_code = generate_campaign_code()
            
            # Create campaign
            campaign = Campaign(
                tenant_id=current_client.tenant_id,
                client_id=current_client.client_id,
                name=data['name'],
                campaign_code=campaign_code,
                campaign_type=campaign_type,
                status=CampaignStatus.ACTIVE,
                start_date=start_date,
                end_date=end_date
            )
            
            db.add(campaign)
            await db.flush()
            await db.refresh(campaign)
            
            results.append(csv_processor.create_success_row(
                row_num,
                {
                    "campaign_id": str(campaign.campaign_id),
                    "campaign_code": campaign.campaign_code,
                    "name": campaign.name,
                    "campaign_type": campaign.campaign_type.value,
                    "start_date": campaign.start_date.isoformat(),
                    "end_date": campaign.end_date.isoformat()
                }
            ))
            successful += 1
            
        except Exception as e:
            logger.error(f"Error processing row {row_num}: {e}")
            results.append(csv_processor.create_error_row(
                row_num,
                f"Unexpected error: {str(e)}"
            ))
            failed += 1
    
    # Commit all successful operations with rollback safety
    if successful > 0:
        try:
            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            logger.error(f"Database integrity error during bulk campaign commit: {e}")
            return BulkOperationResponse(
                total_rows=len(rows),
                successful=0,
                failed=len(rows),
                results=[],
                errors=[f"Database error: A constraint violation occurred. Some campaigns may have duplicate names. ({ErrorCode.DB_CONSTRAINT_VIOLATION})"]
            )
        except Exception as e:
            await db.rollback()
            logger.error(f"Unexpected error during bulk campaign commit: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"message": "Failed to save campaigns", "code": ErrorCode.INTERNAL_ERROR}
            )
    
    return BulkOperationResponse(
        total_rows=len(rows),
        successful=successful,
        failed=failed,
        results=results,
        errors=[]
    )


@router.get("/campaigns/template")
async def download_campaign_template():
    """
    Download CSV template for bulk campaign upload.
    
    Requirements:
    - Req 2.7: CSV template download
    """
    template = "name,campaign_type,start_date,end_date,address,latitude,longitude,location_name\n"
    template += '"NYC Billboard Q2","ooh","2026-04-01","2026-06-30","Times Square, NYC",,,"Times Square"\n'
    template += '"Construction Site A","construction","2026-03-15","2026-12-31",,40.7128,-74.0060,"Site A Main"\n'
    
    from fastapi.responses import Response
    return Response(
        content=template,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=campaign_template.csv"}
    )




@router.post("/vendors", response_model=BulkOperationResponse)
async def bulk_create_vendors(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_client: Client = Depends(get_current_active_client)
):
    """
    Bulk create vendors from CSV file.
    
    CSV Format:
    name,phone_number,email
    
    Requirements:
    - Req 3.1: Bulk vendor import
    - Req 3.2: CSV column validation
    - Req 3.3: Vendor ID uniqueness
    - Req 3.4: Phone number format validation
    - Req 3.5: Email format validation
    - Req 3.6: Inter-file duplicate detection
    - Req 3.7: Partial success handling
    - Req 3.9: SMS notification resilience
    - Req 3.10: Operation report structure
    - Property 6: Bulk import correctness
    - Property 13: Vendor ID uniqueness
    - Property 14: Phone number format validation
    - Property 15: Email format validation
    """
    csv_processor = CSVProcessor()
    
    # Validate file type
    is_valid, error = csv_processor.validate_file_type(file)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": error, "code": ErrorCode.CSV_INVALID_FILE_TYPE}
        )
    
    # Validate CSV structure
    is_valid, error, rows = await csv_processor.validate_csv_structure(
        file,
        required_columns=csv_processor.VENDOR_REQUIRED_COLUMNS,
        optional_columns=csv_processor.VENDOR_OPTIONAL_COLUMNS
    )
    
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )
    
    # Check row count limit
    if len(rows) > csv_processor.MAX_ROWS_VENDORS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Too many rows. Maximum {csv_processor.MAX_ROWS_VENDORS} vendors allowed per upload"
        )
    
    # Detect duplicates within CSV (by phone number)
    duplicates = csv_processor.detect_duplicates_in_csv(rows, 'phone_number')
    
    results = []
    successful = 0
    failed = 0
    sms_failures = []
    
    for row in rows:
        row_num = row['row_number']
        data = row['data']
        
        try:
            # Check if this row is a duplicate
            if data['phone_number'] in duplicates and row_num in duplicates[data['phone_number']][1:]:
                results.append(csv_processor.create_error_row(
                    row_num,
                    f"Duplicate phone number in CSV: {data['phone_number']}"
                ))
                failed += 1
                continue
            
            # Validate required fields
            if not data.get('name'):
                results.append(csv_processor.create_error_row(row_num, "Vendor name is required"))
                failed += 1
                continue
            
            if not data.get('phone_number'):
                results.append(csv_processor.create_error_row(row_num, "Phone number is required"))
                failed += 1
                continue
            
            # Validate phone number format (E.164)
            phone = data['phone_number'].strip()
            if not phone.startswith('+'):
                results.append(csv_processor.create_error_row(
                    row_num,
                    f"Phone number must start with + (E.164 format): {phone}"
                ))
                failed += 1
                continue
            
            if not phone[1:].isdigit():
                results.append(csv_processor.create_error_row(
                    row_num,
                    f"Phone number must contain only digits after +: {phone}"
                ))
                failed += 1
                continue
            
            if len(phone) < 8 or len(phone) > 16:
                results.append(csv_processor.create_error_row(
                    row_num,
                    f"Phone number must be 8-16 characters (including +): {phone}"
                ))
                failed += 1
                continue
            
            # Validate email format if provided
            email = data.get('email', '').strip() if data.get('email') else None
            if email:
                if '@' not in email or '.' not in email.split('@')[1]:
                    results.append(csv_processor.create_error_row(
                        row_num,
                        f"Invalid email format: {email}"
                    ))
                    failed += 1
                    continue
            
            # Check for existing vendor with same phone number
            result = await db.execute(
                select(Vendor).where(Vendor.phone_number == phone)
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                results.append(csv_processor.create_error_row(
                    row_num,
                    f"Vendor with phone number '{phone}' already exists"
                ))
                failed += 1
                continue
            
            # Generate unique vendor ID
            vendor_id = generate_vendor_id()
            
            # Ensure vendor ID is unique (very unlikely collision, but check anyway)
            result = await db.execute(
                select(Vendor).where(Vendor.vendor_id == vendor_id)
            )
            if result.scalar_one_or_none():
                # Regenerate if collision
                vendor_id = generate_vendor_id()
            
            # Create vendor
            vendor = Vendor(
                vendor_id=vendor_id,
                tenant_id=current_client.tenant_id,
                name=data['name'].strip(),
                phone_number=phone,
                email=email,
                created_by_client_id=current_client.client_id,
                status=VendorStatus.ACTIVE
            )
            
            db.add(vendor)
            await db.flush()
            await db.refresh(vendor)
            
            # Try to send SMS (non-blocking - failure doesn't prevent vendor creation)
            sms_sent = False
            try:
                await sms_service.send_vendor_welcome_sms(
                    phone_number=phone,
                    vendor_id=vendor_id,
                    vendor_name=data['name'].strip()
                )
                sms_sent = True
            except Exception as sms_error:
                logger.warning(f"SMS failed for vendor {vendor_id}: {sms_error}")
                sms_failures.append(f"Row {row_num}: SMS failed for {phone}")
            
            results.append(csv_processor.create_success_row(
                row_num,
                {
                    "vendor_id": vendor.vendor_id,
                    "name": vendor.name,
                    "phone_number": vendor.phone_number,
                    "email": vendor.email,
                    "sms_sent": sms_sent
                }
            ))
            successful += 1
            
        except Exception as e:
            logger.error(f"Error processing row {row_num}: {e}")
            results.append(csv_processor.create_error_row(
                row_num,
                f"Unexpected error: {str(e)}"
            ))
            failed += 1
    
    # Commit all successful operations with rollback safety
    if successful > 0:
        try:
            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            logger.error(f"Database integrity error during bulk vendor commit: {e}")
            return BulkOperationResponse(
                total_rows=len(rows),
                successful=0,
                failed=len(rows),
                results=[],
                errors=[f"Database error: A constraint violation occurred. Some vendors may have duplicate phone numbers. ({ErrorCode.DB_CONSTRAINT_VIOLATION})"]
            )
        except Exception as e:
            await db.rollback()
            logger.error(f"Unexpected error during bulk vendor commit: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"message": "Failed to save vendors", "code": ErrorCode.INTERNAL_ERROR}
            )
    
    # Add SMS failures to global errors (informational only)
    global_errors = []
    if sms_failures:
        global_errors.append(f"SMS delivery failed for {len(sms_failures)} vendors (vendors created successfully)")
    
    return BulkOperationResponse(
        total_rows=len(rows),
        successful=successful,
        failed=failed,
        results=results,
        errors=global_errors
    )


@router.get("/vendors/template")
async def download_vendor_template():
    """
    Download CSV template for bulk vendor upload.
    
    Requirements:
    - Req 3.11: CSV template download
    """
    template = "name,phone_number,email\n"
    template += '"John Doe","+1234567890","john@example.com"\n'
    template += '"Jane Smith","+0987654321","jane@example.com"\n'
    
    from fastapi.responses import Response
    return Response(
        content=template,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=vendor_template.csv"}
    )



@router.post("/assignments", response_model=BulkOperationResponse)
async def bulk_create_assignments(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_client: Client = Depends(get_current_active_client)
):
    """
    Bulk create campaign-vendor assignments from CSV file.
    
    CSV Format:
    campaign_code,vendor_id,address,latitude,longitude,location_name
    
    Requirements:
    - Req 4.1: Bulk assignment import
    - Req 4.2: CSV column validation
    - Req 4.3: Campaign code validation
    - Req 4.4: Vendor ID validation
    - Req 4.5: Duplicate detection
    - Req 4.6: Partial success handling
    - Req 4.7: Operation report structure
    - Req 4.10: Multiple vendors per campaign
    - Req 4.11: Multiple campaigns per vendor
    - Property 6: Bulk import correctness
    - Property 39: Location data validation
    """
    csv_processor = CSVProcessor()
    
    # Validate file type
    is_valid, error = csv_processor.validate_file_type(file)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": error, "code": ErrorCode.CSV_INVALID_FILE_TYPE}
        )
    
    # Validate CSV structure
    is_valid, error, rows = await csv_processor.validate_csv_structure(
        file,
        required_columns=csv_processor.ASSIGNMENT_REQUIRED_COLUMNS,
        optional_columns=csv_processor.ASSIGNMENT_OPTIONAL_COLUMNS
    )
    
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )
    
    # Check row count limit
    if len(rows) > csv_processor.MAX_ROWS_ASSIGNMENTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Too many rows. Maximum {csv_processor.MAX_ROWS_ASSIGNMENTS} assignments allowed per upload"
        )
    
    results = []
    successful = 0
    failed = 0
    duplicate_count = 0
    
    # Pre-fetch all campaigns and vendors for this client to avoid repeated queries
    campaigns_result = await db.execute(
        select(Campaign).where(Campaign.client_id == current_client.client_id)
    )
    campaigns_map = {c.campaign_code: c for c in campaigns_result.scalars().all()}
    
    vendors_result = await db.execute(
        select(Vendor).where(Vendor.created_by_client_id == current_client.client_id)
    )
    vendors_map = {v.vendor_id: v for v in vendors_result.scalars().all()}
    
    # Pre-fetch existing assignments to detect duplicates
    existing_assignments_result = await db.execute(
        select(CampaignVendorAssignment).where(
            CampaignVendorAssignment.campaign_id.in_([c.campaign_id for c in campaigns_map.values()])
        )
    )
    existing_assignments = existing_assignments_result.scalars().all()
    existing_pairs = {
        (a.campaign_id, a.vendor_id) for a in existing_assignments
    }
    
    for row in rows:
        row_num = row['row_number']
        data = row['data']
        
        try:
            # Validate required fields
            if not data.get('campaign_code'):
                results.append(csv_processor.create_error_row(
                    row_num, "Campaign code is required"
                ))
                failed += 1
                continue
            
            if not data.get('vendor_id'):
                results.append(csv_processor.create_error_row(
                    row_num, "Vendor ID is required"
                ))
                failed += 1
                continue
            
            campaign_code = data['campaign_code'].strip()
            vendor_id = data['vendor_id'].strip()
            
            # Validate vendor ID format
            if len(vendor_id) != 6 or not vendor_id.isalnum():
                results.append(csv_processor.create_error_row(
                    row_num,
                    f"Invalid vendor ID format: {vendor_id}. Must be 6 alphanumeric characters."
                ))
                failed += 1
                continue
            
            # Check if campaign exists
            if campaign_code not in campaigns_map:
                results.append(csv_processor.create_error_row(
                    row_num,
                    f"Campaign with code '{campaign_code}' not found"
                ))
                failed += 1
                continue
            
            # Check if vendor exists
            if vendor_id not in vendors_map:
                results.append(csv_processor.create_error_row(
                    row_num,
                    f"Vendor with ID '{vendor_id}' not found"
                ))
                failed += 1
                continue
            
            campaign = campaigns_map[campaign_code]
            vendor = vendors_map[vendor_id]
            
            # Check for duplicate assignment
            if (campaign.campaign_id, vendor.vendor_id) in existing_pairs:
                results.append(csv_processor.create_error_row(
                    row_num,
                    f"Assignment already exists for campaign '{campaign_code}' and vendor '{vendor_id}'"
                ))
                duplicate_count += 1
                failed += 1
                continue
            
            # Validate coordinates if provided
            is_valid, error, lat, lon = csv_processor.validate_coordinates(
                data.get('latitude'),
                data.get('longitude')
            )
            if not is_valid:
                results.append(csv_processor.create_error_row(row_num, error))
                failed += 1
                continue
            
            # Auto-geocode address if provided but coordinates are missing
            address = data.get('address', '').strip() if data.get('address') else None
            if address and not lat and not lon:
                try:
                    geocoding_service = get_geocoding_service()
                    geocode_result = await geocoding_service.geocode_address(address)
                    lat = geocode_result.latitude
                    lon = geocode_result.longitude
                    logger.info(f"Auto-geocoded address '{address}' to ({lat}, {lon})")
                except GeocodingError as e:
                    logger.warning(f"Failed to geocode address '{address}': {e}")
                    # Continue without coordinates - address-only assignment is valid
            
            # Create assignment
            assignment = CampaignVendorAssignment(
                campaign_id=campaign.campaign_id,
                vendor_id=vendor.vendor_id,
                assignment_address=address,
                assignment_latitude=lat,
                assignment_longitude=lon,
                assignment_location_name=data.get('location_name', '').strip() if data.get('location_name') else None
            )
            
            db.add(assignment)
            await db.flush()
            
            # Add to existing pairs to detect duplicates within this CSV
            existing_pairs.add((campaign.campaign_id, vendor.vendor_id))
            
            results.append(csv_processor.create_success_row(
                row_num,
                {
                    "campaign_code": campaign_code,
                    "campaign_name": campaign.name,
                    "vendor_id": vendor_id,
                    "vendor_name": vendor.name,
                    "assignment_address": assignment.assignment_address,
                    "assignment_latitude": assignment.assignment_latitude,
                    "assignment_longitude": assignment.assignment_longitude,
                    "assignment_location_name": assignment.assignment_location_name
                }
            ))
            successful += 1
            
        except Exception as e:
            logger.error(f"Error processing row {row_num}: {e}")
            results.append(csv_processor.create_error_row(
                row_num,
                f"Unexpected error: {str(e)}"
            ))
            failed += 1
    
    # Commit all successful operations with rollback safety
    if successful > 0:
        try:
            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            logger.error(f"Database integrity error during bulk assignment commit: {e}")
            return BulkOperationResponse(
                total_rows=len(rows),
                successful=0,
                failed=len(rows),
                results=[],
                errors=[f"Database error: A constraint violation occurred. Some assignments may be duplicates. ({ErrorCode.DB_CONSTRAINT_VIOLATION})"]
            )
        except Exception as e:
            await db.rollback()
            logger.error(f"Unexpected error during bulk assignment commit: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"message": "Failed to save assignments", "code": ErrorCode.INTERNAL_ERROR}
            )
    
    # Add duplicate count to global errors if any
    global_errors = []
    if duplicate_count > 0:
        global_errors.append(f"{duplicate_count} duplicate assignments skipped")
    
    return BulkOperationResponse(
        total_rows=len(rows),
        successful=successful,
        failed=failed,
        results=results,
        errors=global_errors
    )


@router.get("/assignments/template")
async def download_assignment_template():
    """
    Download CSV template for bulk assignment upload.
    
    Requirements:
    - Req 4.12: CSV template download
    """
    template = "campaign_code,vendor_id,address,latitude,longitude,location_name\n"
    template += '"CAM-2026-A3X9","ABC123","123 Main St, NYC",,,\n'
    template += '"CAM-2026-A3X9","DEF456",,40.7128,-74.0060,"Times Square"\n'
    template += '"CAM-2026-B7Y4","ABC123","456 Broadway, NYC",40.7614,-73.9776,"Broadway Store"\n'
    
    from fastapi.responses import Response
    return Response(
        content=template,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=assignment_template.csv"}
    )
