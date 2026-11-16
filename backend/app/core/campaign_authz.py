"""
Shared campaign authorization for vendor uploads.

Used by POST /api/evidence/upload and POST /api/photos/upload so both endpoints apply the same rules.
It MUST run before the uploaded file is read or validated, before any object-storage write, before any
database mutation and before geofence verification, so a rejected request leaves no side effects and
reveals no verification data.

Contract:
  * no campaign reference at all                  -> returns None (explicit Quick Capture; the caller decides
                                                     whether Quick Capture is allowed for the endpoint)
  * campaign_id malformed                         -> 400
  * campaign_id and campaign_code both given but
    they identify different campaigns             -> 400
  * campaign missing, or in another tenant        -> 404 with ONE shared body (no existence oracle)
  * vendor not assigned to the campaign           -> 403
  * campaign not ACTIVE                           -> 409 {"code": "CAMPAIGN_INACTIVE", ...}
  * an invalid or unknown reference NEVER falls back to Quick Capture.

Resolution is always scoped to the AUTHENTICATED vendor's tenant (``vendor.tenant_id``); nothing the client
sends decides the tenant. Assignment is the control that separates clients inside a shared tenant.

Statuses that accept uploads are listed in ONE place (``UPLOADABLE_STATUSES``). Late uploads for COMPLETED
campaigns are intentionally not handled here (no held-for-review workflow yet).
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import Campaign, CampaignStatus
from app.models.campaign_vendor_assignment import CampaignVendorAssignment

UPLOADABLE_STATUSES = frozenset({CampaignStatus.ACTIVE})

CAMPAIGN_NOT_FOUND_DETAIL = "Campaign not found"


def _not_found() -> HTTPException:
    # One shared body for nonexistent, foreign-tenant and unknown references.
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=CAMPAIGN_NOT_FOUND_DETAIL)


def _clean(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value or None


async def authorize_campaign_reference(
    db: AsyncSession,
    vendor,
    *,
    campaign_id: Optional[str] = None,
    campaign_code: Optional[str] = None,
) -> Optional[Campaign]:
    """Authorize the vendor to upload into the referenced campaign.

    Returns the Campaign, or None when no reference was supplied (explicit Quick Capture).
    Raises HTTPException (400 / 403 / 404 / 409) otherwise.
    """
    campaign_id = _clean(campaign_id)
    campaign_code = _clean(campaign_code)
    if campaign_id is None and campaign_code is None:
        return None

    tenant_id = getattr(vendor, "tenant_id", None)
    vendor_id = getattr(vendor, "vendor_id", None)
    if tenant_id is None or vendor_id is None:
        raise _not_found()                       # fail closed: no tenant scope, nothing can match

    parsed_id: Optional[UUID] = None
    if campaign_id is not None:
        try:
            parsed_id = UUID(campaign_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid campaign reference")

    by_id: Optional[Campaign] = None
    by_code: Optional[Campaign] = None
    if parsed_id is not None:
        by_id = (await db.execute(
            select(Campaign).where(Campaign.campaign_id == parsed_id, Campaign.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if by_id is None:
            raise _not_found()
    if campaign_code is not None:
        by_code = (await db.execute(
            select(Campaign).where(Campaign.campaign_code == campaign_code, Campaign.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if by_code is None:
            raise _not_found()

    if by_id is not None and by_code is not None and by_id.campaign_id != by_code.campaign_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="campaign_id and campaign_code refer to different campaigns")
    campaign = by_id or by_code

    assigned = (await db.execute(
        select(CampaignVendorAssignment.assignment_id).where(
            CampaignVendorAssignment.campaign_id == campaign.campaign_id,
            CampaignVendorAssignment.vendor_id == vendor_id,
        )
    )).first()
    if assigned is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Vendor not assigned to this campaign")

    if campaign.status not in UPLOADABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CAMPAIGN_INACTIVE", "message": "Campaign is not accepting uploads"},
        )
    return campaign
