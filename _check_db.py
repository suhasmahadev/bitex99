import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def check():
    e = create_async_engine("postgresql+asyncpg://postgres:1234567890@localhost:5432/bitex")
    async with e.connect() as c:
        r = await c.execute(text("SELECT version()"))
        print(r.scalar())
    await e.dispose()

asyncio.run(check())
