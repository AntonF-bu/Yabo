-- Yabo Database Schema
-- Run this in the Supabase SQL Editor (supabase.com > project > SQL Editor)

-- Users profile (extends Clerk user data with Yabo-specific fields)
CREATE TABLE IF NOT EXISTS profiles (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  clerk_id TEXT UNIQUE NOT NULL,
  username TEXT UNIQUE,
  display_name TEXT,

  -- Quiz results
  trader_type TEXT,
  sectors TEXT[] DEFAULT '{}',
  risk_tolerance TEXT,
  experience_level TEXT,
  scenario_choice TEXT,

  -- Computed from quiz (preliminary) then updated from real trades
  archetype TEXT,
  tier TEXT DEFAULT 'Rookie',
  rank_score INTEGER DEFAULT 0,
  level INTEGER DEFAULT 1,
  xp INTEGER DEFAULT 0,
  streak INTEGER DEFAULT 0,

  -- Portfolio
  starting_capital NUMERIC DEFAULT 100000,
  current_value NUMERIC DEFAULT 100000,

  -- Behavioral traits (0-100, preliminary from quiz, updated by AI later)
  trait_entry_timing INTEGER DEFAULT 50,
  trait_hold_discipline INTEGER DEFAULT 50,
  trait_position_sizing INTEGER DEFAULT 50,
  trait_conviction_accuracy INTEGER DEFAULT 50,
  trait_risk_management INTEGER DEFAULT 50,
  trait_sector_focus INTEGER DEFAULT 50,
  trait_drawdown_resilience INTEGER DEFAULT 50,
  trait_thesis_quality INTEGER DEFAULT 50,

  onboarding_complete BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Trades (immutable log)
CREATE TABLE IF NOT EXISTS trades (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  clerk_id TEXT NOT NULL REFERENCES profiles(clerk_id),
  ticker TEXT NOT NULL,
  side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
  quantity NUMERIC NOT NULL,
  price NUMERIC NOT NULL,
  total_value NUMERIC,
  fees NUMERIC DEFAULT 0,
  sector TEXT,
  source TEXT DEFAULT 'manual',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  locked_at TIMESTAMPTZ DEFAULT NOW()
);

-- Positions (current holdings, derived from trades)
CREATE TABLE IF NOT EXISTS positions (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  clerk_id TEXT NOT NULL REFERENCES profiles(clerk_id),
  ticker TEXT NOT NULL,
  shares NUMERIC NOT NULL DEFAULT 0,
  avg_cost NUMERIC NOT NULL DEFAULT 0,
  current_price NUMERIC,
  sector TEXT,
  conviction INTEGER,
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(clerk_id, ticker)
);

-- Theses (posted to The Room)
CREATE TABLE IF NOT EXISTS theses (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  clerk_id TEXT NOT NULL REFERENCES profiles(clerk_id),
  ticker TEXT NOT NULL,
  direction TEXT NOT NULL CHECK (direction IN ('long', 'short')),
  entry_price NUMERIC,
  target_price NUMERIC,
  stop_price NUMERIC,
  conviction INTEGER CHECK (conviction >= 0 AND conviction <= 100),
  body TEXT NOT NULL,
  ai_signal_score INTEGER,
  ai_signal_reasoning TEXT,
  thesis_quality_score INTEGER,
  status TEXT DEFAULT 'active',
  yes_votes INTEGER DEFAULT 0,
  no_votes INTEGER DEFAULT 0,
  reply_count INTEGER DEFAULT 0,
  rep_count INTEGER DEFAULT 0,
  expires_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Predictions
CREATE TABLE IF NOT EXISTS predictions (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  question TEXT NOT NULL,
  category TEXT,
  yes_probability NUMERIC DEFAULT 0.5,
  total_votes INTEGER DEFAULT 0,
  hot BOOLEAN DEFAULT FALSE,
  resolves_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- User prediction votes
CREATE TABLE IF NOT EXISTS prediction_votes (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  clerk_id TEXT NOT NULL,
  prediction_id UUID NOT NULL REFERENCES predictions(id),
  vote TEXT NOT NULL CHECK (vote IN ('yes', 'no')),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(clerk_id, prediction_id)
);

-- Enable Row Level Security on all tables
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE theses ENABLE ROW LEVEL SECURITY;
ALTER TABLE predictions ENABLE ROW LEVEL SECURITY;
ALTER TABLE prediction_votes ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY "Public profiles are viewable by everyone" ON profiles FOR SELECT USING (true);
CREATE POLICY "Users can insert their own profile" ON profiles FOR INSERT WITH CHECK (true);
CREATE POLICY "Users can update their own profile" ON profiles FOR UPDATE USING (true);

CREATE POLICY "Trades are viewable by everyone" ON trades FOR SELECT USING (true);
CREATE POLICY "Users can insert their own trades" ON trades FOR INSERT WITH CHECK (true);

CREATE POLICY "Positions are viewable by everyone" ON positions FOR SELECT USING (true);
CREATE POLICY "Users can manage their own positions" ON positions FOR INSERT WITH CHECK (true);
CREATE POLICY "Users can update their own positions" ON positions FOR UPDATE USING (true);

CREATE POLICY "Theses are viewable by everyone" ON theses FOR SELECT USING (true);
CREATE POLICY "Users can insert their own theses" ON theses FOR INSERT WITH CHECK (true);

CREATE POLICY "Predictions are viewable by everyone" ON predictions FOR SELECT USING (true);
CREATE POLICY "Anyone can create predictions" ON predictions FOR INSERT WITH CHECK (true);

CREATE POLICY "Votes are viewable by everyone" ON prediction_votes FOR SELECT USING (true);
CREATE POLICY "Users can insert votes" ON prediction_votes FOR INSERT WITH CHECK (true);
