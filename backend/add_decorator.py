#!/usr/bin/env python3
"""Add the missing @router.get decorator to get_current_subscription."""

with open('app/api/subscriptions.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the line with "async def get_current_subscription"
for i, line in enumerate(lines):
    if 'async def get_current_subscription' in line:
        # Check if the previous line has the decorator
        if i > 0 and '@router' not in lines[i-1]:
            # Insert the decorator
            lines.insert(i, '@router.get("/current")\n')
            print(f"✓ Added @router.get('/current') decorator at line {i+1}")
            break
else:
    print("✗ Could not find 'async def get_current_subscription'")
    exit(1)

# Write back
with open('app/api/subscriptions.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("✓ Updated app/api/subscriptions.py")
