import re
import json
from typing import Optional, Dict, Any, List

def parse_number(text: str) -> Optional[float]:
    if text is None:
        return None
    s = text.lower().strip().replace(",", "")
    m = re.match(r"([\d\.]+)\s*million", s)
    if m:
        return int(float(m.group(1)) * 1_000_000)
    m = re.match(r"([\d\.]+)\s*billion", s)
    if m:
        return int(float(m.group(1)) * 1_000_000_000)
    m = re.match(r"([\d\.]+)%", s)
    if m:
        v = float(m.group(1))
        return v
    m = re.match(r"([\d\.]+)", s)
    if m:
        v = float(m.group(1))
        return int(v) if v.is_integer() else v
    return None

def match_sma(nl: str):
    out = []
    pat = r"(close|open|high|low)\s*(?:price\s*)?(?:is\s*)?(above|below|>|<)\s*(?:the\s*)?(\d{1,3})-day\s*moving\s*average"
    for m in re.finditer(pat, nl, flags=re.I):
        series, op, days = m.group(1).lower(), m.group(2), int(m.group(3))
        op = ">" if op.lower() in ("above", ">") else "<"
        out.append({"left": series, "operator": op, "right": f"sma({series},{days})"})
    return out

def match_volume(nl: str):
    out = []
    pat = r"volume\s*(?:is\s*)?(above|below|>|<)\s*([\d\.]+(?:\s*(?:million|billion)?)?)"
    for m in re.finditer(pat, nl, flags=re.I):
        op = m.group(1).lower()
        num = parse_number(m.group(2))
        if num is not None:
            op = ">" if op in ("above", ">") else "<"
            out.append({"left": "volume", "operator": op, "right": num})
    return out

def match_rsi(nl: str):
    out = []
    pat = r"rsi\s*\(\s*(\d{1,2})\s*\)\s*(?:is\s*)?(above|below|>|<)\s*(\d{1,3})"
    for m in re.finditer(pat, nl, flags=re.I):
        n, op, th = int(m.group(1)), m.group(2), int(m.group(3))
        op = ">" if op.lower() in ("above", ">") else "<"
        out.append({"left": f"rsi(close,{n})", "operator": op, "right": th})
    return out

def match_cross(nl: str):
    out = []
    pat = r"(price|close)\s*cross(?:es)?\s*(above|below)\s*yesterday'?s\s*(high|low)"
    for m in re.finditer(pat, nl, flags=re.I):
        series, op, rhs = m.group(1).lower(), m.group(2).lower(), m.group(3).lower()
        out.append({
            "left": series,
            "operator": "CROSS_ABOVE" if op == "above" else "CROSS_BELOW",
            "right": rhs,
            "time_modifier": "yesterday"
        })
    return out

def match_volume_pct_increase(nl: str):
    """
    Matches phrases like:
    - "volume increases by more than 30 percent compared to last week"
    - "volume increases by 25% compared to last week"
    Returns rule:
    {"left":"volume", "operator":"PCT_INCREASE", "right":{"period":5,"pct":30}}
    """
    out = []
    # capture percent and 'last week' / 'last 7 days' / 'compared to last week'
    pat = r"volume\s+.*?increase(?:s)?\s+by\s+(?:more\s+than\s+)?(?P<pct>[\d\.]+)\s*(?:%|percent)\s*(?:compared\s+to|vs|versus)\s*(?P<period>last week|last 7 days|last 7|last 5|last week)"
    for m in re.finditer(pat, nl, flags=re.I):
        pct = float(m.group("pct"))
        period_raw = m.group("period").lower()
        # map period to days (assume trading days)
        if "7" in period_raw:
            period = 7
        else:
            # treat "last week" as 5 trading days
            period = 5
        out.append({"left": "volume", "operator": "PCT_INCREASE", "right": {"period": period, "pct": pct}})
    return out

def nl_to_json(nl_text: str) -> Dict[str, List[Dict[str, Any]]]:
    nl = nl_text.lower().replace("’", "'").strip()
    result = {"entry": [], "exit": []}

    # heuristics for entry/exit detection
    is_entry = "buy" in nl or "enter" in nl or "trigger entry" in nl
    is_exit = "exit" in nl or "sell" in nl

    rules = []
    rules += match_sma(nl)
    rules += match_volume(nl)
    rules += match_rsi(nl)
    rules += match_cross(nl)
    rules += match_volume_pct_increase(nl)

    # assign: pct increase likely an entry trigger
    for r in rules:
        if r["operator"] == "PCT_INCREASE":
            result["entry"].append(r)
            continue
        if r["left"].startswith("rsi") and r["operator"] == "<":
            result["exit"].append(r)
        else:
            result["entry"].append(r)

    # normalize raw rsi strings if any
    def normalize_rsi(rule_list):
        for r in rule_list:
            if isinstance(r.get("left"), str):
                m = re.match(r"rsi\(\s*(\d+)\s*\)", r["left"])
                if m:
                    r["left"] = f"rsi(close,{int(m.group(1))})"
            if isinstance(r.get("right"), str):
                m = re.match(r"rsi\(\s*(\d+)\s*\)", r["right"])
                if m:
                    r["right"] = f"rsi(close,{int(m.group(1))})"
    normalize_rsi(result["entry"])
    normalize_rsi(result["exit"])

    return result

# quick CLI demo if run directly
if __name__ == "__main__":
    ex1 = "Trigger entry when volume increases by more than 30 percent compared to last week."
    ex2 = "Buy when the close price is above the 20-day moving average and volume is above 1 million."
    for ex in [ex1, ex2]:
        print("NL:", ex)
        print("JSON:", json.dumps(nl_to_json(ex), indent=2))
