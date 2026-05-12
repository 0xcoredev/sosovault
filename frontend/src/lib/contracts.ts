import { ethers } from "ethers";

/**
 * Filled in after `npx hardhat run scripts/deploy.js --network <sodex-testnet>`.
 * The frontend gracefully degrades to a mocked tx hash if these are blank,
 * so the demo still works without a deployment.
 */
export const CONTRACT_ADDRESSES = {
  portfolioManager: import.meta.env.VITE_PORTFOLIO_MANAGER_ADDRESS || "",
  usdc: import.meta.env.VITE_USDC_ADDRESS || "",
};

const PORTFOLIO_MANAGER_ABI = [
  "function deposit(uint256 _amount) external",
  "function withdraw(uint256 _shareAmount) external",
  "function executeBasket(uint256[] calldata _weights, string[] calldata _symbols) external",
  "function getTotalValue() external view returns (uint256)",
  "function getUserValue(address _user) external view returns (uint256)",
  "function shares(address _user) external view returns (uint256)",
  "function totalShares() external view returns (uint256)",
  "function usdc() external view returns (address)",
  "event BasketRebalanced(address indexed user, uint256[] weights, string[] symbols, uint256 totalValue, uint256 timestamp)",
  "event Deposited(address indexed user, uint256 amount, uint256 sharesMinted)",
  "event Withdrawn(address indexed user, uint256 amount, uint256 sharesBurned)",
];

const ERC20_ABI = [
  "function approve(address spender, uint256 amount) external returns (bool)",
  "function allowance(address owner, address spender) external view returns (uint256)",
  "function balanceOf(address account) external view returns (uint256)",
  "function decimals() external view returns (uint8)",
];

export type TransactionStatus = "idle" | "pending" | "confirming" | "success" | "failed";

export interface TransactionState {
  status: TransactionStatus;
  txHash?: string;
  error?: string;
  confirmations?: number;
}

export class ContractService {
  private provider: ethers.BrowserProvider | null = null;
  private signer: ethers.Signer | null = null;

  async connect(): Promise<boolean> {
    if (!(window as any).ethereum) return false;
    try {
      this.provider = new ethers.BrowserProvider((window as any).ethereum);
      this.signer = await this.provider.getSigner();
      return true;
    } catch (error) {
      console.error("Failed to connect wallet:", error);
      return false;
    }
  }

  isConnected(): boolean {
    return this.signer !== null;
  }

  isDeployed(): boolean {
    return Boolean(CONTRACT_ADDRESSES.portfolioManager);
  }

  async approveToken(tokenAddress: string, spender: string, amount: ethers.BigNumberish) {
    if (!this.signer) throw new Error("Wallet not connected");
    const token = new ethers.Contract(tokenAddress, ERC20_ABI, this.signer);
    const owner = await this.signer.getAddress();
    const current = await token.allowance(owner, spender);
    if (current < amount) {
      return await token.approve(spender, ethers.MaxUint256);
    }
    return null;
  }

  async executeBasket(weights: number[], symbols: string[]) {
    if (!this.signer) throw new Error("Wallet not connected");
    if (!this.isDeployed()) {
      throw new Error("PortfolioManager not deployed yet — running in demo mode");
    }
    const contract = new ethers.Contract(
      CONTRACT_ADDRESSES.portfolioManager,
      PORTFOLIO_MANAGER_ABI,
      this.signer,
    );
    return await contract.executeBasket(weights, symbols);
  }

  async deposit(amount: ethers.BigNumberish) {
    if (!this.signer) throw new Error("Wallet not connected");
    if (!this.isDeployed()) throw new Error("PortfolioManager not deployed yet");
    const contract = new ethers.Contract(
      CONTRACT_ADDRESSES.portfolioManager,
      PORTFOLIO_MANAGER_ABI,
      this.signer,
    );
    if (CONTRACT_ADDRESSES.usdc) {
      await this.approveToken(CONTRACT_ADDRESSES.usdc, CONTRACT_ADDRESSES.portfolioManager, amount);
    }
    return await contract.deposit(amount);
  }

  async withdraw(shareAmount: ethers.BigNumberish) {
    if (!this.signer) throw new Error("Wallet not connected");
    if (!this.isDeployed()) throw new Error("PortfolioManager not deployed yet");
    const contract = new ethers.Contract(
      CONTRACT_ADDRESSES.portfolioManager,
      PORTFOLIO_MANAGER_ABI,
      this.signer,
    );
    return await contract.withdraw(shareAmount);
  }

  async getUserShares(): Promise<bigint> {
    if (!this.signer || !this.isDeployed()) return 0n;
    const contract = new ethers.Contract(
      CONTRACT_ADDRESSES.portfolioManager,
      PORTFOLIO_MANAGER_ABI,
      this.signer,
    );
    const address = await this.signer.getAddress();
    return await contract.shares(address);
  }
}

export const contractService = new ContractService();
