"""Holdings Feature Extractor — 69 features from stored Supabase data.

Computes h_ prefixed features measuring WHAT the trader has built
(portfolio structure) vs the 212 trade features measuring HOW they trade.

Reads from: holdings, income, fees, trades_new tables.
Uses MarketDataService for sector/ETF/market cap lookups.
All thresholds loaded from analysis_config table — no magic numbers.
"""

from __future__ import annotations

import logging
import math
import time
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)


class HoldingsExtractor:
    """Computes 69 holdings features from stored Supabase data.

    Reads from: holdings, income, fees, trades_new tables.
    Uses MarketDataService for sector/ETF/market cap lookups.
    """

    def __init__(self, supabase_client: Any, market_data: Any = None):
        self._client = supabase_client
        self._market_data = market_data
        # Config loaded from analysis_config
        self._config: dict[str, Any] = {}
        self._load_config()

    def _load_config(self) -> None:
        """Load thresholds from analysis_config table."""
        if not self._client:
            return
        try:
            resp = self._client.table("analysis_config").select("key, value").execute()
            for row in (resp.data or []):
                key = row["key"]
                if key.startswith("h_"):
                    self._config[key] = row["value"]
        except Exception:
            logger.debug("[HOLDINGS] Failed to load config from analysis_config", exc_info=True)

    def _get_config(self, key: str, default: Any = None) -> Any:
        """Get a config value, parsing JSON if needed."""
        import json
        val = self._config.get(key, default)
        if isinstance(val, str):
            try:
                return json.loads(val)
            except (json.JSONDecodeError, TypeError):
                try:
                    return float(val)
                except (ValueError, TypeError):
                    return val
        return val

    def extract(self, profile_id: str) -> dict[str, Any]:
        """Extract 69 h_ prefixed features for a profile.

        Returns dict of {feature_key: value} where keys match
        feature_registry exactly.
        """
        t0 = time.monotonic()

        # Read data from Supabase
        holdings = self._read_holdings(profile_id)
        income = self._read_income(profile_id)
        fees = self._read_fees(profile_id)
        trades = self._read_trades(profile_id)
        self._cached_trades = trades

        if not holdings:
            logger.info("[HOLDINGS] %s: no holdings data, returning empty", profile_id)
            return {}

        # Prefetch market data for all tickers
        all_tickers = list(set(h.get("ticker", "") for h in holdings if h.get("ticker")))
        if self._market_data and all_tickers:
            try:
                self._market_data.prefetch_tickers(all_tickers)
            except Exception:
                logger.debug("[HOLDINGS] Ticker prefetch failed", exc_info=True)

        # Compute features by module
        features: dict[str, Any] = {}
        features.update(self._compute_account_features(holdings))
        features.update(self._compute_concentration_features(holdings))
        features.update(self._compute_allocation_features(holdings))
        features.update(self._compute_options_features(holdings, trades))
        features.update(self._compute_income_features(holdings, income, fees))
        features.update(self._compute_risk_features(holdings))
        features.update(self._compute_sophistication_features(holdings, income, trades))
        features.update(self._compute_signal_features(holdings, trades, income))

        elapsed = time.monotonic() - t0
        computed = sum(1 for v in features.values() if v is not None)
        logger.info(
            "[HOLDINGS] %s: %d features extracted (%d non-null) in %.1fs",
            profile_id, len(features), computed, elapsed,
        )

        features["_meta_holdings_extraction_time_seconds"] = round(elapsed, 2)
        features["_meta_holdings_count"] = len(holdings)
        return features

    # ── Data readers ─────────────────────────────────────────────────

    def _read_holdings(self, profile_id: str) -> list[dict]:
        if not self._client:
            return []
        try:
            resp = (
                self._client.table("holdings")
                .select("*")
                .eq("profile_id", profile_id)
                .execute()
            )
            return resp.data or []
        except Exception:
            logger.warning("[HOLDINGS] Failed to read holdings", exc_info=True)
            return []

    def _read_income(self, profile_id: str) -> list[dict]:
        if not self._client:
            return []
        try:
            resp = (
                self._client.table("income")
                .select("*")
                .eq("profile_id", profile_id)
                .execute()
            )
            return resp.data or []
        except Exception:
            logger.warning("[HOLDINGS] Failed to read income", exc_info=True)
            return []

    def _read_fees(self, profile_id: str) -> list[dict]:
        if not self._client:
            return []
        try:
            resp = (
                self._client.table("fees")
                .select("*")
                .eq("profile_id", profile_id)
                .execute()
            )
            return resp.data or []
        except Exception:
            logger.warning("[HOLDINGS] Failed to read fees", exc_info=True)
            return []

    def _read_trades(self, profile_id: str) -> list[dict]:
        if not self._client:
            return []
        try:
            resp = (
                self._client.table("trades_new")
                .select("*")
                .eq("profile_id", profile_id)
                .execute()
            )
            return resp.data or []
        except Exception:
            logger.warning("[HOLDINGS] Failed to read trades", exc_info=True)
            return []

    # ── Helpers ─────────────────────────────────────────────────────

    def _position_value(self, h: dict) -> float:
        """Best estimate of position value."""
        cv = h.get("current_value")
        if cv is not None:
            return abs(float(cv))
        qty = abs(float(h.get("quantity", 0) or 0))
        cb = abs(float(h.get("cost_basis", 0) or 0))
        if qty > 0 and cb > 0:
            return qty * cb
        return 0.0

    def _get_instrument_type(self, h: dict) -> str:
        return (h.get("instrument_type") or "equity").lower()

    def _get_account_type(self, account_id: str) -> str:
        """Classify an account ID/name into a type using config patterns."""
        import json
        patterns = self._get_config("h_account_type_patterns", {})
        if isinstance(patterns, str):
            try:
                patterns = json.loads(patterns)
            except Exception:
                patterns = {}

        acct_lower = (account_id or "").lower()
        for acct_type, keywords in patterns.items():
            if isinstance(keywords, list):
                for kw in keywords:
                    if kw.lower() in acct_lower:
                        return acct_type
        return "brokerage"

    def _is_tax_advantaged(self, account_id: str) -> bool:
        atype = self._get_account_type(account_id)
        return atype in ("ira", "retirement")

    def _get_sector(self, ticker: str) -> str:
        if self._market_data:
            return self._market_data.get_sector(ticker)
        return "unknown"

    def _is_etf(self, ticker: str) -> bool:
        if self._market_data:
            return self._market_data.is_etf(ticker)
        return False

    def _is_leveraged_etf(self, ticker: str) -> bool:
        if self._market_data:
            return self._market_data.is_leveraged_etf(ticker)
        return False

    # ── Module 1: h_account (8 features) ────────────────────────────

    def _compute_account_features(self, holdings: list[dict]) -> dict[str, Any]:
        accounts: dict[str, float] = defaultdict(float)
        ticker_accounts: dict[str, set[str]] = defaultdict(set)
        account_types: set[str] = set()
        account_type_values: dict[str, float] = defaultdict(float)

        for h in holdings:
            acct = h.get("account_id") or "default"
            val = self._position_value(h)
            accounts[acct] += val
            ticker = h.get("ticker", "")
            if ticker:
                ticker_accounts[ticker].add(acct)
            atype = self._get_account_type(acct)
            account_types.add(atype)
            account_type_values[atype] += val

        total_value = sum(accounts.values())
        account_count = len(accounts)

        # h_largest_account_pct
        largest_pct = max(accounts.values()) / total_value if total_value > 0 else None

        # h_account_type_mix: ratio taxable / total
        taxable_value = sum(
            v for k, v in account_type_values.items()
            if k in ("brokerage", "business")
        )
        type_mix = taxable_value / total_value if total_value > 0 else None

        # h_account_purpose_diversity: entropy of account types
        diversity = None
        if total_value > 0 and len(account_type_values) > 1:
            entropy = 0.0
            for v in account_type_values.values():
                p = v / total_value
                if p > 0:
                    entropy -= p * math.log2(p)
            diversity = round(entropy, 4)

        # h_cross_account_overlap_count: tickers in 2+ accounts
        overlap_count = sum(1 for accts in ticker_accounts.values() if len(accts) >= 2)

        # h_cross_account_conflicting: same ticker different strategies
        conflicting = self._detect_cross_account_conflicts(holdings, ticker_accounts)

        return {
            "h_account_count": account_count,
            "h_total_value": round(total_value, 2) if total_value > 0 else None,
            "h_largest_account_pct": round(largest_pct, 4) if largest_pct is not None else None,
            "h_account_type_count": len(account_types),
            "h_account_type_mix": round(type_mix, 4) if type_mix is not None else None,
            "h_account_purpose_diversity": diversity,
            "h_cross_account_overlap_count": overlap_count,
            "h_cross_account_conflicting": conflicting,
        }

    def _detect_cross_account_conflicts(
        self, holdings: list[dict], ticker_accounts: dict[str, set[str]]
    ) -> int:
        """Count tickers with conflicting strategies across accounts."""
        # Group positions by ticker+account
        ticker_positions: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
        for h in holdings:
            ticker = h.get("ticker", "")
            acct = h.get("account_id") or "default"
            itype = self._get_instrument_type(h)
            ticker_positions[ticker][acct].append(itype)

        conflicts = 0
        for ticker, acct_types in ticker_positions.items():
            if len(acct_types) < 2:
                continue
            # Check if one account has equity and another has options (e.g., short calls)
            all_types = set()
            for types_list in acct_types.values():
                all_types.update(types_list)
            if "equity" in all_types and "options" in all_types:
                conflicts += 1
        return conflicts

    # ── Module 2: h_concentration (7 features) ──────────────────────

    def _compute_concentration_features(self, holdings: list[dict]) -> dict[str, Any]:
        position_values: dict[str, float] = defaultdict(float)
        sector_values: dict[str, float] = defaultdict(float)

        for h in holdings:
            ticker = h.get("ticker", "")
            val = self._position_value(h)
            position_values[ticker] += val
            sector = self._get_sector(ticker)
            sector_values[sector] += val

        total = sum(position_values.values())
        if total <= 0:
            return {
                "h_ticker_hhi": None, "h_sector_hhi": None,
                "h_top1_pct": None, "h_top3_pct": None, "h_top5_pct": None,
                "h_sector_max_pct": None, "h_correlation_estimate": None,
            }

        # HHI calculations
        ticker_hhi = sum((v / total) ** 2 for v in position_values.values())
        sector_hhi = sum((v / total) ** 2 for v in sector_values.values())

        # Top N pct
        sorted_vals = sorted(position_values.values(), reverse=True)
        top1 = sorted_vals[0] / total if sorted_vals else 0
        top3 = sum(sorted_vals[:3]) / total if len(sorted_vals) >= 3 else sum(sorted_vals) / total
        top5 = sum(sorted_vals[:5]) / total if len(sorted_vals) >= 5 else sum(sorted_vals) / total

        # Sector max
        sector_max = max(sector_values.values()) / total if sector_values else 0

        # Correlation estimate: if >threshold in one sector, high correlation
        threshold = self._get_config("h_correlation_high_sector_threshold", 0.50)
        if sector_max > threshold:
            correlation = round(0.5 + (sector_max - threshold) * 1.0, 2)
        else:
            correlation = round(sector_max * 0.6, 2)

        return {
            "h_ticker_hhi": round(ticker_hhi, 4),
            "h_sector_hhi": round(sector_hhi, 4),
            "h_top1_pct": round(top1, 4),
            "h_top3_pct": round(top3, 4),
            "h_top5_pct": round(top5, 4),
            "h_sector_max_pct": round(sector_max, 4),
            "h_correlation_estimate": min(1.0, correlation),
        }

    # ── Module 3: h_allocation (7 features) ─────────────────────────

    def _compute_allocation_features(self, holdings: list[dict]) -> dict[str, Any]:
        allocations: dict[str, float] = defaultdict(float)

        for h in holdings:
            ticker = h.get("ticker", "")
            val = self._position_value(h)
            itype = self._get_instrument_type(h)

            if itype == "options":
                allocations["options"] += val
            elif itype in ("muni_bond", "corp_bond", "bond"):
                allocations["fixed_income"] += val
            elif itype == "structured":
                allocations["structured"] += val
            elif itype in ("money_market", "cash"):
                allocations["cash"] += val
            elif self._is_etf(ticker):
                allocations["etf"] += val
            elif itype in ("equity", "stock") or itype == "etf":
                allocations["equity"] += val
            else:
                allocations["alternatives"] += val

        total = sum(allocations.values())
        if total <= 0:
            return {
                "h_equity_pct": None, "h_fixed_income_pct": None,
                "h_etf_pct": None, "h_options_pct": None,
                "h_structured_pct": None, "h_cash_pct": None,
                "h_alternatives_pct": None,
            }

        return {
            "h_equity_pct": round(allocations.get("equity", 0) / total, 4),
            "h_fixed_income_pct": round(allocations.get("fixed_income", 0) / total, 4),
            "h_etf_pct": round(allocations.get("etf", 0) / total, 4),
            "h_options_pct": round(allocations.get("options", 0) / total, 4),
            "h_structured_pct": round(allocations.get("structured", 0) / total, 4),
            "h_cash_pct": round(allocations.get("cash", 0) / total, 4),
            "h_alternatives_pct": round(allocations.get("alternatives", 0) / total, 4),
        }

    # ── Module 4: h_options (8 features) ────────────────────────────

    def _compute_options_features(
        self, holdings: list[dict], trades: list[dict]
    ) -> dict[str, Any]:
        covered_calls = 0
        protective_puts = 0
        leaps_count = 0
        options_notional = 0.0
        options_premium_paid = 0.0
        strategy_types: set[str] = set()
        spread_count = 0

        # Build equity ownership map: {account: {ticker: qty}}
        equity_by_account: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for h in holdings:
            if self._get_instrument_type(h) in ("equity", "stock", "etf"):
                acct = h.get("account_id") or "default"
                ticker = h.get("ticker", "")
                equity_by_account[acct][ticker] += abs(float(h.get("quantity", 0) or 0))

        for h in holdings:
            itype = self._get_instrument_type(h)
            if itype != "options":
                continue

            details = h.get("instrument_details") or {}
            opt_type = (details.get("option_type") or "").lower()
            underlying = (details.get("underlying") or "").upper()
            strike = float(details.get("strike", 0) or 0)
            qty = abs(float(h.get("quantity", 0) or 0))
            acct = h.get("account_id") or "default"

            # Options notional: contracts * 100 * strike
            notional = qty * 100 * strike
            options_notional += notional

            # Check for LEAPS (expiry > 1 year from now)
            expiry_str = details.get("expiry", "")
            if expiry_str:
                try:
                    from datetime import datetime
                    exp_date = datetime.strptime(expiry_str[:10], "%Y-%m-%d")
                    days_to_expiry = (exp_date - datetime.now()).days
                    if days_to_expiry > 365:
                        leaps_count += 1
                except Exception:
                    pass

            # Track strategy from trades
            strategy = details.get("strategy", "")
            if strategy:
                strategy_types.add(strategy)

            # Covered call: sold call + own underlying
            direction = float(h.get("quantity", 0) or 0)
            if direction < 0 and opt_type == "call":
                owns_underlying = equity_by_account.get(acct, {}).get(underlying, 0)
                if owns_underlying >= qty * 100:
                    covered_calls += 1

            # Protective put: long put + own underlying
            if direction > 0 and opt_type == "put":
                owns_underlying = equity_by_account.get(acct, {}).get(underlying, 0)
                if owns_underlying > 0:
                    protective_puts += 1

            # Premium paid for long options
            cost = abs(float(h.get("cost_basis", 0) or 0))
            if direction > 0:
                options_premium_paid += cost * qty

        # Count spreads from trades instrument_details
        for t in trades:
            details = t.get("instrument_details") or {}
            strategy = details.get("strategy", "")
            if strategy in ("call_spread", "put_spread", "calendar_spread"):
                spread_count += 1
            if strategy:
                strategy_types.add(strategy)

        # Total portfolio value for leverage ratio
        total_value = sum(self._position_value(h) for h in holdings)
        leverage_ratio = options_notional / total_value if total_value > 0 else None

        return {
            "h_covered_call_count": covered_calls,
            "h_protective_put_count": protective_puts,
            "h_leaps_count": leaps_count,
            "h_options_notional": round(options_notional, 2) if options_notional > 0 else None,
            "h_options_tail_risk": round(options_premium_paid, 2) if options_premium_paid > 0 else None,
            "h_options_leverage_ratio": round(leverage_ratio, 4) if leverage_ratio is not None else None,
            "h_options_strategy_count": len(strategy_types) if strategy_types else 0,
            "h_options_spread_count": spread_count,
        }

    # ── Module 5: h_income (8 features) ─────────────────────────────

    def _compute_income_features(
        self, holdings: list[dict], income: list[dict], fees: list[dict]
    ) -> dict[str, Any]:
        total_dividends = 0.0
        total_interest = 0.0
        total_options_income = 0.0
        muni_interest = 0.0

        for inc in income:
            amt = abs(float(inc.get("amount", 0) or 0))
            income_type = (inc.get("income_type") or "").lower()

            if income_type == "dividend":
                total_dividends += amt
            elif income_type in ("muni_interest", "municipal"):
                muni_interest += amt
                total_interest += amt
            elif income_type in ("interest", "corporate_interest", "money_market"):
                total_interest += amt

        # Options income from trades with premium_type = 'collected'
        # (This is computed from trades since income table doesn't store option premiums)
        # We read from the trades list that was already loaded by extract()
        for t in self._cached_trades:
            details = t.get("instrument_details") or {}
            if details.get("premium_type") == "collected":
                amt = abs(float(t.get("amount", 0) or 0))
                total_options_income += amt

        total_income = total_dividends + total_interest + total_options_income
        total_value = sum(self._position_value(h) for h in holdings)

        # Annual yield
        annual_yield = total_income / total_value if total_value > 0 else None

        # Tax free income ratio
        tax_free_ratio = muni_interest / total_income if total_income > 0 else None

        # Fee drag
        total_fees = sum(abs(float(f.get("amount", 0) or 0)) for f in fees)
        annualize_factor = self._get_config("h_fee_drag_advisory_annualize_factor", 4.0)
        # If fees look quarterly, annualize
        annual_fees = total_fees * annualize_factor if total_fees > 0 else 0
        fee_drag = annual_fees / total_value if total_value > 0 else None

        # Muni bond pct
        muni_value = sum(
            self._position_value(h) for h in holdings
            if (h.get("instrument_type") or "").lower() == "muni_bond"
        )
        muni_pct = muni_value / total_value if total_value > 0 else None

        # Tax placement score: are tax-inefficient assets in tax-advantaged accounts?
        tax_score = self._compute_tax_placement_score(holdings)

        return {
            "h_annual_dividend": round(total_dividends, 2) if total_dividends > 0 else None,
            "h_annual_interest": round(total_interest, 2) if total_interest > 0 else None,
            "h_annual_options_income": round(total_options_income, 2) if total_options_income > 0 else None,
            "h_annual_yield": round(annual_yield, 4) if annual_yield is not None else None,
            "h_tax_free_income_ratio": round(tax_free_ratio, 4) if tax_free_ratio is not None else None,
            "h_fee_drag_pct": round(fee_drag, 4) if fee_drag is not None else None,
            "h_muni_bond_pct": round(muni_pct, 4) if muni_pct is not None else None,
            "h_tax_placement_score": tax_score,
        }

    def _compute_tax_placement_score(self, holdings: list[dict]) -> float | None:
        """Score 0-100: are tax-inefficient assets in tax-advantaged accounts?"""
        high_yield_threshold = self._get_config("h_tax_placement_high_yield_threshold", 0.03)

        tax_advantaged_tickers: set[str] = set()
        taxable_tickers: set[str] = set()
        high_yield_tickers: set[str] = set()

        for h in holdings:
            ticker = h.get("ticker", "")
            acct = h.get("account_id") or "default"
            if self._is_tax_advantaged(acct):
                tax_advantaged_tickers.add(ticker)
            else:
                taxable_tickers.add(ticker)

            # Use MarketDataService for dividend yield classification
            if self._market_data and self._market_data.is_income(ticker):
                high_yield_tickers.add(ticker)

        if not high_yield_tickers:
            return None  # Can't assess without income data

        # Score: what fraction of high-yield tickers are in tax-advantaged accounts?
        in_tax_advantaged = len(high_yield_tickers & tax_advantaged_tickers)
        total_high_yield = len(high_yield_tickers)
        if total_high_yield == 0:
            return None

        return round((in_tax_advantaged / total_high_yield) * 100, 1)

    # ── Module 6: h_risk (7 features) ───────────────────────────────

    def _compute_risk_features(self, holdings: list[dict]) -> dict[str, Any]:
        total_value = sum(self._position_value(h) for h in holdings)
        if total_value <= 0:
            return {
                "h_max_single_position_loss": None,
                "h_stress_test_20pct": None,
                "h_beta_estimate": None,
                "h_margin_usage": None,
                "h_max_single_position_pct": None,
                "h_options_leverage_ratio": None,
                "h_interest_rate_sensitivity": None,
            }

        position_values: dict[str, float] = defaultdict(float)
        weighted_beta = 0.0
        bond_allocation = 0.0
        default_beta = self._get_config("h_stress_test_default_beta", 1.0)
        decline_pct = self._get_config("h_stress_test_decline_pct", 0.20)

        stress_loss = 0.0

        for h in holdings:
            ticker = h.get("ticker", "")
            val = self._position_value(h)
            position_values[ticker] += val
            itype = self._get_instrument_type(h)

            # Beta: use default 1.0 — MarketDataService doesn't have beta yet
            beta = default_beta
            weighted_beta += (val / total_value) * beta

            # Stress test: position_value * beta * decline_pct
            stress_loss += val * beta * decline_pct

            # Bond allocation for interest rate sensitivity
            if itype in ("muni_bond", "corp_bond", "bond"):
                bond_allocation += val

        max_position = max(position_values.values()) if position_values else 0
        max_pct = max_position / total_value if total_value > 0 else None

        # Interest rate sensitivity: bond allocation * estimated duration
        # Without duration data, use bond_pct as proxy (0 to 1 scale)
        bond_pct = bond_allocation / total_value if total_value > 0 else 0
        ir_sensitivity = round(bond_pct * 5.0, 2) if bond_pct > 0 else None  # avg duration ~5y

        # Options leverage ratio (computed in options module, duplicate ref)
        options_notional = 0.0
        for h in holdings:
            if self._get_instrument_type(h) == "options":
                details = h.get("instrument_details") or {}
                strike = float(details.get("strike", 0) or 0)
                qty = abs(float(h.get("quantity", 0) or 0))
                options_notional += qty * 100 * strike

        opt_leverage = options_notional / total_value if total_value > 0 and options_notional > 0 else None

        return {
            "h_max_single_position_loss": round(max_position, 2),
            "h_stress_test_20pct": round(stress_loss, 2),
            "h_beta_estimate": round(weighted_beta, 4),
            "h_margin_usage": None,  # Not detectable from available data
            "h_max_single_position_pct": round(max_pct, 4) if max_pct is not None else None,
            "h_options_leverage_ratio": round(opt_leverage, 4) if opt_leverage is not None else None,
            "h_interest_rate_sensitivity": ir_sensitivity,
        }

    # ── Module 7: h_sophistication (12 features) ───────────────────

    def _compute_sophistication_features(
        self, holdings: list[dict], income: list[dict], trades: list[dict]
    ) -> dict[str, Any]:
        # Instrument type count
        instrument_types: set[str] = set()
        for h in holdings:
            instrument_types.add(self._get_instrument_type(h))

        # Strategy complexity score
        complexity_weights = self._get_config("h_strategy_complexity_weights", {
            "covered_call": 1, "protective_put": 2, "spread": 3,
            "calendar_spread": 3, "leaps": 2, "structured_product": 4,
            "muni_bond": 2, "multi_account_coordination": 3,
        })
        strategies_found: set[str] = set()
        for t in trades:
            details = t.get("instrument_details") or {}
            strategy = details.get("strategy", "")
            if strategy:
                strategies_found.add(strategy)
        for h in holdings:
            itype = self._get_instrument_type(h)
            if itype == "structured":
                strategies_found.add("structured_product")
            if itype == "muni_bond":
                strategies_found.add("muni_bond")

        complexity_score = 0
        for s in strategies_found:
            # Map strategy keys to weight keys
            for weight_key, weight in complexity_weights.items():
                if weight_key in s:
                    complexity_score += int(weight)
                    break

        # Multi-account coordination
        accounts = set(h.get("account_id") or "default" for h in holdings)
        # Evidence: same ticker in multiple accounts
        ticker_accounts: dict[str, set[str]] = defaultdict(set)
        for h in holdings:
            ticker_accounts[h.get("ticker", "")].add(h.get("account_id") or "default")
        multi_account = sum(1 for accts in ticker_accounts.values() if len(accts) >= 2)
        multi_account_score = min(100, multi_account * 20) if len(accounts) > 1 else 0
        if multi_account > 0:
            complexity_score += int(complexity_weights.get("multi_account_coordination", 3))

        # Income engineering score (0-100)
        max_sources = int(self._get_config("h_income_engineering_max_sources", 5))
        income_types: set[str] = set()
        for inc in income:
            income_types.add((inc.get("income_type") or "").lower())
        # Also count option premiums as income source
        for t in trades:
            details = t.get("instrument_details") or {}
            if details.get("premium_type") == "collected":
                income_types.add("option_premium")
        income_engineering = round(min(100, (len(income_types) / max_sources) * 100), 1) if income_types else 0

        # Tax optimization score (0-100)
        muni_count = sum(
            1 for h in holdings
            if self._get_instrument_type(h) == "muni_bond"
        )
        tax_advantaged_accounts = sum(
            1 for a in accounts if self._is_tax_advantaged(a)
        )
        tax_score = min(100, (
            (20 if muni_count > 0 else 0)
            + (30 if tax_advantaged_accounts > 0 else 0)
            + (20 if len(accounts) > 1 else 0)
            + min(30, muni_count * 10)
        ))

        # Hedging score (0-1)
        hedging_instruments = 0
        for h in holdings:
            ticker = h.get("ticker", "")
            itype = self._get_instrument_type(h)
            if itype == "options" and float(h.get("quantity", 0) or 0) > 0:
                details = h.get("instrument_details") or {}
                if (details.get("option_type") or "").lower() == "put":
                    hedging_instruments += 1
            if self._market_data and self._market_data.is_inverse_etf(ticker):
                hedging_instruments += 1
        hedging_score = min(1.0, hedging_instruments * 0.25)

        # Structured product usage
        structured_count = sum(
            1 for h in holdings if self._get_instrument_type(h) == "structured"
        )

        # Perpetual bond pct
        total_fi = sum(
            self._position_value(h) for h in holdings
            if self._get_instrument_type(h) in ("muni_bond", "corp_bond", "bond")
        )
        perpetual_value = sum(
            self._position_value(h) for h in holdings
            if (h.get("instrument_details") or {}).get("sub_type") == "perpetual"
        )
        perpetual_pct = perpetual_value / total_fi if total_fi > 0 else None

        # Autocallable notes
        autocallable_count = sum(
            1 for h in holdings
            if "autocall" in (h.get("description") or "").lower()
            or (h.get("instrument_details") or {}).get("sub_type") == "autocallable"
        )

        # Calendar spread count
        calendar_count = sum(
            1 for t in trades
            if (t.get("instrument_details") or {}).get("strategy") == "calendar_spread"
        )

        # Inter-account transfers
        transfer_count = sum(
            1 for t in trades
            if (t.get("side") or "").lower() in ("transfer", "journal")
        )

        # Overall sophistication composite
        soph_weights = self._get_config("h_sophistication_weights", {
            "instrument_type_count": 0.15, "strategy_complexity": 0.20,
            "multi_account": 0.10, "income_engineering": 0.15,
            "tax_optimization": 0.15, "hedging": 0.10,
            "structured_products": 0.05, "perpetual_bonds": 0.05,
            "autocallable_notes": 0.05,
        })

        # Normalize each component to 0-100
        inst_norm = min(100, len(instrument_types) * 16.7)  # 6 types = 100
        complexity_norm = min(100, complexity_score * 10)
        structured_norm = min(100, structured_count * 33)
        perp_norm = min(100, (perpetual_pct or 0) * 200)
        auto_norm = min(100, autocallable_count * 50)

        overall = (
            inst_norm * float(soph_weights.get("instrument_type_count", 0.15))
            + complexity_norm * float(soph_weights.get("strategy_complexity", 0.20))
            + multi_account_score * float(soph_weights.get("multi_account", 0.10))
            + income_engineering * float(soph_weights.get("income_engineering", 0.15))
            + tax_score * float(soph_weights.get("tax_optimization", 0.15))
            + (hedging_score * 100) * float(soph_weights.get("hedging", 0.10))
            + structured_norm * float(soph_weights.get("structured_products", 0.05))
            + perp_norm * float(soph_weights.get("perpetual_bonds", 0.05))
            + auto_norm * float(soph_weights.get("autocallable_notes", 0.05))
        )

        return {
            "h_instrument_type_count": len(instrument_types),
            "h_strategy_complexity_score": complexity_score,
            "h_multi_account_coordination": multi_account_score,
            "h_income_engineering_score": round(income_engineering, 1),
            "h_tax_optimization_score": round(tax_score, 1),
            "h_hedging_score": round(hedging_score, 2),
            "h_structured_product_usage": structured_count,
            "h_overall_sophistication": round(min(100, overall), 1),
            "h_inter_account_transfers": transfer_count,
            "h_perpetual_bond_pct": round(perpetual_pct, 4) if perpetual_pct is not None else None,
            "h_autocallable_note_count": autocallable_count,
            "h_calendar_spread_count": calendar_count,
        }

    # ── Module 8: h_signals (3 features) ────────────────────────────

    def _compute_signal_features(
        self,
        holdings: list[dict],
        trades: list[dict],
        income: list[dict],
    ) -> dict[str, Any]:
        # h_insider_affiliation_signal: wire transfers from companies also traded
        traded_tickers = set(
            (t.get("ticker") or "").upper() for t in trades
        )
        wire_sources: set[str] = set()
        largest_wire = 0.0

        for t in trades:
            desc = (t.get("description") or "").lower()
            side = (t.get("side") or "").lower()
            amt = abs(float(t.get("amount", 0) or 0))

            if side in ("transfer", "wire") or "wire" in desc:
                if amt > largest_wire:
                    largest_wire = amt
                # Check if company name in desc matches any traded ticker
                for ticker in traded_tickers:
                    if ticker.lower() in desc:
                        wire_sources.add(ticker)

        insider_signal = len(wire_sources) > 0

        # h_completeness_confidence: from completeness analysis results
        completeness_confidence = None
        if self._client:
            try:
                resp = (
                    self._client.table("analysis_results")
                    .select("summary_stats")
                    .eq("profile_id", holdings[0]["profile_id"] if holdings else "")
                    .eq("analysis_type", "completeness")
                    .limit(1)
                    .execute()
                )
                if resp.data:
                    stats = resp.data[0].get("summary_stats") or {}
                    conf = stats.get("completeness_confidence")
                    if conf == "high":
                        completeness_confidence = 0.9
                    elif conf == "medium":
                        completeness_confidence = 0.6
                    elif conf == "low":
                        completeness_confidence = 0.3
            except Exception:
                pass

        return {
            "h_insider_affiliation_signal": insider_signal,
            "h_largest_wire": round(largest_wire, 2) if largest_wire > 0 else None,
            "h_completeness_confidence": completeness_confidence,
        }
