/**
 * SoSoVault data shapes + offline fallback fixtures.
 *
 * Real data is fetched from the backend (`/strategy/generate`, `/portfolio/{address}`,
 * `/signals/feed`, etc.) which proxies the SoSoValue OpenAPI and SoDEX testnet REST API.
 * The fixtures below are only used when the backend is unreachable so the demo never
 * shows a blank screen.
 */

export type RiskLevel = "low" | "medium" | "high";

export type AllocationType = "Index" | "ETF Proxy" | "Stable Reserve";

export interface BasketAllocation {
  /** Index ticker (e.g. "ssimag7") or asset symbol (e.g. "BTC", "USDC"). */
  symbol: string;
  /** Human label, e.g. "SoSoValue Mag7 Index". */
  name: string;
  /** Whole-percent integer 0-100. */
  percentage: number;
  type: AllocationType;
  /** Trailing 1-month return as a decimal (e.g. 0.062 = +6.2%). */
  oneMonthRoi?: number;
  /** Trailing 1-year return as a decimal. */
  oneYearRoi?: number;
  /** Color hex for chart rendering. */
  color: string;
}

export interface BasketReasoning {
  /** Why this volatility band was chosen, plain language. */
  volatility: string;
  /** Yield / return narrative. */
  yield: string;
  /** Risk-control narrative (caps, drawdown protection, news triggers). */
  risk: string;
}

export interface StrategyRecommendation {
  summary: string;
  constraints: string[];
  allocations: BasketAllocation[];
  reasoning: BasketReasoning;
  /** Blended expected return (annualised, decimal). */
  estimatedYield: number;
  /** Estimated gas in native units (display only). */
  estimatedGas: number;
  executionSteps: string[];
}

export interface PortfolioToken {
  symbol: string;
  name: string;
  balance: number;
  value: number;
  percentage: number;
  color: string;
}

export interface PortfolioSnapshot {
  totalValue: number;
  change24h: number;
  tokens: PortfolioToken[];
}

export const riskProfiles: Record<RiskLevel, {
  label: string;
  description: string;
  expectedApy: string;
  color: string;
}> = {
  low: {
    label: "Low Risk",
    description:
      "Conservative SoSoValue index basket dominated by stable reserves and BTC-heavy exposure. Capital preservation first.",
    color: "risk-low",
    expectedApy: "3-7%",
  },
  medium: {
    label: "Medium Risk",
    description:
      "Balanced exposure across SoSoValue Mag7, Layer-1, and a stable reserve sleeve for rebalance flexibility.",
    color: "risk-medium",
    expectedApy: "7-18%",
  },
  high: {
    label: "High Risk",
    description:
      "Aggressive growth basket leaning into SoSoValue indices with the highest 1-month momentum and minimal stable reserve.",
    color: "risk-high",
    expectedApy: "15-40%",
  },
};

/**
 * Offline fallback baskets — used only if the backend is unreachable.
 * Real allocations come from `POST /strategy/generate` which builds them from
 * live SoSoValue index/ETF/news data.
 */
export const strategyByRisk: Record<RiskLevel, StrategyRecommendation> = {
  low: {
    summary:
      "Capital-preserving basket: half stable reserve, BTC-heavy via SoSoValue Layer-1 index, light Mag7 sleeve for upside.",
    constraints: [
      "Cap volatile index exposure below 50%",
      "Keep stable reserve above 40%",
      "Auto-derisk on negative ETF flow signals",
    ],
    allocations: [
      { symbol: "USDC", name: "USDC Stable Reserve", percentage: 50, type: "Stable Reserve", color: "#2775CA" },
      { symbol: "ssilayer1", name: "SoSoValue Layer-1 Index", percentage: 35, type: "Index", color: "#F7931A", oneMonthRoi: 0.04, oneYearRoi: 0.32 },
      { symbol: "ssimag7", name: "SoSoValue Mag7 Index", percentage: 15, type: "Index", color: "#627EEA", oneMonthRoi: 0.062, oneYearRoi: 0.45 },
    ],
    reasoning: {
      volatility:
        "Recent BTC ETF flows are choppy and news sentiment skews neutral, so the basket biases toward stable reserves while still capturing index drift.",
      yield:
        "Blended return is anchored by Layer-1 index drift and a small Mag7 sleeve; downside is bounded by the 50% USDC reserve.",
      risk:
        "Negative ETF flow days will trigger an auto-rotation: 5% rotates from Mag7 → USDC if cumulative inflow turns negative for 48h.",
    },
    estimatedYield: 0.058,
    estimatedGas: 0.0038,
    executionSteps: [
      "Approve USDC into PortfolioManager",
      "Mint SoSoVault shares at current NAV",
      "Submit BasketRebalance(weights, symbols) on SoDEX testnet",
      "Emit BasketRebalanced event for on-chain audit trail",
    ],
  },
  medium: {
    summary:
      "Balanced SoSoValue index basket: equal-weight Mag7 and Layer-1 exposure with a meaningful stable reserve.",
    constraints: [
      "Maintain stable reserve between 25-35%",
      "Equal-weight major SoSoValue indices",
      "Trim positions with 7-day ROI below -8%",
    ],
    allocations: [
      { symbol: "ssimag7", name: "SoSoValue Mag7 Index", percentage: 40, type: "Index", color: "#627EEA", oneMonthRoi: 0.062, oneYearRoi: 0.45 },
      { symbol: "ssilayer1", name: "SoSoValue Layer-1 Index", percentage: 30, type: "Index", color: "#F7931A", oneMonthRoi: 0.04, oneYearRoi: 0.32 },
      { symbol: "USDC", name: "USDC Stable Reserve", percentage: 30, type: "Stable Reserve", color: "#2775CA" },
    ],
    reasoning: {
      volatility:
        "Index volatility is moderate; the basket leans into Mag7 momentum while keeping a 30% reserve to fund opportunistic rebalances.",
      yield:
        "Weighted yield is dominated by Mag7 1-month ROI (+6.2%) and Layer-1 drift (+4%), with the stable sleeve providing dry powder.",
      risk:
        "Concentration risk is controlled by equal-weighting two SoSoValue indices and a 30% USDC floor; news-triggered de-risk is enabled.",
    },
    estimatedYield: 0.124,
    estimatedGas: 0.0045,
    executionSteps: [
      "Approve USDC into PortfolioManager",
      "Mint SoSoVault shares at current NAV",
      "Route 70% of capital across Mag7 + Layer-1 SoDEX pairs",
      "Hold 30% USDC reserve, emit BasketRebalanced event",
    ],
  },
  high: {
    summary:
      "Aggressive growth basket leaning into the highest-momentum SoSoValue index with a small stable buffer.",
    constraints: [
      "Mag7 weight at least 50%",
      "Stable reserve no more than 20%",
      "Active rebalance every 4h on signal change",
    ],
    allocations: [
      { symbol: "ssimag7", name: "SoSoValue Mag7 Index", percentage: 60, type: "Index", color: "#627EEA", oneMonthRoi: 0.062, oneYearRoi: 0.45 },
      { symbol: "ssilayer1", name: "SoSoValue Layer-1 Index", percentage: 25, type: "Index", color: "#F7931A", oneMonthRoi: 0.04, oneYearRoi: 0.32 },
      { symbol: "USDC", name: "USDC Buffer", percentage: 15, type: "Stable Reserve", color: "#2775CA" },
    ],
    reasoning: {
      volatility:
        "The basket accepts wider price swings, prioritising Mag7 momentum capture. Tight 4h rebalance cadence keeps the position aligned with signals.",
      yield:
        "Expected return is dominated by Mag7 1-month ROI; the small Layer-1 sleeve diversifies inside the volatile band.",
      risk:
        "Drawdown exposure is real. The 15% buffer plus auto-trim on -8% 7-day ROI provides the only safety net.",
    },
    estimatedYield: 0.243,
    estimatedGas: 0.0062,
    executionSteps: [
      "Approve USDC into PortfolioManager",
      "Mint SoSoVault shares at current NAV",
      "Route 85% of capital across Mag7 + Layer-1 SoDEX pairs",
      "Schedule 4h rebalance loop, emit BasketRebalanced event",
    ],
  },
};

/**
 * Default basket displayed before a risk profile is selected.
 * Existing components import `aiStrategy` — keep that symbol exported so the build
 * does not break while we incrementally migrate to the props-driven flow.
 */
export const aiStrategy: StrategyRecommendation = strategyByRisk.medium;

export const portfolioData: PortfolioSnapshot = {
  totalValue: 84521.34,
  change24h: 3.42,
  tokens: [
    { symbol: "ssimag7", name: "SoSoValue Mag7 Index", balance: 1620, value: 33892, percentage: 40.1, color: "#627EEA" },
    { symbol: "ssilayer1", name: "SoSoValue Layer-1 Index", balance: 1050, value: 25356, percentage: 30.0, color: "#F7931A" },
    { symbol: "USDC", name: "USDC Reserve", balance: 25273.34, value: 25273.34, percentage: 29.9, color: "#2775CA" },
  ],
};

export const performanceData = [
  { date: "Apr 14", value: 70200 },
  { date: "Apr 18", value: 72800 },
  { date: "Apr 22", value: 71350 },
  { date: "Apr 26", value: 75420 },
  { date: "Apr 30", value: 77900 },
  { date: "May 04", value: 79800 },
  { date: "May 08", value: 82100 },
  { date: "May 12", value: 84521 },
];

export const activityLog = [
  { id: 1, type: "deposit" as const, description: "Deposited 10,000 USDC", timestamp: "2026-05-11 14:32", status: "success" as const },
  { id: 2, type: "strategy" as const, description: "Basket rebalanced to Medium Risk", timestamp: "2026-05-11 14:35", status: "success" as const },
  { id: 3, type: "rebalance" as const, description: "Auto-rebalance: +3% ssimag7, -3% USDC (Mag7 ROI signal)", timestamp: "2026-05-10 18:44", status: "success" as const },
  { id: 4, type: "strategy" as const, description: "Generated Signal-to-Execution plan", timestamp: "2026-05-09 11:20", status: "success" as const },
];

export const architectureLayers = [
  {
    title: "Frontend Dashboard",
    purpose: "Wallet connection, portfolio view, risk selection, basket review, and execution approvals.",
    modules: ["MetaMask / WalletConnect", "Portfolio overview", "Risk selector", "Basket panel", "Signals feed"],
  },
  {
    title: "Backend / AI Engine",
    purpose: "Pull SoSoValue indices, ETF flows, and news; convert risk profile into constraints; build basket.",
    modules: ["SoSoValue API client", "Basket builder", "AI reasoning layer", "SoDEX price client"],
  },
  {
    title: "Smart Contracts",
    purpose: "Deposit/withdraw share accounting and on-chain audit trail of every basket rebalance.",
    modules: ["PortfolioManager", "deposit()", "withdraw()", "executeBasket()", "BasketRebalanced event"],
  },
  {
    title: "Execution Layer",
    purpose: "Route basket weights into actual orders on the SoDEX orderbook (Wave 2).",
    modules: ["SoDEX testnet REST", "EIP-712 order signing", "Bookticker pricing"],
  },
];

export const architectureFlow = [
  "User connects wallet on SoDEX testnet",
  "User selects a risk tier (Low / Medium / High)",
  "Backend pulls live SoSoValue indices, ETF flows, and news",
  "Basket builder converts the risk tier + signals into target weights",
  "An AI reasoning layer produces human-readable explanations for each pillar",
  "Frontend shows the basket, reasoning, and SoDEX-priced expected slippage",
  "User confirms execution; PortfolioManager mints shares and emits BasketRebalanced",
  "Background loop monitors signals; auto-rebalances on ETF flow / news triggers",
];

export const mvpPrinciples = [
  "Real SoSoValue API calls drive every basket — no hardcoded allocations",
  "One AI inference call per strategy generation produces the explainable reasoning",
  "SoDEX bookticker REST is integrated read-only in Wave 1; signed order placement lands in Wave 2",
  "Smart contract is intentionally minimal: deposit/withdraw/share accounting + BasketRebalanced event",
];
