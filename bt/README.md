# chkm8 backtest, 2026-10-08

Data: Lighter 1h candles + hourly funding, 22 crypto perps with >= $1M/day volume, 2026-06-05 to 2026-10-08
(~4 months). Raw: `candles_1h.json`, `funding_1h.json` in this folder.
Costs: 0.07% per side (fees + slippage) plus the actual hourly funding paid/received. Entry at the next bar's open.
If stop and target are both inside one bar, the stop counts first (pessimistic).
Split: first 2/3 of each market's history = in-sample (IS), last 1/3 = out-of-sample (OOS).

## Results (average R per trade; 1R = the amount risked to the stop)

| Strategy | IS | OOS | Verdict |
|---|---|---|---|
| 1h breakout (48h high/low + volume), long+short | -0.12R (n=523) | -0.17R (n=318) | loses |
| 1h trend pullback (RSI dip in uptrend) | -0.12R (n=236) | +0.18R (n=121) | inconsistent |
| 1h crowded-funding fade (short) | -0.21R (n=101) | -0.20R (n=96) | loses |
| 1h negative-funding squeeze long | -0.46R (n=28) | -0.50R (n=14) | loses |
| 4h Donchian-20 breakout, long+short | -0.05R | -0.11R | loses (shorts -0.30R avg) |
| 4h EMA20 pullback, long+short | -0.11R | -0.06R | loses |
| 4h RSI extremes reversal | -0.14R | -0.01R | flat; longs +0.43R but only n=25 |
| **4h Donchian-20 LONG only, trend filter, SL 2 ATR, TP 4 ATR** | **+0.18R (n=144)** | **+0.19R (n=107)** | **only candidate** |

Best candidate details: profit factor 1.33, still positive at 2x costs (+0.15R / +0.17R), positive on 15 of 22 markets
(best ZRO, PUMP, UNI, WLD, LINK; worst BTC, GRAM, XPL). About 2 signals per day across all markets.
Neighbouring settings (20-30 bar breakouts, 2-2.5 ATR stops, 4-5 ATR targets) all positive in both halves, so it's not
one lucky parameter.

**But it's regime-dependent:** June -4.9R, July -8.4R, August +37.3R, September +36.4R, October (so far) -13.3R.
All the profit came from the Aug-Sep alt rally.

Portfolio simulation ($194, 1.5% risk per trade, max 3 open): **$194 -> $203 (+4%) over 4 months, max drawdown 21%**
($167 low in July). 86 trades taken, 165 skipped by the 3-position cap.

**Every short variant lost money.** Shorting in this sample (a rising market) was a losing game.

## Conclusion
No robust edge yet. The trend-breakout long is the only thing that survived, and only because of two strong months;
it would have lost money in June, July and October. Run it as a paper scanner and compare signals with live results
before risking money on it.
