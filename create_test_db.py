import asyncio
import asyncpg

async def create_db():
    conn = await asyncpg.connect('postgresql://postgres:1234567890@localhost:5432/postgres')
    try:
        await conn.execute('CREATE DATABASE bitex_test')
        print("Database created")
    except asyncpg.exceptions.DuplicateDatabaseError:
        print("Database already exists")
    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(create_db())
