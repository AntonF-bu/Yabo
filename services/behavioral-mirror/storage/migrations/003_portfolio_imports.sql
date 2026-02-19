-- Migration 003: Portfolio imports table for WFA activity analysis
-- Stores parsed brokerage data, reconstructed holdings, and Claude analysis

CREATE TABLE IF NOT EXISTS portfolio_imports (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    trader_id UUID REFERENCES traders(id),
    profile_id TEXT,
    source_type TEXT NOT NULL,
    source_file TEXT,
    raw_transactions JSONB,
    reconstructed_holdings JSONB,
    account_summaries JSONB,
    portfolio_analysis JSONB,
    accounts_detected JSONB,
    instrument_breakdown JSONB,
    status TEXT DEFAULT 'uploaded',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE portfolio_imports ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow anonymous read access"
    ON portfolio_imports FOR SELECT
    USING (true);

CREATE POLICY "Allow service role full access"
    ON portfolio_imports FOR ALL
    USING (true)
    WITH CHECK (true);

-- Add portfolio-related columns to traders table
ALTER TABLE traders
    ADD COLUMN IF NOT EXISTS profile_completeness TEXT DEFAULT 'foundation',
    ADD COLUMN IF NOT EXISTS tax_jurisdiction TEXT,
    ADD COLUMN IF NOT EXISTS accounts JSONB;

-- Index for quick lookups
CREATE INDEX IF NOT EXISTS idx_portfolio_imports_profile_id
    ON portfolio_imports(profile_id);

CREATE INDEX IF NOT EXISTS idx_portfolio_imports_trader_id
    ON portfolio_imports(trader_id);

CREATE INDEX IF NOT EXISTS idx_portfolio_imports_status
    ON portfolio_imports(status);
