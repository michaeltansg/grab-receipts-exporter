-- Create grab_receipts table
-- Matches CSV schema: uid, date, type, order_id, currency, total_amount, metadata

CREATE TABLE IF NOT EXISTS grab_receipts (
    uid INTEGER PRIMARY KEY,
    date TIMESTAMPTZ NOT NULL,
    type VARCHAR(20) NOT NULL CHECK (type IN ('GrabFood', 'GrabTransport', 'GrabTip', 'Unknown')),
    order_id VARCHAR(20),
    currency VARCHAR(3) NOT NULL DEFAULT 'THB',
    total_amount DECIMAL(10, 2) NOT NULL,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for common queries
CREATE INDEX IF NOT EXISTS idx_grab_receipts_date ON grab_receipts(date);
CREATE INDEX IF NOT EXISTS idx_grab_receipts_type ON grab_receipts(type);
CREATE INDEX IF NOT EXISTS idx_grab_receipts_order_id ON grab_receipts(order_id);

-- GIN index for JSONB metadata queries
CREATE INDEX IF NOT EXISTS idx_grab_receipts_metadata ON grab_receipts USING GIN (metadata);

COMMENT ON TABLE grab_receipts IS 'Grab receipt data exported from iCloud Mail';
COMMENT ON COLUMN grab_receipts.uid IS 'Email UID from IMAP server';
COMMENT ON COLUMN grab_receipts.date IS 'Receipt/email date';
COMMENT ON COLUMN grab_receipts.type IS 'Service type: GrabFood, GrabTransport, GrabTip, or Unknown';
COMMENT ON COLUMN grab_receipts.order_id IS 'Grab order ID (e.g., A-7PPCC7TGW4P8AV)';
COMMENT ON COLUMN grab_receipts.currency IS 'Currency code (THB)';
COMMENT ON COLUMN grab_receipts.total_amount IS 'Total amount charged';
COMMENT ON COLUMN grab_receipts.metadata IS 'Service-specific metadata as JSON';
