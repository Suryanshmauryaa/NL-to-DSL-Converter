# DEV_NOTES
Small developer notes — why I made certain choices and some gotchas.

## Overview
This is a deliberately small, reproducible project intended for a take-home assignment. The priority was: reproducible outputs, clear input→output mapping, and readable code.

## Design decisions
  **Regex-based NL→JSON**: deterministic and easy for graders to review. I documented the patterns that are supported.
  **DSL canonicalizer**: makes a single canonical textual form so parser and examples are consistent.
  **Parser**: simple regex parser that is robust for canonical DSL forms. Switched to this approach to avoid fragile parse-tree traversal.
  **Indicators**: SMA implemented via pandas `.rolling().mean()` and RSI via Wilder’s EMA.

## Testing approach
  Synthetic OHLCV generator in `demo.py` to validate indicators and signals.
  I verified cross semantics (`t-1` vs `t`) manually by printing intermediate series.

## Known limitations
  NL parser is not exhaustive — it covers the assignment examples and similar phrasings. Corner cases may need pattern additions.
  Backtester is simplistic (single position, full allocation, immediate execution on close).

## Future improvements (if I had more time)
  Add unit tests for parser and AST evaluator.
  Replace regex parser with Lark for formal grammar validation.
  Support multi-position portfolio backtesting and transaction costs.

