// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/**
 * @title PortfolioManager
 * @notice Minimal SoSoVault share-accounting contract.
 *
 * Wave 1: ABI is documented and unit-tested but the contract is intentionally
 *         not deployed. The frontend "Submit Basket" path runs in paper mode.
 *
 * Wave 2: Deploy to SoDEX testnet (chainId 138565). The agent backend signs
 *         EIP-712 newOrder messages for each basket leg via the SoDEX REST API
 *         and emits BasketRebalanced here for the on-chain audit trail.
 *
 * The contract intentionally does NOT route trades on-chain. SoSoVault baskets
 * route through the SoDEX off-chain orderbook (gas-efficient, Hyperliquid-style
 * model) and only the basket weights, target symbols, and net vault value are
 * persisted on-chain — that is enough for an auditable, agentic fund manager.
 */
contract PortfolioManager is Ownable, ReentrancyGuard {
    IERC20 public immutable usdc;

    address public agent;

    mapping(address => uint256) public deposits;
    mapping(address => uint256) public shares;
    uint256 public totalShares;

    event Deposited(address indexed user, uint256 amount, uint256 sharesMinted);
    event Withdrawn(address indexed user, uint256 amount, uint256 sharesBurned);
    event AgentUpdated(address indexed previousAgent, address indexed newAgent);
    event BasketRebalanced(
        address indexed user,
        uint256[] weights,
        string[] symbols,
        uint256 totalValue,
        uint256 timestamp
    );

    modifier onlyAgentOrUser(address _user) {
        require(msg.sender == _user || msg.sender == agent, "PM: not authorized");
        _;
    }

    constructor(address _usdc) Ownable(msg.sender) {
        require(_usdc != address(0), "PM: invalid USDC");
        usdc = IERC20(_usdc);
    }

    function setAgent(address _agent) external onlyOwner {
        emit AgentUpdated(agent, _agent);
        agent = _agent;
    }

    /// @notice Deposit USDC and receive SoSoVault shares at current NAV.
    function deposit(uint256 _amount) external nonReentrant {
        require(_amount > 0, "PM: amount=0");
        require(usdc.transferFrom(msg.sender, address(this), _amount), "PM: transfer failed");

        uint256 sharesMinted;
        uint256 totalValue = getTotalValue();
        if (totalShares == 0 || totalValue == 0) {
            sharesMinted = _amount;
        } else {
            sharesMinted = (_amount * totalShares) / totalValue;
        }

        deposits[msg.sender] += _amount;
        shares[msg.sender] += sharesMinted;
        totalShares += sharesMinted;

        emit Deposited(msg.sender, _amount, sharesMinted);
    }

    /// @notice Burn SoSoVault shares and withdraw the proportional USDC reserve.
    function withdraw(uint256 _shareAmount) external nonReentrant {
        require(_shareAmount > 0, "PM: shares=0");
        require(shares[msg.sender] >= _shareAmount, "PM: insufficient shares");

        uint256 totalValue = getTotalValue();
        require(totalShares > 0, "PM: no shares");
        uint256 amount = (_shareAmount * totalValue) / totalShares;
        require(amount > 0, "PM: amount=0");

        shares[msg.sender] -= _shareAmount;
        totalShares -= _shareAmount;
        if (deposits[msg.sender] >= amount) {
            deposits[msg.sender] -= amount;
        } else {
            deposits[msg.sender] = 0;
        }

        require(usdc.transfer(msg.sender, amount), "PM: transfer failed");
        emit Withdrawn(msg.sender, amount, _shareAmount);
    }

    /**
     * @notice Record a basket rebalance on-chain.
     * @dev Called by the agent (or the user themselves) after the basket has
     *      been routed through SoDEX off-chain. The arrays MUST line up:
     *      `weights[i]` is the target percentage (0-100) for `symbols[i]`.
     *      The contract validates the weights sum to 100 and the arrays match.
     */
    function executeBasket(
        uint256[] calldata _weights,
        string[] calldata _symbols
    ) external onlyAgentOrUser(msg.sender) nonReentrant {
        require(_weights.length == _symbols.length, "PM: length mismatch");
        require(_weights.length > 0, "PM: empty basket");

        uint256 sum;
        for (uint256 i = 0; i < _weights.length; i++) {
            sum += _weights[i];
        }
        require(sum == 100, "PM: weights must sum to 100");

        emit BasketRebalanced(
            msg.sender,
            _weights,
            _symbols,
            getTotalValue(),
            block.timestamp
        );
    }

    function getTotalValue() public view returns (uint256) {
        return usdc.balanceOf(address(this));
    }

    function getUserValue(address _user) external view returns (uint256) {
        if (totalShares == 0) return 0;
        return (shares[_user] * getTotalValue()) / totalShares;
    }
}
