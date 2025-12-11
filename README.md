# NL-to-DSL-Converter

**Author:** Suryansh Maurya  
**Contact:** (LinkedIn) https://www.linkedin.com/in/suryansh-maurya — Small project built for Rootaly internship take-home.

## TL;DR — what I built
I implemented a lightweight pipeline that converts plain English trading rules into a small DSL, parses that DSL into an AST, generates pandas signals (entry/exit), and runs a simple single-position backtest. This repo contains the converter, parser, codegen and a demo using synthetic OHLCV data so you can reproduce the flow in one command.

## Why I built it this way 
I chose a deterministic, regex-based NL→JSON mapper (no LLM) to keep the output repeatable and easy to grade. The DSL is intentionally small and explicit — easy to extend. I prioritized clarity and reproducibility over chasing exotic features.

## What's in the repo
`nl_to_json.py` — NL → structured JSON rules (simple regex heuristics).  
`dsl_canonicalizer.py` — JSON → canonical DSL text.  
`dsl_parser.py` — DSL → AST (regex parser).  
`ast_to_code.py` — AST → pandas boolean signals; includes SMA and RSI implementations.  
`backtester.py` — simple single-position backtester (entry/exit at close).  
`demo.py` — end-to-end demo that prints JSON, DSL, AST, signals and a backtest summary.  
`dsl_spec.md` — DSL grammar & examples.  
`DEV_NOTES.md` — design choices, limitations, and how I tested the project.  
`requirements.txt`

## How to run (exact steps)
```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python demo.py
