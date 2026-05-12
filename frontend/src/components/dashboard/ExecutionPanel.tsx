import { motion, AnimatePresence } from "framer-motion";
import { Rocket, Fuel, TrendingUp, X, Loader2, AlertCircle, CheckCircle2, Info } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import type { StrategyRecommendation } from "@/lib/mock-data";
import { aiStrategy } from "@/lib/mock-data";
import { GlassCard } from "./GlassCard";
import { toast } from "sonner";
import { SkeletonBlock } from "./SkeletonBlock";
import { useWallet } from "@/hooks/use-wallet";
import { api } from "@/lib/api";

interface ExecutionPanelProps {
  loading?: boolean;
  walletConnected: boolean;
  strategy?: StrategyRecommendation | null;
}

export function ExecutionPanel({ loading, walletConnected, strategy }: ExecutionPanelProps) {
  const [showModal, setShowModal] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [txHash, setTxHash] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const wallet = useWallet();
  const data = strategy ?? aiStrategy;

  const handleExecute = async () => {
    if (!wallet.connected || !wallet.address) {
      toast.error("Please connect your wallet first");
      return;
    }

    setExecuting(true);
    setError(null);
    setTxHash(null);

    try {
      const allocations = data.allocations.map((a) => a.percentage);
      const symbols = data.allocations.map((a) => a.symbol);

      const response = await api.executeStrategy(wallet.address, allocations, symbols);

      if (response.success && response.data) {
        setTxHash(response.data.txHash);
        toast.success("Basket submitted (paper mode)", {
          description: `Tx: ${response.data.txHash.slice(0, 10)}...${response.data.txHash.slice(-8)}`,
        });
      } else {
        throw new Error(response.error || "Execution failed");
      }
    } catch (err: any) {
      setError(err.message || "Submission failed");
      toast.error(err.message || "Submission failed");
    } finally {
      setExecuting(false);
      setTimeout(() => {
        setShowModal(false);
        setTxHash(null);
        setError(null);
      }, 4000);
    }
  };

  if (loading) {
    return (
      <GlassCard>
        <SkeletonBlock className="h-4 w-24 mb-3" />
        <SkeletonBlock className="h-8 w-full mb-2" />
        <SkeletonBlock className="h-8 w-full mb-3" />
        <SkeletonBlock className="h-9 w-full" />
      </GlassCard>
    );
  }

  return (
    <>
      <GlassCard delay={0.15}>
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Execute Basket
          </h3>
          <span className="text-[9px] uppercase text-warning bg-warning/10 px-1.5 py-0.5 rounded font-mono">
            Wave 1: paper
          </span>
        </div>

        <div className="mb-2 flex items-center justify-between rounded-lg bg-muted/20 px-3 py-2">
          <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
            <Fuel className="h-3 w-3" />
            Est. Gas
          </div>
          <span className="font-mono text-[11px]">{data.estimatedGas} ETH</span>
        </div>

        <div className="mb-3 flex items-center justify-between rounded-lg bg-muted/20 px-3 py-2">
          <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
            <TrendingUp className="h-3 w-3" />
            Est. Annual Yield
          </div>
          <span className="font-mono text-[11px] text-success">
            {(data.estimatedYield * 100).toFixed(1)}%
          </span>
        </div>

        <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}>
          <Button
            onClick={() =>
              walletConnected
                ? setShowModal(true)
                : toast.error("Connect your wallet first")
            }
            className="w-full gradient-primary border-0 text-primary-foreground btn-glow gap-2 h-9 text-sm"
          >
            <Rocket className="h-3.5 w-3.5" />
            Submit Basket
          </Button>
        </motion.div>

        <p className="mt-2 text-[10px] text-muted-foreground leading-snug flex gap-1">
          <Info className="h-3 w-3 mt-0.5 shrink-0" />
          Wave 2 will sign EIP-712 SoDEX orders + emit BasketRebalanced on-chain.
        </p>
      </GlassCard>

      <AnimatePresence>
        {showModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm p-4"
            onClick={() => !executing && setShowModal(false)}
          >
            <motion.div
              initial={{ scale: 0.92, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.92, opacity: 0 }}
              transition={{ type: "spring", duration: 0.35 }}
              onClick={(e) => e.stopPropagation()}
              className="glass-card w-full max-w-sm p-5"
            >
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-base font-semibold">Confirm Basket</h3>
                <button
                  onClick={() => !executing && setShowModal(false)}
                  className="text-muted-foreground hover:text-foreground transition-colors"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              <div className="mb-3 space-y-1.5">
                {data.allocations.map((a) => (
                  <div
                    key={a.symbol}
                    className="flex justify-between rounded-md bg-muted/20 px-3 py-1.5 text-sm"
                  >
                    <span className="text-muted-foreground">{a.name}</span>
                    <span className="font-mono text-xs">{a.percentage}%</span>
                  </div>
                ))}
              </div>

              <div className="mb-3 flex justify-between text-[11px] text-muted-foreground px-1">
                <span>Gas: ~{data.estimatedGas} ETH</span>
                <span>Yield: ~{(data.estimatedYield * 100).toFixed(1)}%</span>
              </div>

              {(executing || txHash || error) && (
                <div className="mb-3 p-2 rounded-md bg-muted/30 text-center text-sm">
                  {executing && (
                    <div className="flex items-center justify-center gap-2 text-amber-500">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span>Routing through SoDEX bookticker...</span>
                    </div>
                  )}
                  {txHash && !executing && (
                    <div className="flex flex-col items-center gap-1 text-emerald-500">
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="h-4 w-4" />
                        <span>Submitted (paper mode)</span>
                      </div>
                      <span className="text-[10px] text-muted-foreground font-mono">
                        {txHash.slice(0, 14)}...{txHash.slice(-10)}
                      </span>
                    </div>
                  )}
                  {error && !executing && (
                    <div className="flex items-center justify-center gap-2 text-red-500">
                      <AlertCircle className="h-4 w-4" />
                      <span>{error}</span>
                    </div>
                  )}
                </div>
              )}

              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="flex-1 border-glass-border"
                  onClick={() => setShowModal(false)}
                  disabled={executing}
                >
                  Cancel
                </Button>
                <motion.div className="flex-1" whileTap={{ scale: 0.97 }}>
                  <Button
                    onClick={handleExecute}
                    disabled={executing || Boolean(txHash)}
                    size="sm"
                    className="w-full gradient-primary border-0 text-primary-foreground gap-1.5"
                  >
                    {executing ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        Executing...
                      </>
                    ) : (
                      "Confirm"
                    )}
                  </Button>
                </motion.div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
