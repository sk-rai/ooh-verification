python3 << 'ENDSCRIPT'
import re

# Fix test_reports_api.py
with open('tests/test_reports_api.py', 'r') as f:
    content = f.read()

# Add test_vendor parameter after test_campaign in function signatures
content = re.sub(
    r'(async def test_\w+\([^)]*test_campaign: Campaign,)\s*\n(\s*)(db_session)',
    r'\1\n\2                                test_vendor,\n\2\3',
    content
)

with open('tests/test_reports_api.py', 'w') as f:
    f.write(content)

print("✓ Fixed test_reports_api.py")

# Fix test_reports_integration.py
with open('tests/test_reports_integration.py', 'r') as f:
    content = f.read()

# Fix the fixture signature
content = content.replace(
    'async def test_campaign_with_photos(db_session: AsyncSession, test_client_user: Client):',
    'async def test_campaign_with_photos(db_session: AsyncSession, test_client_user: Client, test_vendor):'
)

with open('tests/test_reports_integration.py', 'w') as f:
    f.write(content)

print("✓ Fixed test_reports_integration.py")
ENDSCRIPT