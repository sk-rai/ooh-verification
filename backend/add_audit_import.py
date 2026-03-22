#!/usr/bin/env python3
"""Script to add audit logger import to photos.py"""

import re

# Read the file
with open('app/api/photos.py', 'r') as f:
    content = f.read()

# Check if import already exists
if 'from app.services.audit_logger import' in content:
    print("Import already exists")
    exit(0)

# Add import after s3_storage import
new_import = "from app.services.audit_logger import audit_logger, AuditFlag\nimport logging\n\nlogger = logging.getLogger(__name__)\n"

# Find the line with s3_storage import
pattern = r'(from app\.services\.s3_storage import s3_storage_service\n)'
replacement = r'\1' + new_import

content = re.sub(pattern, replacement, content)

# Write back
with open('app/api/photos.py', 'w') as f:
    f.write(content)

print("Added audit logger import")
