# -*- coding: utf-8 -*-
"""全局请求限流 + TTL缓存 + 501退避重试（2026-11-18）

背景：腾讯/东财行情接口对突发并发触发WAF频控(HTTP 501)。
MCP客户端会并发调多个tool，必须限流+缓存+退避。
"""
import time
import threading
import functools

_lock = threading.Lock()
_last_ts = [0.0]
MIN_INTERVAL = 1.0        # 全局最小请求间隔(秒)
RETRY_DELAYS = (2.0, 4.0, 8.0)  # 501退避序列

_cache = {}  # key -> (expire_ts, value)
CACHE_TTL = 60


def rate_wait():
    """全局节流：保证相邻HTTP请求间隔>=MIN_INTERVAL"""
    while True:
        with _lock:
            now = time.time()
            wait = _last_ts[0] + MIN_INTERVAL - now
            if wait <= 0:
                _last_ts[0] = now
                return
        time.sleep(min(wait, MIN_INTERVAL))


def cached(ttl=CACHE_TTL):
    """TTL缓存装饰器（key=函数名+args）"""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kw):
            key = (fn.__name__, args, tuple(sorted(kw.items())))
            now = time.time()
            with _lock:
                hit = _cache.get(key)
                if hit and hit[0] > now:
                    return hit[1]
            v = fn(*args, **kw)
            if v is not None:
                with _lock:
                    _cache[key] = (now + ttl, v)
            return v
        return wrapper
    return deco


def with_retry(fn, *args, **kw):
    """带退避重试的调用：501/超时按RETRY_DELAYS退避"""
    last_exc = None
    for i, delay in enumerate((0.0,) + RETRY_DELAYS):
        if delay:
            time.sleep(delay)
        try:
            rate_wait()
            return fn(*args, **kw)
        except Exception as e:  # HTTPError 501 / timeout / URLError
            last_exc = e
            continue
    raise last_exc
