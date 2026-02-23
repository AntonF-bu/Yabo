# Yabo

Behavioral financial intelligence platform. Analyzes trading activity to build behavioral profiles — revealing **how** someone trades, not just **what** they hold.

Built as the data engine behind the **Meridian** advisory intake system: financial advisors upload a client's brokerage export, and within minutes get a structured behavioral dossier with portfolio analytics, a 212-feature behavioral fingerprint, and AI-generated narrative insights.

---

## How We Got Here

**Phase 1 — Trading Simulator (Jan 2026)**
Started as a gamified paper trading platform: leaderboards, streaks, daily challenges, live market data via Finnhub. Users could practice trading with fake money and compete.

**Phase 2 — Behavioral Mirror (Feb 2026)**
Realized the simulator wasn't the product — *understanding trader behavior* was. Pivoted to building a behavioral analysis engine. Users upload their real brokerage CSV exports and get a multi-dimensional behavioral profile. Built the 212-feature extraction engine, 8-dimension behavioral classifier, and Claude-powered narrative generation.

**Phase 3 — Meridian Advisory Intake (Current)**
Repositioned the technology for B2B: financial advisors use Yabo to onboard new clients. Instead of spending hours in intake meetings asking "so what do you invest in?", the advisor uploads the client's brokerage statement and gets a complete picture — portfolio composition, behavioral tendencies, risk patterns, tax optimization opportunities — before the first conversation.

The old simulator UI (Room, Board, trading game) is still in the frontend but is no longer the product focus. The active product is the intake flow (`/intake`), the behavioral analysis pipeline (`/trading-dna`), and the profile dossier page.

---

## Tech Stack

### Frontend
| Technology | Version | Purpose |
|-----------|---------|---------|
| Next.js | 14.2 | React framework, SSR, routing |
| React | 18.3 | UI components |
| TypeScript | 5.9 | Type safety |
| Tailwind CSS | 4.1 | Styling |
| Clerk | 6.37 | Authentication (sign-in, sign-up, user context) |
| Supabase JS | 2.95 | Database client |
| Recharts | 3.7 | Chart visualizations (radar, bar, line) |
| Lucide | 0.564 | Icon library |

### Backend (Behavioral Mirror Service)
| Technology | Purpose |
|-----------|---------|
| Python 3.11 | Runtime |
| FastAPI | API framework |
| Pandas / NumPy / SciPy | Data processing, feature engineering |
| scikit-learn | Behavioral classification |
| yfinance | Live equity/ETF pricing (free) |
| Polygon.io API | Live options pricing with Greeks ($29/mo Starter plan) |
| Anthropic Claude API | CSV format classification (Haiku) + narrative analysis (Sonnet) |
| Supabase Python SDK | Database access |

### Infrastructure
| Service | Role |
|---------|------|
| **Vercel** | Frontend hosting (auto-deploy from `main`) |
| **Railway** | Backend hosting (Docker, auto-deploy on push) |
| **Supabase** | PostgreSQL database + file storage (Storage bucket: `trade-data`) |

---

## Repository Structure

```
yabo/
├── src/                          # Next.js frontend
│   ├── app/                      #   Page routes (dashboard, intake, trading-dna, import)
│   ├── components/               #   React components (90+)
│   └── lib/                      #   Supabase client, sector maps, design tokens
├── backend/                      # Shared Python modules (imported by behavioral-mirror)
│   ├── parsers/                  #   CSV parsing, instrument classification, holdings reconstruction
│   ├── analyzers/                #   Portfolio analyzer, price resolver (yfinance + Polygon)
│   └── tests/                    #   Unit tests
├── services/
│   └── behavioral-mirror/        # FastAPI backend service (runs on Railway)
│       ├── api.py                #   Main endpoint: POST /process-upload
│       ├── features/             #   212-feature extraction engine
│       ├── narrative/            #   Claude prompt engineering for behavioral narratives
│       ├── parsing/              #   Strategy detection, completeness assessment
│       ├── services/             #   Market data service, ticker resolution
│       ├── storage/              #   Supabase client wrapper
│       ├── data/                 #   Tax jurisdictions, config (gitignored caches)
│       └── _deprecated/          #   Old classifier/extractor code (kept for reference)
├── supabase/
│   └── migrations/               # SQL schema (V2: 8 tables)
├── tools/
│   └── trader-generator/         # Synthetic test data generator (dev tool)
└── docs/
    └── CODEBASE_AUDIT.md         # Detailed codebase documentation
```

---

## Database Schema (V2)

8 core tables in Supabase (PostgreSQL):

| Table | Purpose |
|-------|---------|
| `profiles_new` | One row per trader/client. Profile ID (D001, R010), name, brokerage, tax jurisdiction, accounts (JSONB). |
| `uploads` | Every file that enters the system. Tracks status: uploaded → classifying → processing → completed. |
| `trades_new` | Normalized trade records. One row per trade: date, side, ticker, quantity, price, instrument type. |
| `holdings` | Reconstructed position snapshots: ticker, quantity, cost_basis, market_value (live-priced), unrealized P&L. |
| `income` | Dividends, interest, coupon payments extracted from statements. |
| `fees` | Advisory fees, commissions, withholdings. |
| `analysis_results` | All computed output: 212-feature vectors, 8-dimension behavioral scores, AI narrative. |
| `format_signatures` | Learned brokerage file formats (Wells Fargo, Schwab, etc.) for auto-detection on future uploads. |

Full schema: `supabase/migrations/20260219_schema_v2.sql`

---

## Core Pipeline

```
CSV Upload → Format Detection → Parsing → Normalized Tables
                                              ↓
                                   Feature Extraction (212 features)
                                              ↓
                                   Behavioral Classification (8 dimensions)
                                              ↓
                                   Portfolio Analysis (live pricing, allocation, sector exposure)
                                              ↓
                                   Narrative Generation (Claude Sonnet)
                                              ↓
                                   Dossier / Profile Page
```

**212 Features** across 12 categories: timing, entry strategy, exit behavior, position sizing, holding periods, instrument mix, sector allocation, psychology (revenge trading, freeze, emotional index), learning trajectory, risk management, bias detection, and social/herd behavior.

**8 Behavioral Dimensions** (each scored 20-95):
1. Active ↔ Passive
2. Momentum ↔ Value
3. Concentrated ↔ Diversified
4. Disciplined ↔ Emotional
5. Sophisticated ↔ Simple
6. Improving ↔ Declining
7. Independent ↔ Herd
8. Risk Seeking ↔ Risk Averse

**Live Pricing** via unified price resolver (`backend/analyzers/price_resolver.py`):
- Equities/ETFs: yfinance with parquet caching (1-day TTL)
- Options: Polygon.io snapshot API with Greeks (bid/ask/mid, delta/gamma/theta/vega, IV, open interest)
- Bonds: par value; structured products: cost basis; cash/money market: nominal

---

## Local Development

### Prerequisites
- Node.js 18+
- Python 3.11+
- Supabase project (or local Supabase CLI)

### Frontend
```bash
npm install
cp .env.example .env.local   # Fill in your keys
npm run dev                   # http://localhost:3000
```

### Backend
```bash
cd services/behavioral-mirror
pip install -r requirements.txt
export SUPABASE_URL=...
export SUPABASE_SERVICE_KEY=...
export ANTHROPIC_API_KEY=...
export POLYGON_API_KEY=...    # Optional: enables live options pricing
uvicorn api:app --reload --port 8000
```

### Tests
```bash
# Price resolver tests (from repo root)
python -m pytest backend/tests/test_price_resolver.py -v

# Full pipeline test with a CSV
python -m backend.tests.test_wfa_parser backend/test-data/your_file.csv
```

---

## Deployment

**Frontend** deploys to Vercel automatically on push to `main`.

**Backend** deploys to Railway automatically. The Dockerfile copies both `services/behavioral-mirror/` and `backend/` into the container. Railway watches both directories for changes.

Environment variables required on Railway:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `ANTHROPIC_API_KEY`
- `POLYGON_API_KEY` (optional — without it, options fall back to transaction prices)

---

## API Endpoints

The backend exposes a single main endpoint:

```
POST /process-upload
Body: { "upload_id": "uuid" }
```

This triggers the full pipeline: download file from Supabase Storage → detect format → parse → write normalized data → extract features → run analysis → store results.

Supporting endpoints:
- `GET /health` — Health check (used by Railway)
- `POST /reprocess` — Re-run analysis on existing data
- `GET /analysis/{profile_id}` — Fetch analysis results

---

## External API Dependencies

| API | Required? | Cost | Used For |
|-----|-----------|------|----------|
| Supabase | Yes | Free tier sufficient | Database + file storage |
| Clerk | Yes | Free tier sufficient | Authentication |
| Anthropic Claude | Yes | Pay-per-use | CSV classification + behavioral narrative |
| Finnhub | Optional | Free tier | Live quotes on ticker detail pages |
| yfinance | Bundled (free) | Free | Equity/ETF pricing for portfolio valuation |
| Polygon.io | Optional | $29/mo Starter | Live options pricing with Greeks |
