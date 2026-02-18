-- Migration 002: Traders, trade imports, and screenshot extraction tables
-- Run against Supabase SQL editor manually

-- Traders table: who is uploading data
CREATE TABLE IF NOT EXISTS traders (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT,
    email TEXT,
    phone TEXT,
    brokerage TEXT,
    referred_by TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Trade imports: each upload session
CREATE TABLE IF NOT EXISTS trade_imports (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    trader_id UUID REFERENCES traders(id) ON DELETE CASCADE,
    source_type TEXT CHECK (source_type IN ('csv', 'screenshots', 'manual', 'screenshot_analyzed')),
    brokerage_detected TEXT,
    status TEXT DEFAULT 'pending_review' CHECK (status IN ('pending_review', 'approved', 'processed', 'failed')),
    trade_count INTEGER,
    date_range_start DATE,
    date_range_end DATE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);

-- Import screenshots: raw images from screenshot imports
CREATE TABLE IF NOT EXISTS import_screenshots (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    import_id UUID REFERENCES trade_imports(id) ON DELETE CASCADE,
    storage_path TEXT NOT NULL,
    extraction_raw JSONB,
    extraction_status TEXT DEFAULT 'pending' CHECK (extraction_status IN ('pending', 'extracted', 'failed')),
    trades_extracted INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Extracted trades: individual trades from any source
CREATE TABLE IF NOT EXISTS extracted_trades (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    import_id UUID REFERENCES trade_imports(id) ON DELETE CASCADE,
    trader_id UUID REFERENCES traders(id) ON DELETE CASCADE,
    trade_date DATE NOT NULL,
    ticker TEXT NOT NULL,
    side TEXT CHECK (side IN ('BUY', 'SELL')),
    quantity NUMERIC,
    price NUMERIC,
    total NUMERIC,
    currency TEXT DEFAULT 'USD',
    confidence TEXT DEFAULT 'high' CHECK (confidence IN ('high', 'medium', 'low')),
    manually_reviewed BOOLEAN DEFAULT FALSE,
    source_screenshot_index INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Link behavioral profiles to traders
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'behavioral_profiles' AND column_name = 'trader_id'
    ) THEN
        ALTER TABLE behavioral_profiles ADD COLUMN trader_id UUID REFERENCES traders(id) ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_behavioral_profiles_trader ON behavioral_profiles (trader_id) WHERE trader_id IS NOT NULL;

-- Enable RLS on all new tables
ALTER TABLE traders ENABLE ROW LEVEL SECURITY;
ALTER TABLE trade_imports ENABLE ROW LEVEL SECURITY;
ALTER TABLE import_screenshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE extracted_trades ENABLE ROW LEVEL SECURITY;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_trade_imports_trader ON trade_imports (trader_id);
CREATE INDEX IF NOT EXISTS idx_trade_imports_status ON trade_imports (status);
CREATE INDEX IF NOT EXISTS idx_extracted_trades_import ON extracted_trades (import_id);
CREATE INDEX IF NOT EXISTS idx_extracted_trades_trader ON extracted_trades (trader_id);
CREATE INDEX IF NOT EXISTS idx_import_screenshots_import ON import_screenshots (import_id);
