# Test Data

This folder holds **real brokerage export files** used for local testing.

## Rules

- **NEVER** commit real CSV/JSON files to the repo.
- `.gitignore` blocks `*.csv` and `*.json` in this directory.
- Only `.gitkeep` and this `README.md` are tracked.

## Expected Files

| File | Source | Description |
|------|--------|-------------|
| `WFA_Activity_*.csv` | Wells Fargo Advisors | Activity/transaction export |

## How to Get Test Data

1. Log into your brokerage account
2. Export activity/transaction history as CSV
3. Drop the file into this folder
4. Run tests: `python -m backend.tests.test_wfa_parser`
