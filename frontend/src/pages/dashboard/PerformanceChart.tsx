import { useMemo } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { PerformancePoint } from "@/lib/api";
import { GlassCard } from "@/components/dashboard/GlassCard";

interface PerformanceChartProps {
  data: PerformancePoint[];
  loading?: boolean;
}

function formatValue(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

function CustomTooltip({ active, payload, label }: any) {
  if (active && payload && payload.length) {
    return (
      <div className="bg-card border border-border rounded-lg p-3 shadow-lg">
        <p className="text-muted-foreground text-xs mb-1">{label}</p>
        <p className="text-primary font-semibold">{formatValue(payload[0].value)}</p>
      </div>
    );
  }
  return null;
}

export function PerformanceChart({ data, loading }: PerformanceChartProps) {
  const stats = useMemo(() => {
    if (!data.length) return { change: 0, percentage: 0 };
    const first = data[0].value;
    const last = data[data.length - 1].value;
    const change = last - first;
    const percentage = ((change / first) * 100).toFixed(2);
    return { change, percentage: Number(percentage) };
  }, [data]);

  return (
    <GlassCard className="p-4 lg:p-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <div>
          <h2 className="text-lg font-semibold text-foreground">Portfolio Performance</h2>
          <p className="text-sm text-muted-foreground">Track your portfolio value over time</p>
        </div>
        <div className="flex items-center gap-6">
          <div>
            <p className="text-xs text-muted-foreground uppercase tracking-wider">Total Value</p>
            <p className="text-xl font-bold text-foreground">
              {formatValue(data[data.length - 1]?.value || 0)}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground uppercase tracking-wider">Change</p>
            <p className={`text-xl font-bold ${stats.change >= 0 ? "text-emerald-500" : "text-red-500"}`}>
              {stats.change >= 0 ? "+" : ""}{stats.percentage}%
            </p>
          </div>
        </div>
      </div>

      <div className="h-[300px] w-full">
        {loading ? (
          <div className="h-full w-full flex items-center justify-center">
            <div className="animate-pulse flex flex-col items-center gap-3">
              <div className="h-2 w-full bg-muted rounded" />
              <div className="h-2 w-full bg-muted rounded" />
              <div className="h-2 w-full bg-muted rounded" />
              <div className="h-2 w-full bg-muted rounded" />
              <div className="h-2 w-full bg-muted rounded" />
            </div>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border) / 0.3)" vertical={false} />
              <XAxis 
                dataKey="date" 
                tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
                tickLine={false}
                axisLine={{ stroke: "hsl(var(--border))" }}
              />
              <YAxis 
                tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
                width={60}
              />
              <Tooltip content={<CustomTooltip />} />
              <Area
                type="monotone"
                dataKey="value"
                stroke="#10b981"
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#colorValue)"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </GlassCard>
  );
}