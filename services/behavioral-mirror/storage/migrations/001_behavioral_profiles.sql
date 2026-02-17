-- Behavioral Mirror: real user profile storage
-- Run this in your Supabase SQL editor (or via supabase db push)

-- ─── Table ──────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS behavioral_profiles (
    id              TEXT PRIMARY KEY,                    -- R001, R002, ...
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    source          TEXT DEFAULT 'real',                 -- 'real' or 'synthetic'
    csv_format      TEXT,                                -- e.g. 'robinhood', 'schwab'
    trade_count     INTEGER,
    unique_tickers  INTEGER,
    date_range_start DATE,
    date_range_end  DATE,
    confidence_tier TEXT,                                -- 'high', 'medium', 'low', 'insufficient'
    top_archetype   TEXT,                                -- dominant archetype label
    features        JSONB NOT NULL DEFAULT '{}'::jsonb,  -- full extracted feature profile
    classification  JSONB DEFAULT '{}'::jsonb,           -- archetype scores from traits
    holdings_profile JSONB DEFAULT '{}'::jsonb,          -- market cap, sector, risk data
    metadata        JSONB DEFAULT '{}'::jsonb,           -- portfolio value estimates, etc.
    user_id         UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    deleted_at      TIMESTAMPTZ                         -- soft delete (NULL = active)
);

-- ─── Indexes ────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_behavioral_profiles_source
    ON behavioral_profiles (source);

CREATE INDEX IF NOT EXISTS idx_behavioral_profiles_deleted_at
    ON behavioral_profiles (deleted_at)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_behavioral_profiles_created_at
    ON behavioral_profiles (created_at);

CREATE INDEX IF NOT EXISTS idx_behavioral_profiles_user_id
    ON behavioral_profiles (user_id)
    WHERE user_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_behavioral_profiles_top_archetype
    ON behavioral_profiles (top_archetype);

-- ─── RLS (Row Level Security) ───────────────────────────────────────────────
-- The backend uses service_role key which bypasses RLS.
-- These policies protect the table if accessed via the anon/authenticated key.

ALTER TABLE behavioral_profiles ENABLE ROW LEVEL SECURITY;

-- Users can read their own profiles
CREATE POLICY "Users can read own profiles"
    ON behavioral_profiles
    FOR SELECT
    USING (auth.uid() = user_id);

-- Only service role can insert/update/delete (backend handles all writes)
-- No additional policies needed — service_role bypasses RLS
