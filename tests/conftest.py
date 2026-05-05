"""
Pytest configuration and shared fixtures.
"""
import asyncio
from collections.abc import AsyncGenerator
import json
import pytest
import pytest_asyncio
import fakeredis
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.database import Base, get_db
from app.main import app
from app.models.user import User
from app.models.address import Address
from app.models.restaurant import Restaurant
from app.models.menu import MenuCategory, MenuItem
import app.redis_client as rc

TEST_DATABASE_URL = "postgresql+asyncpg://postgres:1234567890@localhost:5432/bitex_test"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(
    bind=test_engine, class_=AsyncSession,
    expire_on_commit=False, autoflush=False,
)

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="function", autouse=True)
async def create_tables():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()

@pytest_asyncio.fixture(autouse=True)
async def redis_client_fixture() -> AsyncGenerator[fakeredis.FakeAsyncRedis, None]:
    fake_redis = fakeredis.FakeAsyncRedis(decode_responses=False)
    rc.redis_client = fake_redis
    yield fake_redis
    await fake_redis.flushall()
    rc.redis_client = None

@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()

from sqlalchemy import select

@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    result = await db_session.execute(select(User).where(User.phone == "+919999000001"))
    user = result.scalar_one_or_none()
    if not user:
        user = User(phone="+919999000001", is_verified=True)
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
    return user

@pytest_asyncio.fixture
async def auth_headers(test_user: User) -> dict:
    from app.utils.jwt import create_access_token
    token = create_access_token(str(test_user.id), phone=test_user.phone)
    return {"Authorization": f"Bearer {token}"}

@pytest_asyncio.fixture
async def seeded_restaurant(db_session: AsyncSession) -> Restaurant:
    restaurant = Restaurant(
        name="Burger Barn",
        slug="burger-barn",
        city="Mumbai",
        full_address="123 Test St",
        is_open=True,
        min_order_amount=0.0,
        rating=4.2,
        delivery_fee=30.0
    )
    db_session.add(restaurant)
    await db_session.commit()
    await db_session.refresh(restaurant)
    return restaurant

@pytest_asyncio.fixture
async def seeded_menu_items(db_session: AsyncSession, seeded_restaurant: Restaurant) -> list[MenuItem]:
    category = MenuCategory(
        restaurant_id=seeded_restaurant.id,
        name="Burgers"
    )
    db_session.add(category)
    await db_session.commit()
    await db_session.refresh(category)

    item1 = MenuItem(
        restaurant_id=seeded_restaurant.id,
        category_id=category.id,
        name="Classic Burger",
        price=150.0,
        is_available=True,
        is_veg=True
    )
    item2 = MenuItem(
        restaurant_id=seeded_restaurant.id,
        category_id=category.id,
        name="Chicken Burger",
        price=200.0,
        is_available=True,
        is_veg=False
    )
    db_session.add_all([item1, item2])
    await db_session.commit()
    await db_session.refresh(item1)
    await db_session.refresh(item2)
    return [item1, item2]

@pytest_asyncio.fixture
async def seeded_address(db_session: AsyncSession, test_user: User) -> Address:
    address = Address(
        user_id=test_user.id,
        label="HOME",
        full_address="456 User St"
    )
    db_session.add(address)
    await db_session.commit()
    await db_session.refresh(address)
    return address
