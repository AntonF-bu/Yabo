"""Generate 75 synthetic trader profiles with intentional variety."""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

TAX_RATES: dict[str, float] = {
    "CA": 0.333, "TX": 0.20, "FL": 0.20, "NY": 0.315,
    "WA": 0.20, "IL": 0.245, "MA": 0.25,
    "RO": 0.03, "SG": 0.0, "UK": 0.20, "DE": 0.264,
    "AU": 0.235, "JP": 0.203, "CA_INT": 0.268, "CH": 0.115,
}

US_STATES = ["CA", "TX", "FL", "NY", "WA", "IL", "MA"]
INTL_CODES = ["RO", "SG", "UK", "DE", "AU", "JP", "CA_INT", "CH"]

ARCHETYPES = [
    "momentum", "value", "income", "swing",
    "day_trader", "event_driven", "mean_reversion", "passive_dca",
]

ENTRY_STYLES = ["breakout", "dip_buy", "earnings_anticipation", "dca_scheduled", "technical_signal"]
EXIT_STYLES = ["target_hit", "trailing_stop", "time_based", "panic_sell", "hold_forever"]
DRAWDOWN_RESPONSES = ["hold_through", "average_down", "panic_sell", "reduce_and_hedge", "stop_loss"]
LOSS_STREAK_RESPONSES = ["pause_trading", "revenge_trade", "reduce_size", "no_change"]
BROKERAGES = ["robinhood", "schwab", "fidelity", "interactive_brokers", "td_ameritrade", "etrade"]

SECTORS = ["Technology", "Financials", "Healthcare", "Energy", "Consumer", "Utilities"]

# Archetype-specific parameter maps (used by both pure and blended builders)
ARCHETYPE_ENTRY_MAPS: dict[str, dict[str, float]] = {
    "momentum": {"breakout": 0.6, "technical_signal": 0.3, "dip_buy": 0.1},
    "value": {"dip_buy": 0.7, "technical_signal": 0.2, "breakout": 0.1},
    "income": {"dca_scheduled": 0.6, "dip_buy": 0.3, "technical_signal": 0.1},
    "swing": {"technical_signal": 0.4, "breakout": 0.3, "dip_buy": 0.3},
    "day_trader": {"breakout": 0.4, "technical_signal": 0.4, "dip_buy": 0.2},
    "event_driven": {"earnings_anticipation": 0.7, "breakout": 0.2, "technical_signal": 0.1},
    "mean_reversion": {"dip_buy": 0.6, "technical_signal": 0.3, "breakout": 0.1},
    "passive_dca": {"dca_scheduled": 0.85, "dip_buy": 0.1, "technical_signal": 0.05},
}

ARCHETYPE_EXIT_MAPS: dict[str, dict[str, float]] = {
    "momentum": {"trailing_stop": 0.5, "target_hit": 0.3, "time_based": 0.2},
    "value": {"target_hit": 0.5, "time_based": 0.3, "hold_forever": 0.2},
    "income": {"hold_forever": 0.6, "time_based": 0.3, "target_hit": 0.1},
    "swing": {"target_hit": 0.4, "trailing_stop": 0.3, "time_based": 0.3},
    "day_trader": {"target_hit": 0.4, "trailing_stop": 0.3, "time_based": 0.3},
    "event_driven": {"target_hit": 0.5, "time_based": 0.3, "trailing_stop": 0.2},
    "mean_reversion": {"target_hit": 0.6, "trailing_stop": 0.2, "time_based": 0.2},
    "passive_dca": {"hold_forever": 0.7, "time_based": 0.2, "target_hit": 0.1},
}

ARCHETYPE_HOLDING_RANGES: dict[str, tuple[float, float]] = {
    "momentum": (5, 30), "value": (60, 365), "income": (180, 500),
    "swing": (2, 15), "day_trader": (0.2, 0.8), "event_driven": (1, 10),
    "mean_reversion": (3, 20), "passive_dca": (30, 365),
}

ARCHETYPE_TRADES_PM_RANGES: dict[str, tuple[float, float]] = {
    "momentum": (8, 20), "value": (1, 4), "income": (1, 3),
    "swing": (10, 25), "day_trader": (30, 80), "event_driven": (4, 12),
    "mean_reversion": (8, 20), "passive_dca": (1, 3),
}

ARCHETYPE_RISK_RANGES: dict[str, tuple[float, float]] = {
    "momentum": (0.5, 0.85), "value": (0.3, 0.6), "income": (0.15, 0.4),
    "swing": (0.5, 0.8), "day_trader": (0.6, 0.95), "event_driven": (0.4, 0.7),
    "mean_reversion": (0.4, 0.7), "passive_dca": (0.1, 0.35),
}


def _blend_styles(archetype_weights: dict[str, float],
                  style_maps: dict[str, dict[str, float]]) -> dict[str, float]:
    """Blend entry/exit styles based on archetype weights."""
    blended: dict[str, float] = {}
    for archetype, weight in archetype_weights.items():
        style_map = style_maps.get(archetype, {})
        for key, value in style_map.items():
            blended[key] = blended.get(key, 0) + value * weight
    total = sum(blended.values())
    if total > 0:
        blended = {k: round(v / total, 3) for k, v in blended.items()}
    return blended


# Name pools
FIRST_NAMES = [
    "James", "Maria", "David", "Sarah", "Michael", "Jennifer", "Robert", "Lisa",
    "William", "Jessica", "Thomas", "Emily", "Daniel", "Ashley", "Christopher",
    "Amanda", "Andrew", "Stephanie", "Joshua", "Nicole", "Ryan", "Lauren",
    "Brandon", "Rachel", "Kevin", "Megan", "Brian", "Heather", "Jason",
    "Michelle", "Nathan", "Samantha", "Ethan", "Brittany", "Tyler", "Danielle",
    "Jacob", "Rebecca", "Austin", "Hannah", "Raj", "Priya", "Wei", "Yuki",
    "Carlos", "Ana", "Ahmed", "Fatima", "Olga", "Marco", "Sophia", "Liam",
    "Emma", "Noah", "Olivia", "Aiden", "Isabella", "Lucas", "Mia", "Mason",
    "Ava", "Logan", "Charlotte", "Elijah", "Amelia", "Oliver", "Harper",
    "Benjamin", "Evelyn", "Alexander", "Abigail", "Sebastian", "Elena",
    "Kai", "Aisha", "Henrik", "Yuna", "Diego",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Anderson", "Taylor", "Thomas",
    "Jackson", "White", "Harris", "Martin", "Thompson", "Moore", "Young",
    "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill",
    "Flores", "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera",
    "Campbell", "Mitchell", "Carter", "Roberts", "Gomez", "Phillips",
    "Evans", "Turner", "Diaz", "Parker", "Cruz", "Edwards", "Collins",
    "Reyes", "Stewart", "Morris", "Morales", "Murphy", "Cook", "Rogers",
    "Gutierrez", "Ortiz", "Morgan", "Cooper", "Peterson", "Bailey",
    "Reed", "Kelly", "Howard", "Ramos", "Kim", "Cox", "Ward",
    "Patel", "Chen", "Tanaka", "Müller", "Petrov", "Svensson", "Ali",
    "Johansson", "Fischer", "Kumar",
]

_rng = random.Random(42)


def _random_name() -> str:
    return f"{_rng.choice(FIRST_NAMES)} {_rng.choice(LAST_NAMES)}"


def _weighted_dict(keys: list[str], dominant: str | None = None,
                   dominant_weight: float = 0.0,
                   min_keys: int = 1, max_keys: int | None = None) -> dict[str, float]:
    """Build a random weight dict that sums to 1.0."""
    if max_keys is None:
        max_keys = len(keys)
    n = _rng.randint(min_keys, min(max_keys, len(keys)))

    if dominant:
        chosen = [dominant]
        others = [k for k in keys if k != dominant]
        _rng.shuffle(others)
        chosen += others[: n - 1]
    else:
        chosen = _rng.sample(keys, n)

    if dominant and dominant_weight > 0:
        remaining = 1.0 - dominant_weight
        raw = [_rng.random() for _ in chosen if _ != dominant]
        total_raw = sum(raw) or 1.0
        weights = {}
        for k in chosen:
            if k == dominant:
                weights[k] = round(dominant_weight, 3)
            else:
                weights[k] = round(remaining * (raw.pop(0) / total_raw), 3)
    else:
        raw = [_rng.random() for _ in chosen]
        total_raw = sum(raw)
        weights = {k: round(v / total_raw, 3) for k, v in zip(chosen, raw)}

    # Fix rounding
    diff = round(1.0 - sum(weights.values()), 3)
    first_key = next(iter(weights))
    weights[first_key] = round(weights[first_key] + diff, 3)
    return weights


def _account_size_for_age_exp(age: int, experience: float) -> int:
    """Generate a plausible account size given age and experience."""
    base = 15_000
    # Older, more experienced traders tend to have larger accounts
    age_factor = max(1.0, (age - 20) / 10)
    exp_factor = max(1.0, experience)
    mean = base * age_factor * exp_factor * _rng.uniform(0.3, 2.0)
    size = int(min(max(mean, 15_000), 3_000_000))
    return size


def _build_pure_trader(idx: int, archetype: str) -> dict[str, Any]:
    """Build a trader where one archetype weight > 0.80."""
    age = _rng.randint(25, 65)
    exp = _rng.uniform(2, min(age - 20, 25))
    location = _rng.choice(US_STATES + INTL_CODES[:3])
    acct = _account_size_for_age_exp(age, exp)

    holding_map = {
        "momentum": _rng.uniform(5, 30),
        "value": _rng.uniform(60, 365),
        "income": _rng.uniform(180, 500),
        "swing": _rng.uniform(2, 15),
        "day_trader": _rng.uniform(0.2, 0.8),
        "event_driven": _rng.uniform(1, 10),
        "mean_reversion": _rng.uniform(3, 20),
        "passive_dca": _rng.uniform(30, 365),
    }

    entry_map: dict[str, dict[str, float]] = {
        "momentum": {"breakout": 0.6, "technical_signal": 0.3, "dip_buy": 0.1},
        "value": {"dip_buy": 0.7, "technical_signal": 0.2, "breakout": 0.1},
        "income": {"dca_scheduled": 0.6, "dip_buy": 0.3, "technical_signal": 0.1},
        "swing": {"technical_signal": 0.4, "breakout": 0.3, "dip_buy": 0.3},
        "day_trader": {"breakout": 0.4, "technical_signal": 0.4, "dip_buy": 0.2},
        "event_driven": {"earnings_anticipation": 0.7, "breakout": 0.2, "technical_signal": 0.1},
        "mean_reversion": {"dip_buy": 0.6, "technical_signal": 0.3, "breakout": 0.1},
        "passive_dca": {"dca_scheduled": 0.85, "dip_buy": 0.1, "technical_signal": 0.05},
    }

    exit_map: dict[str, dict[str, float]] = {
        "momentum": {"trailing_stop": 0.5, "target_hit": 0.3, "time_based": 0.2},
        "value": {"target_hit": 0.5, "time_based": 0.3, "hold_forever": 0.2},
        "income": {"hold_forever": 0.6, "time_based": 0.3, "target_hit": 0.1},
        "swing": {"target_hit": 0.4, "trailing_stop": 0.3, "time_based": 0.3},
        "day_trader": {"target_hit": 0.4, "trailing_stop": 0.3, "time_based": 0.3},
        "event_driven": {"target_hit": 0.5, "time_based": 0.3, "trailing_stop": 0.2},
        "mean_reversion": {"target_hit": 0.6, "trailing_stop": 0.2, "time_based": 0.2},
        "passive_dca": {"hold_forever": 0.7, "time_based": 0.2, "target_hit": 0.1},
    }

    trades_per_month_map = {
        "momentum": _rng.uniform(8, 20),
        "value": _rng.uniform(1, 4),
        "income": _rng.uniform(1, 3),
        "swing": _rng.uniform(10, 25),
        "day_trader": _rng.uniform(30, 80),
        "event_driven": _rng.uniform(4, 12),
        "mean_reversion": _rng.uniform(8, 20),
        "passive_dca": _rng.uniform(1, 3),
    }

    risk_map = {
        "momentum": _rng.uniform(0.5, 0.85),
        "value": _rng.uniform(0.3, 0.6),
        "income": _rng.uniform(0.15, 0.4),
        "swing": _rng.uniform(0.5, 0.8),
        "day_trader": _rng.uniform(0.6, 0.95),
        "event_driven": _rng.uniform(0.4, 0.7),
        "mean_reversion": _rng.uniform(0.4, 0.7),
        "passive_dca": _rng.uniform(0.1, 0.35),
    }

    dom_weight = _rng.uniform(0.80, 0.95)

    if archetype == "day_trader":
        acct = _rng.choice([_rng.randint(15_000, 24_999), _rng.randint(25_000, 150_000)])

    return {
        "trader_id": f"T{idx:03d}",
        "name": _random_name(),
        "age": age,
        "location": location,
        "tax_jurisdiction": location if location in TAX_RATES else "TX",
        "account_size": acct,
        "portfolio_pct_of_net_worth": _rng.randint(10, 80),
        "experience_years": round(exp, 1),
        "pdt_constrained": acct < 25_000,
        "options_approval_level": _rng.randint(0, 2 if exp < 5 else 4),
        "brokerage_platform": _rng.choice(BROKERAGES),
        "archetype_weights": _weighted_dict(ARCHETYPES, dominant=archetype, dominant_weight=dom_weight, min_keys=2, max_keys=3),
        "risk_tolerance": round(risk_map[archetype], 3),
        "sector_affinity": _weighted_dict(SECTORS, min_keys=2, max_keys=4),
        "holding_period_base_days": round(holding_map[archetype], 1),
        "entry_style": entry_map[archetype],
        "exit_style": exit_map[archetype],
        "conviction_sizing": _rng.random() > 0.5,
        "drawdown_response": _rng.choice(DRAWDOWN_RESPONSES),
        "loss_streak_response": _rng.choice(LOSS_STREAK_RESPONSES),
        "discipline_score": round(_rng.uniform(0.65, 0.95), 2),
        "trades_per_month": round(trades_per_month_map[archetype], 1),
        "tax_awareness": round(_rng.uniform(0.3, 0.9), 2),
    }


def _build_blended_trader(idx: int) -> dict[str, Any]:
    """Build a trader with 2-3 archetypes blended."""
    age = _rng.randint(22, 70)
    exp = _rng.uniform(0.5, min(age - 20, 30))
    is_intl = _rng.random() < 0.15
    location = _rng.choice(INTL_CODES) if is_intl else _rng.choice(US_STATES)
    acct = _account_size_for_age_exp(age, exp)

    n_archetypes = _rng.choice([2, 2, 2, 3])
    chosen = _rng.sample(ARCHETYPES, n_archetypes)
    raw = [_rng.random() for _ in chosen]
    total = sum(raw)
    archetype_weights = {k: round(v / total, 3) for k, v in zip(chosen, raw)}
    diff = round(1.0 - sum(archetype_weights.values()), 3)
    archetype_weights[chosen[0]] = round(archetype_weights[chosen[0]] + diff, 3)

    # Blend parameters based on archetype weights (not random!)
    dominant = max(archetype_weights, key=archetype_weights.get)  # type: ignore[arg-type]

    # Log-space weighted blend for holding periods (handles scale differences
    # between day_trader ~0.5d and value ~200d without arithmetic distortion)
    import math
    log_holding = sum(
        w * math.log(max(_rng.uniform(*ARCHETYPE_HOLDING_RANGES.get(a, (10, 60))), 0.1))
        for a, w in archetype_weights.items()
    )
    holding = math.exp(log_holding)

    # Log-space blend for trades/month too (range: 1-80)
    log_tpm = sum(
        w * math.log(max(_rng.uniform(*ARCHETYPE_TRADES_PM_RANGES.get(a, (3, 15))), 0.5))
        for a, w in archetype_weights.items()
    )
    trades_pm = math.exp(log_tpm)
    risk = sum(
        w * _rng.uniform(*ARCHETYPE_RISK_RANGES.get(a, (0.3, 0.7)))
        for a, w in archetype_weights.items()
    )

    discipline = round(_rng.uniform(0.45, 0.9), 2)

    # Blend entry/exit styles from archetype-specific maps
    entry_style = _blend_styles(archetype_weights, ARCHETYPE_ENTRY_MAPS)
    exit_style = _blend_styles(archetype_weights, ARCHETYPE_EXIT_MAPS)

    return {
        "trader_id": f"T{idx:03d}",
        "name": _random_name(),
        "age": age,
        "location": location,
        "tax_jurisdiction": location if location in TAX_RATES else "TX",
        "account_size": acct,
        "portfolio_pct_of_net_worth": _rng.randint(5, 100),
        "experience_years": round(exp, 1),
        "pdt_constrained": acct < 25_000,
        "options_approval_level": _rng.randint(0, min(int(exp), 4)),
        "brokerage_platform": _rng.choice(BROKERAGES),
        "archetype_weights": archetype_weights,
        "risk_tolerance": round(risk, 3),
        "sector_affinity": _weighted_dict(SECTORS, min_keys=2, max_keys=5),
        "holding_period_base_days": round(holding, 1),
        "entry_style": entry_style,
        "exit_style": exit_style,
        "conviction_sizing": _rng.random() > 0.4,
        "drawdown_response": _rng.choice(DRAWDOWN_RESPONSES),
        "loss_streak_response": _rng.choice(LOSS_STREAK_RESPONSES),
        "discipline_score": discipline,
        "trades_per_month": round(trades_pm, 1),
        "tax_awareness": round(_rng.uniform(0.2, 0.85), 2),
    }


def _build_noisy_trader(idx: int) -> dict[str, Any]:
    """Build a trader with low discipline (0.2-0.5)."""
    trader = _build_blended_trader(idx)
    trader["trader_id"] = f"T{idx:03d}"
    trader["discipline_score"] = round(_rng.uniform(0.2, 0.5), 2)
    # Noisy traders tend to revenge-trade or panic
    trader["loss_streak_response"] = _rng.choice(["revenge_trade", "revenge_trade", "no_change", "pause_trading"])
    trader["drawdown_response"] = _rng.choice(["panic_sell", "panic_sell", "hold_through", "average_down"])
    return trader


def _build_pdt_trader(idx: int) -> dict[str, Any]:
    """Build a trader with account < $25K (PDT constrained)."""
    trader = _build_blended_trader(idx)
    trader["trader_id"] = f"T{idx:03d}"
    trader["account_size"] = _rng.randint(15_000, 24_999)
    trader["pdt_constrained"] = True
    trader["age"] = _rng.randint(22, 35)
    trader["experience_years"] = round(_rng.uniform(0.5, 5), 1)
    return trader


def generate_profiles() -> list[dict[str, Any]]:
    """Generate 75 synthetic trader profiles."""
    _rng.seed(42)
    profiles: list[dict[str, Any]] = []
    idx = 1

    # 8 pure archetype traders
    for archetype in ARCHETYPES:
        profiles.append(_build_pure_trader(idx, archetype))
        idx += 1

    # 2 extra pure traders for momentum and swing (popular archetypes)
    for archetype in ["momentum", "swing"]:
        profiles.append(_build_pure_trader(idx, archetype))
        idx += 1

    # 45 blended traders
    for _ in range(45):
        profiles.append(_build_blended_trader(idx))
        idx += 1

    # 12 noisy traders
    for _ in range(12):
        profiles.append(_build_noisy_trader(idx))
        idx += 1

    # 8 PDT-constrained traders
    for _ in range(8):
        profiles.append(_build_pdt_trader(idx))
        idx += 1

    logger.info("Generated %d trader profiles", len(profiles))
    return profiles


def save_profiles(profiles: list[dict[str, Any]]) -> Path:
    """Save profiles to JSON."""
    out = DATA_DIR / "trader_profiles.json"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump(profiles, f, indent=2, default=str)
    logger.info("Saved profiles to %s", out)
    return out


def load_profiles() -> list[dict[str, Any]]:
    """Load profiles from JSON."""
    path = DATA_DIR / "trader_profiles.json"
    with open(path) as f:
        return json.load(f)
