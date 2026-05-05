"""Verify database schema — equivalent of \dt and \d cart_items"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DB = "postgresql+asyncpg://postgres:1234567890@localhost:5432/bitex"

async def main():
    e = create_async_engine(DB)
    async with e.connect() as c:
        # 1. \dt — list all tables
        r = await c.execute(text("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public' 
            ORDER BY tablename
        """))
        tables = r.scalars().all()
        print(f"=== \\dt  ({len(tables)} tables) ===")
        for t in tables:
            print(f"  public | {t}")

        # 2. \d cart_items — describe cart_items table
        r2 = await c.execute(text("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'cart_items' 
            ORDER BY ordinal_position
        """))
        print(f"\n=== \\d cart_items ===")
        print(f"{'Column':<20} {'Type':<25} {'Nullable':<10} {'Default'}")
        print("-" * 90)
        for row in r2:
            print(f"{row[0]:<20} {row[1]:<25} {row[2]:<10} {row[3] or ''}")

        # 3. \d orders — describe orders table (verify JSONB, enums)
        r3 = await c.execute(text("""
            SELECT column_name, data_type, udt_name, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'orders' 
            ORDER BY ordinal_position
        """))
        print(f"\n=== \\d orders ===")
        print(f"{'Column':<30} {'Type':<20} {'UDT':<20} {'Nullable':<10} {'Default'}")
        print("-" * 110)
        for row in r3:
            print(f"{row[0]:<30} {row[1]:<20} {row[2]:<20} {row[3]:<10} {row[4] or ''}")

        # 4. Check menu_items for discounted_price
        r4 = await c.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'menu_items' AND column_name = 'discounted_price'
        """))
        row = r4.first()
        if row:
            print(f"\n=== menu_items.discounted_price ===")
            print(f"  type={row[1]}, nullable={row[2]}  (PASS)")
        else:
            print(f"\n  FAIL: menu_items.discounted_price column NOT FOUND")

        # 5. Check cart_items constraints
        r5 = await c.execute(text("""
            SELECT conname, contype, pg_get_constraintdef(oid)
            FROM pg_constraint 
            WHERE conrelid = 'cart_items'::regclass
            ORDER BY conname
        """))
        print(f"\n=== cart_items constraints ===")
        for row in r5:
            print(f"  {row[0]:<35} type={row[1]}  {row[2]}")

    await e.dispose()

asyncio.run(main())
