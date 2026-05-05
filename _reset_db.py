import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def reset():
    e = create_async_engine("postgresql+asyncpg://postgres:1234567890@localhost:5432/bitex")
    async with e.begin() as c:
        # Drop all tables including alembic tracking
        await c.execute(text("DROP SCHEMA public CASCADE"))
        await c.execute(text("CREATE SCHEMA public"))
        await c.execute(text("GRANT ALL ON SCHEMA public TO postgres"))
        await c.execute(text("GRANT ALL ON SCHEMA public TO public"))
        print("Schema reset complete")
    await e.dispose()

asyncio.run(reset())
