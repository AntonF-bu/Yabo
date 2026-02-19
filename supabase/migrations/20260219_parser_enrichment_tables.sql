-- Parser enrichment configuration tables
-- Created: 2026-02-19
-- These tables store rules and thresholds for the parsing pipeline
-- so that classification logic can be tuned from Supabase, not code.

-- ═══════════════════════════════════════════════════════════════
-- Table 1: Option strategy detection rules
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS option_strategy_rules (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  strategy_key VARCHAR(30) NOT NULL UNIQUE,
  strategy_name VARCHAR(50) NOT NULL,
  description TEXT,
  detection_rules JSONB NOT NULL,
  complexity_score INT DEFAULT 1,
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE option_strategy_rules IS
  'Option strategy definitions for the parsing pipeline. '
  'Each rule maps an action+context to a named strategy. '
  'Add rows to support new strategies — no code change needed.';

INSERT INTO option_strategy_rules (strategy_key, strategy_name, description, detection_rules, complexity_score) VALUES
  ('covered_call', 'Covered Call',
   'Selling calls against long equity in the same account',
   '{"action": "sell_call", "requires": "long_equity_in_same_account", "min_shares": "contracts * 100", "partial_handling": "classify_excess_as_naked"}',
   1),
  ('cash_secured_put', 'Cash-Secured Put',
   'Selling puts with sufficient cash to cover assignment',
   '{"action": "sell_put", "requires": "sufficient_cash_in_account", "min_cash": "contracts * 100 * strike"}',
   1),
  ('protective_put', 'Protective Put',
   'Buying puts to protect a long equity position',
   '{"action": "buy_put", "requires": "long_equity_in_same_account"}',
   1),
  ('call_spread', 'Call Spread',
   'Selling a call while holding a higher-strike call (same underlying, same expiry)',
   '{"action": "sell_call", "requires": "long_call_same_underlying_same_expiry_higher_strike"}',
   2),
  ('put_spread', 'Put Spread',
   'Selling a put while holding a lower-strike put (same underlying, same expiry)',
   '{"action": "sell_put", "requires": "long_put_same_underlying_same_expiry_lower_strike"}',
   2),
  ('calendar_spread', 'Calendar Spread',
   'Selling a near-term option while holding a later-expiry option (same strike)',
   '{"action": "sell_call_or_put", "requires": "long_same_type_same_strike_later_expiry"}',
   2),
  ('naked_call', 'Naked Call',
   'Selling calls without holding the underlying or a covering long call',
   '{"action": "sell_call", "requires": "no_equity_no_long_call"}',
   3),
  ('naked_put', 'Naked Put',
   'Selling puts without sufficient cash or short equity',
   '{"action": "sell_put", "requires": "insufficient_cash_no_short_equity"}',
   2),
  ('leaps', 'LEAPS',
   'Long-term option contracts with more than 365 days to expiry',
   '{"action": "buy_call_or_put", "requires": "dte_greater_than_365"}',
   1)
ON CONFLICT (strategy_key) DO NOTHING;


-- ═══════════════════════════════════════════════════════════════
-- Table 2: Brokerage-specific format rules
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS brokerage_format_rules (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  brokerage VARCHAR(30) NOT NULL,
  rule_key VARCHAR(50) NOT NULL,
  rule_description TEXT,
  rule_logic JSONB NOT NULL,
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(brokerage, rule_key)
);

COMMENT ON TABLE brokerage_format_rules IS
  'Brokerage-specific CSV formatting quirks. '
  'Each brokerage has its own conventions for negative quantities, '
  'dollar formatting, etc. Add rows for new brokerages.';

INSERT INTO brokerage_format_rules (brokerage, rule_key, rule_description, rule_logic) VALUES
  ('wells_fargo_advisors', 'negative_qty_buy_is_close',
   'WFA Buy with negative quantity means closing a short position (e.g. buying to close a short option)',
   '{"condition": "action=Buy AND quantity<0", "interpretation": "closing_short_position", "confidence": 0.95}'),
  ('wells_fargo_advisors', 'negative_qty_sell_is_normal',
   'WFA Sell always shows negative quantity for equity sells — this is normal format, not a short sale',
   '{"condition": "action=Sell AND quantity<0 AND instrument=equity", "interpretation": "normal_sell_not_short", "confidence": 0.90}')
ON CONFLICT (brokerage, rule_key) DO NOTHING;


-- ═══════════════════════════════════════════════════════════════
-- Table 3: Completeness signal types
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS completeness_signal_types (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  signal_key VARCHAR(40) NOT NULL UNIQUE,
  signal_name VARCHAR(60) NOT NULL,
  description TEXT,
  detection_logic TEXT,
  weight FLOAT DEFAULT 1.0,
  is_active BOOLEAN DEFAULT TRUE
);

COMMENT ON TABLE completeness_signal_types IS
  'Signal types for portfolio data completeness assessment. '
  'Each signal indicates evidence that more data exists than was uploaded.';

INSERT INTO completeness_signal_types (signal_key, signal_name, description, detection_logic, weight) VALUES
  ('dividend_no_buy', 'Dividend from untraded position',
   'Dividends received for a ticker with no buy in the CSV window — indicates a pre-existing position',
   'For each dividend transaction, check if the ticker appears in any buy transaction. If not, the position existed before the export window.',
   1.0),
  ('interest_no_buy', 'Interest from untraded bond',
   'Bond interest for a CUSIP not purchased in the CSV window — indicates a pre-existing bond position',
   'For each interest transaction on a CUSIP, check if that CUSIP was purchased. If not, the bond was held before the export.',
   1.0),
  ('option_no_underlying', 'Options on unseen underlying',
   'Option activity on an underlying equity not visible in the position tracker',
   'Extract the underlying from option symbols and check if it was ever bought or sold. Missing underlying = invisible position.',
   0.8),
  ('advisory_fee_implies_aum', 'Advisory fee implies larger AUM',
   'Advisory fee proportional to a larger AUM than what we can reconstruct from trades',
   'Typical advisory fee is ~1% annually (0.25% quarterly). Fee / 0.0025 = implied quarterly AUM. If implied AUM > 1.5x reconstructed value, flag.',
   1.5),
  ('wire_transfer', 'Wire / external transfer',
   'Wire or ACH transfer suggesting external holdings or income sources',
   'Detect transfers with wire/ACH keywords. Large inflows may indicate income or positions at other institutions.',
   0.5),
  ('inter_account_transfer', 'Inter-account transfer',
   'Position transferred between accounts — existed before the CSV window',
   'Journal entries and internal transfers indicate positions that were already held.',
   0.7)
ON CONFLICT (signal_key) DO NOTHING;
