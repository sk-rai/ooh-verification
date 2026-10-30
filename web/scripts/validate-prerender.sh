#!/bin/bash
# Validate prerendered HTML: confirm real content is present without JS.
cd /home/lynksavvy/projects/trustcapture/web

check() {
  local file="$1" label="$2"
  echo "── $label ($file) ──"
  if [ ! -f "$file" ]; then echo "  MISSING"; return 1; fi
  # Title tag present and page-specific
  title=$(grep -o '<title>[^<]*</title>' "$file" | head -1)
  echo "  title: $title"
  # Meta description present
  desc=$(grep -o 'name="description" content="[^"]*"' "$file" | head -1)
  echo "  description: ${desc:0:80}..."
  # Canonical present
  canon=$(grep -o 'rel="canonical"[^>]*>' "$file" | head -1)
  echo "  canonical: $canon"
  # Root div has content (not empty)
  root_len=$(grep -o 'id="root">[^<]*\|id="root"><' "$file" | wc -c)
  full_root=$(python3 -c "
import re, sys
html=open('$file').read()
m=re.search(r'<div id=\"root\">(.*)', html, re.S)
inner=m.group(1)[:200] if m else 'NOT FOUND'
print(repr(inner[:120]))
" 2>/dev/null)
  echo "  root content: $full_root"
  # Meaningful text (product keywords)
  for kw in TrustCapture verification GPS tamper field; do
    cnt=$(grep -ic "$kw" "$file" 2>/dev/null || echo 0)
    echo -n "  keyword '$kw': $cnt  "
  done
  echo ""
}

check "dist/index.html" "Landing (/)"
echo ""
check "dist/privacy/index.html" "Privacy (/privacy)"
echo ""
check "dist/terms/index.html" "Terms (/terms)"
echo ""
check "dist/use-cases/index.html" "Use Cases (/use-cases)"
echo ""
echo "=== File sizes ==="
for f in dist/index.html dist/privacy/index.html dist/terms/index.html dist/use-cases/index.html; do
  [ -f "$f" ] && printf "  %-40s %s bytes\n" "$f" "$(wc -c < "$f")"
done
