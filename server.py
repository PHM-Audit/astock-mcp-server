#!/usr/bin/env python3
"""AStock MCP server -- China A-share quant toolkit for MCP clients.

Exposes a zero-auth A-share quant toolkit as Model Context Protocol tools:
  - stock_quote(code)                  real-time quote snapshot
  - stock_score(code)                  60-point technical score + signals
  - stock_signals(code, days)          multi-indicator resonance (MACD/RSI/KDJ/BB/MA)
  - stock_backtest(code, strategy, days)  strategy backtest with metrics

Data sources: Tencent quote API + EastMoney kline API (public, no auth).
All indicators are standard public formulas (MA/RSI/MACD/KDJ/Bollinger).
Requires: mcp (pip install mcp), pandas, numpy.
Run: python server.py   (stdio transport, Claude Desktop standard)
"""
import json

from mcp.server.fastmcp import FastMCP

from astock_core.mini_realtime import TencentStockAPI
from astock_core.monitor_v3 import score_stock
from astock_core.strategy_v4 import DataSource, Strategies, Backtest

mcp = FastMCP("astock-quant")

_api = TencentStockAPI()


def _norm(code: str) -> str:
    return code.strip().lower().replace("sh", "").replace("sz", "")


@mcp.tool()
def stock_quote(code: str) -> str:
    """Get a real-time A-share quote snapshot (Tencent public API).

    Args:
        code: 6-digit A-share code, e.g. "600519" (Kweichow Moutai),
              "300059" (East Money), "300750" (CATL)

    Returns:
        JSON: name, price, change_pct, open, high, low, volume, turnover
    """
    q = _api.get_quote(_norm(code))
    if not q:
        return json.dumps({"error": f"no quote for {code}"})
    return json.dumps(q, ensure_ascii=False)


@mcp.tool()
def stock_score(code: str) -> str:
    """Score an A-share stock on a 60-point technical scale (trend/BB/RSI/KDJ/MACD).

    Args:
        code: 6-digit A-share code, e.g. "600519"

    Returns:
        JSON: score (0-60), signals list (e.g. "MACD golden cross", "oversold")
    """
    r = score_stock(_norm(code), _api)
    return json.dumps(r, ensure_ascii=False)


@mcp.tool()
def stock_signals(code: str, days: int = 120) -> str:
    """Multi-indicator resonance check: MACD, RSI, KDJ, Bollinger, MA trend.

    Args:
        code: 6-digit A-share code
        days: kline history window (default 120)

    Returns:
        JSON: bullish/bearish indicator counts, strength stars, per-indicator detail
    """
    from astock_core.mini_realtime import calc_sma, calc_rsi, calc_kdj, calc_macd

    code_n = _norm(code)
    q = _api.get_quote(code_n)
    klines = _api.get_klines(code_n, max(days, 60))
    if not klines or not q:
        return json.dumps({"error": f"no kline data for {code}"})
    closes = [k["close"] for k in klines]
    highs = [k["high"] for k in klines]
    lows = [k["low"] for k in klines]
    price = q["price"]
    detail, bull, bear = {}, 0, 0

    # MA trend
    ma5, ma10, ma20 = calc_sma(closes, 5)[-1], calc_sma(closes, 10)[-1], calc_sma(closes, 20)[-1]
    detail["ma_trend"] = "bullish" if ma5 > ma10 > ma20 and price > ma20 else "bearish" if price < ma20 else "neutral"
    if detail["ma_trend"] == "bullish":
        bull += 1
    elif detail["ma_trend"] == "bearish":
        bear += 1

    # RSI
    rsi = calc_rsi(closes, 14)[-1]
    detail["rsi14"] = round(rsi, 1)
    if rsi < 30:
        bull += 1; detail["rsi_signal"] = "oversold"
    elif rsi > 70:
        bear += 1; detail["rsi_signal"] = "overbought"

    # KDJ
    k, d, j = calc_kdj(highs, lows, closes)
    detail["kdj"] = {"k": round(k[-1], 1), "d": round(d[-1], 1), "j": round(j[-1], 1)}
    if j[-1] < 0:
        bull += 1; detail["kdj_signal"] = "oversold"
    elif j[-1] > 100:
        bear += 1; detail["kdj_signal"] = "overbought"
    elif k[-1] > d[-1]:
        bull += 1; detail["kdj_signal"] = "golden cross"

    # MACD
    dif, dea, hist = calc_macd(closes)
    detail["macd"] = {"dif": round(dif[-1], 2), "dea": round(dea[-1], 2)}
    if dif[-1] > dea[-1] and dif[-2] <= dea[-2]:
        bull += 2; detail["macd_signal"] = "golden cross"
    elif dif[-1] > dea[-1]:
        bull += 1; detail["macd_signal"] = "above zero-axis cross"
    elif dif[-1] < dea[-1] and dif[-2] >= dea[-2]:
        bear += 2; detail["macd_signal"] = "death cross"

    # Bollinger
    mid = calc_sma(closes, 20)[-1]
    std = (sum((c - mid) ** 2 for c in closes[-20:]) / 20) ** 0.5
    upper, lower = mid + 2 * std, mid - 2 * std
    detail["bollinger"] = {"upper": round(upper, 2), "mid": round(mid, 2), "lower": round(lower, 2)}
    if price <= lower:
        bull += 1; detail["bb_signal"] = "lower-band touch"
    elif price >= upper:
        bear += 1; detail["bb_signal"] = "upper-band touch"

    stars = 3 if (bull >= 3 and bull > bear * 2) else 2 if bull - bear >= 2 else 1 if bull > bear else 0
    strength = ("⭐⭐⭐ strong " + ("bullish" if bull >= bear else "bearish")) if stars == 3 and abs(bull - bear) >= 2 else \
               ("⭐⭐ lean " + ("bullish" if bull >= bear else "bearish")) if bull != bear else "⭐ neutral"
    return json.dumps({"code": code_n, "price": price, "bull": bull, "bear": bear,
                       "strength": strength, "detail": detail}, ensure_ascii=False)


STRATEGIES = {
    "ma_cross": ("MA 5/20 golden cross", Strategies.MA_Cross, {}),
    "bollinger_reversal": ("Bollinger lower-band reversal", Strategies.Bollinger_Reversal, {}),
    "kdj_overtrade": ("KDJ oversold entry", Strategies.KDJ_OverTrade, {}),
    "rsi_meanreversion": ("RSI mean reversion 14/30/70", Strategies.RSI_MeanReversion, {}),
    "macd_cross": ("MACD golden/death cross", Strategies.MACD_Cross, {}),
    "fusion_ma_bollinger": ("Fusion MA14/18 + Bollinger", Strategies.Fusion_MA_Bollinger, {"stop_loss": 0.05}),
    "fusion_bollinger_kdj": ("Fusion Bollinger + KDJ", Strategies.Fusion_Bollinger_KDJ, {"stop_loss": 0.05}),
    "fusion_triple": ("Fusion triple confirmation", Strategies.Fusion_Triple_Confirmation, {}),
}


@mcp.tool()
def stock_backtest(code: str, strategy: str = "rsi_meanreversion", days: int = 500) -> str:
    """Backtest a classic technical strategy on an A-share stock.

    Args:
        code: 6-digit A-share code
        strategy: one of ma_cross | bollinger_reversal | kdj_overtrade |
                  rsi_meanreversion | macd_cross | fusion_ma_bollinger |
                  fusion_bollinger_kdj | fusion_triple
        days: kline history window (default 500)

    Returns:
        JSON: total return, buy-and-hold, annualized, sharpe, max drawdown,
              win rate, trade count
    """
    if strategy not in STRATEGIES:
        return json.dumps({"error": f"unknown strategy '{strategy}'",
                           "available": list(STRATEGIES)})
    import pandas as pd

    ds = DataSource()
    df = ds.get_kline(_norm(code), max(days, 60))
    if df is None or len(df) < 30:
        return json.dumps({"error": f"insufficient kline data for {code}"})
    df["date"] = pd.to_datetime(df["date"])
    df["return"] = df["close"].pct_change().fillna(0)
    label, func, params = STRATEGIES[strategy]
    result = func(df, **params)
    m = Backtest.evaluate(result, label)
    m.pop("_total", None); m.pop("_annual", None); m.pop("_sharpe", None)
    m.pop("_mdd", None); m.pop("_wr", None); m.pop("_buys", None)
    m["disclaimer"] = "historical simulation for reference only; not investment advice"
    return json.dumps(m, ensure_ascii=False)


def main():
    """console_script entry point"""
    mcp.run()


if __name__ == "__main__":
    main()
