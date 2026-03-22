#!/bin/bash
# Script to update all API routes with tenant context

echo "Updating API routes with tenant context..."
echo ""

# Backup original files
echo "Creating backups..."
cp app/api/campaigns.py app/api/campaigns_backup.py
cp app/api/photos.py app/api/photos_backup.py
cp app/api/subscriptions.py app/api/subscriptions_backup.py
cp app/api/campaign_locations.py app/api/campaign_locations_backup.py
cp app/api/reports.py app/api/reports_backup.py

echo "✓ Backups created"
echo ""

# Run Python script to add imports and basic updates
python3 << 'PYTHON_SCRIPT'
import re
import os

files_to_update = {
    'app/api/campaigns.py': 'Campaign',
    'app/api/photos.py': 'Photo',
    'app/api/subscriptions.py': 'Subscription',
    'app/api/campaign_locations.py': 'CampaignLocation',
    'app/api/reports.py': None,  # Reports may not have direct model
}

for filepath, model_name in files_to_update.items():
    if not os.path.exists(filepath):
        print(f"⚠️  {filepath} not found")
        continue
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    modified = False
    
    # 1. Add Request import if not present
    if ', Request' not in content and 'Request,' not in content:
        if 'from fastapi import' in content:
            # Find the fastapi import line
            pattern = r'from fastapi import ([^\n]+)'
            match = re.search(pattern, content)
            if match:
                imports = match.group(1)
                if 'Request' not in imports:
                    new_imports = imports.rstrip() + ', Request'
                    content = content.replace(match.group(0), f'from fastapi import {new_imports}')
                    modified = True
                    print(f"✓ {filepath}: Added Request import")
    
    # 2. Add tenant context import if not present
    if 'from app.middleware.tenant_context import get_current_tenant' not in content:
        # Find a good place to insert (after other app imports)
        pattern = r'(from app\.(?:core|models|schemas|services)[^\n]+\n)'
        matches = list(re.finditer(pattern, content))
        if matches:
            last_match = matches[-1]
            insert_pos = last_match.end()
            new_import = 'from app.middleware.tenant_context import get_current_tenant\n'
            content = content[:insert_pos] + new_import + content[insert_pos:]
            modified = True
            print(f"✓ {filepath}: Added tenant context import")
    
    if modified:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"✓ {filepath}: Updated")
    else:
        print(f"○ {filepath}: Already up to date")

print("\n✅ Import updates complete")
print("\n⚠️  MANUAL STEPS REQUIRED:")
print("For each route function in the updated files:")
print("1. Add 'request: Request' parameter")
print("2. Add 'tenant_id = get_current_tenant(request)' at the start")
print("3. Add '.where(Model.tenant_id == tenant_id)' to SELECT queries")
print("4. Add 'tenant_id=tenant_id' when creating new model instances")
print("\nSee app/api/vendors.py for reference implementation.")

PYTHON_SCRIPT

echo ""
echo "✅ Automated updates complete"
echo ""
echo "Next steps:"
echo "1. Review the changes in each file"
echo "2. Manually add tenant filtering to queries"
echo "3. Test each endpoint"
echo "4. Remove backup files when satisfied"
