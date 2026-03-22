#!/usr/bin/env python3
"""
Apply tenant context to all API routes systematically.
This script uses editCode-style replacements to add tenant context.
"""
import re
from pathlib import Path

def add_tenant_context_to_function(filepath, function_name, first_code_line):
    """Add tenant_id = get_current_tenant(request) after docstring."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Pattern: Find the function and its docstring, then add tenant_id line
    pattern = rf'(async def {function_name}\([^)]+\):\s*"""[^"]*""")\s*\n(\s+{re.escape(first_code_line)})'
    replacement = r'\1\n    tenant_id = get_current_tenant(request)\n    \n\2'
    
    new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    if new_content != content:
        with open(filepath, 'w') as f:
            f.write(new_content)
        return True
    return False

# Files and functions to update
updates = [
    # campaigns.py
    ('app/api/campaigns.py', 'create_campaign', '# Check campaign quota'),
    ('app/api/campaigns.py', 'list_campaigns', '# Build query'),
    ('app/api/campaigns.py', 'get_campaign', 'result = await db.execute'),
    
    # photos.py  
    ('app/api/photos.py', 'upload_photo', '# Verify campaign exists'),
    ('app/api/photos.py', 'list_photos', '# Build base query'),
    ('app/api/photos.py', 'get_photo', 'result = await db.execute'),
    
    # subscriptions.py
    ('app/api/subscriptions.py', 'get_subscription', 'result = await db.execute'),
    ('app/api/subscriptions.py', 'create_subscription', '# Check if subscription'),
    ('app/api/subscriptions.py', 'update_subscription', 'result = await db.execute'),
    
    # campaign_locations.py
    ('app/api/campaign_locations.py', 'create_campaign_location', '# Verify campaign exists'),
    ('app/api/campaign_locations.py', 'list_campaign_locations', 'result = await db.execute'),
    ('app/api/campaign_locations.py', 'get_campaign_location', 'result = await db.execute'),
    ('app/api/campaign_locations.py', 'update_campaign_location', 'result = await db.execute'),
    ('app/api/campaign_locations.py', 'delete_campaign_location', 'result = await db.execute'),
    
    # reports.py
    ('app/api/reports.py', 'generate_campaign_report', '# Get campaign'),
    ('app/api/reports.py', 'generate_vendor_report', '# Get vendor'),
]

print("Applying tenant context to all API routes...\n")

for filepath, function_name, first_line in updates:
    if add_tenant_context_to_function(filepath, function_name, first_line):
        print(f"✓ {filepath}: {function_name}()")
    else:
        print(f"○ {filepath}: {function_name}() - already updated or pattern not found")

print("\n✅ Tenant context application complete!")
print("\nNote: This adds 'tenant_id = get_current_tenant(request)' to each function.")
print("You still need to:")
print("1. Add tenant_id filters to WHERE clauses")
print("2. Add tenant_id when creating new records")
print("3. Verify each file compiles")
