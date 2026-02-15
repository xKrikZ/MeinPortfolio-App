CREATE TABLE IF NOT EXISTS dividend (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    payment_date DATE NOT NULL,
    amount REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'EUR',
    tax_withheld REAL DEFAULT 0,
    dividend_type TEXT DEFAULT 'regular',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (asset_id) REFERENCES asset(id) ON DELETE CASCADE,
    UNIQUE(asset_id, payment_date)
);

CREATE INDEX IF NOT EXISTS idx_dividend_asset ON dividend(asset_id);
CREATE INDEX IF NOT EXISTS idx_dividend_date ON dividend(payment_date);

CREATE TABLE IF NOT EXISTS price_alert (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    alert_type TEXT NOT NULL,
    threshold_value REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'EUR',
    active INTEGER DEFAULT 1,
    triggered INTEGER DEFAULT 0,
    triggered_at TIMESTAMP,
    notification_sent INTEGER DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (asset_id) REFERENCES asset(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_price_alert_asset ON price_alert(asset_id);
CREATE INDEX IF NOT EXISTS idx_price_alert_active ON price_alert(active, triggered);
