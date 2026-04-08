#!/usr/bin/env python3
"""Build data/seed.db from the checked-in seed_data.sql.

No Faker, no RNG — the SQL dump IS the data. This script just compiles it
into a SQLite file and verifies the expected row counts.
"""

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_FILE = DATA_DIR / "seed.db"
SEED_SQL = ROOT / "seed_data.sql"

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY,
    name TEXT,
    email TEXT,
    segment TEXT,
    region TEXT,
    signup_date TEXT
);
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY,
    name TEXT,
    category TEXT,
    price REAL,
    cost REAL
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    order_date TEXT,
    status TEXT
);
CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id),
    product_id INTEGER REFERENCES products(id),
    quantity INTEGER,
    unit_price REAL
);
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    session_date TEXT,
    duration_min INTEGER,
    channel TEXT
);
"""

EXPECTED_COUNTS = {
    "customers": 500,
    "products": 100,
    "orders": 5373,
    "order_items": 16160,
    "sessions": 16142,
}


def main() -> None:
    if not SEED_SQL.exists():
        raise FileNotFoundError(f"seed_data.sql not found at {SEED_SQL}")

    DATA_DIR.mkdir(exist_ok=True)
    if DB_FILE.exists():
        DB_FILE.unlink()

    conn = sqlite3.connect(str(DB_FILE))
    conn.executescript(SCHEMA)

    print(f"[DB] Loading seed from: {SEED_SQL}")
    sql_text = SEED_SQL.read_text(encoding="utf-8")
    conn.executescript(sql_text)
    conn.commit()

    ok = True
    for table, expected in EXPECTED_COUNTS.items():
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        if count == expected:
            print(f"[DB]   {table}: {count} rows OK")
        else:
            print(f"[DB]   {table}: {count} rows MISMATCH (expected {expected})")
            ok = False

    conn.close()

    if not ok:
        DB_FILE.unlink(missing_ok=True)
        raise RuntimeError("Row count mismatch — seed.db NOT created. Fix seed_data.sql.")

    print("[DB] Database seeded and verified successfully.")


if __name__ == "__main__":
    main()
