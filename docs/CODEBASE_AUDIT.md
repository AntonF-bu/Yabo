# Yabo Codebase Audit

> Generated: 2026-02-18 | Total project: ~31,600 lines across 149 source files

---

## Section 1: Page Routes

| # | Route | File | Lines | What it does | Components imported | APIs / Services called | Data source | Status |
|---|-------|------|-------|-------------|-------------------|----------------------|-------------|--------|
| 1 | `/` | `src/app/page.tsx` | 258 | Marketing landing page. Hero, stats, pricing tiers, FAQ | None (self-contained) | None | **MOCK** (hardcoded stats: "12,400+ traders", "$2.4B volume") | FUNCTIONAL |
| 2 | `/sign-in` | `src/app/sign-in/[[...sign-in]]/page.tsx` | 12 | Clerk sign-in wrapper | `@clerk/nextjs` SignIn | Clerk | Real | FUNCTIONAL |
| 3 | `/sign-up` | `src/app/sign-up/[[...sign-up]]/page.tsx` | 12 | Clerk sign-up wrapper | `@clerk/nextjs` SignUp | Clerk | Real | FUNCTIONAL |
| 4 | `/onboarding` | `src/app/onboarding/page.tsx` | 289 | 5-step quiz: trader type, sectors, scenario, risk, experience. Saves to Supabase | QuizSplash, TraderTypeStep, SectorStep, ScenarioStep, RiskStep, ExperienceStep, ProfileReveal, ProgressBar | Supabase (profiles), `lib/db.ts` | Real + localStorage fallback | FUNCTIONAL |
| 5 | `/intake` | `src/app/intake/page.tsx` | 68 | Intake landing page for new traders (Meridian-branded) | IntakeForm | None directly | Static | FUNCTIONAL |
| 6 | `/import` | `src/app/import/page.tsx` | 969 | Screenshot + CSV upload flow. Sends to Railway for extraction. Multi-step: upload -> review -> analyze | None (self-contained) | Railway (`/extract_screenshots`, `/analyze`), Supabase Storage (`trade-data` bucket), Supabase (`traders`, `trade_imports`) | Real | FUNCTIONAL |
| 7 | `/dashboard` | `src/app/dashboard/page.tsx` | 356 | Main dashboard with 7 tabs: Discover, Room, Predict, Board, Mirror, Strategy, Moves | Sidebar, TopBar, GuidePanel, GuideToggle, DiscoverTab, RoomTab, PredictTab, BoardTab, MirrorTab, StrategyTab, MovesTab, TradePanel | Supabase (profiles, trades, positions), Finnhub | Real + Mock mix | FUNCTIONAL |
| 8 | `/dashboard/import` | `src/app/dashboard/import/page.tsx` | 523 | CSV column-mapping import. 4 steps: Upload -> Map Columns -> Review -> AI Analysis | CsvUploader, ColumnMapper, ImportPreview, ImportSummary | `/api/classify-csv`, `/api/analyze-trades`, Supabase (trades) | Real | FUNCTIONAL |
| 9 | `/dashboard/ticker/[symbol]` | `src/app/dashboard/ticker/[symbol]/page.tsx` | 469 | Stock detail page. Chart, company info, position, trade history | TickerSearch, TradeButton | Finnhub (quote, profile, candles), Supabase (trades, positions) | Real | FUNCTIONAL |
| 10 | `/trading-dna` | `src/app/trading-dna/page.tsx` | 911 | Full behavioral analysis page. CSV upload with 3-layer parsing (auto -> Claude -> manual). Shows Trading DNA profile | RadarProfile | `/api/classify-csv`, Railway (`/analyze`), `lib/trading-dna-parser.ts` | Real | FUNCTIONAL |

**Layouts:**

| File | Lines | Purpose |
|------|-------|---------|
| `src/app/layout.tsx` | 104 | Root layout. ClerkProvider, Google Fonts (Newsreader, Inter, IBM Plex Mono), globals.css |
| `src/app/dashboard/layout.tsx` | 7 | Pass-through wrapper |
| `src/app/intake/layout.tsx` | 15 | Minimal background color wrapper |

---

## Section 2: API Routes

| # | Endpoint | Methods | File | Lines | What it does | External services | Used by |
|---|----------|---------|------|-------|-------------|-------------------|---------|
| 1 | `/api/setup-db` | POST | `src/app/api/setup-db/route.ts` | 62 | Reads `schema.sql` and executes via Supabase RPC (`exec_sql`). One-time DB init. | Supabase | Manual/admin only |
| 2 | `/api/classify-csv` | POST | `src/app/api/classify-csv/route.ts` | 159 | Uses Claude Haiku to detect CSV column mappings. Input: headers + sample rows. Returns: mapping + confidence. | Anthropic (`claude-haiku-4-5-20251001`) | `/dashboard/import`, `/trading-dna` |
| 3 | `/api/analyze-trades` | POST | `src/app/api/analyze-trades/route.ts` | 287 | Uses Claude Sonnet to generate behavioral profile. Input: trades + positions + portfolio. Returns: archetype, 8 traits (20-95), recommendations. Fallback when no API key. | Anthropic (`claude-sonnet-4-20250514`) | `/dashboard/import`, MirrorTab |

---

## Section 3: Components

### UI Components (`src/components/ui/`) — 11 files, 309 lines

| Component | File | Lines | What it renders | Used by | Reusable? | Styling |
|-----------|------|-------|----------------|---------|-----------|---------|
| AccentLine | `AccentLine.tsx` | 11 | Decorative gradient line | MirrorTab | Yes | Meridian |
| Badge | `Badge.tsx` | 25 | Text badge with color variants | Multiple | Yes | Meridian |
| Card | `Card.tsx` | 22 | Rounded card container | Multiple | Yes | Meridian |
| ConvictionBar | `ConvictionBar.tsx` | 28 | Horizontal bar 0-100 | ThesisCard | Yes | Meridian |
| LiveDot | `LiveDot.tsx` | 18 | Pulsing green/red dot | DiscoverTab | Yes | Meridian |
| MockDataBadge | `MockDataBadge.tsx` | 25 | "Using sample data" label | MirrorTab | Yes | Meridian |
| SignalBadge | `SignalBadge.tsx` | 28 | Buy/sell/hold signal chip | ThesisCard | Yes | Meridian |
| Sparkline | `Sparkline.tsx` | 28 | Mini SVG line chart | TickerCard | Yes | Meridian |
| StatCard | `StatCard.tsx` | 24 | Stat with label + value | Dashboard | Yes | Meridian |
| TierBadge | `TierBadge.tsx` | 31 | Tier label (Paper/Bronze/etc) | Sidebar, Board | Yes | Meridian |
| TraitBar | `TraitBar.tsx` | 69 | Skill bar with score + label | MirrorTab | Yes | Meridian |

### Layout Components (`src/components/layout/`) — 2 files, 271 lines

| Component | File | Lines | What it renders | Used by | Styling |
|-----------|------|-------|----------------|---------|---------|
| Sidebar | `Sidebar.tsx` | 212 | Navigation sidebar with 7 tabs, user info, portfolio stats | Dashboard | Meridian |
| TopBar | `TopBar.tsx` | 59 | Header with user name, guide toggle | Dashboard | Meridian |

### Dashboard Tab Components (`src/components/dashboard/`) — 8 files, 1,173 lines

| Component | File | Lines | What it renders | Data source | Styling |
|-----------|------|-------|----------------|-------------|---------|
| DiscoverTab | `DiscoverTab.tsx` | 260 | Stock discovery grid, trending, recent trades, gamification | Finnhub (real) + mock trending list | Meridian |
| RoomTab | `RoomTab.tsx` | 126 | Social chat/thesis feed | **MOCK** (hardcoded) | Meridian |
| PredictTab | `PredictTab.tsx` | 107 | Prediction market cards | **MOCK** (hardcoded) | Meridian |
| BoardTab | `BoardTab.tsx` | 117 | Leaderboard rankings | **MOCK** (hardcoded) | Meridian |
| MirrorTab | `MirrorTab.tsx` | 322 | Trading DNA profile — traits radar, archetype, win/loss | Supabase (real) + fallback | Meridian |
| StrategyTab | `StrategyTab.tsx` | 80 | Trading rules display | **MOCK** (hardcoded) | Meridian |
| MovesTab | `MovesTab.tsx` | 51 | Recent activity feed | **MOCK** (hardcoded) | Meridian |
| PositionsList | `PositionsList.tsx` | 56 | Open positions table | Props (real from dashboard) | Meridian |
| RecentTrades | `RecentTrades.tsx` | 54 | Trade history list | Props (real from dashboard) | Meridian |

### Trade Components (`src/components/trade/`) — 7 files, 661 lines

| Component | File | Lines | What it renders | Data source | Styling |
|-----------|------|-------|----------------|-------------|---------|
| TradePanel | `TradePanel.tsx` | 149 | 3-step trade modal (Search -> Order -> Confirm) | Finnhub + Supabase | Meridian |
| TickerSearch | `TickerSearch.tsx` | 89 | Stock search with autocomplete | Finnhub search API | Meridian |
| OrderEntry | `OrderEntry.tsx` | 169 | Quantity/price input + rule validation | Props | Meridian |
| OrderConfirmation | `OrderConfirmation.tsx` | 80 | Pre-submit trade review | Props | Meridian |
| TradeButton | `TradeButton.tsx` | 34 | Buy/Sell action button | Props | Meridian |
| PortfolioImpact | `PortfolioImpact.tsx` | 57 | Position % impact preview | Props | Meridian |
| RuleCheckList | `RuleCheckList.tsx` | 83 | Rule compliance checklist (15% max position, 40% sector) | Props | Meridian |

### Onboarding Components (`src/components/onboarding/`) — 8 files, 682 lines

| Component | File | Lines | What it renders | Styling |
|-----------|------|-------|----------------|---------|
| QuizSplash | `QuizSplash.tsx` | 43 | Intro screen before quiz | Meridian |
| TraderTypeStep | `TraderTypeStep.tsx` | 109 | 4 trader type options | Meridian |
| SectorStep | `SectorStep.tsx` | 93 | Multi-select sector checkboxes | Meridian |
| ScenarioStep | `ScenarioStep.tsx` | 93 | 3 market scenario options | Meridian |
| RiskStep | `RiskStep.tsx` | 96 | 4 risk tolerance options | Meridian |
| ExperienceStep | `ExperienceStep.tsx` | 96 | 4 experience level options | Meridian |
| ProfileReveal | `ProfileReveal.tsx` | 99 | Animated result reveal | Meridian |
| ProgressBar | `ProgressBar.tsx` | 53 | Step progress indicator | Meridian |

### Import Components (`src/components/import/`) — 4 files, 521 lines

| Component | File | Lines | What it renders | Styling |
|-----------|------|-------|----------------|---------|
| CsvUploader | `CsvUploader.tsx` | 171 | Drag-and-drop CSV upload zone | Meridian |
| ColumnMapper | `ColumnMapper.tsx` | 145 | Manual column mapping dropdowns | Meridian |
| ImportPreview | `ImportPreview.tsx` | 113 | Trade data preview table | Meridian |
| ImportSummary | `ImportSummary.tsx` | 92 | Import stats summary | Meridian |

### Intake Components (`src/components/intake/`) — 1 file, 297 lines

| Component | File | Lines | What it renders | Styling |
|-----------|------|-------|----------------|---------|
| IntakeForm | `IntakeForm.tsx` | 297 | Multi-step intake: Info -> Upload CSV -> Upload Screenshots -> Confirmation | Meridian |

### Guide Components (`src/components/guide/`) — 8 files, 627 lines

| Component | File | Lines | What it renders | Styling |
|-----------|------|-------|----------------|---------|
| GuidePanel | `GuidePanel.tsx` | 188 | Context-aware help sidebar | Meridian |
| GuideToggle | `GuideToggle.tsx` | 31 | Guide on/off switch | Meridian |
| LandingGuide | `LandingGuide.tsx` | 52 | Landing page help content | Meridian |
| DiscoverGuideExtra | `DiscoverGuideExtra.tsx` | 52 | Discover tab tips | Meridian |
| MirrorGuideExtra | `MirrorGuideExtra.tsx` | 76 | Mirror tab tips | Meridian |
| RulesTable | `RulesTable.tsx` | 96 | Trading rules reference table | Meridian |
| TierTable | `TierTable.tsx` | 91 | Tier/level info table | Meridian |
| WhatsNext | `WhatsNext.tsx` | 41 | Next steps prompt | Meridian |

### Card Components (`src/components/cards/`) — 4 files, 299 lines

| Component | File | Lines | What it renders | Data source | Styling |
|-----------|------|-------|----------------|-------------|---------|
| TickerCard | `TickerCard.tsx` | 112 | Stock card with price + buy button | Props (Finnhub data) | Meridian |
| PredictionCard | `PredictionCard.tsx` | 85 | Prediction market card | **MOCK** | Meridian |
| ThesisCard | `ThesisCard.tsx` | 61 | Trade thesis card | **MOCK** | Meridian |
| AchievementCard | `AchievementCard.tsx` | 41 | Achievement badge card | **MOCK** | Meridian |

### Gamification Components (`src/components/gamification/`) — 2 files, 83 lines

| Component | File | Lines | What it renders | Data source | Styling |
|-----------|------|-------|----------------|-------------|---------|
| StreakBanner | `StreakBanner.tsx` | 43 | Trading streak display | **MOCK** | Meridian |
| DailyChallenge | `DailyChallenge.tsx` | 40 | Daily challenge prompt | **MOCK** | Meridian |

### Chart Components (`src/components/charts/`) — 1 file, 127 lines

| Component | File | Lines | What it renders | Styling |
|-----------|------|-------|----------------|---------|
| RadarProfile | `RadarProfile.tsx` | 127 | 8-dimension radar chart (Recharts) | Meridian |

---

## Section 4: External Integrations

### 4.1 Supabase (Database + Storage)

| Aspect | Details |
|--------|---------|
| **Config** | `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` |
| **Client** | `src/lib/supabase.ts` (4 lines) |
| **Schema** | `src/lib/schema.sql` (162 lines) |
| **Migrations** | `supabase/migrations/20260217_parser_configs.sql`, `supabase/migrations/20260218_intake_tables.sql` |
| **Files using it** | `src/lib/db.ts`, `src/lib/intake.ts`, `src/lib/import-engine.ts`, `src/lib/trade-executor.ts`, `src/hooks/usePortfolio.ts`, `src/hooks/useProfile.ts`, `src/app/onboarding/page.tsx`, `src/app/dashboard/page.tsx`, `src/app/import/page.tsx` |
| **Storage bucket** | `trade-data` (CSV + screenshot uploads from intake) |
| **New vision?** | **KEEP** — profiles, trades, trade_imports tables all needed |

### 4.2 Clerk (Authentication)

| Aspect | Details |
|--------|---------|
| **Config** | `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY` + routing URLs |
| **Client** | `src/app/layout.tsx` (ClerkProvider), `src/middleware.ts` |
| **Protected routes** | Everything except `/`, `/sign-in`, `/sign-up`, `/onboarding`, `/intake` |
| **Files using it** | `src/app/layout.tsx`, `src/middleware.ts`, `src/components/layout/TopBar.tsx`, `src/hooks/usePortfolio.ts`, `src/hooks/useProfile.ts`, plus any component calling `useUser()` |
| **New vision?** | **REVIEW** — intake flow is public (no auth). If the new vision is intake-only, Clerk may be optional. Keep if authenticated profiles are needed. |

### 4.3 Anthropic / Claude API

| Aspect | Details |
|--------|---------|
| **Config** | `ANTHROPIC_API_KEY` (server-side only, currently empty in .env.local) |
| **NPM package** | `@anthropic-ai/sdk` v0.74.0 |
| **Files using it** | `src/app/api/classify-csv/route.ts` (Haiku), `src/app/api/analyze-trades/route.ts` (Sonnet) |
| **Also used in** | `services/behavioral-mirror/` (narrative generator, universal parser, screenshot extractor) |
| **New vision?** | **KEEP** — CSV classification and behavioral analysis both needed |

### 4.4 Finnhub (Market Data)

| Aspect | Details |
|--------|---------|
| **Config** | `NEXT_PUBLIC_FINNHUB_API_KEY` |
| **Client** | `src/lib/market-data.ts` (243 lines) with rate limiter |
| **Endpoints** | `/quote`, `/stock/profile2`, `/search`, `/stock/candle` |
| **Files using it** | `src/lib/market-data.ts`, `src/components/dashboard/DiscoverTab.tsx`, `src/components/trade/TickerSearch.tsx`, `src/app/dashboard/ticker/[symbol]/page.tsx` |
| **New vision?** | **REMOVE** — only needed for the simulator (live trading, stock pages). The behavioral mirror service uses yfinance instead. |

### 4.5 Railway (Behavioral Mirror Backend)

| Aspect | Details |
|--------|---------|
| **Config** | `NEXT_PUBLIC_RAILWAY_API_URL` = `https://yabo-production.up.railway.app` |
| **Client** | `src/lib/intake.ts` (299 lines) |
| **Endpoints** | `/analyze`, `/extract_screenshots`, `/health`, `/supported_formats` |
| **Files using it** | `src/lib/intake.ts`, `src/app/import/page.tsx`, `src/app/trading-dna/page.tsx` |
| **New vision?** | **KEEP** — core analysis engine |

### 4.6 yfinance (Market Data — Python backend)

| Aspect | Details |
|--------|---------|
| **Config** | No API key needed (free) |
| **Used in** | `services/behavioral-mirror/features/market_context.py`, `services/behavioral-mirror/extractor/timing.py` (via cached parquet) |
| **New vision?** | **KEEP** — needed for feature extraction (MA20, RSI, breakout detection) |

---

## Section 5: Supabase Schema

### Tables

| Table | Columns | Purpose | New vision? |
|-------|---------|---------|-------------|
| **profiles** | clerk_id, username, display_name, trader_type, sectors[], risk_tolerance, experience_level, scenario_choice, archetype, tier, rank_score, level, xp, streak, starting_capital, current_value, trait_entry_timing, trait_hold_discipline, trait_position_sizing, trait_conviction_accuracy, trait_risk_management, trait_sector_focus, trait_drawdown_resilience, trait_thesis_quality, ai_profile_text, ai_archetype_description, ai_key_stats (JSONB), ai_recommendations (JSONB), ai_analyzed_at, created_at, updated_at | User profile + behavioral traits + AI analysis | **KEEP** — store analysis results |
| **trades** | clerk_id, ticker, side, quantity, price, total_value, fees, sector, source, created_at, locked_at | Immutable trade log | **KEEP** — for simulator; REVIEW for intake-only |
| **positions** | clerk_id, ticker, shares, avg_cost, current_price, sector, conviction, updated_at | Current holdings (derived) | **REMOVE** — simulator only |
| **theses** | clerk_id, ticker, direction, entry_price, target_price, stop_price, conviction, body, ai_signal_score, ai_signal_reasoning, thesis_quality_score, status, votes, expires_at | Social trading ideas | **REMOVE** — simulator only |
| **predictions** | question, category, yes_probability, total_votes, hot, resolves_at | Prediction market | **REMOVE** — simulator only |
| **prediction_votes** | clerk_id, prediction_id, vote | User votes | **REMOVE** — simulator only |
| **traders** | name, email, phone, brokerage, referred_by, status | Intake form submissions | **KEEP** — core intake flow |
| **trade_imports** | trader_id, source_type, brokerage_detected, raw_result (JSONB), status, trade_count, profile_id, error | Import tracking | **KEEP** — tracks analysis jobs |
| **parser_configs** | config_id, format_name, header_signature, config_json (JSONB), source, confidence, times_used, version | CSV parser self-learning configs | **KEEP** — improves parser over time |

### Storage Buckets

| Bucket | Path pattern | Purpose | New vision? |
|--------|-------------|---------|-------------|
| `trade-data` | `intake/{trader_id}/{file}` | CSV uploads | **KEEP** |
| `trade-data` | `intake/{trader_id}/screenshots/{file}` | Screenshot uploads | **KEEP** |

### RLS Policies

- **profiles**: Public SELECT, authenticated INSERT/UPDATE
- **trades**: Public SELECT, authenticated INSERT
- **positions**: Public SELECT, authenticated INSERT/UPDATE
- **theses/predictions/prediction_votes**: Public SELECT, authenticated INSERT
- **traders/trade_imports**: Anonymous INSERT (no auth needed for intake)

---

## Section 6: Reusable Logic

### CSV Parsing & Normalization
| File | Lines | What it does | Keep? |
|------|-------|-------------|-------|
| `services/behavioral-mirror/ingestion/universal_parser.py` | ~380 | Multi-strategy CSV parser: known formats -> Claude fallback -> legacy | **KEEP** |
| `services/behavioral-mirror/extractor/csv_parsers.py` | ~830 | Format-specific parsers (Trading212, Robinhood, Schwab, Wells Fargo, generic) | **KEEP** |
| `src/lib/trading-dna-parser.ts` | 507 | Frontend 3-layer CSV parser (auto-detect -> Claude classify -> manual map) | **KEEP** |
| `src/app/api/classify-csv/route.ts` | 159 | Claude-powered CSV column detection API | **KEEP** |

### Supabase Client & Helpers
| File | Lines | What it does | Keep? |
|------|-------|-------------|-------|
| `src/lib/supabase.ts` | 4 | Supabase client singleton | **KEEP** |
| `src/lib/db.ts` | 200 | Profile CRUD, onboarding save, archetype computation | **KEEP** (extract profile logic) |
| `src/lib/intake.ts` | 299 | Railway API integration, background CSV/screenshot processing | **KEEP** |

### Railway API Integration
| File | Lines | What it does | Keep? |
|------|-------|-------------|-------|
| `src/lib/intake.ts` | 299 | Full intake pipeline: upload -> Railway -> save results | **KEEP** |

### Meridian Design Tokens
| File | Lines | What it does | Keep? |
|------|-------|-------------|-------|
| `src/app/globals.css` | 107 | CSS variables, base styles | **KEEP** |
| `src/app/layout.tsx` | 104 | Font imports (Newsreader, Inter, IBM Plex Mono), ClerkProvider theme | **KEEP** |

Colors used throughout (from Clerk theme + Tailwind classes):
- Background: `#FAF8F4` (warm off-white)
- Text: `#1A1715` (near-black warm)
- Secondary: `#8A8580` (warm gray)
- Input bg: `#F3F0EA` (light warm)
- Borders: typically `border-[#E8E4DE]`
- Accent: `#D4AF37` (gold)

### Shared Utilities
| File | Lines | What it does | Keep? |
|------|-------|-------------|-------|
| `src/lib/trade-analytics.ts` | 335 | Win rate, hold time, sector analysis, drawdown calc | **KEEP** (useful for profile page) |
| `src/lib/analyze.ts` | 130 | Orchestrates AI analysis flow | **KEEP** |
| `src/lib/mock-data.ts` | 379 | Mock trades, positions, profiles for demo | **REVIEW** |

### Authentication
| File | Lines | What it does | Keep? |
|------|-------|-------------|-------|
| `src/middleware.ts` | 22 | Clerk route protection | **REVIEW** — depends on whether auth is needed |

---

## Section 7: Dependency Map

| Package | Version | Verdict | Reason |
|---------|---------|---------|--------|
| `next` | 14.2.35 | **KEEP** | Framework |
| `react` | 18.3.1 | **KEEP** | UI library |
| `react-dom` | 18.3.1 | **KEEP** | DOM rendering |
| `@supabase/supabase-js` | 2.95.3 | **KEEP** | Database |
| `@anthropic-ai/sdk` | 0.74.0 | **KEEP** | CSV classification + trade analysis |
| `@clerk/nextjs` | 6.37.4 | **REVIEW** | Auth — needed if profiles require login |
| `@clerk/themes` | 2.4.52 | **REVIEW** | Clerk theming — goes with Clerk |
| `recharts` | 3.7.0 | **REVIEW** | Used only for RadarProfile chart in MirrorTab. Could keep for profile page or replace. |
| `lucide-react` | 0.564.0 | **KEEP** | Icons throughout the app |
| `tailwindcss` | 4.1.18 | **KEEP** | Styling |
| `@tailwindcss/postcss` | 4.1.18 | **KEEP** | Build tooling |
| `typescript` | 5.9.3 | **KEEP** | Type safety |
| `autoprefixer` | 10.4.24 | **KEEP** | CSS compatibility |
| `postcss` | 8.5.6 | **KEEP** | CSS processing |

No packages to **REMOVE** from package.json. Finnhub has no npm dependency — it's called via raw fetch in `src/lib/market-data.ts`.

---

## Section 8: Cleanup Recommendation

### REMOVE ENTIRELY

These files serve only the old simulator (simulated trading with fake $100K, live stock pages, social features, gamification). They have no role in the intake + profile product.

| # | File | Lines | Reason |
|---|------|-------|--------|
| 1 | `src/lib/market-data.ts` | 243 | Finnhub API client — simulator only |
| 2 | `src/lib/trade-executor.ts` | 116 | Execute simulated buy/sell trades |
| 3 | `src/lib/import-engine.ts` | 139 | Import trades into simulator portfolio |
| 4 | `src/lib/mock-data.ts` | 379 | Mock trades/positions for simulator demo |
| 5 | `src/app/dashboard/page.tsx` | 356 | Main 7-tab simulator dashboard |
| 6 | `src/app/dashboard/layout.tsx` | 7 | Dashboard layout wrapper |
| 7 | `src/app/dashboard/import/page.tsx` | 523 | Dashboard CSV import (feeds simulator) |
| 8 | `src/app/dashboard/ticker/[symbol]/page.tsx` | 469 | Live stock detail page |
| 9 | `src/components/layout/Sidebar.tsx` | 212 | Simulator navigation sidebar |
| 10 | `src/components/layout/TopBar.tsx` | 59 | Simulator top bar |
| 11 | `src/components/dashboard/DiscoverTab.tsx` | 260 | Stock discovery (Finnhub) |
| 12 | `src/components/dashboard/RoomTab.tsx` | 126 | Social chat (mock) |
| 13 | `src/components/dashboard/PredictTab.tsx` | 107 | Prediction market (mock) |
| 14 | `src/components/dashboard/BoardTab.tsx` | 117 | Leaderboard (mock) |
| 15 | `src/components/dashboard/StrategyTab.tsx` | 80 | Strategy rules (mock) |
| 16 | `src/components/dashboard/MovesTab.tsx` | 51 | Activity feed (mock) |
| 17 | `src/components/dashboard/PositionsList.tsx` | 56 | Portfolio positions table |
| 18 | `src/components/dashboard/RecentTrades.tsx` | 54 | Trade history list |
| 19 | `src/components/trade/TradePanel.tsx` | 149 | Trade entry modal |
| 20 | `src/components/trade/TickerSearch.tsx` | 89 | Stock search autocomplete |
| 21 | `src/components/trade/OrderEntry.tsx` | 169 | Order input form |
| 22 | `src/components/trade/OrderConfirmation.tsx` | 80 | Trade confirmation step |
| 23 | `src/components/trade/TradeButton.tsx` | 34 | Buy/sell button |
| 24 | `src/components/trade/PortfolioImpact.tsx` | 57 | Position impact preview |
| 25 | `src/components/trade/RuleCheckList.tsx` | 83 | Rule compliance check |
| 26 | `src/components/cards/PredictionCard.tsx` | 85 | Prediction card |
| 27 | `src/components/cards/ThesisCard.tsx` | 61 | Thesis card |
| 28 | `src/components/cards/AchievementCard.tsx` | 41 | Achievement badge |
| 29 | `src/components/gamification/StreakBanner.tsx` | 43 | Trading streak |
| 30 | `src/components/gamification/DailyChallenge.tsx` | 40 | Daily challenge |
| 31 | `src/components/guide/GuidePanel.tsx` | 188 | Help panel (simulator-specific) |
| 32 | `src/components/guide/GuideToggle.tsx` | 31 | Guide toggle button |
| 33 | `src/components/guide/LandingGuide.tsx` | 52 | Landing page guide |
| 34 | `src/components/guide/DiscoverGuideExtra.tsx` | 52 | Discover tab guide |
| 35 | `src/components/guide/MirrorGuideExtra.tsx` | 76 | Mirror tab guide |
| 36 | `src/components/guide/RulesTable.tsx` | 96 | Trading rules table |
| 37 | `src/components/guide/TierTable.tsx` | 91 | Tier info table |
| 38 | `src/components/guide/WhatsNext.tsx` | 41 | Next steps prompt |
| 39 | `src/hooks/usePortfolio.ts` | 66 | Portfolio data hook (simulator) |

**Total to remove: 39 files, ~4,877 lines**

### KEEP AS-IS

These files serve the new vision (intake + analysis + profile) and work correctly.

| # | File | Lines | What it does |
|---|------|-------|-------------|
| 1 | `src/app/layout.tsx` | 104 | Root layout, fonts, ClerkProvider |
| 2 | `src/app/intake/page.tsx` | 68 | Intake landing page |
| 3 | `src/app/intake/layout.tsx` | 15 | Intake layout |
| 4 | `src/app/sign-in/[[...sign-in]]/page.tsx` | 12 | Sign in |
| 5 | `src/app/sign-up/[[...sign-up]]/page.tsx` | 12 | Sign up |
| 6 | `src/app/api/classify-csv/route.ts` | 159 | CSV column detection (Claude) |
| 7 | `src/app/api/analyze-trades/route.ts` | 287 | Behavioral analysis (Claude) |
| 8 | `src/app/api/setup-db/route.ts` | 62 | DB schema init |
| 9 | `src/lib/supabase.ts` | 4 | Supabase client |
| 10 | `src/lib/db.ts` | 200 | Profile CRUD + archetype logic |
| 11 | `src/lib/intake.ts` | 299 | Railway pipeline integration |
| 12 | `src/lib/analyze.ts` | 130 | Analysis orchestration |
| 13 | `src/lib/trade-analytics.ts` | 335 | Trade metric calculations |
| 14 | `src/lib/schema.sql` | 162 | Database schema |
| 15 | `src/middleware.ts` | 22 | Auth route protection |
| 16 | `src/app/globals.css` | 107 | Global styles |
| 17 | `src/types/index.ts` | 169 | Type definitions |
| 18 | `src/hooks/useProfile.ts` | 34 | Profile data hook |
| 19 | `src/components/intake/IntakeForm.tsx` | 297 | Intake form component |
| 20 | `src/components/import/CsvUploader.tsx` | 171 | CSV upload zone |
| 21 | `src/components/import/ColumnMapper.tsx` | 145 | Column mapping UI |
| 22 | `src/components/import/ImportPreview.tsx` | 113 | Trade preview table |
| 23 | `src/components/import/ImportSummary.tsx` | 92 | Import summary |
| 24 | `src/components/ui/Badge.tsx` | 25 | Badge component |
| 25 | `src/components/ui/Card.tsx` | 22 | Card component |
| 26 | `src/components/ui/StatCard.tsx` | 24 | Stat card |
| 27 | `src/components/ui/TraitBar.tsx` | 69 | Trait score bar |
| 28 | `src/components/ui/AccentLine.tsx` | 11 | Decorative line |
| 29 | `src/components/charts/RadarProfile.tsx` | 127 | Radar chart |
| 30 | `supabase/migrations/*.sql` | ~120 | DB migrations |
| 31 | `services/behavioral-mirror/**` | 18,416 | Entire backend service |

**Total to keep: 31 entries, ~21,400+ lines** (including backend)

### REPURPOSE

These files have useful logic but need changes to fit the new vision.

| # | File | Lines | Useful logic | What needs to change |
|---|------|-------|-------------|---------------------|
| 1 | `src/app/page.tsx` | 258 | Landing page structure, Meridian styling | Replace marketing copy with intake-focused messaging. Remove fake stats. |
| 2 | `src/app/onboarding/page.tsx` | 289 | Multi-step quiz flow, progress tracking | Adapt questions for intake context. Could become the post-upload questionnaire. |
| 3 | `src/components/onboarding/*.tsx` | 682 | Step components, auto-advance, animations | Re-theme for intake. Modify questions to match new product. |
| 4 | `src/app/trading-dna/page.tsx` | 911 | Full analysis display, CSV 3-layer parser, profile rendering | Extract into a standalone `/profile/[id]` page. Remove upload logic (moved to intake). |
| 5 | `src/app/import/page.tsx` | 969 | Screenshot upload, Railway integration, progress UI | Merge best parts into IntakeForm. Currently duplicates intake logic. |
| 6 | `src/lib/trading-dna-parser.ts` | 507 | 3-layer CSV detection (auto -> Claude -> manual) | Move to shared lib. Currently tightly coupled to trading-dna page state. |
| 7 | `src/components/dashboard/MirrorTab.tsx` | 322 | Trait display, radar chart integration, archetype card | Extract into standalone ProfileCard component for the profile page. |
| 8 | `src/components/cards/TickerCard.tsx` | 112 | Card layout pattern | Remove Finnhub dependency. Could be repurposed as generic data card. |
| 9 | `src/components/ui/MockDataBadge.tsx` | 25 | Dev-mode indicator | May be useful during development of new features. |
| 10 | `src/components/ui/LiveDot.tsx` | 18 | Status indicator | Repurpose for analysis job status. |
| 11 | `src/components/ui/Sparkline.tsx` | 28 | Mini chart | Could show trait trend over time. |
| 12 | `src/components/ui/TierBadge.tsx` | 31 | Badge variant | Repurpose for archetype badge. |
| 13 | `src/components/ui/SignalBadge.tsx` | 28 | Status chip | Repurpose for profile status. |
| 14 | `src/components/ui/ConvictionBar.tsx` | 28 | Horizontal bar | Repurpose for trait visualization. |

**Total to repurpose: 14 files, ~4,208 lines**

---

## Summary

| Metric | Value |
|--------|-------|
| **Total frontend source files** | 96 |
| **Total frontend lines** | 13,196 |
| **Backend Python files** | 53 |
| **Backend Python lines** | 18,416 |
| **Total project lines** | ~31,600 |
| | |
| **Files to REMOVE** | 39 (41% of frontend files) |
| **Lines to remove** | ~4,877 (37% of frontend lines) |
| **Files to KEEP** | 31 entries (+ entire backend) |
| **Lines to keep** | ~21,400+ |
| **Files to REPURPOSE** | 14 |
| **Lines to repurpose** | ~4,200 |
| | |
| **Estimated cleanup effort** | **MEDIUM** — Most removals are clean deletes of self-contained simulator components. The repurposing work (extracting MirrorTab into ProfileCard, merging import flows, cleaning landing page) is the real effort. Backend stays untouched. |

### Key Architectural Decision Points

1. **Clerk auth**: Keep or remove? If the product is purely intake (no login required), Clerk can go. If users need to see their profile later, keep it.
2. **Dashboard route**: The entire `/dashboard` tree is simulator. If any dashboard is needed for the new vision, build it fresh rather than surgically removing tabs.
3. **Two import flows**: `/import` and `/dashboard/import` overlap significantly. Consolidate into the IntakeForm component.
4. **Trading DNA page**: Contains the best analysis display code. Extract and move to a profile page.
5. **Finnhub**: Zero files in the new vision need it. The `NEXT_PUBLIC_FINNHUB_API_KEY` env var and `market-data.ts` can be removed completely.
