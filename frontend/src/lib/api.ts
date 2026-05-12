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
    news_count: number;
    last_etf_inflow?: number;
  };
  llm: {
    provider: string;
    model: string;
    latency_ms: number;
  };
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
  /** "etf_flow" | "index_momentum" | "news_sentiment" */
  kind: string;
  /** "bullish" | "bearish" | "neutral" */
  direction: string;
  asset: string;
  headline: string;
  detail: string;
  /** 0..1 confidence */
  confidence: number;
  /** Suggested basket adjustment, e.g. "+5% ssimag7 / -5% USDC". */
  suggested_action: string;
  generated_at: string;
}

export interface SignalsFeed {
  signals: SignalItem[];
  news: NewsItem[];
  generated_at: string;
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
  ): Promise<ApiResponse<{ txHash: string; sodex_route: SodexQuote[] }>> {
    return this.fetchApi("/strategy/execute", {
      method: "POST",
      body: JSON.stringify({ address, allocations, symbols }),
    });
  }

  async getActivity(address: string, limit = 50): Promise<ApiResponse<ActivityItem[]>> {
    return this.fetchApi<ActivityItem[]>(`/activity/${address}?limit=${limit}`);
  }

  async getSignals(): Promise<ApiResponse<SignalsFeed>> {
    return this.fetchApi<SignalsFeed>("/signals/feed");
  }

  async getSodexQuote(symbol: string): Promise<ApiResponse<SodexQuote>> {
    return this.fetchApi<SodexQuote>(`/sodex/quote?symbol=${encodeURIComponent(symbol)}`);
  }
}

export const api = new ApiService();
