"""
Simple backtesting engine that records entry_date and exit_date (if `date` column present).
Assumptions:
  Execute at same-row close price
  Full allocation, buy with all equity on entry, sell all on exit
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any

def run_backtest(df: pd.DataFrame, initial_capital: float = 1_000.0) -> Dict[str, Any]:
    if not {'close','entry_signal','exit_signal'}.issubset(df.columns):
        raise ValueError("DataFrame must contain 'close', 'entry_signal', 'exit_signal' columns")

    equity = initial_capital
    position = 0.0
    in_position = False
    trades = []
    equity_curve = []
    entry_meta = None

    has_date = 'date' in df.columns

    for idx, row in df.iterrows():
        price = float(row['close'])
        entry_sig = bool(row['entry_signal'])
        exit_sig = bool(row['exit_signal'])
        if in_position:
            curr_equity = position * price
        else:
            curr_equity = equity
        equity_curve.append(curr_equity)

        # exit first
        if exit_sig and in_position:
            exit_price = price
            entry_idx, entry_price, entry_date_val = entry_meta
            pnl = (exit_price - entry_price) * position
            ret = (exit_price - entry_price) / entry_price if entry_price != 0 else 0.0
            equity = position * exit_price
            trades.append({
                "entry_idx": entry_idx,
                "exit_idx": idx,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "entry_date": entry_date_val,
                "exit_date": row['date'] if has_date else idx,
                "pnl": pnl,
                "return": ret
            })
            position = 0.0
            in_position = False
            entry_meta = None

        # entry
        if entry_sig and not in_position:
            entry_price = price
            position = equity / entry_price if entry_price != 0 else 0.0
            in_position = True
            entry_date_val = row['date'] if has_date else idx
            entry_meta = (idx, entry_price, entry_date_val)

    # close final pos if still open
    if in_position and entry_meta is not None:
        final_price = float(df.iloc[-1]['close'])
        equity = position * final_price
        entry_idx, entry_price, entry_date_val = entry_meta
        pnl = (final_price - entry_price) * position
        ret = (final_price - entry_price) / entry_price if entry_price != 0 else 0.0
        trades.append({
            "entry_idx": entry_idx,
            "exit_idx": len(df)-1,
            "entry_price": entry_price,
            "exit_price": final_price,
            "entry_date": entry_date_val,
            "exit_date": df.iloc[-1]['date'] if 'date' in df.columns else len(df)-1,
            "pnl": pnl,
            "return": ret
        })

    ec = pd.Series(equity_curve, index=df.index)
    peak = ec.cummax()
    drawdown = (ec - peak) / peak
    max_dd = drawdown.min() if not drawdown.empty else 0.0

    total_return = (equity - initial_capital) / initial_capital
    num_trades = len(trades)
    summary = {
        "initial_capital": initial_capital,
        "final_equity": equity,
        "total_return": total_return,
        "max_drawdown": float(max_dd),
        "num_trades": num_trades,
        "trades": trades
    }
    return summary
