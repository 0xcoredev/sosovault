import { useState, useEffect } from "react";
import { useWallet } from "@/hooks/use-wallet";
import { TopNav } from "@/components/dashboard/TopNav";
import { DashboardSidebar } from "@/components/dashboard/Sidebar";
import { EmptyState } from "@/components/dashboard/EmptyState";
import { GlassCard } from "@/components/dashboard/GlassCard";
import {
  RiskLevel,
  strategyByRisk,
  type StrategyRecommendation,
  riskProfiles,
} from "@/lib/mock-data";
import { api, type StrategyResponse } from "@/lib/api";
import {
  TrendingUp,
  Shield,
  Zap,
  DollarSign,
  Loader2,
  CheckCircle2,
  Sparkles,
} from "lucide-react";

export default function Strategy() {
  const wallet = useWallet();
  const [activeRiskLevel, setActiveRiskLevel] = useState<RiskLevel>("medium");
  const [strategy, setStrategy] = useState<StrategyRecommendation | null>(null);
  const [meta, setMeta] = useState<StrategyResponse["sosovalue"] | null>(null);
  const [llm, setLlm] = useState<StrategyResponse["llm"] | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    if (!wallet.connected || !wallet.address) {
      setStrategy(null);
      setMeta(null);
      setLlm(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    (async () => {
      const res = await api.getStrategy({
        address: wallet.address!,
        riskLevel: activeRiskLevel,
      });
      if (cancelled) return;
      if (res.success && res.data) {
        setStrategy(res.data.strategy);
        setMeta(res.data.sosovalue);
        setLlm(res.data.llm);
      } else {
        setStrategy(strategyByRisk[activeRiskLevel]);
        setMeta(null);
        setLlm(null);
      }
      setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [wallet.connected, wallet.address, activeRiskLevel]);

  const generateNewStrategy = async () => {
    if (!wallet.address) return;
    setGenerating(true);
    const res = await api.getStrategy({
      address: wallet.address,
      riskLevel: activeRiskLevel,
    });
    if (res.success && res.data) {
      setStrategy(res.data.strategy);
      setMeta(res.data.sosovalue);
      setLlm(res.data.llm);
    }
    setGenerating(false);
  };

  const currentProfile = riskProfiles[activeRiskLevel];

  return (
    <div className="min-h-screen bg-background">
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -top-32 -right-32 h-64 w-64 rounded-full bg-primary/5 blur-[100px]" />
        <div className="absolute -bottom-32 -left-32 h-64 w-64 rounded-full bg-accent/5 blur-[100px]" />
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
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                  <div>
                    <h1 className="text-2xl font-bold text-foreground">SoSoValue Basket</h1>
                    <p className="text-muted-foreground">
                      Risk-tiered index basket built from live SoSoValue data
                    </p>
                    {meta && (
                      <p className="text-[11px] text-muted-foreground mt-1 font-mono">
                        indices: {meta.indices_used.join(", ")}
                        {meta.last_etf_inflow !== null && meta.last_etf_inflow !== undefined && (
                          <> · IBIT inflow: {meta.last_etf_inflow.toLocaleString()} USD</>
                        )}
                      </p>
                    )}
                  </div>

                  <div className="flex gap-2">
                    {(["low", "medium", "high"] as RiskLevel[]).map((level) => (
                      <button
                        key={level}
                        onClick={() => setActiveRiskLevel(level)}
                        className={`px-4 py-2 rounded-lg font-medium transition-all ${
                          activeRiskLevel === level
                            ? "bg-primary text-primary-foreground"
                            : "bg-muted text-muted-foreground hover:bg-muted/80"
                        }`}
                      >
                        {riskProfiles[level].label}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                  <GlassCard className="lg:col-span-2 p-6 space-y-6">
                    {loading ? (
                      <div className="flex items-center justify-center h-64">
                        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
                      </div>
                    ) : strategy ? (
                      <>
                        <div>
                          <h3 className="text-lg font-semibold mb-2">Basket Summary</h3>
                          <p className="text-muted-foreground">{strategy.summary}</p>
                        </div>

                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                          <div className="bg-muted/50 rounded-lg p-4">
                            <div className="flex items-center gap-2 text-muted-foreground mb-1">
                              <TrendingUp className="w-4 h-4" />
                              <span className="text-xs">Est. Yield</span>
                            </div>
                            <p className="text-xl font-bold text-emerald-500">
                              {(strategy.estimatedYield * 100).toFixed(1)}%
                            </p>
                          </div>
                          <div className="bg-muted/50 rounded-lg p-4">
                            <div className="flex items-center gap-2 text-muted-foreground mb-1">
                              <DollarSign className="w-4 h-4" />
                              <span className="text-xs">Est. Gas</span>
                            </div>
                            <p className="text-xl font-bold">
                              {strategy.estimatedGas.toFixed(4)} ETH
                            </p>
                          </div>
                          <div className="bg-muted/50 rounded-lg p-4">
                            <div className="flex items-center gap-2 text-muted-foreground mb-1">
                              <Shield className="w-4 h-4" />
                              <span className="text-xs">Risk Tier</span>
                            </div>
                            <p className="text-xl font-bold capitalize">{activeRiskLevel}</p>
                          </div>
                          <div className="bg-muted/50 rounded-lg p-4">
                            <div className="flex items-center gap-2 text-muted-foreground mb-1">
                              <Zap className="w-4 h-4" />
                              <span className="text-xs">AI Engine</span>
                            </div>
                            <p className="text-xs font-bold uppercase">
                              {llm && llm.provider !== "templated" ? "Active" : "Heuristic"}
                            </p>
                            {llm?.latency_ms ? (
                              <p className="text-[10px] text-muted-foreground font-mono">
                                {llm.latency_ms}ms
                              </p>
                            ) : null}
                          </div>
                        </div>

                        <div>
                          <h4 className="font-semibold mb-3">Recommended Allocation</h4>
                          <div className="space-y-3">
                            {strategy.allocations.map((alloc, idx) => (
                              <div
                                key={idx}
                                className="flex items-center justify-between p-3 bg-muted/50 rounded-lg"
                              >
                                <div className="flex items-center gap-3">
                                  <div
                                    className="h-3 w-3 rounded-full"
                                    style={{ backgroundColor: alloc.color }}
                                  />
                                  <div>
                                    <p className="font-medium">{alloc.name}</p>
                                    <p className="text-sm text-muted-foreground uppercase font-mono text-[10px]">
                                      {alloc.symbol} · {alloc.type}
                                    </p>
                                  </div>
                                </div>
                                <div className="text-right">
                                  <p className="font-semibold">{alloc.percentage}%</p>
                                  {alloc.oneMonthRoi !== undefined ? (
                                    <p
                                      className={`text-sm ${
                                        alloc.oneMonthRoi >= 0 ? "text-emerald-500" : "text-red-500"
                                      }`}
                                    >
                                      {alloc.oneMonthRoi >= 0 ? "+" : ""}
                                      {(alloc.oneMonthRoi * 100).toFixed(1)}% 1m
                                    </p>
                                  ) : null}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>

                        <div>
                          <h4 className="font-semibold mb-3">Execution Plan</h4>
                          <div className="space-y-2">
                            {strategy.executionSteps.map((step, idx) => (
                              <div key={idx} className="flex items-start gap-3">
                                <div className="flex-shrink-0 w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center text-xs font-medium">
                                  {idx + 1}
                                </div>
                                <p className="text-sm text-muted-foreground pt-0.5">{step}</p>
                              </div>
                            ))}
                          </div>
                        </div>

                        <button
                          onClick={generateNewStrategy}
                          disabled={generating}
                          className="w-full py-3 bg-primary text-primary-foreground rounded-lg font-medium hover:bg-primary/90 transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
                        >
                          {generating ? (
                            <>
                              <Loader2 className="w-4 h-4 animate-spin" />
                              Regenerating with live data...
                            </>
                          ) : (
                            <>
                              <Sparkles className="w-4 h-4" />
                              Regenerate Basket
                            </>
                          )}
                        </button>
                      </>
                    ) : null}
                  </GlassCard>

                  <div className="space-y-6">
                    <GlassCard className="p-6">
                      <h3 className="font-semibold mb-4">Risk Profile</h3>
                      <div
                        className={`px-4 py-3 rounded-lg mb-4 ${
                          activeRiskLevel === "low"
                            ? "bg-emerald-500/20 text-emerald-500"
                            : activeRiskLevel === "medium"
                            ? "bg-amber-500/20 text-amber-500"
                            : "bg-red-500/20 text-red-500"
                        }`}
                      >
                        <p className="font-semibold">{currentProfile.label}</p>
                        <p className="text-sm opacity-80">{currentProfile.expectedApy} APY</p>
                      </div>
                      <p className="text-sm text-muted-foreground">{currentProfile.description}</p>
                    </GlassCard>

                    <GlassCard className="p-6">
                      <h3 className="font-semibold mb-4">Constraints</h3>
                      <ul className="space-y-2">
                        {strategy?.constraints.map((constraint, idx) => (
                          <li key={idx} className="flex items-start gap-2 text-sm">
                            <CheckCircle2 className="w-4 h-4 text-emerald-500 mt-0.5 flex-shrink-0" />
                            <span className="text-muted-foreground">{constraint}</span>
                          </li>
                        ))}
                      </ul>
                    </GlassCard>

                    <GlassCard className="p-6">
                      <h3 className="font-semibold mb-4">AI Reasoning</h3>
                      <div className="space-y-4 text-sm">
                        <div>
                          <p className="text-muted-foreground mb-1 text-[10px] uppercase tracking-wider">
                            Volatility
                          </p>
                          <p className="text-foreground">{strategy?.reasoning.volatility}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground mb-1 text-[10px] uppercase tracking-wider">
                            Yield
                          </p>
                          <p className="text-foreground">{strategy?.reasoning.yield}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground mb-1 text-[10px] uppercase tracking-wider">
                            Risk
                          </p>
                          <p className="text-foreground">{strategy?.reasoning.risk}</p>
                        </div>
                      </div>
                    </GlassCard>
                  </div>
                </div>
              </div>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}
