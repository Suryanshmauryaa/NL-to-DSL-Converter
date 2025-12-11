"""
Converts structured JSON from nl_to_json into canonical DSL text.
Includes:
  rule deduplication
  rsi(14) normalization
  PCT_INCREASE rendering as PCT_INCREASE(series, period, pct)
"""

import re
from typing import Dict, List, Any

def json_to_dsl(js: Dict[str, List[Dict[str, Any]]]) -> str:
    entry_rules = js.get("entry", [])
    exit_rules = js.get("exit", [])

    # Normalize raw rsi strings

    def normalize_rsi(r):
        if isinstance(r.get("left"), str):
            m = re.match(r"rsi\(\s*(\d+)\s*\)", r["left"], flags=re.I)
            if m:
                r["left"] = f"rsi(close,{int(m.group(1))})"
        if isinstance(r.get("right"), str):
            m = re.match(r"rsi\(\s*(\d+)\s*\)", r["right"], flags=re.I)
            if m:
                r["right"] = f"rsi(close,{int(m.group(1))})"
        return r

    entry_rules = [normalize_rsi(dict(r)) for r in entry_rules]
    exit_rules  = [normalize_rsi(dict(r)) for r in exit_rules]

    # Deduplicate rules

    seen = set()

    def _rule_key(r):
        if r.get("operator", "").startswith("CROSS_"):
            return ("cross", r.get("operator"), r.get("left"), r.get("right"), r.get("time_modifier",""))
        if r.get("operator") == "PCT_INCREASE":
            right = r.get("right", {})
            return ("pct_inc", r.get("left"), int(right.get("period", 0)), float(right.get("pct", 0.0)))
        return ("cmp", r.get("left"), r.get("operator"), str(r.get("right")))

    def dedupe(rules):
        out = []
        for r in rules:
            k = _rule_key(r)
            if k not in seen:
                seen.add(k)
                out.append(r)
        return out

    entry_rules = dedupe(entry_rules)
    seen.clear()
    exit_rules = dedupe(exit_rules)

    # Convert rule to text (handle PCT_INCREASE specially)

    def rule_to_text(r):
        if r.get("operator", "").startswith("CROSS_"):
            return f"{r['operator']}({r['left']}, {r['right']})"
        if r.get("operator") == "PCT_INCREASE":
            pr = r["right"]
            return f"PCT_INCREASE({r['left']}, {int(pr['period'])}, {float(pr['pct'])})"
        left = r["left"]
        op = r["operator"]
        right = r["right"]
        return f"{left} {op} {right}"

    entry_text = " AND ".join(rule_to_text(r) for r in entry_rules) if entry_rules else "TRUE"
    exit_text  = " AND ".join(rule_to_text(r) for r in exit_rules)  if exit_rules else "FALSE"

    return f"ENTRY: {entry_text}\nEXIT: {exit_text}"
