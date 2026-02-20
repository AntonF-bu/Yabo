-- =============================================================================
-- Migration: 20260220_market_data_tables.sql
-- Description: Create market data tables and seed with reference data
-- =============================================================================

-- =============================================================================
-- TABLE 1: ticker_metadata
-- Stores metadata about each ticker symbol (sector, industry, data source, etc.)
-- =============================================================================
CREATE TABLE IF NOT EXISTS ticker_metadata (
    ticker TEXT PRIMARY KEY,
    sector TEXT DEFAULT 'unknown',
    industry TEXT,
    market_cap_category TEXT,
    data_source TEXT DEFAULT 'yfinance',
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '30 days')
);

-- =============================================================================
-- TABLE 2: price_cache
-- Caches OHLCV price data as JSONB to reduce API calls
-- =============================================================================
CREATE TABLE IF NOT EXISTS price_cache (
    ticker TEXT PRIMARY KEY,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    ohlcv_json JSONB NOT NULL,
    row_count INTEGER DEFAULT 0,
    fetched_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- TABLE 3: economic_calendar
-- Tracks scheduled economic events (FOMC, CPI, etc.)
-- =============================================================================
CREATE TABLE IF NOT EXISTS economic_calendar (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    event_type TEXT NOT NULL,
    event_date DATE NOT NULL,
    description TEXT,
    UNIQUE(event_type, event_date)
);

-- =============================================================================
-- TABLE 4: ticker_classifications
-- Categorizes tickers into named lists (meme_stocks, etfs, sectors, etc.)
-- =============================================================================
CREATE TABLE IF NOT EXISTS ticker_classifications (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    list_name TEXT NOT NULL,
    ticker TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(list_name, ticker)
);

-- =============================================================================
-- TABLE 5: analysis_config
-- Key-value configuration store for analysis parameters
-- =============================================================================
CREATE TABLE IF NOT EXISTS analysis_config (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    description TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);


-- =============================================================================
-- SEED: economic_calendar - FOMC dates
-- =============================================================================
INSERT INTO economic_calendar (event_type, event_date, description) VALUES
-- 2023 FOMC
('FOMC', '2023-02-01', 'FOMC Meeting'),
('FOMC', '2023-03-22', 'FOMC Meeting'),
('FOMC', '2023-05-03', 'FOMC Meeting'),
('FOMC', '2023-06-14', 'FOMC Meeting'),
('FOMC', '2023-07-26', 'FOMC Meeting'),
('FOMC', '2023-09-20', 'FOMC Meeting'),
('FOMC', '2023-11-01', 'FOMC Meeting'),
('FOMC', '2023-12-13', 'FOMC Meeting'),
-- 2024 FOMC
('FOMC', '2024-01-31', 'FOMC Meeting'),
('FOMC', '2024-03-20', 'FOMC Meeting'),
('FOMC', '2024-05-01', 'FOMC Meeting'),
('FOMC', '2024-06-12', 'FOMC Meeting'),
('FOMC', '2024-07-31', 'FOMC Meeting'),
('FOMC', '2024-09-18', 'FOMC Meeting'),
('FOMC', '2024-11-07', 'FOMC Meeting'),
('FOMC', '2024-12-18', 'FOMC Meeting'),
-- 2025 FOMC
('FOMC', '2025-01-29', 'FOMC Meeting'),
('FOMC', '2025-03-19', 'FOMC Meeting'),
('FOMC', '2025-05-07', 'FOMC Meeting'),
('FOMC', '2025-06-18', 'FOMC Meeting'),
('FOMC', '2025-07-30', 'FOMC Meeting'),
('FOMC', '2025-09-17', 'FOMC Meeting'),
('FOMC', '2025-11-05', 'FOMC Meeting'),
('FOMC', '2025-12-17', 'FOMC Meeting'),
-- 2026 FOMC
('FOMC', '2026-01-28', 'FOMC Meeting'),
('FOMC', '2026-03-18', 'FOMC Meeting'),
('FOMC', '2026-05-06', 'FOMC Meeting'),
('FOMC', '2026-06-17', 'FOMC Meeting'),
('FOMC', '2026-07-29', 'FOMC Meeting'),
('FOMC', '2026-09-16', 'FOMC Meeting'),
('FOMC', '2026-11-04', 'FOMC Meeting'),
('FOMC', '2026-12-16', 'FOMC Meeting')
ON CONFLICT (event_type, event_date) DO NOTHING;

-- =============================================================================
-- SEED: economic_calendar - CPI dates
-- =============================================================================
INSERT INTO economic_calendar (event_type, event_date, description) VALUES
-- 2023 CPI
('CPI', '2023-01-12', 'CPI Release'),
('CPI', '2023-02-14', 'CPI Release'),
('CPI', '2023-03-14', 'CPI Release'),
('CPI', '2023-04-12', 'CPI Release'),
('CPI', '2023-05-10', 'CPI Release'),
('CPI', '2023-06-13', 'CPI Release'),
('CPI', '2023-07-12', 'CPI Release'),
('CPI', '2023-08-10', 'CPI Release'),
('CPI', '2023-09-13', 'CPI Release'),
('CPI', '2023-10-12', 'CPI Release'),
('CPI', '2023-11-14', 'CPI Release'),
('CPI', '2023-12-12', 'CPI Release'),
-- 2024 CPI
('CPI', '2024-01-11', 'CPI Release'),
('CPI', '2024-02-13', 'CPI Release'),
('CPI', '2024-03-12', 'CPI Release'),
('CPI', '2024-04-10', 'CPI Release'),
('CPI', '2024-05-15', 'CPI Release'),
('CPI', '2024-06-12', 'CPI Release'),
('CPI', '2024-07-11', 'CPI Release'),
('CPI', '2024-08-14', 'CPI Release'),
('CPI', '2024-09-11', 'CPI Release'),
('CPI', '2024-10-10', 'CPI Release'),
('CPI', '2024-11-13', 'CPI Release'),
('CPI', '2024-12-11', 'CPI Release'),
-- 2025 CPI
('CPI', '2025-01-15', 'CPI Release'),
('CPI', '2025-02-12', 'CPI Release'),
('CPI', '2025-03-12', 'CPI Release'),
('CPI', '2025-04-10', 'CPI Release'),
('CPI', '2025-05-13', 'CPI Release'),
('CPI', '2025-06-11', 'CPI Release'),
('CPI', '2025-07-10', 'CPI Release'),
('CPI', '2025-08-12', 'CPI Release'),
('CPI', '2025-09-10', 'CPI Release'),
('CPI', '2025-10-14', 'CPI Release'),
('CPI', '2025-11-12', 'CPI Release'),
('CPI', '2025-12-10', 'CPI Release'),
-- 2026 CPI
('CPI', '2026-01-13', 'CPI Release'),
('CPI', '2026-02-11', 'CPI Release'),
('CPI', '2026-03-11', 'CPI Release'),
('CPI', '2026-04-14', 'CPI Release'),
('CPI', '2026-05-12', 'CPI Release'),
('CPI', '2026-06-10', 'CPI Release'),
('CPI', '2026-07-14', 'CPI Release'),
('CPI', '2026-08-12', 'CPI Release'),
('CPI', '2026-09-15', 'CPI Release'),
('CPI', '2026-10-13', 'CPI Release'),
('CPI', '2026-11-10', 'CPI Release'),
('CPI', '2026-12-09', 'CPI Release')
ON CONFLICT (event_type, event_date) DO NOTHING;


-- =============================================================================
-- SEED: ticker_classifications - meme_stocks
-- =============================================================================
INSERT INTO ticker_classifications (list_name, ticker) VALUES
('meme_stocks', 'GME'),
('meme_stocks', 'AMC'),
('meme_stocks', 'BBBY'),
('meme_stocks', 'BB'),
('meme_stocks', 'NOK'),
('meme_stocks', 'PLTR'),
('meme_stocks', 'WISH'),
('meme_stocks', 'CLOV'),
('meme_stocks', 'SOFI'),
('meme_stocks', 'RIVN'),
('meme_stocks', 'LCID'),
('meme_stocks', 'MSTR'),
('meme_stocks', 'SMCI'),
('meme_stocks', 'DWAC'),
('meme_stocks', 'TRUMP'),
('meme_stocks', 'HOOD')
ON CONFLICT (list_name, ticker) DO NOTHING;

-- =============================================================================
-- SEED: ticker_classifications - top_retail
-- =============================================================================
INSERT INTO ticker_classifications (list_name, ticker) VALUES
('top_retail', 'AAPL'),
('top_retail', 'TSLA'),
('top_retail', 'NVDA'),
('top_retail', 'AMD'),
('top_retail', 'AMZN'),
('top_retail', 'META'),
('top_retail', 'GOOGL'),
('top_retail', 'MSFT'),
('top_retail', 'PLTR'),
('top_retail', 'SOFI'),
('top_retail', 'NIO'),
('top_retail', 'GME'),
('top_retail', 'AMC'),
('top_retail', 'SPY'),
('top_retail', 'QQQ'),
('top_retail', 'COIN'),
('top_retail', 'RIVN'),
('top_retail', 'LCID'),
('top_retail', 'HOOD'),
('top_retail', 'SQ')
ON CONFLICT (list_name, ticker) DO NOTHING;

-- =============================================================================
-- SEED: ticker_classifications - etfs
-- =============================================================================
INSERT INTO ticker_classifications (list_name, ticker) VALUES
('etfs', 'SPY'),
('etfs', 'QQQ'),
('etfs', 'IWM'),
('etfs', 'DIA'),
('etfs', 'VOO'),
('etfs', 'VTI'),
('etfs', 'VEA'),
('etfs', 'VWO'),
('etfs', 'EFA'),
('etfs', 'AGG'),
('etfs', 'BND'),
('etfs', 'TLT'),
('etfs', 'IEF'),
('etfs', 'SHY'),
('etfs', 'GLD'),
('etfs', 'SLV'),
('etfs', 'USO'),
('etfs', 'UNG'),
('etfs', 'VNQ'),
('etfs', 'SCHD'),
('etfs', 'VIG'),
('etfs', 'ARKK'),
('etfs', 'ARKG'),
('etfs', 'ARKW'),
('etfs', 'ARKF'),
('etfs', 'ARKQ'),
('etfs', 'XLK'),
('etfs', 'XLV'),
('etfs', 'XLE'),
('etfs', 'XLF'),
('etfs', 'XLI'),
('etfs', 'XLY'),
('etfs', 'XLP'),
('etfs', 'XLB'),
('etfs', 'XLU'),
('etfs', 'XLRE'),
('etfs', 'XLC'),
('etfs', 'SMH'),
('etfs', 'SOXX'),
('etfs', 'KWEB'),
('etfs', 'EEM'),
('etfs', 'HYG'),
('etfs', 'LQD'),
('etfs', 'TIP'),
('etfs', 'IEMG'),
('etfs', 'RSP'),
('etfs', 'MDY'),
('etfs', 'IJR'),
('etfs', 'IJH'),
('etfs', 'ITOT'),
('etfs', 'IXUS'),
('etfs', 'VXUS'),
('etfs', 'VGT'),
('etfs', 'VHT'),
('etfs', 'VFH'),
('etfs', 'VDE'),
('etfs', 'VIS'),
('etfs', 'VCR'),
('etfs', 'VDC'),
('etfs', 'VAW'),
('etfs', 'VOX'),
('etfs', 'VNQI')
ON CONFLICT (list_name, ticker) DO NOTHING;

-- =============================================================================
-- SEED: ticker_classifications - sector_etfs
-- =============================================================================
INSERT INTO ticker_classifications (list_name, ticker) VALUES
('sector_etfs', 'XLK'),
('sector_etfs', 'XLV'),
('sector_etfs', 'XLE'),
('sector_etfs', 'XLF'),
('sector_etfs', 'XLI'),
('sector_etfs', 'XLY'),
('sector_etfs', 'XLP'),
('sector_etfs', 'XLB'),
('sector_etfs', 'XLU'),
('sector_etfs', 'XLRE'),
('sector_etfs', 'XLC'),
('sector_etfs', 'SMH'),
('sector_etfs', 'SOXX'),
('sector_etfs', 'KWEB'),
('sector_etfs', 'IBB'),
('sector_etfs', 'IHI'),
('sector_etfs', 'ITA'),
('sector_etfs', 'ITB'),
('sector_etfs', 'IGV'),
('sector_etfs', 'HACK'),
('sector_etfs', 'ARKK'),
('sector_etfs', 'ARKG'),
('sector_etfs', 'ARKW'),
('sector_etfs', 'ARKF'),
('sector_etfs', 'ARKQ')
ON CONFLICT (list_name, ticker) DO NOTHING;

-- =============================================================================
-- SEED: ticker_classifications - leveraged_etfs (3x bull)
-- =============================================================================
INSERT INTO ticker_classifications (list_name, ticker, metadata) VALUES
('leveraged_etfs', 'TQQQ', '{"leverage":3,"direction":"bull"}'),
('leveraged_etfs', 'SOXL', '{"leverage":3,"direction":"bull"}'),
('leveraged_etfs', 'UPRO', '{"leverage":3,"direction":"bull"}'),
('leveraged_etfs', 'SPXL', '{"leverage":3,"direction":"bull"}'),
('leveraged_etfs', 'TNA', '{"leverage":3,"direction":"bull"}'),
('leveraged_etfs', 'LABU', '{"leverage":3,"direction":"bull"}'),
('leveraged_etfs', 'TECL', '{"leverage":3,"direction":"bull"}'),
('leveraged_etfs', 'FAS', '{"leverage":3,"direction":"bull"}'),
('leveraged_etfs', 'NUGT', '{"leverage":3,"direction":"bull"}'),
('leveraged_etfs', 'JNUG', '{"leverage":3,"direction":"bull"}'),
('leveraged_etfs', 'UDOW', '{"leverage":3,"direction":"bull"}'),
('leveraged_etfs', 'FNGU', '{"leverage":3,"direction":"bull"}'),
('leveraged_etfs', 'BULZ', '{"leverage":3,"direction":"bull"}'),
('leveraged_etfs', 'CURE', '{"leverage":3,"direction":"bull"}'),
('leveraged_etfs', 'NAIL', '{"leverage":3,"direction":"bull"}'),
('leveraged_etfs', 'RETL', '{"leverage":3,"direction":"bull"}'),
('leveraged_etfs', 'DPST', '{"leverage":3,"direction":"bull"}'),
('leveraged_etfs', 'MIDU', '{"leverage":3,"direction":"bull"}'),
('leveraged_etfs', 'DFEN', '{"leverage":3,"direction":"bull"}'),
('leveraged_etfs', 'DUSL', '{"leverage":3,"direction":"bull"}'),
('leveraged_etfs', 'PILL', '{"leverage":3,"direction":"bull"}'),
('leveraged_etfs', 'UBOT', '{"leverage":3,"direction":"bull"}'),
('leveraged_etfs', 'WANT', '{"leverage":3,"direction":"bull"}'),
-- 3x bear
('leveraged_etfs', 'SQQQ', '{"leverage":3,"direction":"bear"}'),
('leveraged_etfs', 'SPXS', '{"leverage":3,"direction":"bear"}'),
('leveraged_etfs', 'SPXU', '{"leverage":3,"direction":"bear"}'),
('leveraged_etfs', 'TZA', '{"leverage":3,"direction":"bear"}'),
('leveraged_etfs', 'SOXS', '{"leverage":3,"direction":"bear"}'),
('leveraged_etfs', 'LABD', '{"leverage":3,"direction":"bear"}'),
('leveraged_etfs', 'FAZ', '{"leverage":3,"direction":"bear"}'),
('leveraged_etfs', 'SDOW', '{"leverage":3,"direction":"bear"}'),
('leveraged_etfs', 'FNGD', '{"leverage":3,"direction":"bear"}'),
('leveraged_etfs', 'SRTY', '{"leverage":3,"direction":"bear"}'),
-- 2x bull
('leveraged_etfs', 'QLD', '{"leverage":2,"direction":"bull"}'),
('leveraged_etfs', 'SSO', '{"leverage":2,"direction":"bull"}'),
('leveraged_etfs', 'UWM', '{"leverage":2,"direction":"bull"}'),
('leveraged_etfs', 'DDM', '{"leverage":2,"direction":"bull"}'),
('leveraged_etfs', 'MVV', '{"leverage":2,"direction":"bull"}'),
('leveraged_etfs', 'SAA', '{"leverage":2,"direction":"bull"}'),
('leveraged_etfs', 'ROM', '{"leverage":2,"direction":"bull"}'),
('leveraged_etfs', 'UYG', '{"leverage":2,"direction":"bull"}'),
('leveraged_etfs', 'UGE', '{"leverage":2,"direction":"bull"}'),
-- 2x bear
('leveraged_etfs', 'SDS', '{"leverage":2,"direction":"bear"}'),
('leveraged_etfs', 'QID', '{"leverage":2,"direction":"bear"}'),
('leveraged_etfs', 'TWM', '{"leverage":2,"direction":"bear"}'),
('leveraged_etfs', 'DXD', '{"leverage":2,"direction":"bear"}'),
('leveraged_etfs', 'MZZ', '{"leverage":2,"direction":"bear"}'),
-- 1x inverse
('leveraged_etfs', 'SH', '{"leverage":1,"direction":"bear"}'),
('leveraged_etfs', 'PSQ', '{"leverage":1,"direction":"bear"}'),
('leveraged_etfs', 'DOG', '{"leverage":1,"direction":"bear"}'),
('leveraged_etfs', 'RWM', '{"leverage":1,"direction":"bear"}')
ON CONFLICT (list_name, ticker) DO NOTHING;

-- =============================================================================
-- SEED: ticker_classifications - inverse_etfs
-- =============================================================================
INSERT INTO ticker_classifications (list_name, ticker) VALUES
('inverse_etfs', 'SH'),
('inverse_etfs', 'SDS'),
('inverse_etfs', 'SQQQ'),
('inverse_etfs', 'SPXS'),
('inverse_etfs', 'SPXU'),
('inverse_etfs', 'TZA'),
('inverse_etfs', 'SOXS'),
('inverse_etfs', 'LABD'),
('inverse_etfs', 'FAZ'),
('inverse_etfs', 'SDOW'),
('inverse_etfs', 'FNGD'),
('inverse_etfs', 'PSQ'),
('inverse_etfs', 'DOG'),
('inverse_etfs', 'RWM'),
('inverse_etfs', 'SRTY'),
('inverse_etfs', 'QID'),
('inverse_etfs', 'TWM'),
('inverse_etfs', 'DXD'),
('inverse_etfs', 'MZZ')
ON CONFLICT (list_name, ticker) DO NOTHING;

-- =============================================================================
-- SEED: ticker_classifications - mega_cap
-- =============================================================================
INSERT INTO ticker_classifications (list_name, ticker) VALUES
('mega_cap', 'AAPL'),
('mega_cap', 'MSFT'),
('mega_cap', 'GOOGL'),
('mega_cap', 'GOOG'),
('mega_cap', 'AMZN'),
('mega_cap', 'NVDA'),
('mega_cap', 'META'),
('mega_cap', 'TSLA'),
('mega_cap', 'BRK-B'),
('mega_cap', 'LLY')
ON CONFLICT (list_name, ticker) DO NOTHING;

-- =============================================================================
-- SEED: ticker_classifications - small_cap
-- =============================================================================
INSERT INTO ticker_classifications (list_name, ticker) VALUES
('small_cap', 'IONQ'),
('small_cap', 'SOUN'),
('small_cap', 'RKLB'),
('small_cap', 'INMB'),
('small_cap', 'WISH'),
('small_cap', 'CLOV'),
('small_cap', 'BB'),
('small_cap', 'NOK'),
('small_cap', 'BBBY'),
('small_cap', 'DWAC'),
('small_cap', 'LCID'),
('small_cap', 'RIVN'),
('small_cap', 'HOOD'),
('small_cap', 'SOFI'),
('small_cap', 'SMCI')
ON CONFLICT (list_name, ticker) DO NOTHING;

-- =============================================================================
-- SEED: ticker_classifications - growth
-- =============================================================================
INSERT INTO ticker_classifications (list_name, ticker) VALUES
('growth', 'NVDA'),
('growth', 'TSLA'),
('growth', 'AMD'),
('growth', 'SHOP'),
('growth', 'SQ'),
('growth', 'NET'),
('growth', 'SNOW'),
('growth', 'CRWD'),
('growth', 'PLTR'),
('growth', 'COIN'),
('growth', 'MSTR'),
('growth', 'RBLX'),
('growth', 'ABNB'),
('growth', 'RIVN'),
('growth', 'LCID'),
('growth', 'IONQ'),
('growth', 'SOUN'),
('growth', 'RKLB'),
('growth', 'ARKK'),
('growth', 'ARKG'),
('growth', 'TQQQ'),
('growth', 'META'),
('growth', 'AMZN'),
('growth', 'GOOGL'),
('growth', 'NFLX'),
('growth', 'CRM'),
('growth', 'NOW'),
('growth', 'ADBE'),
('growth', 'INTU'),
('growth', 'PANW'),
('growth', 'FTNT'),
('growth', 'ZS'),
('growth', 'APP'),
('growth', 'SMCI')
ON CONFLICT (list_name, ticker) DO NOTHING;

-- =============================================================================
-- SEED: ticker_classifications - value
-- =============================================================================
INSERT INTO ticker_classifications (list_name, ticker) VALUES
('value', 'BRK-B'),
('value', 'JPM'),
('value', 'BAC'),
('value', 'WFC'),
('value', 'JNJ'),
('value', 'PG'),
('value', 'KO'),
('value', 'PEP'),
('value', 'VZ'),
('value', 'T'),
('value', 'XOM'),
('value', 'CVX'),
('value', 'MO'),
('value', 'PM'),
('value', 'ABBV'),
('value', 'MRK'),
('value', 'BMY'),
('value', 'PFE'),
('value', 'MMM'),
('value', 'IBM'),
('value', 'INTC'),
('value', 'COST'),
('value', 'WMT'),
('value', 'HD'),
('value', 'LOW'),
('value', 'GIS'),
('value', 'KHC')
ON CONFLICT (list_name, ticker) DO NOTHING;

-- =============================================================================
-- SEED: ticker_classifications - income
-- =============================================================================
INSERT INTO ticker_classifications (list_name, ticker) VALUES
('income', 'O'),
('income', 'VNQ'),
('income', 'SCHD'),
('income', 'VIG'),
('income', 'T'),
('income', 'VZ'),
('income', 'MO'),
('income', 'PM'),
('income', 'ABBV'),
('income', 'XOM'),
('income', 'CVX'),
('income', 'PG'),
('income', 'KO'),
('income', 'PEP'),
('income', 'JNJ'),
('income', 'DUK'),
('income', 'SO'),
('income', 'NEE'),
('income', 'D')
ON CONFLICT (list_name, ticker) DO NOTHING;

-- =============================================================================
-- SEED: ticker_classifications - recent_ipos
-- =============================================================================
INSERT INTO ticker_classifications (list_name, ticker) VALUES
('recent_ipos', 'ARM'),
('recent_ipos', 'BIRK'),
('recent_ipos', 'CART'),
('recent_ipos', 'CAVA'),
('recent_ipos', 'KPLT'),
('recent_ipos', 'KVYO'),
('recent_ipos', 'TOST'),
('recent_ipos', 'VFS'),
('recent_ipos', 'IBKR'),
('recent_ipos', 'RDDT'),
('recent_ipos', 'ASTERA')
ON CONFLICT (list_name, ticker) DO NOTHING;


-- =============================================================================
-- SEED: analysis_config
-- =============================================================================
INSERT INTO analysis_config (key, value, description) VALUES
('sector_int_map', '{"Technology":0,"Healthcare":1,"Financials":2,"Consumer Discretionary":3,"Consumer Staples":4,"Energy":5,"Industrials":6,"Communication Services":7,"Materials":8,"Utilities":9,"Real Estate":10,"unknown":11}', 'Sector name to integer encoding for ML features'),
('entry_dip_threshold', '0.95', 'Fraction of 20d high for dip buyer detection'),
('entry_breakout_threshold', '0.98', 'Fraction of 20d high for breakout detection'),
('entry_gap_threshold', '0.02', 'Minimum overnight gap percentage for gap score'),
('exit_trailing_max_estimate', '1.5', 'Estimated max unrealized gain multiplier'),
('exit_trailing_drawdown_min', '0.05', 'Min drawdown from max for trailing stop'),
('exit_trailing_drawdown_max', '0.15', 'Max drawdown from max for trailing stop'),
('exit_high_of_day_threshold', '0.80', 'Day range fraction for high-of-day exit'),
('exit_panic_threshold', '-0.03', 'Daily return threshold for panic selling'),
('exit_time_based_min', '-5.0', 'Min return_pct for time-based exit'),
('exit_time_based_max', '5.0', 'Max return_pct for time-based exit'),
('psych_streak_threshold', '3', 'Consecutive wins/losses for streak behavior'),
('psych_revenge_window_days', '2', 'Days after loss to check for revenge trading'),
('psych_freeze_days', '7', 'Inactivity days to count as trading freeze'),
('psych_loss_rebuy_days', '30', 'Days within which rebuy of loser counts'),
('psych_breakeven_range', '2.0', 'Return pct range for breakeven exits'),
('psych_drawdown_threshold', '0.15', 'Drawdown pct threshold for tilt detection'),
('sector_tech_benchmark', '0.30', 'Tech sector weight benchmark for overweight calc'),
('market_dip_threshold', '-0.01', 'SPY daily return for dip classification'),
('market_rally_threshold', '0.01', 'SPY daily return for rally classification'),
('market_regime_bull_threshold', '0.05', 'SPY 20d return for bull regime'),
('market_regime_bear_threshold', '-0.05', 'SPY 20d return for bear regime'),
('risk_stop_std_threshold', '5.0', 'Loss std dev threshold for stop-loss detection'),
('social_high_volume_threshold', '2.0', 'Relative volume threshold for news-driven activity'),
('social_bagholding_days', '30', 'Days held threshold for meme bagholding'),
('earnings_months', '[1,4,7,10]', 'Months considered earnings season')
ON CONFLICT (key) DO NOTHING;


-- =============================================================================
-- SEED: ticker_metadata - initial sector data (193 tickers)
-- =============================================================================
INSERT INTO ticker_metadata (ticker, sector, market_cap_category) VALUES
-- Technology (45 tickers)
('AAPL', 'Technology', 'mega'),
('MSFT', 'Technology', 'mega'),
('GOOGL', 'Technology', 'mega'),
('GOOG', 'Technology', 'mega'),
('META', 'Technology', 'mega'),
('NVDA', 'Technology', 'mega'),
('TSM', 'Technology', NULL),
('AVGO', 'Technology', NULL),
('ADBE', 'Technology', NULL),
('CRM', 'Technology', NULL),
('ORCL', 'Technology', NULL),
('ACN', 'Technology', NULL),
('CSCO', 'Technology', NULL),
('INTC', 'Technology', NULL),
('AMD', 'Technology', NULL),
('TXN', 'Technology', NULL),
('QCOM', 'Technology', NULL),
('IBM', 'Technology', NULL),
('AMAT', 'Technology', NULL),
('NOW', 'Technology', NULL),
('INTU', 'Technology', NULL),
('MU', 'Technology', NULL),
('LRCX', 'Technology', NULL),
('KLAC', 'Technology', NULL),
('SNPS', 'Technology', NULL),
('CDNS', 'Technology', NULL),
('MRVL', 'Technology', NULL),
('NXPI', 'Technology', NULL),
('PANW', 'Technology', NULL),
('CRWD', 'Technology', NULL),
('SNOW', 'Technology', NULL),
('NET', 'Technology', NULL),
('PLTR', 'Technology', NULL),
('SMCI', 'Technology', 'small'),
('APP', 'Technology', NULL),
('SHOP', 'Technology', NULL),
('SQ', 'Technology', NULL),
('COIN', 'Technology', NULL),
('MSTR', 'Technology', NULL),
('IONQ', 'Technology', 'small'),
('SOUN', 'Technology', 'small'),
('RKLB', 'Technology', 'small'),
('ANET', 'Technology', NULL),
('FTNT', 'Technology', NULL),
('ZS', 'Technology', NULL),
-- Healthcare (26 tickers)
('UNH', 'Healthcare', NULL),
('JNJ', 'Healthcare', NULL),
('LLY', 'Healthcare', 'mega'),
('ABBV', 'Healthcare', NULL),
('MRK', 'Healthcare', NULL),
('TMO', 'Healthcare', NULL),
('ABT', 'Healthcare', NULL),
('PFE', 'Healthcare', NULL),
('DHR', 'Healthcare', NULL),
('BMY', 'Healthcare', NULL),
('AMGN', 'Healthcare', NULL),
('GILD', 'Healthcare', NULL),
('MDT', 'Healthcare', NULL),
('ISRG', 'Healthcare', NULL),
('SYK', 'Healthcare', NULL),
('ELV', 'Healthcare', NULL),
('VRTX', 'Healthcare', NULL),
('REGN', 'Healthcare', NULL),
('CI', 'Healthcare', NULL),
('BSX', 'Healthcare', NULL),
('ZTS', 'Healthcare', NULL),
('BDX', 'Healthcare', NULL),
('HCA', 'Healthcare', NULL),
('MRNA', 'Healthcare', NULL),
('INMB', 'Healthcare', 'small'),
('DXCM', 'Healthcare', NULL),
-- Financials (23 tickers)
('BRK-B', 'Financials', 'mega'),
('JPM', 'Financials', NULL),
('V', 'Financials', NULL),
('MA', 'Financials', NULL),
('BAC', 'Financials', NULL),
('WFC', 'Financials', NULL),
('GS', 'Financials', NULL),
('MS', 'Financials', NULL),
('SCHW', 'Financials', NULL),
('AXP', 'Financials', NULL),
('BLK', 'Financials', NULL),
('C', 'Financials', NULL),
('SPGI', 'Financials', NULL),
('CB', 'Financials', NULL),
('MMC', 'Financials', NULL),
('PGR', 'Financials', NULL),
('ICE', 'Financials', NULL),
('CME', 'Financials', NULL),
('AON', 'Financials', NULL),
('MCO', 'Financials', NULL),
('USB', 'Financials', NULL),
('HOOD', 'Financials', 'small'),
('SOFI', 'Financials', 'small'),
-- Consumer Discretionary (16 tickers)
('AMZN', 'Consumer Discretionary', 'mega'),
('TSLA', 'Consumer Discretionary', 'mega'),
('HD', 'Consumer Discretionary', NULL),
('MCD', 'Consumer Discretionary', NULL),
('NKE', 'Consumer Discretionary', NULL),
('LOW', 'Consumer Discretionary', NULL),
('SBUX', 'Consumer Discretionary', NULL),
('TJX', 'Consumer Discretionary', NULL),
('BKNG', 'Consumer Discretionary', NULL),
('CMG', 'Consumer Discretionary', NULL),
('GM', 'Consumer Discretionary', NULL),
('F', 'Consumer Discretionary', NULL),
('RIVN', 'Consumer Discretionary', 'small'),
('LCID', 'Consumer Discretionary', 'small'),
('ABNB', 'Consumer Discretionary', NULL),
('ROST', 'Consumer Discretionary', NULL),
-- Consumer Staples (14 tickers)
('PG', 'Consumer Staples', NULL),
('KO', 'Consumer Staples', NULL),
('PEP', 'Consumer Staples', NULL),
('COST', 'Consumer Staples', NULL),
('WMT', 'Consumer Staples', NULL),
('PM', 'Consumer Staples', NULL),
('MO', 'Consumer Staples', NULL),
('MDLZ', 'Consumer Staples', NULL),
('CL', 'Consumer Staples', NULL),
('EL', 'Consumer Staples', NULL),
('KHC', 'Consumer Staples', NULL),
('GIS', 'Consumer Staples', NULL),
('KR', 'Consumer Staples', NULL),
('SYY', 'Consumer Staples', NULL),
-- Energy (14 tickers)
('XOM', 'Energy', NULL),
('CVX', 'Energy', NULL),
('COP', 'Energy', NULL),
('SLB', 'Energy', NULL),
('EOG', 'Energy', NULL),
('MPC', 'Energy', NULL),
('PSX', 'Energy', NULL),
('VLO', 'Energy', NULL),
('OXY', 'Energy', NULL),
('HAL', 'Energy', NULL),
('DVN', 'Energy', NULL),
('PXD', 'Energy', NULL),
('FANG', 'Energy', NULL),
('HES', 'Energy', NULL),
-- Industrials (18 tickers)
('GE', 'Industrials', NULL),
('CAT', 'Industrials', NULL),
('HON', 'Industrials', NULL),
('UNP', 'Industrials', NULL),
('RTX', 'Industrials', NULL),
('BA', 'Industrials', NULL),
('DE', 'Industrials', NULL),
('LMT', 'Industrials', NULL),
('UPS', 'Industrials', NULL),
('MMM', 'Industrials', NULL),
('GD', 'Industrials', NULL),
('NOC', 'Industrials', NULL),
('EMR', 'Industrials', NULL),
('ITW', 'Industrials', NULL),
('WM', 'Industrials', NULL),
('CSX', 'Industrials', NULL),
('NSC', 'Industrials', NULL),
('FDX', 'Industrials', NULL),
-- Communication Services (12 tickers)
('DIS', 'Communication Services', NULL),
('NFLX', 'Communication Services', NULL),
('CMCSA', 'Communication Services', NULL),
('T', 'Communication Services', NULL),
('VZ', 'Communication Services', NULL),
('TMUS', 'Communication Services', NULL),
('ATVI', 'Communication Services', NULL),
('EA', 'Communication Services', NULL),
('TTWO', 'Communication Services', NULL),
('RBLX', 'Communication Services', NULL),
('SNAP', 'Communication Services', NULL),
('PINS', 'Communication Services', NULL),
-- Materials (9 tickers)
('LIN', 'Materials', NULL),
('APD', 'Materials', NULL),
('FCX', 'Materials', NULL),
('NEM', 'Materials', NULL),
('NUE', 'Materials', NULL),
('DOW', 'Materials', NULL),
('DD', 'Materials', NULL),
('ECL', 'Materials', NULL),
('SHW', 'Materials', NULL),
-- Utilities (8 tickers)
('NEE', 'Utilities', NULL),
('DUK', 'Utilities', NULL),
('SO', 'Utilities', NULL),
('D', 'Utilities', NULL),
('AEP', 'Utilities', NULL),
('SRE', 'Utilities', NULL),
('EXC', 'Utilities', NULL),
('XEL', 'Utilities', NULL),
-- Real Estate (8 tickers)
('PLD', 'Real Estate', NULL),
('AMT', 'Real Estate', NULL),
('CCI', 'Real Estate', NULL),
('EQIX', 'Real Estate', NULL),
('PSA', 'Real Estate', NULL),
('O', 'Real Estate', NULL),
('SPG', 'Real Estate', NULL),
('DLR', 'Real Estate', NULL)
ON CONFLICT (ticker) DO NOTHING;
