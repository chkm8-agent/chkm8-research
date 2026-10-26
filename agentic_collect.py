#!/usr/bin/env python3
"""Weekly 'Agentic AI' data for the Monday market digest (stdlib only).

Prints a compact brief: new releases (last 8 days) + star deltas for the agent-protocol/framework repos we
track, recent multi-agent papers from arXiv, and the CoinGecko 'AI agents' token sector. Raw JSON goes to
wiki/raw/agentic/YYYY-MM-DD.json; star deltas are computed against the previous raw file.
"""
import json, os, re, sys, time, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAW = Path.home() / "chkm8/wiki/raw/agentic"
REPOS = {  # repo -> why we track it
    "a2aproject/A2A": "A2A protocol (agent-to-agent)",
    "modelcontextprotocol/modelcontextprotocol": "MCP spec",
    "x402-foundation/x402": "x402 payments",
    "google-agentic-commerce/AP2": "AP2 payment mandates",
    "google-agentic-commerce/a2a-x402": "A2A x402 extension",
    "erc-8004/erc-8004-contracts": "ERC-8004 agent identity/reputation",
    "kagent-dev/kagent": "kagent (agents on k8s)",
    "kyegomez/swarms": "Swarms framework",
    "TauricResearch/TradingAgents": "multi-agent trading framework",
    "letta-ai/letta": "Letta (stateful/shared memory)",
    "NousResearch/hermes-agent": "Hermes (our harness)",
    "langchain-ai/langgraph": "LangGraph",
    "crewAIInc/crewAI": "CrewAI",
}
UA = {"User-Agent": "chkm8-digest/1.0", "Accept": "application/vnd.github+json"}

def get(url, raw=False, tries=3):
    for i in range(tries):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40).read()
            return r if raw else json.loads(r)
        except Exception as e:
            if i == tries - 1:
                print(f"  ! fetch failed {url.split('?')[0]}: {e}", file=sys.stderr); return None
            time.sleep(3 * (i + 1))

def short(s, n=160):
    s = re.sub(r"<!--.*?-->", " ", s or "", flags=re.S)
    s = re.sub(r"\s+", " ", re.sub(r"[#*`>\[\]]|\(https?://[^)]*\)", "", s or "")).strip()
    return s[:n] + ("…" if len(s) > n else "")

def main():
    now = datetime.now(timezone.utc); since = now - timedelta(days=8)
    RAW.mkdir(parents=True, exist_ok=True)
    prev_files = sorted(p for p in RAW.glob("*.json") if p.stem < now.astimezone().strftime("%Y-%m-%d"))
    prev = json.loads(prev_files[-1].read_text()) if prev_files else {}
    out = {"date": now.astimezone().strftime("%Y-%m-%d"), "repos": {}, "papers": [], "sector": None}

    print("=== AGENTIC AI (weekly) — write a '## Agentic AI' section from this")
    print("--- Repo releases (last 8d) and stars (Δ vs previous run)")
    for repo, why in REPOS.items():
        meta = get(f"https://api.github.com/repos/{repo}") or {}
        rels = get(f"https://api.github.com/repos/{repo}/releases?per_page=5") or []
        new = [dict(tag=r["tag_name"], name=r.get("name") or r["tag_name"], date=r["published_at"][:10],
                    url=r["html_url"], notes=short(r.get("body"))) for r in rels
               if r.get("published_at") and datetime.fromisoformat(r["published_at"].replace("Z", "+00:00")) >= since]
        stars = meta.get("stargazers_count")
        pstars = prev.get("repos", {}).get(repo, {}).get("stars")
        d = f"{stars - pstars:+,}" if stars is not None and pstars is not None else "n/a (first week)"
        out["repos"][repo] = dict(why=why, stars=stars, pushed=meta.get("pushed_at"), releases=new)
        print(f"{repo} [{why}] stars={stars if stars is not None else '?'} Δ={d} last_push={(meta.get('pushed_at') or '?')[:10]}")
        for r in new:
            print(f"   RELEASE {r['tag']} {r['date']} {r['url']} :: {r['notes']}")
        time.sleep(0.5)

    print("--- arXiv: multi-agent LLM papers (newest)")
    q = 'abs:"multi-agent" AND (abs:LLM OR abs:"language model") AND (cat:cs.MA OR cat:cs.AI OR cat:cs.CL OR cat:q-fin.TR)'
    xml = get("http://export.arxiv.org/api/query?" + urllib.parse.urlencode(
        dict(search_query=q, sortBy="submittedDate", sortOrder="descending", max_results=25)), raw=True)
    if xml:
        ns = {"a": "http://www.w3.org/2005/Atom"}
        for e in ET.fromstring(xml).findall("a:entry", ns):
            pub = e.findtext("a:published", "", ns)[:10]
            if pub < since.strftime("%Y-%m-%d"): continue
            p = dict(title=short(e.findtext("a:title", "", ns), 140), date=pub,
                     url=e.findtext("a:id", "", ns), abstract=short(e.findtext("a:summary", "", ns), 220))
            out["papers"].append(p)
        fin = [p for p in out["papers"] if re.search(r"trad|financ|market|crypto|portfolio", p["title"] + p["abstract"], re.I)]
        for p in (fin + [p for p in out["papers"] if p not in fin])[:10]:
            print(f"   {p['date']} {p['title']} {p['url']} :: {p['abstract']}")
        print(f"   ({len(out['papers'])} papers in window; finance/trading-related: {len(fin)})")

    print("--- CoinGecko 'AI agents' sector")
    cats = get("https://api.coingecko.com/api/v3/coins/categories") or []
    for c in cats:
        if c.get("id") in ("ai-agents", "ai-agent-launchpad", "ai-framework"):
            out.setdefault("sectors", []).append(c)
            print(f"   {c['name']}: mcap ${c.get('market_cap') or 0:,.0f} 24h {c.get('market_cap_change_24h') or 0:+.1f}% vol ${c.get('volume_24h') or 0:,.0f}")
    time.sleep(2)
    top = get("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&category=ai-agents&order=market_cap_desc"
              "&per_page=10&price_change_percentage=7d")
    if top:
        out["sector"] = [dict(sym=t["symbol"].upper(), id=t["id"], price=t["current_price"], mcap=t["market_cap"],
                              ch7d=t.get("price_change_percentage_7d_in_currency")) for t in top]
        print("   top10: " + ", ".join(f"{t['sym']} {t['ch7d'] or 0:+.0f}%7d" for t in out["sector"]))

    (RAW / f"{out['date']}.json").write_text(json.dumps(out, indent=1))
    print(f"(raw saved wiki/raw/agentic/{out['date']}.json)")

if __name__ == "__main__":
    main()
