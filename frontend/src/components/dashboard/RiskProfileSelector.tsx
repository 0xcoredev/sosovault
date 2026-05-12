import { motion } from "framer-motion";
import { Shield, Scale, Flame } from "lucide-react";
import { RiskLevel, riskProfiles } from "@/lib/mock-data";
import { GlassCard } from "./GlassCard";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { SkeletonBlock } from "./SkeletonBlock";

const icons = { low: Shield, medium: Scale, high: Flame };

interface RiskProfileSelectorProps {
  selected: RiskLevel;
  onSelect: (level: RiskLevel) => void;
  loading?: boolean;
}

export function RiskProfileSelector({ selected, onSelect, loading }: RiskProfileSelectorProps) {
  if (loading) {
    return (
      <GlassCard>
        <SkeletonBlock className="h-4 w-28 mb-3" />
        <div className="space-y-2">
          {[1, 2, 3].map((i) => <SkeletonBlock key={i} className="h-14 w-full" />)}
        </div>
      </GlassCard>
    );
  }

  return (
    <GlassCard delay={0.1}>
      <h3 className="mb-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Risk Profile</h3>
      <div className="space-y-1.5">
        {(Object.keys(riskProfiles) as RiskLevel[]).map((level) => {
          const profile = riskProfiles[level];
          const Icon = icons[level];
          const isSelected = selected === level;
          const colorClass = level === "low" ? "text-success" : level === "medium" ? "text-warning" : "text-destructive";
          const bgClass = level === "low" ? "bg-success/10 border-success/20" : level === "medium" ? "bg-warning/10 border-warning/20" : "bg-destructive/10 border-destructive/20";
          const glowClass = level === "low" ? "shadow-[0_0_12px_hsl(152,60%,48%,0.15)]" : level === "medium" ? "shadow-[0_0_12px_hsl(38,92%,50%,0.15)]" : "shadow-[0_0_12px_hsl(0,72%,51%,0.15)]";

          return (
            <Tooltip key={level}>
              <TooltipTrigger asChild>
                <motion.button
                  onClick={() => onSelect(level)}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.97 }}
                  className={`w-full flex items-center gap-3 rounded-lg border px-3 py-2.5 text-left transition-all duration-200 ${
                    isSelected
                      ? `${bgClass} ${glowClass}`
                      : "border-transparent bg-muted/20 hover:bg-muted/40"
                  }`}
                >
                  <div className={`rounded-md p-1.5 ${isSelected ? bgClass : "bg-muted/30"}`}>
                    <Icon className={`h-3.5 w-3.5 ${isSelected ? colorClass : "text-muted-foreground"}`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className={`text-sm font-medium leading-tight ${isSelected ? colorClass : ""}`}>{profile.label}</p>
                    <p className="text-[10px] text-muted-foreground font-mono">APY: {profile.expectedApy}</p>
                  </div>
                  {isSelected && (
                    <motion.div
                      layoutId="risk-check"
                      className={`h-1.5 w-1.5 rounded-full ${colorClass} glow-dot`}
                    />
                  )}
                </motion.button>
              </TooltipTrigger>
              <TooltipContent side="left" className="glass-card border-glass-border max-w-[200px] text-[11px]">
                {profile.description}
              </TooltipContent>
            </Tooltip>
          );
        })}
      </div>
    </GlassCard>
  );
}
