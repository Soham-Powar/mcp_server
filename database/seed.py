"""Seed the SQLite database with realistic sample UPI transactions.

Usage:
    python database/seed.py                 # creates ./database/upi.db
    python database/seed.py --rows 5000     # custom row count
    python database/seed.py --db ./upi.db   # custom path

Idempotent: drops and recreates the transactions table each run.
"""
from __future__ import annotations

import argparse
import os
import random
import sqlite3
import uuid
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = os.path.join(HERE, "upi.db")
SCHEMA_PATH = os.path.join(HERE, "schema.sql")

BANKS = ["HDFC", "SBI", "ICICI", "Axis", "Kotak", "PNB", "Yes Bank", "IDFC"]
PAYMENT_APPS = ["GPay", "PhonePe", "Paytm", "BHIM", "Amazon Pay", "CRED"]
DEVICE_TYPES = ["Android", "iOS", "Web"]
LOCATIONS = [
    "Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Chennai",
    "Pune", "Kolkata", "Ahmedabad", "Jaipur", "Surat",
]
STATUSES = (["SUCCESS"] * 88) + (["FAILED"] * 9) + (["PENDING"] * 3)

# category -> list of (merchant_name, vpa_handle, typical amount range)
MERCHANTS = {
    "Shopping": [
        ("Amazon", "amazon@apl", (299, 8000)),
        ("Flipkart", "flipkart@icici", (199, 6500)),
        ("Myntra", "myntra@ybl", (499, 4000)),
        ("Reliance Trends", "trends@hdfcbank", (600, 3500)),
    ],
    "Food": [
        ("Swiggy", "swiggy@ybl", (120, 900)),
        ("Zomato", "zomato@paytm", (150, 1100)),
        ("Dominos", "dominos@hdfcbank", (300, 1200)),
        ("Starbucks", "starbucks@icici", (250, 800)),
    ],
    "Groceries": [
        ("BigBasket", "bigbasket@sbi", (400, 3000)),
        ("Blinkit", "blinkit@ybl", (150, 1500)),
        ("Zepto", "zepto@axis", (100, 1200)),
    ],
    "Bills": [
        ("Airtel", "airtel@hdfcbank", (199, 1499)),
        ("Tata Power", "tatapower@icici", (500, 4000)),
        ("Jio", "jio@paytm", (239, 1199)),
    ],
    "Transport": [
        ("Uber", "uber@axis", (80, 700)),
        ("Ola", "ola@ybl", (70, 650)),
        ("IRCTC", "irctc@sbi", (200, 2500)),
    ],
    "Entertainment": [
        ("Netflix", "netflix@hdfcbank", (199, 649)),
        ("BookMyShow", "bookmyshow@icici", (200, 1500)),
        ("Spotify", "spotify@ybl", (119, 179)),
    ],
    "Transfer": [
        ("Rahul Sharma", "rahul.sharma@oksbi", (100, 15000)),
        ("Priya Patel", "priya.patel@okhdfcbank", (100, 12000)),
        ("Amit Kumar", "amit.kumar@okaxis", (100, 20000)),
    ],
    "Health": [
        ("PharmEasy", "pharmeasy@icici", (150, 2500)),
        ("Apollo", "apollo@hdfcbank", (300, 5000)),
    ],
}

PAYER_VPAS = [
    "user.alpha@okhdfcbank", "user.beta@oksbi", "user.gamma@okicici",
]

REMARK_TEMPLATES = [
    "", "", "", "Payment for {m}", "{m} order", "Monthly {m}",
    "Split bill", "Thanks!", "Refund adjust",
]


def build_row(now: datetime) -> tuple:
    category = random.choice(list(MERCHANTS.keys()))
    merchant, payee_vpa, (lo, hi) = random.choice(MERCHANTS[category])
    amount = round(random.uniform(lo, hi), 2)
    # Weight timestamps toward the last 6 months, some older.
    days_back = int(random.triangular(0, 365, 20))
    ts = now - timedelta(
        days=days_back,
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59),
    )
    payer_vpa = random.choice(PAYER_VPAS)
    status = random.choice(STATUSES)
    remark = random.choice(REMARK_TEMPLATES).format(m=merchant)
    txn_type = "CREDIT" if category == "Transfer" and random.random() < 0.3 else "DEBIT"
    return (
        f"TXN{''.join(random.choices('0123456789ABCDEF', k=16))}",
        ts.strftime("%Y-%m-%d %H:%M:%S"),
        payer_vpa,
        payee_vpa,
        random.choice(BANKS),
        random.choice(BANKS),
        amount,
        txn_type,
        category,
        status,
        random.choice(PAYMENT_APPS),
        random.choice(DEVICE_TYPES),
        random.choice(LOCATIONS),
        remark,
    )


def seed(db_path: str, rows: int, seed_value: int = 42) -> None:
    random.seed(seed_value)
    now = datetime.now()

    with open(SCHEMA_PATH, "r", encoding="utf-8") as fh:
        schema_sql = fh.read()

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.executescript(schema_sql)
        batch = [build_row(now) for _ in range(rows)]
        cur.executemany(
            """
            INSERT OR IGNORE INTO transactions (
                transaction_id, timestamp, payer_vpa, payee_vpa,
                payer_bank, payee_bank, amount, transaction_type,
                transaction_category, status, payment_app,
                device_type, location, remarks
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            batch,
        )
        conn.commit()
        count = cur.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        print(f"Seeded {count} transactions into {db_path}")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed UPI sample data")
    parser.add_argument("--db", default=DEFAULT_DB, help="SQLite file path")
    parser.add_argument("--rows", type=int, default=2000, help="Number of rows")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed")
    args = parser.parse_args()
    seed(args.db, args.rows, args.seed)


if __name__ == "__main__":
    main()
