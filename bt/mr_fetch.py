#!/usr/bin/env python3
"""Fetch Lighter candles + hourly funding for the mean-reversion backtest.
Markets: all active perps with >= $2M/day volume now, plus everything in the earlier breakout set.
Output: research/bt/mr/candles_{1h,15m}.json  {sym: {"market_id", "candles": [[t_ms,o,h,l,c,vol_quote],...]}}
        research/bt/mr/funding_1h.json       {sym: [[t_ms, rate_pct_per_hour], ...]}
"""
import json, os, sys, time, urllib.request, urllib.error
B = "https://mainnet.zklighter.elliot.ai/api/v1"
OUT = os.path.expanduser("~/chkm8/research/bt/mr"); os.makedirs(OUT, exist_ok=True)
NOW = int(time.time())

def get(p, tries=5):
    for i in range(tries):
        try:
            with urllib.request.urlopen(f"{B}/{p}", timeout=40) as r: return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429: time.sleep(5 * (i + 1)); continue
            return json.loads(e.read() or b"{}")
        except Exception:
            time.sleep(3 * (i + 1))
    return {}

def candles(mid, res, secs, start):
    out, end = {}, NOW
    while end > start:
        s = max(start, end - 490 * secs)
        d = get(f"candles?market_id={mid}&resolution={res}&start_timestamp={s}&end_timestamp={end}&count_back=500")
        cs = d.get("c", [])
        if not cs: break
        for c in cs: out[c["t"]] = [c["t"], c["o"], c["h"], c["l"], c["c"], c.get("V", 0)]
        end = s; time.sleep(0.15)
    return [out[k] for k in sorted(out)]

def funding(mid, start):
    out, end = {}, NOW
    while end > start:
        s = max(start, end - 490 * 3600)
        d = get(f"fundings?market_id={mid}&resolution=1h&start_timestamp={s}&end_timestamp={end}&count_back=500")
        fs = d.get("fundings", [])
        if not fs: break
        for f in fs:
            r = float(f["rate"]) * (1 if f.get("direction", "long") == "long" else -1)
            out[f["timestamp"]] = [f["timestamp"] * (1000 if f["timestamp"] < 1e12 else 1), r]
        end = s; time.sleep(0.15)
    return [out[k] for k in sorted(out)]

mk = [o for o in get("orderBookDetails")["order_book_details"] if o["market_type"] == "perp" and o.get("status") == "active"]
old = set(json.load(open(os.path.expanduser("~/chkm8/research/bt/candles_1h.json"))))
sel = [o for o in mk if float(o.get("daily_quote_token_volume") or 0) >= 2e6 or o["symbol"] in old]
print(len(sel), "markets:", " ".join(sorted(o["symbol"] for o in sel)), flush=True)

c1, c15, fu = {}, {}, {}
for i, o in enumerate(sel):
    sym, mid = o["symbol"], o["market_id"]
    c1[sym] = {"market_id": mid, "candles": candles(mid, "1h", 3600, NOW - 135 * 86400)}
    c15[sym] = {"market_id": mid, "candles": candles(mid, "15m", 900, NOW - 60 * 86400)}
    fu[sym] = funding(mid, NOW - 135 * 86400)
    print(f"{i+1}/{len(sel)} {sym}: 1h {len(c1[sym]['candles'])}  15m {len(c15[sym]['candles'])}  funding {len(fu[sym])}", flush=True)
json.dump(c1, open(f"{OUT}/candles_1h.json", "w")); json.dump(c15, open(f"{OUT}/candles_15m.json", "w"))
json.dump(fu, open(f"{OUT}/funding_1h.json", "w"))
print("saved", OUT)
