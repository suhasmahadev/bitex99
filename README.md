# Zomato Clone - Backend & UI Test Client

A production-grade FastAPI backend replicating the customer-side functionality of Zomato, along with a vanilla JS test UI.

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.11+ |
| Framework | FastAPI |
| ORM | SQLAlchemy 2.0 (async) |
| Database | PostgreSQL 15 |
| Cache & Rate Limiting | Redis 7 |
| Migrations | Alembic |
| Testing | pytest, pytest-asyncio, fakeredis |
| Containerization | Docker & docker-compose |

## Folder Structure

```
zomato_user/
├── alembic/
│   ├── env.py
│   └── versions/
├── app/
│   ├── models/
│   │   ├── user.py, address.py, restaurant.py, menu.py, cart.py, order.py, review.py
│   ├── routers/
│   │   ├── auth.py, users.py, addresses.py, restaurants.py, menu.py, cart.py, orders.py, reviews.py
│   ├── schemas/
│   │   ├── auth.py, user.py, address.py, restaurant.py, menu.py, cart.py, order.py, review.py
│   ├── services/
│   │   ├── auth_service.py, user_service.py, address_service.py, restaurant_service.py, menu_service.py, cart_service.py, order_service.py, review_service.py
│   ├── utils/
│   │   ├── otp.py, jwt.py, pagination.py, response.py
│   ├── config.py
│   ├── database.py
│   ├── dependencies.py
│   ├── exceptions.py
│   ├── main.py
│   ├── middleware.py
│   └── redis_client.py
├── static/
│   └── index.html
├── tests/
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_cart.py
│   └── test_orders.py
├── .env.example
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
├── pytest.ini
├── README.md
├── requirements.txt
└── seed.py
```

## Local Setup (Windows-friendly)

1. **Clone the repository and enter the directory**:
   ```cmd
   cd bitex99
   ```

2. **Create a virtual environment**:
   ```cmd
   python -m venv env
   env\Scripts\activate
   ```

3. **Install requirements**:
   ```cmd
   pip install -r requirements.txt
   ```

4. **Set up environment variables**:
   ```cmd
   copy .env.example .env
   ```

5. **Start Database and Redis via Docker**:
   ```cmd
   docker-compose up -d postgres redis
   ```

6. **Run Migrations & Seed the database**:
   ```cmd
   alembic upgrade head
   python seed.py
   ```

## Environment Variables

| Variable | Description |
|---|---|
| `DATABASE_URL` | Asyncpg connection string for PostgreSQL |
| `REDIS_URL` | Redis connection URL |
| `SECRET_KEY` | Secret key for JWT signing |
| `ALGORITHM` | JWT signing algorithm (e.g., HS256) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifespan in minutes |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifespan in days |
| `CORS_ORIGINS` | Comma-separated list of allowed origins |
| `ENVIRONMENT` | deployment environment (development/production) |
| `LOG_LEVEL` | Logging level (INFO, DEBUG, etc.) |

## API Endpoints

| Group | Method | Endpoint | Description |
|---|---|---|---|
| Auth | POST | `/api/v1/auth/send-otp` | Send OTP to phone |
| Auth | POST | `/api/v1/auth/verify-otp` | Verify OTP and return tokens |
| Auth | POST | `/api/v1/auth/refresh` | Refresh access token |
| Auth | POST | `/api/v1/auth/logout` | Logout user |
| Users | GET | `/api/v1/users/me` | Get current user |
| Addresses| GET | `/api/v1/addresses` | List addresses |
| Addresses| POST | `/api/v1/addresses` | Add address |
| Restaurants| GET | `/api/v1/restaurants` | List restaurants (paginated, filtered) |
| Restaurants| GET | `/api/v1/restaurants/{id}` | Get restaurant details |
| Restaurants| GET | `/api/v1/restaurants/{id}/menu`| Get full menu grouped by category |
| Cart | GET | `/api/v1/cart` | Get current cart with totals |
| Cart | POST | `/api/v1/cart/add` | Add item to cart (checks conflict) |
| Cart | POST | `/api/v1/cart/update-quantity`| Update quantity of cart item |
| Cart | POST | `/api/v1/cart/clear` | Empty the cart |
| Orders | POST | `/api/v1/orders/place` | Place an order from cart |
| Orders | GET | `/api/v1/orders` | List user orders |
| Orders | POST | `/api/v1/orders/{id}/cancel` | Cancel an order |
| Reviews | POST | `/api/v1/reviews` | Review a delivered order |

## Order Status Flow

```text
    [ PLACED ]
        |
        v
  [ CONFIRMED ] ---------> [ CANCELLED ]
        |                       ^
        v                       |
  [ PREPARING ] ----------------+  (Cancellation blocked past this point)
        |
        v
[ READY_FOR_PICKUP ]
        |
        v
[ OUT_FOR_DELIVERY ]
        |
        v
  [ DELIVERED ]
```

## Running Tests

Run the test suite using pytest. The tests use `fakeredis` and a separate PostgreSQL test database (ensure you have it created or configured via `conftest.py`).

```cmd
pytest tests/ -v --tb=short
```

## Opening the UI

1. **Start the FastAPI backend server**:
   ```cmd
   uvicorn app.main:app --reload --port 8000
   ```
2. **Open the Zomato test UI**:
   Open a web browser and navigate to:
   http://localhost:8000/static/index.html
