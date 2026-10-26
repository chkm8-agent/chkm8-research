# chkm8-research

Part of **chkm8**, r3lik's autonomous crypto research and trading agent, built on a stock [Hermes Agent](https://hermes-agent.nousresearch.com) install. Main repo: [chkm8-agent/chkm8](https://github.com/chkm8-agent/chkm8).

Data collectors, digest mailer and backtests behind chkm8's daily market digests.

- `digest_collect.py`: morning market digest data (CoinGecko, DefiLlama, Lighter perps, X chatter,
  past signal scoring); raw JSON goes to `chkm8-wiki/raw/digests/`.
- `chains_collect.py`: "Five Chains" digest data (BTC, ETH, NEAR, ZEC, XMR).
- `agentic_collect.py`: weekly agentic-AI section (repo releases, arXiv, AI-agent tokens).
- `digest_send.py`: renders a markdown digest as a newsletter (PNG via headless Brave) and emails it;
  editions: market and Five Chains; extra local editions load via `CHKM8_DIGEST_EDITIONS`.
- `bt/`: regime and mean-reversion backtests (see `bt/README.md`, `bt/mr/README.md`).
- `swarms_brief/`: one-off research brief.

Collected data (`*.json`) and rendered HTML are gitignored.

## License

MIT, see [LICENSE](LICENSE).
