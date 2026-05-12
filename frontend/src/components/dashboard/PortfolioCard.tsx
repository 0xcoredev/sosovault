import { motion } from "framer-motion";
import { TrendingUp, TrendingDown } from "lucide-react";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import type { PortfolioSnapshot } from "@/lib/mock-data";
import { portfolioData, performanceData } from "@/lib/mock-data";
import { GlassCard } from "./GlassCard";
import { SkeletonBlock } from "./SkeletonBlock";

interface PortfolioCardProps {
  loading?: boolean;
  portfolio?: PortfolioSnapshot | null;
  performance?: { date: string; value: number }[];
}

export function PortfolioCard({ loading, portfolio, performance }: PortfolioCardProps) {
  const data = portfolio ?? portfolioData;
  const perf = performance && performance.length > 0 ? performance : performanceData;
  const isPositive = data.change24h >= 0;

  if (loading) {
    return (
      <GlassCard className="col-span-full lg:col-span-2">
        <SkeletonBlock className="h-5 w-40 mb-3" />
        <SkeletonBlock className="h-8 w-48 mb-1" />
        <SkeletonBlock className="h-4 w-24 mb-4" />
        <SkeletonBlock className="h-28 w-full mb-3" />
        <div className="grid grid-cols-3 gap-2">
          {[1, 2, 3].map((i) => (
            <SkeletonBlock key={i} className="h-14" />
          ))}
        </div>
      </GlassCard>
    );
  }

  return (
    <GlassCard className="col-span-full lg:col-span-2">
      <div className="mb-3 flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">
            Vault Value
          </p>
          <motion.h2
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-2xl font-bold tracking-tight"
          >
            <span className="glow-text">${data.totalValue.toLocaleString()}</span>
          </motion.h2>
          <div
            className={`mt-0.5 flex items-center gap-1 text-xs ${
              isPositive ? "text-success" : "text-destructive"
            }`}
          >
            {isPositive ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
            <span className="font-medium">
              {isPositive ? "+" : ""}
              {data.change24h}%
            </span>
            <span className="text-muted-foreground">24h</span>
          </div>
        </div>
      </div>

      <div className="mb-3 h-28 -mx-2">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={perf} margin={{ top: 4, right: 4, bottom: 0, left: 4 }}>
            <defs>
              <linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="hsl(38, 96%, 56%)" stopOpacity={0.4} />
                <stop offset="100%" stopColor="hsl(38, 96%, 56%)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="date"
              axisLine={false}
              tickLine={false}
              tick={{ fontSize: 10, fill: "hsl(220, 15%, 55%)" }}
              interval="preserveStartEnd"
            />
            <Tooltip
              contentStyle={{
                background: "hsl(230, 25%, 11%)",
                border: "1px solid hsl(230, 20%, 22%)",
                borderRadius: "8px",
                color: "hsl(220, 20%, 92%)",
                fontSize: "11px",
                padding: "6px 10px",
              }}
              formatter={(value: number) => [`$${value.toLocaleString()}`, "Value"]}
            />
            <Area
              type="monotone"
              dataKey="value"
              stroke="hsl(38, 96%, 56%)"
              strokeWidth={2}
              fill="url(#chartGradient)"
              dot={false}
              activeDot={{ r: 4, fill: "hsl(38, 96%, 56%)", stroke: "hsl(230, 25%, 11%)", strokeWidth: 2 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-3 gap-2">
        {data.tokens.map((token, i) => (
          <motion.div
            key={token.symbol}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 * i }}
            whileHover={{ scale: 1.04 }}
            className="rounded-lg bg-muted/30 px-2.5 py-2 cursor-default transition-colors hover:bg-muted/50"
          >
            <div className="flex items-center gap-1.5 mb-0.5">
              <div className="h-2 w-2 rounded-full shrink-0" style={{ backgroundColor: token.color }} />
              <span className="text-xs font-semibold uppercase">{token.symbol}</span>
            </div>
            <p className="text-[10px] text-muted-foreground font-mono">
              {token.percentage}% · ${(token.value / 1000).toFixed(1)}k
            </p>
          </motion.div>
        ))}
      </div>
    </GlassCard>
  );
}
