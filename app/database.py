import sqlite3
from pathlib import Path
from typing import Optional

_SEED_DB = Path(__file__).resolve().parent.parent / "data" / "seed.db"
_conn: Optional[sqlite3.Connection] = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY,
    name TEXT,
    email TEXT,
    segment TEXT,       -- 'enterprise','smb','consumer'
    region TEXT,        -- 'north','south','east','west'
    signup_date TEXT
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY,
    name TEXT,
    category TEXT,      -- 'electronics','apparel','home','sports','books'
    price REAL,
    cost REAL
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    order_date TEXT,
    status TEXT          -- 'completed','refunded','cancelled'
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
    channel TEXT          -- 'organic','paid','email','direct'
);
"""


def get_connection() -> sqlite3.Connection:
    """Load the pre-generated seed database into an in-memory connection.

    The seed.db file is copied into :memory: so queries are fast and
    the original file is never mutated by agent queries.
    """
    global _conn
    if _conn is None:
        if not _SEED_DB.exists():
            raise FileNotFoundError(
                f"Seed database not found at {_SEED_DB}. "
                "Run `python scripts/generate_db.py` first."
            )
        disk = sqlite3.connect(str(_SEED_DB))
        _conn = sqlite3.connect(":memory:", check_same_thread=False)
        disk.backup(_conn)
        disk.close()
        _conn.row_factory = sqlite3.Row
    return _conn


def get_schema_str() -> str:
    return SCHEMA.strip()
