#!/bin/bash
# Test DOCX upload to VPS
COOKIE_FILE=/tmp/test_cookies.txt
rm -f $COOKIE_FILE

# Get CSRF
CSRF=$(curl -s -c $COOKIE_FILE http://localhost:8000/api/v1/auth/csrf | python3 -c "import sys,json;print(json.load(sys.stdin)['csrf_token'])")

# Login
curl -s -c $COOKIE_FILE -b $COOKIE_FILE -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -H "X-CSRF-Token: $CSRF" \
  -d '{"email":"test2@mail.ru","password":"1234567890"}' > /dev/null

echo "=== USER ==="
curl -s -b $COOKIE_FILE http://localhost:8000/api/v1/auth/me

echo ""
echo "=== UPLOAD ==="
curl -s -X POST http://localhost:8000/api/v1/upload-report-stream \
  -b $COOKIE_FILE \
  -F 'file=@/tmp/test_report.docx' | python3 -m json.tool 2>&1 | head -30
