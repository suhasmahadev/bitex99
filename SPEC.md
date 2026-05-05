You are a senior backend engineer with 10+ years of production Python experience. Build a complete, production-grade FastAPI backend that replicates the CUSTOMER-SIDE (user app) of Zomato exactly. This is not a tutorial project. Every line must be production-quality.

═══════════════════════════════════════
SECTION 1 — ABSOLUTE SCOPE BOUNDARY
═══════════════════════════════════════
BUILD ONLY the customer-facing user side:
  • OTP-based phone authentication with full security hardening
  • User profile and multi-address management
  • Restaurant discovery, search, and filtering
  • Menu browsing with categories
  • Cart management with cross-restaurant conflict handling
  • Order placement with payment method selection
  • Order lifecycle tracking with status transitions
  • Post-delivery review and rating
  • Coupon / promo code validation

DO NOT BUILD:
  • Restaurant admin panel
  • Delivery partner panel
  • Any internal admin dashboard

═══════════════════════════════════════
SECTION 2 — TECHNOLOGY STACK (FIXED)
═══════════════════════════════════════
Language      : Python 3.11+
Framework     : FastAPI (latest)
ORM           : SQLAlchemy 2.0 (async, mapped_column style)
Migrations    : Alembic (auto-generated, with seed)
Database      : PostgreSQL 15 (asyncpg driver)
Cache / OTP   : Redis 7 (aioredis)
Auth          : JWT (access + refresh tokens), python-jose
Validation    : Pydantic v2
Server        : Uvicorn with --workers
Containerise  : Docker + docker-compose
Env           : python-dotenv + pydantic BaseSettings
Testing       : pytest + pytest-asyncio + httpx AsyncClient
Linting       : ruff + black

═══════════════════════════════════════
SECTION 3 — FOLDER STRUCTURE (EXACT)
═══════════════════════════════════════
Produce this exact layout — no deviations:

zomato_user/
├── app/
│   ├── main.py                  # FastAPI app factory, lifespan, middleware
│   ├── config.py                # pydantic BaseSettings, reads from .env
│   ├── database.py              # async engine, session factory, Base
│   ├── redis_client.py          # aioredis pool singleton
│   ├── dependencies.py          # get_db, get_current_user, rate_limit
│   ├── exceptions.py            # custom exception classes + handlers
│   ├── middleware.py            # request-id, CORS, logging middleware
│   │
│   ├── models/                  # SQLAlchemy ORM models only
│   │   ├── user.py
│   │   ├── address.py
│   │   ├── restaurant.py
│   │   ├── menu.py
│   │   ├── cart.py
│   │   ├── order.py
│   │   └── review.py
│   │
│   ├── schemas/                 # Pydantic v2 request + response schemas
│   │   ├── auth.py
│   │   ├── user.py
│   │   ├── address.py
│   │   ├── restaurant.py
│   │   ├── menu.py
│   │   ├── cart.py
│   │   ├── order.py
│   │   └── review.py
│   │
│   ├── services/                # ALL business logic lives here
│   │   ├── auth_service.py
│   │   ├── user_service.py
│   │   ├── address_service.py
│   │   ├── restaurant_service.py
│   │   ├── menu_service.py
│   │   ├── cart_service.py
│   │   ├── order_service.py
│   │   └── review_service.py
│   │
│   ├── routers/                 # Thin routers — only HTTP wiring
│   │   ├── auth.py
│   │   ├── users.py
│   │   ├── addresses.py
│   │   ├── restaurants.py
│   │   ├── menu.py
│   │   ├── cart.py
│   │   ├── orders.py
│   │   └── reviews.py
│   │
│   └── utils/
│       ├── otp.py               # OTP gen, Redis store, verify, rate limit
│       ├── jwt.py               # access + refresh token create/decode
│       ├── pagination.py        # generic cursor + offset pagination
│       └── response.py          # standard ApiResponse wrapper
│
├── alembic/
│   ├── env.py
│   └── versions/               # migrations auto-generated
├── tests/
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_cart.py
│   └── test_orders.py
├── static/
│   └── index.html               # minimal test UI (fetch-based)
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── alembic.ini
└── seed.py                      # inserts 8 restaurants + 40 menu items

═══════════════════════════════════════
SECTION 4 — DATABASE SCHEMA (COMPLETE)
═══════════════════════════════════════
Every column, constraint, and index specified. No omissions.

── users ──────────────────────────────
  id              UUID PRIMARY KEY default gen_random_uuid()
  phone           VARCHAR(15) UNIQUE NOT NULL  -- E.164 format
  name            VARCHAR(100)
  email           VARCHAR(150) UNIQUE
  profile_picture VARCHAR(500)
  is_active       BOOLEAN default TRUE
  is_verified     BOOLEAN default FALSE
  created_at      TIMESTAMPTZ default now()
  updated_at      TIMESTAMPTZ default now() onupdate now()

── addresses ──────────────────────────
  id              UUID PRIMARY KEY
  user_id         UUID FK → users.id ON DELETE CASCADE
  label           ENUM('HOME','WORK','OTHER')
  full_address    TEXT NOT NULL
  landmark        VARCHAR(200)
  latitude        NUMERIC(10,7)
  longitude       NUMERIC(10,7)
  is_default      BOOLEAN default FALSE
  created_at      TIMESTAMPTZ default now()
  INDEX on (user_id)

── restaurants ────────────────────────
  id              UUID PRIMARY KEY
  name            VARCHAR(200) NOT NULL
  slug            VARCHAR(200) UNIQUE NOT NULL    -- URL-friendly
  description     TEXT
  cuisine_types   VARCHAR[]                       -- ['Indian','Chinese']
  city            VARCHAR(100) NOT NULL
  full_address    TEXT NOT NULL
  latitude        NUMERIC(10,7)
  longitude       NUMERIC(10,7)
  phone           VARCHAR(15)
  image_url       VARCHAR(500)
  cover_image_url VARCHAR(500)
  rating          NUMERIC(3,2) default 0.0       -- 0.00–5.00
  total_reviews   INTEGER default 0
  avg_delivery_time INTEGER                       -- minutes
  min_order_amount NUMERIC(10,2) default 0
  delivery_fee    NUMERIC(10,2) default 0
  is_open         BOOLEAN default TRUE
  is_pure_veg     BOOLEAN default FALSE
  has_offers      BOOLEAN default FALSE
  created_at      TIMESTAMPTZ default now()
  INDEX on (city), INDEX on (rating DESC), GIN index on (cuisine_types)

── menu_categories ────────────────────
  id              UUID PRIMARY KEY
  restaurant_id   UUID FK → restaurants.id
  name            VARCHAR(100) NOT NULL           -- 'Starters','Mains'
  display_order   INTEGER default 0
  is_active       BOOLEAN default TRUE
  INDEX on (restaurant_id)

── menu_items ─────────────────────────
  id              UUID PRIMARY KEY
  restaurant_id   UUID FK → restaurants.id
  category_id     UUID FK → menu_categories.id
  name            VARCHAR(200) NOT NULL
  description     TEXT
  price           NUMERIC(10,2) NOT NULL
  discounted_price NUMERIC(10,2)                  -- NULL = no discount
  image_url       VARCHAR(500)
  is_veg          BOOLEAN NOT NULL default TRUE
  is_available    BOOLEAN default TRUE
  preparation_time INTEGER                        -- minutes
  tags            VARCHAR[]                       -- ['Bestseller','Spicy']
  created_at      TIMESTAMPTZ default now()
  INDEX on (restaurant_id), INDEX on (category_id)

── cart_items ─────────────────────────
  id              UUID PRIMARY KEY
  user_id         UUID FK → users.id ON DELETE CASCADE
  restaurant_id   UUID FK → restaurants.id        -- CRITICAL: enforces single-restaurant cart
  menu_item_id    UUID FK → menu_items.id
  quantity        INTEGER NOT NULL CHECK(quantity >= 1)
  added_at        TIMESTAMPTZ default now()
  UNIQUE CONSTRAINT on (user_id, menu_item_id)
  INDEX on (user_id), INDEX on (user_id, restaurant_id)

── orders ─────────────────────────────
  id              UUID PRIMARY KEY
  user_id         UUID FK → users.id
  restaurant_id   UUID FK → restaurants.id
  delivery_address_id   UUID FK → addresses.id   -- live reference
  delivery_address_snapshot  JSONB NOT NULL       -- frozen at order time
  items_total     NUMERIC(10,2) NOT NULL
  delivery_fee    NUMERIC(10,2) NOT NULL default 0
  discount_amount NUMERIC(10,2) NOT NULL default 0
  total_amount    NUMERIC(10,2) NOT NULL          -- items_total + delivery_fee - discount
  coupon_code     VARCHAR(50)
  payment_method  ENUM('COD','UPI','CARD','WALLET') NOT NULL
  payment_status  ENUM('PENDING','SUCCESS','FAILED','REFUNDED') default 'PENDING'
  status          ENUM('PLACED','CONFIRMED','PREPARING',
                       'READY_FOR_PICKUP','OUT_FOR_DELIVERY',
                       'DELIVERED','CANCELLED','FAILED') default 'PLACED'
  cancellation_reason TEXT
  estimated_delivery_at TIMESTAMPTZ
  delivered_at    TIMESTAMPTZ
  created_at      TIMESTAMPTZ default now()
  updated_at      TIMESTAMPTZ default now()
  INDEX on (user_id), INDEX on (status), INDEX on (created_at DESC)

── order_items ────────────────────────
  id              UUID PRIMARY KEY
  order_id        UUID FK → orders.id ON DELETE CASCADE
  menu_item_id    UUID FK → menu_items.id
  name            VARCHAR(200) NOT NULL           -- snapshot at order time
  price           NUMERIC(10,2) NOT NULL          -- snapshot at order time
  quantity        INTEGER NOT NULL

── coupons ────────────────────────────
  id              UUID PRIMARY KEY
  code            VARCHAR(50) UNIQUE NOT NULL
  description     VARCHAR(300)
  discount_type   ENUM('FLAT','PERCENT')
  discount_value  NUMERIC(10,2) NOT NULL
  min_order_amount NUMERIC(10,2) default 0
  max_discount    NUMERIC(10,2)                   -- cap for PERCENT type
  valid_from      TIMESTAMPTZ
  valid_until     TIMESTAMPTZ
  max_uses        INTEGER
  used_count      INTEGER default 0
  is_active       BOOLEAN default TRUE

── reviews ────────────────────────────
  id              UUID PRIMARY KEY
  order_id        UUID FK → orders.id UNIQUE      -- one review per order
  user_id         UUID FK → users.id
  restaurant_id   UUID FK → restaurants.id
  food_rating     INTEGER CHECK(food_rating BETWEEN 1 AND 5)
  delivery_rating INTEGER CHECK(delivery_rating BETWEEN 1 AND 5)
  comment         TEXT
  image_urls      VARCHAR[]
  created_at      TIMESTAMPTZ default now()
  INDEX on (restaurant_id)

═══════════════════════════════════════
SECTION 5 — AUTH MODULE (HARDENED)
═══════════════════════════════════════
OTP flow — replicate Zomato's exact security model:

POST /auth/send-otp
  Body: { phone: string }  -- validate E.164: +91XXXXXXXXXX
  Logic:
    1. Validate phone format (regex: ^\+[1-9]\d{9,14}$)
    2. Check Redis key "otp:cooldown:{phone}" — if exists, return 429
       with seconds_remaining field
    3. Generate 6-digit OTP using secrets.randbelow(900000)+100000
    4. Store in Redis: SET "otp:{phone}" "{otp}:{attempts}" EX 300
       (5-minute TTL)
    5. Set cooldown: SET "otp:cooldown:{phone}" 1 EX 60
    6. Log OTP to console (dev mode); in prod, call SMS gateway
    7. Return: { message: "OTP sent", expires_in: 300 }

POST /auth/verify-otp
  Body: { phone: string, otp: string }
  Logic:
    1. Fetch Redis key "otp:{phone}" — if missing return 401 "OTP expired"
    2. Parse stored value: split on ":" → stored_otp, attempts
    3. If attempts >= 3: delete key, return 429 "Too many attempts. Request new OTP"
    4. If otp != stored_otp:
         increment attempts in Redis (keep same TTL)
         return 401 with attempts_remaining = 3 - new_attempts
    5. DELETE "otp:{phone}" from Redis (prevent replay)
    6. Upsert user: SELECT by phone, INSERT if not found (is_verified=True)
    7. Generate access_token (JWT, 30 min) + refresh_token (JWT, 7 days)
    8. Store refresh token hash in Redis: SET "refresh:{user_id}" hash EX 604800
    9. Return: { access_token, refresh_token, token_type: "bearer",
                 user: UserResponse, is_new_user: bool }

POST /auth/refresh
  Body: { refresh_token: string }
  Logic:
    1. Decode JWT — extract user_id
    2. Hash incoming token and compare with Redis "refresh:{user_id}"
    3. If mismatch → 401 (token rotation attack detection)
    4. Issue new access_token + new refresh_token (rotate)
    5. Update Redis with new refresh token hash

POST /auth/logout
  Auth: Bearer token required
  Logic: DELETE "refresh:{user_id}" from Redis

JWT payload must include: { sub: user_id, phone: phone, iat, exp, jti }

═══════════════════════════════════════
SECTION 6 — ALL API ENDPOINTS
═══════════════════════════════════════
Prefix every group with /api/v1

── Auth (public) ──────────────────────
POST   /auth/send-otp
POST   /auth/verify-otp
POST   /auth/refresh
POST   /auth/logout            [auth required]

── Users (auth required) ──────────────
GET    /users/me
PATCH  /users/me
DELETE /users/me               -- soft delete (is_active=False)

── Addresses (auth required) ──────────
GET    /addresses              -- list all user addresses
POST   /addresses              -- add new address
GET    /addresses/{id}
PATCH  /addresses/{id}
DELETE /addresses/{id}
PATCH  /addresses/{id}/set-default

── Restaurants (public) ───────────────
GET    /restaurants
  Query params:
    city        : str (required)
    search      : str (partial name / cuisine full-text search)
    cuisine     : str (filter by cuisine type)
    is_veg      : bool
    is_open     : bool (default true)
    min_rating  : float (0–5)
    sort_by     : enum [rating, delivery_time, cost_low, cost_high, newest]
    page        : int (default 1)
    limit       : int (default 20, max 50)

GET    /restaurants/{id}
GET    /restaurants/{id}/menu   -- full menu grouped by category
  Query: is_veg=bool, is_available=bool, search=str

── Cart (auth required) ───────────────
GET    /cart                   -- full cart with computed totals
POST   /cart/add
  Body: { menu_item_id, quantity }
  Logic — execute in this exact order:
    1. Fetch menu_item — if not found or not is_available → 404/409
    2. Fetch user's current cart items (get distinct restaurant_id)
    3. If cart has items from a DIFFERENT restaurant:
         return 409 {
           error_code: "CART_CONFLICT",
           message: "Your cart has items from {existing_restaurant_name}. Clear cart to add from {new_restaurant_name}?",
           existing_restaurant: { id, name },
           new_restaurant: { id, name }
         }
    4. If same restaurant: upsert (INSERT or UPDATE quantity)
    5. Return updated cart summary

POST   /cart/update-quantity
  Body: { menu_item_id, quantity }  -- quantity=0 means remove

POST   /cart/remove
  Body: { menu_item_id }

POST   /cart/clear

POST   /cart/validate
  -- Validates every cart item is still available and restaurant is open
  -- Call this before showing checkout screen
  Returns: { is_valid: bool, invalid_items: [...], restaurant_is_open: bool }

── Orders (auth required) ─────────────
POST   /orders/place
  Body: {
    delivery_address_id : UUID,
    payment_method      : enum COD|UPI|CARD|WALLET,
    coupon_code         : str (optional)
  }
  Logic (transactional — all or nothing):
    1. Validate cart not empty
    2. Validate restaurant is_open
    3. Validate ALL menu items are still is_available
    4. Validate delivery_address belongs to current user
    5. If coupon_code provided → validate coupon (active, not expired,
       min_order met, under max_uses) → compute discount
    6. Compute: items_total, delivery_fee (from restaurant),
       discount_amount, total_amount
    7. Validate total_amount >= restaurant.min_order_amount
    8. Snapshot delivery address → JSONB
    9. Snapshot each item name+price → order_items
   10. INSERT order + order_items in one transaction
   11. If coupon used → increment coupon.used_count
   12. Clear all cart items for this user
   13. Return full OrderDetailResponse

GET    /orders
  Query: status=str, page=int, limit=int (default 10)
  Returns paginated list (newest first)

GET    /orders/{id}            -- full order detail with items

POST   /orders/{id}/cancel
  Body: { reason: string }
  Logic:
    1. Order must belong to current user
    2. Status must be PLACED or CONFIRMED only
    3. Set status=CANCELLED, cancellation_reason=reason
    4. If payment_status=SUCCESS → set payment_status=REFUNDED
    5. Return updated order

── Reviews (auth required) ────────────
POST   /reviews
  Body: { order_id, food_rating, delivery_rating, comment }
  Logic:
    1. Order must belong to user and status=DELIVERED
    2. No existing review for this order
    3. INSERT review
    4. Recalculate restaurant.rating (avg of all reviews) + total_reviews
    5. UPDATE restaurant atomically

GET    /reviews/restaurant/{restaurant_id}
  Query: page, limit

── Coupons (auth required) ────────────
POST   /coupons/validate
  Body: { code, order_amount }
  Returns: { is_valid, discount_amount, final_amount, message }

── System (public) ────────────────────
GET    /health
  Returns: { status, db, redis, version, timestamp }

═══════════════════════════════════════
SECTION 7 — BUSINESS LOGIC RULES
═══════════════════════════════════════
These rules are non-negotiable. Enforce in service layer only.

Cart rules:
  • Single-restaurant constraint: one cart = one restaurant at all times
  • On add: if item exists → increment qty; else → insert new row
  • quantity must be >= 1; set quantity=0 to remove
  • Validate is_available on every add operation
  • Cart totals: sum(item.effective_price * qty) where effective_price
    = discounted_price if not NULL else price

Order status transitions (ONLY these are valid):
  PLACED          → CONFIRMED | CANCELLED | FAILED
  CONFIRMED       → PREPARING | CANCELLED
  PREPARING       → READY_FOR_PICKUP
  READY_FOR_PICKUP → OUT_FOR_DELIVERY
  OUT_FOR_DELIVERY → DELIVERED
  DELIVERED       → (terminal — no transitions)
  CANCELLED       → (terminal — no transitions)
  FAILED          → (terminal — no transitions)

  Enforce with a transition_map dict in order_service.py.
  Any invalid transition → raise 409 InvalidStatusTransition.

Cancellation rules (exactly like Zomato):
  • User can cancel ONLY if status is PLACED or CONFIRMED
  • After PREPARING starts, cancellation is blocked
  • reason field is required

Review rules:
  • Can only review after status = DELIVERED
  • One review per order (UNIQUE on order_id)
  • After insert, atomically update restaurant.rating using:
    new_rating = (old_rating * old_count + new_rating_avg) / (old_count + 1)
    where new_rating_avg = (food_rating + delivery_rating) / 2

Coupon rules:
  • Check valid_from <= now() <= valid_until
  • Check used_count < max_uses (if max_uses is not NULL)
  • Check order total >= min_order_amount
  • FLAT discount: discount = discount_value
  • PERCENT discount: discount = min(order_total * discount_value/100, max_discount)

Address rules:
  • Max 5 addresses per user
  • Only one can be is_default=True at a time
  • On set-default: update all user addresses is_default=False, then set target=True
  • On delete of default: no auto-promotion (user must set new default)

═══════════════════════════════════════
SECTION 8 — NON-FUNCTIONAL REQUIREMENTS
═══════════════════════════════════════

Pagination:
  All list endpoints return:
  {
    success: true,
    data: [...],
    pagination: {
      page, limit, total_items, total_pages, has_next, has_prev
    }
  }

Standard response envelope (ALL endpoints):
  Success: { success: true,  message: str, data: any }
  Error:   { success: false, message: str, error_code: str, details: any }

Error codes (use consistently):
  AUTH_REQUIRED, INVALID_OTP, OTP_EXPIRED, OTP_COOLDOWN,
  TOO_MANY_OTP_ATTEMPTS, TOKEN_EXPIRED, TOKEN_INVALID,
  CART_CONFLICT, CART_EMPTY, ITEM_UNAVAILABLE,
  RESTAURANT_CLOSED, MIN_ORDER_NOT_MET,
  INVALID_STATUS_TRANSITION, REVIEW_ALREADY_EXISTS,
  COUPON_INVALID, COUPON_EXPIRED, COUPON_MIN_ORDER,
  ADDRESS_LIMIT_REACHED, NOT_FOUND, FORBIDDEN

Rate limiting (Redis-based, per IP):
  POST /auth/send-otp    → 5 requests / 10 minutes
  POST /auth/verify-otp  → 10 requests / 10 minutes
  All other endpoints    → 100 requests / minute

Implement as FastAPI middleware using Redis INCR + EXPIRE.

Logging:
  • Every request logs: request_id (UUID), method, path, status, duration_ms
  • Inject X-Request-ID header into every response
  • Use Python structlog or standard logging with JSON formatter

CORS:
  • Allow origins from CORS_ORIGINS env var (comma-separated)
  • Allow credentials=True

Security headers:
  • X-Content-Type-Options: nosniff
  • X-Frame-Options: DENY
  • Add via middleware

Database:
  • Async SQLAlchemy sessions (AsyncSession)
  • Connection pool: pool_size=10, max_overflow=20
  • All queries use select() + scalars() — no raw SQL except for
    the restaurant rating update (use func.avg)

═══════════════════════════════════════
SECTION 9 — INFRASTRUCTURE
═══════════════════════════════════════

.env.example (generate ALL keys):
  DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/zomato_user
  REDIS_URL=redis://localhost:6379/0
  SECRET_KEY=your-256-bit-secret
  ALGORITHM=HS256
  ACCESS_TOKEN_EXPIRE_MINUTES=30
  REFRESH_TOKEN_EXPIRE_DAYS=7
  CORS_ORIGINS=http://localhost:3000,http://localhost:8000
  ENVIRONMENT=development
  LOG_LEVEL=INFO

docker-compose.yml:
  Services: app, postgres:15, redis:7-alpine
  app depends_on: postgres (healthy), redis
  postgres healthcheck: pg_isready
  redis healthcheck: redis-cli ping
  Volume for postgres data persistence
  Expose app on port 8000

Dockerfile:
  FROM python:3.11-slim
  Non-root USER app
  COPY requirements.txt → pip install --no-cache-dir
  COPY . .
  CMD uvicorn app.main:app --host 0.0.0.0 --port 8000

Alembic:
  Configure for async engine in env.py
  Generate initial migration from models
  Include a seed.py that:
    • Creates 8 restaurants across 3 cities (Mumbai, Delhi, Bangalore)
    • Each restaurant has 3–4 menu categories
    • Total 40+ menu items (mix of veg/non-veg, with/without discounts)
    • 2 active coupons (one FLAT, one PERCENT)

═══════════════════════════════════════
SECTION 10 — AUTH REPAIR MANDATE
═══════════════════════════════════════
You told me I have an existing auth module. BEFORE writing new code:

1. READ the existing auth module completely
2. Identify all deviations from the spec in Section 5
3. List every deviation as a numbered finding
4. Rewrite the auth module from scratch to match Section 5 exactly
5. Do not preserve broken patterns — replace completely

Common issues to check and fix:
  ☐ OTP stored as plain string (should be "{otp}:{attempts}")
  ☐ No attempt counter → fix with atomic INCR or parsed value
  ☐ No resend cooldown key → add "otp:cooldown:{phone}"
  ☐ No refresh token implementation → add full rotation logic
  ☐ No jti in JWT payload → add UUID jti
  ☐ Refresh token not hashed in Redis → hash with sha256
  ☐ No logout endpoint → add with Redis key deletion
  ☐ OTP not deleted after verify → add DELETE after success
  ☐ Phone not validated as E.164 → add regex validator in schema
  ☐ No is_new_user flag in response → add boolean field

═══════════════════════════════════════
SECTION 11 — TEST UI (index.html)
═══════════════════════════════════════
Single HTML file at static/index.html using vanilla fetch().
No frameworks. Inline CSS only. Sections:

  1. Login — phone input → Send OTP → OTP input → Verify
     Show access_token, copy button
  2. Restaurants — city input → Search button → card grid
     Each card: name, rating, cuisine, is_open badge
  3. Restaurant detail — click a card → load menu by category
  4. Cart — add item buttons on menu → running cart sidebar
     Show: item names, quantities, subtotal
     Conflict alert if adding from different restaurant
  5. Checkout — address dropdown (load from /addresses) +
     payment method select + coupon code input + Place Order button
  6. Orders — list user orders with status badge
     Each order expandable to show items

Store token in localStorage. Send as Authorization: Bearer {token}.
Handle 401 by clearing token and showing login form.

═══════════════════════════════════════
SECTION 12 — TESTS (REQUIRED)
═══════════════════════════════════════
Write pytest tests for:

tests/test_auth.py:
  • test_send_otp_success
  • test_send_otp_cooldown (second call within 60s → 429)
  • test_verify_otp_success_new_user
  • test_verify_otp_success_existing_user
  • test_verify_otp_wrong_code (check attempts_remaining)
  • test_verify_otp_too_many_attempts (3 failures → block)
  • test_verify_otp_expired (mock Redis returning None)
  • test_refresh_token_rotation
  • test_logout_invalidates_refresh_token

tests/test_cart.py:
  • test_add_item_to_empty_cart
  • test_add_same_item_increments_quantity
  • test_add_item_from_different_restaurant_returns_409
  • test_cart_conflict_response_has_restaurant_names
  • test_remove_item
  • test_clear_cart
  • test_add_unavailable_item_returns_409

tests/test_orders.py:
  • test_place_order_success (clears cart, creates order_items)
  • test_place_order_empty_cart_returns_400
  • test_place_order_restaurant_closed_returns_409
  • test_cancel_order_placed_status
  • test_cancel_order_preparing_returns_409
  • test_invalid_status_transition_returns_409
  • test_coupon_applied_correctly
  • test_coupon_min_order_not_met_returns_400

Use pytest fixtures for: test DB, test Redis, authenticated user client.

═══════════════════════════════════════
SECTION 13 — FINAL CHECKLIST
═══════════════════════════════════════
Before returning output, verify every item:

  ☐ No business logic in routers (routers call service methods only)
  ☐ All services are async (async def)
  ☐ All DB queries use async session
  ☐ Pydantic v2 model_config used (not class Config)
  ☐ All enums defined in models and re-used in schemas
  ☐ Cart conflict returns 409 with full context object
  ☐ Order placement is wrapped in a single DB transaction
  ☐ Address snapshot is stored as JSONB on order creation
  ☐ OTP attempt counter prevents replay after 3 failures
  ☐ Refresh token is hashed (sha256) before Redis storage
  ☐ All list endpoints paginated
  ☐ Standard response envelope on every endpoint
  ☐ Rate limiting on OTP endpoints
  ☐ /health checks both DB and Redis connectivity
  ☐ docker-compose.yml starts all 3 services cleanly
  ☐ seed.py is idempotent (safe to run multiple times)
  ☐ .env.example has every variable used in config.py
  ☐ README with: setup steps, env config, running migrations,
    seeding, running tests, hitting the test UI

Output ALL files. Do not truncate. Do not say "add the rest yourself".
Every file must be complete and immediately runnable.