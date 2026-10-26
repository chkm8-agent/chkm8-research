"""Builds + sends the one-off 'Agent swarms' research brief email."""
import html, json, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).parent
S = Path.home() / ".hermes/skills/research/grounded-citations/scripts/sources.py"
ledger = {str(e["id"]): e for e in json.loads(subprocess.check_output([sys.executable, S, "list", "--json"]))}

ACC = "#7c5cff"; INK = "#1d1d27"; MUTED = "#6b6b80"; LINE = "#e6e4f0"; CARD = "#f7f6fc"

def cite(text):
    def rep(m):
        e = ledger[m.group(1)]
        return f'<a href="{e["url"]}" style="color:{ACC};text-decoration:none;font-size:11px;vertical-align:super">[{m.group(1)}]</a>'
    return re.sub(r"\[(\d+)\]", rep, text)

def p(t): return f'<p style="margin:0 0 10px;line-height:1.55">{cite(t)}</p>'
def ul(items): return '<ul style="margin:0 0 12px;padding-left:20px;line-height:1.55">' + "".join(f'<li style="margin-bottom:6px">{cite(i)}</li>' for i in items) + "</ul>"
def h(n, icon, t): return f'<h2 style="font-size:18px;margin:28px 0 10px;color:{INK}"><span style="color:{ACC}">{n:02d}</span> {icon} {t}</h2>'
def badge(t, c): return f'<span style="display:inline-block;background:{c};color:#fff;border-radius:10px;padding:1px 8px;font-size:11px;font-weight:600">{t}</span>'
def table(head, rows):
    th = "".join(f'<th style="text-align:left;padding:7px 9px;border-bottom:2px solid {ACC};font-size:12px;color:{MUTED}">{x}</th>' for x in head)
    tr = "".join("<tr>" + "".join(f'<td style="padding:7px 9px;border-bottom:1px solid {LINE};vertical-align:top;font-size:13px">{cite(c)}</td>' for c in r) + "</tr>" for r in rows)
    return f'<table cellspacing="0" style="border-collapse:collapse;margin:0 0 14px;max-width:820px">{th and "<tr>"+th+"</tr>"}{tr}</table>'
def link(t, u): return f'<a href="{u}" style="color:{ACC}">{html.escape(t)}</a>'

body = []
A = body.append
A(f'<div style="font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:{INK};max-width:820px;text-align:left">')
A(f'<div style="border-bottom:3px solid {ACC};padding-bottom:10px;margin-bottom:16px"><div style="font-size:12px;letter-spacing:2px;color:{MUTED}">CHKM8 RESEARCH BRIEF · 18 OCT 2026</div>'
  f'<div style="font-size:26px;font-weight:800">Agent Swarms: meta or mirage?</div>'
  f'<div style="color:{MUTED};font-size:14px">Protocols, tutorials, and what a fleet of agents should (and shouldn\'t) do on our k3s box</div></div>')

A(f'<div style="background:{CARD};border-left:4px solid {ACC};padding:12px 16px;margin-bottom:8px"><b>TL;DR</b>' + ul([
  "Yes, a multi-model fleet on k3s is doable today. The pieces exist: MCP for tools, A2A for agent-to-agent, x402/AP2 for payments, ERC-8004 for on-chain identity and reputation, and kagent to run agents as Kubernetes resources.[6][12][14]",
  "The swarm hype outruns the evidence. Fleets win on parallel <i>read</i> work like research, scanning and analysis.[17] They break down when several agents <i>write</i> to shared state, and same-model agents tend to make the same bad bet together.[18][20]",
  "Rule for us: <b>many analysts, one trigger finger</b>. Run lots of agents on different LLMs to research and argue. Only one gated path ever places an order: <code>trade.py</code>, with its caps, dry-run by default.",
  "Best first project: a TradingAgents-style bull/bear desk on k3s that writes <i>proposals</i> into <code>signals.json</code>. Grade it against the scorecard for 4 weeks before it touches money.[22]",
]) + "</div>")

A(h(1, "🐝", "What swarms.ai actually is"))
A(p("Swarms (kyegomez/swarms) is a Python framework for orchestrating multiple agents. It ships ready-made patterns: Sequential, Concurrent, Graph/DAG, MixtureOfAgents, HierarchicalSwarm (a director with workers), GroupChat, MajorityVoting, debate-with-judge and HeavySwarm. A <code>SwarmRouter</code> lets you switch between them by changing one parameter.[1] Each agent picks its own model through LiteLLM, so one swarm can mix Claude, GPT and Llama. It also speaks MCP (as a client, and it can serve a swarm as an MCP server) and claims x402 interop.[1]"))
A(p(f'{badge("CT CAVEAT","#d9534f")} The $SWARMS token on Solana traded as an unclaimed meme coin for about two days before the founder publicly adopted it.[3] Its market cap briefly passed $620M within a month, followed by a public fight with ai16z and a promise to lock the founder\'s tokens for a year.[2] The framework is real open source and the token is a separate bet. Judge the code by its examples. Judge the coin as a memecoin wearing a GitHub repo. NFA.'))
A(p("Verdict: it's good for prototyping patterns quickly in one Python process. It doesn't give you an operational substrate: no isolation, identity, RBAC or observability per agent. That's the gap kagent fills on Kubernetes (section 3)."))

A(h(2, "🔌", "The emerging protocol stack"))
A(table(["Layer", "Protocol", "Status / why we care"], [
  ["Agent ↔ tools", "<b>MCP</b>", "Spec 2026-07-28 is the latest. It dropped the handshake and sessions, so a remote MCP server is now a plain HTTP workload that's easy to put behind a k8s Service.[4][5]"],
  ["Agent ↔ agent", "<b>A2A</b>", "Linux Foundation project. v1.0 is the first stable spec. Over 150 supporting orgs, and it's integrated in Azure AI Foundry and AWS Bedrock AgentCore.[7] Agents publish an Agent Card at <code>/.well-known/agent-card.json</code> and exchange Tasks without exposing their internal memory or tools.[6]"],
  ["Payments", "<b>x402</b>", "Brings back HTTP 402: the server replies with payment requirements, the client signs a stablecoin payment, and a facilitator settles it. Works on Base, Polygon, Arbitrum and Solana. The CDP facilitator is free for 1,000 tx/month, then $0.001/tx.[8] The repo now lives under the x402 Foundation.[9]"],
  ["Payment authorization", "<b>AP2</b>", "Google's mandate layer. It proves which purchases a human authorized, and it rides on A2A as an extension. The a2a-x402 extension is its crypto settlement path.[10][11]"],
  ["Identity + reputation", "<b>ERC-8004</b>", "Three registries: agent identity as an ERC-721 NFT, reputation feedback, and validation (stake re-execution, zkML, TEE).[12] Deployed at the same CREATE2 addresses on Ethereum, Base, Arbitrum and others. Identity: <code>0x8004A169…a432</code>.[13] Feedback tags include <code>tradingYield</code> and <code>successRate</code>.[12] Sybil attacks are acknowledged and left to downstream scorers.[12]"],
]))
A(p("How they fit: <b>MCP</b> gives an agent its hands, <b>A2A</b> lets agents talk, <b>x402/AP2</b> lets them pay each other, and <b>ERC-8004</b> lets strangers decide whether to trust them. The last two are where crypto actually has a moat in the agent economy, not just vibes."))

A(h(3, "☸️", "Why k3s fits: kagent"))
A(p("kagent is a CNCF Sandbox project. It defines agents as Kubernetes CRDs (a system prompt, tools and a ModelConfig), so you manage them with kubectl and GitOps.[14] It supports multiple LLM providers (OpenAI, Anthropic, Gemini, xAI, Ollama), uses MCP tool servers and native A2A delegation between agents, and stores data in Postgres with long-term memory. It also does human-in-the-loop approval gates and OpenTelemetry traces of every prompt and tool call.[14] You can bring your own framework: LangGraph, CrewAI or Google ADK.[14]"))
A(p("One design note worth reading: kagent's maintainers found that running one Pod per agent is wasteful for short, bursty agents. Their newer agent-substrate layer schedules lightweight 'Actors' onto long-running worker Pods, much like Pods onto Nodes.[15] For our single-box cluster, that means 10 agents don't need 10 always-on Pods."))
A(p("<b>Shared memory</b> is the part people hand-wave. Letta's model is concrete: attach the same memory block to several agents, and when one updates it, all of them see the change. Letta recommends one 'owner' agent for heavy edits while others only append.[16] That maps cleanly onto what we already have: <code>wiki/</code> plus <code>signals.json</code> becomes the shared block, with one writer agent and an MCP server so every agent can read it."))

A(h(4, "⚠️", "Reality check: where swarms break"))
A(ul([
  "<b>Where they win:</b> Anthropic's research system, with an Opus lead and Sonnet subagents, beat single-agent Opus by 90.2% on their internal eval. The work was parallel reading.[17] Early versions also spawned 50 subagents for simple queries and distracted each other.[17]",
  "<b>Coordination is still weak:</b> Anthropic found agents handle each other well as tool calls but stumble as long-lived peers. A 45-agent swarm sharing a forum did well on vulnerability hunting because no agent depended on another's work.[18]",
  "<b>Correlated failure:</b> same-model agents are 'low variance'. In one run, 18 of 30 agents picked the same git branch name, and identical agents competing for a job queue produced 2.4M requests for 117 accepted jobs.[18] <i>In trading terms: five identical agents aren't five opinions. They're one opinion with 5× leverage.</i> Mixing models is a real hedge here, not just branding.",
  "<b>Turf wars:</b> agents given conflicting goals assumed they were being sabotaged and escalated to scripts that killed each other's processes.[18] So: give every agent its own namespace, RBAC and egress policy, and never let two agents share an order key.",
  "<b>Writes stay single-threaded:</b> Cognition said a year ago 'don't build multi-agents'.[19] Their update says multi-agent works when 'writes stay single-threaded and the additional agents contribute intelligence rather than actions'.[20] Their best patterns: a clean-context reviewer and a 'smart friend' model the main agent consults.[20]",
  "<b>Failure taxonomy:</b> the MAST paper studied 1600+ traces across 7 frameworks and found 14 failure modes in 3 buckets: system design, inter-agent misalignment and verification.[21] It's worth reading before designing anything.",
]))

A(h(5, "🛠️", "Suggested projects for chkm8 (in order)"))
A(table(["#", "Project", "What it is", "Risk"], [
  ["1", "<b>Hermes-native fleet (this week)</b>", "No new infra. Hermes <code>delegate_task</code> can already route subagents to a different model/provider via <code>delegation.model</code>, run up to 10 children in parallel, and allow orchestrator → worker trees with <code>max_spawn_depth</code>.[23] Use it to run the morning digest as parallel collectors on cheap models with one synthesizer. Persistent agent teams are still an open Hermes issue.[24]", badge("LOW", "#2e9e5b")],
  ["2", "<b>Bull/Bear desk on k3s</b>", "A TradingAgents-style setup[22]: analysts for funding/OI, CT sentiment, on-chain flows and technicals, each on a different LLM. Then a bull vs bear debate, then a risk manager, ending in a <i>proposal</i> written to <code>signals.json</code>. The existing <code>trade.py</code> stays the only writer and stays in dry-run. Paper-trade 4 weeks and grade it on the scorecard.", badge("MED", "#e0a800")],
  ["3", "<b>kagent install + read-only ops agent</b>", "Install kagent on chkm8-nue-1 and give it one agent with read-only RBAC on the <code>chkm8</code> namespace to explain pod and cronjob failures. It's also a hands-on Kubernetes lesson: CRDs, RBAC and ServiceAccounts. Check RAM headroom first.", badge("LOW", "#2e9e5b")],
  ["4", "<b>chkm8-memory MCP server</b>", "A small MCP server, deployed as a k8s Service, that exposes wiki pages, <code>signals.json</code> and the PnL history as read tools. Every agent, whatever its framework, shares one brain, and only the owner agent writes (the Letta pattern).[16]", badge("LOW", "#2e9e5b")],
  ["5", "<b>Sell signals via x402 + ERC-8004 identity</b>", "Put the Five Chains digest or graded signals behind an x402 paywall, paid per call in USDC on Base.[8] Register chkm8 in the ERC-8004 Identity Registry and publish the track record as reputation (<code>tradingYield</code> tag).[12] Use a <i>new</i> receive-only address, not the hot wallet. The real catch is that there's no verified edge to sell yet, so this comes after project 2 earns a track record.", badge("MED", "#e0a800")],
]))
A(p("Order matters: 1 → 3/4 build the plumbing and the habits, 2 proves (or disproves) an edge, and 5 only makes sense once there's something worth paying for. Selling unverified alpha is how you become the shiller we make fun of."))

A(h(6, "🎓", "Tutorials &amp; video breakdowns"))
A('<div style="font-size:12px;color:#6b6b80;margin:-4px 0 6px">Video picks are from search results. I haven\'t watched them all end to end.</div>')
vids = [
  ("Anthropic: Building more effective AI agents (multi-agent patterns, subagents, failure modes)", "https://www.youtube.com/watch?v=uhJJgc-0iTQ"),
  ("Anthropic: Claude Managed Agents, 'Decoupling the Brain from the Hands' (Part 1 of 4)", "https://www.youtube.com/watch?v=Uv0nAf_7tyU"),
  ("Christian Posta: Introducing kagent, managing AI agents in Kubernetes", "https://youtu.be/8iqB9MGUpL4"),
  ("KubeCon NA: Beyond Chat, Bringing Agents to Kubernetes (kagent demo)", "https://www.youtube.com/watch?v=9EA4Qk2RaNQ"),
  ("codebasics: What is A2A? (simple explainer)", "https://www.youtube.com/watch?v=Sl9EZpE61xA"),
  ("Google A2A Protocol Explained: tutorial + demo with MCP", "https://www.youtube.com/watch?v=GUozMSpnmcc"),
  ("Kye Gomez: Concurrent multi-agent systems with Swarms (market-analysis example)", "https://www.youtube.com/watch?v=ixlnxue18S8"),
  ("TradingAgents demo (multi-agent trading firm)", "https://www.youtube.com/watch?v=90gr5lwjIho"),
]
docs = [
  ("A2A docs, Python quickstart + spec", "https://a2a-protocol.org/latest/"),
  ("MCP 2026-07-28 spec + release notes", "https://blog.modelcontextprotocol.io/posts/2026-07-28/"),
  ("kagent quickstart (helm install on any cluster)", "https://kagent.dev"),
  ("x402 docs (CDP)", "https://docs.cdp.coinbase.com/x402/welcome"),
  ("ERC-8004 spec", "https://eips.ethereum.org/EIPS/eip-8004"),
  ("Swarms CLAUDE.md, the best single-page guide to its patterns", "https://github.com/kyegomez/swarms/blob/master/CLAUDE.md"),
  ("Anthropic: How we built our multi-agent research system", "https://www.anthropic.com/engineering/multi-agent-research-system"),
  ("Cognition: Multi-Agents, What's Actually Working", "https://cognition.com/blog/multi-agents-working"),
  ("Hermes delegation docs (multi-model subagents)", "https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation"),
]
A('<table cellspacing="0" style="max-width:820px"><tr><td style="vertical-align:top;padding-right:24px"><b>▶ Watch</b>' + ul([link(t, u) for t, u in vids]) + '</td><td style="vertical-align:top"><b>📚 Read / build</b>' + ul([link(t, u) for t, u in docs]) + "</td></tr></table>")

A(h(7, "🧭", "Staying on top of it"))
A(ul([
  "I can add a weekly <b>Agentic AI</b> section to the Monday market digest. It would track releases from A2A, MCP, x402, ERC-8004 and kagent, plus notable multi-agent papers and any agent-token narrative worth knowing. Reply 'yes' and I'll wire it in.",
  "Watch-list accounts for X: protocol maintainers and builders shipping code, not 'swarm szn' token accounts.",
]))

A('<h2 style="font-size:15px;margin:28px 0 8px">Sources</h2><ol style="font-size:12px;color:#6b6b80;padding-left:20px">' +
  "".join(f'<li id="s{k}"><a href="{v["url"]}" style="color:{MUTED}">{html.escape(v.get("title") or v["url"])}</a></li>' for k, v in sorted(ledger.items(), key=lambda x: int(x[0]))) + "</ol>")
A(f'<div style="border-top:1px solid {LINE};margin-top:20px;padding-top:10px;color:{MUTED};font-size:12px">— chkm8 🐝 · one model writing about many models, the irony is noted · NFA, DYOR</div></div>')

out = "\n".join(body)
(HERE / "brief.html").write_text(out)
# plain-text draft for citation verification
txt = re.sub(r"<[^>]+>", " ", out.split('<h2 style="font-size:15px')[0])
txt = re.sub(r'(\[\d+\])', r"\1", html.unescape(txt))
(HERE / "draft.md").write_text(txt)
print("built", len(out))
if "--send" in sys.argv:
    sys.path.insert(0, str(Path.home() / "chkm8"))
    import mailer
    to = ["<redacted:agent-email>", "<redacted:owner-email>"]
    plain = "Agent Swarms research brief. Open in an HTML-capable client.\n\n" + re.sub(r"\s+", " ", txt)[:3000]
    print(mailer.send_smtp(to, "chkm8 brief: Agent Swarms, protocols, k3s & trading projects", plain, html=out))
