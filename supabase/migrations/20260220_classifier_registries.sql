-- Migration: Create dimension_registry + feature_registry tables for classifier_v2.
-- These tables drive the config-based scoring path in classifier_v2.py.
-- When present, they override the hardcoded _DIRECTION_MAP / _NORM_RANGES fallbacks.

-- =========================================================================
-- 1. dimension_registry
-- =========================================================================
CREATE TABLE IF NOT EXISTS dimension_registry (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dimension_key   TEXT   NOT NULL UNIQUE,
    name            TEXT   NOT NULL,
    low_label       TEXT   NOT NULL DEFAULT 'Low',
    high_label      TEXT   NOT NULL DEFAULT 'High',
    display_order   INT    NOT NULL DEFAULT 0,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =========================================================================
-- 2. feature_registry
-- =========================================================================
CREATE TABLE IF NOT EXISTS feature_registry (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    feature_key     TEXT    NOT NULL,
    dimension_feeds TEXT    NOT NULL REFERENCES dimension_registry(dimension_key),
    weight          FLOAT   NOT NULL DEFAULT 1.0,
    direction       SMALLINT,          -- +1 or -1
    norm_min        FLOAT,
    norm_max        FLOAT,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (dimension_feeds, feature_key)
);

-- Index for the is_active filter used by classifier_v2
CREATE INDEX IF NOT EXISTS idx_feature_registry_active
    ON feature_registry (is_active) WHERE is_active = TRUE;

-- =========================================================================
-- 3. Seed dimensions  (labels from classifier_v2.py docstrings)
-- =========================================================================
INSERT INTO dimension_registry (dimension_key, name, low_label, high_label, display_order)
VALUES
    ('active_passive',          'Activity Level',         'Passive',       'Active',        1),
    ('momentum_value',          'Entry Strategy',         'Value',         'Momentum',      2),
    ('concentrated_diversified','Concentration',          'Diversified',   'Concentrated',  3),
    ('disciplined_emotional',   'Discipline',             'Emotional',     'Disciplined',   4),
    ('sophisticated_simple',    'Sophistication',         'Simple',        'Sophisticated', 5),
    ('improving_declining',     'Learning Trajectory',    'Declining',     'Improving',     6),
    ('independent_herd',        'Independence',           'Herd Follower', 'Independent',   7),
    ('risk_seeking_averse',     'Risk Appetite',          'Risk Averse',   'Risk Seeking',  8)
ON CONFLICT (dimension_key) DO NOTHING;

-- =========================================================================
-- 4. Seed features  (direction + norm ranges from _DIRECTION_MAP / _NORM_RANGES)
-- =========================================================================
INSERT INTO feature_registry (feature_key, dimension_feeds, weight, direction, norm_min, norm_max)
VALUES
    -- ── active_passive ──
    ('timing_trading_days_per_month',      'active_passive',  1.0,  1, 3,    18),
    ('timing_avg_trades_per_active_day',   'active_passive',  1.0,  1, 1,    5),
    ('holding_pct_investment',             'active_passive',  1.0, -1, 0,    0.9),
    ('holding_pct_day_trades',             'active_passive',  1.0,  1, 0,    0.7),
    ('holding_pct_swing',                  'active_passive',  1.0,  1, 0,    0.7),
    ('portfolio_monthly_turnover',         'active_passive',  1.0,  1, 0.05, 0.8),
    ('exit_partial_ratio',                 'active_passive',  1.0,  1, 0,    0.7),
    ('sector_ticker_churn',                'active_passive',  1.0,  1, 0,    0.8),
    ('instrument_etf_pct',                 'active_passive',  1.0, -1, 0,    0.8),

    -- ── momentum_value ──
    ('entry_breakout_score',               'momentum_value',  1.0,  1, 0,    0.7),
    ('entry_above_ma_score',               'momentum_value',  1.0,  1, 0.3,  0.9),
    ('entry_dip_buyer_score',              'momentum_value',  1.0, -1, 0,    0.6),
    ('entry_vs_52w_range',                 'momentum_value',  1.0,  1, 0.2,  0.8),
    ('entry_on_red_days',                  'momentum_value',  1.0, -1, 0,    1.0),
    ('entry_on_green_days',                'momentum_value',  1.0,  1, 0,    1.0),
    ('market_contrarian_score',            'momentum_value',  1.0, -1, -0.5, 0.5),
    ('holding_median_days',                'momentum_value',  1.0, -1, 5,    120),

    -- ── concentrated_diversified ──
    ('instrument_top3_concentration',      'concentrated_diversified', 1.0,  1, 0.2,  0.8),
    ('sector_hhi',                         'concentrated_diversified', 1.0,  1, 0.1,  0.5),
    ('portfolio_diversification',          'concentrated_diversified', 1.0, -1, 0.2,  0.9),
    ('instrument_unique_tickers',          'concentrated_diversified', 1.0, -1, 3,    25),
    ('sizing_max_single_trade_pct',        'concentrated_diversified', 1.0,  1, 0.05, 0.35),
    ('sector_count',                       'concentrated_diversified', 1.0, -1, 2,    8),
    ('sector_core_vs_explore',             'concentrated_diversified', 1.0,  1, 0.3,  0.9),

    -- ── disciplined_emotional ──
    ('psych_revenge_score',                'disciplined_emotional', 1.0, -1, 0,   0.6),
    ('psych_freeze_score',                 'disciplined_emotional', 1.0, -1, 0,   0.5),
    ('sizing_cv',                          'disciplined_emotional', 1.0, -1, 0.3, 2.0),
    ('holding_cv',                         'disciplined_emotional', 1.0, -1, 0.3, 2.0),
    ('psych_emotional_index',              'disciplined_emotional', 1.0, -1, 0,   0.6),
    ('exit_take_profit_discipline',        'disciplined_emotional', 1.0,  1, 0,   0.8),
    ('risk_has_stops',                     'disciplined_emotional', 1.0,  1, 0,   1.0),
    ('learning_mistake_repetition',        'disciplined_emotional', 1.0, -1, 0,   0.5),
    ('bias_disposition',                   'disciplined_emotional', 1.0, -1, 0.8, 1.5),

    -- ── sophisticated_simple ──
    ('instrument_options_pct',             'sophisticated_simple', 1.0,  1, 0,    0.3),
    ('instrument_etf_pct',                 'sophisticated_simple', 1.0,  1, 0,    1.0),
    ('instrument_leveraged_etf',           'sophisticated_simple', 1.0,  1, 0,    1.0),
    ('instrument_inverse_etf',             'sophisticated_simple', 1.0,  1, 0,    1.0),
    ('risk_hedge_ratio',                   'sophisticated_simple', 1.0,  1, 0,    0.3),
    ('sector_count',                       'sophisticated_simple', 1.0,  1, 2,    8),
    ('instrument_complexity_trend',        'sophisticated_simple', 1.0,  1, -0.5, 0.5),
    ('exit_trailing_stop_score',           'sophisticated_simple', 1.0,  1, 0,    0.5),
    ('timing_december_shift',              'sophisticated_simple', 1.0,  1, 0.8,  2.0),
    ('portfolio_income_component',         'sophisticated_simple', 1.0,  1, 0,    1.0),

    -- ── improving_declining ──
    ('learning_skill_trajectory',          'improving_declining', 1.0,  1, -1.0, 1.0),
    ('learning_win_rate_trend',            'improving_declining', 1.0,  1, -0.5, 0.5),
    ('learning_risk_trend',                'improving_declining', 1.0, -1, -0.5, 0.5),
    ('learning_hold_optimization',         'improving_declining', 1.0, -1, -0.5, 0.5),
    ('learning_mistake_repetition',        'improving_declining', 1.0, -1, 0,    0.5),
    ('learning_sizing_improvement',        'improving_declining', 1.0, -1, -0.5, 0.5),

    -- ── independent_herd ──
    ('social_contrarian_independence',     'independent_herd', 1.0,  1, 0,    1.0),
    ('social_meme_rate',                   'independent_herd', 1.0, -1, 0,    0.5),
    ('social_copycat',                     'independent_herd', 1.0, -1, 0,    0.6),
    ('market_herd_score',                  'independent_herd', 1.0, -1, -0.5, 0.5),
    ('social_bagholding',                  'independent_herd', 1.0, -1, 0,    0.5),
    ('bias_availability',                  'independent_herd', 1.0, -1, 0,    0.8),
    ('social_influence_trend',             'independent_herd', 1.0, -1, -0.5, 0.5),

    -- ── risk_seeking_averse ──
    ('sizing_max_single_trade_pct',        'risk_seeking_averse', 1.0,  1, 0.05, 0.35),
    ('sizing_avg_position_pct',            'risk_seeking_averse', 1.0,  1, 0.02, 0.2),
    ('risk_has_stops',                     'risk_seeking_averse', 1.0, -1, 0,    1.0),
    ('risk_max_loss_pct',                  'risk_seeking_averse', 1.0,  1, 5,    50),
    ('instrument_leveraged_etf',           'risk_seeking_averse', 1.0,  1, 0,    1.0),
    ('sizing_after_losses',                'risk_seeking_averse', 1.0,  1, 0.7,  1.5),
    ('sector_meme_exposure',               'risk_seeking_averse', 1.0,  1, 0,    0.3),
    ('portfolio_long_only',                'risk_seeking_averse', 1.0,  1, 0,    1.0),
    ('risk_hedge_ratio',                   'risk_seeking_averse', 1.0, -1, 0,    0.3),
    ('holding_pct_day_trades',             'risk_seeking_averse', 1.0,  1, 0,    0.4),
    ('psych_escalation',                   'risk_seeking_averse', 1.0,  1, 0,    0.5)
ON CONFLICT (dimension_feeds, feature_key) DO NOTHING;

-- =========================================================================
-- 5. DISABLE 10 meme-stock / social / retail-favourite features
--
-- These features depend on meme-stock and retail-favourite classification
-- data that is unreliable.  Setting is_active = FALSE excludes them from
-- the config-driven scoring path.  The hardcoded fallback in classifier_v2
-- still references them but will only run if this table is inaccessible.
--
-- Features disabled:
--   independent_herd:  social_meme_rate, social_copycat, social_bagholding,
--                      social_contrarian_independence, social_influence_trend,
--                      bias_availability
--   risk_seeking_averse: sector_meme_exposure
--   (not in classifier):  social_hype_position, social_trend_entry_speed,
--                          social_trend_exit_timing
-- =========================================================================

UPDATE feature_registry
SET    is_active   = FALSE,
       updated_at  = now()
WHERE  (dimension_feeds, feature_key) IN (
    ('independent_herd', 'social_meme_rate'),
    ('independent_herd', 'social_copycat'),
    ('independent_herd', 'social_bagholding'),
    ('independent_herd', 'social_contrarian_independence'),
    ('independent_herd', 'social_influence_trend'),
    ('independent_herd', 'bias_availability'),
    ('risk_seeking_averse', 'sector_meme_exposure')
);

-- Note: social_hype_position, social_trend_entry_speed, and
-- social_trend_exit_timing are NOT in the classifier's _DIRECTION_MAP
-- and thus have no feature_registry rows.  They are already excluded
-- from scoring.  They will still be extracted by f13_social.py but
-- the values will be ignored by classifier_v2.

-- =========================================================================
-- 6. RLS policies  (match existing pattern)
-- =========================================================================
ALTER TABLE dimension_registry ENABLE ROW LEVEL SECURITY;
ALTER TABLE feature_registry   ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow authenticated read on dimension_registry"
    ON dimension_registry FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Allow authenticated read on feature_registry"
    ON feature_registry FOR SELECT
    TO authenticated
    USING (true);
