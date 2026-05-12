import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  TrendingUp,
  TrendingDown,
  Minus,
  Zap,
  Newspaper,
  RefreshCcw,
  Loader2,
  ExternalLink,
  Radio,
} from "lucide-react";
import { TopNav } from "@/components/dashboard/TopNav";
import { DashboardSidebar } from "@/components/dashboard/Sidebar";
import { GlassCard } from "@/components/dashboard/GlassCard";
import { useWallet } from "@/hooks/use-wallet";
import { api, type SignalsFeed, type SignalItem } from "@/lib/api";
import { toast } from "sonner";

const KIND_LABELS: Record<string, string> = {
  etf_flow: "ETF Flow",
  index_momentum: "Index Momentum",
  news_sentiment: "News Sentiment",
};

const KIND_ICONS: Record<string, typeof TrendingUp> = {
  etf_flow: TrendingUp,
  index_momentum: Zap,
  news_sentiment: Newspaper,
};

function directionStyles(direction: string) {
  if (direction === "bullish") {
    return {
      Icon: TrendingUp,
      className: "text-emerald-500",
      pillClass: "bg-emerald-500/15 text-emerald-500 border-emerald-500/30",
    };
  }
  if (direction === "bearish") {
    return {
      Icon: TrendingDown,
      className: "text-red-500",
      pillClass: "bg-red-500/15 text-red-500 border-red-500/30",
    };
  }
  return {
    Icon: Minus,
    className: "text-muted-foreground",
    pillClass: "bg-muted/30 text-muted-foreground border-muted",
  };
}

function relativeTime(ts: number | string): string {
  const time = typeof ts === "number" ? ts : Date.parse(ts);
  if (!time) return "";
  const diff = Date.now() - time;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export default function Signals() {
  const wallet = useWallet();
  const [feed, setFeed] = useState<SignalsFeed | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchFeed = async () => {
    setRefreshing(true);
    const res = await api.getSignals();
    if (res.success && res.data) setFeed(res.data);
    setRefreshing(false);
    setLoading(false);
  };

  useEffect(() => {
    fetchFeed();
    const id = setInterval(fetchFeed, 60000);
    return () => clearInterval(id);
  }, []);

  const applySignal = (signal: SignalItem) => {
    toast.success("Suggestion captured", {
      description: `${signal.suggested_action} — open the Strategy page to apply it.`,
    });
  };

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

          <main className="flex-1 p-3 lg:p-5 max-w-[1400px] mx-auto w-full space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div>
                <h1 className="text-2xl font-bold flex items-center gap-2">
                  <Radio className="h-6 w-6 text-primary" />
                  Live Signals
                </h1>
                <p className="text-muted-foreground">
                  ETF flows, SoSoValue index momentum, and news sentiment turned into
                  one-click rebalance suggestions.
                </p>
              </div>
              <button
                onClick={fetchFeed}
                disabled={refreshing}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-muted/50 hover:bg-muted/70 transition disabled:opacity-50"
              >
                {refreshing ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCcw className="h-4 w-4" />
                )}
                <span className="text-sm">Refresh</span>
              </button>
            </div>

            {loading ? (
              <div className="flex items-center justify-center py-32">
                <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
              </div>
            ) : !feed || feed.signals.length === 0 ? (
              <GlassCard className="p-10 text-center">
                <p className="text-muted-foreground">
                  No live signals right now. (Backend may be starting up — give it a few
                  seconds and refresh.)
                </p>
              </GlassCard>
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2 space-y-4">
                  {feed.signals.map((signal, i) => {
                    const KindIcon = KIND_ICONS[signal.kind] || Zap;
                    const dir = directionStyles(signal.direction);

                    return (
                      <motion.div
                        key={signal.id}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: i * 0.05 }}
                      >
                        <GlassCard className="p-5">
                          <div className="flex items-start gap-4">
                            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/15 shrink-0">
                              <KindIcon className="h-5 w-5 text-primary" />
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex flex-wrap items-center gap-2 mb-1">
                                <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">
                                  {KIND_LABELS[signal.kind] || signal.kind}
                                </span>
                                <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
                                  · {signal.asset}
                                </span>
                                <span
                                  className={`px-2 py-0.5 rounded-full text-[10px] font-medium border ${dir.pillClass} flex items-center gap-1`}
                                >
                                  <dir.Icon className="h-3 w-3" />
                                  {signal.direction}
                                </span>
                                <span className="text-[10px] text-muted-foreground ml-auto">
                                  conf {(signal.confidence * 100).toFixed(0)}%
                                </span>
                              </div>
                              <h3 className="font-semibold mb-1">{signal.headline}</h3>
                              <p className="text-sm text-muted-foreground mb-3">
                                {signal.detail}
                              </p>
                              <div className="flex flex-wrap items-center gap-3">
                                <span className="text-xs font-mono bg-muted/40 rounded px-2 py-1">
                                  {signal.suggested_action}
                                </span>
                                <button
                                  onClick={() => applySignal(signal)}
                                  className="text-xs px-3 py-1 rounded gradient-primary text-primary-foreground"
                                >
                                  Apply to basket
                                </button>
                                <span className="text-[10px] text-muted-foreground ml-auto">
                                  {relativeTime(signal.generated_at)}
                                </span>
                              </div>
                            </div>
                          </div>
                        </GlassCard>
                      </motion.div>
                    );
                  })}
                </div>

                <div className="space-y-4">
                  <GlassCard className="p-5">
                    <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                      <Newspaper className="h-4 w-4 text-primary" />
                      SoSoValue Newsroom
                    </h3>
                    <div className="space-y-3">
                      {feed.news.length === 0 ? (
                        <p className="text-xs text-muted-foreground">
                          No headlines from the SoSoValue feed right now.
                        </p>
                      ) : (
                        feed.news.map((n) => {
                          const dir = directionStyles((n as any).verdict || "neutral");
                          return (
                            <div
                              key={n.id}
                              className="flex flex-col gap-1 border-b border-border/30 pb-2 last:border-b-0 last:pb-0"
                            >
                              <div className="flex items-start gap-2">
                                <span
                                  className={`mt-1 h-1.5 w-1.5 rounded-full ${
                                    dir.className.replace("text-", "bg-")
                                  } shrink-0`}
                                />
                                <p className="text-xs leading-snug">{n.title}</p>
                              </div>
                              <div className="flex items-center justify-between text-[10px] text-muted-foreground pl-3">
                                <span>{relativeTime(n.release_time)}</span>
                                {n.source_link && (
                                  <a
                                    href={n.source_link}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="hover:text-primary flex items-center gap-1"
                                  >
                                    source <ExternalLink className="h-2.5 w-2.5" />
                                  </a>
                                )}
                              </div>
                            </div>
                          );
                        })
                      )}
                    </div>
                  </GlassCard>

                  <GlassCard className="p-5 text-xs text-muted-foreground space-y-2">
                    <p className="font-semibold text-foreground text-sm">How signals work</p>
                    <p>
                      Every minute the backend pulls{" "}
                      <span className="font-mono text-foreground">/etfs/IBIT/market-snapshot</span>
                      , <span className="font-mono text-foreground">/indices/&#123;t&#125;/market-snapshot</span>
                      , and <span className="font-mono text-foreground">/news</span> from the
                      SoSoValue OpenAPI.
                    </p>
                    <p>
                      Each signal comes with a deterministic suggested basket adjustment so the
                      "insight → action" loop is one click away.
                    </p>
                  </GlassCard>
                </div>
              </div>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}
