#!/usr/bin/env python3
"""Send a markdown digest as a newsletter-style email.
The markdown is laid out as a newsletter (masthead, brief, numbered sections, stat tiles, cards),
rendered to PNG with headless Brave and attached; the plain markdown goes in the body as a fallback.

Two editions share this renderer:
  digest_send.py wiki/digests/2026-10-01.md            # The chkm8 Digest (market)
  digest_send.py wiki/chains/2026-10-05.md --kind chains   # Five Chains (BTC/ETH/NEAR/ZEC/XMR)
Options: --dry (render only)  --theme NAME (preview a specific theme)

DESIGN ROTATION: the visual theme changes every Monday (ISO week), cycling through THEMES so the
operator can eventually pick a favourite. The theme name is printed in the footer + subject-free.
To lock a theme permanently, set LOCKED_THEME below."""
import html, os, re, subprocess, sys
from datetime import datetime, date as _date
import markdown

HOME = os.path.expanduser("~/chkm8")
TO = ["<redacted:agent-email>", "<redacted:owner-email>"]
FROM = "<redacted:agent-email>"
BRAVE = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
W = 720
LOCKED_THEME = "Solarized"     # operator 2026-10-23: no more rotation. An edition's own theme= wins (market: Swiss, 2026-10-26)
ROTATION_START = _date(2026, 10, 5)   # Monday; week 0 of the rotation

SERIF = "'Iowan Old Style','Palatino',Georgia,serif"
SANS = "-apple-system,'SF Pro Text',Helvetica,Arial,sans-serif"
MONO = "'JetBrains Mono','SF Mono',Menlo,monospace"
GROTESK = "'Helvetica Neue',Helvetica,Arial,sans-serif"

# Each theme: palette + fonts + masthead flavour. bg must be a solid colour (used for the render check).
THEMES = [
    dict(name="Broadsheet", bg=(246, 243, 236), fg="#1f2328", muted="#6e6a60", accent="#a0522d", card="#fffdf8",
         line="#e3ddcf", th="#efe9dc", brief_bg="#1f2328", brief_fg="#f6f3ec", brief_lbl="#d9b45a",
         pos="#1a7f37", neg="#cf222e", bpos="#56d364", bneg="#ff7b72", head=SERIF, body=SANS, radius=10,
         rule="3px double", h1=46, kick_case="uppercase"),
    dict(name="Terminal", bg=(10, 14, 10), fg="#c8f7c5", muted="#5f8f5c", accent="#39ff14", card="#0f1a0f",
         line="#1f3a1f", th="#0c160c", brief_bg="#132413", brief_fg="#c8f7c5", brief_lbl="#39ff14",
         pos="#39ff14", neg="#ff5555", bpos="#39ff14", bneg="#ff5555", head=MONO, body=MONO, radius=0, tile_v=17,
         rule="1px dashed", h1=40, kick_case="none"),
    dict(name="Bloomberg", bg=(0, 0, 0), fg="#f2f2f2", muted="#9a9a9a", accent="#ff9f1c", card="#111111",
         line="#2b2b2b", th="#1a1a1a", brief_bg="#ff9f1c", brief_fg="#000000", brief_lbl="#000000",
         pos="#2ee66b", neg="#ff4d4d", bpos="#003b12", bneg="#5c0000", head=GROTESK, body=GROTESK, radius=2,
         rule="2px solid", h1=44, kick_case="uppercase"),
    dict(name="Vaporwave", bg=(28, 12, 48), fg="#f5e9ff", muted="#b48ce0", accent="#ff4fd8", card="#2b1650",
         line="#4b2a80", th="#351c62", brief_bg="#00e5ff", brief_fg="#1c0c30", brief_lbl="#ff4fd8",
         pos="#5cffb0", neg="#ff6b9d", bpos="#00513a", bneg="#8a0040", head=GROTESK, body=SANS, radius=16,
         rule="2px solid", h1=48, kick_case="uppercase"),
    dict(name="Swiss", bg=(255, 255, 255), fg="#111111", muted="#777777", accent="#e30613", card="#ffffff",
         line="#111111", th="#f2f2f2", brief_bg="#e30613", brief_fg="#ffffff", brief_lbl="#ffffff",
         pos="#0a7d2c", neg="#e30613", bpos="#ffffff", bneg="#111111", head=GROTESK, body=GROTESK, radius=0,
         rule="4px solid", h1=56, kick_case="uppercase"),
    dict(name="Zine", bg=(255, 228, 77), fg="#111111", muted="#4a3f00", accent="#ff3d00", card="#fff7c2",
         line="#111111", th="#ffe066", brief_bg="#111111", brief_fg="#fff7c2", brief_lbl="#ffe44d",
         pos="#006b2b", neg="#c4001a", bpos="#7dff9e", bneg="#ff8a8a", head="'Impact','Haettenschweiler',sans-serif",
         body=SANS, radius=4, rule="3px solid", h1=58, kick_case="uppercase"),
    # ---- 10 more options (2026-10-23), not in use until picked
    dict(name="Nord", bg=(46, 52, 64), fg="#eceff4", muted="#9aa5b8", accent="#88c0d0", card="#3b4252",
         line="#4c566a", th="#434c5e", brief_bg="#88c0d0", brief_fg="#2e3440", brief_lbl="#2e3440",
         pos="#a3be8c", neg="#bf616a", bpos="#2e5d1f", bneg="#7a1f27", head=GROTESK, body=SANS, radius=8,
         rule="2px solid", h1=46, kick_case="uppercase"),
    dict(name="FT", bg=(255, 241, 229), fg="#33302e", muted="#807973", accent="#0d7680", card="#fff9f5",
         line="#e6d9ce", th="#f2dfce", brief_bg="#33302e", brief_fg="#fff1e5", brief_lbl="#f2a68c",
         pos="#09a25a", neg="#cc0000", bpos="#7fe0a8", bneg="#ff9a9a", head=SERIF, body=SERIF, radius=0,
         rule="1px solid", h1=48, kick_case="uppercase"),
    dict(name="Solarized", bg=(0, 43, 54), fg="#eee8d5", muted="#839496", accent="#b58900", card="#073642",
         line="#0f4c5c", th="#083e4b", brief_bg="#b58900", brief_fg="#002b36", brief_lbl="#002b36",
         pos="#859900", neg="#dc322f", bpos="#2f3a00", bneg="#5c0f0d", head=MONO, body=SANS, radius=4,
         rule="2px solid", h1=42, kick_case="none"),
    dict(name="Blueprint", bg=(16, 52, 110), fg="#e8f1ff", muted="#9cb8e0", accent="#ffffff", card="#163f80",
         line="#3d67a8", th="#1a4a92", brief_bg="#e8f1ff", brief_fg="#10346e", brief_lbl="#10346e",
         pos="#8cf2b0", neg="#ff9a8a", bpos="#0a5a2a", bneg="#8a1a10", head=MONO, body=MONO, radius=0,
         rule="1px dashed", h1=40, kick_case="uppercase"),
    dict(name="Gruvbox", bg=(40, 40, 40), fg="#ebdbb2", muted="#a89984", accent="#fe8019", card="#32302f",
         line="#504945", th="#3c3836", brief_bg="#fabd2f", brief_fg="#282828", brief_lbl="#282828",
         pos="#b8bb26", neg="#fb4934", bpos="#3a3c00", bneg="#6a120a", head=MONO, body=SANS, radius=6,
         rule="2px solid", h1=44, kick_case="none"),
    dict(name="Dracula", bg=(40, 42, 54), fg="#f8f8f2", muted="#a0a4c4", accent="#bd93f9", card="#343746",
         line="#44475a", th="#3a3d4e", brief_bg="#bd93f9", brief_fg="#282a36", brief_lbl="#282a36",
         pos="#50fa7b", neg="#ff5555", bpos="#0f5a24", bneg="#7a1010", head=GROTESK, body=SANS, radius=12,
         rule="2px solid", h1=46, kick_case="uppercase"),
    dict(name="Ledger", bg=(244, 240, 225), fg="#2a2a2a", muted="#7a7262", accent="#1f5c3a", card="#fbf9f0",
         line="#c9c1a8", th="#e9e2c9", brief_bg="#1f5c3a", brief_fg="#f4f0e1", brief_lbl="#d9e8c4",
         pos="#1f5c3a", neg="#a3261b", bpos="#bff0c9", bneg="#ffb3a8", head=SERIF, body=MONO, radius=0,
         rule="3px double", h1=44, kick_case="uppercase"),
    dict(name="Neon", bg=(10, 10, 10), fg="#f5f5f5", muted="#8c8c8c", accent="#f5e100", card="#151515",
         line="#2e2e2e", th="#1c1c1c", brief_bg="#f5e100", brief_fg="#0a0a0a", brief_lbl="#0a0a0a",
         pos="#00ffa3", neg="#ff2e63", bpos="#004d31", bneg="#6b0020", head=GROTESK, body=GROTESK, radius=0,
         rule="3px solid", h1=58, kick_case="uppercase"),
    dict(name="Minimal", bg=(250, 250, 250), fg="#18181b", muted="#71717a", accent="#2563eb", card="#ffffff",
         line="#e4e4e7", th="#f4f4f5", brief_bg="#18181b", brief_fg="#fafafa", brief_lbl="#93c5fd",
         pos="#16a34a", neg="#dc2626", bpos="#86efac", bneg="#fca5a5", head=SANS, body=SANS, radius=14,
         rule="1px solid", h1=44, kick_case="none"),
    dict(name="Sakura", bg=(255, 244, 246), fg="#3a2a30", muted="#9a7d86", accent="#d6336c", card="#ffffff",
         line="#f3d3dc", th="#fde6ec", brief_bg="#3a2a30", brief_fg="#fff4f6", brief_lbl="#ffb3c8",
         pos="#2f9e44", neg="#d6336c", bpos="#b2f2bb", bneg="#ffc9d9", head=SERIF, body=SANS, radius=18,
         rule="2px solid", h1=48, kick_case="none"),
]

PREVIEW = False

def pick_theme(name=None):
    if name or LOCKED_THEME:
        want = (name or LOCKED_THEME).lower()
        for t in THEMES:
            if t["name"].lower() == want: return t
        raise SystemExit(f"unknown theme {name}; options: {[t['name'] for t in THEMES]}")
    weeks = (_date.today() - ROTATION_START).days // 7          # flips every Monday
    return THEMES[(1 + weeks) % len(THEMES)]                     # week 0 = Terminal (Broadsheet ran first)

EDITIONS = {
    "market": dict(title="The chkm8 Digest", theme="Swiss", kick="Morning edition · crypto · perps · vibes",
                   tag="dispatches from an AI with a hot wallet and opinions", emoji="☕", brief="The brief",
                   sections=[("market", "📊", "The Market"), ("radar", "🔭", "Spot Radar"), ("spot", "🔭", "Spot Radar"),
                             ("mover", "🚀", "Movers & Shakers"), ("trend", "🔥", "Narratives & CT Pulse"),
                             ("narrative", "🔥", "Narratives & CT Pulse"), ("perp", "⚖️", "Perps Positioning"),
                             ("book", "📒", "Our Book"), ("agentic", "🤖", "Agentic AI"), ("watch", "👀", "Watchlist"), ("score", "🎯", "Scorecard")]),
    "chains": dict(title="Five Chains", kick="BTC · ETH · NEAR · ZEC · XMR · daily",
                   tag="the chains we actually care about, block by block", emoji="⛓️", brief="Chain brief",
                   sections=[("scoreboard", "🏁", "Scoreboard"), ("bitcoin", "🟠", "Bitcoin"), ("ethereum", "🔷", "Ethereum"),
                             ("near", "🟢", "NEAR"), ("zcash", "🛡️", "Zcash"), ("monero", "🕶️", "Monero"),
                             ("privacy", "🕶️", "Privacy Wars"), ("ecosystem", "🌱", "Ecosystem Radar"),
                             ("cross", "🔀", "Cross-Chain"), ("watch", "👀", "What to Watch"), ("radar", "🔭", "Ecosystem Radar")]),
}
# Extra editions that are not public (own recipients, titles, sections) live in a local module that
# defines register(EDITIONS). Path: $CHKM8_DIGEST_EDITIONS, else ~/.config/chkm8-digest/editions.py.
_EXTRA = os.path.expanduser(os.environ.get("CHKM8_DIGEST_EDITIONS", "~/.config/chkm8-digest/editions.py"))
if os.path.exists(_EXTRA):
    import importlib.util
    _spec = importlib.util.spec_from_file_location("chkm8_digest_editions", _EXTRA)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    _mod.register(EDITIONS)

def css(t):
    bg = "rgb" + str(t["bg"]); r = t["radius"]
    return f"""
*{{box-sizing:border-box}}
body{{margin:0;background:{bg};color:{t['fg']};font-family:{t['body']};font-size:15px;line-height:1.55}}
.page{{width:{W}px;padding:34px 40px 30px;overflow-wrap:anywhere}}
.mast{{text-align:center;border-bottom:{t['rule']} {t['fg']};padding-bottom:14px}}
.mast .kick{{font-size:11px;letter-spacing:.28em;text-transform:{t['kick_case']};color:{t['muted']}}}
.mast h1{{font-family:{t['head']};font-size:{t['h1']}px;line-height:1.05;margin:8px 0 6px;letter-spacing:-.01em;color:{t['fg']}}}
.mast .tag{{font-family:{t['head']};font-style:italic;color:{t['muted']};font-size:15px}}
.meta{{display:flex;justify-content:space-between;font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:{t['muted']};
      border-bottom:1px solid {t['fg']};padding:7px 2px;margin-bottom:22px}}
.brief{{background:{t['brief_bg']};color:{t['brief_fg']};border-radius:{r + 2}px;padding:20px 24px 16px;margin-bottom:10px}}
.brief .lbl{{font-size:11px;letter-spacing:.24em;text-transform:uppercase;color:{t['brief_lbl']};margin-bottom:10px;font-weight:700}}
.brief ol{{margin:0;padding-left:22px}} .brief li{{margin:0 0 9px}} .brief strong{{color:{t['brief_fg']}}}
.brief .pos{{color:{t['bpos']}}} .brief .neg{{color:{t['bneg']}}}
.note{{font-family:{t['head']};font-style:italic;color:{t['muted']};text-align:center;margin:12px 0 4px;font-size:14px}}
section{{margin-top:26px}}
.sh{{display:flex;align-items:baseline;gap:10px;border-top:1px solid {t['fg']};padding-top:10px;margin-bottom:10px}}
.sh .num{{font-family:{t['head']};font-size:13px;color:{t['accent']};font-weight:700}}
.sh h2{{font-family:{t['head']};font-size:24px;margin:0;letter-spacing:-.005em;color:{t['fg']}}}
.sh .ico{{margin-left:auto;font-size:20px}}
p{{margin:8px 0}} ul,ol{{margin:8px 0;padding-left:22px}} li{{margin:5px 0}}
strong{{color:{t['fg']}}} em{{color:inherit;font-style:italic}} a{{color:{t['accent']}}}
table{{width:100%;border-collapse:collapse;font-size:13.5px;margin:10px 0;background:{t['card']};border:1px solid {t['line']}}}
th{{text-align:left;font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;color:{t['muted']};font-weight:600;padding:9px 11px;background:{t['th']};border-bottom:1px solid {t['line']}}}
td{{padding:9px 11px;border-bottom:1px solid {t['line']};vertical-align:top;font-variant-numeric:tabular-nums}}
tr:last-child td{{border-bottom:none}} td:first-child{{font-weight:600;white-space:nowrap}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(112px,1fr));gap:10px;margin:6px 0 12px}}
.tile{{background:{t['card']};border:1px solid {t['line']};border-radius:{r}px;padding:11px 13px}}
.tile .l{{font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;color:{t['muted']}}}
.tile .v{{font-family:{t['head']};font-size:{t.get('tile_v',22)}px;white-space:nowrap;font-weight:700;margin:2px 0}}
.tile .c{{font-size:12.5px}} .tile .dim{{color:{t['muted']}}}
section.watch ol,section.radar ol,section.ecosystem ol,section.recommend ol{{list-style:none;padding:0}}
section.watch ol li,section.radar ol li,section.ecosystem ol li,section.recommend ol li{{background:{t['card']};border:1px solid {t['line']};border-left:4px solid {t['accent']};border-radius:{r}px;padding:12px 15px;margin:10px 0}}
section.book ul{{list-style:none;padding:0}}
section.book li{{background:{t['card']};border:1px solid {t['line']};border-radius:{r}px;padding:10px 14px;margin:8px 0}}
blockquote{{margin:10px 0;padding:10px 16px;border-left:3px solid {t['accent']};background:{t['card']};border-radius:0 {r}px {r}px 0}}
.pos{{color:{t['pos']};font-weight:600;white-space:nowrap}} .neg{{color:{t['neg']};font-weight:600;white-space:nowrap}}
.sign{{font-family:{t['head']};font-style:italic;text-align:center;font-size:16px;margin:30px 0 6px}}
.foot{{text-align:center;color:{t['muted']};font-size:11px;letter-spacing:.06em;border-top:{t['rule']} {t['fg']};padding-top:12px;margin-top:10px}}
.spark{{display:inline-flex;align-items:flex-end;gap:2px;height:16px;vertical-align:middle;white-space:nowrap}}
.spark i{{display:inline-block;width:6px;background:{t['accent']};border-radius:1px;opacity:.85}}
th{{white-space:nowrap}}
.page table{{table-layout:auto}}
{"table{font-size:12.5px} td,th{padding:8px 8px} th{letter-spacing:.06em}" if 'Mono' in t['body'] else ''}
.theme{{margin-top:6px;font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;color:{t['accent']}}}
"""

SPARK = "▁▂▃▄▅▆▇█"

def sparkify(h):
    """Unicode block sparklines (▁▃▅█) render inconsistently (font fallback, wrapping), so turn any run of
    3+ block characters in a text node into fixed-size CSS bars."""
    def bars(m):
        s = m.group(0)
        out = "".join(f'<i style="height:{2 + SPARK.index(c) * 2}px"></i>' for c in s)
        return f'<span class="spark">{out}</span>'
    return re.sub(r"(?<=>)[^<]+", lambda m: re.sub(f"[{SPARK}]{{3,}}", bars, m.group(0)), h)

def colorize(h, invert=False):
    """Green/red signed numbers, only inside text nodes (never inside tags/attributes).
    invert=True editions: a + is the bad direction (red), a - the good one (green)."""
    up, dn = ("neg", "pos") if invert else ("pos", "neg")
    def sub(m):
        t = m.group(0)
        t = re.sub(r"(?<![\w#])(\+\$?\d[\d,.]*[KMBTk]?%?)", rf'<span class="{up}">\1</span>', t)
        t = re.sub(r"(?<![\w#\-/])((?:-|−)\$?\d[\d,.]*[KMBTk]?%)", rf'<span class="{dn}">\1</span>', t)
        t = re.sub(r"(?<![\w#\-/])((?:-|−)\$\d[\d,.]*[KMBTk]?)(?!%)", rf'<span class="{dn}">\1</span>', t)
        return t
    return re.sub(r"(?<=>)[^<]+", sub, h)

def md(s):
    s = re.sub(r"(?m)^(?!\s*([-*]|\d+\.)\s)(.+)\n(?=\s*([-*]|\d+\.)\s)", r"\2\n\n", s)   # blank line before lists
    return markdown.markdown(s, extensions=["tables", "sane_lists"])
def inline(s):
    h = md(s).strip()
    return h[3:-4] if h.startswith("<p>") and h.endswith("</p>") else h

def parse_table(lines):
    rows = [[c.strip() for c in l.strip().strip("|").split("|")] for l in lines if l.strip().startswith("|")]
    rows = [r for r in rows if not all(re.fullmatch(r":?-{2,}:?", c) for c in r if c)]
    return rows[0], rows[1:]

def tiles(rows):
    out = []
    for r in rows:
        r = r + [""] * (4 - len(r))
        lbl, val, d1, d7 = r[:4]
        c = inline(d1) + (f' <span class="dim">· 7d {inline(d7)}</span>' if d7 and d7.lower() != "n/a" else "")
        out.append(f'<div class="tile"><div class="l">{inline(lbl)}</div><div class="v">{inline(val)}</div><div class="c">{c}</div></div>')
    return '<div class="tiles">' + "".join(out) + "</div>"

def render(md_text, png, issue, date, ed, theme):
    E = EDITIONS[ed]
    md_text = re.sub(r"\A---\n.*?\n---\n", "", md_text, flags=re.S)                                    # frontmatter
    md_text = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", lambda m: m.group(2) or m.group(1), md_text)  # wikilinks
    words = len(re.findall(r"\w+", md_text))
    lines = [l for l in md_text.strip().splitlines() if not l.startswith("# ")]
    pre, secs, cur = [], [], None
    for l in lines:
        if l.startswith("## "):
            cur = [l[3:].strip(), []]; secs.append(cur)
        elif cur is None: pre.append(l)
        else: cur[1].append(l)
    bq = [re.sub(r"^>\s?", "", l) for l in pre if l.startswith(">")]
    items = [re.sub(r"^\s*([-*]|\d+\.)\s+", "", l) for l in bq if re.match(r"^\s*([-*]|\d+\.)\s+", l)]
    if not items and bq: items = [" ".join(x for x in bq if x.strip() and "tl;dr" not in x.lower())]
    brief = (f'<div class="brief"><div class="lbl">{E["emoji"]} {E["brief"]}</div><ol>' +
             "".join(f"<li>{inline(i)}</li>" for i in items) + "</ol></div>") if items else ""
    rest_pre = "\n".join(l for l in pre if not l.startswith(">")).strip()
    note = f'<div class="note">{inline(rest_pre.strip("*_ "))}</div>' if rest_pre else ""
    sign = ""
    if secs:
        sl = secs[-1][1]
        idx = max((i for i, l in enumerate(sl) if l.strip()), default=None)
        if idx is not None and re.fullmatch(r"[*_][^*_].*[*_]", sl[idx].strip()):
            sign = f'<div class="sign">{inline(sl[idx].strip().strip("*_"))}</div>'
            secs[-1][1] = sl[:idx]
    body = []
    for n, (title, sl) in enumerate(secs, 1):
        key = next(((k, ico, disp) for k, ico, disp in E["sections"] if k in title.lower()), None)
        cls, ico, disp = (key[0], key[1], key[2]) if key else ("x", "•", title)
        text = "\n".join(sl)
        inner = ""
        if cls in ("market", "scoreboard", "glance"):
            tl = [l for l in sl if l.strip().startswith("|")]
            if tl:
                _, rows = parse_table(tl)
                if 0 < len(rows) <= 6:
                    inner += tiles(rows)
                    text = "\n".join(l for l in sl if not l.strip().startswith("|"))
        inner += md(text)
        body.append(f'<section class="{cls}"><div class="sh"><span class="num">{n:02d}</span><h2>{html.escape(disp)}</h2>'
                    f'<span class="ico">{ico}</span></div>{inner}</section>')
    page = f"""<!doctype html><html><head><meta charset="utf-8"><style>{css(theme)}</style></head><body><div class="page">
<div class="mast"><div class="kick">{E['kick']}</div><h1>{E['title']}</h1>
<div class="tag">{E['tag']}</div></div>
<div class="meta"><span>Issue #{issue}</span><span>{date:%A, %B %-d, %Y}</span><span>{max(1, round(words / 220))} min read</span></div>
{brief}{note}{''.join(body)}{sign}
<div class="foot">{E.get('foot', "chkm8 🤖 · @Chkm8_agent · <redacted:wallet-short> · automated · not financial advice")}
{(f'<div class="theme">design preview: {theme["name"]}</div>' if PREVIEW else '') if E.get('theme') else f'<div class="theme">design: {theme["name"]}</div>'}</div>
</div></body></html>"""
    hp = png[:-4] + ".html"
    open(hp, "w").write(sparkify(colorize(page, invert=E.get("invert", False))))
    subprocess.run([BRAVE, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2",
                    f"--window-size={W},9000", f"--screenshot={png}", f"file://{hp}"], capture_output=True, timeout=120)
    from PIL import Image
    BG = theme["bg"]
    im = Image.open(png).convert("RGB"); w, h = im.size
    if im.getpixel((10, 10)) != BG:   # anything else = render failed (e.g. browser error page)
        raise SystemExit(f"render check failed for {png}: unexpected background {im.getpixel((10, 10))}")
    # Crop to the content (all four sides) + a small even margin, so the email shows the column, not a wide
    # slab of page background around it.
    from PIL import ImageChops
    bbox = ImageChops.difference(im, Image.new("RGB", im.size, BG)).getbbox()
    if bbox:
        pad = 20   # px at 2x = 10 CSS px
        l, t, r, b = bbox
        im = im.crop((max(0, l - pad), max(0, t - pad), min(w, r + pad), min(h, b + pad)))
    im.save(png, optimize=True)

def link_footer(links, body):
    """The digest itself is a PNG (links in it can't be clicked), so add a real clickable credit line under
    the image. mailer inserts the image right after the bare <body> tag."""
    a = " &amp; ".join(f'<a href="{u}" style="color:#a0522d;text-decoration:none;font-weight:600">{n}</a>'
                       for n, u in links)
    esc = body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return ('<html><body><div style="font-family:Georgia,serif;font-style:italic;color:#6e6a60;font-size:14px;'
            f'padding:14px 0 6px;max-width:660px;text-align:center">built by {a} 🤖</div>'
            '<pre style="font-family:-apple-system,Helvetica,Arial,sans-serif;white-space:pre-wrap;color:#57606a;'
            f'font-size:12px;padding:12px 0;margin:0;max-width:660px">{esc}</pre></body></html>')

def send(subject, body, png, to=None, links=None):
    sys.path.insert(0, HOME)
    import mailer
    os.makedirs(f"{HOME}/logs", exist_ok=True)
    log = lambda s: open(f"{HOME}/logs/digest.log", "a").write(f"{datetime.now().isoformat()} {s}\n")
    return mailer.send(to or TO, subject, body, png, log=log, html=link_footer(links, body) if links else None)

def arg(flag, default=None):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default

if __name__ == "__main__":
    md_path = os.path.abspath(os.path.expanduser(sys.argv[1]))
    ed = arg("--kind", "market")
    PREVIEW = "--theme" in sys.argv and bool(EDITIONS[ed].get("theme"))   # design-comparison sends
    theme = pick_theme(arg("--theme") or EDITIONS[ed].get("theme"))
    to = arg("--to").split(",") if arg("--to") else EDITIONS[ed].get("to")
    text = open(md_path).read()
    d, name = os.path.dirname(md_path), os.path.basename(md_path)
    issue = len([f for f in os.listdir(d) if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.md", f) and f <= name]) or 1
    m = re.match(r"(\d{4}-\d{2}-\d{2})", name)
    date = datetime.strptime(m.group(1), "%Y-%m-%d") if m else datetime.now()
    png = md_path[:-3] + (f".{theme['name'].lower()}.png" if arg("--theme") else ".png")
    render(text, png, issue, date, ed, theme)
    E = EDITIONS[ed]
    head = re.search(r"^>\s*(?:[-*]|\d+\.)\s+\*\*(.+?)\*\*", text, re.M)
    head_txt = head.group(1).rstrip(".") if head else date.strftime("%b %-d")
    subject = (f"{E['emoji']} " if E.get("subject_emoji", True) else "") + f"{E['title']} #{issue}: " + head_txt
    if E.get("subject_fmt"):              # an edition can define its own subject line
        subject = E["subject_fmt"].format(emoji=E["emoji"], title=E["title"], issue=issue, date=date, head=head_txt)
    if PREVIEW:
        subject += f" · design {arg('--preview-n', '?')}: {theme['name']}"
    if "--dry" in sys.argv:
        print(subject, "|", theme["name"], "|", png); sys.exit()
    res = send(subject, re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S), png, to, EDITIONS[ed].get("links"))
    os.makedirs(f"{HOME}/logs", exist_ok=True)
    with open(f"{HOME}/logs/digest.log", "a") as f: f.write(f"{datetime.now().isoformat()} {md_path} [{ed}/{theme['name']}] {res}\n")
    print(res)
