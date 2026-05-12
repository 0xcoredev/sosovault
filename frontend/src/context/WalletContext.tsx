import { createContext, useContext, useCallback, useEffect, useState, type ReactNode } from "react";
import { BrowserProvider, formatEther } from "ethers";

const SODEX_CHAIN_ID = Number(import.meta.env.VITE_SODEX_CHAIN_ID || 138565);
const SODEX_CHAIN_ID_HEX = `0x${SODEX_CHAIN_ID.toString(16)}`;
const SODEX_RPC = import.meta.env.VITE_SODEX_RPC_URL || "https://testnet-rpc.sodex.dev";
const SODEX_CHAIN_NAME = import.meta.env.VITE_SODEX_CHAIN_NAME || "SoDEX Testnet";

interface WalletState {
  connected: boolean;
  address: string | null;
  network: string;
  chainId: number;
  balance: number;
}

const networkConfigs: Record<number, { name: string; chainId: string }> = {
  [SODEX_CHAIN_ID]: { name: SODEX_CHAIN_NAME, chainId: SODEX_CHAIN_ID_HEX },
  286623: { name: "SoDEX Mainnet", chainId: "0x45f7f" },
  1: { name: "Ethereum Mainnet", chainId: "0x1" },
  11155111: { name: "Sepolia Testnet", chainId: "0xaa36a7" },
  31337: { name: "Localhost", chainId: "0x7a69" },
};

async function switchToSodexNetwork(provider: BrowserProvider): Promise<void> {
  const network = await provider.getNetwork();
  if (Number(network.chainId) === SODEX_CHAIN_ID) return;

  try {
    await (window as any).ethereum.request({
      method: "wallet_switchEthereumChain",
      params: [{ chainId: SODEX_CHAIN_ID_HEX }],
    });
  } catch (switchError: any) {
    if (switchError?.code === 4902) {
      await (window as any).ethereum.request({
        method: "wallet_addEthereumChain",
        params: [
          {
            chainId: SODEX_CHAIN_ID_HEX,
            chainName: SODEX_CHAIN_NAME,
            nativeCurrency: { name: "ETH", symbol: "ETH", decimals: 18 },
            rpcUrls: [SODEX_RPC],
            blockExplorerUrls: [],
          },
        ],
      });
    }
    // Non-fatal: user can stay on current chain.
  }
}

interface WalletContextValue extends WalletState {
  shortenedAddress: string | null;
  connecting: boolean;
  error: string | null;
  isWrongNetwork: boolean;
  connect: () => Promise<void>;
  disconnect: () => void;
  refreshBalance: () => Promise<void>;
}

const WalletContext = createContext<WalletContextValue | null>(null);

const STORAGE_KEY = "sosovault.wallet.connected";

export function WalletProvider({ children }: { children: ReactNode }) {
  const [wallet, setWallet] = useState<WalletState>({
    connected: false,
    address: null,
    network: SODEX_CHAIN_NAME,
    chainId: SODEX_CHAIN_ID,
    balance: 0,
  });
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchBalance = useCallback(
    async (address: string, provider: BrowserProvider): Promise<number> => {
      try {
        const balance = await provider.getBalance(address);
        return Number(formatEther(balance));
      } catch {
        return 0;
      }
    },
    [],
  );

  const applyConnection = useCallback(
    async (provider: BrowserProvider, address: string) => {
      const network = await provider.getNetwork();
      const balance = await fetchBalance(address, provider);
      const networkName =
        networkConfigs[Number(network.chainId)]?.name || `Chain ${network.chainId}`;
      setWallet({
        connected: true,
        address,
        network: networkName,
        chainId: Number(network.chainId),
        balance,
      });
      try {
        localStorage.setItem(STORAGE_KEY, "1");
      } catch {
        /* ignore */
      }
    },
    [fetchBalance],
  );

  const connect = useCallback(async () => {
    setConnecting(true);
    setError(null);

    try {
      if (!(window as any).ethereum) {
        throw new Error("No wallet detected. Please install MetaMask.");
      }

      const provider = new BrowserProvider((window as any).ethereum);
      const accounts = await provider.send("eth_requestAccounts", []);

      if (accounts.length === 0) {
        throw new Error("No accounts found. Please unlock your wallet.");
      }

      await switchToSodexNetwork(provider);
      await applyConnection(provider, accounts[0]);
    } catch (err: any) {
      setError(err?.message || "Failed to connect wallet");
      setWallet((prev) => ({ ...prev, connected: false }));
      try {
        localStorage.removeItem(STORAGE_KEY);
      } catch {
        /* ignore */
      }
    } finally {
      setConnecting(false);
    }
  }, [applyConnection]);

  const disconnect = useCallback(() => {
    setWallet({
      connected: false,
      address: null,
      network: SODEX_CHAIN_NAME,
      chainId: SODEX_CHAIN_ID,
      balance: 0,
    });
    setError(null);
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore */
    }
  }, []);

  const refreshBalance = useCallback(async () => {
    if (!wallet.address || !wallet.connected) return;
    try {
      const provider = new BrowserProvider((window as any).ethereum);
      const balance = await fetchBalance(wallet.address, provider);
      setWallet((prev) => ({ ...prev, balance }));
    } catch (err) {
      console.error("Failed to refresh balance:", err);
    }
  }, [wallet.address, wallet.connected, fetchBalance]);

  // Auto-reconnect on mount if we previously connected and the wallet still has accounts.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const eth = (window as any).ethereum;
      if (!eth) return;
      let shouldRestore = false;
      try {
        shouldRestore = localStorage.getItem(STORAGE_KEY) === "1";
      } catch {
        /* ignore */
      }
      if (!shouldRestore) return;
      try {
        const provider = new BrowserProvider(eth);
        const accounts: string[] = await eth.request({ method: "eth_accounts" });
        if (cancelled) return;
        if (accounts && accounts.length > 0) {
          await applyConnection(provider, accounts[0]);
        } else {
          try {
            localStorage.removeItem(STORAGE_KEY);
          } catch {
            /* ignore */
          }
        }
      } catch (err) {
        console.warn("Auto-reconnect failed:", err);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [applyConnection]);

  // Listen for account / chain changes once at provider level.
  useEffect(() => {
    const eth = (window as any).ethereum;
    if (!eth) return;

    const handleAccountsChanged = async (accounts: string[]) => {
      if (!accounts || accounts.length === 0) {
        disconnect();
        return;
      }
      try {
        const provider = new BrowserProvider(eth);
        await applyConnection(provider, accounts[0]);
      } catch (err) {
        console.warn("accountsChanged handler failed:", err);
      }
    };

    const handleChainChanged = () => {
      // Easiest way to keep state coherent across all routes.
      window.location.reload();
    };

    eth.on?.("accountsChanged", handleAccountsChanged);
    eth.on?.("chainChanged", handleChainChanged);

    return () => {
      eth.removeListener?.("accountsChanged", handleAccountsChanged);
      eth.removeListener?.("chainChanged", handleChainChanged);
    };
  }, [applyConnection, disconnect]);

  const shortenedAddress = wallet.address
    ? `${wallet.address.slice(0, 6)}...${wallet.address.slice(-4)}`
    : null;

  const value: WalletContextValue = {
    ...wallet,
    shortenedAddress,
    connecting,
    error,
    isWrongNetwork: wallet.connected && wallet.chainId !== SODEX_CHAIN_ID,
    connect,
    disconnect,
    refreshBalance,
  };

  return <WalletContext.Provider value={value}>{children}</WalletContext.Provider>;
}

export function useWallet(): WalletContextValue {
  const ctx = useContext(WalletContext);
  if (!ctx) {
    throw new Error("useWallet must be used within a <WalletProvider>");
  }
  return ctx;
}
