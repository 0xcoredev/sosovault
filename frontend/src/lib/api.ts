import type {
  RiskLevel,
  StrategyRecommendation,
  PortfolioSnapshot,
} from "@/lib/mock-data";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:3001";

export type PortfolioData = PortfolioSnapshot;

export interface PerformancePoint {
  date: string;
  value: number;
}

export interface ActivityItem {
  id: number;
  type: "deposit" | "strategy" | "rebalance" | "withdraw";
  description: string;
  timestamp: string;
  status: "success" | "pending" | "failed";
  txHash?: string;
}

export interface StrategyRequest {
  address: string;
  riskLevel: RiskLevel;
  currentPortfolio?: PortfolioData;
}

export interface StrategyResponse {
  strategy: StrategyRecommendation;
  sosovalue: {
    indices_used: string[];
    sample_index_price?: number;
    last_etf_inflow?: number;
  };
  llm: {
    provider: string;
    model: string;
    latency_ms: number;
  };
  risk?: RiskCheckResult;
}

export interface SodexQuote {
  symbol: string;
  bidPx: string;
  bidSz: string;
  askPx: string;
  askSz: string;
  fetchedAt: string;
}

export interface NewsItem {
  id: string;
  title: string;
  release_time: number;
  source_link?: string;
}

export interface SignalItem {
  id: string;
  kind: string;
  direction: string;
  asset: string;
  headline: string;
  detail: string;
  confidence: number;
  suggested_action: string;
  generated_at: string;
  entry_price?: number;
  take_profit?: number;
  stop_loss?: number;
  outcome?: string;
  outcome_price?: number;
  outcome_at?: string;
}

export interface SignalsFeed {
  signals: SignalItem[];
  news: NewsItem[];
  generated_at: string;
}

export interface SignalStats {
  total: number;
  hit: number;
  stop: number;
  drift: number;
  pending: number;
  win_rate: number;
  resolved: number;
}

export interface SignalTrackerResponse {
  signals: SignalItem[];
  stats: SignalStats;
}

export interface TradeItem {
  id: number;
  address: string;
  signal_id?: string;
  symbol: string;
  side: string;
  order_type: string;
  quantity: number;
  price: number;
  notional: number;
  sodex_order_id?: string;
  tx_hash?: string;
  status: string;
  error_message?: string;
  created_at: string;
  filled_at?: string;
}

export interface TradeStats {
  total: number;
  filled: number;
  failed: number;
  pending: number;
  total_notional: number;
}

export interface AgentLog {
  id: number;
  agent: string;
  action: string;
  input_data?: string;
  output_data?: string;
  success: number;
  latency_ms?: number;
  created_at: string;
}

export interface RiskCheckResult {
  all_passed: boolean;
  checks: Array<{
    check: string;
    passed: boolean;
    [key: string]: unknown;
  }>;
  timestamp: string;
}

export interface RiskStatus {
  circuit_breaker: {
    open: boolean;
    consecutive_fails: number;
    cooldown_remaining_s: number;
  };
  parameters: {
    max_daily_trades: number;
    max_concentration_pct: number;
    min_signal_confidence: number;
    max_daily_drawdown_pct: number;
  };
  blocked_assets: string[];
}

export interface SectorIntel {
  ticker: string;
  price: number;
  change_24h: number;
  roi_7d: number;
  roi_1m: number;
  roi_1y: number;
  score: number;
  verdict: string;
}

export interface SodexStatus {
  configured: boolean;
  chain_id: number;
  base_url: string;
  address: string;
  account_id: number;
}

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
}

class ApiService {
  private async fetchApi<T>(endpoint: string, options?: RequestInit): Promise<ApiResponse<T>> {
    try {
      const response = await fetch(`${API_URL}${endpoint}`, {
        ...options,
        headers: {
          "Content-Type": "application/json",
          ...options?.headers,
        },
      });

      if (!response.ok) {
        return { success: false, error: `HTTP ${response.status}` };
      }

      const data = await response.json();
      return { success: true, data };
    } catch (error) {
      console.error(`API error (${endpoint}):`, error);
      return { success: false, error: "Network error" };
    }
  }

  async getPortfolio(address: string): Promise<ApiResponse<PortfolioData>> {
    return this.fetchApi<PortfolioData>(`/portfolio/${address}`);
  }

  async getPerformance(
    address: string,
    period: "24h" | "7d" | "30d" | "all" = "30d",
  ): Promise<ApiResponse<PerformancePoint[]>> {
    return this.fetchApi<PerformancePoint[]>(`/portfolio/${address}/performance?period=${period}`);
  }

  async getStrategy(request: StrategyRequest): Promise<ApiResponse<StrategyResponse>> {
    return this.fetchApi<StrategyResponse>("/strategy/generate", {
      method: "POST",
      body: JSON.stringify(request),
    });
  }

  async executeStrategy(
    address: string,
    allocations: number[],
    symbols: string[],
    totalValue?: number,
  ): Promise<ApiResponse<{ ok: boolean; mode: string; risk?: RiskCheckResult; results?: unknown[] }>> {
    return this.fetchApi("/strategy/execute", {
      method: "POST",
      body: JSON.stringify({ address, allocations, symbols, totalValue }),
    });
  }

  async getActivity(address: string, limit = 50): Promise<ApiResponse<ActivityItem[]>> {
    return this.fetchApi<ActivityItem[]>(`/activity/${address}?limit=${limit}`);
  }

  async getSignals(): Promise<ApiResponse<SignalsFeed>> {
    return this.fetchApi<SignalsFeed>("/signals/feed");
  }

  async getSignalTracker(limit = 50): Promise<ApiResponse<SignalTrackerResponse>> {
    return this.fetchApi<SignalTrackerResponse>(`/signals/tracker?limit=${limit}`);
  }

  async getSignalStats(): Promise<ApiResponse<SignalStats>> {
    return this.fetchApi<SignalStats>("/signals/stats");
  }

  async triggerSignalScan(): Promise<ApiResponse<{ generated: unknown; scanned: unknown }>> {
    return this.fetchApi("/signals/scan", { method: "POST" });
  }

  async getTrades(address?: string, limit = 50): Promise<ApiResponse<{ trades: TradeItem[]; stats: TradeStats }>> {
    const params = new URLSearchParams();
    if (address) params.set("address", address);
    params.set("limit", String(limit));
    return this.fetchApi(`/trades?${params}`);
  }

  async getTradeStats(): Promise<ApiResponse<TradeStats>> {
    return this.fetchApi<TradeStats>("/trades/stats");
  }

  async getAgentLogs(agent?: string, limit = 50): Promise<ApiResponse<AgentLog[]>> {
    const params = new URLSearchParams();
    if (agent) params.set("agent", agent);
    params.set("limit", String(limit));
    return this.fetchApi(`/agent/logs?${params}`);
  }

  async getRiskStatus(): Promise<ApiResponse<RiskStatus>> {
    return this.fetchApi<RiskStatus>("/risk/status");
  }

  async runRiskCheck(address: string, confidence = 0.7): Promise<ApiResponse<RiskCheckResult>> {
    return this.fetchApi<RiskCheckResult>(`/risk/check?address=${address}&confidence=${confidence}`, {
      method: "POST",
    });
  }

  async resetCircuitBreaker(): Promise<ApiResponse<{ ok: boolean; message: string }>> {
    return this.fetchApi("/risk/circuit-breaker/reset", { method: "POST" });
  }

  async getSodexQuote(symbol: string): Promise<ApiResponse<SodexQuote>> {
    return this.fetchApi<SodexQuote>(`/sodex/quote?symbol=${encodeURIComponent(symbol)}`);
  }

  async getSodexSymbols(): Promise<ApiResponse<unknown[]>> {
    return this.fetchApi("/sodex/symbols");
  }

  async getSodexStatus(): Promise<ApiResponse<SodexStatus>> {
    return this.fetchApi<SodexStatus>("/sodex/status");
  }

  async getSectorsIntel(): Promise<ApiResponse<{ sectors: SectorIntel[]; count: number; generated_at: string }>> {
    return this.fetchApi("/sectors/intel");
  }

  async getSectorBasket(ticker: string): Promise<ApiResponse<{ ticker: string; assets: unknown[] }>> {
    return this.fetchApi(`/sectors/intel/${ticker}/basket`);
  }

  async getSnapshots(address: string, limit = 30): Promise<ApiResponse<unknown[]>> {
    return this.fetchApi(`/snapshots/${address}?limit=${limit}`);
  }

  async configureWallet(
    address: string,
    riskLevel = "medium",
    autoRebalance = false,
    rebalanceThreshold = 0.7,
  ): Promise<ApiResponse<{ ok: boolean }>> {
    return this.fetchApi("/wallet/config", {
      method: "POST",
      body: JSON.stringify({ address, riskLevel, autoRebalance, rebalanceThreshold }),
    });
  }

  async getWalletConfig(address: string): Promise<ApiResponse<unknown>> {
    return this.fetchApi(`/wallet/${address}`);
  }

  async getServiceInfo(): Promise<ApiResponse<unknown>> {
    return this.fetchApi("/");
  }
}

export const api = new ApiService();
