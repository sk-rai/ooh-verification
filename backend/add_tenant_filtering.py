#!/usr/bin/env python3
"""
Script to add tenant filtering to API route functions.

This script:
1. Adds 'request: Request' parameter to route functions
2. Adds 'tenant_id = get_current_tenant(request)' at function start
3. Adds tenant_id filtering to SELECT queries
4. Adds tenant_id when creating model instances
"""
import re
import os

def process_campaigns_py():
    """Update campaigns.py with tenant filtering."""
    filepath = 'app/api/campaigns.py'
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Update create_campaign function
    content = re.sub(
        r'(async def create_campaign\(\s*data: CampaignCreate,)',
        r'\1\n    request: Request,',
        content
    )
    
    # Add tenant_id at start of create_campaign
    content = re.sub(
        r'(async def create_campaign\([^)]+\):[\s\S]*?"""[\s\S]*?""")\s*\n(\s+# Check campaign quota)',
        r'\1\n    tenant_id = get_current_tenant(request)\n    \n\2',
        content
    )
    
    # Add tenant_id to Campaign creation
    content = re.sub(
        r'(campaign = Campaign\(\s*campaign_code=campaign_code,\s*name=data\.name,\s*campaign_type=CampaignType\(data\.campaign_type\),)',
        r'\1\n        tenant_id=tenant_id,',
        content
    )
    
    # Add tenant filter to campaign code check
    content = re.sub(
        r'(select\(Campaign\)\.where\(Campaign\.campaign_code == candidate_code\))',
        r'select(Campaign).where(Campaign.campaign_code == candidate_code, Campaign.tenant_id == tenant_id)',
        content
    )
    
    # Update list_campaigns function
    content = re.sub(
        r'(async def list_campaigns\(\s*)',
        r'\1request: Request,\n    ',
        content
    )
    
    # Add tenant_id at start of list_campaigns
    content = re.sub(
        r'(async def list_campaigns\([^)]+\):[\s\S]*?"""[\s\S]*?""")\s*\n(\s+# Build query)',
        r'\1\n    tenant_id = get_current_tenant(request)\n    \n\2',
        content
    )
    
    # Add tenant filter to list query
    content = re.sub(
        r'(query = select\(Campaign\)\.where\(Campaign\.client_id == client\.client_id\))',
        r'query = select(Campaign).where(Campaign.tenant_id == tenant_id, Campaign.client_id == client.client_id)',
        content
    )
    
    # Update get_campaign function
    content = re.sub(
        r'(async def get_campaign\(\s*campaign_id: UUID,)',
        r'\1\n    request: Request,',
        content
    )
    
    # Add tenant_id and filter to get_campaign
    content = re.sub(
        r'(async def get_campaign\([^)]+\):[\s\S]*?"""[\s\S]*?""")\s*\n(\s+result = await db\.execute)',
        r'\1\n    tenant_id = get_current_tenant(request)\n    \n\2',
        content
    )
    
    content = re.sub(
        r'(select\(Campaign\)\.where\(\s*Campaign\.campaign_id == campaign_id,\s*Campaign\.client_id == client\.client_id)',
        r'select(Campaign).where(\n            Campaign.campaign_id == campaign_id,\n            Campaign.tenant_id == tenant_id,\n            Campaign.client_id == client.client_id',
        content
    )
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"✓ {filepath}: Added tenant filtering")

def process_photos_py():
    """Update photos.py with tenant filtering."""
    filepath = 'app/api/photos.py'
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Update upload_photo function
    content = re.sub(
        r'(async def upload_photo\([^)]*\bvendor: Vendor = Depends\(get_current_vendor\),)',
        r'\1\n    request: Request,',
        content
    )
    
    # Add tenant_id at start
    content = re.sub(
        r'(async def upload_photo\([^)]+\):[\s\S]*?"""[\s\S]*?""")\s*\n(\s+# Verify campaign exists)',
        r'\1\n    tenant_id = get_current_tenant(request)\n    \n\2',
        content
    )
    
    # Add tenant_id to Photo creation
    content = re.sub(
        r'(photo = Photo\(\s*vendor_id=vendor\.vendor_id,\s*campaign_id=campaign_id,)',
        r'\1\n        tenant_id=tenant_id,',
        content
    )
    
    # Add tenant filter to campaign lookup
    content = re.sub(
        r'(select\(Campaign\)\.where\(Campaign\.campaign_id == campaign_id\))',
        r'select(Campaign).where(Campaign.campaign_id == campaign_id, Campaign.tenant_id == tenant_id)',
        content
    )
    
    # Update list_photos function
    content = re.sub(
        r'(async def list_photos\(\s*)',
        r'\1request: Request,\n    ',
        content
    )
    
    # Add tenant_id and filter
    content = re.sub(
        r'(async def list_photos\([^)]+\):[\s\S]*?"""[\s\S]*?""")\s*\n(\s+# Build base query)',
        r'\1\n    tenant_id = get_current_tenant(request)\n    \n\2',
        content
    )
    
    content = re.sub(
        r'(query = select\(Photo\)\.where\(Photo\.campaign_id\.in_\(campaign_ids\)\))',
        r'query = select(Photo).where(Photo.tenant_id == tenant_id, Photo.campaign_id.in_(campaign_ids))',
        content
    )
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"✓ {filepath}: Added tenant filtering")

def process_subscriptions_py():
    """Update subscriptions.py with tenant filtering."""
    filepath = 'app/api/subscriptions.py'
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Add request parameter to functions
    for func_name in ['get_subscription', 'create_subscription', 'update_subscription']:
        content = re.sub(
            rf'(async def {func_name}\([^)]*\bclient: Client = Depends\(get_current_active_client\),)',
            r'\1\n    request: Request,',
            content
        )
    
    # Add tenant_id at start of each function
    for func_name in ['get_subscription', 'create_subscription', 'update_subscription']:
        content = re.sub(
            rf'(async def {func_name}\([^)]+\):[\s\S]*?"""[\s\S]*?""")\s*\n(\s+[a-z#])',
            r'\1\n    tenant_id = get_current_tenant(request)\n    \n\2',
            content
        )
    
    # Add tenant filter to subscription queries
    content = re.sub(
        r'(select\(Subscription\)\.where\(Subscription\.client_id == client\.client_id\))',
        r'select(Subscription).where(Subscription.tenant_id == tenant_id, Subscription.client_id == client.client_id)',
        content
    )
    
    # Add tenant_id to Subscription creation
    content = re.sub(
        r'(subscription = Subscription\(\s*client_id=client\.client_id,)',
        r'\1\n        tenant_id=tenant_id,',
        content
    )
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"✓ {filepath}: Added tenant filtering")

def process_campaign_locations_py():
    """Update campaign_locations.py with tenant filtering."""
    filepath = 'app/api/campaign_locations.py'
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Add request parameter
    for func_name in ['create_campaign_location', 'list_campaign_locations', 'get_campaign_location', 'update_campaign_location', 'delete_campaign_location']:
        content = re.sub(
            rf'(async def {func_name}\([^)]*\bdb: AsyncSession = Depends\(get_db\))',
            r'\1,\n    request: Request',
            content
        )
    
    # Add tenant_id at start
    for func_name in ['create_campaign_location', 'list_campaign_locations', 'get_campaign_location', 'update_campaign_location', 'delete_campaign_location']:
        content = re.sub(
            rf'(async def {func_name}\([^)]+\):[\s\S]*?"""[\s\S]*?""")\s*\n(\s+[a-z#])',
            r'\1\n    tenant_id = get_current_tenant(request)\n    \n\2',
            content
        )
    
    # Add tenant filter to queries
    content = re.sub(
        r'(select\(CampaignLocation\)\.where\(CampaignLocation\.campaign_id == campaign_id\))',
        r'select(CampaignLocation).where(CampaignLocation.tenant_id == tenant_id, CampaignLocation.campaign_id == campaign_id)',
        content
    )
    
    content = re.sub(
        r'(select\(CampaignLocation\)\.where\(CampaignLocation\.location_id == location_id\))',
        r'select(CampaignLocation).where(CampaignLocation.tenant_id == tenant_id, CampaignLocation.location_id == location_id)',
        content
    )
    
    # Add tenant_id to CampaignLocation creation
    content = re.sub(
        r'(location = CampaignLocation\(\s*campaign_id=campaign_id,)',
        r'\1\n        tenant_id=tenant_id,',
        content
    )
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"✓ {filepath}: Added tenant filtering")

def process_reports_py():
    """Update reports.py with tenant filtering."""
    filepath = 'app/api/reports.py'
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Add request parameter to report functions
    for func_name in ['generate_campaign_report', 'generate_vendor_report']:
        content = re.sub(
            rf'(async def {func_name}\([^)]*\bclient: Client = Depends\(get_current_active_client\),)',
            r'\1\n    request: Request,',
            content
        )
    
    # Add tenant_id at start
    for func_name in ['generate_campaign_report', 'generate_vendor_report']:
        content = re.sub(
            rf'(async def {func_name}\([^)]+\):[\s\S]*?"""[\s\S]*?""")\s*\n(\s+[a-z#])',
            r'\1\n    tenant_id = get_current_tenant(request)\n    \n\2',
            content
        )
    
    # Add tenant filter to queries (reports typically query multiple models)
    content = re.sub(
        r'(select\(Campaign\)\.where\(Campaign\.campaign_id == campaign_id)',
        r'select(Campaign).where(Campaign.tenant_id == tenant_id, Campaign.campaign_id == campaign_id',
        content
    )
    
    content = re.sub(
        r'(select\(Vendor\)\.where\(Vendor\.vendor_id == vendor_id)',
        r'select(Vendor).where(Vendor.tenant_id == tenant_id, Vendor.vendor_id == vendor_id',
        content
    )
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"✓ {filepath}: Added tenant filtering")

# Main execution
print("Adding tenant filtering to API routes...\n")

try:
    process_campaigns_py()
    process_photos_py()
    process_subscriptions_py()
    process_campaign_locations_py()
    process_reports_py()
    print("\n✅ All routes updated with tenant filtering")
    print("\n⚠️  IMPORTANT: Review the changes and test each endpoint!")
except Exception as e:
    print(f"\n❌ Error: {str(e)}")
    print("Some files may need manual updates.")
