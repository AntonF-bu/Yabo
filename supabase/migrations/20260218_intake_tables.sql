-- Traders: people who submit data via the intake form
CREATE TABLE IF NOT EXISTS traders (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT,
    brokerage TEXT,
    referred_by TEXT,
    status TEXT DEFAULT 'pending',  -- pending, profiled, contacted
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Trade imports: each upload (CSV or screenshots)
CREATE TABLE IF NOT EXISTS trade_imports (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    trader_id UUID REFERENCES traders(id),
    source_type TEXT NOT NULL,  -- csv, screenshots, manual
    brokerage_detected TEXT,
    raw_result JSONB,
    status TEXT DEFAULT 'pending_review' CHECK (status IN ('pending_review', 'approved', 'processed', 'failed')),
    trade_count INTEGER DEFAULT 0,
    profile_id TEXT,  -- links to behavioral_profiles
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_traders_email ON traders(email);
CREATE INDEX IF NOT EXISTS idx_traders_status ON traders(status);
CREATE INDEX IF NOT EXISTS idx_trade_imports_trader_id ON trade_imports(trader_id);
CREATE INDEX IF NOT EXISTS idx_trade_imports_status ON trade_imports(status);

-- Enable RLS
ALTER TABLE traders ENABLE ROW LEVEL SECURITY;
ALTER TABLE trade_imports ENABLE ROW LEVEL SECURITY;

-- Allow anonymous inserts from the intake form (uses anon key)
CREATE POLICY "Allow anonymous inserts on traders" ON traders
    FOR INSERT TO anon WITH CHECK (true);

CREATE POLICY "Allow anonymous inserts on trade_imports" ON trade_imports
    FOR INSERT TO anon WITH CHECK (true);

-- Allow service role full access
CREATE POLICY "Service role full access on traders" ON traders
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "Service role full access on trade_imports" ON trade_imports
    FOR ALL TO service_role USING (true) WITH CHECK (true);
