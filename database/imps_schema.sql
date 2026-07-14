-- IMPS Analytics — SQLite schema
-- IMPS (Immediate Payment Service) is bank-account-to-account transfer, so the
-- model centers on remitter/beneficiary accounts, IFSC, channel and purpose —
-- distinct from the UPI VPA/merchant model.

CREATE TABLE IF NOT EXISTS transfers (
    transaction_id       TEXT PRIMARY KEY,
    timestamp            DATETIME NOT NULL,
    remitter_name        TEXT,
    remitter_account     TEXT NOT NULL,   -- masked, e.g. XXXXXX4321
    remitter_ifsc        TEXT,
    remitter_bank        TEXT,
    beneficiary_name     TEXT,
    beneficiary_account  TEXT NOT NULL,   -- masked
    beneficiary_ifsc     TEXT,
    beneficiary_bank     TEXT,
    amount               REAL NOT NULL,
    transfer_mode        TEXT,            -- P2A (account+IFSC) | P2P (MMID+mobile)
    channel              TEXT,            -- Mobile Banking, Internet Banking, Branch, ATM, USSD
    status               TEXT,            -- SUCCESS | FAILED | PENDING
    purpose              TEXT,            -- Rent, Salary, Loan Repayment, ...
    rrn                  TEXT,            -- 12-digit Retrieval Reference Number
    remarks              TEXT
);

-- Indexes matching the columns the analytics tools filter/group by.
CREATE INDEX IF NOT EXISTS idx_imps_timestamp   ON transfers (timestamp);
CREATE INDEX IF NOT EXISTS idx_imps_status      ON transfers (status);
CREATE INDEX IF NOT EXISTS idx_imps_channel     ON transfers (channel);
CREATE INDEX IF NOT EXISTS idx_imps_purpose     ON transfers (purpose);
CREATE INDEX IF NOT EXISTS idx_imps_mode        ON transfers (transfer_mode);
CREATE INDEX IF NOT EXISTS idx_imps_beneficiary ON transfers (beneficiary_account);
