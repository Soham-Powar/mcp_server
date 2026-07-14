"""Seed the SQLite database with realistic sample IMPS transfers.

Usage:
    python database/imps_seed.py                 # creates ./database/imps.db
    python database/imps_seed.py --rows 3000
    python database/imps_seed.py --db ./imps.db

Mirrors database/seed.py (UPI) but for the account-to-account IMPS model.
Idempotent: drops and recreates the transfers table each run.
"""
from __future__ import annotations

import argparse
import os
import random
import sqlite3
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = os.path.join(HERE, "imps.db")
SCHEMA_PATH = os.path.join(HERE, "imps_schema.sql")

BANKS = [
    ("HDFC Bank", "HDFC"), ("State Bank of India", "SBIN"),
    ("ICICI Bank", "ICIC"), ("Axis Bank", "UTIB"),
    ("Kotak Mahindra", "KKBK"), ("Punjab National Bank", "PUNB"),
    ("Yes Bank", "YESB"), ("IDFC First", "IDFB"),
]
CHANNELS = (
    ["Mobile Banking"] * 50 + ["Internet Banking"] * 30
    + ["Branch"] * 10 + ["ATM"] * 5 + ["USSD"] * 5
)
STATUSES = (["SUCCESS"] * 90) + (["FAILED"] * 7) + (["PENDING"] * 3)

# purpose -> (typical amount range)
PURPOSES = {
    "Rent": (6000, 45000),
    "Salary": (18000, 120000),
    "Loan Repayment": (2500, 60000),
    "Family Support": (1000, 40000),
    "Investment": (5000, 200000),
    "Vendor Payment": (2000, 150000),
    "Education Fees": (5000, 90000),
    "Refund": (200, 15000),
}

BENEFICIARIES = [
    "Rahul Sharma", "Priya Patel", "Amit Kumar", "Sneha Reddy",
    "Vikram Singh", "Anjali Gupta", "Rohit Mehta", "Kavya Nair",
    "Sunrise Realty", "Acme Traders", "Global Tuitions", "Nova Mutual Fund",
    "Bharat Finance", "Sterling Vendors",
]

REMARKS = ["", "", "", "Monthly {p}", "{p} transfer", "Ref {rrn}", "Urgent", "Thanks"]

SOURCE_ACCOUNTS = ["XXXXXX4321", "XXXXXX9087", "XXXXXX1102"]


def _acct() -> str:
    return "XXXXXX" + f"{random.randint(0, 9999):04d}"


def _rrn() -> str:
    return f"{random.randint(0, 999999999999):012d}"


def build_row(now: datetime) -> tuple:
    purpose = random.choice(list(PURPOSES.keys()))
    lo, hi = PURPOSES[purpose]
    amount = round(random.uniform(lo, hi), 2)
    days_back = int(random.triangular(0, 365, 20))
    ts = now - timedelta(
        days=days_back,
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59),
    )
    r_bank, r_pfx = random.choice(BANKS)
    b_bank, b_pfx = random.choice(BANKS)
    mode = "P2P" if random.random() < 0.15 else "P2A"
    rrn = _rrn()
    remark = random.choice(REMARKS).format(p=purpose, rrn=rrn)
    return (
        f"IMPS{rrn}",
        ts.strftime("%Y-%m-%d %H:%M:%S"),
        "Primary Account Holder",
        random.choice(SOURCE_ACCOUNTS),
        f"{r_pfx}0{random.randint(100000, 999999)}",
        r_bank,
        random.choice(BENEFICIARIES),
        _acct(),
        f"{b_pfx}0{random.randint(100000, 999999)}",
        b_bank,
        amount,
        mode,
        random.choice(CHANNELS),
        random.choice(STATUSES),
        purpose,
        rrn,
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
            INSERT OR IGNORE INTO transfers (
                transaction_id, timestamp, remitter_name, remitter_account,
                remitter_ifsc, remitter_bank, beneficiary_name,
                beneficiary_account, beneficiary_ifsc, beneficiary_bank,
                amount, transfer_mode, channel, status, purpose, rrn, remarks
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            batch,
        )
        conn.commit()
        count = cur.execute("SELECT COUNT(*) FROM transfers").fetchone()[0]
        print(f"Seeded {count} IMPS transfers into {db_path}")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed IMPS sample data")
    parser.add_argument("--db", default=DEFAULT_DB, help="SQLite file path")
    parser.add_argument("--rows", type=int, default=1500, help="Number of rows")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed")
    args = parser.parse_args()
    seed(args.db, args.rows, args.seed)


if __name__ == "__main__":
    main()
