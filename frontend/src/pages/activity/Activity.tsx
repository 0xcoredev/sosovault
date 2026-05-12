import { useState, useEffect } from "react";
import { useWallet } from "@/hooks/use-wallet";
import { TopNav } from "@/components/dashboard/TopNav";
import { DashboardSidebar } from "@/components/dashboard/Sidebar";
import { EmptyState } from "@/components/dashboard/EmptyState";
import { GlassCard } from "@/components/dashboard/GlassCard";
import { activityLog } from "@/lib/mock-data";
import { api, type ActivityItem } from "@/lib/api";
import {
  ArrowUpRight,
  ArrowDownLeft,
  RefreshCcw,
  BrainCircuit,
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
} from "lucide-react";

const activityIcons: Record<string, typeof ArrowDownLeft> = {
  deposit: ArrowDownLeft,
  withdraw: ArrowUpRight,
  rebalance: RefreshCcw,
  strategy: BrainCircuit,
};

const activityColors: Record<string, string> = {
  deposit: "text-blue-500 bg-blue-500/20",
  withdraw: "text-purple-500 bg-purple-500/20",
  rebalance: "text-amber-500 bg-amber-500/20",
  strategy: "text-emerald-500 bg-emerald-500/20",
};

const statusIcons: Record<string, typeof CheckCircle2> = {
  success: CheckCircle2,
  failed: XCircle,
  pending: Clock,
};

const statusColors: Record<string, string> = {
  success: "text-emerald-500",
  failed: "text-red-500",
  pending: "text-amber-500",
};

export default function Activity() {
  const wallet = useWallet();
  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "deposit" | "withdraw" | "strategy" | "rebalance">("all");

  useEffect(() => {
    if (!wallet.connected || !wallet.address) {
      setActivities([]);
      return;
    }
    setLoading(true);
    (async () => {
      const res = await api.getActivity(wallet.address!);
      if (res.success && res.data) {
        setActivities(res.data);
      } else {
        setActivities(activityLog as unknown as ActivityItem[]);
      }
      setLoading(false);
    })();
  }, [wallet.connected, wallet.address]);

  const filteredActivities =
    filter === "all" ? activities : activities.filter((a) => a.type === filter);

  const stats = {
    total: activities.length,
    successful: activities.filter((a) => a.status === "success").length,
    pending: activities.filter((a) => a.status === "pending").length,
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

          <main className="flex-1 p-3 lg:p-5 max-w-[1400px] mx-auto w-full">
            {!wallet.connected ? (
              <EmptyState type="no-wallet" onAction={wallet.connect} />
            ) : (
              <div className="space-y-6">
                <div>
                  <h1 className="text-2xl font-bold text-foreground">Vault Activity</h1>
                  <p className="text-muted-foreground">
                    Deposits, basket rebalances, and strategy generations.
                  </p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <GlassCard className="p-4">
                    <p className="text-sm text-muted-foreground">Total Events</p>
                    <p className="text-2xl font-bold">{stats.total}</p>
                  </GlassCard>
                  <GlassCard className="p-4">
                    <p className="text-sm text-muted-foreground">Successful</p>
                    <p className="text-2xl font-bold text-emerald-500">{stats.successful}</p>
                  </GlassCard>
                  <GlassCard className="p-4">
                    <p className="text-sm text-muted-foreground">Pending</p>
                    <p className="text-2xl font-bold text-amber-500">{stats.pending}</p>
                  </GlassCard>
                </div>

                <GlassCard className="p-6">
                  <div className="flex flex-wrap gap-2 mb-6">
                    {(["all", "deposit", "withdraw", "strategy", "rebalance"] as const).map((type) => (
                      <button
                        key={type}
                        onClick={() => setFilter(type)}
                        className={`px-4 py-2 rounded-lg font-medium transition-all capitalize ${
                          filter === type
                            ? "bg-primary text-primary-foreground"
                            : "bg-muted text-muted-foreground hover:bg-muted/80"
                        }`}
                      >
                        {type === "all" ? "All" : type}
                      </button>
                    ))}
                  </div>

                  {loading ? (
                    <div className="flex items-center justify-center h-64">
                      <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
                    </div>
                  ) : filteredActivities.length === 0 ? (
                    <div className="text-center py-12">
                      <p className="text-muted-foreground">No activity yet</p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {filteredActivities.map((activity) => {
                        const Icon = activityIcons[activity.type] || RefreshCcw;
                        const StatusIcon = statusIcons[activity.status] || Clock;

                        return (
                          <div
                            key={activity.id}
                            className="flex items-center justify-between p-4 bg-muted/50 rounded-lg hover:bg-muted/70 transition-colors"
                          >
                            <div className="flex items-center gap-4">
                              <div className={`p-2 rounded-lg ${activityColors[activity.type] || ""}`}>
                                <Icon className="w-5 h-5" />
                              </div>
                              <div>
                                <p className="font-medium">{activity.description}</p>
                                <p className="text-sm text-muted-foreground">{activity.timestamp}</p>
                              </div>
                            </div>

                            <div className="flex items-center gap-3">
                              <div className={`flex items-center gap-1 ${statusColors[activity.status]}`}>
                                <StatusIcon className="w-4 h-4" />
                                <span className="text-sm capitalize">{activity.status}</span>
                              </div>

                              {activity.txHash && (
                                <span className="text-xs font-mono text-muted-foreground">
                                  {activity.txHash.slice(0, 8)}...{activity.txHash.slice(-6)}
                                </span>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </GlassCard>
              </div>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}
