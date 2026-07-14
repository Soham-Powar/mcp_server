-- UPI Analytics — SQLite schema
-- Single source of truth for the transactions table.

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id       TEXT PRIMARY KEY,
    timestamp            DATETIME NOT NULL,
    payer_vpa            TEXT NOT NULL,
    payee_vpa            TEXT NOT NULL,
    payer_bank           TEXT,
    payee_bank           TEXT,
    amount               REAL NOT NULL,
    transaction_type     TEXT,      -- DEBIT | CREDIT
    transaction_category TEXT,      -- Shopping, Food, Bills, ...
    status               TEXT,      -- SUCCESS | FAILED | PENDING
    payment_app          TEXT,      -- GPay, PhonePe, Paytm, ...
    device_type          TEXT,      -- Android | iOS | Web
    location             TEXT,      -- City
    remarks              TEXT
);

-- Indexes to keep analytics tools fast on larger datasets.
CREATE INDEX IF NOT EXISTS idx_txn_timestamp ON transactions (timestamp);
CREATE INDEX IF NOT EXISTS idx_txn_category  ON transactions (transaction_category);
CREATE INDEX IF NOT EXISTS idx_txn_status    ON transactions (status);
CREATE INDEX IF NOT EXISTS idx_txn_location  ON transactions (location);
CREATE INDEX IF NOT EXISTS idx_txn_payee     ON transactions (payee_vpa);
