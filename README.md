# astock-mcp-server

China A-share quant toolkit exposed as [Model Context Protocol](https://modelcontextprotocol.io) tools. Zero auth, public data sources, standard public indicators.

## Tools

| Tool | Input | Returns |
|------|-------|---------|
| `stock_quote` | `code` (e.g. `"600519"`) | realtime snapshot: price/open/high/low/change%/volume/PE |
| `stock_score` | `code` | 60-point technical score + signal list (MA position, Bollinger band, RSI, KDJ, MACD, trend) |
| `stock_signals` | `code`, `days=120` | multi-indicator resonance: bullish/bearish count, strength stars, per-indicator detail |
| `stock_backtest` | `code`, `strategy`, `days=500` | total return, buy-and-hold, annualized, Sharpe, max drawdown, win rate, trade count |

### Available backtest strategies

`ma_cross` · `bollinger_reversal` · `kdj_overtrade` · `rsi_meanreversion` · `macd_cross` · `fusion_ma_bollinger` · `fusion_boll_kdj` · `fusion_triple`

## Code format

Shanghai: `600519` (6xxxxx) · Shenzhen: `000001` / `300750` · auto-detected. Do not prefix with `sh`/`sz`.

## Data sources

- Realtime quotes: Tencent `qt.gtimg.cn`
- Daily klines (qfq): EastMoney `push2his.eastmoney.com` (Tencent kline endpoint used as primary, EastMoney fallback on WAF throttling)
- Rate limiting + TTL caching + exponential-backoff retry built in, safe for concurrent MCP clients

All indicators are standard public formulas (MA/RSI/MACD/KDJ/Bollinger). No proprietary logic is included.

## Install

```bash
pip install astock-mcp-server
```

## Claude Desktop / any MCP client config

```json
{
  "mcpServers": {
    "astock-quant": {
      "command": "python",
      "args": ["-m", "astock_mcp_server_runner"]
    }
  }
}
```

Or run directly after cloning:

```bash
pip install mcp pandas numpy
python server.py
```

## Example

```json
{"tool": "stock_backtest", "args": {"code": "600519", "strategy": "rsi_meanreversion", "days": 500}}
```

```json
{"总收益": "25.49%", "买入持有": "3.83%", "年化": "12.13%", "夏普": 0.86, "回撤": "-9.71%", "胜率": "52%", "交易": "17次"}
```

## Disclaimer

Historical simulation and technical indicators for reference only. Not investment advice.
