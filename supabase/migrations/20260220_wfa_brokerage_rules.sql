-- WFA brokerage rules: naked calls/puts prohibited
-- Created: 2026-02-20
-- Wells Fargo Advisors advisory accounts do not allow naked call writing.
-- Every sold call is by definition covered. Sold puts are cash-secured.

INSERT INTO brokerage_format_rules (brokerage, rule_key, rule_description, rule_logic) VALUES
  ('wells_fargo_advisors', 'no_naked_calls',
   'WFA does not allow naked call writing in advisory accounts',
   '{"sold_call_default": "covered_call", "confidence": "confirmed", "reason": "WFA advisory accounts prohibit naked call writing"}'),
  ('wells_fargo_advisors', 'no_naked_puts',
   'WFA requires cash collateral for short puts in advisory accounts',
   '{"sold_put_default": "cash_secured_put", "confidence": "confirmed", "reason": "WFA requires cash collateral for short puts"}'),
  ('wells_fargo_advisors', 'contracts_to_shares',
   'WFA options: contracts * 100 = shares covered. 50 contracts = 5,000 shares.',
   '{"multiplier": 100, "note": "Trader must own underlying shares to sell calls"}')
ON CONFLICT (brokerage, rule_key) DO NOTHING;
