#!/usr/bin/env python3
"""chkm8 'Five Chains' digest collector: BTC, ETH, NEAR, ZEC, XMR and their ecosystems (stdlib only).
Prints a compact brief for the writing agent and saves raw JSON to ~/chkm8/wiki/raw/chains/YYYY-MM-DD.json.
Day-over-day deltas are computed against the previous raw file."""
import json, os, subprocess, time, urllib.request, urllib.parse, urllib.error, collections
from datetime import datetime, timezone

HOME = os.path.expanduser("~/chkm8")
RAW = f"{HOME}/wiki/raw/chains"
XURL = "/opt/homebrew/bin/xurl"
COINS = {"bitcoin": "BTC", "ethereum": "ETH", "near": "NEAR", "zcash": "ZEC", "monero": "XMR"}
ECOS = {"BTC": "bitcoin-ecosystem", "ETH": "ethereum-ecosystem", "NEAR": "near-protocol-ecosystem",
        "PRIVACY": "privacy-coins"}
STABLE = {"usdt", "usdc", "dai", "usde", "usds", "fdusd", "pyusd", "tusd", "usd1", "rlusd", "usdg", "frax", "susde",
          "susds", "wbtc", "weth", "steth", "wsteth", "cbbtc", "weeth", "reth", "lbtc", "solvbtc", "usdtb", "gho", "crvusd"}

def get(url, data=None, headers=None, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers={"User-Agent": "chkm8-chains/1.0",
                                                                  "Accept": "application/json", **(headers or {})})
            return json.load(urllib.request.urlopen(req, timeout=40))
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < tries - 1: time.sleep(20 * (i + 1)); continue
            if e.code < 500 or i == tries - 1:
                try: return json.loads(e.read() or b"{}")
                except Exception: return {}
        except Exception:
            if i == tries - 1: return {}
        time.sleep(4 * (i + 1))

def cg(path):
    time.sleep(2.5)                      # stay under the free-tier rate limit
    return get("https://api.coingecko.com/api/v3/" + path)

def pct(x): return f"{x:+.1f}%" if isinstance(x, (int, float)) else "n/a"
def usd(x):
    if not isinstance(x, (int, float)): return "n/a"
    for d, s in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(x) >= d: return f"${x / d:.2f}{s}"
    return f"${x:,.2f}"
def dd(cur, prev):
    try: return f" ({(float(cur) / float(prev) - 1) * 100:+.1f}% d/d)" if prev else ""
    except Exception: return ""

def xsearch(q, n=10):
    path = (f"/2/tweets/search/recent?query={urllib.parse.quote(q)}&max_results={max(10, n)}&sort_order=relevancy"
            "&tweet.fields=public_metrics,created_at")
    try:
        return json.loads(subprocess.run([XURL, path], capture_output=True, text=True, timeout=60).stdout)
    except Exception as e:
        return {"error": str(e)}

def main():
    os.makedirs(RAW, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d")
    prev = {}
    for f in sorted(os.listdir(RAW), reverse=True):
        if f.endswith(".json") and not f.startswith(stamp):
            try: prev = json.load(open(f"{RAW}/{f}")); break
            except Exception: pass
    P = lambda *ks: _dig(prev, ks)
    out = {"generated_utc": datetime.now(timezone.utc).isoformat()}
    L = []

    # ---- scoreboard
    mk = cg("coins/markets?vs_currency=usd&ids=" + ",".join(COINS) + "&price_change_percentage=24h,7d,30d") or []
    if isinstance(mk, dict): mk = []
    btc = next((c for c in mk if c["id"] == "bitcoin"), {})
    out["coins"] = {}
    L.append("## SCOREBOARD (CoinGecko)")
    for c in sorted(mk, key=lambda c: list(COINS).index(c["id"])):
        s = COINS[c["id"]]
        rel = None
        if btc and c["id"] != "bitcoin" and c.get("price_change_percentage_7d_in_currency") is not None:
            rel = c["price_change_percentage_7d_in_currency"] - btc.get("price_change_percentage_7d_in_currency", 0)
        out["coins"][s] = {k: c.get(k) for k in ("current_price", "market_cap", "market_cap_rank", "total_volume",
                           "price_change_percentage_24h_in_currency", "price_change_percentage_7d_in_currency",
                           "price_change_percentage_30d_in_currency", "ath", "ath_change_percentage", "circulating_supply")}
        L.append(f"- {s} ${c['current_price']:,.4g} | 24h {pct(c.get('price_change_percentage_24h_in_currency'))} | "
                 f"7d {pct(c.get('price_change_percentage_7d_in_currency'))} | 30d {pct(c.get('price_change_percentage_30d_in_currency'))} | "
                 f"mcap {usd(c.get('market_cap'))} (#{c.get('market_cap_rank')}) | vol {usd(c.get('total_volume'))} | "
                 f"{pct(c.get('ath_change_percentage'))} from ATH" + (f" | 7d vs BTC {rel:+.1f}pp" if rel is not None else ""))

    # ---- Lighter perps positioning for the five
    LB = "https://mainnet.zklighter.elliot.ai/api/v1"
    ob = {o["symbol"]: o for o in get(f"{LB}/orderBookDetails").get("order_book_details", []) if o.get("market_type") == "perp"}
    fr = collections.defaultdict(dict)
    for x in get(f"{LB}/funding-rates").get("funding_rates", []): fr[x["symbol"]][x["exchange"]] = x["rate"]
    rows = []
    for s in COINS.values():
        o = ob.get(s)
        if o:
            rows.append(f"{s} OI {usd(float(o['open_interest']) * float(o['last_trade_price']))}, funding Lighter "
                        f"{(fr[s].get('lighter') or 0) * 100:+.4f}% / Binance {(fr[s].get('binance') or 0) * 100:+.4f}%")
            out.setdefault("perps", {})[s] = {"oi_usd": float(o["open_interest"]) * float(o["last_trade_price"]),
                                              "fund_lighter": fr[s].get("lighter"), "fund_binance": fr[s].get("binance")}
        else:
            rows.append(f"{s}: no Lighter perp")
    L.append("Perps (Lighter): " + " | ".join(rows))

    # ---- chain TVL + stablecoins
    chains = get("https://api.llama.fi/v2/chains") or []
    if isinstance(chains, dict): chains = []
    tvl = {c["name"]: c.get("tvl") for c in chains}
    st = get("https://stablecoins.llama.fi/stablecoinchains") or []
    if isinstance(st, dict): st = []
    stab = {c["name"]: (c.get("totalCirculatingUSD") or {}).get("peggedUSD") for c in st}
    out["tvl"] = {k: tvl.get(k) for k in ("Bitcoin", "Ethereum", "Near")}
    out["stables"] = {k: stab.get(k) for k in ("Bitcoin", "Ethereum", "Near")}

    # ---- BITCOIN
    b = get("https://api.blockchair.com/bitcoin/stats").get("data", {})
    fees = get("https://mempool.space/api/v1/fees/recommended")
    da = get("https://mempool.space/api/v1/difficulty-adjustment")
    out["btc_chain"] = {"tx_24h": b.get("transactions_24h"), "mempool_tx": b.get("mempool_transactions"),
                        "hashrate_24h": float(b.get("hashrate_24h") or 0), "avg_fee_usd": b.get("average_transaction_fee_usd_24h"),
                        "fees": fees, "diff_adj": {k: da.get(k) for k in ("difficultyChange", "progressPercent", "remainingBlocks", "estimatedRetargetDate")},
                        "nodes": b.get("nodes")}
    hb = out["btc_chain"]
    L.append("\n## BITCOIN CHAIN")
    L.append(f"Tx 24h {hb['tx_24h']:,}{dd(hb['tx_24h'], P('btc_chain', 'tx_24h'))} | mempool {hb['mempool_tx']:,} tx | "
             f"fees fastest {fees.get('fastestFee')} / hour {fees.get('hourFee')} sat/vB | avg fee ${hb['avg_fee_usd'] or 0:.2f} | "
             f"hashrate {hb['hashrate_24h'] / 1e18:,.0f} EH/s{dd(hb['hashrate_24h'], P('btc_chain', 'hashrate_24h'))} | "
             f"next difficulty adj {pct(da.get('difficultyChange'))} in {da.get('remainingBlocks')} blocks | "
             f"BTC-chain DeFi TVL {usd(tvl.get('Bitcoin'))}{dd(tvl.get('Bitcoin'), P('tvl', 'Bitcoin'))}")

    # ---- ETHEREUM
    gas = get("https://ethereum-rpc.publicnode.com", data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_gasPrice", "params": []}).encode(),
              headers={"Content-Type": "application/json"})
    gwei = int(gas.get("result", "0x0"), 16) / 1e9 if gas.get("result") else None
    edex = get("https://api.llama.fi/overview/dexs/ethereum?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true")
    efee = get("https://api.llama.fi/overview/fees/ethereum?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true")
    out["eth_chain"] = {"gas_gwei": gwei, "dex_24h": edex.get("total24h"), "dex_chg_7d": edex.get("change_7d"),
                        "dex_chg_1m": edex.get("change_1m"), "fees_24h": efee.get("total24h"), "fees_chg_7d": efee.get("change_7d"),
                        "fees_chg_1m": efee.get("change_1m")}
    top_eth = sorted([p for p in edex.get("protocols", []) if p.get("total24h")], key=lambda p: -p["total24h"])[:5]
    he = out["eth_chain"]
    L.append("\n## ETHEREUM CHAIN")
    L.append(f"Gas {gwei:.2f} gwei | " if gwei is not None else "Gas n/a | ")
    L[-1] += (f"DEX vol 24h {usd(he['dex_24h'])} (7d {pct(he['dex_chg_7d'])}, 1m {pct(he['dex_chg_1m'])}) | "
              f"app fees on Ethereum 24h {usd(he['fees_24h'])} (7d {pct(he['fees_chg_7d'])}, 1m {pct(he['fees_chg_1m'])}) | "
              f"TVL {usd(tvl.get('Ethereum'))}{dd(tvl.get('Ethereum'), P('tvl', 'Ethereum'))} | "
              f"stablecoins {usd(stab.get('Ethereum'))}{dd(stab.get('Ethereum'), P('stables', 'Ethereum'))}")
    L.append("Top Ethereum DEXs 24h: " + "; ".join(f"{p['name']} {usd(p['total24h'])} ({pct(p.get('change_1d'))})" for p in top_eth))

    # ---- NEAR
    ni = get("https://api.llama.fi/summary/dexs/near-intents?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true")
    nfee = get("https://api.llama.fi/overview/fees/near?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true")
    out["near_chain"] = {"intents_24h": ni.get("total24h"), "intents_7d": ni.get("total7d"), "intents_30d": ni.get("total30d"),
                         "intents_chg_1d": ni.get("change_1d"), "fees_24h": nfee.get("total24h"), "fees_chg_1m": nfee.get("change_1m")}
    hn = out["near_chain"]
    L.append("\n## NEAR CHAIN")
    L.append(f"NEAR Intents volume 24h {usd(hn['intents_24h'])} ({pct(hn['intents_chg_1d'])} d/d), 7d {usd(hn['intents_7d'])}, "
             f"30d {usd(hn['intents_30d'])} | app fees on NEAR 24h {usd(hn['fees_24h'])} (1m {pct(hn['fees_chg_1m'])}) | "
             f"TVL {usd(tvl.get('Near'))}{dd(tvl.get('Near'), P('tvl', 'Near'))} | stablecoins {usd(stab.get('Near'))}")

    # ---- ZCASH
    z = get("https://api.blockchair.com/zcash/stats").get("data", {})
    out["zec_chain"] = {"tx_24h": z.get("transactions_24h"), "blocks_24h": z.get("blocks_24h"), "hashrate_24h": float(z.get("hashrate_24h") or 0),
                        "mempool_tx": z.get("mempool_transactions"), "nodes": z.get("nodes"),
                        "largest_tx_usd": (z.get("largest_transaction_24h") or {}).get("value_usd"),
                        "median_fee_usd": z.get("median_transaction_fee_usd_24h")}
    hz = out["zec_chain"]
    L.append("\n## ZCASH CHAIN")
    L.append(f"Tx 24h {hz['tx_24h']:,}{dd(hz['tx_24h'], P('zec_chain', 'tx_24h'))} | blocks {hz['blocks_24h']} | "
             f"hashrate {hz['hashrate_24h'] / 1e9:,.1f} GSol/s{dd(hz['hashrate_24h'], P('zec_chain', 'hashrate_24h'))} | "
             f"nodes {hz['nodes']} | median fee ${hz['median_fee_usd'] or 0:.3f} | largest tx 24h {usd(hz['largest_tx_usd'])} "
             f"(transparent-visible only; shielded activity not measured here)")

    # ---- MONERO
    x = get("https://xmrchain.net/api/networkinfo").get("data", {})
    out["xmr_chain"] = {"hash_rate": x.get("hash_rate"), "difficulty": x.get("difficulty"), "tx_pool": x.get("tx_pool_size"),
                        "height": x.get("height"), "tx_count": x.get("tx_count")}
    hx = out["xmr_chain"]
    ptx = P("xmr_chain", "tx_count")
    L.append("\n## MONERO CHAIN")
    L.append(f"Hashrate {(hx['hash_rate'] or 0) / 1e9:,.2f} GH/s{dd(hx['hash_rate'], P('xmr_chain', 'hash_rate'))} | "
             f"tx pool {hx['tx_pool']} | height {hx['height']:,}" +
             (f" | tx since last report {hx['tx_count'] - ptx:,}" if ptx and hx.get("tx_count") else ""))

    # ---- ecosystems: category moves + top movers
    cats = cg("coins/categories") or []
    if isinstance(cats, dict): cats = []
    cmap = {c["id"]: c for c in cats}
    out["ecosystems"] = {}
    L.append("\n## ECOSYSTEMS (CoinGecko categories; tokens >$20M mcap, ex-stables/wrapped)")
    for label, cid in ECOS.items():
        c = cmap.get(cid, {})
        toks = cg(f"coins/markets?vs_currency=usd&category={cid}&order=market_cap_desc&per_page=100&page=1&price_change_percentage=24h,7d") or []
        if isinstance(toks, dict): toks = []
        toks = [t for t in toks if t["symbol"].lower() not in STABLE and t["id"] not in COINS and (t.get("market_cap") or 0) >= 2e7
                and t.get("price_change_percentage_24h_in_currency") is not None]
        g = sorted(toks, key=lambda t: -t["price_change_percentage_24h_in_currency"])[:5]
        lo = sorted(toks, key=lambda t: t["price_change_percentage_24h_in_currency"])[:3]
        w7 = sorted([t for t in toks if t.get("price_change_percentage_7d_in_currency") is not None],
                    key=lambda t: -t["price_change_percentage_7d_in_currency"])[:5]
        f = lambda t, k: f"{t['symbol'].upper()} ({t['name']}) {pct(t[k])} mcap {usd(t.get('market_cap'))}"
        out["ecosystems"][label] = {"cat_mcap": c.get("market_cap"), "cat_chg_24h": c.get("market_cap_change_24h"),
                                    "gainers": [(t["symbol"], t["name"], t["price_change_percentage_24h_in_currency"], t.get("market_cap")) for t in g],
                                    "losers": [(t["symbol"], t["name"], t["price_change_percentage_24h_in_currency"]) for t in lo],
                                    "best_7d": [(t["symbol"], t["name"], t.get("price_change_percentage_7d_in_currency")) for t in w7]}
        L.append(f"{label}: category mcap {usd(c.get('market_cap'))} ({pct(c.get('market_cap_change_24h'))} 24h), {len(toks)} liquid tokens")
        L.append("  24h up: " + "; ".join(f(t, "price_change_percentage_24h_in_currency") for t in g))
        L.append("  24h down: " + "; ".join(f(t, "price_change_percentage_24h_in_currency") for t in lo))
        L.append("  7d best: " + "; ".join(f(t, "price_change_percentage_7d_in_currency") for t in w7))

    # ---- CT chatter (NEAR / ZEC / XMR; BTC & ETH chatter is mostly noise)
    L.append("\n## X / CT CHATTER (relevancy-ranked samples)")
    out["x"] = {}
    for s in ("NEAR", "ZEC", "XMR"):
        r = xsearch(f"${s} -is:retweet -is:reply lang:en", 10)
        ts = sorted(r.get("data", []), key=lambda t: -(t["public_metrics"]["like_count"] + 2 * t["public_metrics"]["retweet_count"]))
        out["x"][s] = [t["text"] for t in ts]
        L.append(f"${s} ({len(ts)}):")
        L += [f"- [{t['public_metrics']['like_count']}♥] " + t["text"].replace("\n", " ")[:200] for t in ts[:6]]

    json.dump(out, open(f"{RAW}/{stamp}.json", "w"), indent=1, default=str)
    L.append(f"\n(raw: {RAW}/{stamp}.json; d/d deltas vs {('previous file' if prev else 'n/a, first run')})")
    print("\n".join(L))

def _dig(d, ks):
    for k in ks:
        if not isinstance(d, dict): return None
        d = d.get(k)
    return d

if __name__ == "__main__":
    main()
