"""Option strategy detector — classifies option trades using Supabase rules.

Loads strategy definitions from `option_strategy_rules` table at startup,
then for each option transaction checks the position tracker state to
classify the strategy (covered call, spread, LEAPS, etc.).

When a new pattern is discovered (iron condor, butterfly), add a row
to Supabase — no code change needed.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Module-level cache: loaded once per process lifetime
_cached_rules: list[dict[str, Any]] | None = None


# ---------------------------------------------------------------------------
# Hardcoded fallback rules (used when Supabase is unavailable)
# ---------------------------------------------------------------------------

_FALLBACK_RULES: list[dict[str, Any]] = [
    {
        "strategy_key": "covered_call",
        "strategy_name": "Covered Call",
        "detection_rules": {
            "action": "sell_call",
            "requires": "long_equity_in_same_account",
            "min_shares": "contracts * 100",
            "partial_handling": "classify_excess_as_naked",
        },
        "complexity_score": 1,
    },
    {
        "strategy_key": "cash_secured_put",
        "strategy_name": "Cash-Secured Put",
        "detection_rules": {
            "action": "sell_put",
            "requires": "sufficient_cash_in_account",
            "min_cash": "contracts * 100 * strike",
        },
        "complexity_score": 1,
    },
    {
        "strategy_key": "protective_put",
        "strategy_name": "Protective Put",
        "detection_rules": {
            "action": "buy_put",
            "requires": "long_equity_in_same_account",
        },
        "complexity_score": 1,
    },
    {
        "strategy_key": "call_spread",
        "strategy_name": "Call Spread",
        "detection_rules": {
            "action": "sell_call",
            "requires": "long_call_same_underlying_same_expiry_higher_strike",
        },
        "complexity_score": 2,
    },
    {
        "strategy_key": "put_spread",
        "strategy_name": "Put Spread",
        "detection_rules": {
            "action": "sell_put",
            "requires": "long_put_same_underlying_same_expiry_lower_strike",
        },
        "complexity_score": 2,
    },
    {
        "strategy_key": "calendar_spread",
        "strategy_name": "Calendar Spread",
        "detection_rules": {
            "action": "sell_call_or_put",
            "requires": "long_same_type_same_strike_later_expiry",
        },
        "complexity_score": 2,
    },
    {
        "strategy_key": "leaps",
        "strategy_name": "LEAPS",
        "detection_rules": {
            "action": "buy_call_or_put",
            "requires": "dte_greater_than_365",
        },
        "complexity_score": 1,
    },
    {
        "strategy_key": "likely_covered_call",
        "strategy_name": "Likely Covered Call",
        "detection_rules": {
            "action": "sell_call",
            "requires": "no_equity_but_underlying_in_trade_history",
        },
        "complexity_score": 2,
    },
    {
        "strategy_key": "likely_cash_secured_put",
        "strategy_name": "Likely Cash-Secured Put",
        "detection_rules": {
            "action": "sell_put",
            "requires": "no_short_equity_underlying_in_trade_history",
        },
        "complexity_score": 2,
    },
    {
        "strategy_key": "naked_call",
        "strategy_name": "Naked Call",
        "detection_rules": {
            "action": "sell_call",
            "requires": "no_equity_no_long_call",
        },
        "complexity_score": 3,
    },
    {
        "strategy_key": "naked_put",
        "strategy_name": "Naked Put",
        "detection_rules": {
            "action": "sell_put",
            "requires": "insufficient_cash_no_short_equity",
        },
        "complexity_score": 2,
    },
]


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def load_strategy_rules() -> list[dict[str, Any]]:
    """Load option strategy rules from Supabase, falling back to hardcoded.

    Caches the result so repeated calls are free.
    """
    global _cached_rules
    if _cached_rules is not None:
        return _cached_rules

    try:
        from storage.supabase_client import _get_client

        client = _get_client()
        if client is None:
            raise RuntimeError("Supabase not configured")

        resp = (
            client.table("option_strategy_rules")
            .select("*")
            .eq("is_active", True)
            .order("complexity_score")
            .execute()
        )
        if resp.data:
            _cached_rules = resp.data
            logger.info(
                "[STRATEGY_DETECTOR] Loaded %d rules from Supabase", len(_cached_rules)
            )
            return _cached_rules
    except Exception:
        logger.debug(
            "[STRATEGY_DETECTOR] Supabase unavailable, using fallback rules",
            exc_info=True,
        )

    _cached_rules = _FALLBACK_RULES
    logger.info("[STRATEGY_DETECTOR] Using %d fallback rules", len(_cached_rules))
    return _cached_rules


def reset_cache() -> None:
    """Clear the cached rules (for testing or hot-reload)."""
    global _cached_rules
    _cached_rules = None


# ---------------------------------------------------------------------------
# Strategy confidence mapping
# ---------------------------------------------------------------------------

_STRATEGY_CONFIDENCE: dict[str, str] = {
    "covered_call": "confirmed",
    "cash_secured_put": "confirmed",
    "protective_put": "confirmed",
    "call_spread": "confirmed",
    "put_spread": "confirmed",
    "calendar_spread": "confirmed",
    "leaps": "confirmed",
    "likely_covered_call": "likely",
    "likely_cash_secured_put": "likely",
    "naked_call": "unknown",
    "naked_put": "unknown",
}


# ---------------------------------------------------------------------------
# Strategy classification
# ---------------------------------------------------------------------------


def classify_option_strategy(
    txn: dict[str, Any],
    position_tracker: Any,
    option_details: Optional[dict[str, Any]] = None,
    trade_history: Optional[Any] = None,
    brokerage: Optional[str] = None,
) -> dict[str, Any]:
    """Classify the strategy for an option transaction.

    Parameters
    ----------
    txn : dict
        Parsed transaction with: action, symbol, quantity, instrument_type,
        account (or account_id), price, amount.
    position_tracker : PositionTracker
        Current position state.
    option_details : dict, optional
        Parsed option symbol details: underlying, option_type (call/put),
        strike, expiry_year, expiry_month, expiry_day.
    trade_history : DataFrame | list[dict] | set[str] | None
        All tickers that have ever appeared in the user's trade history.
        Used to distinguish "likely covered" from "naked" when the
        underlying isn't in the current position tracker.

    Returns
    -------
    dict with keys:
        strategy_key, strategy_name, confidence, complexity_score, details
        details includes strategy_confidence: "confirmed" | "likely" | "unknown"
    """
    rules = load_strategy_rules()
    action = (txn.get("action") or "").lower()
    account = txn.get("account", txn.get("account_id", "default"))

    # Build set of all tickers ever traded (for naked vs likely-covered logic)
    history_tickers: set[str] = set()
    if trade_history is not None:
        if isinstance(trade_history, set):
            history_tickers = {t.upper() for t in trade_history}
        elif hasattr(trade_history, "columns"):
            # pandas DataFrame
            for col in ("ticker", "symbol"):
                if col in trade_history.columns:
                    history_tickers = set(
                        trade_history[col].str.upper().dropna().unique()
                    )
                    break
        elif hasattr(trade_history, "__iter__"):
            for item in trade_history:
                if isinstance(item, str):
                    history_tickers.add(item.upper())
                elif isinstance(item, dict):
                    t = item.get("ticker") or item.get("symbol") or ""
                    if t:
                        history_tickers.add(str(t).upper())
    qty = abs(float(txn.get("quantity", 0) or 0))

    if option_details is None:
        # Try to parse from instrument_details or sub_type
        option_details = txn.get("option_details") or {}

    opt_type = (option_details.get("option_type") or "").lower()
    underlying = (option_details.get("underlying") or "").upper()
    strike = float(option_details.get("strike", 0) or 0)
    expiry_year = option_details.get("expiry_year", 0) or 0
    expiry_month = option_details.get("expiry_month", 0) or 0
    expiry_day = option_details.get("expiry_day", 0) or 0

    # Build the "action type" for rule matching
    if action == "sell" and opt_type == "call":
        action_type = "sell_call"
    elif action == "sell" and opt_type == "put":
        action_type = "sell_put"
    elif action == "buy" and opt_type == "call":
        action_type = "buy_call"
    elif action == "buy" and opt_type == "put":
        action_type = "buy_put"
    elif action == "sell":
        action_type = "sell_call_or_put"
    elif action == "buy":
        action_type = "buy_call_or_put"
    else:
        return _unknown_strategy("Non buy/sell action for option")

    # Get current positions for context
    equity_positions = position_tracker.get_equity_positions(account)
    option_positions = position_tracker.get_option_positions(account)
    equity_held = equity_positions.get(underlying, 0)
    contracts = qty  # each contract = 100 shares

    for rule in rules:
        detection = rule.get("detection_rules", {})
        rule_action = detection.get("action", "")

        # Check if this rule's action matches
        if not _action_matches(action_type, rule_action):
            continue

        requirement = detection.get("requires", "")
        matched, confidence, details = _check_requirement(
            requirement=requirement,
            underlying=underlying,
            opt_type=opt_type,
            strike=strike,
            expiry_year=expiry_year,
            expiry_month=expiry_month,
            expiry_day=expiry_day,
            contracts=contracts,
            equity_held=equity_held,
            option_positions=option_positions,
            detection=detection,
            history_tickers=history_tickers,
        )

        if matched:
            strategy_key = rule["strategy_key"]
            details["strategy_confidence"] = _STRATEGY_CONFIDENCE.get(
                strategy_key, "unknown"
            )
            result = {
                "strategy_key": strategy_key,
                "strategy_name": rule["strategy_name"],
                "confidence": confidence,
                "complexity_score": rule.get("complexity_score", 1),
                "details": details,
            }
            # Apply brokerage-level overrides
            result = _apply_brokerage_overrides(result, brokerage, action_type=action_type)

            # Final safety: side/strategy mismatch guard
            result = _guard_side_strategy_mismatch(result, action, opt_type, brokerage)

            return result

    # No rule matched — apply brokerage safety net before returning unknown
    fallback = _unknown_strategy(f"No rule matched for {action_type} on {underlying}")
    result = _apply_brokerage_overrides(fallback, brokerage, action_type=action_type)

    # Final safety: side/strategy mismatch guard
    result = _guard_side_strategy_mismatch(result, action, opt_type, brokerage)

    return result


# ---------------------------------------------------------------------------
# Side / strategy mismatch guard
# ---------------------------------------------------------------------------

_SELL_ONLY_STRATEGIES = {"covered_call", "cash_secured_put", "naked_call", "naked_put",
                         "likely_covered_call", "likely_cash_secured_put"}
_BUY_ONLY_STRATEGIES = {"long_call", "long_put", "long_option", "protective_put",
                        "protective_collar", "long_straddle", "long_strangle"}


def _guard_side_strategy_mismatch(
    result: dict[str, Any],
    action: str,
    opt_type: str,
    brokerage: str | None,
) -> dict[str, Any]:
    """Correct strategy if it contradicts the trade side.

    Buy options must never have sell-only strategies (covered_call, naked_call, ...).
    Sell options must never have buy-only strategies (long_call, long_put, ...).
    """
    strat = result.get("strategy_key", "")
    norm_broker = (brokerage or "").lower().replace(" ", "_")
    is_wfa = norm_broker in _WFA_BROKERAGES

    # Buy with sell-only strategy → correct to long_call / long_put
    if action == "buy" and strat in _SELL_ONLY_STRATEGIES:
        buy_strat = "long_call" if opt_type == "call" else "long_put" if opt_type == "put" else "long_option"
        logger.info(
            "[STRATEGY_DETECTOR] Buy option had sell strategy '%s', corrected to '%s'",
            strat, buy_strat,
        )
        result["strategy_key"] = buy_strat
        result["strategy_name"] = buy_strat.replace("_", " ").title()
        result["details"]["side_override"] = True

    # Sell with buy-only strategy → correct based on brokerage
    elif action == "sell" and strat in _BUY_ONLY_STRATEGIES:
        if is_wfa:
            # WFA: all sold calls are covered, all sold puts are cash-secured
            sell_strat = "covered_call" if opt_type == "call" else "cash_secured_put" if opt_type == "put" else "covered_call"
        else:
            # Other brokerages: default to naked (may be covered but we can't confirm)
            sell_strat = "naked_call" if opt_type == "call" else "naked_put" if opt_type == "put" else "naked_call"
        logger.info(
            "[STRATEGY_DETECTOR] Sell option had buy strategy '%s', corrected to '%s' (wfa=%s)",
            strat, sell_strat, is_wfa,
        )
        result["strategy_key"] = sell_strat
        result["strategy_name"] = sell_strat.replace("_", " ").title()
        result["details"]["side_override"] = True

    return result


# ---------------------------------------------------------------------------
# Brokerage-level overrides
# ---------------------------------------------------------------------------

# Module-level cache for brokerage rules
_cached_brokerage_rules: dict[str, dict[str, Any]] | None = None

_WFA_BROKERAGES = {"wfa", "wells_fargo", "wells_fargo_advisors"}


def _load_brokerage_rules(brokerage: str) -> dict[str, Any]:
    """Load brokerage-specific rules from Supabase, with fallback."""
    global _cached_brokerage_rules
    if _cached_brokerage_rules is None:
        _cached_brokerage_rules = {}
        try:
            from storage.supabase_client import _get_client
            client = _get_client()
            if client:
                resp = (
                    client.table("brokerage_format_rules")
                    .select("brokerage, rule_key, rule_logic")
                    .eq("is_active", True)
                    .execute()
                )
                for row in (resp.data or []):
                    b = row["brokerage"]
                    _cached_brokerage_rules.setdefault(b, {})[row["rule_key"]] = row["rule_logic"]
                logger.info("[STRATEGY_DETECTOR] Loaded brokerage rules for %d brokerages",
                            len(_cached_brokerage_rules))
        except Exception:
            logger.debug("[STRATEGY_DETECTOR] Brokerage rules unavailable", exc_info=True)

    # Normalize brokerage name to match DB key
    norm = brokerage.lower().replace(" ", "_") if brokerage else ""
    return _cached_brokerage_rules.get(norm, {})


def _apply_brokerage_overrides(
    result: dict[str, Any],
    brokerage: str | None,
    action_type: str | None = None,
) -> dict[str, Any]:
    """Apply brokerage-level strategy overrides.

    WFA advisory accounts prohibit naked calls — every sold call is
    covered.  Naked puts become cash-secured puts.

    The action_type param (e.g. "sell_call") is used as a safety net:
    if a WFA sold call/put is classified as "unknown", we still override
    it.  Zero naked calls for WFA, period.
    """
    if not brokerage:
        return result

    norm = brokerage.lower().replace(" ", "_") if brokerage else ""
    is_wfa = norm in _WFA_BROKERAGES
    strategy_key = result.get("strategy_key", "")

    if is_wfa:
        # Try loading from Supabase rules first
        rules = _load_brokerage_rules(norm)
        no_naked_calls = rules.get("no_naked_calls", {})
        no_naked_puts = rules.get("no_naked_puts", {})

        if strategy_key == "naked_call":
            override_to = no_naked_calls.get("sold_call_default", "covered_call")
            reason = no_naked_calls.get("reason", "WFA advisory accounts prohibit naked call writing")
            result["strategy_key"] = override_to
            result["strategy_name"] = "Covered Call"
            result["confidence"] = 0.95
            result["details"]["strategy_confidence"] = "confirmed"
            result["details"]["brokerage_override"] = True
            result["details"]["override_reason"] = reason
            logger.info("[STRATEGY_DETECTOR] WFA override: naked_call → %s", override_to)

        elif strategy_key == "naked_put":
            override_to = no_naked_puts.get("sold_put_default", "cash_secured_put")
            reason = no_naked_puts.get("reason", "WFA requires cash collateral for short puts")
            result["strategy_key"] = override_to
            result["strategy_name"] = "Cash-Secured Put"
            result["confidence"] = 0.95
            result["details"]["strategy_confidence"] = "confirmed"
            result["details"]["brokerage_override"] = True
            result["details"]["override_reason"] = reason
            logger.info("[STRATEGY_DETECTOR] WFA override: naked_put → %s", override_to)

        elif strategy_key in ("likely_covered_call", "likely_cash_secured_put"):
            # WFA: "likely" becomes "confirmed" since all calls are covered
            result["confidence"] = 0.95
            result["details"]["strategy_confidence"] = "confirmed"
            result["details"]["brokerage_override"] = True
            result["details"]["override_reason"] = "WFA prohibits naked options"
            if strategy_key == "likely_covered_call":
                result["strategy_key"] = "covered_call"
                result["strategy_name"] = "Covered Call"
            else:
                result["strategy_key"] = "cash_secured_put"
                result["strategy_name"] = "Cash-Secured Put"

        elif strategy_key == "unknown_option_strategy":
            # WFA safety net: if we can't determine the strategy but know
            # the action type, override based on sell direction.
            # WFA prohibits naked options — all sold calls are covered,
            # all sold puts are cash-secured.
            at = (action_type or "").lower()
            if "sell_call" in at or at == "sell_call_or_put":
                result["strategy_key"] = "covered_call"
                result["strategy_name"] = "Covered Call"
                result["confidence"] = 0.95
                result["details"]["strategy_confidence"] = "confirmed"
                result["details"]["brokerage_override"] = True
                result["details"]["override_reason"] = "WFA prohibits naked calls; defaulting to covered"
                logger.info("[STRATEGY_DETECTOR] WFA safety net: unknown → covered_call")
            elif "sell_put" in at:
                result["strategy_key"] = "cash_secured_put"
                result["strategy_name"] = "Cash-Secured Put"
                result["confidence"] = 0.95
                result["details"]["strategy_confidence"] = "confirmed"
                result["details"]["brokerage_override"] = True
                result["details"]["override_reason"] = "WFA requires cash collateral for short puts"
                logger.info("[STRATEGY_DETECTOR] WFA safety net: unknown → cash_secured_put")

    return result


# ---------------------------------------------------------------------------
# Rule matching helpers
# ---------------------------------------------------------------------------


def _action_matches(actual: str, rule_action: str) -> bool:
    """Check if the actual action type matches the rule's action spec."""
    if actual == rule_action:
        return True
    # "sell_call_or_put" matches both "sell_call" and "sell_put"
    if rule_action == "sell_call_or_put" and actual in ("sell_call", "sell_put"):
        return True
    if rule_action == "buy_call_or_put" and actual in ("buy_call", "buy_put"):
        return True
    return False


def _check_requirement(
    *,
    requirement: str,
    underlying: str,
    opt_type: str,
    strike: float,
    expiry_year: int,
    expiry_month: int,
    expiry_day: int,
    contracts: float,
    equity_held: float,
    option_positions: list[dict[str, Any]],
    detection: dict[str, Any],
    history_tickers: set[str] | None = None,
) -> tuple[bool, float, dict[str, Any]]:
    """Evaluate a single requirement string against current state.

    Returns (matched, confidence, details_dict).
    """
    shares_needed = contracts * 100

    if requirement == "long_equity_in_same_account":
        if equity_held >= shares_needed:
            return True, 0.95, {
                "equity_held": equity_held,
                "shares_needed": shares_needed,
                "fully_covered": True,
            }
        elif equity_held > 0:
            # Partially covered
            partial = detection.get("partial_handling", "")
            return True, 0.80, {
                "equity_held": equity_held,
                "shares_needed": shares_needed,
                "fully_covered": False,
                "partial_handling": partial,
            }
        return False, 0.0, {}

    if requirement == "sufficient_cash_in_account":
        # We can't see cash balance directly, but if there's equity held
        # for the underlying, it's more likely a covered strategy.
        # Without cash data, we classify as cash-secured with lower confidence.
        return True, 0.60, {"note": "cash_balance_unknown"}

    if requirement == "long_call_same_underlying_same_expiry_higher_strike":
        for op in option_positions:
            # option position tickers encode underlying + expiry + strike
            if (
                op.get("quantity", 0) > 0
                and _option_matches_underlying(op["ticker"], underlying)
            ):
                return True, 0.75, {"pairing_position": op["ticker"]}
        return False, 0.0, {}

    if requirement == "long_put_same_underlying_same_expiry_lower_strike":
        for op in option_positions:
            if (
                op.get("quantity", 0) > 0
                and _option_matches_underlying(op["ticker"], underlying)
            ):
                return True, 0.75, {"pairing_position": op["ticker"]}
        return False, 0.0, {}

    if requirement == "long_same_type_same_strike_later_expiry":
        for op in option_positions:
            if (
                op.get("quantity", 0) > 0
                and _option_matches_underlying(op["ticker"], underlying)
            ):
                return True, 0.70, {"pairing_position": op["ticker"]}
        return False, 0.0, {}

    if requirement == "dte_greater_than_365":
        dte = _compute_dte(expiry_year, expiry_month, expiry_day)
        if dte is not None and dte > 365:
            return True, 0.90, {"dte": dte}
        return False, 0.0, {}

    if requirement == "no_equity_but_underlying_in_trade_history":
        # Sold call/put with no current position, but underlying appears
        # in the user's trade history — they likely own it elsewhere.
        if history_tickers and underlying in history_tickers and equity_held <= 0:
            has_long_call = any(
                op.get("quantity", 0) > 0
                and _option_matches_underlying(op["ticker"], underlying)
                for op in option_positions
            )
            if not has_long_call:
                return True, 0.65, {
                    "equity_held": equity_held,
                    "note": "underlying_in_trade_history_but_not_in_positions",
                }
        return False, 0.0, {}

    if requirement == "no_short_equity_underlying_in_trade_history":
        # Sold put with no short equity, but underlying appears in trade
        # history — they likely have cash/familiarity for a secured put.
        if history_tickers and underlying in history_tickers and equity_held >= 0:
            return True, 0.55, {
                "note": "underlying_in_trade_history_likely_cash_secured",
            }
        return False, 0.0, {}

    if requirement == "no_equity_no_long_call":
        has_long_call = any(
            op.get("quantity", 0) > 0
            and _option_matches_underlying(op["ticker"], underlying)
            for op in option_positions
        )
        if equity_held <= 0 and not has_long_call:
            return True, 0.70, {"equity_held": equity_held, "warning": "naked_position"}
        return False, 0.0, {}

    if requirement == "insufficient_cash_no_short_equity":
        # If no short equity (can't verify cash), classify with moderate confidence
        if equity_held >= 0:
            return True, 0.60, {"note": "cash_balance_unknown_no_short_equity"}
        return False, 0.0, {}

    logger.debug("[STRATEGY_DETECTOR] Unknown requirement: %s", requirement)
    return False, 0.0, {}


def _option_matches_underlying(option_ticker: str, underlying: str) -> bool:
    """Check if an option ticker is for the given underlying."""
    if not underlying:
        return False
    return option_ticker.upper().startswith(underlying.upper())


def _compute_dte(year: int, month: int, day: int) -> int | None:
    """Compute days to expiry from a date. Returns None if unparseable."""
    if not year or not month or not day:
        return None
    try:
        expiry = datetime(year, month, day)
        now = datetime.now()
        return max(0, (expiry - now).days)
    except (ValueError, OverflowError):
        return None


def _unknown_strategy(reason: str) -> dict[str, Any]:
    """Return the fallback result when no strategy rule matches."""
    return {
        "strategy_key": "unknown_option_strategy",
        "strategy_name": "Unknown Option Strategy",
        "confidence": 0.30,
        "complexity_score": 0,
        "details": {"reason": reason, "strategy_confidence": "unknown"},
    }
