from __future__ import annotations

import json
import shlex
import subprocess
from datetime import datetime
from typing import Optional


def _run_longbridge(args: list[str]) -> str:
    """Run longbridge CLI and return stdout text.

    This adapter intentionally uses the Longbridge CLI so users only need to
    configure Longbridge auth once in their environment. If CLI is missing or
    not authenticated, we return a readable error string for downstream agents.
    """
    cmd = ["longbridge", *args]
    try:
        proc = subprocess.run(  # noqa: S603
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        return (
            "Longbridge CLI is not installed. Install it first, then authenticate before "
            "using longbridge vendor."
        )
    except subprocess.TimeoutExpired:
        return f"Longbridge request timed out: {' '.join(shlex.quote(c) for c in cmd)}"

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        return f"Longbridge command failed: {' '.join(shlex.quote(c) for c in cmd)}\n{err}"
    return (proc.stdout or "").strip()


def _normalize_symbol(symbol: str) -> str:
    """Convert plain ticker to Longbridge format when market suffix is missing."""
    symbol = symbol.strip().upper()
    if "." in symbol:
        return symbol
    # Default to US market for plain tickers, e.g. AAPL -> AAPL.US
    return f"{symbol}.US"


def get_stock_data_longbridge(symbol: str, start_date: str, end_date: str) -> str:
    lb_symbol = _normalize_symbol(symbol)
    output = _run_longbridge(
        [
            "kline",
            "history",
            lb_symbol,
            "--start",
            start_date,
            "--end",
            end_date,
            "--period",
            "day",
        ]
    )
    header = f"# Longbridge Kline data for {lb_symbol} from {start_date} to {end_date}\n"
    return header + output


def get_indicators_longbridge(symbol: str, indicator: str, curr_date: str, look_back_days: int) -> str:
    """Longbridge adapter currently returns recent kline for indicator reasoning."""
    lb_symbol = _normalize_symbol(symbol)
    output = _run_longbridge(
        [
            "kline",
            "history",
            lb_symbol,
            "--start",
            curr_date,
            "--end",
            curr_date,
            "--period",
            "day",
        ]
    )
    return (
        f"# Longbridge indicator proxy for {lb_symbol}\n"
        f"Requested indicator: {indicator}, look_back_days: {look_back_days}, date: {curr_date}\n"
        "Note: Raw kline returned for LLM-side indicator reasoning.\n\n"
        f"{output}"
    )


def get_news_longbridge(ticker: str, start_date: str, end_date: str) -> str:
    lb_symbol = _normalize_symbol(ticker)
    output = _run_longbridge(["news", lb_symbol])
    header = f"# Longbridge news for {lb_symbol} from {start_date} to {end_date}\n"
    return header + output


def get_global_news_longbridge(curr_date: str, look_back_days: int = 7, limit: int = 10) -> str:
    output = _run_longbridge(["market-temp"])
    start_date = datetime.strptime(curr_date, "%Y-%m-%d").date()
    return (
        f"# Longbridge global market snapshot around {curr_date}\n"
        f"look_back_days={look_back_days}, limit={limit}\n"
        "Note: market-temp is used as macro sentiment proxy.\n\n"
        f"{output}"
    )


def get_fundamentals_longbridge(ticker: str, curr_date: Optional[str] = None) -> str:
    lb_symbol = _normalize_symbol(ticker)
    output = _run_longbridge(["quote", lb_symbol])
    date_note = f" as of {curr_date}" if curr_date else ""
    return f"# Longbridge quote/fundamentals proxy for {lb_symbol}{date_note}\n{output}"


def get_balance_sheet_longbridge(ticker: str, freq: str = "quarterly", curr_date: Optional[str] = None) -> str:
    return (
        f"Longbridge vendor does not currently expose balance sheet via this adapter "
        f"(ticker={_normalize_symbol(ticker)}, freq={freq}, curr_date={curr_date}). "
        "Use alpha_vantage for fundamental statement tools."
    )


def get_cashflow_longbridge(ticker: str, freq: str = "quarterly", curr_date: Optional[str] = None) -> str:
    return (
        f"Longbridge vendor does not currently expose cashflow via this adapter "
        f"(ticker={_normalize_symbol(ticker)}, freq={freq}, curr_date={curr_date}). "
        "Use alpha_vantage for fundamental statement tools."
    )


def get_income_statement_longbridge(ticker: str, freq: str = "quarterly", curr_date: Optional[str] = None) -> str:
    return (
        f"Longbridge vendor does not currently expose income statement via this adapter "
        f"(ticker={_normalize_symbol(ticker)}, freq={freq}, curr_date={curr_date}). "
        "Use alpha_vantage for fundamental statement tools."
    )


def get_insider_transactions_longbridge(ticker: str) -> str:
    lb_symbol = _normalize_symbol(ticker)
    output = _run_longbridge(["insider-trades", lb_symbol])
    return f"# Longbridge insider trades for {lb_symbol}\n{output}"

