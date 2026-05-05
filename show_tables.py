import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def show_tables():
    engine = create_async_engine('postgresql+asyncpg://postgres:1234567890@localhost:5432/bitex')
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname != 'pg_catalog' AND schemaname != 'information_schema' ORDER BY tablename;"))
        rows = result.fetchall()
        print("          List of relations")
        print(" Schema |       Name        | Type  |  Owner   ")
        print("--------+-------------------+-------+----------")
        for row in rows:
            name = row[0].ljust(17)
            print(f" public | {name} | table | postgres ")
    await engine.dispose()

if __name__ == '__main__':
    asyncio.run(show_tables())
