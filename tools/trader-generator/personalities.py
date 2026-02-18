"""
Generates unique trader personalities using structured randomization.
Each trader is a dictionary with no archetype labels — just continuous
behavioural sliders and life-context fields that drive the simulator.
"""

import math
import random
from typing import List, Dict, Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

JOB_SECTORS = [
    "tech", "healthcare", "finance", "retail", "trades",
    "student", "retired", "creative", "legal", "government",
    "military", "food_service",
]

DISCOVERY_SOURCES = [
    "reddit", "tiktok", "friend", "self_directed",
    "newsletter", "financial_advisor",
]

TIME_AVAILABILITY_LEVELS = [
    "very_low", "low", "medium", "high", "full_time",
]

# Sector -> tickers that someone in that sector would overweight
SECTOR_TICKERS = {
    "tech":        ["AAPL", "MSFT", "NVDA", "AMD", "CRM", "ADBE", "INTC", "PLTR", "NET", "SNOW"],
    "healthcare":  ["JNJ", "PFE", "UNH", "ABBV", "MRK", "LLY", "AMGN", "MRNA", "ISRG", "DXCM"],
    "finance":     ["JPM", "GS", "BAC", "BRK-B", "V", "MA", "SCHW", "BLK", "C", "MS"],
    "retail":      ["WMT", "COST", "TGT", "HD", "LOW", "AMZN", "SBUX", "NKE", "DG", "ETSY"],
    "trades":      ["CAT", "DE", "SHW", "VMC", "MLM", "URI", "PWR", "EME", "FIX", "APH"],
    "student":     ["AAPL", "TSLA", "AMZN", "DIS", "NFLX", "RBLX", "SPOT", "SNAP", "U", "COIN"],
    "retired":     ["JNJ", "PG", "KO", "PEP", "VZ", "T", "MO", "XOM", "CVX", "O"],
    "creative":    ["DIS", "NFLX", "SPOT", "ROKU", "WBD", "PARA", "RBLX", "U", "SNAP", "PINS"],
    "legal":       ["MSFT", "GOOGL", "LMT", "RTX", "NOC", "GD", "BAH", "LDOS", "ACN", "IT"],
    "government":  ["LMT", "RTX", "NOC", "GD", "BAH", "LDOS", "MSFT", "ORCL", "PANW", "CRWD"],
    "military":    ["LMT", "RTX", "NOC", "GD", "BA", "HII", "TXT", "LHX", "KTOS", "PLTR"],
    "food_service": ["MCD", "SBUX", "CMG", "DPZ", "YUM", "DNUT", "WING", "CAVA", "SHAK", "QSR"],
}

MEGA_CAPS = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "GOOGL", "META"]

SPECULATIVE_TICKERS = [
    "GME", "AMC", "RIVN", "PLTR", "SMCI", "MSTR", "ARM",
    "SOFI", "LCID", "NIO", "COIN", "HOOD", "DKNG", "IONQ",
]

ETFS = ["SPY", "QQQ", "XLK", "XLV", "XLE", "ARKK", "VTI", "IWM", "GLD", "TLT"]

# Trending tickers by rough quarter for FOMO events
TRENDING_BY_PERIOD = {
    "2023-Q3": ["NVDA", "ARM", "TSLA", "META"],
    "2023-Q4": ["MSFT", "GOOGL", "SMCI", "MSTR"],
    "2024-Q1": ["NVDA", "SMCI", "ARM", "MSTR"],
    "2024-Q2": ["GME", "AMC", "NVDA", "PLTR"],
    "2024-Q3": ["NVDA", "TSLA", "SMCI", "PLTR"],
    "2024-Q4": ["PLTR", "MSTR", "TSLA", "IONQ"],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _log_normal_account(rng: random.Random, median: float = 25_000,
                        sigma: float = 1.0) -> float:
    """Log-normal account size, clamped to [2_000, 500_000]."""
    raw = rng.lognormvariate(math.log(median), sigma)
    return max(2_000.0, min(500_000.0, round(raw, 2)))


def _build_watchlist(rng: random.Random, personality: Dict[str, Any]) -> List[str]:
    """Build a trader's core watchlist (5-15 tickers)."""
    tickers = set()

    # 1) Sector-familiar tickers
    for sector in personality["familiar_sectors"]:
        sector_pool = SECTOR_TICKERS.get(sector, [])
        n = rng.randint(2, min(4, len(sector_pool)))
        tickers.update(rng.sample(sector_pool, n))

    # 2) Some mega caps
    n_mega = rng.randint(1, 3)
    tickers.update(rng.sample(MEGA_CAPS, n_mega))

    # 3) Speculative names
    n_spec = rng.randint(1, 3)
    tickers.update(rng.sample(SPECULATIVE_TICKERS, n_spec))

    # 4) ETFs based on experience / instrument comfort
    if personality["instrument_comfort"]["etfs"] > rng.random():
        n_etf = rng.randint(1, 4)
        tickers.update(rng.sample(ETFS, n_etf))

    # Trim to 5-15
    tickers = list(tickers)
    rng.shuffle(tickers)
    size = rng.randint(5, 15)
    return tickers[:size]


# ---------------------------------------------------------------------------
# Life events
# ---------------------------------------------------------------------------

def _generate_life_events(rng: random.Random,
                          personality: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate life events placed across the 18-month simulation window."""
    events: List[Dict[str, Any]] = []

    # vacation_gaps: 1-3 gaps of 5-15 trading days
    n_vacations = rng.randint(1, 3)
    for _ in range(n_vacations):
        # day offset from start of sim (0 = 2023-06-01, ~390 trading days total)
        start_offset = rng.randint(0, 370)
        duration = rng.randint(5, 15)
        events.append({
            "type": "vacation_gap",
            "start_day_offset": start_offset,
            "duration_days": duration,
        })

    # bonus_deposit: 1-2 sudden account bumps (10-50% of account)
    n_bonus = rng.randint(1, 2)
    for _ in range(n_bonus):
        day_offset = rng.randint(10, 380)
        bump_pct = rng.uniform(0.10, 0.50)
        events.append({
            "type": "bonus_deposit",
            "day_offset": day_offset,
            "bump_pct": bump_pct,
        })

    # tax_loss_harvesting: 40% chance, placed in December
    if rng.random() < 0.40:
        # December 2023 or December 2024
        year = rng.choice([2023, 2024])
        events.append({
            "type": "tax_loss_harvesting",
            "year": year,
        })

    # new_years_resolution: 30% chance of discipline spike in January
    if rng.random() < 0.30:
        year = rng.choice([2024])  # only Jan 2024 falls in window
        events.append({
            "type": "new_years_resolution",
            "year": year,
            "duration_days": rng.randint(10, 30),
        })

    # fomo_events: 2-5 moments chasing trending ticker
    n_fomo = rng.randint(2, 5)
    for _ in range(n_fomo):
        day_offset = rng.randint(0, 380)
        events.append({
            "type": "fomo_event",
            "day_offset": day_offset,
        })

    # burnout: 20% chance, 4-8 weeks dramatically reduced activity after big loss
    if rng.random() < 0.20:
        day_offset = rng.randint(30, 350)
        duration = rng.randint(20, 40)  # 4-8 weeks in trading days
        events.append({
            "type": "burnout",
            "start_day_offset": day_offset,
            "duration_days": duration,
        })

    return events


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_personality(rng: random.Random, trader_id: int) -> Dict[str, Any]:
    """Generate a single trader personality dictionary."""
    age = rng.randint(19, 65)
    job_sector = rng.choice(JOB_SECTORS)
    experience_years = rng.randint(0, 15)

    # Risk tolerance influenced by age
    age_risk_factor = 1.0 - (age - 19) / (65 - 19) * 0.3  # younger = slightly more risk

    risk_appetite = _clamp(rng.gauss(0.5, 0.2) * age_risk_factor)

    # Instrument comfort — experience and risk drive options access
    exp_factor = experience_years / 15.0
    options_calls = _clamp(rng.uniform(0.0, 0.4) * (0.3 + 0.7 * exp_factor) *
                           (0.5 + 0.5 * risk_appetite))
    options_puts = _clamp(rng.uniform(0.0, 0.2) * (0.3 + 0.7 * exp_factor))

    account_size = _log_normal_account(rng)

    personality: Dict[str, Any] = {
        "trader_id": trader_id,
        # Identity
        "age": age,
        "job_sector": job_sector,
        "account_size": account_size,
        "experience_years": experience_years,
        "time_availability": rng.choice(TIME_AVAILABILITY_LEVELS),
        "discovery_source": rng.choice(DISCOVERY_SOURCES),

        # Behavioural sliders (0.0 – 1.0)
        "patience": _clamp(rng.gauss(0.5, 0.22)),
        "risk_appetite": risk_appetite,
        "conviction": _clamp(rng.gauss(0.5, 0.22)),
        "loss_aversion": _clamp(rng.gauss(0.5, 0.22)),
        "fomo_susceptibility": _clamp(rng.gauss(0.45, 0.22)),
        "discipline": _clamp(rng.gauss(0.5, 0.22)),
        "overconfidence_after_wins": _clamp(rng.gauss(0.4, 0.22)),
        "revenge_trade_tendency": _clamp(rng.gauss(0.35, 0.22)),

        # Instrument comfort (probabilities)
        "instrument_comfort": {
            "individual_stocks": 1.0,
            "etfs": _clamp(rng.uniform(0.5, 0.9)),
            "options_calls": options_calls,
            "options_puts": options_puts,
            "fractional_shares": _clamp(
                rng.uniform(0.3, 0.7) + (0.2 if account_size < 10_000 else 0.0)
            ),
        },

        # Sector familiarity
        "familiar_sectors": _pick_familiar_sectors(rng, job_sector),
    }

    # Stock universe
    personality["core_watchlist"] = _build_watchlist(rng, personality)

    # Life events
    personality["life_events"] = _generate_life_events(rng, personality)

    return personality


def _pick_familiar_sectors(rng: random.Random, job_sector: str) -> List[str]:
    """Pick 1-3 sectors the trader overweights, always including their job sector."""
    sectors = [job_sector]
    others = [s for s in JOB_SECTORS if s != job_sector]
    extras = rng.randint(0, 2)
    if extras:
        sectors.extend(rng.sample(others, extras))
    return sectors


def generate_traders(count: int, seed: int = 42) -> List[Dict[str, Any]]:
    """Generate *count* traders, enforcing ≤30% watchlist overlap between any pair."""
    rng = random.Random(seed)
    traders: List[Dict[str, Any]] = []

    for i in range(count):
        for _attempt in range(10):  # retry up to 10 times for overlap constraint
            p = generate_personality(rng, trader_id=i + 1)
            if _watchlist_overlap_ok(p, traders):
                traders.append(p)
                break
        else:
            # If 10 retries fail, accept the last one — hard constraint with many traders
            traders.append(p)

    return traders


def _watchlist_overlap_ok(candidate: Dict[str, Any],
                          existing: List[Dict[str, Any]],
                          max_overlap: float = 0.30) -> bool:
    """Check that candidate watchlist overlaps ≤30% with every existing trader."""
    cand_set = set(candidate["core_watchlist"])
    for other in existing:
        other_set = set(other["core_watchlist"])
        union_size = len(cand_set | other_set)
        if union_size == 0:
            continue
        overlap = len(cand_set & other_set) / union_size
        if overlap > max_overlap:
            return False
    return True


def get_all_tickers(traders: List[Dict[str, Any]]) -> List[str]:
    """Collect the full universe of tickers across all traders."""
    tickers = set()
    for t in traders:
        tickers.update(t["core_watchlist"])
    # Always include benchmark
    tickers.add("SPY")
    # Include trending tickers for FOMO events
    for period_tickers in TRENDING_BY_PERIOD.values():
        tickers.update(period_tickers)
    return sorted(tickers)
