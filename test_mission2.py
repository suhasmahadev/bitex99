"""
Mission 2 — All 6 tests using only stdlib (no requests needed).
"""
import base64
import json
import os
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
import ssl

# Disable SSL verification for localhost
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

BASE = "http://localhost:8000/api/v1"

def api(method, path, body=None, token=None, files=None):
    """Make an API call. Returns (status_code, response_dict)."""
    url = f"{BASE}{path}"
    headers = {}
    data = None

    if files:
        # multipart/form-data
        boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        parts = []
        for key, value in files.items():
            if isinstance(value, tuple):
                filename, file_content, content_type = value
                parts.append(
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="{key}"; filename="{filename}"\r\n'
                    f"Content-Type: {content_type}\r\n\r\n"
                )
                parts.append(file_content)
                parts.append("\r\n")
            else:
                parts.append(
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="{key}"\r\n\r\n'
                    f"{value}\r\n"
                )
        parts.append(f"--{boundary}--\r\n")
        data = b""
        for part in parts:
            if isinstance(part, bytes):
                data += part
            else:
                data += part.encode("utf-8")
    elif body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")

    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req)
        return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body_bytes = e.read()
        try:
            return e.code, json.loads(body_bytes.decode())
        except:
            return e.code, {"raw": body_bytes.decode()}


def decode_jwt(token):
    """Decode JWT payload without verification."""
    payload_b64 = token.split(".")[1]
    payload_b64 += "=" * (4 - len(payload_b64) % 4)
    return json.loads(base64.urlsafe_b64decode(payload_b64))


def get_otp_from_redis(phone):
    """Read OTP directly from Redis using redis package."""
    import redis
    try:
        rd = redis.Redis(host='localhost', port=6379, db=0)
        otp = rd.get(f"otp:{phone}")
        if otp:
            return otp.decode()
    except Exception as e:
        print(f"Redis error: {e}")
    return None


def separator(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ═══════════════════════════════════════════════════════════════
# TEST 1 — Register as delivery partner
# ═══════════════════════════════════════════════════════════════
separator("TEST 1 — Register as Delivery Partner")

PHONE = "+919876543210"

# Send OTP
status, resp = api("POST", "/auth/send-otp", {"phone": PHONE})
print(f"\n[send-otp] Status: {status}")
print(f"Response: {json.dumps(resp, indent=2)}")

# Get OTP from Redis
otp = get_otp_from_redis(PHONE)
print(f"\nOTP from Redis: {otp}")
if not otp:
    print("ERROR: Could not retrieve OTP from Redis!")
    sys.exit(1)

# Verify OTP with register_as_partner=true
status, resp = api("POST", "/auth/verify-otp", {
    "phone": PHONE,
    "otp": otp,
    "register_as_partner": True,
})
print(f"\n[verify-otp] Status: {status}")
print(f"Response: {json.dumps(resp, indent=2)}")

partner_token = resp.get("access_token", "")
user_data = resp.get("user", {})

# Validate Test 1 expectations
t1_pass = True
if not user_data.get("fe_id", "").startswith("ZFE"):
    print("❌ FAIL: fe_id missing or doesn't start with ZFE")
    t1_pass = False
else:
    print(f"✅ fe_id: {user_data['fe_id']}")

if user_data.get("partner_status") != "PENDING_KYC":
    print(f"❌ FAIL: partner_status is '{user_data.get('partner_status')}', expected 'PENDING_KYC'")
    t1_pass = False
else:
    print(f"✅ partner_status: {user_data['partner_status']}")

if user_data.get("role") != "DELIVERY_PARTNER":
    print(f"❌ FAIL: role is '{user_data.get('role')}', expected 'DELIVERY_PARTNER'")
    t1_pass = False
else:
    print(f"✅ role: {user_data['role']}")

if resp.get("is_new_partner") is not True:
    # Might be false if user already existed from previous run
    print(f"⚠️  is_new_partner: {resp.get('is_new_partner')} (may be false on re-run)")

print(f"\n{'✅ TEST 1 PASSED' if t1_pass else '❌ TEST 1 FAILED'}")


# ═══════════════════════════════════════════════════════════════
# TEST 2 — Check JWT contains role and partner_id
# ═══════════════════════════════════════════════════════════════
separator("TEST 2 — JWT Contains role + partner_id")

payload = decode_jwt(partner_token)
print(f"\nJWT Payload: {json.dumps(payload, indent=2)}")

t2_pass = True
if payload.get("role") != "DELIVERY_PARTNER":
    print(f"❌ FAIL: JWT role is '{payload.get('role')}', expected 'DELIVERY_PARTNER'")
    t2_pass = False
else:
    print(f"✅ JWT role: {payload['role']}")

if not payload.get("partner_id"):
    print("❌ FAIL: JWT missing partner_id field")
    t2_pass = False
else:
    print(f"✅ JWT partner_id: {payload['partner_id']}")

partner_id = payload.get("partner_id", "")
print(f"\n{'✅ TEST 2 PASSED' if t2_pass else '❌ TEST 2 FAILED'}")


# ═══════════════════════════════════════════════════════════════
# TEST 3 — Protected route blocked before KYC
# ═══════════════════════════════════════════════════════════════
separator("TEST 3 — Protected Route Blocked Before KYC")

status, resp = api("POST", "/partner/duty/start", {"latitude": 19.0760, "longitude": 72.8777}, token=partner_token)
print(f"\n[duty/start] Status: {status}")
print(f"Response: {json.dumps(resp, indent=2)}")

t3_pass = True
if status != 403:
    print(f"❌ FAIL: Expected 403, got {status}")
    t3_pass = False
else:
    print("✅ Got 403 as expected")

detail = resp.get("detail", {})
if isinstance(detail, dict) and detail.get("error_code") == "KYC_NOT_APPROVED":
    print(f"✅ error_code: KYC_NOT_APPROVED")
elif isinstance(detail, str) and "KYC_NOT_APPROVED" in str(resp):
    print(f"✅ KYC_NOT_APPROVED found in response")
else:
    print(f"⚠️  Response detail: {detail}")

print(f"\n{'✅ TEST 3 PASSED' if t3_pass else '❌ TEST 3 FAILED'}")


# ═══════════════════════════════════════════════════════════════
# TEST 4 — Upload KYC document
# ═══════════════════════════════════════════════════════════════
separator("TEST 4 — Upload KYC Document")

# Create a small dummy JPEG file (valid JPEG header)
dummy_jpg = b'\xff\xd8\xff\xe0' + b'\x00' * 100 + b'\xff\xd9'

status, resp = api("POST", "/partner/kyc/upload", token=partner_token, files={
    "doc_type": "AADHAAR_FRONT",
    "file": ("test_aadhaar.jpg", dummy_jpg, "image/jpeg"),
})
print(f"\n[kyc/upload] Status: {status}")
print(f"Response: {json.dumps(resp, indent=2)}")

t4_pass = True
if status != 200:
    print(f"❌ FAIL: Expected 200, got {status}")
    t4_pass = False
else:
    docs = resp.get("documents", [])
    aadhaar_doc = [d for d in docs if d.get("doc_type") == "AADHAAR_FRONT"]
    if aadhaar_doc and aadhaar_doc[0].get("status") == "PENDING":
        print("✅ AADHAAR_FRONT uploaded with status PENDING")
    else:
        print(f"❌ FAIL: AADHAAR_FRONT not found or wrong status")
        t4_pass = False

    # Check file exists on disk
    if partner_id:
        kyc_dir = os.path.join("uploads", "kyc", partner_id)
        if os.path.exists(kyc_dir):
            files_in_dir = os.listdir(kyc_dir)
            aadhaar_files = [f for f in files_in_dir if f.startswith("AADHAAR_FRONT")]
            if aadhaar_files:
                print(f"✅ File saved to uploads/kyc/ folder: {aadhaar_files[0]}")
            else:
                print("❌ FAIL: No AADHAAR_FRONT file found in uploads dir")
                t4_pass = False
        else:
            print(f"❌ FAIL: Upload directory not found: {kyc_dir}")
            t4_pass = False

print(f"\n{'✅ TEST 4 PASSED' if t4_pass else '❌ TEST 4 FAILED'}")


# ═══════════════════════════════════════════════════════════════
# TEST 5 — Check KYC status shows missing docs
# ═══════════════════════════════════════════════════════════════
separator("TEST 5 — KYC Status Shows Missing Docs")

status, resp = api("GET", "/partner/kyc/status", token=partner_token)
print(f"\n[kyc/status] Status: {status}")
print(f"Response: {json.dumps(resp, indent=2)}")

t5_pass = True
if status != 200:
    print(f"❌ FAIL: Expected 200, got {status}")
    t5_pass = False
else:
    missing = resp.get("missing_required", [])
    can_submit = resp.get("can_submit", True)
    print(f"\nmissing_required ({len(missing)} docs): {missing}")
    print(f"can_submit: {can_submit}")

    if len(missing) == 8:
        print("✅ 8 remaining docs missing (correct)")
    else:
        print(f"⚠️  Expected 8 missing, got {len(missing)}")

    if can_submit is False:
        print("✅ can_submit: false")
    else:
        print("❌ FAIL: can_submit should be false")
        t5_pass = False

print(f"\n{'✅ TEST 5 PASSED' if t5_pass else '❌ TEST 5 FAILED'}")


# ═══════════════════════════════════════════════════════════════
# TEST 6 — Upload all remaining docs, admin approve, then duty/start
# ═══════════════════════════════════════════════════════════════
separator("TEST 6 — Admin Approve KYC → Duty/Start Works")

# Step 1: Upload remaining 8 required docs
remaining_docs = [
    "AADHAAR_BACK", "PAN_CARD",
    "DRIVING_LICENSE_FRONT", "DRIVING_LICENSE_BACK",
    "VEHICLE_RC", "VEHICLE_INSURANCE",
    "BANK_PASSBOOK", "PROFILE_PHOTO",
]

print("\nUploading remaining documents...")
for doc_type in remaining_docs:
    status, resp = api("POST", "/partner/kyc/upload", token=partner_token, files={
        "doc_type": doc_type,
        "file": (f"test_{doc_type.lower()}.jpg", dummy_jpg, "image/jpeg"),
    })
    if status == 200:
        print(f"  ✅ {doc_type} uploaded")
    else:
        print(f"  ❌ {doc_type} FAILED: {status} {resp}")

# Verify all docs uploaded
status, resp = api("GET", "/partner/kyc/status", token=partner_token)
print(f"\nAfter all uploads:")
print(f"  missing_required: {resp.get('missing_required', [])}")
print(f"  can_submit: {resp.get('can_submit')}")
print(f"  overall_status: {resp.get('overall_status')}")

# Step 2: Submit KYC
status, resp = api("POST", "/partner/kyc/submit", token=partner_token)
print(f"\n[kyc/submit] Status: {status}, Response: {json.dumps(resp, indent=2)}")

# Step 3: Create admin user and get admin token
# First, use a different phone for admin
ADMIN_PHONE = "+911111111111"
status, resp = api("POST", "/auth/send-otp", {"phone": ADMIN_PHONE})
print(f"\n[admin send-otp] Status: {status}")

admin_otp = get_otp_from_redis(ADMIN_PHONE)
print(f"Admin OTP from Redis: {admin_otp}")

if admin_otp:
    status, resp = api("POST", "/auth/verify-otp", {
        "phone": ADMIN_PHONE,
        "otp": admin_otp,
    })
    print(f"[admin verify-otp] Status: {status}")
    admin_token_temp = resp.get("access_token", "")

    # Now update this user to ADMIN role via python
    import asyncio
    async def set_admin():
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text
        engine = create_async_engine("postgresql+asyncpg://postgres:1234567890@localhost:5432/bitex")
        async with engine.begin() as conn:
            result = await conn.execute(text(f"UPDATE users SET role='ADMIN' WHERE phone='{ADMIN_PHONE}' RETURNING id, role;"))
            row = result.fetchone()
            print(f"\n[Python UPDATE to ADMIN] Updated row: {row}")
        await engine.dispose()
    asyncio.run(set_admin())

    # Re-login as admin to get token with ADMIN role
    status, resp = api("POST", "/auth/send-otp", {"phone": ADMIN_PHONE})
    admin_otp2 = get_otp_from_redis(ADMIN_PHONE)
    status, resp = api("POST", "/auth/verify-otp", {
        "phone": ADMIN_PHONE,
        "otp": admin_otp2,
    })
    print(f"[admin re-login] Status: {status}")
    admin_token = resp.get("access_token", "")
    admin_payload = decode_jwt(admin_token)
    print(f"Admin JWT role: {admin_payload.get('role')}")

    # Step 4: Admin approves KYC
    print(f"\nApproving KYC for partner_id: {partner_id}")
    status, resp = api("POST", f"/admin/kyc/{partner_id}/approve", token=admin_token)
    print(f"[admin approve] Status: {status}")
    print(f"Response: {json.dumps(resp, indent=2)}")

    t6_pass = True
    if status != 200:
        print(f"❌ FAIL: Approve returned {status}")
        t6_pass = False

    # Step 5: Verify partner_status is KYC_APPROVED in DB
    async def check_status():
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text
        engine = create_async_engine("postgresql+asyncpg://postgres:1234567890@localhost:5432/bitex")
        async with engine.connect() as conn:
            result = await conn.execute(text(f"SELECT partner_status FROM users WHERE phone='{PHONE}';"))
            row = result.fetchone()
            return row[0] if row else None
    
    db_status = asyncio.run(check_status())
    print(f"\n[DB check] partner_status: '{db_status}'")
    if "KYC_APPROVED" in db_status:
        print("✅ partner_status is KYC_APPROVED in DB")
    else:
        print(f"❌ FAIL: Expected KYC_APPROVED, got '{db_status}'")
        t6_pass = False

    # Step 6: Re-login as partner to get fresh token with updated status
    status, resp = api("POST", "/auth/send-otp", {"phone": PHONE})
    partner_otp = get_otp_from_redis(PHONE)
    status, resp = api("POST", "/auth/verify-otp", {
        "phone": PHONE,
        "otp": partner_otp,
    })
    new_partner_token = resp.get("access_token", "")
    print(f"\n[partner re-login] Status: {status}")

    # Step 7: Try duty/start — should now return 200
    status, resp = api("POST", "/partner/duty/start",
                       {"latitude": 19.0760, "longitude": 72.8777},
                       token=new_partner_token)
    print(f"\n[duty/start after approve] Status: {status}")
    print(f"Response: {json.dumps(resp, indent=2)}")

    if status == 200:
        print("✅ duty/start returns 200 after KYC approval")
    else:
        print(f"❌ FAIL: Expected 200, got {status}")
        t6_pass = False

    print(f"\n{'✅ TEST 6 PASSED' if t6_pass else '❌ TEST 6 FAILED'}")
else:
    print("❌ Could not get admin OTP")


# ═══════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════
separator("SUMMARY")
print(f"  Test 1 (Register as partner):      {'✅ PASS' if t1_pass else '❌ FAIL'}")
print(f"  Test 2 (JWT has role+partner_id):   {'✅ PASS' if t2_pass else '❌ FAIL'}")
print(f"  Test 3 (403 before KYC):           {'✅ PASS' if t3_pass else '❌ FAIL'}")
print(f"  Test 4 (Upload KYC doc):           {'✅ PASS' if t4_pass else '❌ FAIL'}")
print(f"  Test 5 (Missing docs list):        {'✅ PASS' if t5_pass else '❌ FAIL'}")
print(f"  Test 6 (Admin approve → 200):      {'✅ PASS' if t6_pass else '❌ FAIL'}")
