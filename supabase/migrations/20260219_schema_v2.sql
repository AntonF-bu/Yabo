-- ============================================================================
-- Schema V2: Clean normalized schema for Yabo
-- ============================================================================
-- Run this in the Supabase SQL Editor.
--
-- Creates 8 new tables alongside existing ones. Old tables are NOT dropped
-- until code migration (Checkpoint 4B) is verified.
--
-- Tables:
--   1. profiles_new     – center of everything, one row per user/trader
--   2. uploads          – every file that enters the system
--   3. trades_new       – normalized trade records, one row per trade
--   4. holdings         – reconstructed positions at a point in time
--   5. income           – dividends, interest, coupon payments
--   6. analysis_results – all computed analysis output
--   7. format_signatures– learned file formats for auto-detection
--   8. fees             – advisory fees, commissions, withholdings
-- ============================================================================


-- ─── TABLE 1: profiles_new ──────────────────────────────────────────────────
-- The center. One row per user/trader.

CREATE TABLE IF NOT EXISTS profiles_new (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  profile_id TEXT UNIQUE NOT NULL,   -- human-readable: D001, R010, etc.
  name TEXT,
  email TEXT,
  phone TEXT,
  brokerage TEXT,
  portfolio_size TEXT,
  experience TEXT,
  tax_jurisdiction TEXT,
  profile_completeness TEXT DEFAULT 'foundation',
  accounts JSONB,                    -- detected account structure
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE profiles_new ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_read_profiles" ON profiles_new
  FOR SELECT USING (true);
CREATE POLICY "anon_insert_profiles" ON profiles_new
  FOR INSERT WITH CHECK (true);
CREATE POLICY "anon_update_profiles" ON profiles_new
  FOR UPDATE USING (true);

CREATE INDEX idx_profiles_profile_id ON profiles_new(profile_id);


-- ─── TABLE 2: uploads ───────────────────────────────────────────────────────
-- Every file that enters the system. Raw storage reference.

CREATE TABLE IF NOT EXISTS uploads (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  profile_id TEXT NOT NULL REFERENCES profiles_new(profile_id),
  file_path TEXT NOT NULL,           -- path in Supabase Storage
  file_name TEXT NOT NULL,
  file_size_bytes INTEGER,
  classified_as TEXT,                -- trade_history | activity_export |
                                     -- holdings_snapshot | screenshot | unknown
  classification_method TEXT,        -- auto | claude_api | user_specified
  format_signature_id UUID,          -- FK to format_signatures if matched
  brokerage_detected TEXT,
  data_types_extracted TEXT[],       -- array: ['trades','holdings','income']
  status TEXT DEFAULT 'uploaded',
    -- uploaded → classifying → classified → processing → completed → error
  error_message TEXT,
  processing_started_at TIMESTAMPTZ,
  processing_completed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE uploads ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_read_uploads" ON uploads
  FOR SELECT USING (true);
CREATE POLICY "anon_insert_uploads" ON uploads
  FOR INSERT WITH CHECK (true);
CREATE POLICY "anon_update_uploads" ON uploads
  FOR UPDATE USING (true);

CREATE INDEX idx_uploads_profile ON uploads(profile_id);
CREATE INDEX idx_uploads_status ON uploads(status);


-- ─── TABLE 3: trades_new ────────────────────────────────────────────────────
-- Clean, normalized trade records. One row per trade.

CREATE TABLE IF NOT EXISTS trades_new (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  profile_id TEXT NOT NULL REFERENCES profiles_new(profile_id),
  upload_id UUID REFERENCES uploads(id),
  date DATE NOT NULL,
  account_id TEXT,                   -- *4416, *0356, etc.
  account_type TEXT,                 -- ira, taxable, business
  side TEXT NOT NULL,                -- buy, sell
  ticker TEXT,
  cusip TEXT,
  instrument_type TEXT,              -- equity, etf, option, muni_bond, etc.
  instrument_details JSONB,          -- strike, expiry, coupon, etc.
  quantity NUMERIC,
  price NUMERIC,
  amount NUMERIC,                    -- net with fees
  fees NUMERIC,
  description TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE trades_new ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_read_trades" ON trades_new
  FOR SELECT USING (true);
CREATE POLICY "anon_insert_trades" ON trades_new
  FOR INSERT WITH CHECK (true);

CREATE INDEX idx_trades_profile ON trades_new(profile_id);
CREATE INDEX idx_trades_upload ON trades_new(upload_id);
CREATE INDEX idx_trades_ticker ON trades_new(ticker);
CREATE INDEX idx_trades_date ON trades_new(date);


-- ─── TABLE 4: holdings ──────────────────────────────────────────────────────
-- Current positions. Snapshot at a point in time.

CREATE TABLE IF NOT EXISTS holdings (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  profile_id TEXT NOT NULL REFERENCES profiles_new(profile_id),
  upload_id UUID REFERENCES uploads(id),
  snapshot_date DATE,                -- when was this accurate
  account_id TEXT,
  account_type TEXT,
  ticker TEXT,
  cusip TEXT,
  instrument_type TEXT,
  instrument_details JSONB,
  quantity NUMERIC,
  cost_basis NUMERIC,
  market_value NUMERIC,
  unrealized_gain NUMERIC,
  unrealized_gain_pct NUMERIC,
  total_dividends NUMERIC,
  pre_existing BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE holdings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_read_holdings" ON holdings
  FOR SELECT USING (true);
CREATE POLICY "anon_insert_holdings" ON holdings
  FOR INSERT WITH CHECK (true);

CREATE INDEX idx_holdings_profile ON holdings(profile_id);
CREATE INDEX idx_holdings_upload ON holdings(upload_id);


-- ─── TABLE 5: income ────────────────────────────────────────────────────────
-- Dividend, interest, coupon payments.

CREATE TABLE IF NOT EXISTS income (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  profile_id TEXT NOT NULL REFERENCES profiles_new(profile_id),
  upload_id UUID REFERENCES uploads(id),
  date DATE NOT NULL,
  account_id TEXT,
  account_type TEXT,
  income_type TEXT,                  -- dividend, muni_interest,
                                     -- corporate_interest, money_market, reinvest
  ticker TEXT,
  cusip TEXT,
  issuer TEXT,
  amount NUMERIC,
  description TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE income ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_read_income" ON income
  FOR SELECT USING (true);
CREATE POLICY "anon_insert_income" ON income
  FOR INSERT WITH CHECK (true);

CREATE INDEX idx_income_profile ON income(profile_id);


-- ─── TABLE 6: analysis_results ──────────────────────────────────────────────
-- All computed analysis output. Behavioral, portfolio, combined.

CREATE TABLE IF NOT EXISTS analysis_results (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  profile_id TEXT NOT NULL REFERENCES profiles_new(profile_id),
  analysis_type TEXT NOT NULL,       -- behavioral | portfolio | combined
  version INTEGER DEFAULT 1,
  features JSONB,                    -- 212 behavioral features OR 60 portfolio features
  dimensions JSONB,                  -- 8-dimension classification (behavioral)
  narrative JSONB,                   -- Claude's interpretation
  summary_stats JSONB,               -- win_rate, profit_factor, etc.
  account_summaries JSONB,           -- per-account breakdowns (portfolio)
  status TEXT DEFAULT 'pending',
    -- pending → computing → narrating → completed → error
  error_message TEXT,
  model_used TEXT,                   -- claude-sonnet-4-20250514 etc.
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE analysis_results ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_read_analysis" ON analysis_results
  FOR SELECT USING (true);
CREATE POLICY "anon_insert_analysis" ON analysis_results
  FOR INSERT WITH CHECK (true);
CREATE POLICY "anon_update_analysis" ON analysis_results
  FOR UPDATE USING (true);

CREATE INDEX idx_analysis_profile ON analysis_results(profile_id);
CREATE INDEX idx_analysis_type ON analysis_results(analysis_type);


-- ─── TABLE 7: format_signatures ─────────────────────────────────────────────
-- Learned file formats. No Claude needed on second upload.

CREATE TABLE IF NOT EXISTS format_signatures (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  signature TEXT UNIQUE NOT NULL,    -- column hash or header pattern
  brokerage TEXT,                    -- wells_fargo | schwab | interactive_brokers
  format_name TEXT,                  -- 'Wells Fargo Activity Export'
  data_types TEXT[],                 -- ['trades','holdings','income','transfers']
  parser_config JSONB,               -- column mappings, skip rows, delimiters
  sample_headers TEXT[],             -- first row of column names for matching
  detection_rules JSONB,             -- rules for matching this format
  times_matched INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE format_signatures ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_read_formats" ON format_signatures
  FOR SELECT USING (true);
CREATE POLICY "anon_insert_formats" ON format_signatures
  FOR INSERT WITH CHECK (true);
CREATE POLICY "anon_update_formats" ON format_signatures
  FOR UPDATE USING (true);


-- ─── TABLE 8: fees ──────────────────────────────────────────────────────────
-- Advisory fees, commissions, withholdings.

CREATE TABLE IF NOT EXISTS fees (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  profile_id TEXT NOT NULL REFERENCES profiles_new(profile_id),
  upload_id UUID REFERENCES uploads(id),
  date DATE NOT NULL,
  account_id TEXT,
  fee_type TEXT,                     -- advisory, commission, withholding
  amount NUMERIC,
  description TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE fees ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_read_fees" ON fees
  FOR SELECT USING (true);
CREATE POLICY "anon_insert_fees" ON fees
  FOR INSERT WITH CHECK (true);

CREATE INDEX idx_fees_profile ON fees(profile_id);


-- ─── SEED: Wells Fargo Activity format signature ────────────────────────────

INSERT INTO format_signatures (
  signature, brokerage, format_name, data_types,
  parser_config, sample_headers, detection_rules
) VALUES (
  'wfa_activity_household',
  'wells_fargo',
  'Wells Fargo Advisors Activity Export',
  ARRAY['trades', 'holdings', 'income', 'fees', 'transfers'],
  '{"header_row": 11, "skip_rows_top": 10, "footer_detection": "empty_first_col_or_disclaimer", "amount_format": "dollar_parens_negative", "account_column": "Account", "date_format": "MM/DD/YYYY"}'::jsonb,
  ARRAY['Date', 'Account', 'Activity', 'Symbol', 'CUSIP', 'Description', 'Quantity', 'Price 1', 'Amount 2'],
  '{"header_contains": ["Account Activity For:"], "columns_contain": ["Activity", "CUSIP", "Price 1", "Amount 2"]}'::jsonb
)
ON CONFLICT (signature) DO NOTHING;


-- ============================================================================
-- NOTE: Old tables (trade_imports, portfolio_imports, extracted_trades,
-- positions, behavioral_profiles, import_screenshots, profiles, predictions,
-- prediction_votes, theses) are NOT dropped. They remain until Checkpoint 4B
-- code migration is verified. Drop them manually after.
-- ============================================================================
