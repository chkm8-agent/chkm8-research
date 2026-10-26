#!/usr/bin/env python3
"""Mean-reversion (buy-the-dip) backtest on Lighter perps. Data from mr_fetch.py.

Rules tested (long only):
  signal on a CLOSED bar i:  z = (close - SMA20) / std20 <= -K   or   RSI14 <= R
  regime filter:  none | chop (|EMA50/EMA200 - 1| small) | notdown (EMA50 >= 0.99 x EMA200)
  BTC filter:     off | on (skip if BTC is down > 3% over the last 24h)
  stocks/commodities: only bars inside the US cash session
  entry:  limit buy at close[i] - OFF x ATR, valid 2 bars; fills only if price trades THROUGH it
          (low < limit; fill at min(open, limit))
  exit:   target = SMA20 at signal time (limit, exact price; needs high > target)
          stop   = entry - SLM x ATR (market: fill at min(stop, open) minus slippage)
          time   = MAX bars, at close minus slippage
  pessimistic: on the fill bar only the stop is checked; stop beats target inside a bar
  costs:  Lighter fees are 0 (maker/taker 0.0000); stop/time slippage 0.05% (stress 0.15%);
          actual hourly funding (longs pay when rate > 0, receive when < 0)
  one position per market at a time; IS = first 2/3 of the period, OOS = last 1/3
"""
import json, os, sys, math, itertools, datetime as dt, collections

D = os.path.expanduser("~/chkm8/research/bt/mr")
TRADFI = {"XAU", "XAG", "US100", "US500", "SPY", "QQQ", "WTI", "BRENTOIL", "NATGAS", "NVDA", "AAPL", "MU", "GOOGL",
          "AMZN", "INTC", "META", "TSLA", "AMD", "MSFT", "NBIS", "HOOD", "COIN", "CRCL", "IBM", "SNDK", "SOXL", "ORCL",
          "PLTR", "MSTR", "NFLX", "AVGO", "TSM", "PONS", "IWM", "DIA", "GLD", "SLV", "TLT", "USO", "MRNA", "SKHY",
          "COPPER", "PLATINUM", "EURUSD", "USDJPY", "GBPUSD"}
WEEK_START = int(dt.datetime(2026, 10, 9, tzinfo=dt.timezone.utc).timestamp() * 1000)


def ema(x, n):
    k = 2 / (n + 1); out = [x[0]]
    for v in x[1:]: out.append(v * k + out[-1] * (1 - k))
    return out


def prep(cs, tf_h):
    t = [c[0] for c in cs]; o = [c[1] for c in cs]; h = [c[2] for c in cs]; l = [c[3] for c in cs]; c = [c[4] for c in cs]
    n = len(c)
    sma, sd = [None] * n, [None] * n
    for i in range(19, n):
        w = c[i - 19:i + 1]; m = sum(w) / 20
        sma[i] = m; sd[i] = math.sqrt(sum((v - m) ** 2 for v in w) / 20)
    rsi = [None] * n; ag = al = 0.0
    for i in range(1, n):
        ch = c[i] - c[i - 1]; g, lo = max(ch, 0), max(-ch, 0)
        if i <= 14: ag += g / 14; al += lo / 14
        else: ag = (ag * 13 + g) / 14; al = (al * 13 + lo) / 14
        if i >= 14: rsi[i] = 100 - 100 / (1 + ag / al) if al else 100
    tr = [h[0] - l[0]] + [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) for i in range(1, n)]
    return dict(t=t, o=o, h=h, l=l, c=c, sma=sma, sd=sd, rsi=rsi, atr=ema(tr, 14), e50=ema(c, 50), e200=ema(c, 200),
                tf_h=tf_h)


def us_session(t_ms):
    d = dt.datetime.fromtimestamp(t_ms / 1000, dt.timezone.utc)
    return d.weekday() < 5 and 13 * 60 + 30 <= d.hour * 60 + d.minute < 20 * 60


def simulate(sym, m, fund, btc_ret, P, slip):
    t, o, h, l, c, atr = m["t"], m["o"], m["h"], m["l"], m["c"], m["atr"]
    n = len(c); trades = []; i = 210; chop_thr = 0.03 if m["tf_h"] == 1 else 0.015
    tradfi = sym in TRADFI
    while i < n - 3:
        if m["sma"][i] is None or m["sd"][i] in (None, 0): i += 1; continue
        z = (c[i] - m["sma"][i]) / m["sd"][i]
        sig = (z <= -P["k"]) if P["sig"] == "z" else (m["rsi"][i] is not None and m["rsi"][i] <= P["k"])
        if not sig: i += 1; continue
        r = m["e50"][i] / m["e200"][i] - 1
        if P["reg"] == "chop" and abs(r) >= chop_thr: i += 1; continue
        if P["reg"] == "notdown" and r < -0.01: i += 1; continue
        if P["btc"] and btc_ret.get(t[i], 0) < -0.03: i += 1; continue
        if tradfi and not us_session(t[i]): i += 1; continue
        lim = c[i] - P["off"] * atr[i]; tgt = m["sma"][i]
        j, entry = None, None
        for k in (i + 1, i + 2):
            if k < n and l[k] < lim: j, entry = k, min(o[k], lim); break
        if j is None or tgt <= entry: i += 1; continue
        stop = entry - P["slm"] * atr[i]
        ex = reason = None; k = j
        if l[j] <= stop: ex, reason = min(stop, o[j]) * (1 - slip), "stop"
        else:
            for k in range(j + 1, min(n, j + 1 + P["max"])):
                if l[k] <= stop: ex, reason = min(stop, o[k]) * (1 - slip), "stop"; break
                if h[k] > tgt: ex, reason = max(tgt, o[k]), "target"; break
            if ex is None: k = min(n - 1, j + P["max"]); ex, reason = c[k] * (1 - slip), "time"
        hrs = range(t[j] // 3600000, t[k] // 3600000 + 1)
        fr = sum(fund.get(hh, 0.0) for hh in hrs) / 100
        pnl = ex / entry - 1 - fr
        risk = (entry - stop) / entry
        trades.append((t[j], sym, reason, pnl / risk, pnl, fr))
        i = k + 1
    return trades


def stats(tr):
    if not tr: return dict(n=0)
    R = [x[3] for x in tr]; w = [x for x in R if x > 0]; lo = [x for x in R if x <= 0]
    return dict(n=len(R), win=round(100 * len(w) / len(R)), avgR=round(sum(R) / len(R), 3), sumR=round(sum(R), 1),
                pf=round(sum(w) / -sum(lo), 2) if lo and sum(lo) else None)


def main():
    slip = float(sys.argv[1]) if len(sys.argv) > 1 else 0.0005
    fu = json.load(open(f"{D}/funding_1h.json"))
    fund = {s: {int(x[0]) // 3600000: x[1] for x in v} for s, v in fu.items()}
    out = {}
    for tf, tf_h, mx in (("1h", 1, 24), ("15m", 0.25, 48)):
        raw = json.load(open(f"{D}/candles_{tf}.json"))
        M = {s: prep(v["candles"], tf_h) for s, v in raw.items() if len(v["candles"]) > 300}
        b = M["BTC"]; per = int(24 / tf_h)
        btc_ret = {b["t"][i]: b["c"][i] / b["c"][i - per] - 1 for i in range(per, len(b["c"]))}
        t_all = sorted({x for m in M.values() for x in m["t"]}); cut = t_all[int(len(t_all) * 2 / 3)]
        grid = []
        for sig, k in (("z", 2.0), ("z", 2.5), ("z", 3.0), ("rsi", 25), ("rsi", 20)):
            for reg, btc, off, slm in itertools.product(("none", "chop", "notdown"), (False, True), (0.0, 0.5), (1.0, 1.5, 2.0)):
                grid.append(dict(sig=sig, k=k, reg=reg, btc=btc, off=off, slm=slm, max=mx))
        for P in grid:
            tr = []
            for s, m in M.items(): tr += simulate(s, m, fund.get(s, {}), btc_ret, P, slip)
            tr.sort()
            key = f"{tf}|{P['sig']}{P['k']}|{P['reg']}|btc={int(P['btc'])}|off={P['off']}|sl={P['slm']}"
            months = collections.defaultdict(float)
            for x in tr: months[dt.datetime.fromtimestamp(x[0] / 1000, dt.timezone.utc).strftime("%Y-%m")] += x[3]
            out[key] = dict(all=stats(tr), IS=stats([x for x in tr if x[0] < cut]), OOS=stats([x for x in tr if x[0] >= cut]),
                            week=stats([x for x in tr if x[0] >= WEEK_START]),
                            crypto=stats([x for x in tr if x[1] not in TRADFI]), tradfi=stats([x for x in tr if x[1] in TRADFI]),
                            months={k2: round(v, 1) for k2, v in sorted(months.items())},
                            reasons=dict(collections.Counter(x[2] for x in tr)),
                            fund_bps=round(1e4 * sum(x[5] for x in tr) / max(1, len(tr)), 2),
                            cut=dt.datetime.fromtimestamp(cut / 1000, dt.timezone.utc).strftime("%Y-%m-%d"))
        print(tf, "done", len(grid), "configs", flush=True)
    json.dump(out, open(f"{D}/results_slip{int(slip*1e4)}bp.json", "w"), indent=1)
    print("saved", f"{D}/results_slip{int(slip*1e4)}bp.json")


if __name__ == "__main__":
    main()
