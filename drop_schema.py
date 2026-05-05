import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def clean():
    engine = create_async_engine('postgresql+asyncpg://postgres:1234567890@localhost:5432/bitex', isolation_level='AUTOCOMMIT')
    async with engine.connect() as conn:
        await conn.execute(text('DROP SCHEMA public CASCADE;'))
        await conn.execute(text('CREATE SCHEMA public;'))
    await engine.dispose()

if __name__ == '__main__':
    asyncio.run(clean())
