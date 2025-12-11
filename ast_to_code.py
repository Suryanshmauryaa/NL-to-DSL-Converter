"""
Converts AST into pandas boolean signals.
Added support for 'PCT_INCREASE' rules where right is {"period":N,"pct":X}
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Union

def sma(series: pd.Series, n: int) -> pd.Series:
    return series.rolling(window=n, min_periods=n).mean()

def rsi(series: pd.Series, n: int = 14) -> pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    ma_up = up.ewm(alpha=1/n, adjust=False, min_periods=n).mean()
    ma_down = down.ewm(alpha=1/n, adjust=False, min_periods=n).mean()
    rs = ma_up / (ma_down.replace(0, np.nan))
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)

def ensure_indicators(df: pd.DataFrame, ast: Dict[str, Any]) -> pd.DataFrame:
    df = df.copy()
    inds = []
    def walk(node):
        if isinstance(node, dict):
            t = node.get("type")
            if t == "indicator":
                inds.append((node["name"], node["series"], int(node["n"])))
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for it in node:
                walk(it)
    walk(ast.get("entry", []))
    walk(ast.get("exit", []))
    seen = set()
    for name, series_name, n in inds:
        key = (name, series_name, n)
        if key in seen:
            continue
        seen.add(key)
        if name.lower() == "sma":
            col = f"sma_{series_name}_{n}"
            df[col] = sma(df[series_name], n)
        elif name.lower() == "rsi":
            col = f"rsi_{series_name}_{n}"
            df[col] = rsi(df[series_name], n)
    return df

def value_to_series(df: pd.DataFrame, value):
    if isinstance(value, dict):
        if value.get("type") == "series":
            name = value["value"]
            if name == "price":
                name = "close"
            return df[name]
        if value.get("type") == "indicator":
            name = value["name"].lower()
            series_name = value["series"]
            n = int(value["n"])
            if name == "sma":
                return df[f"sma_{series_name}_{n}"]
            if name == "rsi":
                return df[f"rsi_{series_name}_{n}"]
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            if value.isdigit():
                return int(value)
            return float(value)
        except:
            return value
    return value

def eval_comparison(node: Dict[str, Any], df: pd.DataFrame) -> pd.Series:
    left = value_to_series(df, node["left"])
    right = node["right"]
    op = node.get("op") or node.get("operator")
    # handle pct increase syntax: right is dict {"period":N,"pct":X}
    if isinstance(right, dict) and right.get("pct") is not None:
        period = int(right.get("period", 5))
        pct = float(right.get("pct"))
        # baseline: mean over previous 'period' rows (shifted by 1 to exclude current)
        baseline = left.rolling(window=period, min_periods=period).mean().shift(1)
        pct_series = (left / baseline - 1) * 100
        return pct_series > pct
    # normal numeric comparisons
    right_val = value_to_series(df, right)
    # left is series usually
    if isinstance(left, pd.Series) and not isinstance(right_val, pd.Series):
        if op == ">":
            return left > right_val
        if op == "<":
            return left < right_val
        if op == ">=":
            return left >= right_val
        if op == "<=":
            return left <= right_val
        if op == "==":
            return left == right_val
    if isinstance(right_val, pd.Series) and not isinstance(left, pd.Series):
        if op == ">":
            return left > right_val
        if op == "<":
            return left < right_val
        if op == ">=":
            return left >= right_val
        if op == "<=":
            return left <= right_val
        if op == "==":
            return left == right_val
    if isinstance(left, pd.Series) and isinstance(right_val, pd.Series):
        if op == ">":
            return left > right_val
        if op == "<":
            return left < right_val
        if op == ">=":
            return left >= right_val
        if op == "<=":
            return left <= right_val
        if op == "==":
            return left == right_val
    return pd.Series(False, index=df.index)

def eval_cross(node: Dict[str, Any], df: pd.DataFrame) -> pd.Series:
    left = value_to_series(df, node["left"])
    right = value_to_series(df, node["right"])
    kind = node.get("kind", "CROSS_ABOVE")
    if node.get("time_modifier") == "yesterday":
        rhs_prev = right.shift(1) if isinstance(right, pd.Series) else right
        rhs_now = right
    else:
        rhs_prev = right.shift(1) if isinstance(right, pd.Series) else right
        rhs_now = right
    left_prev = left.shift(1) if isinstance(left, pd.Series) else left
    left_now = left
    if kind == "CROSS_ABOVE":
        cond = (left_prev <= rhs_prev) & (left_now > rhs_now)
    else:
        cond = (left_prev >= rhs_prev) & (left_now < rhs_now)
    return cond.fillna(False)

def eval_single_expr(expr_node: Dict[str, Any], df: pd.DataFrame) -> pd.Series:
    t = expr_node.get("type")
    if t == "comparison":
        return eval_comparison(expr_node, df)
    if t == "cross":
        return eval_cross(expr_node, df)
    if t == "literal":
        return pd.Series(True, index=df.index) if expr_node.get("value") == "TRUE" else pd.Series(False, index=df.index)
    if t == "indicator":
        return value_to_series(df, expr_node)
    if t == "raw":
        return pd.Series(False, index=df.index)
    if isinstance(expr_node, list):
        s = eval_single_expr(expr_node[0], df)
        for item in expr_node[1:]:
            logic = item.get("logic")
            e = item.get("expr")
            se = eval_single_expr(e, df)
            s = s & se if logic == "AND" else s | se
        return s.fillna(False)
    return pd.Series(False, index=df.index)

def eval_expr_list(ast_list: List[Any], df: pd.DataFrame) -> pd.Series:
    if not ast_list:
        return pd.Series(False, index=df.index)
    first = ast_list[0]
    s = eval_single_expr(first, df)
    for item in ast_list[1:]:
        logic = item.get("logic")
        expr = item.get("expr")
        se = eval_single_expr(expr, df)
        s = s & se if logic == "AND" else s | se
    return s.fillna(False)

def ast_to_signals(ast: Dict[str, Any], df: pd.DataFrame) -> pd.DataFrame:
    df2 = df.copy().reset_index(drop=True)
    for c in ("open", "high", "low", "close", "volume"):
        if c not in df2.columns:
            raise ValueError(f"DataFrame missing required column: {c}")
    df2 = ensure_indicators(df2, ast)
    entry_series = eval_expr_list(ast.get("entry", []), df2)
    exit_series = eval_expr_list(ast.get("exit", []), df2)
    df2["entry_signal"] = entry_series.astype(bool)
    df2["exit_signal"] = exit_series.astype(bool)
    return df2
