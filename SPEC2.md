You are a senior backend engineer. Read SPEC.md (the completed 
user-side API) fully before writing a single line. SPEC2.md 
extends the same monolithic FastAPI app, same PostgreSQL database 
(bitex), same JWT auth system. Add role="DELIVERY_PARTNER" to the 
existing users table. Do NOT break any existing functionality.

═══════════════════════════════════════════════════════
SECTION 1 — SCOPE
═══════════════════════════════════════════════════════
BUILD ONLY the delivery partner side:
  • Registration + KYC document submission
  • KYC verification flow (admin approves/rejects)
  • Online/offline toggle (duty status)
  • Order assignment (auto-assign nearest available partner)
  • Order acceptance / rejection with timer
  • Navigation waypoints (restaurant → customer)
  • Live GPS location broadcasting via WebSocket
  • Order lifecycle updates (picked up, delivered, failed)
  • OTP-based delivery confirmation
  • Earnings dashboard (per delivery, daily, weekly)
  • Incentive and bonus tracking
  • Performance metrics (rating, acceptance rate, completion rate)
  • Payout history and withdrawal simulation
  • Shift / login hours tracking
  • In-app support ticket system
  • Referral system (partner refers partner)
  • Surge / peak hour detection

DO NOT BUILD:
  • Restaurant admin panel (separate SPEC3.md)
  • Customer-facing UI changes

═══════════════════════════════════════════════════════
SECTION 2 — FOLDER STRUCTURE ADDITIONS
═══════════════════════════════════════════════════════
Add these to the existing app/ structure:

app/
├── models/
│   ├── delivery_partner.py      ← partner profile + KYC
│   ├── kyc_document.py          ← individual doc records
│   ├── partner_location.py      ← live GPS positions
│   ├── partner_shift.py         ← login/logout sessions
│   ├── delivery_assignment.py   ← order↔partner link
│   ├── delivery_otp.py          ← 4-digit delivery OTP
│   ├── partner_earnings.py      ← per-delivery breakdown
│   ├── payout.py                ← weekly payout records
│   ├── incentive_rule.py        ← configurable bonus rules
│   ├── partner_incentive.py     ← earned incentives
│   └── support_ticket.py        ← help tickets
│
├── schemas/
│   ├── delivery_partner.py
│   ├── kyc.py
│   ├── assignment.py
│   ├── partner_earnings.py
│   ├── payout.py
│   └── support_ticket.py
│
├── services/
│   ├── delivery_partner_service.py
│   ├── kyc_service.py
│   ├── assignment_service.py    ← auto-assign logic
│   ├── location_service.py      ← GPS update handling
│   ├── earnings_service.py
│   ├── incentive_service.py
│   ├── payout_service.py
│   └── support_service.py
│
├── routers/
│   └── delivery/
│       ├── auth.py              ← /api/v1/partner/auth
│       ├── profile.py           ← /api/v1/partner/profile
│       ├── kyc.py               ← /api/v1/partner/kyc
│       ├── duty.py              ← /api/v1/partner/duty
│       ├── assignments.py       ← /api/v1/partner/assignments
│       ├── location.py          ← /api/v1/partner/location
│       ├── earnings.py          ← /api/v1/partner/earnings
│       ├── payouts.py           ← /api/v1/partner/payouts
│       └── support.py           ← /api/v1/partner/support
│
└── utils/
    ├── assignment_engine.py     ← Haversine nearest-partner logic
    ├── surge_detector.py        ← peak hour detection
    └── delivery_otp.py          ← 4-digit OTP for delivery confirm

═══════════════════════════════════════════════════════
SECTION 3 — DATABASE SCHEMA (COMPLETE)
═══════════════════════════════════════════════════════

── users table (ALTER existing) ──────────────────────
  ADD COLUMN role VARCHAR(20) DEFAULT 'CUSTOMER'
    CHECK (role IN ('CUSTOMER','DELIVERY_PARTNER','ADMIN'))
  ADD COLUMN partner_status VARCHAR(20) DEFAULT NULL
    -- NULL for customers
    -- 'PENDING_KYC' | 'KYC_SUBMITTED' | 'KYC_APPROVED' 
    -- | 'KYC_REJECTED' | 'SUSPENDED' | 'ACTIVE'

── delivery_partners ─────────────────────────────────
  id                UUID PRIMARY KEY
  user_id           UUID FK → users.id UNIQUE ON DELETE CASCADE
  fe_id             VARCHAR(20) UNIQUE     ← Fleet Executive ID e.g. "ZFE00123"
  city              VARCHAR(100) NOT NULL
  vehicle_type      ENUM('BIKE','SCOOTER','CYCLE','EV_BIKE')
  vehicle_number    VARCHAR(20)            ← e.g. "KA01AB1234"
  vehicle_model     VARCHAR(100)
  is_online         BOOLEAN DEFAULT FALSE  ← duty toggle
  current_latitude  NUMERIC(10,7)
  current_longitude NUMERIC(10,7)
  last_location_at  TIMESTAMPTZ
  rating            NUMERIC(3,2) DEFAULT 5.0
  total_ratings     INTEGER DEFAULT 0
  acceptance_rate   NUMERIC(5,2) DEFAULT 100.0  ← %
  completion_rate   NUMERIC(5,2) DEFAULT 100.0  ← %
  total_deliveries  INTEGER DEFAULT 0
  total_earnings    NUMERIC(12,2) DEFAULT 0.00
  wallet_balance    NUMERIC(12,2) DEFAULT 0.00  ← earned not yet paid out
  referral_code     VARCHAR(20) UNIQUE
  referred_by       UUID FK → delivery_partners.id (nullable)
  joined_at         TIMESTAMPTZ DEFAULT now()
  INDEX on (city), INDEX on (is_online, city)
  INDEX on (current_latitude, current_longitude)

── kyc_documents ─────────────────────────────────────
  id                UUID PRIMARY KEY
  partner_id        UUID FK → delivery_partners.id
  doc_type          ENUM(
                      'AADHAAR_FRONT',
                      'AADHAAR_BACK',
                      'PAN_CARD',
                      'DRIVING_LICENSE_FRONT',
                      'DRIVING_LICENSE_BACK',
                      'VEHICLE_RC',
                      'VEHICLE_INSURANCE',
                      'BANK_PASSBOOK',
                      'PROFILE_PHOTO',
                      'POLICE_VERIFICATION'    ← optional
                    )
  file_url          VARCHAR(500) NOT NULL
  file_name         VARCHAR(200)
  status            ENUM('PENDING','APPROVED','REJECTED')
                    DEFAULT 'PENDING'
  rejection_reason  VARCHAR(500)
  verified_at       TIMESTAMPTZ
  uploaded_at       TIMESTAMPTZ DEFAULT now()
  UNIQUE on (partner_id, doc_type)
  INDEX on (partner_id), INDEX on (status)

── partner_locations ─────────────────────────────────
  id                UUID PRIMARY KEY
  partner_id        UUID FK → delivery_partners.id
  latitude          NUMERIC(10,7) NOT NULL
  longitude         NUMERIC(10,7) NOT NULL
  speed_kmph        NUMERIC(5,2)
  heading_degrees   INTEGER           ← 0-360 compass direction
  accuracy_meters   NUMERIC(6,2)
  recorded_at       TIMESTAMPTZ DEFAULT now()
  INDEX on (partner_id, recorded_at DESC)
  -- retain last 24 hours only (cleanup via background task)

── partner_shifts ────────────────────────────────────
  id                UUID PRIMARY KEY
  partner_id        UUID FK → delivery_partners.id
  started_at        TIMESTAMPTZ DEFAULT now()
  ended_at          TIMESTAMPTZ
  duration_minutes  INTEGER           ← computed on end
  deliveries_in_shift INTEGER DEFAULT 0
  earnings_in_shift NUMERIC(10,2) DEFAULT 0.00
  city              VARCHAR(100)
  INDEX on (partner_id, started_at DESC)

── delivery_assignments ──────────────────────────────
  id                UUID PRIMARY KEY
  order_id          UUID FK → orders.id UNIQUE
  partner_id        UUID FK → delivery_partners.id
  status            ENUM(
                      'ASSIGNED',       ← partner notified
                      'ACCEPTED',       ← partner accepted
                      'REJECTED',       ← partner rejected
                      'TIMED_OUT',      ← no response in 45s
                      'REACHED_RESTAURANT', ← partner at pickup
                      'PICKED_UP',      ← food in hand
                      'REACHED_CUSTOMER',   ← at delivery location
                      'DELIVERED',      ← completed
                      'FAILED'          ← could not deliver
                    ) DEFAULT 'ASSIGNED'
  assigned_at       TIMESTAMPTZ DEFAULT now()
  accepted_at       TIMESTAMPTZ
  rejected_at       TIMESTAMPTZ
  rejection_reason  VARCHAR(300)
  picked_up_at      TIMESTAMPTZ
  delivered_at      TIMESTAMPTZ
  failed_at         TIMESTAMPTZ
  failure_reason    VARCHAR(300)
  distance_km       NUMERIC(6,2)       ← total route distance
  restaurant_latitude  NUMERIC(10,7)   ← snapshot at assign time
  restaurant_longitude NUMERIC(10,7)
  customer_latitude    NUMERIC(10,7)   ← snapshot at assign time
  customer_longitude   NUMERIC(10,7)
  customer_address     TEXT            ← snapshot of delivery address
  customer_name        VARCHAR(100)    ← snapshot
  customer_phone       VARCHAR(15)     ← masked: +91 XXXXX 05678
  INDEX on (partner_id, status)
  INDEX on (order_id)

── delivery_otps ─────────────────────────────────────
  id                UUID PRIMARY KEY
  assignment_id     UUID FK → delivery_assignments.id UNIQUE
  otp               VARCHAR(4) NOT NULL
  is_used           BOOLEAN DEFAULT FALSE
  created_at        TIMESTAMPTZ DEFAULT now()
  expires_at        TIMESTAMPTZ        ← created_at + 30 minutes

── partner_earnings ──────────────────────────────────
  id                UUID PRIMARY KEY
  partner_id        UUID FK → delivery_partners.id
  assignment_id     UUID FK → delivery_assignments.id
  order_id          UUID FK → orders.id
  base_pay          NUMERIC(8,2) NOT NULL   ← ₹25 base
  distance_pay      NUMERIC(8,2) DEFAULT 0  ← ₹8/km beyond 3km
  surge_pay         NUMERIC(8,2) DEFAULT 0  ← peak hour bonus
  incentive_pay     NUMERIC(8,2) DEFAULT 0  ← daily/weekly slab
  tip_amount        NUMERIC(8,2) DEFAULT 0
  total_earned      NUMERIC(8,2) NOT NULL   ← sum of above
  earned_at         TIMESTAMPTZ DEFAULT now()
  INDEX on (partner_id, earned_at DESC)

── payouts ───────────────────────────────────────────
  id                UUID PRIMARY KEY
  partner_id        UUID FK → delivery_partners.id
  amount            NUMERIC(10,2) NOT NULL
  payout_period_start DATE NOT NULL
  payout_period_end   DATE NOT NULL
  status            ENUM('PENDING','PROCESSING','PAID','FAILED')
                    DEFAULT 'PENDING'
  bank_account      VARCHAR(20)   ← last 4 digits shown
  utr_number        VARCHAR(50)   ← bank transfer reference
  initiated_at      TIMESTAMPTZ DEFAULT now()
  paid_at           TIMESTAMPTZ
  INDEX on (partner_id, status)

── incentive_rules ───────────────────────────────────
  id                UUID PRIMARY KEY
  name              VARCHAR(200) NOT NULL    ← "Daily 10 Orders Bonus"
  type              ENUM('DAILY_ORDERS','WEEKLY_ORDERS',
                         'PEAK_HOUR','RAIN_BONUS',
                         'CONSECUTIVE_DAYS','ACCEPTANCE_RATE')
  threshold_value   INTEGER         ← e.g. 10 (orders), 80 (%)
  bonus_amount      NUMERIC(8,2) NOT NULL
  city              VARCHAR(100)    ← NULL = all cities
  valid_from        TIMESTAMPTZ
  valid_until       TIMESTAMPTZ
  is_active         BOOLEAN DEFAULT TRUE

── partner_incentives ────────────────────────────────
  id                UUID PRIMARY KEY
  partner_id        UUID FK → delivery_partners.id
  rule_id           UUID FK → incentive_rules.id
  bonus_amount      NUMERIC(8,2) NOT NULL
  reason            VARCHAR(300)
  earned_at         TIMESTAMPTZ DEFAULT now()
  payout_id         UUID FK → payouts.id (nullable)
  INDEX on (partner_id, earned_at DESC)

── support_tickets ───────────────────────────────────
  id                UUID PRIMARY KEY
  partner_id        UUID FK → delivery_partners.id
  assignment_id     UUID FK → delivery_assignments.id (nullable)
  category          ENUM('EARNINGS','ORDER_ISSUE','APP_BUG',
                         'PAYMENT','ACCOUNT','SAFETY','OTHER')
  subject           VARCHAR(300) NOT NULL
  description       TEXT NOT NULL
  status            ENUM('OPEN','IN_PROGRESS','RESOLVED','CLOSED')
                    DEFAULT 'OPEN'
  created_at        TIMESTAMPTZ DEFAULT now()
  resolved_at       TIMESTAMPTZ
  INDEX on (partner_id, status)

═══════════════════════════════════════════════════════
SECTION 4 — AUTH FLOW (DELIVERY PARTNER)
═══════════════════════════════════════════════════════
Uses the SAME OTP auth endpoints as customers:
  POST /api/v1/auth/send-otp  → same endpoint, same logic
  POST /api/v1/auth/verify-otp
    Body adds optional field: { register_as_partner: bool }
    If register_as_partner=true:
      Set users.role = 'DELIVERY_PARTNER'
      Set users.partner_status = 'PENDING_KYC'
      Create delivery_partners record with auto-generated fe_id
      fe_id format: "ZFE" + zero-padded 5-digit sequence e.g. "ZFE00001"
      Generate referral_code: random 8 char alphanumeric
      Return is_new_partner: true in response

JWT payload for partners:
  { sub: user_id, phone: phone, role: "DELIVERY_PARTNER",
    partner_id: delivery_partner.id, jti: uuid, exp: expiry }

All /api/v1/partner/* routes require:
  1. Valid JWT
  2. role = "DELIVERY_PARTNER"
  3. partner_status = "KYC_APPROVED" (except KYC upload routes)

Create dependency: require_approved_partner()
  Raises 403 if KYC not approved with message:
  "Your account is under verification. Status: {partner_status}"

═══════════════════════════════════════════════════════
SECTION 5 — KYC MODULE
═══════════════════════════════════════════════════════
Exactly like Zomato's onboarding flow.

Documents required (MUST ALL be uploaded before approval):
  REQUIRED (mandatory):
    AADHAAR_FRONT          ← clear photo of front
    AADHAAR_BACK           ← clear photo of back
    PAN_CARD               ← clear photo
    DRIVING_LICENSE_FRONT  ← valid DL front
    DRIVING_LICENSE_BACK   ← valid DL back
    VEHICLE_RC             ← Registration Certificate
    VEHICLE_INSURANCE      ← valid insurance cert
    BANK_PASSBOOK          ← or cancelled cheque
    PROFILE_PHOTO          ← selfie / headshot

  OPTIONAL:
    POLICE_VERIFICATION    ← some cities require this

Endpoints under /api/v1/partner/kyc:
  Auth: JWT required. KYC_APPROVED NOT required for these routes.

  GET /kyc/status
    Returns: list of all doc_types with upload status
    {
      "overall_status": "KYC_SUBMITTED",
      "documents": [
        {
          "doc_type": "AADHAAR_FRONT",
          "status": "APPROVED",
          "uploaded_at": "...",
          "rejection_reason": null
        },
        {
          "doc_type": "PAN_CARD",
          "status": "PENDING",
          ...
        },
        {
          "doc_type": "VEHICLE_RC",
          "status": null,     ← not uploaded yet
          "uploaded_at": null
        }
      ],
      "missing_required": ["VEHICLE_INSURANCE"],
      "can_submit": false     ← true only when all required uploaded
    }

  POST /kyc/upload
    Body: multipart/form-data
      doc_type: str (must be valid enum value)
      file: UploadFile (JPEG/PNG/PDF, max 5MB)
    Logic:
      1. Validate doc_type is valid enum
      2. Validate file size <= 5MB
      3. Validate file type (image/jpeg, image/png, application/pdf)
      4. Simulate file storage: save to local path 
         uploads/kyc/{partner_id}/{doc_type}_{timestamp}.{ext}
      5. Upsert kyc_document record (INSERT or UPDATE if re-upload)
      6. Set status = PENDING on every upload
      7. Check if ALL required docs are uploaded →
         if yes, set users.partner_status = 'KYC_SUBMITTED'
      8. Return updated kyc status

  POST /kyc/submit
    Logic:
      1. Verify all required docs are uploaded (not just status=PENDING)
      2. Verify partner_status = 'KYC_SUBMITTED'
      3. Notify admin (log to console in dev)
      4. Return: "Your KYC has been submitted for review. 
                  Verification takes 2-7 working days."

── Admin KYC endpoints (require role=ADMIN) ──────────
  GET /api/v1/admin/kyc/pending
    Returns list of partners with status KYC_SUBMITTED
    with all their document URLs

  POST /api/v1/admin/kyc/{partner_id}/approve
    Logic:
      1. Set all kyc_documents status = APPROVED
      2. Set users.partner_status = 'KYC_APPROVED'
      3. Create partner notification: "KYC Approved! Start delivering now."

  POST /api/v1/admin/kyc/{partner_id}/reject
    Body: { doc_type: str, reason: str }
    Logic:
      1. Set specific document status = REJECTED
      2. Set document rejection_reason
      3. Set users.partner_status = 'KYC_REJECTED'
      4. Partner must re-upload that document and resubmit

═══════════════════════════════════════════════════════
SECTION 6 — DUTY TOGGLE (ONLINE/OFFLINE)
═══════════════════════════════════════════════════════
Exactly like Zomato's green/grey availability switch.

POST /api/v1/partner/duty/start
  Auth: require_approved_partner()
  Logic:
    1. Check partner is not already online → 409 if yes
    2. Require current location in body: { latitude, longitude }
    3. Validate coordinates are within partner's registered city
       (rough bounding box check)
    4. Set delivery_partners.is_online = TRUE
    5. Update current_latitude, current_longitude, last_location_at
    6. INSERT partner_shift record with started_at = now()
    7. Return: { status: "ONLINE", shift_id, message: "You are now online" }

POST /api/v1/partner/duty/stop
  Auth: require_approved_partner()
  Logic:
    1. Check partner is online → 409 if already offline
    2. Fetch active shift (ended_at IS NULL)
    3. If partner has an ACTIVE assignment (status ACCEPTED or PICKED_UP)
       → return 409: "Cannot go offline during an active delivery"
    4. Set delivery_partners.is_online = FALSE
    5. Update shift: ended_at = now(),
       duration_minutes = diff in minutes,
       earnings_in_shift from earnings table
    6. Return shift summary: { duration_minutes, deliveries_in_shift,
                               earnings_in_shift }

GET /api/v1/partner/duty/status
  Returns:
  {
    "is_online": true,
    "current_shift": {
      "shift_id": "...",
      "started_at": "...",
      "duration_minutes": 45,
      "deliveries_so_far": 3,
      "earnings_so_far": 165.00
    },
    "active_assignment": null or { ...assignment details... }
  }

═══════════════════════════════════════════════════════
SECTION 7 — ORDER ASSIGNMENT ENGINE
═══════════════════════════════════════════════════════
This is the core logistics algorithm.

Trigger: When an order is placed by customer (order status → PLACED)
         AND restaurant confirms (status → CONFIRMED):
         Call auto_assign_partner(order_id)

auto_assign_partner logic in assignment_service.py:

  Step 1: Fetch the order with restaurant lat/lng
  
  Step 2: Find eligible partners using this exact query:
    SELECT dp.*, 
      (6371 * acos(
        cos(radians(restaurant.latitude)) 
        * cos(radians(dp.current_latitude))
        * cos(radians(dp.current_longitude) - radians(restaurant.longitude))
        + sin(radians(restaurant.latitude)) 
        * sin(radians(dp.current_latitude))
      )) AS distance_km
    FROM delivery_partners dp
    WHERE dp.is_online = TRUE
      AND dp.city = restaurant.city
      AND dp.last_location_at > now() - INTERVAL '5 minutes'
      AND NOT EXISTS (
        SELECT 1 FROM delivery_assignments da 
        WHERE da.partner_id = dp.id 
        AND da.status IN ('ASSIGNED','ACCEPTED','PICKED_UP')
      )
    ORDER BY distance_km ASC
    LIMIT 5
    
  Step 3: If no partners found:
    Store in Redis: SET "unassigned:{order_id}" 1 EX 600
    Retry every 30 seconds for up to 10 minutes
    After 10 min: mark order as FAILED, notify customer

  Step 4: Assign to nearest partner:
    INSERT delivery_assignment with status=ASSIGNED
    Compute delivery_otp: 4-digit random (secrets.randbelow(9000)+1000)
    INSERT delivery_otp record (expires 30 min)
    Store in Redis: SET "assignment:{partner_id}" order_id EX 45
    (45 second acceptance window)
    
  Step 5: Notify partner via WebSocket if connected
    Push to partner's WS channel:
    {
      "event": "NEW_ORDER",
      "assignment_id": "...",
      "order": {
        "restaurant_name": "Burger Barn",
        "restaurant_address": "...",
        "restaurant_lat": 19.0760,
        "restaurant_lng": 72.8777,
        "customer_address": "123 MG Road",  ← delivery address
        "customer_lat": 19.0820,
        "customer_lng": 72.8850,
        "items_summary": "Crispy Chicken x2, Coke x1",
        "order_total": 670.00,
        "estimated_earnings": 55.00,   ← base + distance preview
        "distance_km": 2.3
      },
      "expires_in_seconds": 45
    }

  Step 6: If partner does NOT respond in 45 seconds:
    Set assignment status = TIMED_OUT
    Decrement acceptance_rate slightly
    Move to next nearest partner (Step 4 with next in list)
    Log: "Order {id} timed out for partner {id}, trying next"

═══════════════════════════════════════════════════════
SECTION 8 — ASSIGNMENT ENDPOINTS
═══════════════════════════════════════════════════════

POST /api/v1/partner/assignments/{id}/accept
  Auth: require_approved_partner()
  Logic:
    1. Fetch assignment → verify belongs to this partner
    2. Check status == ASSIGNED → else 409
    3. Check Redis "assignment:{partner_id}" still exists
       (not expired = still within 45s window)
       → if expired return 409: "Assignment window expired"
    4. Set status = ACCEPTED, accepted_at = now()
    5. Update order status → OUT_FOR_DELIVERY 
       (assignment accepted = rider is coming)
    6. Broadcast to customer WebSocket:
       { event: "PARTNER_ASSIGNED", 
         partner_name: "Rahul", 
         partner_rating: 4.8,
         vehicle_number: "KA01AB1234",
         estimated_pickup_time: "8 mins" }
    7. Delete Redis key
    8. Return full assignment with navigation waypoints:
       {
         "assignment_id": "...",
         "waypoints": [
           {
             "step": 1,
             "type": "PICKUP",
             "label": "Burger Barn",
             "address": "...",
             "latitude": 19.0760,
             "longitude": 72.8777,
             "instructions": "Collect order and verify items"
           },
           {
             "step": 2,
             "type": "DELIVERY",
             "label": "Customer: Rahul",
             "address": "123 MG Road, Flat 4B",
             "latitude": 19.0820,
             "longitude": 72.8850,
             "instructions": "Call customer if gate is closed",
             "delivery_otp": "7842"  ← show to partner only
           }
         ]
       }

POST /api/v1/partner/assignments/{id}/reject
  Auth: require_approved_partner()
  Body: { reason: str (optional) }
  Logic:
    1. Verify assignment belongs to this partner
    2. Status must be ASSIGNED
    3. Set status = REJECTED, rejection_reason
    4. Decrement acceptance_rate:
       new_rate = ((old_rate * total_orders) - 100) / (total_orders + 1)
       (every rejection reduces acceptance rate)
    5. Trigger next-partner assignment from queue
    6. Return: { message: "Order rejected" }

POST /api/v1/partner/assignments/{id}/reached-restaurant
  Logic:
    1. Verify assignment ACCEPTED
    2. Set status = REACHED_RESTAURANT
    3. Broadcast to customer:
       { event: "PARTNER_AT_RESTAURANT",
         message: "Your delivery partner has reached the restaurant" }

POST /api/v1/partner/assignments/{id}/picked-up
  Logic:
    1. Verify status == REACHED_RESTAURANT or ACCEPTED
    2. Set status = PICKED_UP, picked_up_at = now()
    3. Update order status → stays OUT_FOR_DELIVERY
    4. Broadcast to customer:
       { event: "ORDER_PICKED_UP",
         message: "Your food is on the way!",
         estimated_delivery_minutes: calculated_from_distance }

POST /api/v1/partner/assignments/{id}/reached-customer
  Logic:
    1. Verify status == PICKED_UP
    2. Set status = REACHED_CUSTOMER
    3. Broadcast to customer:
       { event: "PARTNER_AT_DOOR",
         message: "Your delivery partner is at your location.
                   Please share the 4-digit OTP to confirm delivery." }

POST /api/v1/partner/assignments/{id}/deliver
  Body: { otp: str }   ← customer reads OTP from their app
  Logic:
    1. Verify status == REACHED_CUSTOMER or PICKED_UP
    2. Fetch delivery_otp record for this assignment
    3. Check is_used == FALSE → if used return 409 "OTP already used"
    4. Check expires_at > now() → if expired return 409
    5. If otp != delivery_otp.otp → return 401 "Invalid OTP"
    6. Mark delivery_otp.is_used = TRUE
    7. Set assignment status = DELIVERED, delivered_at = now()
    8. Update order status → DELIVERED
    9. Update order.delivered_at = now()
   10. Compute earnings and insert partner_earnings:
       base_pay = 25.00
       distance_pay = max(0, (distance_km - 3) * 8)
       surge_pay = check surge_detector for current time/area
       total = base_pay + distance_pay + surge_pay + tip_amount
   11. Update delivery_partners.total_deliveries += 1
   12. Update delivery_partners.total_earnings += total
   13. Update delivery_partners.wallet_balance += total
   14. Update partner_shift deliveries_in_shift + earnings_in_shift
   15. Check incentive rules → award any triggered incentives
   16. Broadcast to customer:
       { event: "DELIVERED",
         message: "Order delivered! Enjoy your meal 😊" }
   17. Return earnings breakdown for this delivery

POST /api/v1/partner/assignments/{id}/failed
  Body: { reason: ENUM('CUSTOMER_UNAVAILABLE','ADDRESS_NOT_FOUND',
                        'CUSTOMER_REFUSED','OTHER'),
          description: str }
  Logic:
    1. Verify status is PICKED_UP or REACHED_CUSTOMER
    2. Max 3 delivery attempts before marking failed
    3. Set status = FAILED
    4. Update order status = FAILED
    5. Partial pay to partner: 50% of base_pay
    6. Return instructions: "Return food to restaurant or dispose 
                             as per your city's policy"

GET /api/v1/partner/assignments/active
  Returns current active assignment (if any) with waypoints.
  Partners check this on app start to restore in-progress delivery.

GET /api/v1/partner/assignments/history
  Query: page, limit, status (optional)
  Returns paginated assignment history newest first.

═══════════════════════════════════════════════════════
SECTION 9 — LIVE GPS LOCATION
═══════════════════════════════════════════════════════

WebSocket: /api/v1/ws/partner/location?token={jwt}

  On connect:
    1. Validate JWT → must be DELIVERY_PARTNER role
    2. Verify partner is_online = TRUE
    3. Store connection in ConnectionManager keyed by partner_id
    4. Send: { event: "CONNECTED", message: "Location tracking active" }

  On message (partner sends location every 5 seconds):
    Expected format:
    {
      "latitude": 19.0761,
      "longitude": 72.8778,
      "speed_kmph": 24.5,
      "heading_degrees": 180,
      "accuracy_meters": 8.2
    }
    
    Processing:
    1. Validate lat/lng ranges
    2. UPDATE delivery_partners SET 
         current_latitude, current_longitude, last_location_at
    3. INSERT partner_locations record (history log)
    4. If partner has active assignment (ACCEPTED/PICKED_UP):
         Broadcast location to customer's WS channel:
         {
           "event": "PARTNER_LOCATION_UPDATE",
           "latitude": 19.0761,
           "longitude": 72.8778,
           "heading_degrees": 180,
           "estimated_minutes": calculated_from_haversine
         }
    5. Respond to partner:
         { "event": "LOCATION_RECEIVED", "timestamp": "..." }

  On disconnect:
    Remove from ConnectionManager.
    Do NOT set is_online=FALSE (partner may reconnect).
    is_online only changes via duty/stop endpoint.

HTTP fallback for location (for partners without WS):
  POST /api/v1/partner/location/update
    Body: { latitude, longitude, speed_kmph, heading_degrees }
    Same logic as WS message processing.
    Returns: { received: true, active_assignment: null or id }

═══════════════════════════════════════════════════════
SECTION 10 — EARNINGS MODULE
═══════════════════════════════════════════════════════

Earnings calculation per delivery (in earnings_service.py):

  BASE_PAY = ₹25.00 (flat per delivery)
  
  DISTANCE_PAY:
    First 3km: included in base
    3-4km: +₹8
    4-5km: +₹16 (cumulative)
    5-6km: +₹24
    Beyond 6km: +₹10 per additional km
    Formula: max(0, (distance_km - 3)) * 8
  
  SURGE_PAY (check surge_detector.py):
    Peak hours: 12:00-14:00 and 19:00-22:00 IST → +₹10/delivery
    Late night: 23:00-02:00 IST → +₹15/delivery
    Rain bonus (manual toggle by admin): +₹20/delivery
    Weekend (Sat/Sun): +₹5/delivery
    Determine using: current IST time + is_surge flag in Redis
  
  TIP: if customer tipped → add directly
  
  TOTAL = base_pay + distance_pay + surge_pay + tip_amount

GET /api/v1/partner/earnings/today
  Returns:
  {
    "date": "2026-04-24",
    "total_earned": 385.00,
    "deliveries_completed": 8,
    "breakdown": {
      "base_pay": 200.00,
      "distance_pay": 80.00,
      "surge_pay": 80.00,
      "tips": 25.00,
      "incentives": 0.00
    },
    "shift_hours": 5.5,
    "avg_per_delivery": 48.13
  }

GET /api/v1/partner/earnings/weekly
  Returns last 7 days with daily breakdown.
  Include: earnings chart data (array of {date, amount}).

GET /api/v1/partner/earnings/history
  Query: page, limit, from_date, to_date
  Returns paginated partner_earnings records.

GET /api/v1/partner/earnings/delivery/{assignment_id}
  Returns detailed breakdown for single delivery.

═══════════════════════════════════════════════════════
SECTION 11 — INCENTIVE SYSTEM
═══════════════════════════════════════════════════════
Exactly like Zomato's "Touchpoints" incentive structure.

Check incentives after every DELIVERED:
  in incentive_service.check_and_award(partner_id, date)

Incentive rules (seed these in seed.py):
  Rule 1 — Daily 8 Orders:
    type: DAILY_ORDERS, threshold: 8, bonus: ₹100
    "Complete 8 deliveries today to earn ₹100 bonus"

  Rule 2 — Daily 12 Orders:
    type: DAILY_ORDERS, threshold: 12, bonus: ₹200
    "Complete 12 deliveries today to earn ₹200 bonus"

  Rule 3 — Weekly 50 Orders:
    type: WEEKLY_ORDERS, threshold: 50, bonus: ₹500
    "Complete 50 deliveries this week to earn ₹500 bonus"

  Rule 4 — Peak Hour 5 Orders:
    type: PEAK_HOUR, threshold: 5, bonus: ₹75
    "Complete 5 deliveries during peak hours to earn ₹75"

  Rule 5 — 5 Consecutive Login Days:
    type: CONSECUTIVE_DAYS, threshold: 5, bonus: ₹150
    "Stay active for 5 days straight to earn ₹150"

  Rule 6 — High Acceptance Rate:
    type: ACCEPTANCE_RATE, threshold: 90, bonus: ₹50
    "Maintain 90%+ acceptance rate for weekly ₹50 bonus"

GET /api/v1/partner/incentives/active
  Returns currently available incentive rules with progress:
  {
    "incentives": [
      {
        "rule_id": "...",
        "name": "Daily 8 Orders Bonus",
        "bonus_amount": 100.00,
        "progress": 5,
        "threshold": 8,
        "remaining": 3,
        "progress_percent": 62.5,
        "description": "Complete 3 more deliveries to earn ₹100"
      }
    ]
  }

GET /api/v1/partner/incentives/earned
  Returns earned incentives (paginated, newest first).

═══════════════════════════════════════════════════════
SECTION 12 — PAYOUT SYSTEM
═══════════════════════════════════════════════════════
Zomato pays every Monday for the previous week.

GET /api/v1/partner/payouts
  Returns payout history (paginated).
  Each payout shows: period, amount, status, bank, utr_number.

GET /api/v1/partner/payouts/pending
  Returns unpaid earnings:
  {
    "pending_amount": 1250.00,
    "pending_deliveries": 28,
    "next_payout_date": "2026-04-28",  ← next Monday
    "breakdown": {
      "delivery_earnings": 1100.00,
      "incentive_earnings": 150.00,
      "tips": 0.00
    }
  }

POST /api/v1/partner/payouts/request
  Simulate instant withdrawal (like Zomato's "pocket" feature):
  Body: { amount: float }
  Logic:
    1. Validate amount <= wallet_balance
    2. Validate amount >= 50 (minimum withdrawal)
    3. Deduct from wallet_balance
    4. Create payout record with status PROCESSING
    5. Simulate: after 2 seconds set status PAID + fake UTR number
    6. Return: { message: "₹{amount} transferred to your bank account",
                 utr_number: "ZOMTXN{timestamp}", 
                 expected_time: "Within 2 hours" }

═══════════════════════════════════════════════════════
SECTION 13 — PERFORMANCE METRICS
═══════════════════════════════════════════════════════

GET /api/v1/partner/profile/stats
  Returns comprehensive performance dashboard:
  {
    "partner": {
      "name": "Rahul Kumar",
      "fe_id": "ZFE00123",
      "city": "Mumbai",
      "vehicle_type": "BIKE",
      "joined_days_ago": 45,
      "profile_photo_url": "..."
    },
    "ratings": {
      "overall_rating": 4.8,
      "total_ratings": 234,
      "rating_breakdown": {
        "5_star": 180,
        "4_star": 40,
        "3_star": 10,
        "2_star": 3,
        "1_star": 1
      }
    },
    "performance": {
      "acceptance_rate": 94.5,
      "completion_rate": 97.2,
      "avg_delivery_time_minutes": 28,
      "on_time_delivery_rate": 91.0
    },
    "totals": {
      "total_deliveries": 234,
      "total_earnings": 12840.00,
      "total_hours_online": 310,
      "total_km_covered": 1240
    },
    "this_week": {
      "deliveries": 28,
      "earnings": 1540.00,
      "hours_online": 38
    },
    "level": "GOLD",       ← BRONZE < 100, SILVER < 500, GOLD < 1000, PLATINUM 1000+
    "badges": ["On-Time King", "Top Earner", "5-Star Rider"]
  }

PATCH /api/v1/partner/profile
  Update: name, vehicle_type, vehicle_number, vehicle_model.
  Cannot update: phone (goes through auth), city (admin only).

── Customer rating of delivery partner ───────────────
When customer submits review (existing review endpoint):
  Add optional field: delivery_partner_rating (1-5)
  
  In review_service.create_review:
    If delivery_partner_rating provided:
      Fetch assignment for this order
      If assignment exists:
        Recalculate partner rating atomically:
        UPDATE delivery_partners SET
          rating = ((rating * total_ratings) + new_rating) / (total_ratings + 1),
          total_ratings = total_ratings + 1
        WHERE id = assignment.partner_id

═══════════════════════════════════════════════════════
SECTION 14 — SURGE DETECTOR
═══════════════════════════════════════════════════════
File: app/utils/surge_detector.py

  is_surge_active(city: str) → bool
    Checks Redis key "surge:{city}" first (manual admin toggle)
    Then checks current IST time:
      12:00-14:00 → True (lunch peak)
      19:00-22:00 → True (dinner peak)
      23:00-02:00 → True (late night)
      else → False

  get_surge_multiplier(city: str) → float
    Returns surge pay amount for current time:
      Peak hours → 10.0
      Late night → 15.0
      Rain bonus → 20.0 (only if "surge:rain:{city}" key exists)
      Weekend extra → 5.0 (if today is Sat/Sun)
      Returns sum of applicable multipliers

Admin endpoints:
  POST /api/v1/admin/surge/enable
    Body: { city: str, type: "RAIN" | "MANUAL", duration_minutes: int }
    Sets Redis: SET "surge:{type}:{city}" 1 EX {duration*60}

  POST /api/v1/admin/surge/disable
    Body: { city: str, type: str }
    Deletes Redis key

  GET /api/v1/admin/surge/status
    Returns all active surge keys and their TTLs.

═══════════════════════════════════════════════════════
SECTION 15 — REFERRAL SYSTEM
═══════════════════════════════════════════════════════
Partner refers another partner.

POST /api/v1/partner/referral/apply
  Body: { referral_code: str }
  Logic:
    1. Only allowed if partner's referred_by IS NULL
    2. Fetch referrer by referral_code
    3. referrer cannot refer themselves
    4. Set current partner.referred_by = referrer.id
    5. Credit referrer wallet: +₹500 bonus
    6. Credit current partner wallet: +₹200 joining bonus
    7. Create incentive records for both
    8. Return: { message: "Referral applied! You earned ₹200 bonus." }

GET /api/v1/partner/referral/stats
  Returns:
  {
    "my_referral_code": "ZFE0A1B2",
    "total_referred": 3,
    "total_referral_earned": 1500.00,
    "referred_partners": [
      { "name": "Vijay K", "joined_at": "...", "bonus_earned": 500.00 }
    ]
  }

═══════════════════════════════════════════════════════
SECTION 16 — SUPPORT TICKETS
═══════════════════════════════════════════════════════

POST /api/v1/partner/support/tickets
  Body: { category, subject, description, assignment_id (optional) }
  Creates support ticket with status OPEN.

GET /api/v1/partner/support/tickets
  Returns paginated tickets for this partner.

GET /api/v1/partner/support/tickets/{id}
  Returns ticket detail.

── Admin support endpoints ───────────────────────────
  GET /api/v1/admin/support/tickets
    Query: status, category, page, limit
    Returns all tickets for admin.

  PATCH /api/v1/admin/support/tickets/{id}
    Body: { status, resolution_note }
    Updates ticket status.

═══════════════════════════════════════════════════════
SECTION 17 — WEBSOCKET ARCHITECTURE
═══════════════════════════════════════════════════════
Two separate WS connections:

WS 1 — Partner receives orders + notifications:
  /api/v1/ws/partner/orders?token={jwt}
  Partner connects on app open.
  Server pushes: NEW_ORDER, ORDER_CANCELLED, INCENTIVE_EARNED,
                 SURGE_ACTIVATED, SYSTEM_MESSAGE

WS 2 — Partner sends live location:
  /api/v1/ws/partner/location?token={jwt}
  Partner sends GPS every 5 seconds while online.
  Server forwards to customer tracking channel.

ConnectionManager (singleton in app.state):
  partner_order_connections: Dict[str, WebSocket]
  partner_location_connections: Dict[str, WebSocket]
  customer_tracking_connections: Dict[str, WebSocket]
                                 (already exists from user side)

  Methods:
    connect_partner_orders(partner_id, ws)
    disconnect_partner_orders(partner_id)
    send_to_partner(partner_id, message)
    broadcast_location_to_customer(order_id, location_data)

═══════════════════════════════════════════════════════
SECTION 18 — LOCATION CLEANUP BACKGROUND TASK
═══════════════════════════════════════════════════════
Add to app startup (via FastAPI lifespan):

  Every 1 hour: DELETE FROM partner_locations 
    WHERE recorded_at < now() - INTERVAL '24 hours'
  
  Every 5 minutes: Find partners where:
    is_online = TRUE AND last_location_at < now() - INTERVAL '10 minutes'
    Auto set is_online = FALSE (stale location = app crashed)
    Close their active shift.
    Log: "Partner {id} auto-offlined due to stale location"

Implement using asyncio.create_task() in lifespan.

═══════════════════════════════════════════════════════
SECTION 19 — ALEMBIC MIGRATIONS
═══════════════════════════════════════════════════════
Create migrations in this exact order:

  alembic revision -m "add_role_to_users"
  alembic revision -m "create_delivery_partners"
  alembic revision -m "create_kyc_documents"
  alembic revision -m "create_partner_locations"
  alembic revision -m "create_partner_shifts"
  alembic revision -m "create_delivery_assignments"
  alembic revision -m "create_delivery_otps"
  alembic revision -m "create_partner_earnings"
  alembic revision -m "create_payouts"
  alembic revision -m "create_incentive_rules"
  alembic revision -m "create_partner_incentives"
  alembic revision -m "create_support_tickets"

Run: alembic upgrade head
Show: psql -d bitex -c "\dt" → must show all tables (22+ total)

═══════════════════════════════════════════════════════
SECTION 20 — SEED DATA (seed_partner.py)
═══════════════════════════════════════════════════════
Create seed_partner.py (separate from seed.py, idempotent):

  - 5 approved delivery partners (KYC_APPROVED, is_online=True)
    Each in a different city: Mumbai x2, Delhi x2, Bangalore x1
    With realistic coordinates inside the city
    FE IDs: ZFE00001 through ZFE00005
    
  - 1 pending partner (KYC_SUBMITTED, awaiting approval)
  
  - 3 incentive rules (DAILY_ORDERS 8→₹100, DAILY_ORDERS 12→₹200, 
    PEAK_HOUR 5→₹75)
    
  - Sample earnings for each partner (last 7 days)
  
  - 1 completed assignment linked to an existing seeded order

═══════════════════════════════════════════════════════
SECTION 21 — TESTS
═══════════════════════════════════════════════════════

tests/test_partner_auth.py:
  test_register_as_delivery_partner
  test_partner_jwt_contains_role_and_partner_id
  test_protected_route_requires_kyc_approval
  test_pending_kyc_partner_blocked_from_duty

tests/test_kyc.py:
  test_upload_aadhaar_front_success
  test_upload_invalid_file_type_returns_400
  test_upload_file_too_large_returns_400
  test_kyc_status_shows_missing_documents
  test_all_docs_uploaded_sets_kyc_submitted
  test_admin_approve_kyc_sets_active_status
  test_admin_reject_specific_doc

tests/test_duty.py:
  test_go_online_success
  test_go_online_already_online_returns_409
  test_go_offline_during_active_delivery_returns_409
  test_go_offline_closes_shift_with_summary

tests/test_assignment.py:
  test_auto_assign_finds_nearest_partner
  test_accept_assignment_within_window
  test_accept_assignment_after_timeout_returns_409
  test_reject_decrements_acceptance_rate
  test_deliver_with_correct_otp_completes_order
  test_deliver_with_wrong_otp_returns_401
  test_deliver_with_expired_otp_returns_409

tests/test_earnings.py:
  test_earnings_created_after_delivery
  test_surge_pay_added_during_peak_hours
  test_distance_pay_calculated_correctly
  test_daily_earnings_summary_accurate

tests/test_partner_ws.py:
  test_partner_connects_to_order_ws_with_valid_token
  test_partner_rejected_without_token
  test_location_update_broadcasts_to_customer

═══════════════════════════════════════════════════════
SECTION 22 — ALL API ENDPOINTS SUMMARY
═══════════════════════════════════════════════════════
All under /api/v1/partner/* (auth required, DELIVERY_PARTNER role):

── Auth (extends existing) ─────────────────────
POST /api/v1/auth/verify-otp    ← add register_as_partner field

── KYC ─────────────────────────────────────────
GET  /api/v1/partner/kyc/status
POST /api/v1/partner/kyc/upload
POST /api/v1/partner/kyc/submit

── Profile ─────────────────────────────────────
GET  /api/v1/partner/profile
PATCH /api/v1/partner/profile
GET  /api/v1/partner/profile/stats

── Duty ─────────────────────────────────────────
POST /api/v1/partner/duty/start
POST /api/v1/partner/duty/stop
GET  /api/v1/partner/duty/status

── Assignments ──────────────────────────────────
GET  /api/v1/partner/assignments/active
GET  /api/v1/partner/assignments/history
POST /api/v1/partner/assignments/{id}/accept
POST /api/v1/partner/assignments/{id}/reject
POST /api/v1/partner/assignments/{id}/reached-restaurant
POST /api/v1/partner/assignments/{id}/picked-up
POST /api/v1/partner/assignments/{id}/reached-customer
POST /api/v1/partner/assignments/{id}/deliver
POST /api/v1/partner/assignments/{id}/failed

── Location ─────────────────────────────────────
POST /api/v1/partner/location/update  ← HTTP fallback

── Earnings ─────────────────────────────────────
GET  /api/v1/partner/earnings/today
GET  /api/v1/partner/earnings/weekly
GET  /api/v1/partner/earnings/history
GET  /api/v1/partner/earnings/delivery/{assignment_id}

── Incentives ───────────────────────────────────
GET  /api/v1/partner/incentives/active
GET  /api/v1/partner/incentives/earned

── Payouts ──────────────────────────────────────
GET  /api/v1/partner/payouts
GET  /api/v1/partner/payouts/pending
POST /api/v1/partner/payouts/request

── Referrals ────────────────────────────────────
POST /api/v1/partner/referral/apply
GET  /api/v1/partner/referral/stats

── Support ──────────────────────────────────────
POST /api/v1/partner/support/tickets
GET  /api/v1/partner/support/tickets
GET  /api/v1/partner/support/tickets/{id}

── WebSockets ───────────────────────────────────
WS   /api/v1/ws/partner/orders?token={jwt}
WS   /api/v1/ws/partner/location?token={jwt}

── Admin ────────────────────────────────────────
GET  /api/v1/admin/kyc/pending
POST /api/v1/admin/kyc/{partner_id}/approve
POST /api/v1/admin/kyc/{partner_id}/reject
POST /api/v1/admin/surge/enable
POST /api/v1/admin/surge/disable
GET  /api/v1/admin/surge/status
GET  /api/v1/admin/support/tickets
PATCH /api/v1/admin/support/tickets/{id}

═══════════════════════════════════════════════════════
SECTION 23 — FINAL CHECKS
═══════════════════════════════════════════════════════

Check 1 — migrations:
  alembic upgrade head
  psql -d bitex -c "\dt" | grep -c "table"
  → must show 22+ tables

Check 2 — full test suite:
  pytest tests/ -v --tb=short
  → ALL tests green (existing + new)

Check 3 — endpoint count:
  curl http://localhost:8000/openapi.json | \
    python -m json.tool | grep '"operationId"' | wc -l
  → must show 55+ endpoints

Check 4 — partner full flow simulation:
  Step 1: Register as partner (verify-otp with register_as_partner=true)
  Step 2: Upload all 9 KYC documents (use test images)
  Step 3: Submit KYC
  Step 4: Approve KYC via admin endpoint
  Step 5: Go online (POST duty/start with coordinates)
  Step 6: Customer places order (use existing customer token)
  Step 7: Verify assignment created (GET assignments/active)
  Step 8: Accept assignment
  Step 9: Picked up → reached customer
  Step 10: GET delivery OTP from DB
  Step 11: POST deliver with OTP
  Step 12: Verify order status = DELIVERED in DB
  Step 13: Verify earnings created in partner_earnings table
  Step 14: GET earnings/today → must show this delivery
  Show output of every step.

Check 5 — WebSocket location test:
  Use wscat or Python websockets client:
  Connect to ws://localhost:8000/api/v1/ws/partner/location?token={jwt}
  Send: {"latitude":19.0760,"longitude":72.8777,"speed_kmph":20}
  Verify location updated in delivery_partners table.

Show all 5 check outputs. Do not say done until all shown.