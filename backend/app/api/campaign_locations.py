"""
Campaign Locations API - Manage physical locations for campaigns.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import uuid

from app.core.database import get_db
from app.core.deps import get_current_client
from app.models.client import Client
from app.models.campaign import Campaign
from app.models.campaign_location import CampaignLocation
from app.schemas.campaign_location import (
    CampaignLocationCreate,
    CampaignLocationCreateWithCoords,
    CampaignLocationUpdate,
    CampaignLocationResponse,
    GeocodeRequest,
    ReverseGeocodeRequest,
    GeocodeResponse,
    LocationVerificationResponse
)
from app.services.geocoding_service import get_geocoding_service
from app.services.location_verification_service import get_location_verification_service

router = APIRouter(prefix="/api/campaigns", tags=["Campaign Locations"])


@router.post("/{campaign_id}/locations", response_model=CampaignLocationResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign_location(
    campaign_id: str,
    location_data: CampaignLocationCreate,
    db: AsyncSession = Depends(get_db),
    current_client: Client = Depends(get_current_client)
):
    """
    Create a new location for a campaign (with automatic geocoding).
    
    The address will be automatically geocoded to get coordinates.
    """
    # Verify campaign exists and belongs to client
    result = await db.execute(
        select(Campaign).where(
            Campaign.campaign_id == uuid.UUID(campaign_id),
            Campaign.client_id == current_client.client_id
        )
    )
    campaign = result.scalar_one_or_none()
    
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found or access denied"
        )
    
    # Geocode the address
    geocoding_service = get_geocoding_service()
    geocode_result = await geocoding_service.geocode(location_data.address)
    
    if not geocode_result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to geocode address. Please check the address and try again."
        )
    
    # Create location with geocoded coordinates
    new_location = CampaignLocation(
        campaign_id=uuid.UUID(campaign_id),
        name=location_data.name,
        description=location_data.description,
        address=geocode_result.formatted_address,
        city=geocode_result.address_components.get("city"),
        state=geocode_result.address_components.get("state"),
        country=geocode_result.address_components.get("country"),
        postal_code=geocode_result.address_components.get("postal_code"),
        latitude=geocode_result.latitude,
        longitude=geocode_result.longitude,
        verification_radius_meters=location_data.verification_radius_meters,
        geocoding_accuracy=geocode_result.accuracy,
        place_id=geocode_result.place_id
    )
    
    db.add(new_location)
    await db.commit()
    await db.refresh(new_location)
    
    return new_location


@router.post("/{campaign_id}/locations/with-coords", response_model=CampaignLocationResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign_location_with_coords(
    campaign_id: str,
    location_data: CampaignLocationCreateWithCoords,
    db: AsyncSession = Depends(get_db),
    current_client: Client = Depends(get_current_client)
):
    """
    Create a new location for a campaign with explicit coordinates (no geocoding).
    
    Use this endpoint when you already have the coordinates.
    """
    # Verify campaign exists and belongs to client
    result = await db.execute(
        select(Campaign).where(
            Campaign.campaign_id == uuid.UUID(campaign_id),
            Campaign.client_id == current_client.client_id
        )
    )
    campaign = result.scalar_one_or_none()
    
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found or access denied"
        )
    
    # Create location with provided coordinates
    new_location = CampaignLocation(
        campaign_id=uuid.UUID(campaign_id),
        name=location_data.name,
        description=location_data.description,
        address=location_data.address,
        city=location_data.city,
        state=location_data.state,
        country=location_data.country,
        postal_code=location_data.postal_code,
        latitude=location_data.latitude,
        longitude=location_data.longitude,
        verification_radius_meters=location_data.verification_radius_meters,
        geocoding_accuracy=location_data.geocoding_accuracy,
        place_id=location_data.place_id
    )
    
    db.add(new_location)
    await db.commit()
    await db.refresh(new_location)
    
    return new_location


@router.get("/{campaign_id}/locations", response_model=List[CampaignLocationResponse])
async def list_campaign_locations(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    current_client: Client = Depends(get_current_client)
):
    """
    Get all locations for a campaign.
    """
    # Verify campaign exists and belongs to client
    result = await db.execute(
        select(Campaign).where(
            Campaign.campaign_id == uuid.UUID(campaign_id),
            Campaign.client_id == current_client.client_id
        )
    )
    campaign = result.scalar_one_or_none()
    
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found or access denied"
        )
    
    # Get all locations
    result = await db.execute(
        select(CampaignLocation).where(
            CampaignLocation.campaign_id == uuid.UUID(campaign_id)
        ).order_by(CampaignLocation.created_at)
    )
    locations = result.scalars().all()
    
    return locations


@router.get("/{campaign_id}/locations/{location_id}", response_model=CampaignLocationResponse)
async def get_campaign_location(
    campaign_id: str,
    location_id: str,
    db: AsyncSession = Depends(get_db),
    current_client: Client = Depends(get_current_client)
):
    """
    Get a specific campaign location.
    """
    # Verify campaign exists and belongs to client
    result = await db.execute(
        select(Campaign).where(
            Campaign.campaign_id == uuid.UUID(campaign_id),
            Campaign.client_id == current_client.client_id
        )
    )
    campaign = result.scalar_one_or_none()
    
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found or access denied"
        )
    
    # Get location
    result = await db.execute(
        select(CampaignLocation).where(
            CampaignLocation.location_id == uuid.UUID(location_id),
            CampaignLocation.campaign_id == uuid.UUID(campaign_id)
        )
    )
    location = result.scalar_one_or_none()
    
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found"
        )
    
    return location


@router.put("/{campaign_id}/locations/{location_id}", response_model=CampaignLocationResponse)
async def update_campaign_location(
    campaign_id: str,
    location_id: str,
    location_data: CampaignLocationUpdate,
    db: AsyncSession = Depends(get_db),
    current_client: Client = Depends(get_current_client)
):
    """
    Update a campaign location.
    
    If address is updated, it will be automatically geocoded.
    """
    # Verify campaign exists and belongs to client
    result = await db.execute(
        select(Campaign).where(
            Campaign.campaign_id == uuid.UUID(campaign_id),
            Campaign.client_id == current_client.client_id
        )
    )
    campaign = result.scalar_one_or_none()
    
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found or access denied"
        )
    
    # Get location
    result = await db.execute(
        select(CampaignLocation).where(
            CampaignLocation.location_id == uuid.UUID(location_id),
            CampaignLocation.campaign_id == uuid.UUID(campaign_id)
        )
    )
    location = result.scalar_one_or_none()
    
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found"
        )
    
    # If address is being updated, geocode it
    if location_data.address and location_data.address != location.address:
        geocoding_service = get_geocoding_service()
        geocode_result = await geocoding_service.geocode(location_data.address)
        
        if geocode_result:
            location.address = geocode_result.formatted_address
            location.latitude = geocode_result.latitude
            location.longitude = geocode_result.longitude
            location.city = geocode_result.address_components.get("city")
            location.state = geocode_result.address_components.get("state")
            location.country = geocode_result.address_components.get("country")
            location.postal_code = geocode_result.address_components.get("postal_code")
            location.geocoding_accuracy = geocode_result.accuracy
            location.place_id = geocode_result.place_id
    
    # Update other fields
    update_data = location_data.dict(exclude_unset=True, exclude={"address"})
    for field, value in update_data.items():
        setattr(location, field, value)
    
    await db.commit()
    await db.refresh(location)
    
    return location


@router.delete("/{campaign_id}/locations/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign_location(
    campaign_id: str,
    location_id: str,
    db: AsyncSession = Depends(get_db),
    current_client: Client = Depends(get_current_client)
):
    """
    Delete a campaign location.
    """
    # Verify campaign exists and belongs to client
    result = await db.execute(
        select(Campaign).where(
            Campaign.campaign_id == uuid.UUID(campaign_id),
            Campaign.client_id == current_client.client_id
        )
    )
    campaign = result.scalar_one_or_none()
    
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found or access denied"
        )
    
    # Get location
    result = await db.execute(
        select(CampaignLocation).where(
            CampaignLocation.location_id == uuid.UUID(location_id),
            CampaignLocation.campaign_id == uuid.UUID(campaign_id)
        )
    )
    location = result.scalar_one_or_none()
    
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found"
        )
    
    await db.delete(location)
    await db.commit()
    
    return None


# Geocoding endpoints
@router.post("/geocode", response_model=GeocodeResponse)
async def geocode_address(
    request: GeocodeRequest,
    current_client: Client = Depends(get_current_client)
):
    """
    Convert an address to coordinates.
    
    Uses Google Maps API if configured, otherwise falls back to OpenStreetMap Nominatim.
    """
    geocoding_service = get_geocoding_service()
    result = await geocoding_service.geocode(request.address)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to geocode address. Please check the address and try again."
        )
    
    components = result.address_components or {}
    return GeocodeResponse(
        latitude=result.latitude,
        longitude=result.longitude,
        formatted_address=result.formatted_address,
        accuracy=result.accuracy or "unknown",
        place_id=result.place_id,
        city=components.get("city"),
        state=components.get("state"),
        country=components.get("country"),
        postal_code=components.get("postal_code"),
    )


@router.post("/reverse-geocode", response_model=GeocodeResponse)
async def reverse_geocode_coordinates(
    request: ReverseGeocodeRequest,
    current_client: Client = Depends(get_current_client)
):
    """
    Convert coordinates to an address.
    
    Uses Google Maps API if configured, otherwise falls back to OpenStreetMap Nominatim.
    """
    geocoding_service = get_geocoding_service()
    result = await geocoding_service.reverse_geocode(request.latitude, request.longitude)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to reverse geocode coordinates."
        )
    
    components = result.address_components or {}
    return GeocodeResponse(
        latitude=result.latitude,
        longitude=result.longitude,
        formatted_address=result.formatted_address,
        accuracy=result.accuracy or "unknown",
        place_id=result.place_id,
        city=components.get("city"),
        state=components.get("state"),
        country=components.get("country"),
        postal_code=components.get("postal_code"),
    )


@router.post("/{campaign_id}/verify-location", response_model=LocationVerificationResponse)
async def verify_photo_location(
    campaign_id: str,
    request: ReverseGeocodeRequest,
    db: AsyncSession = Depends(get_db),
    current_client: Client = Depends(get_current_client)
):
    """
    Verify if coordinates are within acceptable range of campaign locations.
    
    Returns validation status and distance to nearest location.
    """
    # Verify campaign exists and belongs to client
    result = await db.execute(
        select(Campaign).where(
            Campaign.campaign_id == uuid.UUID(campaign_id),
            Campaign.client_id == current_client.client_id
        )
    )
    campaign = result.scalar_one_or_none()
    
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found or access denied"
        )
    
    # Verify location
    verification_service = get_location_verification_service()
    verification_result = await verification_service.verify_location(
        db,
        campaign_id,
        request.latitude,
        request.longitude
    )
    
    return LocationVerificationResponse(**verification_result.to_dict())
