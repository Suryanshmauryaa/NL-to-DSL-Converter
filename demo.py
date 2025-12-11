"""
This is a robust, beginner-friendly DSL parser that does NOT use Lark.
It parses the canonical DSL text produced by dsl_canonicalizer.py.

It outputs an AST-like dict:
{
  "entry": [ first_expr, {"logic":"AND","expr": next_expr}, ... ],
  "exit":  [ ... ]
}
"""

import re
import json
from typing import Dict, Any, List, Union, Optional

def parse_number(text: str) -> Optional[Union[int, float]]:
    if text is None:
        return None
    s = text.strip().lower().replace(",", "")
    m = re.match(r'^([\d\.]+)\s*million$', s)
    if m:
        return int(float(m.group(1)) * 1_000_000)
    m = re.match(r'^([\d\.]+)\s*billion$', s)
    if m:
        return int(float(m.group(1)) * 1_000_000_000)
    m = re.match(r'^([\d\.]+)$', s)
    if m:
        val = float(m.group(1))
        return int(val) if val.is_integer() else val
    return None

def series_node(name: str) -> Dict[str, Any]:
    return {"type":"series", "value": name.lower()}

def indicator_node(name: str, series: str, n: int) -> Dict[str, Any]:
    return {"type":"indicator", "name": name.lower(), "series": series.lower(), "n": int(n)}

def comparison_node(left, op: str, right) -> Dict[str, Any]:
    return {"type":"comparison", "left": left, "op": op, "right": right}

def cross_node(kind: str, left, right) -> Dict[str, Any]:
    return {"type":"cross", "kind": kind, "left": left, "right": right}

def parse_indicator(token: str):
    token = token.strip()
    m = re.match(r'(?i)SMA\s*\(\s*(?P<ser>open|high|low|close|volume)\s*,\s*(?P<n>\d+)\s*\)', token)
    if m:
        return indicator_node("sma", m.group("ser"), int(m.group("n")))
    m = re.match(r'(?i)RSI\s*\(\s*(?P<ser>open|high|low|close|volume)\s*,\s*(?P<n>\d+)\s*\)', token)
    if m:
        return indicator_node("rsi", m.group("ser"), int(m.group("n")))
    return None

def parse_value_token(token: str):
    token = token.strip()
    ind = parse_indicator(token)
    if ind:
        return ind
    if re.fullmatch(r'(?i)(open|high|low|close|volume|price)', token):
        name = token.lower()
        if name == "price":
            name = "close"
        return series_node(name)
    num = parse_number(token)
    if num is not None:
        return num
    return token

def parse_comparison(expr: str):
    m = re.search(r'(>=|<=|==|>|<)', expr)
    if not m:
        return None
    op = m.group(1)
    left_text = expr[:m.start()].strip()
    right_text = expr[m.end():].strip()
    left = parse_value_token(left_text)
    right = parse_value_token(right_text)
    return comparison_node(left, op, right)

def parse_cross(expr: str):
    m = re.match(r'(?i)CROSS_ABOVE\s*\(\s*(?P<l>[^,]+)\s*,\s*(?P<r>[^)]+)\s*\)', expr)
    if m:
        left = parse_value_token(m.group("l"))
        right = parse_value_token(m.group("r"))
        return cross_node("CROSS_ABOVE", left, right)
    m = re.match(r'(?i)CROSS_BELOW\s*\(\s*(?P<l>[^,]+)\s*,\s*(?P<r>[^)]+)\s*\)', expr)
    if m:
        left = parse_value_token(m.group("l"))
        right = parse_value_token(m.group("r"))
        return cross_node("CROSS_BELOW", left, right)
    m = re.search(r'(?i)(close|open|high|low|price)\s+cross(?:es)?\s+(above|below)\s+(.+)', expr)
    if m:
        left_name = m.group(1).lower()
        dirw = m.group(2).lower()
        rhs = m.group(3).strip()
        if "yesterday" in rhs.lower():
            rhs_node = series_node("high" if "high" in rhs.lower() else "low")
            node = cross_node("CROSS_ABOVE" if dirw == "above" else "CROSS_BELOW", series_node(left_name), rhs_node)
            node["time_modifier"] = "yesterday"
            return node
        else:
            rhs_node = parse_value_token(rhs)
            return cross_node("CROSS_ABOVE" if dirw == "above" else "CROSS_BELOW", series_node(left_name), rhs_node)
    return None

def split_by_logic(expr_text: str) -> List[Union[str, Dict[str,str]]]:
    parts = re.split(r'\s+(AND|OR)\s+', expr_text, flags=re.IGNORECASE)
    return [p for p in parts if p is not None and p != ""]

def parse_expr_list(expr_text: str):
    parts = split_by_logic(expr_text)
    nodes = []
    if not parts:
        return nodes
    first = parts[0]
    expr_node = parse_single_expr(first)
    nodes.append(expr_node)
    i = 1
    while i < len(parts):
        logic = parts[i].upper()
        nxt = parts[i+1]
        nodes.append({"logic": logic, "expr": parse_single_expr(nxt)})
        i += 2
    return nodes

def parse_single_expr(expr: str):
    expr = expr.strip()
    if expr.upper() in ("TRUE", "FALSE"):
        return {"type":"literal", "value": expr.upper()}

    # parse PCT_INCREASE(series, period, pct)
    m = re.match(r'(?i)PCT_INCREASE\s*\(\s*(?P<series>\w+)\s*,\s*(?P<period>\d+)\s*,\s*(?P<pct>[\d\.]+)\s*\)\s*$', expr)
    if m:
        series = m.group("series").lower()
        period = int(m.group("period"))
        pct = float(m.group("pct"))
        left_node = {"type":"series", "value": series}
        right_dict = {"period": period, "pct": pct}
        return {"type":"comparison", "left": left_node, "op": "PCT_INCREASE", "right": right_dict}

    c = parse_cross(expr)
    if c:
        return c
    comp = parse_comparison(expr)
    if comp:
        return comp
    ind = parse_indicator(expr)
    if ind:
        return ind
    return {"type":"raw", "value": expr}

def parse_dsl_text(text: str) -> Dict[str, Any]:
    text = text.strip()
    m = re.search(r'ENTRY\s*:\s*(?P<entry>.*?)\n\s*EXIT\s*:\s*(?P<exit>.*)', text, flags=re.IGNORECASE|re.DOTALL)
    if not m:
        m2 = re.match(r'ENTRY\s*:\s*(?P<entry>.*)\s+EXIT\s*:\s*(?P<exit>.*)', text, flags=re.IGNORECASE)
        if not m2:
            raise ValueError("Could not find ENTRY: ... EXIT: ... in DSL text")
        ent_text = m2.group("entry").strip()
        exit_text = m2.group("exit").strip()
    else:
        ent_text = m.group("entry").strip()
        exit_text = m.group("exit").strip()

    entry_ast = parse_expr_list(ent_text)
    exit_ast = parse_expr_list(exit_text)
    return {"entry": entry_ast, "exit": exit_ast}

if __name__ == "__main__":
    examples = [
        "ENTRY: close > SMA(close,20) AND volume > 1000000\nEXIT: RSI(close,14) < 30",
        "ENTRY: CROSS_ABOVE(close, high)\nEXIT: FALSE",
        "ENTRY: PCT_INCREASE(volume, 5, 30)\nEXIT: FALSE"
    ]
    for ex in examples:
        print("DSL INPUT:")
        print(ex)
        print("\nParsed AST:")
        try:
            ast = parse_dsl_text(ex)
            print(json.dumps(ast, indent=2))
        except Exception as e:
            print("ERROR:", e)
        print("\n" + ("-"*70) + "\n")