"""Tests for centralized price resolver."""

import pytest
from unittest.mock import patch, MagicMock
from backend.analyzers.price_resolver import (
    wfa_to_occ,
    occ_to_polygon,
    polygon_to_occ,
    wfa_symbol_to_occ,
    instrument_details_to_occ,
    option_details_to_occ,
    resolve_price,
    get_equity_price,
    PriceResult,
    OptionQuote,
    _occ_matches,
)


class TestOCCConversion:
    def test_tsla_call(self):
        assert wfa_to_occ("TSLA", 2028, 2, 21, "call", 710.0) == "TSLA280221C00710000"

    def test_aapl_put(self):
        assert wfa_to_occ("AAPL", 2025, 1, 17, "put", 150.0) == "AAPL250117P00150000"

    def test_fractional_strike(self):
        assert wfa_to_occ("SPY", 2025, 3, 21, "call", 450.5) == "SPY250321C00450500"

    def test_low_strike(self):
        assert wfa_to_occ("F", 2025, 6, 20, "put", 12.0) == "F250620P00012000"

    def test_polygon_prefix(self):
        assert occ_to_polygon("TSLA280221C00710000") == "O:TSLA280221C00710000"
        assert occ_to_polygon("O:TSLA280221C00710000") == "O:TSLA280221C00710000"

    def test_polygon_strip(self):
        assert polygon_to_occ("O:TSLA280221C00710000") == "TSLA280221C00710000"
        assert polygon_to_occ("TSLA280221C00710000") == "TSLA280221C00710000"

    def test_wfa_roundtrip(self):
        occ = wfa_symbol_to_occ("TSLA2821A710")
        assert occ is not None
        assert "TSLA" in occ
        assert "C" in occ
        assert "00710000" in occ

    def test_invalid_symbol(self):
        assert wfa_symbol_to_occ("NOTANOPTION") is None

    def test_instrument_details_conversion(self):
        details = {
            "underlying": "TSLA",
            "option_type": "call",
            "strike": 710,
            "expiry": "2028-02-21",
        }
        occ = instrument_details_to_occ(details)
        assert occ == "TSLA280221C00710000"

    def test_instrument_details_missing_fields(self):
        assert instrument_details_to_occ({"underlying": "TSLA"}) is None
        assert instrument_details_to_occ({}) is None

    def test_option_details_dataclass(self):
        """Test conversion from OptionDetails dataclass (what PositionRecord uses)."""
        from backend.parsers.instrument_classifier import OptionDetails
        od = OptionDetails(
            underlying="NVDA",
            option_type="put",
            strike=140.0,
            expiry_year=2025,
            expiry_month=3,
            expiry_day=21,
        )
        occ = option_details_to_occ(od)
        assert occ == "NVDA250321P00140000"

    def test_option_details_none(self):
        assert option_details_to_occ(None) is None


class TestOCCMatching:
    def test_exact_match(self):
        assert _occ_matches("TSLA280221C00710000", "TSLA280221C00710000")

    def test_with_prefix(self):
        assert _occ_matches("O:TSLA280221C00710000", "TSLA280221C00710000")

    def test_no_match(self):
        assert not _occ_matches("TSLA280221C00710000", "TSLA280221P00710000")


class TestResolvePrice:
    def test_cash(self):
        r = resolve_price("USD", "cash")
        assert r.price == 1.0
        assert r.source == "nominal"

    def test_money_market(self):
        r = resolve_price("SWVXX", "money_market")
        assert r.price == 1.0
        assert r.source == "nominal"

    def test_equity_fallback(self):
        mock_pos = MagicMock()
        mock_pos.transactions = [MagicMock(price=150.0)]
        with patch("backend.analyzers.price_resolver.get_equity_price", return_value=None):
            r = resolve_price("AAPL", "equity", mock_pos)
            assert r.price == 150.0
            assert r.source == "last_transaction"

    def test_structured(self):
        mock_pos = MagicMock()
        mock_pos.cost_basis = 250000.0
        r = resolve_price("NOTE", "structured", mock_pos)
        assert r.price == 250000.0
        assert r.source == "cost_basis"

    def test_bond_with_face_value(self):
        mock_pos = MagicMock()
        mock_pos.face_value = 10000.0
        mock_pos.quantity = 1.0
        r = resolve_price("MUNI", "muni_bond", mock_pos)
        assert r.price == 10000.0
        assert r.source == "par_value"

    def test_options_without_polygon(self):
        """Without POLYGON_API_KEY, options fall back to transaction price."""
        mock_pos = MagicMock()
        mock_pos.transactions = [MagicMock(price=5.50)]
        mock_pos.instrument = MagicMock()
        mock_pos.instrument.option_details = None
        with patch.dict("os.environ", {}, clear=True):
            r = resolve_price("TSLA2821A710", "options", mock_pos)
            assert r.price == 5.50
            assert r.source == "last_transaction"

    def test_expired_option_uses_transaction(self):
        """Expired options should always use transaction price."""
        mock_pos = MagicMock()
        mock_pos.transactions = [MagicMock(price=3.20)]
        mock_pos.instrument = MagicMock()
        mock_pos.instrument.option_details = None
        details = {
            "underlying": "AAPL",
            "option_type": "call",
            "strike": 150,
            "expiry": "2024-01-19",  # Already expired
        }
        r = resolve_price("AAPL2419A150", "options", mock_pos, details)
        assert r.price == 3.20
        assert r.source == "last_transaction"

    def test_equity_with_live_price(self):
        """When get_equity_price returns a result, use it."""
        mock_result = PriceResult(price=142.50, source="live")
        with patch("backend.analyzers.price_resolver.get_equity_price", return_value=mock_result):
            r = resolve_price("AAPL", "equity")
            assert r.price == 142.50
            assert r.source == "live"


class TestGetEquityPrice:
    def test_returns_result_or_none(self):
        """Smoke test: should not raise."""
        result = get_equity_price("AAPL")
        assert result is None or isinstance(result, PriceResult)


class TestOptionQuoteDataclass:
    def test_construction(self):
        q = OptionQuote(
            occ_symbol="TSLA280221C00710000",
            underlying="TSLA",
            option_type="call",
            strike=710.0,
            expiration="2028-02-21",
            last=5.50,
            bid=5.30,
            ask=5.70,
            mid=5.50,
            volume=100,
            open_interest=5000,
            delta=0.35,
        )
        assert q.occ_symbol == "TSLA280221C00710000"
        assert q.delta == 0.35
        assert q.gamma is None  # not set
