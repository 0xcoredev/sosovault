/**
 * Backwards-compatible re-export.
 *
 * The actual wallet state lives in a single React context
 * (`@/context/WalletContext`) so navigating between pages does not
 * lose the connection. Components can keep importing `useWallet`
 * from here unchanged.
 */
export { useWallet } from "@/context/WalletContext";
