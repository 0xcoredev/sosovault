# SoSoVault

> Agentic on-chain index portfolios — pick a risk tier, get a SoSoValue-curated index basket, route the rebalance through SoDEX with EIP-712 signed orders.

**SoSoValue Buildathon — Wave 2 submission**

[![Wave](https://img.shields.io/badge/Wave-2%20%E2%80%94%20Execution-blue)]()
[![SoSoValue API](https://img.shields.io/badge/SoSoValue-35%2B%20endpoints-green)]()
[![SoDEX](https://img.shields.io/badge/SoDEX-EIP--712%20live-green)]()
[![AI](https://img.shields.io/badge/AI-agent%20pipeline-orange)]()
[![DB](https://img.shields.io/badge/DB-SQLite-purple)]()

---

## Live demo

- **Frontend:** https://sosovault.vercel.app
- **Backend (live API):** https://sosovault-api.onrender.com
- **Repo:** this repository

> Free-tier Render spins the backend down after 15 min of inactivity — first
> request after a cold start may take ~30s. Subsequent requests are instant.

---

## Wave 2 highlights

| Deliverable | What changed |
|---|---|
| **EIP-712 SoDEX execution** | Real signed orders replace paper mode. Full `ExchangeAction` signing pipeline in Python. |
| **SQLite persistence** | 5 tables: signals, trades, agent_logs, portfolio_snapshots, wallets |
| **Signal outcome tracking** | Every signal gets HIT/STOP/DRIFT classification with public win rate stats |
| **Risk management** | 4-check gatekeeper (daily cap, concentration, confidence, drawdown) + circuit breaker |
| **Agent pipeline** | Orchestrator coordinates: risk gate → EIP-712 execution → trade recording → snapshot |
| **35+ SoSoValue endpoints** | All 9 API modules: Currencies, ETF, Indices, Stocks, BTC Treasuries, Fundraising, Macro, Analysis, News |
| **Background scanner** | Auto-generates signals every 5 min, checks outcomes every 2 min |
| **51 API routes** | Up from 8 in Wave 1 |
| **Sector intelligence** | Composite scoring (30% 7d + 35% 1m + 35% 24h) with STRONG_BUY/BUY/NEUTRAL/SELL verdicts |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                  Frontend (React + Vite + shadcn)              │
│  Dashboard · Strategy · Signals · Activity · Wallet (SoDEX)    │
└────────────────────────────┬────────────────────────────────────┘
                             │  REST (JSON) — 51 endpoints
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              Backend (FastAPI · Python 3.11 · SQLite)           │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Orchestrator (orchestrator.py)                          │   │
│  │   risk gate → EIP-712 execution → trade recording → DB  │   │
│  └────┬────────────┬──────────────┬───────────────┬────────┘   │
│       │            │              │               │             │
│  ┌────▼────┐ ┌─────▼─────┐ ┌─────▼─────┐ ┌──────▼──────┐     │
│  │ Risk    │ │ EIP-712   │ │ Scanner   │ │ SoSoValue   │     │
│  │ Manager │ │ SoDEX     │ │ Tracker   │ │ Client      │     │
│  │ 4-check │ │ signing   │ │ HIT/STOP  │ │ 35+ EP      │     │
│  │ +breaker│ │ + orders  │ │ /DRIFT    │ │ 9 modules   │     │
│  └─────────┘ └───────────┘ └───────────┘ └─────────────┘     │
│                                                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │ Basket   │ │ Signals  │ │ LLM      │ │ SQLite           │  │
│  │ Builder  │ │ Builder  │ │ Reasoning│ │ 5 tables         │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### EIP-712 signing flow

```
order body → keccak256(JSON({type, params})) → ExchangeAction{payloadHash, nonce}
→ sign with private key → wire format 0x01+r+s+v (v normalized 27/28→0/1)
→ X-API-Sign / X-API-Nonce / X-API-Chain headers
→ POST /api/v1/spot/trade/orders/batch
```

---

## Repository layout

```
sosovault/
├── frontend/                 React + Vite + shadcn dashboard
│   └── src/
│       ├── pages/            Index, Dashboard, Strategy, Signals, Activity
│       ├── components/       GlassCard, TopNav, Sidebar, etc.
│       ├── hooks/use-wallet  SoDEX-testnet wallet logic
│       └── lib/api.ts        30+ typed API methods
├── backend/                  FastAPI service
│   ├── main.py               51 routes, lifespan-managed background scanner
│   ├── services/
│   │   ├── database.py       SQLite layer (5 tables)
│   │   ├── eip712.py         EIP-712 signing + SoDEX order placement
│   │   ├── orchestrator.py   Agent pipeline coordinator
│   │   ├── risk.py           4-check gatekeeper + circuit breaker
│   │   ├── scanner.py        Signal tracker + background generator
│   │   ├── basket.py         Risk-tier basket builder
│   │   ├── signals.py        ETF/momentum/news signal builder
│   │   ├── sosovalue.py      35+ endpoint client (9 modules)
│   │   ├── sodex.py          SoDEX read-only client
│   │   └── llm.py            Groq LLM reasoning
│   └── requirements.txt
├── contracts/PortfolioManager.sol
├── scripts/deploy.js
├── test/PortfolioManager.js
└── hardhat.config.js
```

---

## API endpoints (51 total)

### Execution & Strategy
| Method | Path | Description |
|---|---|---|
| `POST` | `/strategy/generate` | Build basket with AI reasoning + risk check |
| `POST` | `/strategy/execute` | EIP-712 signed basket execution on SoDEX |

### Signals & Tracking
| Method | Path | Description |
|---|---|---|
| `GET` | `/signals/feed` | Live ETF/momentum/news signals |
| `GET` | `/signals/tracker` | Signal outcome history (HIT/STOP/DRIFT) |
| `GET` | `/signals/stats` | Public win rate statistics |
| `POST` | `/signals/scan` | Manual signal generation + outcome scan |

### Trades & Agent Logs
| Method | Path | Description |
|---|---|---|
| `GET` | `/trades` | Trade history with filters |
| `GET` | `/trades/stats` | Fill/fail/notional statistics |
| `GET` | `/agent/logs` | Agent activity logs |

### Risk Management
| Method | Path | Description |
|---|---|---|
| `GET` | `/risk/status` | Circuit breaker + parameters |
| `POST` | `/risk/check` | Run all 4 risk checks |
| `POST` | `/risk/circuit-breaker/reset` | Manual reset |

### SoDEX
| Method | Path | Description |
|---|---|---|
| `GET` | `/sodex/quote` | Bookticker quote |
| `GET` | `/sodex/symbols` | All spot markets |
| `GET` | `/sodex/orderbook` | Live orderbook depth |
| `GET` | `/sodex/balances/{addr}` | Account balances |
| `GET` | `/sodex/status` | Integration status |

### Sectors & Portfolio
| Method | Path | Description |
|---|---|---|
| `GET` | `/sectors/intel` | All indices scored + verdict |
| `GET` | `/sectors/intel/{t}/basket` | Top 3 assets per sector |
| `GET` | `/portfolio/{addr}` | Portfolio (SoDEX or DB snapshot) |
| `GET` | `/snapshots/{addr}` | Historical snapshots |

### SoSoValue (20+ proxy routes)
All 9 modules proxied with caching: `/sosovalue/indices`, `/sosovalue/etfs`, `/sosovalue/currencies`, `/sosovalue/crypto-stocks`, `/sosovalue/btc-treasuries`, `/sosovalue/fundraising`, `/sosovalue/macro/events`, `/sosovalue/analyses`, `/sosovalue/sector-spotlight`

---

## Setup

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Required
export SOSOVALUE_API_KEY=...

# For real SoDEX execution (optional — falls back to read-only quotes)
export SODEX_PRIVATE_KEY=0x...
export SODEX_ADDRESS=0x...
export SODEX_ACCOUNT_ID=...

# For AI reasoning (optional — falls back to deterministic templates)
export GROQ_API_KEY=...

uvicorn main:app --port 3001 --reload
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

### Contracts

```bash
npm install
npx hardhat compile
npx hardhat test
```

---

## Wave 1 → Wave 2

| Dimension | Wave 1 | Wave 2 |
|---|---|---|
| Execution | Paper mode | Real EIP-712 signed orders |
| Database | None | SQLite, 5 tables |
| SoSoValue endpoints | 5 | 35+, all 9 modules |
| Signal tracking | Display only | HIT/STOP/DRIFT + win rate |
| Risk management | Copy only | 4-check + circuit breaker |
| Agent system | Single LLM call | Orchestrator pipeline |
| Background tasks | None | 5min gen, 2min scan |
| Portfolio data | Fixtures | SoDEX balances or DB |
| API endpoints | 8 | 51 |

---

## License

MIT
