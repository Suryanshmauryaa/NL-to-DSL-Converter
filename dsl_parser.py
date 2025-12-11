"""
This is a robust, beginner-friendly DSL parser that does NOT use Lark.
It parses the canonical DSL text produced by dsl_canonicalizer.py:

Example DSL:
ENTRY: close > SMA(close,20) AND volume > 1000000
EXIT: RSI(close,14) < 30

It outputs an AST-like dict:
{
  "entry": [ first_expr, {"logic":"AND","expr": next_expr}, ... ],
  "exit":  [ ... ]
}
"""

import re
import json
from typing import Dict, Any, List, Union, Optional

# Helpers

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

def normalize(s: str) -> str:
    return s.strip()

# AST node constructors

def series_node(name: str) -> Dict[str, Any]:
    return {"type":"series", "value": name.lower()}

def indicator_node(name: str, series: str, n: int) -> Dict[str, Any]:
    return {"type":"indicator", "name": name.lower(), "series": series.lower(), "n": int(n)}

def comparison_node(left, op: str, right) -> Dict[str, Any]:
    return {"type":"comparison", "left": left, "op": op, "right": right}

def cross_node(kind: str, left, right) -> Dict[str, Any]:
    return {"type":"cross", "kind": kind, "left": left, "right": right}

# Expression parsers

SERIES_RE = r'\b(open|high|low|close|volume|price)\b'

def parse_indicator(token: str):
    """
    Parse SMA(x, N) or RSI(x, N)
    Return indicator_node or None
    """
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

    # indicator?
    ind = parse_indicator(token)
    if ind:
        return ind
    
    # series name?
    if re.fullmatch(r'(?i)(open|high|low|close|volume|price)', token):
        
        # map "price" -> "close" for simplicity
        name = token.lower()
        if name == "price":
            name = "close"
        return series_node(name)
    
    # number?
    num = parse_number(token)
    if num is not None:
        return num
    
    # fallback: raw string
    return token

def parse_comparison(expr: str):
    """
    Parse comparisons like 'close > SMA(close,20)' or 'volume > 1000000'
    """
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
    """
    Parse CROSS_ABOVE(left, right) or CROSS_BELOW(...)
    """
    # Allow both CROSS_ABOVE(...) token form and textual 'crosses above' form
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
    
    # textual form: e.g., "price crosses above yesterday's high"
    m = re.search(r'(?i)(close|open|high|low|price)\s+cross(?:es)?\s+(above|below)\s+(.+)', expr)
    if m:
        left_name = m.group(1).lower()
        dirw = m.group(2).lower()
        rhs = m.group(3).strip()
        
        # rhs might be "yesterday's high" or "high" or "SMA(close,20)"
        if "yesterday" in rhs.lower():
        
            # simplify to RHS = high (with time modifier)
            rhs_node = series_node("high" if "high" in rhs.lower() else "low")
        
            # we preserve time modifier by adding field
            node = cross_node("CROSS_ABOVE" if dirw == "above" else "CROSS_BELOW", series_node(left_name), rhs_node)
            node["time_modifier"] = "yesterday"
            return node
        else:
            rhs_node = parse_value_token(rhs)
            return cross_node("CROSS_ABOVE" if dirw == "above" else "CROSS_BELOW", series_node(left_name), rhs_node)
    return None

# Expression list parser

def split_by_logic(expr_text: str) -> List[Union[str, Dict[str,str]]]:
    """
    Splits 'A AND B OR C' into tokens: ['A', 'AND', 'B', 'OR', 'C']
    """
    parts = re.split(r'\s+(AND|OR)\s+', expr_text, flags=re.IGNORECASE)
    
    # parts will be like ['A', 'AND', 'B', 'OR', 'C']
    return [p for p in parts if p is not None and p != ""]

def parse_expr_list(expr_text: str):
    parts = split_by_logic(expr_text)
    nodes = []
    if not parts:
        return nodes
    
    # first is expression
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
    
    # try cross first
    c = parse_cross(expr)
    if c:
        return c
    
    # try comparison
    comp = parse_comparison(expr)
    if comp:
        return comp
    
    # try indicator alone like "RSI(close,14) < 30" handled above; if it reaches here maybe it's a lone indicator
    ind = parse_indicator(expr)
    if ind:
        return ind
    
    # fallback: return raw token
    return {"type":"raw", "value": expr}

# Top-level parse function

def parse_dsl_text(text: str) -> Dict[str, Any]:
    """
    Extract ENTRY and EXIT lines (case-insensitive) and parse them.
    """
    # Normalize newlines
    text = text.strip()
    
    # Use regex to capture ENTRY: ... EXIT: ... allowing multiline
    m = re.search(r'ENTRY\s*:\s*(?P<entry>.*?)\n\s*EXIT\s*:\s*(?P<exit>.*)', text, flags=re.IGNORECASE|re.DOTALL)
    if not m:
    
        # try single-line forms
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

# Demo / CLI
if __name__ == "__main__":
    examples = [
        "ENTRY: close > SMA(close,20) AND volume > 1000000\nEXIT: RSI(close,14) < 30",
        "ENTRY: CROSS_ABOVE(close, high)\nEXIT: FALSE",
        "ENTRY: close > SMA(close,20)\nEXIT: RSI(close,14) < 30",
        "ENTRY: close > sma(close,20) AND volume > 1 million\nEXIT: rsi(14) < 30",
        "ENTRY: price crosses above yesterday's high\nEXIT: FALSE"
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