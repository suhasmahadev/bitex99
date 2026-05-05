# BiteX99 Production Architecture

## 1. System Overview

BiteX99 is a three-sided food delivery marketplace connecting Customers, Restaurant Partners, and Delivery Partners in real time. The core challenge is coordinating three actors around one order with low latency, no double assignment, and consistent financial state across `orders`, `delivery_assignments`, `partner_earnings`, `restaurant_partners`, and `cart_items`.

Actors:

| Actor | Goal | Primary modules |
| --- | --- | --- |
| Customer | Discover restaurants, add food, place order, track, review | `app/routers/restaurants.py`, `cart.py`, `orders.py`, `reviews.py` |
| Restaurant Partner | Receive orders, manage menu, analytics, payouts | `app/routers/restaurant/*`, `menu_management_service.py`, `order_management_service.py` |
| Delivery Partner | Go online, accept orders, navigate, earn | `app/routers/delivery/*`, `assignment_service.py`, `earnings_service.py`, `location_service.py` |

This repo uses a modular monolith: FastAPI routers are thin HTTP adapters, services hold business logic, SQLAlchemy models represent shared tables, Redis stores ephemeral coordination state, and WebSockets in `app/main.py` provide live order/location channels.

Why this architecture fits BiteX99 today:

| Choice | Justification from codebase |
| --- | --- |
| FastAPI modular monolith | `app/main.py` includes customer, delivery, restaurant, and admin routers in one app so `order_service.place_order()` can create an order, clear cart, notify restaurant, and trigger assignment without cross-service latency. |
| PostgreSQL | Financial and lifecycle records need relational integrity: `orders`, `order_items`, `delivery_assignments`, `partner_earnings`, `restaurant_payouts`, and `reviews` all use FKs. |
| Redis | Used for OTP keys, refresh token hashes, assignment windows, unassigned retries, and restaurant offline queues. |
| WebSockets | `ConnectionManager` holds `partner_order_connections`, `partner_location_connections`, `restaurant_connections`, and `user_connections`. |
| SQLAlchemy async | All service files use `AsyncSession` and async `select()` patterns. |

## 2. End-to-End System Flow

1. Customer opens the app. JWT is checked by dependencies such as `CurrentUser` and role guards in `app/dependencies.py`.
2. Customer browses restaurants via `GET /api/v1/restaurants?city=Mumbai`. `RestaurantService.list_restaurants()` now selects only list columns and uses the `idx_restaurants_city` migration index.
3. Customer opens a restaurant menu via `GET /api/v1/restaurants/{restaurant_id}/menu`. `MenuService.get_menu()` verifies the restaurant, fetches categories, then fetches all menu items with one `IN` query.
4. Customer adds an item via `POST /api/v1/cart/add`. `CartService.add_item()` loads the `MenuItem` with its `Restaurant`, checks availability and `is_open`, then enforces the single-restaurant cart using `cart_items.restaurant_id`.
5. Customer places order via `POST /api/v1/orders/place`. `OrderService.place_order()` performs these atomic steps:
   1. Load cart items.
   2. Reject empty cart.
   3. Load restaurant.
   4. Reject closed restaurant.
   5. Load menu items in one query.
   6. Reject unavailable items.
   7. Validate address ownership.
   8. Compute `items_total`, `delivery_fee`, `discount_amount`, `total_amount`.
   9. Validate coupon and increment `coupons.used_count`.
   10. Insert `orders`.
   11. Insert `order_items` snapshots.
   12. Delete user cart rows.
6. After flush/commit, background tasks trigger restaurant notification and delivery assignment. `notify_restaurant_new_order()` pushes to `/api/v1/ws/restaurant/orders` or queues in Redis under `restaurant:pending:{restaurant_id}`.
7. `AssignmentService.auto_assign_partner()` loads the order and restaurant, calls `find_nearest_partners()`, inserts `delivery_assignments`, creates `delivery_otps`, and stores `assignment_pending:{partner_id}` for 45 seconds.
8. Restaurant accepts via `POST /api/v1/restaurant/orders/{order_id}/accept`. The order becomes `CONFIRMED`; then `PREPARING`; then `READY_FOR_PICKUP`.
9. Partner accepts via `POST /api/v1/partner/assignments/{assignment_id}/accept`; the Redis pending key is deleted and waypoints are returned.
10. Partner sends GPS every 5 seconds to `/api/v1/ws/partner/location`; `location_service.update_location()` records `partner_locations` and updates `delivery_partners.last_location_at`.
11. Partner confirms delivery via `POST /api/v1/partner/assignments/{assignment_id}/deliver` with `delivery_otps.otp`. The assignment and order become delivered, `partner_earnings` is inserted, partner wallet is credited, and `restaurant_partners.wallet_balance` is updated net of commission.
12. Customer reviews via `POST /api/v1/reviews`; `reviews` is inserted and restaurant rating is recalculated.

ASCII data flow:

```text
Customer App       -> FastAPI routers -> Services -> PostgreSQL
                         |                 |           ^
                         v                 v           |
                    Redis OTP/locks   WebSocket state  |
                         ^                 ^           |
Restaurant App     -> /restaurant/* -> ConnectionManager
Delivery App       -> /partner/*    -> assignment/location flow
```

## 3. Architecture Justification

Why modular monolith now:

| Reason | BiteX99 detail |
| --- | --- |
| Single deployment | `Dockerfile` launches one FastAPI app and `docker-compose.yml` wires app, postgres, redis. |
| Shared DB transactions | Order placement touches `orders`, `order_items`, `cart_items`, `coupons`, `addresses`, and `restaurants`. |
| Lower latency | Restaurant notification and partner assignment happen in-process after order creation. |
| Easier debugging | One request ID can trace through router, service, DB, Redis, and WebSocket push. |

Why not microservices yet:

| Microservice cost | Why it is premature |
| --- | --- |
| Sagas for order placement | `order_service.place_order()` needs all-or-nothing writes across 6 tables. |
| Distributed WebSocket broker | Current `ConnectionManager` is in memory and simple. |
| More deployment units | Current scale and repo structure do not justify separate teams or deployments. |

Extraction milestones:

| Future service | Trigger |
| --- | --- |
| Tracking service | Partner GPS exceeds 10K updates/sec. |
| Payment service | PCI isolation and real payment gateway settlement. |
| Notification service | SMS/push volume exceeds 100K/day. |
| Assignment service | Assignment retries need durable queues and dedicated scaling. |

Trade-offs:

| Decision | Chosen | Alternative | Trade-off |
| --- | --- | --- | --- |
| ORM | SQLAlchemy async | raw asyncpg | Developer speed and relationships vs max raw SQL performance |
| Auth | JWT + Redis refresh hash | DB sessions | Stateless access tokens vs more complex rotation |
| Cache | Redis | Memcached | TTL keys, lists, counters, future pub/sub |
| WS | FastAPI native | Socket.IO | Simpler backend vs fewer client protocol features |

## 4. Component Breakdown

FastAPI:

| Component | Code |
| --- | --- |
| Entry point | `app/main.py` |
| Lifespan | Initializes Redis, starts cleanup task, closes Redis on shutdown |
| Middleware | `register_middleware(app)` from `app/middleware.py` |
| Exceptions | `register_exception_handlers(app)` from `app/exceptions.py` |
| Static UI | `static/index.html`, served by `GET /` |

Middleware goals in this codebase: CORS, request ID, logging, security headers, rate limiting, and gzip where configured.

Router organization:

| Prefix | Audience |
| --- | --- |
| `/api/v1/auth/*` | Public + authenticated logout |
| `/api/v1/users`, `/addresses`, `/cart`, `/orders`, `/reviews`, `/coupons` | Customer |
| `/api/v1/partner/*` | Delivery partner |
| `/api/v1/restaurant/*` | Restaurant partner |
| `/api/v1/admin/*` | Admin approval flows |
| `/api/v1/ws/*` | WebSocket channels |

PostgreSQL:

| Detail | Value |
| --- | --- |
| Driver | asyncpg via `postgresql+asyncpg://` |
| Pool | `pool_size=10`, `max_overflow=20` in `app/database.py` |
| Critical tables | `orders`, `order_items`, `cart_items`, `delivery_assignments`, `partner_earnings`, `restaurant_partners` |

Redis:

| Usage | Keys |
| --- | --- |
| OTP | `otp:{phone}`, `otp:cooldown:{phone}` |
| Refresh token rotation | `refresh:{user_id}` |
| Assignment | `assignment_pending:{partner_id}`, `unassigned:{order_id}` |
| Restaurant offline queue | `restaurant:pending:{restaurant_id}` |
| Surge | `surge:MANUAL:{city}`, `surge:RAIN:{city}` |

WebSocket channels:

| Channel | Purpose |
| --- | --- |
| `/api/v1/ws/partner/orders` | Partner receives `NEW_ORDER`, `PING` |
| `/api/v1/ws/partner/location` | Partner streams GPS |
| `/api/v1/ws/restaurant/orders` | Restaurant receives `NEW_ORDER`, `PENDING_ORDERS`, `PING` |
| `/api/v1/ws/orders/{order_id}` | Target customer tracking channel for status/location updates |

Background tasks:

| Task | Code path |
| --- | --- |
| Cleanup stale partner locations | `app/main.py` lifespan cleanup loop |
| Auto assignment | `OrderService.place_order()` creates task calling `AssignmentService.auto_assign_partner()` |
| Assignment timeout | `AssignmentService._handle_timeout()` sleeps 45 seconds |
| Restaurant timeout | `auto_reject_timeout()` invoked after order placement |

## 5. API Design and Endpoint Map

Customer endpoints:

| Method | Path | Auth | Body | Side effects |
| --- | --- | --- | --- | --- |
| POST | `/api/v1/auth/send-otp` | Public | `phone` | Writes `otp:*`, cooldown |
| POST | `/api/v1/auth/verify-otp` | Public | `phone`, `otp`, role flags | Upserts `users`, creates partner status, writes `refresh:*` |
| POST | `/api/v1/auth/refresh` | Public | `refresh_token` | Rotates Redis refresh hash |
| POST | `/api/v1/auth/logout` | CurrentUser | none | Deletes `refresh:{user_id}` |
| GET | `/api/v1/users/me` | CurrentUser | none | none |
| PATCH | `/api/v1/users/me` | CurrentUser | profile fields | Updates `users` |
| GET | `/api/v1/addresses` | CurrentUser | none | none |
| POST | `/api/v1/addresses` | CurrentUser | address fields | Inserts `addresses` |
| PATCH | `/api/v1/addresses/{address_id}` | CurrentUser | address fields | Updates address |
| DELETE | `/api/v1/addresses/{address_id}` | CurrentUser | none | Deletes address |
| POST | `/api/v1/addresses/{address_id}/set-default` | CurrentUser | none | Clears previous default, sets target |
| GET | `/api/v1/restaurants` | Public | query params | none |
| GET | `/api/v1/restaurants/{restaurant_id}` | Public | none | none |
| GET | `/api/v1/restaurants/by-slug/{slug}` | Public | none | none |
| GET | `/api/v1/restaurants/{restaurant_id}/menu` | Public | query params | none |
| GET | `/api/v1/restaurants/menu-items/{item_id}` | Public | none | none |
| GET | `/api/v1/restaurants/{restaurant_id}/coupons` | Public | none | none |
| POST | `/api/v1/restaurants/coupons/validate` | Public | `code`, `restaurant_id`, `order_amount` | none |
| GET | `/api/v1/cart` | CurrentUser | none | none |
| POST | `/api/v1/cart/add` | CurrentUser | `menu_item_id`, `quantity` | Inserts/updates `cart_items`; may return `CART_CONFLICT` |
| POST | `/api/v1/cart/update-quantity` | CurrentUser | `menu_item_id`, `quantity` | Updates/deletes cart item |
| POST | `/api/v1/cart/remove` | CurrentUser | `menu_item_id` | Deletes cart item |
| POST | `/api/v1/cart/clear` | CurrentUser | none | Deletes user cart |
| POST | `/api/v1/orders/place` | CurrentUser | address, payment, coupon | Inserts order/items, increments coupon, clears cart, starts background tasks |
| GET | `/api/v1/orders` | CurrentUser | query params | none |
| GET | `/api/v1/orders/{order_id}` | CurrentUser | none | none |
| POST | `/api/v1/orders/{order_id}/cancel` | CurrentUser | `reason` | Updates status/payment refund |
| PATCH | `/api/v1/orders/{order_id}/status` | Internal | `status` | Updates lifecycle |
| POST | `/api/v1/reviews` | CurrentUser | ratings/comment | Inserts review, updates restaurant rating |
| GET | `/api/v1/reviews/restaurant/{restaurant_id}` | Public | pagination | none |
| POST | `/api/v1/coupons/validate` | CurrentUser | `code`, `order_amount` | none |

Delivery endpoints:

| Method | Path | Side effects |
| --- | --- | --- |
| GET | `/api/v1/partner/kyc/status` | none |
| POST | `/api/v1/partner/kyc/upload` | Writes upload file, upserts `kyc_documents` |
| POST | `/api/v1/partner/kyc/submit` | Advances status |
| GET/PATCH | `/api/v1/partner/profile` | Reads/updates `delivery_partners` |
| GET | `/api/v1/partner/profile/stats` | Aggregates partner metrics |
| POST | `/api/v1/partner/duty/start` | Sets online, creates `partner_shifts` |
| POST | `/api/v1/partner/duty/stop` | Sets offline, closes shift |
| GET | `/api/v1/partner/duty/status` | none |
| GET | `/api/v1/partner/assignments/active` | none |
| GET | `/api/v1/partner/assignments/history` | Paginated history |
| POST | `/api/v1/partner/assignments/{id}/accept` | Deletes `assignment_pending:*`, returns waypoints |
| POST | `/api/v1/partner/assignments/{id}/reject` | Marks rejected, reassigns |
| POST | `/api/v1/partner/assignments/{id}/reached-restaurant` | Advances assignment |
| POST | `/api/v1/partner/assignments/{id}/picked-up` | Sets `orders.status=OUT_FOR_DELIVERY` |
| POST | `/api/v1/partner/assignments/{id}/reached-customer` | Advances assignment |
| POST | `/api/v1/partner/assignments/{id}/deliver` | Marks delivered, writes earnings |
| POST | `/api/v1/partner/assignments/{id}/failed` | Marks failed, partial pay |
| POST | `/api/v1/partner/location/update` | Writes `partner_locations`, updates current location |
| GET | `/api/v1/partner/earnings/today` | Aggregate earnings |
| GET | `/api/v1/partner/earnings/weekly` | Aggregate weekly earnings |
| GET | `/api/v1/partner/incentives/active` | Active incentives |
| GET | `/api/v1/partner/payouts/pending` | Pending payout |
| POST | `/api/v1/partner/payouts/request` | Creates payout request |
| POST/GET | `/api/v1/partner/support/tickets` | Create/list support tickets |

Restaurant endpoints:

| Method | Path | Side effects |
| --- | --- | --- |
| POST | `/api/v1/restaurant/profile/setup` | Creates `restaurants`, `restaurant_partners`, `restaurant_timings` |
| GET/PATCH | `/api/v1/restaurant/profile` | Read/update restaurant |
| POST | `/api/v1/restaurant/profile/open-toggle` | Updates `restaurants.is_open` |
| GET/PATCH | `/api/v1/restaurant/profile/timings` | Read/update timings |
| GET | `/api/v1/restaurant/documents/status` | none |
| POST | `/api/v1/restaurant/documents/upload` | Writes file, upserts `restaurant_documents` |
| POST | `/api/v1/restaurant/documents/submit` | Advances docs status |
| GET/POST/PATCH/DELETE | `/api/v1/restaurant/menu/categories` | Category CRUD |
| GET/POST/PATCH/DELETE | `/api/v1/restaurant/menu/items` | Item CRUD |
| PATCH | `/api/v1/restaurant/menu/items/{id}/toggle` | Updates `menu_items.is_available` |
| POST | `/api/v1/restaurant/menu/items/{id}/image` | Writes image file |
| POST | `/api/v1/restaurant/menu/bulk-toggle` | Bulk item availability |
| GET | `/api/v1/restaurant/orders/live` | Live grouped orders |
| GET | `/api/v1/restaurant/orders/pending` | Pending orders |
| GET | `/api/v1/restaurant/orders` | History |
| GET | `/api/v1/restaurant/orders/{id}` | Detail |
| POST | `/api/v1/restaurant/orders/{id}/accept` | CONFIRMED + response log |
| POST | `/api/v1/restaurant/orders/{id}/reject` | CANCELLED + response log |
| POST | `/api/v1/restaurant/orders/{id}/preparing` | PREPARING |
| POST | `/api/v1/restaurant/orders/{id}/ready` | READY_FOR_PICKUP |
| GET | `/api/v1/restaurant/analytics/overview` | Aggregates orders and rating |
| GET | `/api/v1/restaurant/analytics/revenue-chart` | Revenue buckets |
| GET | `/api/v1/restaurant/analytics/top-items` | Top order items |
| GET | `/api/v1/restaurant/analytics/peak-hours` | Hourly buckets |
| GET | `/api/v1/restaurant/analytics/ratings-summary` | Rating histogram |
| GET/POST | `/api/v1/restaurant/payouts` | List/request payouts |
| GET/POST/PATCH/DELETE | `/api/v1/restaurant/offers` | Offer CRUD |
| PATCH | `/api/v1/restaurant/offers/{id}/toggle` | Enable/disable offer |
| GET | `/api/v1/restaurant/reviews` | List reviews |
| GET | `/api/v1/restaurant/reviews/stats` | Rating stats |
| POST | `/api/v1/restaurant/reviews/{id}/respond` | Writes `reviews.response_text` |

Admin/system endpoints include `/api/v1/admin/kyc/*`, `/api/v1/admin/restaurant/*`, and `/api/v1/health`.

Versioning strategy: current version is `/api/v1/*`. A future `/api/v2/*` should run alongside v1 for 6 months. Breaking response shape or state machine changes require a new version.

Response envelope convention:

```json
{ "success": true, "message": "optional", "data": {}, "pagination": {} }
{ "success": false, "message": "human text", "error_code": "CART_CONFLICT", "details": {} }
```

Observed/required error codes include: `AUTH_REQUIRED`, `INVALID_OTP`, `OTP_EXPIRED`, `OTP_COOLDOWN`, `TOO_MANY_OTP_ATTEMPTS`, `TOKEN_EXPIRED`, `TOKEN_INVALID`, `INVALID_REGISTRATION`, `CART_CONFLICT`, `CART_EMPTY`, `ITEM_UNAVAILABLE`, `RESTAURANT_CLOSED`, `MIN_ORDER_NOT_MET`, `INVALID_STATUS_TRANSITION`, `REVIEW_ALREADY_EXISTS`, `COUPON_INVALID`, `COUPON_EXPIRED`, `COUPON_MIN_ORDER`, `ADDRESS_LIMIT_REACHED`, `NOT_FOUND`, `FORBIDDEN`, `ASSIGNMENT_EXPIRED`, `INVALID_ASSIGNMENT_STATUS`, `OTP_ALREADY_USED`, `INVALID_DELIVERY_OTP`, `INVALID_FILE_TYPE`, `FILE_TOO_LARGE`, `CATEGORY_HAS_ITEMS`.

## 6. Database Schema Design

Table inventory:

| Table | Why it exists | Key relationships/indexes |
| --- | --- | --- |
| `users` | Single account table for all roles | Unique `phone`; role/status columns |
| `addresses` | Customer delivery locations | FK `user_id`, index `ix_addresses_user_id` |
| `restaurants` | Customer-visible restaurant listing | Indexes on city/rating/cuisine; new hot indexes |
| `menu_categories` | Menu grouping | FK restaurant, index restaurant |
| `menu_items` | Sellable items | FK restaurant/category, new `idx_menu_items_restaurant` |
| `cart_items` | Current cart | FK user/restaurant/menu item; unique user+item; restaurant denormalization |
| `orders` | Financial and lifecycle source of truth | FK user/restaurant/address; hot indexes user+created, restaurant+status |
| `order_items` | Immutable item snapshots | FK order/menu item |
| `coupons` | Promo validation | Unique code, optional restaurant FK |
| `reviews` | Customer feedback | Unique order review, index restaurant+created |
| `delivery_partners` | Partner profile/wallet/location | Index city, online city, location |
| `kyc_documents` | Delivery KYC docs | Unique partner+doc type |
| `partner_locations` | GPS history | Index partner+recorded |
| `partner_shifts` | Online work sessions | Index partner+started |
| `delivery_assignments` | Order-partner link | Unique order_id; index partner+status |
| `delivery_otps` | Delivery proof | Unique assignment |
| `partner_earnings` | Per-delivery pay | Index partner+earned |
| `payouts` | Partner withdrawals | Index partner+status |
| `incentive_rules` | Bonus configuration | active/type/city fields |
| `partner_incentives` | Earned bonuses | Index partner+earned |
| `support_tickets` | Partner support | Index partner+status |
| `restaurant_partners` | Restaurant owner account | Unique user and restaurant |
| `restaurant_documents` | Restaurant verification docs | Unique partner+doc |
| `restaurant_timings` | Weekly operating hours | Unique restaurant+day |
| `restaurant_offers` | Restaurant promos | Index restaurant+active |
| `restaurant_payouts` | Restaurant settlements | Index partner+status |
| `order_responses` | Accept/reject audit | Unique order_id |
| `customer_profiles`, `delivery_profiles`, `restaurant_profiles` | Role profile extension tables | PK/FK user_id |

UUID primary keys prevent sequential enumeration and are safe in URLs. `order_items` uses the snapshot pattern (`name`, `price`, `quantity`) so historical receipts do not change if `menu_items.price` changes later.

`cart_items.restaurant_id` exists because cart conflict checks need the current restaurant without joining through `menu_items`. It also enables the 409 `CART_CONFLICT` response to compare existing/new restaurant IDs quickly.

Hot index strategy added in `alembic/versions/c1a2b3c4d5e6_add_hot_query_indexes.py`:

| Index | Purpose |
| --- | --- |
| `idx_restaurants_city` | Restaurant listing by city |
| `idx_restaurants_rating` | Sort by rating |
| `idx_restaurants_is_open` | Open restaurant filtering |
| `idx_cart_user_id` | Cart fetch |
| `idx_cart_restaurant` | Cart conflict check |
| `idx_orders_user_created` | User order history |
| `idx_orders_restaurant_status` | Restaurant live orders |
| `idx_assignments_partner_status` | Active partner assignment |
| `idx_partner_loc_partner_time` | Recent GPS |
| `idx_menu_items_restaurant` | Menu availability |
| `idx_reviews_restaurant` | Restaurant reviews |

## 7. Transaction Management

| Transaction | Code | Why |
| --- | --- | --- |
| Order placement | `OrderService.place_order()` | Prevents order without items, coupon increment without order, or uncleared cart |
| Address default | `AddressService.set_default()` | Prevents multiple defaults |
| Review creation | `ReviewService.create_review()` | Review/rating consistency |
| Assignment delivery | `AssignmentService.deliver()` | Delivered order, OTP use, partner earnings, restaurant wallet must move together |
| Restaurant order accept/reject | `order_management_service.py` | Status and response audit must agree |

Default isolation is PostgreSQL `READ COMMITTED`. Assignment creation should use row-level locking on `delivery_partners` when scaling beyond the current implementation to prevent simultaneous transactions assigning the same partner.

Race prevention:

| Race | Prevention |
| --- | --- |
| Same cart placed twice | Future Redis `order:idempotency:{user_id}:{cart_hash}` |
| Two partners accept | `assignment_pending:{partner_id}` is deleted on first accept; `delivery_assignments.order_id` is unique |
| Cart conflict from two devices | `cart_items` unique user+menu item plus restaurant check |
| Coupon max use | Should lock coupon row before `used_count` increment |
| Restaurant rating update | Atomic aggregate/update recommended in review service |

## 8. Idempotency Design

Order placement should use Redis:

```text
order:idempotency:{user_id}:{cart_hash} -> order_id, TTL 60s
cart_hash = md5(sorted(menu_item_ids + quantities))
```

Current OTP idempotency already exists via `otp:{phone}` and `otp:cooldown:{phone}`. Delivery OTP idempotency exists via `delivery_otps.is_used`; once marked true, subsequent calls return `OTP_ALREADY_USED`.

## 9. Redis Architecture

| Key pattern | TTL | Purpose |
| --- | --- | --- |
| `otp:{phone}` | 300s | OTP and attempt count |
| `otp:cooldown:{phone}` | 60s | Prevent resend |
| `refresh:{user_id}` | 7 days | Refresh token hash |
| `assignment_pending:{partner_id}` | 45s | Assignment accept window |
| `unassigned:{order_id}` | 600s | No partner available retry marker |
| `restaurant:pending:{restaurant_id}` | 3600s | Offline restaurant order queue |
| `surge:MANUAL:{city}` | varies | Manual surge |
| `surge:RAIN:{city}` | varies | Rain surge |
| `ratelimit:{ip}:{path}:{window}` | 60s | Rate limiting |

OTP value format is specified as `"334096:0"`, meaning `OTP_CODE:ATTEMPT_COUNT`. On success the key is deleted, preventing replay.

Failure behavior:

| Scenario | Response |
| --- | --- |
| Redis down at startup | App should fail fast because OTP/auth/assignment windows depend on Redis |
| Redis down during OTP | Return 503 for auth operations |
| Redis down during non-critical rate limit | Bypass or degrade with logging |
| Redis timeout | Keep timeout low and fail closed for security-sensitive flows |

## 10. Authentication and Security

OTP flow:

1. `POST /api/v1/auth/send-otp`
2. Validate E.164 phone.
3. Check `otp:cooldown:{phone}`.
4. Generate 6 digits using secure randomness.
5. Store `otp:{phone}` as `"{otp}:{attempts}"` with 300s TTL.
6. Store cooldown for 60s.
7. Return expiry.

Verify flow:

1. `POST /api/v1/auth/verify-otp`.
2. Fetch `otp:{phone}`.
3. If missing, return `OTP_EXPIRED`.
4. If wrong, increment attempts.
5. If attempts exceed max, delete OTP and return `TOO_MANY_OTP_ATTEMPTS`.
6. If correct, delete OTP, upsert user, issue JWT pair, write `refresh:{user_id}`.

JWT payload includes `sub`, `phone`, `role`, `partner_id`, `restaurant_id`, `jti`, `iat`, `exp`.

Token rotation:

| Step | Behavior |
| --- | --- |
| Decode refresh | Extract user ID and jti |
| Hash incoming token | Compare to Redis `refresh:{user_id}` |
| Mismatch | 401 token reuse risk |
| Match | Issue new pair and replace Redis hash |

Attack prevention:

| Attack | Control |
| --- | --- |
| OTP brute force | Attempts in Redis, cooldown/rate limit |
| OTP replay | Delete on success |
| Refresh theft | Rotation and hash-at-rest |
| XSS token theft | Short access TTL; future httpOnly cookies recommended |
| CORS abuse | Env-driven CORS origins |

## 11. Order Lifecycle State Machine

Valid transitions from `app/models/order.py`:

| From | To |
| --- | --- |
| `PLACED` | `CONFIRMED`, `CANCELLED`, `FAILED` |
| `CONFIRMED` | `PREPARING`, `OUT_FOR_DELIVERY`, `CANCELLED` |
| `PREPARING` | `READY_FOR_PICKUP` |
| `READY_FOR_PICKUP` | `OUT_FOR_DELIVERY` |
| `OUT_FOR_DELIVERY` | `DELIVERED`, `FAILED` |
| `DELIVERED` | terminal |
| `CANCELLED` | terminal |
| `FAILED` | terminal |

Trigger ownership:

| Transition | Trigger |
| --- | --- |
| `PLACED` | Customer order placement |
| `CONFIRMED` | Restaurant accept |
| `CANCELLED` | Customer cancel, restaurant reject, system timeout |
| `PREPARING` | Restaurant mark preparing |
| `READY_FOR_PICKUP` | Restaurant mark ready |
| `OUT_FOR_DELIVERY` | Partner picked up |
| `DELIVERED` | Partner delivery OTP |
| `FAILED` | Delivery failure/system |

Strict enforcement avoids impossible financial states such as `PLACED -> DELIVERED` without assignment and earnings.

## 12. Assignment Engine Design

`AssignmentService.auto_assign_partner()` calls `find_nearest_partners()` using restaurant coordinates and city. Eligibility:

| Filter | Reason |
| --- | --- |
| `is_online = TRUE` | Partner is on duty |
| same `city` | Avoid cross-city assignment |
| fresh `last_location_at` | Avoid stale devices |
| no active assignment | Prevent double work |

Haversine SQL uses earth radius `6371` km. `LEAST/GREATEST` clamping prevents `acos()` domain errors for nearly identical coordinates.

Queue behavior:

1. Top 5 nearest partners are selected.
2. Nearest partner gets `assignment_pending:{partner_id}` for 45 seconds.
3. If accepted, key is deleted.
4. If rejected/timed out, service attempts reassignment.
5. If none available, writes `unassigned:{order_id}`.

## 13. Concurrency and Race Conditions

| Scenario | Risk | Mitigation |
| --- | --- | --- |
| Customer taps place order twice | duplicate orders | Redis idempotency key planned |
| Two partners accept same assignment | duplicate delivery | Redis pending key + unique `delivery_assignments.order_id` |
| Restaurant review race | wrong rating | atomic update recommended |
| Wallet double-credit/debit | wrong payout | delivery completion updates wallets in one transaction |
| Cart from two devices | mixed restaurant cart | `cart_items.restaurant_id` check and unique user+item |
| Coupon used at limit | revenue leakage | `SELECT FOR UPDATE` on coupon recommended |

## 14. Background Job System

Current implementation uses `asyncio.create_task()`:

| Task | Code path | Risk |
| --- | --- | --- |
| Auto assign partner | `OrderService.place_order()` | lost on process restart |
| Assignment timeout | `AssignmentService._handle_timeout()` | sleep lost on restart |
| Restaurant auto reject | `auto_reject_timeout()` | sleep lost on restart |
| Stale location cleanup | `app/main.py` lifespan | only one process should own cleanup |

Migration point to Celery + Redis: before 1000 daily orders or any scenario where a lost background task can lose money. Celery tasks should retry three times, then write a dead-letter record and alert engineering.

## 15. WebSocket Architecture

`ConnectionManager` in `app/main.py` stores:

| Dict | Key | Purpose |
| --- | --- | --- |
| `partner_order_connections` | `partner_id` | Push assignment events |
| `partner_location_connections` | `partner_id` | Receive GPS |
| `restaurant_connections` | `restaurant_id` | Push restaurant orders |
| `user_connections` | `user_id` | Push customer updates |

Lifecycle:

1. Client connects with `?token=`.
2. JWT is verified with `verify_access_token`.
3. Role is checked.
4. Socket is accepted.
5. Connection is stored.
6. Pending Redis messages are drained where applicable.
7. Ping keeps connection alive.
8. Disconnect removes dict entry.

Events:

| Audience | Events |
| --- | --- |
| Customer | `STATUS_UPDATE`, `PARTNER_ASSIGNED`, `PARTNER_LOCATION_UPDATE`, `ORDER_CANCELLED`, `DELIVERED` |
| Partner | `NEW_ORDER`, `ORDER_CANCELLED`, `INCENTIVE_EARNED`, `PING` |
| Restaurant | `NEW_ORDER`, `PENDING_ORDERS`, `PING` |

Scaling plan: use Redis Pub/Sub channels like `location:{order_id}`, `restaurant:{restaurant_id}`, and `partner:{partner_id}` so any app server can forward events to local sockets.

## 16. Failure Scenarios

| ID | Scenario | Impact | Mitigation |
| --- | --- | --- | --- |
| F01 | Redis down | OTP, refresh, assignments fail | Startup ping fail-fast; 503 for auth |
| F02 | PostgreSQL slow query | Pool exhaustion | Hot indexes, statement timeout, pg_stat_activity |
| F03 | Partner app crash mid-delivery | stale tracking | stale cleanup offlines partner; active assignment reload |
| F04 | SMS gateway down | login blocked | retry gateway; secure admin OTP fallback |
| F05 | Duplicate order placement | double charge/order | Redis idempotency key |
| F06 | All partners reject | undelivered order | `unassigned:{order_id}`, retry, then FAILED/refund |
| F07 | Payment failure | pending order | `payment_status=PENDING/FAILED`, no restaurant confirmation until success |
| F08 | Restaurant no response | stuck PLACED | 90s auto reject task |
| F09 | Concurrent cart adds | mixed cart | single-restaurant check + unique constraint |
| F10 | Delivery OTP expired | cannot deliver | `OTP_EXPIRED`, support/manual resolution |
| F11 | Partner offline during delivery | tracking paused | active assignment remains; reconnect restores |
| F12 | DB pool exhausted | connection errors | pool_size 10, max_overflow 20, PgBouncer later |
| F13 | Server restart | tasks lost | scan non-terminal orders on startup; future Celery |
| F14 | Invalid coordinates | assignment/location bad | validate lat/lng and clamp Haversine |
| F15 | Review bombing | fake ratings | unique `reviews.order_id`, delivered-order requirement |
| F16 | GPS flood | DB overwhelmed | server-side per-connection throttle |
| F17 | JWT stolen | impersonation | short access TTL, refresh hash/rotation |
| F18 | Commission bug | under/overpay | calculate on delivered and audit by `order_id` |
| F19 | Menu price changes | historical mismatch | `order_items.price` snapshot |
| F20 | Coupon overuse | revenue loss | lock coupon row, increment in order transaction |

## 17. Observability

Structured request log:

```json
{
  "timestamp": "2026-05-05T15:30:00Z",
  "level": "INFO",
  "request_id": "uuid",
  "method": "POST",
  "path": "/api/v1/orders/place",
  "status_code": 200,
  "duration_ms": 145,
  "user_id": "uuid",
  "role": "CUSTOMER",
  "ip": "192.168.1.1"
}
```

Metrics to track:

| Metric | Target |
| --- | --- |
| P95 latency per endpoint | < 500ms |
| Error rate | < 0.1% |
| OTP success rate | > 98% |
| Assignment success rate | > 90% |
| WebSocket connection count | capacity indicator |
| Redis memory | < 80% |
| DB pool wait | < 100ms |
| Active orders | operational dashboard |

Request ID should be injected into response headers and logs. Alerts: P95 > 500ms, error rate > 1%, Redis memory > 80%, DB pool wait > 100ms, assignment failure > 10%.

## 18. Performance and Scaling

Part 1 mitigations added:

| Area | Fix |
| --- | --- |
| Restaurant listing | Selects only list columns instead of full ORM object |
| Cart serialization | Uses `selectinload(CartItem.menu_item)` and `selectinload(CartItem.restaurant)` |
| Assignment active/accept | Eager-loads OTP/order/restaurant |
| Earnings today | Shift hours aggregated in SQL instead of Python object loop |
| Restaurant analytics overview | Consolidated 5 stats calls into one aggregate query |
| Hot indexes | Added migration `c1a2b3c4d5e6_add_hot_query_indexes.py` |
| Sync file writes | Replaced `open(...).write()` with `asyncio.to_thread(Path.write_bytes)` |

Current bottlenecks:

| Bottleneck | Next fix |
| --- | --- |
| Restaurant list no cache | Redis key `cache:restaurants:{city}:{filters_hash}:{page}`, 5min TTL |
| Haversine over all partners | PostGIS `ST_DWithin` spatial index |
| In-memory WebSockets | Redis Pub/Sub |
| Background task durability | Celery with Redis broker |

Scaling phases:

| Phase | Architecture |
| --- | --- |
| Current | One FastAPI app, PostgreSQL, Redis |
| 1K daily orders | PgBouncer, query monitoring |
| 10K daily orders | Multiple app servers, Redis Pub/Sub, read replica |
| 100K daily orders | Kubernetes, tracking service, Kafka/event bus |

Cache policy:

| Data | TTL |
| --- | --- |
| Restaurant list | 5 minutes |
| Restaurant detail | 10 minutes |
| Menu | 10 minutes, invalidate on menu change |
| User profile/cart | no cache |

## 19. Deployment Architecture

Development:

```text
PostgreSQL: docker-compose service postgres
Redis: docker-compose service redis
FastAPI: uvicorn app.main:app --reload --port 8000
Static UI: GET /
```

Docker production:

| Service | Image/config |
| --- | --- |
| app | `Dockerfile`, Python 3.11 slim, uvicorn |
| postgres | `postgres:15-alpine`, volume `postgres_data` |
| redis | `redis:7-alpine`, volume `redis_data` |

Nginx reverse proxy:

```nginx
upstream bitex_app { server app:8000; }
server {
  listen 80;
  location /api/ {
    proxy_pass http://bitex_app;
    proxy_set_header X-Real-IP $remote_addr;
  }
  location /api/v1/ws/ {
    proxy_pass http://bitex_app;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 86400;
  }
}
```

Production env:

```env
DATABASE_URL=postgresql+asyncpg://user:pass@rds-endpoint/bitex
REDIS_URL=redis://elasticache-endpoint:6379/0
SECRET_KEY=<256-bit-random>
ENVIRONMENT=production
LOG_LEVEL=INFO
CORS_ORIGINS=https://bitex99.in,https://app.bitex99.in
```

AWS shape: ALB -> EC2/Fargate app -> RDS PostgreSQL -> ElastiCache Redis -> Route53.

## 20. Testing Strategy

Current tests exist under `tests/` for auth, cart, orders, restaurant analytics/offers/payouts/reviews. Add coverage for:

| Test type | Scope |
| --- | --- |
| Unit | Service math like `calculate_earnings()` and coupon discount |
| Integration | httpx AsyncClient against test DB and fake Redis |
| Concurrency | double place-order, double assignment accept, coupon max-use race |
| WebSocket | partner orders, partner location, restaurant orders |
| Load | Locust browsing and order placement |

Example concurrency tests:

```python
async def test_concurrent_order_placement(client):
    results = await asyncio.gather(place_order(client), place_order(client))
    assert sum(r.status_code == 200 for r in results) == 1

async def test_concurrent_accept_assignment(client, assignment_id):
    results = await asyncio.gather(accept(client, assignment_id), accept(client, assignment_id))
    assert sum(r.status_code == 200 for r in results) == 1
```

Coverage targets:

| Module | Target |
| --- | --- |
| Auth | 100% |
| Order placement | 100% |
| Cart | 95% |
| Assignment | 90% |
| Analytics | 70% |

Run command:

```bash
pytest tests/ -v --tb=short --cov=app --cov-report=term-missing
```

Local verification note: this workstation currently lacks a usable Python interpreter, `psql`, and a running Docker daemon, so dynamic query-count and test execution must be run in an environment with those tools available.
