# -*- coding: utf-8 -*-
"""东方财富K线数据适配器（2026-11-18）
根因：腾讯web.ifzq.gtimg.cn fqkline接口对本服务器IP触发WAF(501拦截)。
东财push2his接口公开稳定，字段：日期,开,收,高,低,成交量,成交额。
"""
import json
import urllib.request
from .rate_limit import cached, with_retry


def _secid(code: str) -> str:
    """A股代码转东财secid：沪市1.xxxx，深市0.xxxx"""
    if code.startswith(('6', '9', '5')):
        return f"1.{code}"
    return f"0.{code}"


@cached(60)
def get_klines_em(code: str, days: int = 120) -> list:
    """东方财富日K（前复权），返回与腾讯版同构的[{date,open,close,high,low,volume}]"""
    url = (f"https://push2his.eastmoney.com/api/qt/stock/kline/get"
           f"?secid={_secid(code)}&fields1=f1,f2,f3,f4,f5,f6"
           f"&fields2=f51,f52,f53,f54,f55,f56,f57&klt=101&fqt=1&lmt={days}&end=20500101")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    d = json.loads(with_retry(lambda: urllib.request.urlopen(req, timeout=15).read().decode("utf-8")))
    klines = []
    for line in (d.get("data") or {}).get("klines") or []:
        p = line.split(",")  # date,open,close,high,low,vol,amount
        klines.append({
            "date": p[0], "open": float(p[1]), "close": float(p[2]),
            "high": float(p[3]), "low": float(p[4]), "volume": float(p[5]),
        })
    return klines


# monkey-patch式注入：把TencentStockAPI.get_klines换成东财源
def patch_tencent_api():
    from finance_toolkit.mini_realtime import TencentStockAPI
    TencentStockAPI.get_klines = lambda self, code, days=120: get_klines_em(code, days)
    return TencentStockAPI
