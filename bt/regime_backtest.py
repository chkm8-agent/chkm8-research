#!/usr/bin/env python3
"""Breakout backtest WITH market-regime filters, on fresh data (1h -> 4h, to 2026-10-16).

Strategy (unchanged from the live bot): 4h close > highest high of previous 20 bars, close > EMA50 > EMA200,
entry next bar open, stop 2 ATR, target 4 ATR, 42-bar time stop. Crypto only. Long only.
Costs: Lighter fees 0; slippage 0.05% on entry and on stop/time exits (stress 0.15%); actual hourly funding.
Pessimistic: stop checked before target inside a bar.

Regime filters (evaluated on the signal bar, using only data up to that bar):
  none      no filter (= live bot)
  btc50d    BTC daily-ish trend: BTC 4h close > BTC SMA300 (~50 days)
  btcema    BTC 4h EMA50 > EMA200 and BTC close > EMA50
  breadth   > 50% of crypto markets have close > their own EMA200
  breadth60 > 60%
  combo     btc50d AND breadth
  vol5m     market's trailing 7-day average $ volume >= $5M/day (liquidity floor), no regime filter
  combo+vol combo AND vol5m
"""
import json, os, sys, math, collections, datetime as dt

D = os.path.expanduser("~/chkm8/research/bt/mr")
TRADFI = {"XAU", "XAG", "US100", "US500", "SPY", "QQQ", "WTI", "BRENTOIL", "NATGAS", "NVDA", "AAPL", "MU", "GOOGL",
          "AMZN", "INTC", "META", "TSLA", "AMD", "MSFT", "NBIS", "HOOD", "COIN", "CRCL", "IBM", "SNDK", "SOXL", "ORCL",
          "PLTR", "MSTR", "NFLX", "AVGO", "TSM", "PONS", "IWM", "DIA", "GLD", "SLV", "TLT", "USO", "MRNA", "SKHY",
          "COPPER", "PLATINUM", "EURUSD", "USDJPY", "GBPUSD", "SPCX", "ANTHROPIC"}
H4 = 4 * 3600 * 1000


def ema(x, n):
    k = 2 / (n + 1); out = [x[0]]
    for v in x[1:]: out.append(v * k + out[-1] * (1 - k))
    return out


def to4h(cs):
    by = collections.OrderedDict()
    for c in cs: by.setdefault(c[0] - c[0] % H4, []).append(c)
    rows = [(t, v) for t, v in by.items() if len(v) == 4]
    return dict(t=[t for t, _ in rows], o=[v[0][1] for _, v in rows], h=[max(x[2] for x in v) for _, v in rows],
                l=[min(x[3] for x in v) for _, v in rows], c=[v[-1][4] for _, v in rows],
                vq=[sum(x[5] for x in v) for _, v in rows])


def prep(m):
    c, h, l = m["c"], m["h"], m["l"]
    tr = [h[0] - l[0]] + [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) for i in range(1, len(c))]
    m["atr"], m["e50"], m["e200"] = ema(tr, 14), ema(c, 50), ema(c, 200)
    m["idx"] = {t: i for i, t in enumerate(m["t"])}
    return m


def main():
    slip = float(sys.argv[1]) if len(sys.argv) > 1 else 0.0005
    raw = json.load(open(f"{D}/candles_1h.json"))
    fu = json.load(open(f"{D}/funding_1h.json"))
    fund = {s: {int(x[0]) // 3600000: x[1] for x in v} for s, v in fu.items()}
    M = {s: prep(to4h(v["candles"])) for s, v in raw.items() if s not in TRADFI and len(v["candles"]) > 1500}
    b = M["BTC"]; bc = b["c"]
    sma300 = [None] * len(bc)
    for i in range(299, len(bc)): sma300[i] = sum(bc[i - 299:i + 1]) / 300
    btc = {t: dict(b50d=(sma300[i] is not None and bc[i] > sma300[i]),
                   bema=(b["e50"][i] > b["e200"][i] and bc[i] > b["e50"][i])) for i, t in enumerate(b["t"])}
    breadth = {}
    for t in b["t"]:
        n = up = 0
        for m in M.values():
            i = m["idx"].get(t)
            if i is not None and i >= 200: n += 1; up += m["c"][i] > m["e200"][i]
        breadth[t] = up / n if n else 0
    t_all = sorted(b["t"]); cut = t_all[int(len(t_all) * 2 / 3)]

    def ok(name, sym, m, i):
        t = m["t"][i]; r = btc.get(t)
        if r is None: return False
        vol7 = sum(m["vq"][max(0, i - 41):i + 1]) / min(42, i + 1) * 6           # 6 x 4h bars per day
        f = dict(none=True, btc50d=r["b50d"], btcema=r["bema"], breadth=breadth[t] > 0.5, breadth60=breadth[t] > 0.6,
                 combo=r["b50d"] and breadth[t] > 0.5, vol5m=vol7 >= 5e6)
        f["combo+vol"] = f["combo"] and f["vol5m"]
        return f[name]

    out = {}
    for name in ("none", "btc50d", "btcema", "breadth", "breadth60", "combo", "vol5m", "combo+vol"):
        trades = []
        for sym, m in M.items():
            c, h, l, o, atr = m["c"], m["h"], m["l"], m["o"], m["atr"]; n = len(c); i = 210
            while i < n - 1:
                if not (c[i] > max(h[i - 20:i]) and c[i] > m["e50"][i] > m["e200"][i]) or not ok(name, sym, m, i):
                    i += 1; continue
                j = i + 1; entry = o[j] * (1 + slip); sl = entry - 2 * atr[i]; tp = entry + 4 * atr[i]
                ex = reason = None
                for k in range(j, min(n, j + 42)):
                    if l[k] <= sl: ex, reason = min(sl, o[k]) * (1 - slip), "stop"; break
                    if h[k] >= tp: ex, reason = max(tp, o[k]), "target"; break
                if ex is None: k = min(n - 1, j + 41); ex, reason = c[k] * (1 - slip), "time"
                fr = sum(fund.get(sym, {}).get(hh, 0.0) for hh in range(m["t"][j] // 3600000, m["t"][k] // 3600000 + 4)) / 100
                R = (ex / entry - 1 - fr) / ((entry - sl) / entry)
                trades.append((m["t"][j], sym, reason, R)); i = k + 1
        trades.sort()

        def st(x):
            if not x: return "n=0"
            R = [y[3] for y in x]; w = sum(1 for r in R if r > 0)
            return f"n={len(R):3} win={100*w/len(R):3.0f}% avg={sum(R)/len(R):+.2f}R sum={sum(R):+6.1f}R"
        mon = collections.defaultdict(float)
        for x in trades: mon[dt.datetime.fromtimestamp(x[0] / 1000, dt.timezone.utc).strftime("%m")] += x[3]
        since = int(dt.datetime(2026, 10, 1, tzinfo=dt.timezone.utc).timestamp() * 1000)
        print(f"{name:10} ALL {st(trades)} | IS {st([x for x in trades if x[0] < cut])} | OOS {st([x for x in trades if x[0] >= cut])}"
              f" | Oct {st([x for x in trades if x[0] >= since])}")
        print(f"{'':10} by month R: " + " ".join(f"{k}:{v:+.1f}" for k, v in sorted(mon.items())))
        out[name] = [list(x) for x in trades]
    on = sum(1 for t in b["t"] if btc[t]["b50d"] and breadth[t] > 0.5) / len(b["t"])
    print(f"\ncrypto markets: {len(M)} | split {dt.datetime.fromtimestamp(cut/1000, dt.timezone.utc):%Y-%m-%d} | "
          f"combo filter ON {on:.0%} of the time | latest: BTC>SMA300 {btc[b['t'][-1]]['b50d']}, breadth {breadth[b['t'][-1]]:.0%}")
    json.dump(out, open(f"{D}/regime_trades_slip{int(slip*1e4)}bp.json", "w"))


if __name__ == "__main__":
    main()
