import { motion } from "framer-motion";
import { Layers, Brain, Radio, Rocket, ArrowRight, ShieldCheck, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/dashboard/GlassCard";

export default function Index() {
  return (
    <div className="min-h-screen bg-background">
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -top-32 -right-32 h-96 w-96 rounded-full bg-primary/10 blur-[120px]" />
        <div className="absolute -bottom-32 -left-32 h-96 w-96 rounded-full bg-accent/10 blur-[120px]" />
      </div>

      <header className="relative z-10 flex items-center justify-between px-6 py-4 max-w-6xl mx-auto">
        <div className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg gradient-primary">
            <Layers className="h-5 w-5 text-primary-foreground" />
          </div>
          <span className="text-xl font-bold gradient-text">SoSoVault</span>
        </div>
        <Link to="/dashboard">
          <Button className="gradient-primary border-0 text-primary-foreground btn-glow gap-2">
            Launch App <ArrowRight className="h-4 w-4" />
          </Button>
        </Link>
      </header>

      <main className="relative z-10 px-6 py-16 max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center max-w-3xl mx-auto mb-16"
        >
          <div className="inline-flex items-center gap-2 rounded-full bg-primary/10 border border-primary/20 px-3 py-1 text-xs font-medium text-primary mb-4">
            <Sparkles className="h-3 w-3" />
            SoSoValue Buildathon · Wave 1 Submission
          </div>
          <h1 className="text-5xl md:text-6xl font-bold tracking-tight mb-4">
            Agentic on-chain <span className="gradient-text">index portfolios</span>
          </h1>
          <p className="text-lg text-muted-foreground mb-8">
            SoSoVault picks a SoSoValue index basket for your risk tier, explains why
            using live ETF flows + news, and routes the rebalance through SoDEX.
            One-person fund manager — for everyone.
          </p>
          <div className="flex items-center justify-center gap-3">
            <Link to="/dashboard">
              <Button size="lg" className="gradient-primary border-0 text-primary-foreground btn-glow gap-2">
                <Rocket className="h-4 w-4" /> Open Dashboard
              </Button>
            </Link>
            <Link to="/signals">
              <Button size="lg" variant="outline" className="border-glass-border gap-2">
                <Radio className="h-4 w-4" /> View Live Signals
              </Button>
            </Link>
          </div>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-16">
          {[
            {
              icon: Layers,
              title: "SoSoValue indices",
              body: "Live `/indices` data + market snapshots feed every basket. Real ROI numbers, real ETF flows, no hardcoded weights.",
            },
            {
              icon: Brain,
              title: "AI-explained baskets",
              body: "Every basket ships a 3-pillar explanation (volatility, yield, risk) generated from the live SoSoValue data your basket consumed.",
            },
            {
              icon: Radio,
              title: "Insight-to-action signals",
              body: "ETF flows, index momentum, and news sentiment surface as one-click rebalance suggestions — the agentic loop.",
            },
          ].map(({ icon: Icon, title, body }) => (
            <GlassCard key={title} className="p-5">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/15 mb-3">
                <Icon className="h-5 w-5 text-primary" />
              </div>
              <h3 className="font-semibold mb-1">{title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{body}</p>
            </GlassCard>
          ))}
        </div>

        <GlassCard className="p-6">
          <div className="flex items-center gap-2 mb-4">
            <ShieldCheck className="h-4 w-4 text-success" />
            <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              How SoSoVault works
            </h3>
          </div>
          <ol className="space-y-2 text-sm text-muted-foreground list-decimal list-inside">
            <li>Connect your wallet on the SoDEX testnet (chainId 138565).</li>
            <li>Select Low / Medium / High risk tier.</li>
            <li>The backend pulls live SoSoValue indices, ETF flows, and news.</li>
            <li>The basket builder converts that into target weights with a momentum tilt.</li>
            <li>An AI layer generates the human-readable reasoning grounded in those live numbers.</li>
            <li>SoDEX bookticker quotes the route; the basket is submitted (paper mode in Wave 1).</li>
            <li>The Signals page surfaces rebalance suggestions as new flows + news arrive.</li>
          </ol>
          <p className="mt-4 text-xs text-muted-foreground">
            Wave 1 ships the read-to-submit flow with a paper-execution stub. Wave 2 wires
            EIP-712 SoDEX order signing + on-chain `BasketRebalanced` events.
          </p>
        </GlassCard>
      </main>

      <footer className="relative z-10 max-w-6xl mx-auto px-6 py-8 text-center text-xs text-muted-foreground">
        Built for the SoSoValue Buildathon · Powered by SoSoValue OpenAPI · SoDEX testnet
      </footer>
    </div>
  );
}
