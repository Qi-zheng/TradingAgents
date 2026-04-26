#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import os
import shlex
import subprocess
from typing import Any, Optional

import cli.main as cli_main
from cli.main import run_analysis
from cli.models import AnalystType
from langchain_openai import ChatOpenAI

from tradingagents.agents.utils import (
    core_stock_tools,
    fundamental_data_tools,
    news_data_tools,
    technical_indicators_tools,
)
from tradingagents.graph import trading_graph
from tradingagents.llm_clients.base_client import BaseLLMClient, normalize_content
from tradingagents.llm_clients.factory import create_llm_client as core_create_llm_client

DUCKCODING_BASE_URL = "https://www.duckcoding.ai/v1"
DEFAULT_MODEL = "gemini-3.1-pro-preview"


class _NormalizedChatOpenAI(ChatOpenAI):
    def invoke(self, input, config=None, **kwargs):  # noqa: A002
        return normalize_content(super().invoke(input, config, **kwargs))


class _DuckCodingClient(BaseLLMClient):
    def __init__(self, model: str, base_url: Optional[str] = None, **kwargs):
        super().__init__(model, base_url, **kwargs)
        self.provider = "duckcoding"

    def get_llm(self) -> Any:
        api_key = os.getenv("DUCKCODING_API_KEY") or os.getenv("OPENAI_API_KEY")
        llm_kwargs = {
            "model": self.model,
            "base_url": self.base_url or DUCKCODING_BASE_URL,
            "api_key": api_key,
        }
        for key in ("timeout", "max_retries", "callbacks", "http_client", "http_async_client"):
            if key in self.kwargs:
                llm_kwargs[key] = self.kwargs[key]
        return _NormalizedChatOpenAI(**llm_kwargs)

    def validate_model(self) -> bool:
        return True


def _install_duckcoding_adapter() -> None:
    def patched_create_llm_client(provider: str, model: str, base_url: Optional[str] = None, **kwargs):
        if provider.lower() == "duckcoding":
            return _DuckCodingClient(model=model, base_url=base_url, **kwargs)
        return core_create_llm_client(provider=provider, model=model, base_url=base_url, **kwargs)

    trading_graph.create_llm_client = patched_create_llm_client


def _normalize_symbol(symbol: str) -> str:
    sym = symbol.strip().upper()
    return sym if "." in sym else f"{sym}.US"


def _run_longbridge(args: list[str]) -> str:
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
        return "Longbridge CLI not found. Please install and login first."
    except subprocess.TimeoutExpired:
        return f"Longbridge timeout: {' '.join(shlex.quote(c) for c in cmd)}"
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        return f"Longbridge command failed: {' '.join(shlex.quote(c) for c in cmd)}\n{err}"
    return (proc.stdout or "").strip()


def _install_longbridge_data_adapter() -> None:
    """Use Longbridge CLI for market data to avoid yfinance limits."""

    def longbridge_route(method: str, *args, **kwargs):
        if method == "get_stock_data":
            symbol, start_date, end_date = args
            return _run_longbridge(
                [
                    "kline",
                    "history",
                    _normalize_symbol(symbol),
                    "--start",
                    start_date,
                    "--end",
                    end_date,
                    "--period",
                    "day",
                ]
            )
        if method == "get_news":
            ticker, _start_date, _end_date = args
            return _run_longbridge(["news", _normalize_symbol(ticker)])
        if method == "get_global_news":
            return _run_longbridge(["market-temp"])
        if method == "get_insider_transactions":
            ticker = args[0]
            return _run_longbridge(["insider-trades", _normalize_symbol(ticker)])
        if method == "get_fundamentals":
            ticker = args[0]
            return _run_longbridge(["quote", _normalize_symbol(ticker)])
        if method in {"get_indicators", "get_balance_sheet", "get_cashflow", "get_income_statement"}:
            return (
                f"[DATA WARNING] {method} has no dedicated Longbridge adapter in td wrapper. "
                "Continuing with available context."
            )
        return f"[DATA WARNING] Unsupported method in longbridge adapter: {method}"

    core_stock_tools.route_to_vendor = longbridge_route
    technical_indicators_tools.route_to_vendor = longbridge_route
    news_data_tools.route_to_vendor = longbridge_route
    fundamental_data_tools.route_to_vendor = longbridge_route


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run TradingAgents CLI with duckcoding defaults.")
    p.add_argument("ticker", help="Ticker symbol, e.g. DUOL / AAPL / 0700.HK")
    p.add_argument("--date", default=dt.date.today().isoformat(), help="Analysis date YYYY-MM-DD")
    p.add_argument("--output-dir", default=None, help="Override results root directory")
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    _install_duckcoding_adapter()
    _install_longbridge_data_adapter()
    if args.output_dir:
        cli_main.DEFAULT_CONFIG["results_dir"] = args.output_dir

    cli_main.get_user_selections = lambda: {
        "ticker": args.ticker.upper().strip(),
        "analysis_date": args.date,
        "analysts": [
            AnalystType.MARKET,
            AnalystType.SOCIAL,
            AnalystType.NEWS,
            AnalystType.FUNDAMENTALS,
        ],
        "research_depth": 3,
        "llm_provider": "duckcoding",
        "backend_url": DUCKCODING_BASE_URL,
        "shallow_thinker": DEFAULT_MODEL,
        "deep_thinker": DEFAULT_MODEL,
        "google_thinking_level": None,
        "openai_reasoning_effort": None,
        "anthropic_effort": None,
        "output_language": "Chinese",
    }

    # Skip trailing interactive prompts for save/display report.
    original_prompt = cli_main.typer.prompt
    cli_main.typer.prompt = lambda text="", default=None, *a, **k: (
        "N" if "save report?" in text.strip().lower() or "display full report on screen?" in text.strip().lower()
        else original_prompt(text, default=default, *a, **k)
    )

    run_analysis()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

