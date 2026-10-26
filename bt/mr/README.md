# Mean-reversion (buy-the-dip) backtest, 2026-10-16

Code: `../mr_fetch.py` (data), `../mr_backtest.py` (test). Raw results: `results_slip5bp.json`, `results_slip15bp.json`.

Data: 55 Lighter perps (>= $2M/day + earlier set), 1h candles ~143 days (to 2026-10-16), 15m candles ~61 days,
actual hourly funding. In-sample/out-of-sample split at 2/3 (1h: 2026-08-29, 15m: 2026-09-26).

Rules: long when close is K std-devs below SMA20 (K = 2, 2.5, 3) or RSI14 <= 25/20; filters: chop / not-downtrend /
BTC-not-crashing (each on/off); limit entry at close or 0.5 ATR lower, filled only if price trades THROUGH it; target
SMA20 (limit), stop 1/1.5/2 ATR (market + slippage), time stop 24h (1h) / 12h (15m). Lighter fees are 0. Slippage on
stops 0.05% (stress 0.15%). Pessimistic intrabar ordering. Stocks/commodities only in the US cash session.
360 variations.

## Result: no edge on crypto
- **0 of 357** variations (with enough trades) made money in BOTH halves. Median out-of-sample: about -0.15R per trade.
- Win rates were only ~30-45%: dips kept falling (stops hit 2-3x as often as targets).
- **This week** (from 10-09) was worse: -0.2 to -0.6R per trade. The chop is choppy downward, not sideways.
- The best variations hovered around 0R, and all went negative with 0.15% stop slippage.

## One lead, not a result: index/stock perps, 15m
Slicing the best 15m variation (3 std-dev dip, limit 0.5 ATR lower, stop 1.5 ATR) into crypto vs stocks/commodities:

| tradfi only | trades | win | avg R (IS) | avg R (OOS) | avg R OOS @0.15% slip |
|---|---|---|---|---|---|
| no regime filter | 191 | 44% | +0.20 | +0.10 | -0.05 |
| chop filter | 161 | 48% | +0.32 | +0.20 | +0.04 |
| not-downtrend filter | 166 | 46% | +0.24 | +0.23 | +0.07 |

Most of it came from indices: US500 +9.4R, US100 +9.1R, QQQ +8.7R, SPY +7.8R, AAPL +7.5R. Losers: TSLA, SNDK, XAU, INTC.

Caveats: found by slicing results after the fact (data snooping), only ~60 out-of-sample trades, the edge mostly
disappears at 0.15% slippage, and these perps trade 24/7 on Lighter while their underlying markets don't.
Treat it as a hypothesis for paper trading with these exact rules, not as a proven strategy.

## US hours vs overnight vs weekend (15m index dip rule, US500/US100/SPY/QQQ/AAPL, 2026-10-16)
Same rule with the US-session gate removed; trades bucketed by fill time.

| session | trades | win | avg R | avg R @0.15% slip | avg $ volume / 15m bar |
|---|---|---|---|---|---|
| US cash hours | 40 | 62% | +0.79 | +0.62 | $177k |
| weeknight (outside 09:30-16:00 ET) | 39 | 31% | -0.41 | -1.13 | $93k |
| weekend | 28 | 25% | -1.05 | -2.39 | $42k |

Off-hours dips keep falling (stops 2-4x as often as targets). Keep the US-hours gate.

## Breakout + market-regime filters (2026-10-22, regime_backtest.py, crypto only, 4h, data to 2026-10-16)
| filter | trades | win | avg R IS | avg R OOS | October |
|---|---|---|---|---|---|
| none (live rules) | 238 | 38% | +0.20 | -0.00 | 31 trades, 3% win, -28.1R |
| BTC > ~50-day avg | 228 | 37% | +0.14 | -0.00 | -28.1R (filter was ON all October) |
| BTC EMA50 > EMA200 | 190 | 37% | +0.33 | -0.08 | -28.0R |
| >50% of coins above EMA200 | 201 | 36% | +0.14 | +0.01 | -26.7R |
| >60% of coins above EMA200 | 174 | 40% | +0.50 | +0.04 | 16 trades, -16.5R |
| $5M/day volume floor | 88 | 34% | +0.06 | -0.12 | -11.3R |
No filter rescues October: every breakout failed (backtest 0-3% win, live 2/18). Only Aug-Sep made money.
Breadth > 60% halves October's losses and is OFF now (breadth 23% on 10-16), so it agrees with the pause.
