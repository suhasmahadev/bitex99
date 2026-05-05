You are a senior backend engineer. Read SPEC.md (user side — COMPLETE)
and SPEC2.md (delivery partner side — COMPLETE) fully before writing
a single line. SPEC3.md extends the SAME monolithic FastAPI app,
SAME PostgreSQL database (bitex), SAME JWT system.
Do NOT break any existing functionality.

Role to add: role="RESTAURANT_PARTNER" in existing users table.

════════════════════════════════════════════════════════
SECTION 1 — SCOPE
════════════════════════════════════════════════════════
BUILD ONLY the restaurant partner side:

  • Restaurant registration + document verification
  • Restaurant profile management (info, images, timings)
  • Menu management (categories, items, pricing, availability)
  • Live order management (accept, reject, prepare, ready)
  • Order history and search
  • Business analytics dashboard
  • Payout and commission tracking
  • Offer and discount management
  • Reviews management (read + respond)
  • Open/Close toggle (online availability)
  • WebSocket for real-time incoming orders
  • Customer-side rendering connection (restaurants 
    and menus already served from existing tables)
  • Seed data — 8 fully seeded fake restaurants

DO NOT BUILD:
  • Customer panel (SPEC.md — COMPLETE)
  • Delivery partner panel (SPEC2.md — COMPLETE)

CONNECTION TO CUSTOMER SIDE:
  The customer-side already reads from these tables:
    restaurants, menu_categories, menu_items
  Restaurant partner manages THESE SAME TABLES.
  No duplication. Same data, different role manages it.
  When restaurant partner updates menu_items.is_available
  → customer immediately sees it in /restaurants/{id}/menu
  When restaurant partner sets is_open=false
  → customer sees restaurant as CLOSED in listing

════════════════════════════════════════════════════════
SECTION 2 — FOLDER STRUCTURE ADDITIONS
════════════════════════════════════════════════════════
Add to existing app/ structure:

app/
├── models/
│   ├── restaurant_partner.py    ← partner profile + docs
│   ├── restaurant_document.py   ← FSSAI, GST, PAN etc
│   ├── restaurant_timing.py     ← operating hours per day
│   ├── restaurant_payout.py     ← weekly settlement
│   ├── restaurant_offer.py      ← discounts and promos
│   └── order_response.py        ← restaurant's accept/reject log
│
├── schemas/
│   ├── restaurant_partner.py
│   ├── restaurant_document.py
│   ├── restaurant_management.py ← profile, timing, toggle
│   ├── menu_management.py       ← CRUD for categories + items
│   ├── order_management.py      ← incoming order handling
│   ├── restaurant_analytics.py
│   ├── restaurant_payout.py
│   └── restaurant_offer.py
│
├── services/
│   ├── restaurant_partner_service.py
│   ├── restaurant_document_service.py
│   ├── menu_management_service.py
│   ├── order_management_service.py  ← accept/reject/prepare
│   ├── restaurant_analytics_service.py
│   ├── restaurant_payout_service.py
│   └── restaurant_offer_service.py
│
└── routers/
    └── restaurant/
        ├── auth.py           → /api/v1/restaurant/auth
        ├── profile.py        → /api/v1/restaurant/profile
        ├── documents.py      → /api/v1/restaurant/documents
        ├── menu.py           → /api/v1/restaurant/menu
        ├── orders.py         → /api/v1/restaurant/orders
        ├── analytics.py      → /api/v1/restaurant/analytics
        ├── payouts.py        → /api/v1/restaurant/payouts
        ├── offers.py         → /api/v1/restaurant/offers
        └── reviews.py        → /api/v1/restaurant/reviews

════════════════════════════════════════════════════════
SECTION 3 — DATABASE SCHEMA (COMPLETE)
════════════════════════════════════════════════════════

── users table (ALTER existing) ──────────────────────
  role already has 'RESTAURANT_PARTNER' in CHECK constraint
  ADD COLUMN restaurant_status VARCHAR(20) DEFAULT NULL
    Values: NULL (not a restaurant partner)
            'PENDING_DOCS' | 'DOCS_SUBMITTED' | 
            'DOCS_APPROVED' | 'DOCS_REJECTED' | 
            'SUSPENDED' | 'ACTIVE'

── restaurant_partners ───────────────────────────────
  id                  UUID PRIMARY KEY
  user_id             UUID FK → users.id UNIQUE ON DELETE CASCADE
  restaurant_id       UUID FK → restaurants.id UNIQUE
                      ← links partner account to existing restaurant
  owner_name          VARCHAR(200) NOT NULL
  business_type       ENUM('RESTAURANT','CLOUD_KITCHEN',
                           'BAKERY','CAFE','FOOD_TRUCK')
  commission_rate     NUMERIC(5,2) DEFAULT 20.0  ← % per order
  wallet_balance      NUMERIC(12,2) DEFAULT 0.00 ← earnings
  total_revenue       NUMERIC(14,2) DEFAULT 0.00
  total_orders        INTEGER DEFAULT 0
  bank_account_number VARCHAR(20)
  bank_ifsc           VARCHAR(15)
  bank_account_name   VARCHAR(200)
  gstin               VARCHAR(20)
  pan_number          VARCHAR(15)
  fssai_number        VARCHAR(20) NOT NULL
  fssai_expiry        DATE
  joined_at           TIMESTAMPTZ DEFAULT now()
  INDEX on (restaurant_id)

── restaurant_documents ──────────────────────────────
  id                  UUID PRIMARY KEY
  partner_id          UUID FK → restaurant_partners.id
  doc_type            ENUM(
                        'FSSAI_LICENSE',
                        'GST_CERTIFICATE',
                        'PAN_CARD',
                        'BANK_CANCELLED_CHEQUE',
                        'OWNER_AADHAAR_FRONT',
                        'OWNER_AADHAAR_BACK',
                        'SHOP_ACT_LICENSE',
                        'PARTNERSHIP_DEED',    ← if partnership
                        'MENU_PHOTO',
                        'RESTAURANT_PHOTO_FRONT',
                        'RESTAURANT_PHOTO_INTERIOR'
                      )
  file_url            VARCHAR(500) NOT NULL
  file_name           VARCHAR(200)
  status              ENUM('PENDING','APPROVED','REJECTED')
                      DEFAULT 'PENDING'
  rejection_reason    VARCHAR(500)
  verified_at         TIMESTAMPTZ
  uploaded_at         TIMESTAMPTZ DEFAULT now()
  UNIQUE on (partner_id, doc_type)
  INDEX on (partner_id)

── restaurant_timings ────────────────────────────────
  id                  UUID PRIMARY KEY
  restaurant_id       UUID FK → restaurants.id
  day_of_week         INTEGER NOT NULL  ← 0=Monday, 6=Sunday
  opens_at            TIME NOT NULL     ← e.g. "10:00"
  closes_at           TIME NOT NULL     ← e.g. "23:00"
  is_closed           BOOLEAN DEFAULT FALSE ← holiday/day off
  UNIQUE on (restaurant_id, day_of_week)

── restaurant_payouts ────────────────────────────────
  id                  UUID PRIMARY KEY
  partner_id          UUID FK → restaurant_partners.id
  period_start        DATE NOT NULL
  period_end          DATE NOT NULL
  gross_revenue       NUMERIC(12,2) NOT NULL
  commission_deducted NUMERIC(10,2) NOT NULL
  net_payout          NUMERIC(12,2) NOT NULL
  order_count         INTEGER NOT NULL
  status              ENUM('PENDING','PROCESSING','PAID','FAILED')
                      DEFAULT 'PENDING'
  bank_account        VARCHAR(20)
  utr_number          VARCHAR(50)
  initiated_at        TIMESTAMPTZ DEFAULT now()
  paid_at             TIMESTAMPTZ
  INDEX on (partner_id, status)

── restaurant_offers ─────────────────────────────────
  id                  UUID PRIMARY KEY
  restaurant_id       UUID FK → restaurants.id
  title               VARCHAR(200) NOT NULL  ← "40% OFF up to ₹80"
  offer_type          ENUM('FLAT','PERCENT','FREE_DELIVERY',
                           'BOGO')           ← Buy one get one
  discount_value      NUMERIC(8,2) NOT NULL
  max_discount        NUMERIC(8,2)
  min_order_amount    NUMERIC(10,2) DEFAULT 0
  valid_from          TIMESTAMPTZ
  valid_until         TIMESTAMPTZ
  is_active           BOOLEAN DEFAULT TRUE
  usage_count         INTEGER DEFAULT 0
  INDEX on (restaurant_id, is_active)

── order_responses ───────────────────────────────────
  id                  UUID PRIMARY KEY
  order_id            UUID FK → orders.id UNIQUE
  restaurant_id       UUID FK → restaurants.id
  action              ENUM('ACCEPTED','REJECTED')
  preparation_time    INTEGER              ← minutes estimated
  rejection_reason    VARCHAR(300)
  responded_at        TIMESTAMPTZ DEFAULT now()

── ALTER orders table ────────────────────────────────
  ADD COLUMN preparation_time INTEGER      ← set by restaurant
  ADD COLUMN restaurant_confirmed_at TIMESTAMPTZ
  ADD COLUMN ready_at TIMESTAMPTZ          ← food is ready

════════════════════════════════════════════════════════
SECTION 4 — AUTH FLOW (RESTAURANT PARTNER)
════════════════════════════════════════════════════════
Uses SAME OTP auth endpoints.

Extend POST /api/v1/auth/verify-otp:
  Add optional field: register_as_restaurant: bool = False
  
  If register_as_restaurant=True:
    Set user.role = 'RESTAURANT_PARTNER'
    Set user.restaurant_status = 'PENDING_DOCS'
    DO NOT create restaurant record yet
    (restaurant created during profile setup)
    Return: is_new_restaurant_partner: true

JWT for restaurant partners:
  { sub, phone, role: "RESTAURANT_PARTNER",
    restaurant_partner_id, restaurant_id, jti, exp }

Dependencies to create in app/dependencies.py:
  require_restaurant_partner():
    Check role == 'RESTAURANT_PARTNER'
    Check restaurant_status == 'DOCS_APPROVED'
    Return restaurant_partner object

  require_restaurant_jwt():
    Check role == 'RESTAURANT_PARTNER' only
    (for document upload routes before approval)

════════════════════════════════════════════════════════
SECTION 5 — RESTAURANT REGISTRATION FLOW
════════════════════════════════════════════════════════
Exactly like Zomato's restaurant onboarding.

Step 1 — Basic Info (creates restaurant + partner record):
  POST /api/v1/restaurant/profile/setup
  Auth: require_restaurant_jwt()
  Body:
  {
    "restaurant_name": "Burger Palace",
    "business_type": "RESTAURANT",
    "cuisine_types": ["Burgers","American"],
    "city": "Mumbai",
    "full_address": "123 MG Road, Bandra West",
    "latitude": 19.0596,
    "longitude": 72.8295,
    "phone": "+912212345678",
    "owner_name": "Rahul Sharma",
    "fssai_number": "12345678901234",
    "fssai_expiry": "2026-12-31",
    "gstin": "27ABCDE1234F1Z5",
    "pan_number": "ABCDE1234F",
    "bank_account_number": "1234567890",
    "bank_ifsc": "HDFC0001234",
    "bank_account_name": "Rahul Sharma"
  }
  
  Logic:
    1. Check partner has no existing restaurant
    2. Generate slug from restaurant_name
       slug = restaurant_name.lower().replace(' ', '-')
       + random 4 digits if slug exists
    3. INSERT restaurants record (is_open=FALSE initially)
    4. INSERT restaurant_partners record
    5. INSERT restaurant_timings for all 7 days
       (default: 10:00-23:00, no days closed)
    6. Link partner.restaurant_id = new restaurant.id
    7. Return: { restaurant_id, partner_id, 
                 next_step: "Upload documents" }

Step 2 — Document Upload:
  POST /api/v1/restaurant/documents/upload
  Auth: require_restaurant_jwt()
  Body: multipart/form-data { doc_type, file }
  
  REQUIRED documents (must all be uploaded before approval):
    FSSAI_LICENSE
    PAN_CARD
    BANK_CANCELLED_CHEQUE
    OWNER_AADHAAR_FRONT
    OWNER_AADHAAR_BACK
    RESTAURANT_PHOTO_FRONT
  
  OPTIONAL:
    GST_CERTIFICATE (required if turnover > 20L)
    SHOP_ACT_LICENSE
    MENU_PHOTO
    RESTAURANT_PHOTO_INTERIOR
    PARTNERSHIP_DEED
  
  Logic: same as KYC upload in SPEC2.md
    Validate file type + size (max 10MB for photos)
    Save to uploads/restaurant/{partner_id}/{doc_type}_{ts}.ext
    UPSERT document record
    Check if all required docs uploaded
    If yes → set user.restaurant_status = 'DOCS_SUBMITTED'

  GET /api/v1/restaurant/documents/status
    Returns all doc types with upload status + missing required

  POST /api/v1/restaurant/documents/submit
    Validates all required docs present
    Logs notification to admin

Step 3 — Admin Approves:
  POST /api/v1/admin/restaurant/{partner_id}/approve
    Set all docs status = APPROVED
    Set user.restaurant_status = 'DOCS_APPROVED'
    Set restaurants.is_open = TRUE (restaurant goes live)
    
  POST /api/v1/admin/restaurant/{partner_id}/reject
    Body: { doc_type, reason }
    Set specific doc = REJECTED with reason
    Set user.restaurant_status = 'DOCS_REJECTED'

════════════════════════════════════════════════════════
SECTION 6 — RESTAURANT PROFILE MANAGEMENT
════════════════════════════════════════════════════════

GET /api/v1/restaurant/profile
  Returns full restaurant profile + partner details + timings

PATCH /api/v1/restaurant/profile
  Auth: require_restaurant_partner()
  Can update:
    name, description, cuisine_types, phone,
    image_url, cover_image_url,
    min_order_amount, avg_delivery_time
  Cannot update: city, full_address (requires admin)
  Cannot update: is_open via this endpoint (use toggle)

POST /api/v1/restaurant/profile/open-toggle
  Auth: require_restaurant_partner()
  Body: { is_open: bool }
  Logic:
    UPDATE restaurants SET is_open = is_open
    If closing: check no active orders in 
      status PLACED/CONFIRMED/PREPARING
      If active orders exist → return 409:
      { "error_code": "ACTIVE_ORDERS_EXIST",
        "active_order_count": 3,
        "message": "Cannot close while orders are being processed" }
  Returns: { is_open: bool, message }

PATCH /api/v1/restaurant/profile/timings
  Auth: require_restaurant_partner()
  Body: array of timing objects:
  [
    { "day_of_week": 0, "opens_at": "10:00",
      "closes_at": "23:00", "is_closed": false },
    { "day_of_week": 6, "opens_at": "11:00",
      "closes_at": "22:00", "is_closed": false }
  ]
  UPSERT all provided timings.
  Returns updated full weekly schedule.

GET /api/v1/restaurant/profile/timings
  Returns weekly schedule with today highlighted.

════════════════════════════════════════════════════════
SECTION 7 — MENU MANAGEMENT
════════════════════════════════════════════════════════
Restaurant partner manages THE SAME tables customers read.
No separate menu tables. Direct CRUD on menu_categories
and menu_items with restaurant_id ownership check.

── Category Management ───────────────────────────────

GET /api/v1/restaurant/menu/categories
  Returns all categories for this restaurant
  Ordered by display_order.

POST /api/v1/restaurant/menu/categories
  Body: { name, display_order }
  INSERT menu_categories with restaurant_id = partner's restaurant
  Returns new category.

PATCH /api/v1/restaurant/menu/categories/{id}
  Body: { name, display_order, is_active }
  Verify category.restaurant_id == partner's restaurant
  UPDATE category.

DELETE /api/v1/restaurant/menu/categories/{id}
  Verify ownership.
  Check no menu_items in this category → else 409:
  { "error_code": "CATEGORY_HAS_ITEMS",
    "item_count": 5,
    "message": "Move or delete items before deleting category" }
  DELETE category.

── Item Management ───────────────────────────────────

GET /api/v1/restaurant/menu/items
  Query: category_id, is_available, search
  Returns all items for this restaurant.

POST /api/v1/restaurant/menu/items
  Auth: require_restaurant_partner()
  Body:
  {
    "category_id": "uuid",
    "name": "Classic Burger",
    "description": "Juicy beef patty with lettuce",
    "price": 199.00,
    "discounted_price": 149.00,   ← null = no discount
    "is_veg": false,
    "is_available": true,
    "preparation_time": 15,
    "tags": ["Bestseller","Spicy"],
    "image_url": "..."
  }
  Validate category belongs to this restaurant.
  INSERT menu_item.

PATCH /api/v1/restaurant/menu/items/{id}
  Same body fields, all optional.
  Verify item.restaurant_id == partner's restaurant.
  UPDATE only provided fields.

DELETE /api/v1/restaurant/menu/items/{id}
  Verify ownership.
  Soft delete: SET is_available=FALSE, add "_deleted" tag.
  Do not hard delete (order_items snapshot references it).

PATCH /api/v1/restaurant/menu/items/{id}/toggle
  Body: { is_available: bool }
  Quick toggle for marking items out of stock.
  This is the most used endpoint in real Zomato partner app.
  Returns: { id, name, is_available }

POST /api/v1/restaurant/menu/items/{id}/image
  Multipart: { file: UploadFile }
  Save to uploads/menu/{restaurant_id}/{item_id}.jpg
  UPDATE menu_items.image_url
  Returns updated item.

POST /api/v1/restaurant/menu/bulk-toggle
  Body: { item_ids: [uuid], is_available: bool }
  Toggle multiple items at once.
  Returns count of updated items.

════════════════════════════════════════════════════════
SECTION 8 — LIVE ORDER MANAGEMENT (MOST CRITICAL)
════════════════════════════════════════════════════════
This is the heart of the restaurant partner app.
Orders come in → restaurant accepts/rejects → prepares → ready.

WebSocket: /api/v1/ws/restaurant/orders?token={jwt}
  On connect:
    Validate JWT → must be RESTAURANT_PARTNER + DOCS_APPROVED
    Store in ConnectionManager keyed by restaurant_id
    Send all pending orders (status=PLACED) immediately:
    { "event": "PENDING_ORDERS", "orders": [...] }
  
  When new order arrives (customer places order):
    Push to restaurant's WS channel:
    {
      "event": "NEW_ORDER",
      "order": {
        "order_id": "...",
        "order_number": "#1042",  ← sequential short number
        "items": [
          { "name": "Classic Burger", "quantity": 2,
            "is_veg": false, "special_instructions": null }
        ],
        "total_amount": 670.00,
        "payment_method": "UPI",
        "payment_status": "SUCCESS",
        "customer_name": "Rahul",
        "delivery_address": "123 MG Road, Bandra",
        "created_at": "..."
      },
      "expires_in_seconds": 90  ← auto-reject after 90s
    }
  
  If restaurant does NOT respond in 90 seconds:
    Auto-reject order.
    Set order status = CANCELLED
    Set cancellation_reason = "Restaurant did not respond"
    Notify customer WebSocket.
    Log: "Order {id} auto-rejected by restaurant timeout"

HTTP fallback (polling) for restaurants without WS:
  GET /api/v1/restaurant/orders/pending
    Returns all orders with status=PLACED for this restaurant.

── Order Lifecycle Endpoints ─────────────────────────

POST /api/v1/restaurant/orders/{id}/accept
  Auth: require_restaurant_partner()
  Body: { preparation_time: int }  ← minutes e.g. 20
  Logic:
    1. Verify order.restaurant_id == partner's restaurant
    2. Verify order.status == 'PLACED'
    3. INSERT order_responses: action=ACCEPTED, prep_time
    4. UPDATE order:
       status = 'CONFIRMED'
       preparation_time = body.preparation_time
       restaurant_confirmed_at = now()
       estimated_delivery_at = now() + prep_time + 15min
    5. Broadcast to customer WS:
       { "event": "ORDER_CONFIRMED",
         "preparation_time": 20,
         "message": "Restaurant accepted your order!
                     Estimated delivery in 35 minutes" }
    6. Trigger auto_assign_partner() for delivery
    7. Return: { status: "CONFIRMED", preparation_time: 20 }

POST /api/v1/restaurant/orders/{id}/reject
  Auth: require_restaurant_partner()
  Body: { reason: ENUM('OUT_OF_STOCK','RESTAURANT_CLOSING',
                        'HIGH_DEMAND','OTHER'),
          description: str (optional) }
  Logic:
    1. Verify ownership + status == 'PLACED'
    2. INSERT order_responses: action=REJECTED
    3. UPDATE order status = 'CANCELLED'
    4. UPDATE order.cancellation_reason = reason
    5. Broadcast to customer WS:
       { "event": "ORDER_CANCELLED",
         "reason": "Restaurant is currently unable to fulfil order",
         "refund_message": "Refund initiated if payment made" }
    6. Return: { status: "CANCELLED" }

POST /api/v1/restaurant/orders/{id}/preparing
  Logic:
    1. Verify status == 'CONFIRMED'
    2. UPDATE order status = 'PREPARING'
    3. Broadcast to customer WS:
       { "event": "ORDER_PREPARING",
         "message": "Chef is preparing your food 👨‍🍳" }

POST /api/v1/restaurant/orders/{id}/ready
  Logic:
    1. Verify status == 'PREPARING'
    2. UPDATE order:
       status = 'READY_FOR_PICKUP'
       ready_at = now()
    3. Broadcast to customer WS:
       { "event": "ORDER_READY",
         "message": "Food is ready! Delivery partner will pick up soon." }
    4. Notify assigned delivery partner via WS:
       { "event": "ORDER_READY_FOR_PICKUP",
         "order_id": "...",
         "message": "Food is ready at restaurant" }

GET /api/v1/restaurant/orders
  Query: status, page, limit, date_from, date_to, search
  Returns paginated orders for this restaurant.
  Default: today's orders, newest first.
  Each order shows: order_number, items summary, 
  total, status, payment_method, customer_name, time.

GET /api/v1/restaurant/orders/{id}
  Full order detail with items, customer info,
  delivery partner info (if assigned), timeline.

GET /api/v1/restaurant/orders/live
  Returns ALL currently active orders:
  PLACED, CONFIRMED, PREPARING, READY_FOR_PICKUP
  Grouped by status.
  This is the main dashboard view.

════════════════════════════════════════════════════════
SECTION 9 — ANALYTICS DASHBOARD
════════════════════════════════════════════════════════
Exactly like Zomato's business reporting.

GET /api/v1/restaurant/analytics/overview
  Auth: require_restaurant_partner()
  Returns:
  {
    "today": {
      "orders": 23,
      "revenue": 12450.00,
      "avg_order_value": 541.30,
      "cancelled": 2,
      "cancellation_rate": 8.7
    },
    "this_week": {
      "orders": 145,
      "revenue": 78500.00,
      "best_day": "Saturday",
      "best_day_revenue": 18200.00
    },
    "this_month": {
      "orders": 543,
      "revenue": 298000.00,
      "growth_vs_last_month": 12.5  ← %
    },
    "all_time": {
      "total_orders": 2341,
      "total_revenue": 1250000.00,
      "avg_rating": 4.3,
      "total_reviews": 456
    }
  }

GET /api/v1/restaurant/analytics/revenue-chart
  Query: period=ENUM('7days','30days','3months','year')
  Returns daily/weekly revenue array for chart:
  {
    "labels": ["Apr 21","Apr 22","Apr 23",...],
    "revenue": [12450, 9800, 15600, ...],
    "orders": [23, 18, 29, ...]
  }

GET /api/v1/restaurant/analytics/top-items
  Query: period, limit (default 10)
  Returns best-selling menu items:
  {
    "items": [
      {
        "menu_item_id": "...",
        "name": "Classic Burger",
        "orders_count": 234,
        "revenue": 46600.00,
        "rank": 1
      }
    ]
  }

GET /api/v1/restaurant/analytics/peak-hours
  Returns hourly order distribution:
  {
    "hours": [
      { "hour": "12:00", "avg_orders": 8.5 },
      { "hour": "13:00", "avg_orders": 12.3 },
      { "hour": "19:00", "avg_orders": 15.1 },
      ...
    ]
  }

GET /api/v1/restaurant/analytics/ratings-summary
  Returns:
  {
    "overall_rating": 4.3,
    "total_reviews": 456,
    "breakdown": {
      "5_star": 280, "4_star": 120,
      "3_star": 40,  "2_star": 10, "1_star": 6
    },
    "recent_reviews": [ ...last 5 reviews with comments... ]
  }

════════════════════════════════════════════════════════
SECTION 10 — PAYOUT AND COMMISSION
════════════════════════════════════════════════════════
Commission rate: 20% default (stored per restaurant partner).

Commission calculation per order:
  gross_amount = order.total_amount
  commission = gross_amount * (partner.commission_rate / 100)
  net_to_restaurant = gross_amount - commission

On order DELIVERED:
  UPDATE restaurant_partners.wallet_balance += net_to_restaurant
  UPDATE restaurant_partners.total_revenue += gross_amount
  UPDATE restaurant_partners.total_orders += 1

GET /api/v1/restaurant/payouts
  Returns payout history (paginated).

GET /api/v1/restaurant/payouts/pending
  Returns:
  {
    "pending_amount": 45600.00,
    "pending_orders": 89,
    "commission_deducted": 9120.00,
    "net_payout": 36480.00,
    "next_payout_date": "2026-05-05",  ← next Monday
    "breakdown_by_day": [
      { "date": "2026-04-27", "orders": 23,
        "gross": 12450.00, "commission": 2490.00,
        "net": 9960.00 }
    ]
  }

POST /api/v1/restaurant/payouts/request
  Simulate weekly payout:
  Creates restaurant_payout record.
  Deducts from wallet_balance.
  Returns UTR number.

════════════════════════════════════════════════════════
SECTION 11 — OFFER MANAGEMENT
════════════════════════════════════════════════════════
Restaurant creates offers → shown to customers on listing.

GET /api/v1/restaurant/offers
  Returns all offers for this restaurant.

POST /api/v1/restaurant/offers
  Auth: require_restaurant_partner()
  Body:
  {
    "title": "40% OFF up to ₹80",
    "offer_type": "PERCENT",
    "discount_value": 40,
    "max_discount": 80,
    "min_order_amount": 199,
    "valid_from": "2026-04-27T00:00:00Z",
    "valid_until": "2026-05-31T23:59:59Z"
  }
  INSERT restaurant_offers.
  UPDATE restaurants.has_offers = TRUE.
  Offer immediately visible to customers on restaurant card.

PATCH /api/v1/restaurant/offers/{id}
  Update offer details.

PATCH /api/v1/restaurant/offers/{id}/toggle
  Body: { is_active: bool }
  If no active offers remain → UPDATE restaurants.has_offers=FALSE

DELETE /api/v1/restaurant/offers/{id}
  Soft delete: is_active=FALSE.

════════════════════════════════════════════════════════
SECTION 12 — REVIEW MANAGEMENT
════════════════════════════════════════════════════════
Restaurants can READ customer reviews (already in DB).
Future: respond to reviews (stored as text field).

GET /api/v1/restaurant/reviews
  Query: rating (filter), page, limit
  Returns paginated reviews for this restaurant.
  Sorted: newest first.
  Each review: food_rating, delivery_rating, comment,
               customer_name (first name only), date.

GET /api/v1/restaurant/reviews/stats
  Returns rating breakdown + avg response time stats.

POST /api/v1/restaurant/reviews/{id}/respond
  Body: { response: str (max 500 chars) }
  Save response_text on review record.
  (Add response_text VARCHAR(500) to reviews table via migration)

════════════════════════════════════════════════════════
SECTION 13 — WEBSOCKET ARCHITECTURE
════════════════════════════════════════════════════════
Add to existing ConnectionManager in app.state:

  restaurant_connections: Dict[str, WebSocket]
    key = restaurant_id
  
  Methods to add:
    connect_restaurant(restaurant_id, ws)
    disconnect_restaurant(restaurant_id)
    send_to_restaurant(restaurant_id, message)
    is_restaurant_connected(restaurant_id) → bool

Trigger from order_service.place_order():
  After order INSERT:
    await notify_restaurant_new_order(order.restaurant_id, order)
  
  In notification_service.py:
    If restaurant WS connected → push NEW_ORDER event
    If not connected → store in Redis:
      LPUSH "restaurant:pending:{restaurant_id}" order_json
      EXPIRE key 3600
    When restaurant connects → drain Redis queue and push all.

════════════════════════════════════════════════════════
SECTION 14 — SEEDING (seed_restaurant.py)
════════════════════════════════════════════════════════
Create seed_restaurant.py (idempotent, run separately).

Seed exactly 8 restaurants with FULL data:

Restaurant 1 — "Burger Barn" (Mumbai, Bandra)
  cuisine: Burgers, American
  rating: 4.2, is_open: true, is_pure_veg: false
  delivery_fee: 30, min_order: 199, avg_delivery: 35
  Categories: Burgers (4 items), Sides (3 items), Drinks (3 items)
  Sample items:
    Classic Smash Burger ₹299 (discounted ₹249), non-veg, Bestseller
    Double Patty ₹399, non-veg
    Veggie Burger ₹219, veg
    Chicken Wings ₹249, non-veg
    Fries ₹99, veg
    Coke ₹60, veg

Restaurant 2 — "Dosa Darbar" (Mumbai, Andheri)
  cuisine: South Indian, Dosa
  rating: 4.5, is_open: true, is_pure_veg: true
  delivery_fee: 25, min_order: 150, avg_delivery: 25
  Categories: Dosas (5 items), Idli (3 items), Beverages (2 items)

Restaurant 3 — "Biryani Blues" (Delhi, Connaught Place)
  cuisine: Biryani, Mughlai
  rating: 4.6, is_open: true, is_pure_veg: false
  delivery_fee: 40, min_order: 299, avg_delivery: 45
  Categories: Biryani (4 items), Kebabs (3 items), Raita (2 items)

Restaurant 4 — "Pizza House" (Delhi, Hauz Khas)
  cuisine: Pizza, Italian
  rating: 4.1, is_open: true, is_pure_veg: false
  delivery_fee: 35, min_order: 249, avg_delivery: 40
  Categories: Pizzas (5 items), Pasta (3 items), Garlic Bread (2 items)

Restaurant 5 — "Green Bowl" (Bangalore, Koramangala)
  cuisine: Healthy, Salads
  rating: 4.4, is_open: true, is_pure_veg: true
  delivery_fee: 30, min_order: 199, avg_delivery: 30
  Categories: Bowls (4 items), Salads (3 items), Smoothies (3 items)

Restaurant 6 — "Wok Express" (Bangalore, Indiranagar)
  cuisine: Chinese, Asian
  rating: 3.9, is_open: true, is_pure_veg: false
  delivery_fee: 30, min_order: 179, avg_delivery: 35
  Categories: Noodles (4 items), Rice (3 items), Starters (3 items)

Restaurant 7 — "Tandoor Times" (Mumbai, Powai)
  cuisine: North Indian, Punjabi
  rating: 4.3, is_open: false, is_pure_veg: false
  delivery_fee: 45, min_order: 299, avg_delivery: 50
  is_open: FALSE ← shows as CLOSED to customers
  Categories: Dal (2), Paneer (3), Chicken (3), Breads (3)

Restaurant 8 — "Sweet Tooth" (Bangalore, HSR Layout)
  cuisine: Desserts, Bakery
  rating: 4.7, is_open: true, is_pure_veg: true
  delivery_fee: 20, min_order: 99, avg_delivery: 20
  Categories: Cakes (4 items), Ice Cream (4 items), Pastries (3 items)

For each restaurant also seed:
  - 7 days of restaurant_timings (10:00-23:00)
  - 1 active offer per restaurant
  - 1 restaurant_partner record (linked to a test partner user)
  - restaurant_status: 'DOCS_APPROVED'
  - All documents marked APPROVED

Create 1 test restaurant partner user:
  phone: +919000000001
  role: RESTAURANT_PARTNER
  restaurant_status: DOCS_APPROVED
  Linked to Restaurant 1 (Burger Barn)

Total seed data:
  8 restaurants, 8 partners, ~85 menu items,
  8 offers, 56 timing records

════════════════════════════════════════════════════════
SECTION 15 — CONNECTION TO CUSTOMER SIDE
════════════════════════════════════════════════════════
These connections already work because we use SAME tables.
Verify each one after building:

1. Restaurant listing (customer side):
   GET /api/v1/restaurants?city=Mumbai
   → must show all 8 seeded restaurants
   → Tandoor Times must show is_open: false
   → Burger Barn must show has_offers: true

2. Menu browsing (customer side):
   GET /api/v1/restaurants/{burger_barn_id}/menu
   → must show categories and items
   → After partner toggles item unavailable:
     GET menu again → item shows is_available: false

3. Order flow (customer → restaurant):
   Customer places order
   → Restaurant partner sees it in WS NEW_ORDER event
   → Restaurant accepts → order status CONFIRMED
   → Customer WS receives ORDER_CONFIRMED event

4. Restaurant open/close toggle:
   Partner: POST /api/v1/restaurant/profile/open-toggle
     { is_open: false }
   Customer: GET /api/v1/restaurants?city=Mumbai
     → Burger Barn shows is_open: false (CLOSED badge)

5. Rating from customer review:
   Customer: POST /api/v1/reviews { order_id, food_rating: 5 }
   → restaurants.rating auto-updated
   Partner: GET /api/v1/restaurant/analytics/overview
     → rating reflects new review

════════════════════════════════════════════════════════
SECTION 16 — ALEMBIC MIGRATIONS
════════════════════════════════════════════════════════
Create in this order:

  alembic revision -m "add_restaurant_status_to_users"
  alembic revision -m "create_restaurant_partners"
  alembic revision -m "create_restaurant_documents"
  alembic revision -m "create_restaurant_timings"
  alembic revision -m "create_restaurant_payouts"
  alembic revision -m "create_restaurant_offers"
  alembic revision -m "create_order_responses"
  alembic revision -m "add_preparation_fields_to_orders"
  alembic revision -m "add_response_text_to_reviews"

Run: alembic upgrade head
Show: psql -d bitex -c "\dt" → must show 31+ tables

════════════════════════════════════════════════════════
SECTION 17 — ALL API ENDPOINTS
════════════════════════════════════════════════════════
All under /api/v1/restaurant/* (auth required):

── Auth ─────────────────────────────────────────────
POST /api/v1/auth/verify-otp ← extend with register_as_restaurant

── Registration ─────────────────────────────────────
POST /api/v1/restaurant/profile/setup
GET  /api/v1/restaurant/documents/status
POST /api/v1/restaurant/documents/upload
POST /api/v1/restaurant/documents/submit

── Profile ──────────────────────────────────────────
GET  /api/v1/restaurant/profile
PATCH /api/v1/restaurant/profile
POST /api/v1/restaurant/profile/open-toggle
GET  /api/v1/restaurant/profile/timings
PATCH /api/v1/restaurant/profile/timings

── Menu ─────────────────────────────────────────────
GET  /api/v1/restaurant/menu/categories
POST /api/v1/restaurant/menu/categories
PATCH /api/v1/restaurant/menu/categories/{id}
DELETE /api/v1/restaurant/menu/categories/{id}
GET  /api/v1/restaurant/menu/items
POST /api/v1/restaurant/menu/items
PATCH /api/v1/restaurant/menu/items/{id}
DELETE /api/v1/restaurant/menu/items/{id}
PATCH /api/v1/restaurant/menu/items/{id}/toggle
POST /api/v1/restaurant/menu/items/{id}/image
POST /api/v1/restaurant/menu/bulk-toggle

── Orders ───────────────────────────────────────────
GET  /api/v1/restaurant/orders
GET  /api/v1/restaurant/orders/live
GET  /api/v1/restaurant/orders/pending
GET  /api/v1/restaurant/orders/{id}
POST /api/v1/restaurant/orders/{id}/accept
POST /api/v1/restaurant/orders/{id}/reject
POST /api/v1/restaurant/orders/{id}/preparing
POST /api/v1/restaurant/orders/{id}/ready

── Analytics ────────────────────────────────────────
GET  /api/v1/restaurant/analytics/overview
GET  /api/v1/restaurant/analytics/revenue-chart
GET  /api/v1/restaurant/analytics/top-items
GET  /api/v1/restaurant/analytics/peak-hours
GET  /api/v1/restaurant/analytics/ratings-summary

── Payouts ──────────────────────────────────────────
GET  /api/v1/restaurant/payouts
GET  /api/v1/restaurant/payouts/pending
POST /api/v1/restaurant/payouts/request

── Offers ───────────────────────────────────────────
GET  /api/v1/restaurant/offers
POST /api/v1/restaurant/offers
PATCH /api/v1/restaurant/offers/{id}
PATCH /api/v1/restaurant/offers/{id}/toggle
DELETE /api/v1/restaurant/offers/{id}

── Reviews ──────────────────────────────────────────
GET  /api/v1/restaurant/reviews
GET  /api/v1/restaurant/reviews/stats
POST /api/v1/restaurant/reviews/{id}/respond

── Admin ────────────────────────────────────────────
GET  /api/v1/admin/restaurant/pending
POST /api/v1/admin/restaurant/{partner_id}/approve
POST /api/v1/admin/restaurant/{partner_id}/reject

── WebSocket ────────────────────────────────────────
WS   /api/v1/ws/restaurant/orders?token={jwt}

════════════════════════════════════════════════════════
SECTION 18 — TESTS
════════════════════════════════════════════════════════

tests/test_restaurant_auth.py:
  test_register_as_restaurant_partner
  test_jwt_contains_restaurant_role
  test_protected_route_blocked_before_docs_approved
  test_admin_approve_sets_active_status

tests/test_menu_management.py:
  test_create_category
  test_create_menu_item
  test_toggle_item_unavailable
  test_toggle_reflects_in_customer_menu_endpoint
  test_delete_category_with_items_returns_409
  test_bulk_toggle_items

tests/test_order_management.py:
  test_accept_order_updates_status_to_confirmed
  test_reject_order_updates_status_to_cancelled
  test_auto_reject_after_90s_timeout
  test_mark_ready_triggers_partner_notification
  test_cannot_close_restaurant_with_active_orders

tests/test_restaurant_analytics.py:
  test_overview_returns_correct_today_totals
  test_revenue_chart_returns_correct_period
  test_top_items_sorted_by_order_count

════════════════════════════════════════════════════════
SECTION 19 — FINAL VERIFICATION
════════════════════════════════════════════════════════

Check 1 — migrations:
  alembic upgrade head
  psql -d bitex -c "\dt" | wc -l → must show 31+

Check 2 — seed restaurants:
  python seed_restaurant.py
  psql -d bitex -c "SELECT name, city, is_open, rating
    FROM restaurants ORDER BY created_at"
  → must show all 8 restaurants

Check 3 — customer can browse seeded restaurants:
  curl "http://localhost:8000/api/v1/restaurants?city=Mumbai"
  → must return Burger Barn, Dosa Darbar, Tandoor Times
  → Tandoor Times must show is_open: false

Check 4 — full order flow end to end:
  Step 1: Login as customer → add Burger Barn item to cart
  Step 2: Place order → verify order.status = PLACED in DB
  Step 3: Login as restaurant partner (+919000000001)
  Step 4: GET /restaurant/orders/pending → order appears
  Step 5: POST /restaurant/orders/{id}/accept
          { preparation_time: 20 }
  Step 6: Verify order.status = CONFIRMED in DB
  Step 7: POST /restaurant/orders/{id}/preparing
  Step 8: POST /restaurant/orders/{id}/ready
  Step 9: Verify delivery partner can now pick up
  Show all 9 step outputs.

Check 5 — menu toggle reflects to customer:
  Partner: PATCH /restaurant/menu/items/{id}/toggle
    { is_available: false }
  Customer: GET /restaurants/{id}/menu
    → item must show is_available: false

Check 6 — tests:
  pytest tests/test_restaurant_auth.py -v
  pytest tests/test_menu_management.py -v
  pytest tests/test_order_management.py -v
  → All tests green

Show all 6 check outputs.
Do not say done until all shown.