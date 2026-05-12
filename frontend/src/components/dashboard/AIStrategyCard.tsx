import { motion, AnimatePresence } from "framer-motion";
import { Brain, ChevronDown, Sparkles } from "lucide-react";
import { useState } from "react";
import type { StrategyRecommendation } from "@/lib/mock-data";
import { aiStrategy } from "@/lib/mock-data";
import { GlassCard } from "./GlassCard";
import { SkeletonBlock } from "./SkeletonBlock";

interface AIStrategyCardProps {
  loading?: boolean;
  strategy?: StrategyRecommendation | null;
  /** Whether the AI reasoning engine produced the prose (vs the heuristic fallback). */
  llmActive?: boolean;
}

export function AIStrategyCard({ loading, strategy, llmActive }: AIStrategyCardProps) {
  const [expanded, setExpanded] = useState(false);
  const data = strategy ?? aiStrategy;

  if (loading) {
    return (
      <GlassCard className="col-span-full lg:col-span-2">
        <SkeletonBlock className="h-4 w-44 mb-3" />
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <SkeletonBlock key={i} className="h-10 w-full" />
          ))}
        </div>
      </GlassCard>
    );
  }

  return (
    <GlassCard delay={0.2} className="col-span-full lg:col-span-2">
      <div className="mb-3 flex items-center gap-2">
        <div className="flex h-6 w-6 items-center justify-center rounded-md bg-accent/20">
          <Brain className="h-3.5 w-3.5 text-accent" />
        </div>
        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          SoSoValue Basket Allocation
        </h3>
        <Sparkles className="h-3 w-3 text-accent animate-pulse" />
        {llmActive && (
          <span className="ml-auto text-[9px] text-success font-mono uppercase">
            AI · live
          </span>
        )}
      </div>

      <div className="space-y-2">
        {data.allocations.map((alloc, i) => (
          <motion.div
            key={alloc.symbol + i}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.08 * i }}
            className="flex items-center gap-3 rounded-lg bg-muted/15 px-3 py-2 hover:bg-muted/25 transition-colors"
          >
            <div className="relative h-9 w-9 flex items-center justify-center shrink-0">
              <svg className="h-9 w-9 -rotate-90">
                <circle cx="18" cy="18" r="14" fill="none" stroke="hsl(var(--muted))" strokeWidth="2.5" />
                <motion.circle
                  cx="18"
                  cy="18"
                  r="14"
                  fill="none"
                  stroke={alloc.color || "hsl(var(--primary))"}
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeDasharray={`${alloc.percentage * 0.88} 100`}
                  initial={{ strokeDasharray: "0 100" }}
                  animate={{ strokeDasharray: `${alloc.percentage * 0.88} 100` }}
                  transition={{ delay: 0.15 * i, duration: 0.8 }}
                />
              </svg>
              <span className="absolute text-[9px] font-bold">{alloc.percentage}%</span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate leading-tight">{alloc.name}</p>
              <p className="text-[10px] text-muted-foreground">{alloc.type}</p>
            </div>
            {alloc.oneMonthRoi !== undefined && (
              <span
                className={`text-[10px] font-mono shrink-0 ${
                  alloc.oneMonthRoi >= 0 ? "text-success" : "text-destructive"
                }`}
              >
                {alloc.oneMonthRoi >= 0 ? "+" : ""}
                {(alloc.oneMonthRoi * 100).toFixed(1)}% 1m
              </span>
            )}
          </motion.div>
        ))}
      </div>

      <motion.button
        onClick={() => setExpanded(!expanded)}
        whileTap={{ scale: 0.98 }}
        className="mt-3 flex w-full items-center gap-2 rounded-lg bg-muted/15 px-3 py-1.5 text-[11px] text-muted-foreground transition-colors hover:bg-muted/30 hover:text-foreground"
      >
        <span>Why this basket?</span>
        <motion.div animate={{ rotate: expanded ? 180 : 0 }} transition={{ duration: 0.2 }}>
          <ChevronDown className="h-3 w-3" />
        </motion.div>
      </motion.button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="overflow-hidden"
          >
            <div className="mt-2 space-y-2 rounded-lg bg-muted/10 p-3">
              {Object.entries(data.reasoning).map(([key, value]) => (
                <div key={key}>
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-primary mb-0.5">
                    {key}
                  </p>
                  <p className="text-[11px] text-muted-foreground leading-relaxed">{value}</p>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </GlassCard>
  );
}
