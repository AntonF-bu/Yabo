"""
Test script for the full portfolio analysis pipeline.

Runs: CSV → parse → classify → reconstruct → analyze (metrics + Claude)

Usage:
    cd ~/Yabo && python3 -m backend.tests.test_portfolio_analysis
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from backend.parsers.wfa_activity import WFAActivityParser
from backend.parsers.instrument_classifier import classify
from backend.parsers.holdings_reconstructor import reconstruct
from backend.analyzers.portfolio_analyzer import analyze_portfolio, compute_metrics


def find_csv() -> Path:
    """Find a test CSV file."""
    if len(sys.argv) > 1:
        p = Path(sys.argv[1])
        if p.exists():
            return p
        print(f"ERROR: File not found: {p}")
        sys.exit(1)

    test_data = Path(__file__).resolve().parent.parent / "test-data"
    csvs = sorted(test_data.glob("*.csv"))
    if csvs:
        return csvs[0]

    print("ERROR: No CSV file found.")
    sys.exit(1)


def fmt_dollar(amount: float) -> str:
    if amount < 0:
        return f"-${abs(amount):,.2f}"
    return f"${amount:,.2f}"


def main() -> None:
    csv_path = find_csv()

    print("=" * 70)
    print("  Portfolio Analysis Pipeline - Full Test")
    print(f"  File: {csv_path.name}")
    print("=" * 70)

    # ----- Step 1: Parse -----
    print("\n[1/6] Parsing CSV...")
    parser = WFAActivityParser()
    transactions = parser.parse_csv(csv_path)
    print(f"  Parsed {len(transactions)} transactions across {len(parser.accounts)} accounts")

    if not transactions:
        print("  No transactions found. Aborting.")
        return

    # ----- Step 2: Reconstruct -----
    print("\n[2/6] Reconstructing holdings...")
    snapshot = reconstruct(transactions)
    print(f"  {len(snapshot.positions)} positions, {len(snapshot.pre_existing_positions)} pre-existing")
    print(f"  Accounts: {', '.join(snapshot.accounts.keys())}")

    # ----- Step 3: Compute metrics -----
    print("\n[3/6] Computing portfolio metrics + features...")
    metrics = compute_metrics(snapshot, transactions)

    # Print asset allocation
    alloc = metrics["asset_allocation"]
    total = alloc.get("_total_estimated_value", 0)
    print(f"\n  Asset Allocation (estimated total: {fmt_dollar(total)}):")
    for itype, data in sorted(alloc.items()):
        if itype.startswith("_"):
            continue
        print(f"    {itype:<18} {fmt_dollar(data['market_value']):>16} ({data['percentage']:>5.1f}%)")

    # Print sector exposure
    sectors = metrics["sector_exposure"]
    print(f"\n  Sector Exposure:")
    for sector, data in sectors.items():
        print(f"    {sector:<18} {fmt_dollar(data['market_value']):>16}  [{', '.join(data['symbols'][:5])}]")

    # Print cross-account exposure
    cross = metrics["multi_account_breakdown"]["cross_account_exposure"]
    if cross:
        print(f"\n  Cross-Account Exposures:")
        for sym, data in sorted(cross.items(), key=lambda x: -x[1]["total_exposure"]):
            types = ", ".join(data["instrument_types"])
            accts = len(data["accounts"])
            print(f"    {sym:<10} {fmt_dollar(data['total_exposure']):>16}  ({types}) across {accts} accounts")

    # Print income summary
    income = metrics["income_summary"]
    print(f"\n  Income Summary ({income['date_range_days']} days):")
    print(f"    Dividends:          {fmt_dollar(income['total_dividends'])}")
    print(f"    Interest (total):   {fmt_dollar(income['total_interest'])}")
    print(f"      Muni bond:        {fmt_dollar(income.get('muni_bond_interest', 0))}")
    print(f"      Other:            {fmt_dollar(income.get('other_interest', 0))}")
    print(f"    Fees:               {fmt_dollar(income['total_fees'])}")
    print(f"    Annualized income:  {fmt_dollar(income['annualized_income'])}")
    print(f"    Annualized muni:    {fmt_dollar(income.get('annualized_muni_income', 0))}")
    print(f"    Annualized fees:    {fmt_dollar(income['annualized_fees'])}")

    # Print muni bond holdings
    munis = metrics.get("muni_bond_holdings", {})
    if munis.get("count", 0) > 0:
        print(f"\n  Municipal Bond Holdings ({munis['count']} bonds, total face: {fmt_dollar(munis['total_face_value'])}):")
        for b in munis["positions"]:
            print(f"    {b['issuer'][:40]:<40}  face {fmt_dollar(b['face_value']):>14}  "
                  f"cpn {b['coupon_rate']:>6}  int {fmt_dollar(b['interest_received']):>10}  [{b['state']}]")

    # Print tax jurisdiction
    tax = metrics.get("detected_tax_jurisdiction", {})
    print(f"\n  Tax Jurisdiction: {tax.get('jurisdiction', 'N/A')} "
          f"(confidence: {tax.get('confidence', 'N/A')}, "
          f"{tax.get('dominant_percentage', 0):.0f}% of muni face value)")
    print(f"    Evidence: {tax.get('evidence', 'N/A')}")

    # Print portfolio features (33 computed features)
    feats = metrics.get("portfolio_features", {})
    if feats:
        print(f"\n  Portfolio Features ({len(feats)} features):")
        print(f"  {'─' * 50}")
        # Concentration
        print(f"    CONCENTRATION:")
        print(f"      ticker_hhi:                  {feats.get('ticker_hhi', 'N/A')}")
        print(f"      sector_hhi:                  {feats.get('sector_hhi', 'N/A')}")
        print(f"      top1_concentration:           {feats.get('top1_concentration', 'N/A')}%")
        print(f"      top3_concentration:           {feats.get('top3_concentration', 'N/A')}%")
        print(f"      top5_concentration:           {feats.get('top5_concentration', 'N/A')}%")
        print(f"      single_name_vs_etf_ratio:     {feats.get('single_name_vs_etf_ratio', 'N/A')}")
        print(f"      max_cross_account_exposure:   {feats.get('max_cross_account_exposure', 'N/A')}%")
        print(f"      sector_max_pct:               {feats.get('sector_max_pct', 'N/A')}%")
        # Structure
        print(f"    PORTFOLIO STRUCTURE:")
        print(f"      equity_pct:                   {feats.get('equity_pct', 'N/A')}%")
        print(f"      etf_pct:                      {feats.get('etf_pct', 'N/A')}%")
        print(f"      options_pct:                  {feats.get('options_pct', 'N/A')}%")
        print(f"      fixed_income_pct:             {feats.get('fixed_income_pct', 'N/A')}%")
        print(f"      structured_pct:               {feats.get('structured_pct', 'N/A')}%")
        print(f"      cash_pct:                     {feats.get('cash_pct', 'N/A')}%")
        print(f"      domestic_vs_international:     {feats.get('domestic_vs_international', 'N/A')}")
        print(f"      active_vs_passive:             {feats.get('active_vs_passive', 'N/A')}")
        # Income
        print(f"    INCOME & COST:")
        print(f"      gross_dividend_income:         {fmt_dollar(feats.get('gross_dividend_income', 0))}")
        print(f"      gross_interest_income:         {fmt_dollar(feats.get('gross_interest_income', 0))}")
        print(f"      total_fees:                    {fmt_dollar(feats.get('total_fees', 0))}")
        print(f"      fee_drag_pct:                  {feats.get('fee_drag_pct', 'N/A')}%")
        print(f"      net_income_after_fees:          {fmt_dollar(feats.get('net_income_after_fees', 0))}")
        print(f"      income_concentration_top3:     {feats.get('income_concentration_top3', 'N/A')}%")
        print(f"      estimated_portfolio_yield:     {feats.get('estimated_portfolio_yield', 'N/A')}%")
        # Tax
        print(f"    TAX:")
        print(f"      tax_jurisdiction:              {feats.get('tax_jurisdiction', 'N/A')}")
        print(f"      muni_face_value:               {fmt_dollar(feats.get('muni_face_value', 0))}")
        print(f"      muni_annual_income:            {fmt_dollar(feats.get('muni_annual_income', 0))}")
        print(f"      tax_placement_score:           {feats.get('tax_placement_score', 'N/A')}/100")
        # Risk
        print(f"    RISK:")
        print(f"      options_premium_at_risk:       {fmt_dollar(feats.get('options_premium_at_risk', 0))}")
        print(f"      options_notional_exposure:     {fmt_dollar(feats.get('options_notional_exposure', 0))}")
        print(f"      structured_product_exposure:   {fmt_dollar(feats.get('structured_product_exposure', 0))}")
        print(f"      correlation_estimate:          {feats.get('correlation_estimate', 'N/A')}")
        print(f"      largest_loss_potential:        {fmt_dollar(feats.get('largest_loss_potential', 0))}")
        print(f"      drawdown_sensitivity:          {fmt_dollar(feats.get('drawdown_sensitivity', 0))}")
        print(f"  {'─' * 50}")

    # Print options summary
    opts = metrics["options_summary"]
    print(f"\n  Options Summary:")
    print(f"    Total positions:    {opts['total_positions']}")
    print(f"    Premium deployed:   {fmt_dollar(opts['total_premium_deployed'])}")
    print(f"    LEAPS (>1yr):       {opts['leaps_count']}")
    print(f"    Short-dated:        {opts['short_dated_count']}")
    for p in opts["positions"]:
        tag = "LEAP" if p["dte"] > 365 else f"{p['dte']}d"
        print(f"      {p['symbol']:<18} {p['option_type']:<5} ${p['strike']:>7.0f}  "
              f"exp {p['expiry']}  qty {p['quantity']:>6.0f}  "
              f"premium {fmt_dollar(p['premium_paid']):>12}  [{tag}]")

    # ----- Step 4: Claude analysis -----
    print(f"\n[4/6] Generating Claude narrative analysis...")
    result = analyze_portfolio(snapshot, transactions)
    analysis = result["analysis"]

    generated_by = analysis.get("_generated_by", "unknown")
    print(f"  Generated by: {generated_by}")

    if generated_by == "claude":
        # Print key sections
        ps = analysis.get("portfolio_structure", {})
        print(f"\n  Portfolio: {ps.get('headline', 'N/A')}")
        for acct in ps.get("account_purposes", []):
            print(f"    {acct.get('account_id', '?')}: {acct.get('purpose', '?')} "
                  f"({acct.get('strategy', '?')}) ~{acct.get('estimated_value', '?')}")

        ca = analysis.get("concentration_analysis", {})
        print(f"\n  Concentration: {ca.get('headline', 'N/A')}")
        for exp in ca.get("top_exposures", [])[:5]:
            print(f"    {exp.get('name', '?')}: {exp.get('total_exposure', '?')} "
                  f"({exp.get('includes', '?')})")

        ia = analysis.get("income_analysis", {})
        print(f"\n  Income: {ia.get('headline', 'N/A')}")
        print(f"    Annual estimate: {ia.get('annual_estimate', 'N/A')}")

        os_section = analysis.get("options_strategy", {})
        print(f"\n  Options: {os_section.get('headline', 'N/A')}")

        ra = analysis.get("risk_assessment", {})
        print(f"\n  Risk: {ra.get('headline', 'N/A')}")
        for risk in ra.get("key_risks", [])[:5]:
            print(f"    [{risk.get('severity', '?').upper()}] {risk.get('risk', '?')}: {risk.get('detail', '')[:80]}")

        tc = analysis.get("tax_context", {})
        print(f"\n  Tax: jurisdiction={tc.get('detected_jurisdiction', 'N/A')}, "
              f"evidence={tc.get('evidence', 'N/A')[:60]}")

        print(f"\n  Key Recommendation: {analysis.get('key_recommendation', 'N/A')}")
    else:
        print(f"  (placeholder — set ANTHROPIC_API_KEY for full narrative)")

    # ----- Step 5: Save results -----
    print(f"\n[5/6] Saving results...")
    output_path = csv_path.parent / "portfolio_result_v2.json"
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"  Saved to: {output_path}")

    # ----- Step 6: Verify feature count -----
    print(f"\n[6/6] Verifying features...")
    feat_count = len(feats) if feats else 0
    print(f"  Feature count: {feat_count}")
    if feat_count >= 33:
        print(f"  ✓ All {feat_count} features computed")
    else:
        print(f"  ⚠ Expected ≥33 features, got {feat_count}")

    print(f"\n{'=' * 70}")
    print(f"  Done. Full pipeline complete.")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
