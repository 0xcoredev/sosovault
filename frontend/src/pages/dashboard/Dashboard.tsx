import { useState, useEffect, useMemo } from "react";
import { useWallet } from "@/hooks/use-wallet";
import { TopNav } from "@/components/dashboard/TopNav";
import { DashboardSidebar } from "@/components/dashboard/Sidebar";
import { PortfolioCard } from "@/components/dashboard/PortfolioCard";
import { RiskProfileSelector } from "@/components/dashboard/RiskProfileSelector";
import { AIStrategyCard } from "@/components/dashboard/AIStrategyCard";
import { ExecutionPanel } from "@/components/dashboard/ExecutionPanel";
import { ActivityLog } from "@/components/dashboard/ActivityLog";
import { EmptyState } from "@/components/dashboard/EmptyState";
import { PerformanceChart } from "./PerformanceChart";
import {
  RiskLevel,
  portfolioData,
  performanceData,
  type StrategyRecommendation,
  type PortfolioSnapshot,
} from "@/lib/mock-data";
import { api, type ActivityItem, type PerformancePoint } from "@/lib/api";

export default function Dashboard() {
  const wallet = useWallet();
  const [riskLevel, setRiskLevel] = useState<RiskLevel>("medium");
  const [loading, setLoading] = useState(true);
  const [portfolio, setPortfolio] = useState<PortfolioSnapshot | null>(null);
  const [performance, setPerformance] = useState<PerformancePoint[]>([]);
  const [activity, setActivity] = useState<ActivityItem[] | null>(null);
  const [strategy, setStrategy] = useState<StrategyRecommendation | null>(null);
  const [llmActive, setLlmActive] = useState(false);
  const [strategyLoading, setStrategyLoading] = useState(false);

  // Fetch portfolio + performance + activity when wallet connects.
  useEffect(() => {
    if (!wallet.connected || !wallet.address) {
      setPortfolio(null);
      setPerformance([]);
      setActivity(null);
      return;
    }

    setLoading(true);
    (async () => {
      const [pRes, perfRes, actRes] = await Promise.all([
        api.getPortfolio(wallet.address!),
        api.getPerformance(wallet.address!),
        api.getActivity(wallet.address!),
      ]);
      setPortfolio(pRes.success && pRes.data ? pRes.data : portfolioData);
      setPerformance(perfRes.success && perfRes.data ? perfRes.data : performanceData);
      setActivity(actRes.success && actRes.data ? actRes.data : null);
      setLoading(false);
    })();
  }, [wallet.connected, wallet.address]);

  // Fetch strategy whenever risk level changes (and wallet is connected).
  useEffect(() => {
    if (!wallet.connected || !wallet.address) {
      setStrategy(null);
      return;
    }
    setStrategyLoading(true);
    (async () => {
      const res = await api.getStrategy({
        address: wallet.address!,
        riskLevel,
      });
      if (res.success && res.data) {
        setStrategy(res.data.strategy);
        setLlmActive(Boolean(res.data.llm) && res.data.llm.provider !== "templated");
      } else {
        setStrategy(null);
        setLlmActive(false);
      }
      setStrategyLoading(false);
    })();
  }, [wallet.connected, wallet.address, riskLevel]);

  const chartData = useMemo(
    () => (performance.length > 0 ? performance : performanceData),
    [performance],
  );

  return (
    <div className="min-h-screen bg-background">
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -top-32 -right-32 h-64 w-64 rounded-full bg-primary/5 blur-[100px]" />
        <div className="absolute -bottom-32 -left-32 h-64 w-64 rounded-full bg-accent/5 blur-[100px]" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 h-96 w-96 rounded-full bg-primary/[0.02] blur-[150px]" />
      </div>

      <div className="relative z-10">
        <TopNav
          connected={wallet.connected}
          connecting={wallet.connecting}
          address={wallet.shortenedAddress}
          network={wallet.network}
          balance={wallet.balance}
          onConnect={wallet.connect}
          onDisconnect={wallet.disconnect}
        />

        <div className="flex">
          <DashboardSidebar />

          <main className="flex-1 p-3 lg:p-5 max-w-[1400px] mx-auto w-full">
            {!wallet.connected ? (
              <EmptyState type="no-wallet" onAction={wallet.connect} />
            ) : (
              <div className="space-y-6">
                <PerformanceChart data={chartData} loading={loading} />

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
                  <PortfolioCard
                    loading={loading}
                    portfolio={portfolio}
                    performance={performance}
                  />
                  <RiskProfileSelector
                    selected={riskLevel}
                    onSelect={setRiskLevel}
                    loading={loading}
                  />
                  <AIStrategyCard
                    loading={strategyLoading || loading}
                    strategy={strategy}
                    llmActive={llmActive}
                  />
                  <ExecutionPanel
                    loading={loading}
                    walletConnected={wallet.connected}
                    strategy={strategy}
                  />
                  <ActivityLog loading={loading} activity={activity} />
                </div>
              </div>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}
