/**
 * SoSoVault — PortfolioManager deploy script.
 *
 * Wave 1: NOT executed in production. The contract compiles and the unit tests
 * pass; deployment is deferred to Wave 2 once the SoDEX testnet deposit/faucet
 * loop is verified.
 *
 * To deploy locally for tests:
 *   npx hardhat node                   (terminal A)
 *   npx hardhat run scripts/deploy.js --network localhost   (terminal B)
 */
const hre = require("hardhat");

async function main() {
  const [deployer] = await hre.ethers.getSigners();
  console.log("Deploying SoSoVault PortfolioManager with:", deployer.address);

  // Deploy a mock USDC for local runs. On a live testnet, pass the real USDC address
  // via the USDC_ADDRESS env var.
  let usdcAddress = process.env.USDC_ADDRESS;
  if (!usdcAddress) {
    const ERC20 = await hre.ethers.getContractFactory("contracts/MockERC20.sol:MockERC20").catch(() => null);
    if (ERC20) {
      const usdc = await ERC20.deploy("Mock USDC", "USDC", 6);
      await usdc.waitForDeployment();
      usdcAddress = await usdc.getAddress();
      console.log("MockUSDC deployed at:", usdcAddress);
    } else {
      // Fallback: use deployer as a placeholder so the deploy script still runs.
      // The contract will revert on real deposits but compiles + deploys cleanly.
      usdcAddress = deployer.address;
      console.log("USDC_ADDRESS not set; using deployer as placeholder");
    }
  }

  const PortfolioManager = await hre.ethers.getContractFactory("PortfolioManager");
  const pm = await PortfolioManager.deploy(usdcAddress);
  await pm.waitForDeployment();

  const pmAddress = await pm.getAddress();
  console.log("PortfolioManager deployed at:", pmAddress);
  console.log(JSON.stringify({ portfolioManager: pmAddress, usdc: usdcAddress }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
