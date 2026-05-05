import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def q():
    e = create_async_engine('postgresql+asyncpg://postgres:1234567890@localhost:5432/bitex')
    async with e.connect() as c:
        r = await c.execute(text('SELECT COUNT(*) FROM restaurants'))
        print('Restaurants:', r.scalar())
        r2 = await c.execute(text('SELECT COUNT(*) FROM menu_items'))
        print('Menu items:', r2.scalar())
        # Get 2 restaurants with their IDs and names
        r3 = await c.execute(text('SELECT id, name FROM restaurants LIMIT 3'))
        rows = r3.fetchall()
        for row in rows:
            print(f'  Restaurant: {row[0]} -> {row[1]}')
        # Get 1 menu item from each of the first 2 restaurants
        for row in rows[:2]:
            r4 = await c.execute(text(f"SELECT id, name, price, discounted_price, is_available FROM menu_items WHERE restaurant_id = '{row[0]}' LIMIT 2"))
            items = r4.fetchall()
            for item in items:
                print(f'    MenuItem: {item[0]} -> {item[1]} price={item[2]} disc={item[3]} avail={item[4]}')
    await e.dispose()

asyncio.run(q())
