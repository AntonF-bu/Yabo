-- Holdings feature extractor configuration
-- Created: 2026-02-20
-- Thresholds and weights for the 69 holdings features (h_ prefix).

-- Strategy complexity weights for h_strategy_complexity_score
INSERT INTO analysis_config (key, value, description) VALUES
  ('h_strategy_complexity_weights',
   '{"covered_call":1,"protective_put":2,"spread":3,"calendar_spread":3,"leaps":2,"structured_product":4,"muni_bond":2,"multi_account_coordination":3}',
   'Complexity weight per strategy type for h_strategy_complexity_score'),
  ('h_stress_test_default_beta', '1.0',
   'Default beta when MarketDataService cannot resolve ticker beta'),
  ('h_stress_test_decline_pct', '0.20',
   'Market decline percentage for h_stress_test_20pct'),
  ('h_correlation_high_sector_threshold', '0.50',
   'If >50% in one sector, correlation estimate is high'),
  ('h_tax_placement_high_yield_threshold', '0.03',
   'Dividend yield above this is considered tax-inefficient'),
  ('h_fee_drag_advisory_annualize_factor', '4.0',
   'Multiply quarterly advisory fees by this to annualize'),
  ('h_income_engineering_max_sources', '5',
   'Max number of distinct income source types for normalization'),
  ('h_sophistication_weights',
   '{"instrument_type_count":0.15,"strategy_complexity":0.20,"multi_account":0.10,"income_engineering":0.15,"tax_optimization":0.15,"hedging":0.10,"structured_products":0.05,"perpetual_bonds":0.05,"autocallable_notes":0.05}',
   'Weights for h_overall_sophistication composite score')
ON CONFLICT (key) DO NOTHING;

-- Account type pattern rules for classifying account names
INSERT INTO analysis_config (key, value, description) VALUES
  ('h_account_type_patterns',
   '{"ira":["ira","individual retirement","roth","sep-ira","simple ira"],"brokerage":["brokerage","individual","joint","margin","cash"],"business":["trust","corp","llc","business","estate","foundation"],"retirement":["401k","403b","pension","annuity"]}',
   'Account name substrings to classify account types')
ON CONFLICT (key) DO NOTHING;
