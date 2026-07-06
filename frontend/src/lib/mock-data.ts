/**
 * SoSoVault data shapes and static config.
 *
 * All real data is fetched from the backend API.
 * This file exports TypeScript types and UI config (risk profiles).
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
