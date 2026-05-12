import { motion } from "framer-motion";
import { ArrowDownCircle, Brain, RefreshCw, ArrowUpCircle, CheckCircle2, Clock } from "lucide-react";
import type { ActivityItem } from "@/lib/api";
import { activityLog } from "@/lib/mock-data";
import { GlassCard } from "./GlassCard";
import { SkeletonBlock } from "./SkeletonBlock";

const typeIcons: Record<string, typeof ArrowDownCircle> = {
  deposit: ArrowDownCircle,
  withdraw: ArrowUpCircle,
  strategy: Brain,
  rebalance: RefreshCw,
};

interface ActivityLogProps {
  loading?: boolean;
  activity?: ActivityItem[] | null;
}

export function ActivityLog({ loading, activity }: ActivityLogProps) {
  const items = activity && activity.length > 0 ? activity : activityLog;

  if (loading) {
    return (
      <GlassCard className="col-span-full">
        <SkeletonBlock className="h-4 w-32 mb-3" />
        <div className="space-y-2">
          {[1, 2, 3, 4].map((i) => (
            <SkeletonBlock key={i} className="h-10 w-full" />
          ))}
        </div>
      </GlassCard>
    );
  }

  return (
    <GlassCard delay={0.3} className="col-span-full">
      <h3 className="mb-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
        Recent Activity
      </h3>
      <div className="divide-y divide-border/30">
        {items.map((item, i) => {
          const Icon = typeIcons[item.type] || RefreshCw;
          return (
            <motion.div
              key={item.id}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.04 * i }}
              className="flex items-center gap-3 py-2.5 first:pt-0 last:pb-0 transition-colors hover:bg-muted/10 -mx-2 px-2 rounded-md"
            >
              <div className="flex h-7 w-7 items-center justify-center rounded-md bg-muted/30 shrink-0">
                <Icon className="h-3.5 w-3.5 text-muted-foreground" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm truncate">{item.description}</p>
                <p className="text-[10px] text-muted-foreground font-mono">{item.timestamp}</p>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                {item.status === "success" ? (
                  <CheckCircle2 className="h-3.5 w-3.5 text-success" />
                ) : (
                  <Clock className="h-3.5 w-3.5 text-warning animate-pulse" />
                )}
                <span
                  className={`text-[10px] font-medium uppercase tracking-wide ${
                    item.status === "success" ? "text-success" : "text-warning"
                  }`}
                >
                  {item.status}
                </span>
              </div>
            </motion.div>
          );
        })}
      </div>
    </GlassCard>
  );
}
