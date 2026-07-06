const { expect } = require("chai");
const hre = require("hardhat");
const { ethers } = hre;

describe("PortfolioManager (SoSoVault)", function () {
  let pm, usdc, owner, user, agent;

  beforeEach(async function () {
    [owner, user, agent] = await ethers.getSigners();

    const MockERC20 = await ethers.getContractFactory("MockERC20");
    usdc = await MockERC20.deploy("Mock USDC", "USDC", 6);
    await usdc.waitForDeployment();

    const PortfolioManager = await ethers.getContractFactory("PortfolioManager");
    pm = await PortfolioManager.deploy(await usdc.getAddress());
    await pm.waitForDeployment();
  });

  describe("Deployment", function () {
    it("sets the USDC address correctly", async function () {
      expect(await pm.usdc()).to.equal(await usdc.getAddress());
    });

    it("starts with zero total shares", async function () {
      expect(await pm.totalShares()).to.equal(0n);
    });

    it("sets deployer as owner", async function () {
      expect(await pm.owner()).to.equal(owner.address);
    });
  });

  describe("Agent Management", function () {
    it("owner can set agent", async function () {
      await pm.setAgent(agent.address);
      expect(await pm.agent()).to.equal(agent.address);
    });

    it("non-owner cannot set agent", async function () {
      await expect(pm.connect(user).setAgent(agent.address)).to.be.revertedWith(
        "Ownable: caller is not the owner"
      );
    });

    it("emits AgentUpdated event", async function () {
      await expect(pm.setAgent(agent.address))
        .to.emit(pm, "AgentUpdated")
        .withArgs(ethers.ZeroAddress, agent.address);
    });
  });

  describe("Deposit", function () {
    beforeEach(async function () {
      await usdc.mint(user.address, ethers.parseUnits("10000", 6));
    });

    it("deposits USDC and mints shares", async function () {
      await usdc.connect(user).approve(await pm.getAddress(), ethers.parseUnits("1000", 6));
      await pm.connect(user).deposit(ethers.parseUnits("1000", 6));

      expect(await pm.totalShares()).to.equal(ethers.parseUnits("1000", 6));
      expect(await pm.shares(user.address)).to.equal(ethers.parseUnits("1000", 6));
      expect(await pm.deposits(user.address)).to.equal(ethers.parseUnits("1000", 6));
    });

    it("emits Deposited event", async function () {
      await usdc.connect(user).approve(await pm.getAddress(), ethers.parseUnits("1000", 6));
      await expect(pm.connect(user).deposit(ethers.parseUnits("1000", 6)))
        .to.emit(pm, "Deposited")
        .withArgs(user.address, ethers.parseUnits("1000", 6), ethers.parseUnits("1000", 6));
    });

    it("rejects zero amount", async function () {
      await expect(pm.connect(user).deposit(0)).to.be.revertedWith("PM: amount=0");
    });

    it("mints proportional shares on second deposit", async function () {
      await usdc.connect(user).approve(await pm.getAddress(), ethers.parseUnits("10000", 6));

      await pm.connect(user).deposit(ethers.parseUnits("5000", 6));
      await pm.connect(user).deposit(ethers.parseUnits("5000", 6));

      expect(await pm.totalShares()).to.equal(ethers.parseUnits("10000", 6));
      expect(await pm.shares(user.address)).to.equal(ethers.parseUnits("10000", 6));
    });
  });

  describe("Withdraw", function () {
    beforeEach(async function () {
      await usdc.mint(user.address, ethers.parseUnits("10000", 6));
      await usdc.connect(user).approve(await pm.getAddress(), ethers.parseUnits("10000", 6));
      await pm.connect(user).deposit(ethers.parseUnits("10000", 6));
    });

    it("withdraws proportional USDC", async function () {
      const balanceBefore = await usdc.balanceOf(user.address);
      await pm.connect(user).withdraw(ethers.parseUnits("5000", 6));
      const balanceAfter = await usdc.balanceOf(user.address);

      expect(balanceAfter - balanceBefore).to.equal(ethers.parseUnits("5000", 6));
      expect(await pm.shares(user.address)).to.equal(ethers.parseUnits("5000", 6));
    });

    it("emits Withdrawn event", async function () {
      await expect(pm.connect(user).withdraw(ethers.parseUnits("5000", 6)))
        .to.emit(pm, "Withdrawn")
        .withArgs(user.address, ethers.parseUnits("5000", 6), ethers.parseUnits("5000", 6));
    });

    it("rejects zero shares", async function () {
      await expect(pm.connect(user).withdraw(0)).to.be.revertedWith("PM: shares=0");
    });

    it("rejects insufficient shares", async function () {
      await expect(
        pm.connect(user).withdraw(ethers.parseUnits("20000", 6))
      ).to.be.revertedWith("PM: insufficient shares");
    });
  });

  describe("executeBasket", function () {
    it("rejects weights that don't sum to 100", async function () {
      await expect(pm.executeBasket([30, 30, 30], ["a", "b", "c"])).to.be.revertedWith(
        "PM: weights must sum to 100"
      );
    });

    it("rejects empty basket", async function () {
      await expect(pm.executeBasket([], [])).to.be.revertedWith("PM: empty basket");
    });

    it("rejects length mismatch", async function () {
      await expect(pm.executeBasket([50, 50], ["a"])).to.be.revertedWith(
        "PM: length mismatch"
      );
    });

    it("emits BasketRebalanced when valid", async function () {
      await expect(pm.executeBasket([30, 40, 30], ["USDC", "ssimag7", "ssilayer1"]))
        .to.emit(pm, "BasketRebalanced");
    });

    it("allows agent to execute", async function () {
      await pm.setAgent(agent.address);
      await expect(pm.connect(agent).executeBasket([100], ["USDC"]))
        .to.emit(pm, "BasketRebalanced");
    });

    it("rejects unauthorized caller", async function () {
      await expect(pm.connect(user).executeBasket([100], ["USDC"])).to.be.revertedWith(
        "PM: not authorized"
      );
    });
  });

  describe("Value Queries", function () {
    it("getTotalValue returns USDC balance", async function () {
      await usdc.mint(await pm.getAddress(), ethers.parseUnits("50000", 6));
      expect(await pm.getTotalValue()).to.equal(ethers.parseUnits("50000", 6));
    });

    it("getUserValue returns proportional value", async function () {
      await usdc.mint(user.address, ethers.parseUnits("10000", 6));
      await usdc.connect(user).approve(await pm.getAddress(), ethers.parseUnits("10000", 6));
      await pm.connect(user).deposit(ethers.parseUnits("10000", 6));

      await usdc.mint(await pm.getAddress(), ethers.parseUnits("50000", 6));

      const userValue = await pm.getUserValue(user.address);
      expect(userValue).to.equal(ethers.parseUnits("10000", 6));
    });

    it("getUserValue returns 0 for non-depositor", async function () {
      expect(await pm.getUserValue(user.address)).to.equal(0n);
    });
  });
});
