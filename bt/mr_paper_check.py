#!/usr/bin/env python3
"""Check that lighter/paper_mr.py (live paper bot, bar-by-bar) reproduces research/bt/mr_backtest.py on history."""
import json, os, sys
os.environ.setdefault("CHKM8_LOGS", "-")
H = os.path.expanduser("~/chkm8")
sys.path[:0] = [f"{H}/lighter", f"{H}/research/bt"]
import paper_mr as pm, mr_backtest as bt
pm.log = lambda s: None

raw = json.load(open(f"{bt.D}/candles_15m.json")); fu = json.load(open(f"{bt.D}/funding_1h.json"))
fund = {s: {int(x[0]) // 3600000: x[1] for x in v} for s, v in fu.items()}
def fund_fn(sym, a, b): return sum(fund[sym].get(hh, 0.0) for hh in range(a // 3600000, b // 3600000 + 1))

P = dict(sig="z", k=3.0, reg="notdown", btc=False, off=0.5, slm=1.5, max=48)
tot_bt = tot_live = 0
for sym in pm.MARKETS:
    cs = [x[:5] for x in raw[sym]["candles"]]
    m_bt = bt.prep(raw[sym]["candles"], 0.25); ref = bt.simulate(sym, m_bt, fund.get(sym, {}), {}, P, pm.SLIP)
    m = pm.indicators(cs); st = pm.new_state(); st["pending"][sym] = []
    for k in range(len(cs) - 3): pm.step(st, sym, m, k, fund_fn)
    cut = m["t"][-60]                                        # ignore trades the backtest truncated at the end
    a = [(x[0], x[2], round(x[3], 4)) for x in ref if x[0] < cut]
    b = [(c["fill_t"], c["reason"], round(c["R"], 4)) for c in st["closed"] if c["fill_t"] < cut]
    same = sum(1 for x in a if x in set(b))
    print(f"{sym:6} backtest {len(a):3} trades {sum(x[2] for x in a):+7.2f}R | live-bot {len(b):3} trades "
          f"{sum(x[2] for x in b):+7.2f}R | identical trades {same}/{len(a)}")
    if a != b:
        for x, y in zip(a, b):
            if x != y: print("   first diff:", x, "vs", y); break
    tot_bt += sum(x[2] for x in a); tot_live += sum(x[2] for x in b)
print(f"TOTAL backtest {tot_bt:+.2f}R  live-bot {tot_live:+.2f}R")
