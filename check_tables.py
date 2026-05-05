import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.config import settings

async def get_tables():
    engine = create_async_engine(str(settings.DATABASE_URL))
    async with engine.begin() as conn:
        res = await conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
        tables = res.scalars().all()
        for t in tables:
            print(t)
        print(f'Total tables: {len(tables)}')
    await engine.dispose()

asyncio.run(get_tables())
