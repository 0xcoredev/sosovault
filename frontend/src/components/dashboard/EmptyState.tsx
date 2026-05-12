import { motion } from "framer-motion";
import { Wallet, Coins } from "lucide-react";
import { Button } from "@/components/ui/button";

interface EmptyStateProps {
  type: "no-wallet" | "no-funds";
  onAction: () => void;
}

export function EmptyState({ type, onAction }: EmptyStateProps) {
  const config = {
    "no-wallet": {
      icon: Wallet,
      title: "Connect Wallet to Start",
      description:
        "Link your wallet to access SoSoVault — agentic on-chain index portfolios powered by SoSoValue indices and SoDEX execution.",
      action: "Connect Wallet",
    },
    "no-funds": {
      icon: Coins,
      title: "Deposit USDC to Begin",
      description:
        "Transfer USDC into the vault to mint SoSoVault shares against your selected index basket.",
      action: "Deposit USDC",
    },
  }[type];

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="col-span-full flex flex-col items-center justify-center py-20"
    >
      <motion.div
        animate={{ y: [0, -8, 0] }}
        transition={{ repeat: Infinity, duration: 3, ease: "easeInOut" }}
        className="mb-6 flex h-20 w-20 items-center justify-center rounded-2xl bg-primary/10 border border-primary/20"
      >
        <config.icon className="h-10 w-10 text-primary" />
      </motion.div>
      <h2 className="mb-2 text-xl font-semibold">{config.title}</h2>
      <p className="mb-6 max-w-md text-center text-sm text-muted-foreground">
        {config.description}
      </p>
      <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
        <Button onClick={onAction} className="gradient-primary border-0 text-primary-foreground btn-glow">
          {config.action}
        </Button>
      </motion.div>
    </motion.div>
  );
}
