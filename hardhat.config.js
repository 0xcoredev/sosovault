require("@nomicfoundation/hardhat-toolbox");
require("dotenv").config();

const SODEX_TESTNET_RPC = process.env.SODEX_TESTNET_RPC || "https://testnet-rpc.sodex.dev";
const DEPLOYER_PRIVATE_KEY = process.env.DEPLOYER_PRIVATE_KEY;

module.exports = {
  solidity: {
    version: "0.8.20",
    settings: {
      optimizer: { enabled: true, runs: 200 },
    },
  },
  networks: {
    localhost: {
      url: "http://127.0.0.1:8545",
    },
    hardhat: {
      chainId: 31337,
    },
    sodexTestnet: {
      url: SODEX_TESTNET_RPC,
      chainId: 138565,
      accounts: DEPLOYER_PRIVATE_KEY ? [DEPLOYER_PRIVATE_KEY] : [],
    },
  },
};
