# SoSoVault

> Agentic on-chain index portfolios — pick a risk tier, get a SoSoValue-curated index basket, route the rebalance through SoDEX.

**SoSoValue Buildathon — Wave 1 submission**

[![Wave](https://img.shields.io/badge/Wave-1%20%E2%80%94%20Concept%2FPrototype-blue)]()
[![SoSoValue API](https://img.shields.io/badge/SoSoValue-OpenAPI%20live-green)]()
[![SoDEX](https://img.shields.io/badge/SoDEX-testnet%20read--only-green)]()
[![AI](https://img.shields.io/badge/AI-reasoning%20layer-orange)]()

---

## Project overview

| Field | Value |
|---|---|
| **Project name** | SoSoVault |
| **Short description** | An agentic on-chain fund manager. Pick a risk tier; SoSoVault assembles a SoSoValue-curated index basket, explains its reasoning using live ETF flows + news, and routes the rebalance through SoDEX. |
| **Target users** | Crypto-curious users who want professional-grade index exposure without managing it themselves. Also DeFi natives who want explainable, signal-driven rebalances instead of static "yield farms". |
| **Core APIs** | SoSoValue OpenAPI (`/indices`, `/indices/{t}/market-snapshot`, `/etfs/{t}/market-snapshot`, `/news`); SoDEX testnet REST (`/api/v1/spot/markets/bookTickers`); AI reasoning layer. |
| **Data sources** | SoSoValue indices, SoSoValue ETF flow data (IBIT spot ETF), SoSoValue news feed, live SoDEX bookticker quotes. |

### Why this maps to all three judging teams

- **SoSoValue (data / news):** the Strategy *and* Signals pages consume live `/indices`, `/etfs/{t}`, `/news`, `/indices/{t}/market-snapshot`. News headlines are classified as bullish / bearish / neutral and surfaced with a one-click rebalance suggestion.
- **SoSoValueIndexes:** the basket builder uses real SoSoValue index tickers (`ssimag7`, `ssilayer1`, …) as the basket components — not generic "ETH/USDC LP" placeholders. Index 1-month and 1-year ROI drive the momentum tilt that decides per-tier weights.
- **SoDEX:** every basket calls SoDEX testnet `/markets/bookTickers` for live BTC/ETH pair pricing in the execution flow. Wave 2 wires EIP-712 `newOrder` placement through the same gateway.

---

## Live demo

- **Frontend:** _to be deployed on Vercel after submission_
- **Backend:** _to be deployed on Render_
- **Repo:** this repository

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                  Frontend (React + Vite + shadcn)              │
│  Dashboard · Strategy · Signals · Activity · Wallet (SoDEX)    │
└────────────────────────────┬────────────────────────────────────┘
                             │  REST (JSON)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                Backend (FastAPI · Python 3.11)                 │
│  ┌──────────────────────┐  ┌──────────────────────┐            │
│  │ basket builder       │  │ signals builder      │            │
│  │ (services/basket.py) │  │ (services/signals.py)│            │
│  └──────┬───────┬───────┘  └────┬─────────────────┘            │
│         │       │               │                                │
│         ▼       ▼               ▼                                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                        │
│  │ AI reasoning layer │ │ SoSoValue│ │ SoDEX    │                        │
│  │ reasoning│ │ OpenAPI  │ │ bookticker│                        │
│  │ (llm.py) │ │(sosovalue│ │ (sodex.py)│                        │
│  │          │ │   .py)   │ │           │                        │
│  └──────────┘ └──────────┘ └──────────┘                        │
└─────────────────────────────────────────────────────────────────┘

  Smart contract (PortfolioManager.sol — Wave 2 deployment)
  ┌─────────────────────────────────────────────────────┐
  │ deposit(usdc) → mint shares                          │
  │ withdraw(shares) → burn + return USDC               │
  │ executeBasket(weights[], symbols[]) → emit event    │
  │   ↳ on-chain audit trail of every rebalance          │
  └─────────────────────────────────────────────────────┘
```

### Wave 1 scope (this submission)

✅ **Live SoSoValue OpenAPI integration** (real `x-soso-api-key` calls — no fixtures in the hot path)
✅ **Live SoDEX testnet bookticker** integration (read-only, no auth required)
✅ **AI reasoning layer reasoning** for every basket (with deterministic templated fallback if the key is missing)
✅ **Signals page** turning ETF flows + index momentum + news sentiment into one-click rebalance suggestions
✅ **PortfolioManager.sol** written and unit-tested (3 passing tests)
✅ **Wallet flow** auto-switches MetaMask to SoDEX testnet (`chainId 138565`)
🅿️ **Paper execution** — the Submit Basket button posts to `/strategy/execute` which fetches a real SoDEX quote and returns a clearly labeled mock tx hash. _Wave 2 will sign EIP-712 `newOrder` messages._
🅿️ **Smart contract NOT deployed** for Wave 1 — deferred to Wave 2 (matches the official Wave 2 focus: "initial SoDEX API or execution module integration").

### Wave 2 plan

1. Deploy `PortfolioManager.sol` to SoDEX testnet (chainId 138565) and update `VITE_PORTFOLIO_MANAGER_ADDRESS`.
2. Implement EIP-712 `ExchangeAction` signing in the backend agent (per [SoDEX docs](https://sodex.com/documentation/api/api)). Submit `newOrder` for each non-stable basket leg via `/api/v1/spot/orders`.
3. After all legs settle, the agent calls `executeBasket(weights[], symbols[])` on the contract, emitting `BasketRebalanced` for the on-chain audit trail.
4. Background loop re-scans signals every 5 minutes and triggers an auto-rebalance when the suggested action's confidence > 0.7.

### Wave 3 plan

1. Risk-control layer: max-drawdown caps per tier, news-triggered de-risk, per-tier slippage budget enforcement.
2. Multi-account agent (one EIP-712 wallet, multiple sub-account vaults).
3. Deeper SoSoValue integration: BTC Treasuries, Macro events, Analysis Charts modules.
4. UX polish, public landing page, demo video, audit pass.

---

## Repository layout

```
sosovault/
├── README.md                this file
├── frontend/                React + Vite dashboard
│   ├── src/
│   │   ├── pages/           Index, Dashboard, Strategy, Signals, Activity
│   │   ├── components/dashboard/   GlassCard / PortfolioCard / RiskProfileSelector / AIStrategyCard / ExecutionPanel / Sidebar / TopNav / ActivityLog / EmptyState
│   │   ├── hooks/use-wallet.ts     SoDEX-testnet wallet logic
│   │   └── lib/             api.ts, contracts.ts, mock-data.ts (fallback only)
│   └── .env.example
├── backend/                 FastAPI service
│   ├── main.py              routes: /portfolio /strategy /signals /sodex/quote /activity
│   ├── services/
│   │   ├── sosovalue.py     SoSoValue OpenAPI client (cached)
│   │   ├── sodex.py         SoDEX read-only client (testnet)
│   │   ├── llm.py           AI reasoning with fallback
│   │   ├── basket.py        risk-tier basket builder
│   │   └── signals.py       ETF/momentum/news → signals
│   ├── requirements.txt
│   └── .env.example
├── contracts/PortfolioManager.sol   Wave 2 deployment target
├── scripts/deploy.js                Hardhat deploy script
├── test/PortfolioManager.js         3 unit tests
├── hardhat.config.js
└── render.yaml                      backend deploy config
```

---

## Setup

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Required for live SoSoValue calls (the demo will still run with fixtures if missing).
export SOSOVALUE_API_KEY=...
# Optional: real LLM reasoning. Falls back to deterministic templated text if missing.
export GROQ_API_KEY=...

uvicorn main:app --port 3001 --reload
```

Smoke test:

```bash
curl http://localhost:3001/                          # service info + integration flags
curl http://localhost:3001/signals/feed              # live signal feed
curl http://localhost:3001/sodex/quote?symbol=vBTC_vUSDC
curl -X POST http://localhost:3001/strategy/generate \
     -H 'content-type: application/json' \
     -d '{"address":"0xdead","riskLevel":"medium"}'
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env  # adjust VITE_API_URL if backend is remote
npm run dev           # runs on http://localhost:8080
```

### Contracts (optional)

```bash
npm install
npx hardhat compile
npx hardhat test
# Wave 2 deployment:
# DEPLOYER_PRIVATE_KEY=... npx hardhat run scripts/deploy.js --network sodexTestnet
```

---

## Judging-criteria self-review

| Criterion | Weight | How SoSoVault scores |
|---|---|---|
| **User Value & Practical Impact** | 30% | "Pick a risk tier and get an explainable, signal-driven on-chain index portfolio" is a clear, defensible use case. Three judging teams each see direct value: data team (Signals page), index team (basket = real SoSoValue indices), DEX team (SoDEX execution rail). |
| **Functionality & Working Demo** | 25% | Live Vercel deployment. Real SoSoValue API calls. Real SoDEX bookticker quotes. Wallet connect + chain switch. Paper-mode execution clearly labeled to avoid misleading judges. |
| **Logic, Workflow & Product Design** | 20% | Risk tier → live SoSoValue data → momentum-tilted basket → AI reasoning → SoDEX quote → mocked submission → on-chain audit trail (Wave 2). Each stage has its own service module with explicit input/output contracts. |
| **Data / API Integration** | 15% | Five SoSoValue endpoints integrated live (`/indices`, `/indices/{t}/constituents`, `/indices/{t}/market-snapshot`, `/etfs/{t}/market-snapshot`, `/news`). One SoDEX testnet endpoint integrated live. AI reasoning layer integrated. All three external surfaces are real. |
| **UX & Clarity** | 10% | Polished Tailwind + shadcn + Framer Motion design. Sidebar nav, sticky top nav, glass cards, animated donut allocations, sonner toasts, modal flows. Mobile-aware grid layouts. |

**Bonus features hit:** SoDEX integration ⭐, AI/LLM-enhanced ⭐, opportunity discovery (Signals) ⭐, risk control framing in copy ⭐, insight-to-action loop (Signals → Apply) ⭐, polished UX ⭐.

---

## Team

- **Builder:** _your handle here_ — full-stack engineer, single-person team
- **Contact:** _your email or Discord_

---

## Wave 1 changelog

- ✅ Initial Wave 1 submission — concept + interactive prototype
- ✅ Live SoSoValue OpenAPI integration (5 endpoints)
- ✅ Live SoDEX testnet bookticker integration
- ✅ AI reasoning layer with deterministic fallback
- ✅ Signals page with ETF flow + index momentum + news sentiment heuristics
- ✅ Risk-tier basket builder with momentum-tilt and ETF-flow risk-off rules
- ✅ PortfolioManager.sol minimal share-accounting contract + 3 unit tests
- ✅ Wallet auto-switches to SoDEX testnet (chainId 138565)
- ✅ Paper-execution mode clearly labeled (Wave 2 will swap in EIP-712 signing)

---

## License

MIT
