import { motion } from "framer-motion";
import { Wifi, ChevronDown, LogOut, Layers } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface TopNavProps {
  connected: boolean;
  connecting: boolean;
  address: string | null;
  network: string;
  balance?: number;
  onConnect: () => void;
  onDisconnect: () => void;
}

export function TopNav({
  connected,
  connecting,
  address,
  network,
  balance = 0,
  onConnect,
  onDisconnect,
}: TopNavProps) {
  return (
    <motion.header
      initial={{ y: -20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      className="glass-card sticky top-0 z-50 flex items-center justify-between px-6 py-3"
    >
      <div className="flex items-center gap-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg gradient-primary">
          <Layers className="h-4 w-4 text-primary-foreground" />
        </div>
        <div className="leading-tight">
          <span className="text-lg font-bold gradient-text">SoSoVault</span>
          <p className="text-[9px] text-muted-foreground uppercase tracking-wider">
            agentic on-chain indices
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {connected ? (
          <>
            <div className="hidden sm:flex items-center gap-2 rounded-lg bg-muted/50 px-3 py-1.5 text-sm">
              <span className="h-2 w-2 rounded-full bg-success glow-dot" />
              <span className="text-muted-foreground">{network}</span>
            </div>

            <div className="hidden sm:flex items-center gap-2 rounded-lg bg-muted/50 px-3 py-1.5 text-sm">
              <span className="text-foreground font-medium">{balance.toFixed(4)}</span>
              <span className="text-muted-foreground">ETH</span>
            </div>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-2 border-glass-border bg-muted/30 hover:bg-muted/50"
                >
                  <Wifi className="h-3.5 w-3.5 text-success" />
                  <span className="font-mono text-xs">{address}</span>
                  <ChevronDown className="h-3 w-3 text-muted-foreground" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="glass-card border-glass-border">
                <DropdownMenuItem
                  onClick={onDisconnect}
                  className="gap-2 text-destructive focus:text-destructive"
                >
                  <LogOut className="h-4 w-4" />
                  Disconnect
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </>
        ) : (
          <Button
            onClick={onConnect}
            disabled={connecting}
            className="gradient-primary border-0 text-primary-foreground btn-glow"
          >
            {connecting ? (
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
                className="h-4 w-4 rounded-full border-2 border-primary-foreground/30 border-t-primary-foreground"
              />
            ) : (
              "Connect Wallet"
            )}
          </Button>
        )}
      </div>
    </motion.header>
  );
}
