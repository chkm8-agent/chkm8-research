#!/usr/bin/env python3
"""chkm8 morning digest collector (stdlib only).
Pulls CoinGecko (global, trending, movers, categories), DefiLlama chain TVL, Lighter perps
(movers, funding extremes), X cashtag chatter, and scores past watchlist signals.
Writes raw JSON to ~/chkm8/wiki/raw/digests/YYYY-MM-DD.json and prints a compact text brief
(this stdout is what the digest agent reads)."""
import json, os, re, subprocess, time, urllib.request, urllib.parse, urllib.error, collections
from datetime import datetime, timezone

HOME = os.path.expanduser("~/chkm8")
WIKI = f"{HOME}/wiki"
RAW = f"{WIKI}/raw/digests"
SIGNALS = f"{WIKI}/signals.json"
XURL = "/opt/homebrew/bin/xurl"
X_BROAD = 30          # posts for the broad CT query  (~$0.005/post)
X_PER_TICKER = 10     # posts per top-chatter ticker
X_TICKERS = 2         # how many tickers get a dedicated sentiment pull
STABLES = {"usdt", "usdc", "dai", "fdusd", "usde", "usds", "pyusd", "tusd", "usdd", "susde", "usd1", "rlusd",
           "usdg", "busd", "frax", "gusd", "lusd", "eurc", "usdtb", "bsc-usd", "usdf", "usdx", "susds", "wbtc",
           "weth", "steth", "wsteth", "cbbtc", "weeth", "reth", "wbeth", "lbtc", "solvbtc", "bnsol", "jitosol", "msol"}

def get(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "chkm8-digest/1.0", "Accept": "application/json"})
            return json.load(urllib.request.urlopen(req, timeout=40))
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < tries - 1:
                time.sleep(20 * (i + 1)); continue
            if e.code < 500 or i == tries - 1:
                try: return json.loads(e.read() or b"{}")
                except Exception: return {}
        except Exception:
            if i == tries - 1: return {}
        time.sleep(5 * (i + 1))

def cg(path): return get("https://api.coingecko.com/api/v3/" + path)

def pct(x): return f"{x:+.1f}%" if isinstance(x, (int, float)) else "n/a"
def usd(x):
    if not isinstance(x, (int, float)): return "n/a"
    for div, s in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(x) >= div: return f"${x/div:.2f}{s}"
    return f"${x:.2f}"

def xsearch(query, n):
    q = urllib.parse.quote(query)
    path = (f"/2/tweets/search/recent?query={q}&max_results={max(10, min(100, n))}&sort_order=relevancy"
            "&tweet.fields=public_metrics,entities,created_at&expansions=author_id&user.fields=username,public_metrics")
    try:
        r = subprocess.run([XURL, path], capture_output=True, text=True, timeout=60)
        return json.loads(r.stdout)
    except Exception as e:
        return {"error": str(e)}

def main():
    os.makedirs(RAW, exist_ok=True)
    out = {"generated_utc": datetime.now(timezone.utc).isoformat()}
    L = []

    # ---- global
    g = cg("global").get("data", {})
    out["global"] = {k: g.get(k) for k in ("market_cap_change_percentage_24h_usd",)}
    mc = g.get("total_market_cap", {}).get("usd"); vol = g.get("total_volume", {}).get("usd")
    dom = g.get("market_cap_percentage", {})
    out["global"].update(mcap=mc, volume=vol, btc_dom=dom.get("btc"), eth_dom=dom.get("eth"))
    L.append("## MARKET")
    L.append(f"Total mcap {usd(mc)} ({pct(g.get('market_cap_change_percentage_24h_usd'))} 24h) | 24h vol {usd(vol)} | "
             f"BTC dom {dom.get('btc', 0):.1f}% | ETH dom {dom.get('eth', 0):.1f}%")

    # ---- markets (top 250 by volume) for majors + movers
    mk = cg("coins/markets?vs_currency=usd&order=volume_desc&per_page=250&page=1&price_change_percentage=24h,7d") or []
    if isinstance(mk, dict): mk = []
    by_sym = {c["symbol"].lower(): c for c in mk}
    majors = []
    for s in ("btc", "eth", "sol", "bnb", "xrp", "hype"):
        c = by_sym.get(s)
        if c: majors.append(f"{s.upper()} ${c['current_price']:,.4g} ({pct(c.get('price_change_percentage_24h_in_currency'))} 24h, "
                            f"{pct(c.get('price_change_percentage_7d_in_currency'))} 7d)")
    L.append("Majors: " + " | ".join(majors))
    alts = [c for c in mk if c["symbol"].lower() not in STABLES and (c.get("market_cap") or 0) >= 1e8
            and c.get("price_change_percentage_24h_in_currency") is not None]
    gain = sorted(alts, key=lambda c: -c["price_change_percentage_24h_in_currency"])[:10]
    lose = sorted(alts, key=lambda c: c["price_change_percentage_24h_in_currency"])[:8]
    up = sum(1 for c in alts if c["price_change_percentage_24h_in_currency"] > 0)
    out["breadth"] = {"up": up, "total": len(alts)}
    L.append(f"Breadth (liquid alts >$100M mcap): {up}/{len(alts)} green 24h")
    fmt = lambda c: (f"{c['symbol'].upper()} ({c['name']}) {pct(c['price_change_percentage_24h_in_currency'])} 24h, "
                     f"{pct(c.get('price_change_percentage_7d_in_currency'))} 7d, mcap {usd(c.get('market_cap'))}, vol {usd(c.get('total_volume'))}")
    L.append("\n## TOP GAINERS 24h"); L += ["- " + fmt(c) for c in gain]
    L.append("\n## TOP LOSERS 24h"); L += ["- " + fmt(c) for c in lose]
    out["gainers"] = [{k: c.get(k) for k in ("id", "symbol", "name", "current_price", "market_cap", "total_volume",
                       "price_change_percentage_24h_in_currency", "price_change_percentage_7d_in_currency")} for c in gain]
    out["losers"] = [{k: c.get(k) for k in ("id", "symbol", "name", "current_price", "market_cap",
                      "price_change_percentage_24h_in_currency", "price_change_percentage_7d_in_currency")} for c in lose]

    # ---- trending (CoinGecko search trends = what people are looking up)
    tr = cg("search/trending")
    tcoins = []
    for c in tr.get("coins", [])[:15]:
        i = c["item"]; d = i.get("data", {})
        tcoins.append({"id": i["id"], "symbol": i["symbol"], "name": i["name"], "rank": i.get("market_cap_rank"),
                       "chg24": (d.get("price_change_percentage_24h") or {}).get("usd"), "mcap": d.get("market_cap"),
                       "vol": d.get("total_volume")})
    out["cg_trending"] = tcoins
    L.append("\n## COINGECKO TRENDING SEARCHES")
    L += [f"- {c['symbol']} ({c['name']}) rank #{c['rank']} {pct(c['chg24'])} 24h, mcap {c['mcap']}" for c in tcoins]
    tcat = [(c["name"], (c.get("data", {}).get("market_cap_change_percentage_24h") or {}).get("usd")) for c in tr.get("categories", [])]
    if tcat: L.append("Trending categories: " + ", ".join(f"{n} ({pct(v)})" for n, v in tcat))
    out["cg_trending_categories"] = tcat

    # ---- sector rotation (categories with real size)
    cats = cg("coins/categories") or []
    if isinstance(cats, dict): cats = []
    big = [c for c in cats if (c.get("market_cap") or 0) >= 1e9 and c.get("market_cap_change_24h") is not None
           and not re.search(r"(stablecoin|bridged|wrapped|portfolio|ecosystem|binance|coinbase|launchpad|alleged|etf|made in|tokenized)", c["name"], re.I)]
    bc = sorted(big, key=lambda c: -c["market_cap_change_24h"])
    out["sectors_top"] = [(c["name"], c["market_cap_change_24h"], c["market_cap"]) for c in bc[:8]]
    out["sectors_bottom"] = [(c["name"], c["market_cap_change_24h"], c["market_cap"]) for c in bc[-5:]]
    L.append("\n## SECTORS (>$1B mcap) 24h")
    L.append("Leading: " + "; ".join(f"{n} {pct(v)}" for n, v, _ in out["sectors_top"]))
    L.append("Lagging: " + "; ".join(f"{n} {pct(v)}" for n, v, _ in out["sectors_bottom"]))

    # ---- DefiLlama chain TVL (current snapshot; day-over-day computed from previous raw file)
    chains = get("https://api.llama.fi/v2/chains") or []
    if isinstance(chains, dict): chains = []
    tvl = {c["name"]: c.get("tvl") or 0 for c in chains}
    out["chain_tvl"] = dict(sorted(tvl.items(), key=lambda kv: -kv[1])[:40])
    prev = None
    for f in sorted(os.listdir(RAW), reverse=True):
        if f.endswith(".json") and not f.startswith(datetime.now().strftime("%Y-%m-%d")):
            try: prev = json.load(open(f"{RAW}/{f}")); break
            except Exception: pass
    L.append("\n## CHAIN TVL (DefiLlama)")
    rows = []
    for n, v in list(out["chain_tvl"].items())[:12]:
        pv = (prev or {}).get("chain_tvl", {}).get(n)
        rows.append(f"{n} {usd(v)}" + (f" ({pct((v / pv - 1) * 100)} vs prev)" if pv else ""))
    L.append(" | ".join(rows))

    # ---- Lighter perps: movers + funding extremes
    LB = "https://mainnet.zklighter.elliot.ai/api/v1"
    ob = get(f"{LB}/orderBookDetails").get("order_book_details", [])
    fr = get(f"{LB}/funding-rates").get("funding_rates", [])
    fmap = collections.defaultdict(dict)
    for x in fr: fmap[x["symbol"]][x["exchange"]] = x["rate"]
    perps = [o for o in ob if o.get("market_type") == "perp" and float(o.get("daily_quote_token_volume") or 0) > 2e6]
    lm = sorted(perps, key=lambda o: -abs(float(o.get("daily_price_change") or 0)))[:8]
    out["lighter_movers"] = [(o["symbol"], float(o["daily_price_change"]), float(o["daily_quote_token_volume"])) for o in lm]
    fx = [(o["symbol"], fmap[o["symbol"]].get("lighter"), fmap[o["symbol"]].get("binance")) for o in perps if fmap[o["symbol"]].get("lighter") is not None]
    fx.sort(key=lambda t: -abs(t[1] or 0))
    out["lighter_funding_extremes"] = fx[:8]
    L.append("\n## LIGHTER PERPS (vol > $2M)")
    L.append("Biggest 24h moves: " + "; ".join(f"{s} {pct(c)} (vol {usd(v)})" for s, c, v in out["lighter_movers"]))
    L.append("Funding extremes (hourly-ish rate; + = longs pay): " +
             "; ".join(f"{s} L {l*100:+.4f}% / Bin {(b or 0)*100:+.4f}%" for s, l, b in out["lighter_funding_extremes"]))

    # ---- cycle leaders: longer-horizon performance (top 250 by mcap) for spot ideas
    lt = cg("coins/markets?vs_currency=usd&order=market_cap_desc&per_page=250&page=1&price_change_percentage=30d,200d,1y") or []
    if isinstance(lt, dict): lt = []
    lt = [c for c in lt if c["symbol"].lower() not in STABLES]
    def lead(key, n=10):
        xs = [c for c in lt if c.get(key) is not None]
        return sorted(xs, key=lambda c: -c[key])[:n]
    out["leaders_30d"] = [(c["symbol"].upper(), c["name"], c.get("price_change_percentage_30d_in_currency"), c.get("market_cap"), c.get("ath_change_percentage")) for c in lead("price_change_percentage_30d_in_currency")]
    out["leaders_200d"] = [(c["symbol"].upper(), c["name"], c.get("price_change_percentage_200d_in_currency"), c.get("market_cap"), c.get("ath_change_percentage")) for c in lead("price_change_percentage_200d_in_currency")]
    ref = {c["symbol"].upper(): c for c in lt if c["symbol"].lower() in ("hype", "lit", "zec", "near")}
    L.append("\n## CYCLE LEADERS (top-250 mcap, ex-stables)")
    L.append("Reference winners: " + " | ".join(f"{s} 30d {pct(c.get('price_change_percentage_30d_in_currency'))}, 200d {pct(c.get('price_change_percentage_200d_in_currency'))}, {pct(c.get('ath_change_percentage'))} from ATH" for s, c in ref.items()))
    L.append("Best 30d: " + "; ".join(f"{s} ({n}) {pct(p)} mcap {usd(m)} ATH {pct(a)}" for s, n, p, m, a in out["leaders_30d"]))
    L.append("Best 200d: " + "; ".join(f"{s} {pct(p)} ATH {pct(a)}" for s, n, p, m, a in out["leaders_200d"]))

    # ---- DefiLlama protocol revenue momentum (real usage signal)
    fees = get("https://api.llama.fi/overview/fees?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true&dataType=dailyRevenue") or {}
    prot = [p for p in fees.get("protocols", []) if (p.get("total30d") or 0) >= 1e6 and p.get("total60dto30d")
            and p.get("category") not in ("Stablecoin Issuer", "Chain")]
    for p in prot: p["_mom"] = (p["total30d"] / p["total60dto30d"] - 1) * 100
    rising = sorted([p for p in prot if p["_mom"] > 20], key=lambda p: -p["total30d"])[:12]
    biggest = sorted(prot, key=lambda p: -p["total30d"])[:10]
    out["revenue_rising"] = [(p["name"], p.get("category"), p["total30d"], p["_mom"]) for p in rising]
    out["revenue_top"] = [(p["name"], p.get("category"), p["total30d"], p["_mom"]) for p in biggest]
    L.append("\n## PROTOCOL REVENUE (DefiLlama, 30d vs prior 30d)")
    L.append("Top earners: " + "; ".join(f"{n} [{c}] {usd(t)} ({pct(m)})" for n, c, t, m in out["revenue_top"]))
    L.append("Rising >20% m/m (>= $1M/30d): " + "; ".join(f"{n} [{c}] {usd(t)} ({pct(m)})" for n, c, t, m in out["revenue_rising"]))

    # ---- X / CT chatter
    L.append("\n## X / CRYPTO TWITTER")
    broad = xsearch("(crypto OR altcoin OR altcoins OR memecoin OR defi) has:cashtags -is:retweet -is:reply lang:en", X_BROAD)
    tweets = broad.get("data", [])
    cnt, eng = collections.Counter(), collections.Counter()
    for t in tweets:
        m = t.get("public_metrics", {}); w = 1 + m.get("like_count", 0) + 2 * m.get("retweet_count", 0)
        for c in {c["tag"].upper() for c in t.get("entities", {}).get("cashtags", [])}:
            cnt[c] += 1; eng[c] += w
    top_tags = [t for t, _ in cnt.most_common(12) if t not in ("BTC", "ETH", "USDT", "USDC")]
    out["x_cashtags"] = cnt.most_common(20)
    L.append(f"Sampled {len(tweets)} relevancy-ranked posts. Most-mentioned cashtags: " +
             ", ".join(f"${t} x{n}" for t, n in cnt.most_common(15)))
    best = sorted(tweets, key=lambda t: -(t["public_metrics"]["like_count"] + 2 * t["public_metrics"]["retweet_count"]))[:6]
    L.append("Highest-engagement posts:")
    L += [f"- [{t['public_metrics']['like_count']}♥ {t['public_metrics']['retweet_count']}rt] " + t["text"].replace("\n", " ")[:220] for t in best]
    out["x_top_posts"] = [{"id": t["id"], "text": t["text"], "m": t["public_metrics"]} for t in best]
    out["x_ticker_samples"] = {}
    for tag in top_tags[:X_TICKERS]:
        r = xsearch(f"${tag} -is:retweet lang:en", X_PER_TICKER)
        ts = r.get("data", [])
        out["x_ticker_samples"][tag] = [t["text"] for t in ts]
        L.append(f"\n${tag} sample ({len(ts)} posts):")
        L += ["- " + t["text"].replace("\n", " ")[:200] for t in ts]
    if "error" in broad or "errors" in broad or "detail" in broad:
        L.append(f"(X search issue: {json.dumps(broad)[:200]})")

    # ---- what larger traders/data accounts are saying (2026-10-23). Context for our own read, NOT signals:
    # never copy a trade from these, and treat newsletter/stream promos as noise.
    TRADERS = ["52kskew", "CryptoCred", "DonAlt", "HsakaTrades", "Tradermayne", "rektcapital",
               "coinglass_com", "laevitas1", "glassnode", "ki_young_ju"]
    tq = "(" + " OR ".join(f"from:{u}" for u in TRADERS) + ") -is:retweet -is:reply"
    tr = xsearch(tq, 100)
    tusers = {u["id"]: u["username"] for u in tr.get("includes", {}).get("users", [])}
    promo = re.compile(r"newsletter|sign up|going live|livestream|stream|giveaway|download it free|premium|discount|"
                       r"subscribe|watchlist like this|blueprint", re.I)
    mkt = re.compile(r"\$[A-Z]{2,10}\b|#BTC|bitcoin|\bBTC\b|\bETH\b|funding|open interest|\bOI\b|liquidat|support|"
                     r"resistance|range|breakout|breakdown|retest|close above|close below|ETF|inflow|outflow|leverage|"
                     r"long|short|bid|ask|whale|cost basis|perp|altcoin", re.I)
    tposts = [t for t in tr.get("data", []) if not promo.search(t["text"]) and mkt.search(t["text"])
              and len(t["text"]) > 60]
    tposts.sort(key=lambda t: t["created_at"], reverse=True)          # newest first: what they think NOW
    L.append(f"\n## WHAT LARGER TRADERS / DATA ACCOUNTS ARE SAYING (last 7d, {len(tposts)} market posts, newest first; "
             f"context only, never copy trades)")
    L += [f"- @{tusers.get(t['author_id'], '?')} [{t['public_metrics']['like_count']}♥ {t['created_at'][5:10]}]: "
          + t["text"].replace("\n", " ")[:260] for t in tposts[:25]]
    out["x_traders"] = [{"user": tusers.get(t["author_id"]), "text": t["text"], "m": t["public_metrics"],
                         "at": t["created_at"]} for t in tposts[:40]]

    # ---- score previous watchlist signals
    try: sig = json.load(open(SIGNALS))
    except Exception: sig = []
    if sig:
        ids = ",".join(sorted({s["coingecko_id"] for s in sig if s.get("coingecko_id")}))
        px = cg(f"simple/price?ids={urllib.parse.quote(ids)}&vs_currencies=usd") if ids else {}
        L.append("\n## PAST WATCHLIST SIGNALS (scorecard) -- IDEAS ONLY, NEVER TRADED: these are paper calls from past digests, not positions. Real positions are only in the Lighter account section.")
        scored = []
        for s in sig[-30:]:
            now = (px.get(s.get("coingecko_id"), {}) or {}).get("usd")
            if now and s.get("price"):
                r = (now / s["price"] - 1) * 100 * (1 if s.get("direction", "long") == "long" else -1)
                scored.append(r)
                L.append(f"- {s['date']} {s['direction'].upper()} {s['symbol']} @ {s['price']:.6g} -> {now:.6g}: {r:+.1f}% "
                         f"| thesis: {s.get('thesis', '')[:90]}")
        if scored:
            L.append(f"Hit rate: {sum(1 for r in scored if r > 0)}/{len(scored)} | avg {sum(scored)/len(scored):+.1f}%")
        out["signals_scored"] = len(scored)

    stamp = datetime.now().strftime("%Y-%m-%d")
    json.dump(out, open(f"{RAW}/{stamp}.json", "w"), indent=1, default=str)
    L.append(f"\n(raw data saved: {RAW}/{stamp}.json)")
    print("\n".join(L))

if __name__ == "__main__":
    main()
