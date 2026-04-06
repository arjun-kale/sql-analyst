import random
import sqlite3
from datetime import date
from typing import Optional

from faker import Faker

fake = Faker()
random.seed(42)
Faker.seed(42)

DB_PATH = ":memory:"
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
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _seed_database(_conn)
    return _conn


def _seed_database(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    _seed_customers(conn)
    _seed_products(conn)
    _seed_orders_and_items(conn)
    _seed_sessions(conn)
    conn.commit()


def _seed_customers(conn: sqlite3.Connection) -> None:
    segs = ["enterprise", "smb", "consumer"]
    regions = ["north", "south", "east", "west"]
    rows = [
        (
            i,
            fake.name(),
            fake.email(),
            random.choice(segs),
            random.choice(regions),
            str(fake.date_between(date(2021, 1, 1), date(2023, 6, 30))),
        )
        for i in range(1, 501)
    ]
    conn.executemany("INSERT INTO customers VALUES (?,?,?,?,?,?)", rows)


def _seed_products(conn: sqlite3.Connection) -> None:
    cats = ["electronics", "apparel", "home", "sports", "books"]
    rows = []
    for i in range(1, 101):
        price = round(random.uniform(10, 500), 2)
        rows.append(
            (
                i,
                f"{fake.word().title()} {fake.word().title()}",
                random.choice(cats),
                price,
                round(price * 0.6, 2),
            )
        )
    conn.executemany("INSERT INTO products VALUES (?,?,?,?,?)", rows)


def _seed_orders_and_items(conn: sqlite3.Connection) -> None:
    oid = 1
    item_id = 1
    for cust_id in range(1, 501):
        n_orders = random.randint(1, 20)
        for _ in range(n_orders):
            order_date = str(fake.date_between(date(2022, 1, 1), date(2023, 12, 31)))
            status = random.choices(
                ["completed", "refunded", "cancelled"], weights=[85, 10, 5], k=1
            )[0]
            conn.execute(
                "INSERT INTO orders VALUES (?,?,?,?)",
                (oid, cust_id, order_date, status),
            )
            n_items = random.randint(1, 5)
            for _ in range(n_items):
                pid = random.randint(1, 100)
                qty = random.randint(1, 3)
                price_row = conn.execute(
                    "SELECT price FROM products WHERE id=?", (pid,)
                ).fetchone()
                price = float(price_row[0]) if price_row is not None else 0.0
                conn.execute(
                    "INSERT INTO order_items VALUES (?,?,?,?,?)",
                    (item_id, oid, pid, qty, price),
                )
                item_id += 1
            oid += 1


def _seed_sessions(conn: sqlite3.Connection) -> None:
    channels = ["organic", "paid", "email", "direct"]
    sid = 1
    for cust_id in range(1, 501):
        n = random.randint(5, 60)
        for _ in range(n):
            session_date = str(fake.date_between(date(2023, 1, 1), date(2023, 12, 31)))
            conn.execute(
                "INSERT INTO sessions VALUES (?,?,?,?,?)",
                (sid, cust_id, session_date, random.randint(1, 120), random.choice(channels)),
            )
            sid += 1


def get_schema_str() -> str:
    return SCHEMA.strip()
