const { expect } = require("chai");
const hre = require("hardhat");

describe("PortfolioManager (SoSoVault)", function () {
  it("deploys with the USDC address set", async function () {
    const [owner] = await hre.ethers.getSigners();
    const PortfolioManager = await hre.ethers.getContractFactory("PortfolioManager");
    const pm = await PortfolioManager.deploy(owner.address);
    await pm.waitForDeployment();
    expect(await pm.usdc()).to.equal(owner.address);
    expect(await pm.totalShares()).to.equal(0n);
  });

  it("rejects executeBasket weights that don't sum to 100", async function () {
    const [owner] = await hre.ethers.getSigners();
    const PortfolioManager = await hre.ethers.getContractFactory("PortfolioManager");
    const pm = await PortfolioManager.deploy(owner.address);
    await pm.waitForDeployment();
    await expect(pm.executeBasket([30, 30, 30], ["a", "b", "c"])).to.be.revertedWith(
      "PM: weights must sum to 100"
    );
  });

  it("emits BasketRebalanced when weights sum to 100 and arrays match", async function () {
    const [owner] = await hre.ethers.getSigners();
    const PortfolioManager = await hre.ethers.getContractFactory("PortfolioManager");
    const pm = await PortfolioManager.deploy(owner.address);
    await pm.waitForDeployment();
    await expect(pm.executeBasket([30, 40, 30], ["USDC", "ssimag7", "ssilayer1"]))
      .to.emit(pm, "BasketRebalanced");
  });
});
