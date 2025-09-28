# Tropykus.js Library

A JavaScript SDK for Ethereum and the Tropykus Protocol. Wraps around [Ethers.js](https://github.com/ethers-io/ethers.js/). Works in the **web browser** and **Node.js**.

[Tropykus.js Documentation](https://tropykus.gitbook.io/tropykus-protocol)

This SDK is in **open beta**, and is constantly under development. **USE AT YOUR OWN RISK**.

## Install / Import

**Node.js / ReactJS / VueJS**

```
npm install @tropykus/tropykus-js
```

```js
const Tropykus = require("@tropykus/tropykus-js");

// or, when using ES6

import Tropykus from "@tropykus/tropykus-js";
```

**Web Browser**

```html
<script
	type="text/javascript"
	src="https://cdn.jsdelivr.net/npm/@tropykus/tropykus-js@latest/dist/browser/tropykus.min.js"
></script>

<script type="text/javascript">
	window.Tropykus; // or `Tropykus`
</script>
```

## Instance Creation

This SDK can be used both on a browser as well as on a NodeJS application. If you are accessing with an injected provider such as Metamask, ensure that you are connected the the Rootstock Mainnet (or Rootstock Testnet) network

```js
const tropykus = new Tropykus(window.ethereum); // web browser

const tropykus = new Tropykus('http://127.0.0.1:8545'); // HTTP provider

const tropykus = new Tropykus(); // Uses Ethers.js fallback mainnet (for testing only)

const tropykus = new Tropykus('https://public-node.testnet.rsk.co'); // Uses Ethers.js fallback (for testing only)

// Init with private key (server side)
const tropykus = new Tropykus('https://public-node.rsk.co', {
  privateKey: '0x_your_private_key_', // preferably with environment variable
});

// Init with HD mnemonic (server side)
const tropykus = new Tropykus('https://public-node.rsk.co' {
  mnemonic: 'clutch captain shoe...', // preferably with environment variable
});
```

## Instance Creation example using React + Wagmi 2.x.x

In this example we are creating an instance of the library in a NextJS application using [RainbowKit](https://www.rainbowkit.com/) v2.x.x. This code should serve as an example on how to use the library in a browser environment

```js
import { useAccount } from "wagmi";
const Home: NextPage = () => {
	const { chain, isConnected } = useAccount();
	let tropykus;
	if (isConnected) {
		const signer = window.ethereum;
		if (!signer) throw new Error("No signer found");
		if (!chain) throw new Error("No chain found");
		tropykus = new Tropykus(signer);
	}
	// ... Rest of your code ...
};
```

## Tropykus Protocol

### Constants and Contract Addresses

Names of contracts, their addresses, ABIs, token decimals, and more can be found in `/src/constants.ts`. Addresses, for all networks, can be easily fetched using the `getAddress` function, combined with contract name constants.

```js
console.log(Tropykus.DOC, Tropykus.BPRO, Tropykus.kRBTC);

// To get the token address for RSK mainnet
const kDOC = Tropykus.util.getAddress(Tropykus.kDOC);

// To get the token address for RSK testnet
const kBPRO = Tropykus.util.getAddress(Tropykus.kBPRO, "rsk_testnet");
```

### Protocol actions: Supply, Borrow, Repay and Redeem

The SDK provides some simple methods to interact with the protocol.

**Important:** It is critical to set the gasLimit option on each transaction to ensure the exeuction of the method

The accepted assets to interact with the protocol are: RBTC, DOC and BPRO

```js
const tropykus = new Tropykus(window.ethereum); // in a web browser

// Ensure that the tropykus instance is created and connected before calling any function

// Ethers.js overrides are an optional 3rd parameter for `supply`
// const trxOptions = { gasLimit: 250000, mantissa: false };

const amount = 1; // It can also be a string... const amount = "1"
 
// Supply of RBTC
(async function () {
	console.log("Supplying RBTC to the Tropykus protocol...");
	const trx = await tropykus.supply(Tropykus.RBTC, amount, {
		gasLimit: 250000
	});
	console.log("Ethers.js transaction object", trx);
})().catch(console.error);

// Supply of DOC or BPRO
(async function () {
	console.log("Supplying DOC to the Tropykus protocol...");
	const trx = await tropykus.supply(Tropykus.DOC, amount, {
		gasLimit: 450000
	});
	console.log("Ethers.js transaction object", trx);
})().catch(console.error);

(async function () {
	console.log("Supplying BPRO to the Tropykus protocol...");
	const trx = await tropykus.supply(Tropykus.BPRO, amount, {
		gasLimit: 450000
	});
	console.log("Ethers.js transaction object", trx);
})().catch(console.error);

// Borrow
(async function () {
	console.log("Borriwng DOC from the Tropykus protocol...");
	const trx = await tropykus.borrow(Tropykus.DOC, amount, {
		gasLimit: 650000
	});
	console.log("Ethers.js transaction object", trx);
})().catch(console.error);

// Redeem
(async function () {
	console.log("Redeeming RBTC from the Tropykus protocol...");
	const trx = await tropykus.redeem(Tropykus.RBTC, amount, {
		gasLimit: 450000
	});
	console.log("Ethers.js transaction object", trx);
})().catch(console.error);

// RepayBorrow
(async function () {
	console.log("Repaying a loan in DOC from the Tropykus protocol...");
	const trx = await tropykus.repayBorrow(Tropykus.RBTC, amount, 0xMyAddress, {
		gasLimit: 450000
	});
	console.log("Ethers.js transaction object", trx);
})().catch(console.error);
```

## API

### Get User Balance

The Tropykus API was integrated in the product in order to easily fetch the data and perform calculations on a user balance. The main method is `getUserBalance`

In order to fetch to balance of a user simply call:

```js
const userAddress = "0x123....";
const chainId = 30; // 30 for RSK Mainnet, 31 for testnet
const userBalance = await tropykus.getUserBalance(userAddress, chainId);
```

### Response Schema

```ts
{
	data: {
		borrows: number,
		deposits: number,
		borrowInterest: number,
		depositsInterest: number,
		market: string
	}
}

```

### Get Markets

In order to fetch the markets information call `getMarkets()`

```js
const chainId = 30; // 30 for RSK Mainnet, 31 for testnet
const markets = await tropykus.getMarkets(chainId);
```

### Response Schema

```ts
{
	data: {
		id: number,
		name: string,
		contract_address: string,
		is_listed: boolean,
		borrow_rate: string,
		total_borrows: string,
		total_supply: string,
		underlying_token_price: string,
		underlying_token_address: string,
		supply_rate: string
	}
}
```

**IMPORTANT**: In order to access the API, the URL has to be whitelisted. Please contact the Tropykus team at contact@tropykus.com to whitelist your URL.

## Transaction Options

Each method that interacts with the blockchain accepts a final optional parameter for overrides, much like [Ethers.js overrides](https://docs.ethers.io/ethers.js/v5-beta/api-contract.html#overrides).

```js
// The options object itself and all options are optional
const trxOptions = {
	mantissa, // Boolean, parameters array arg of 1 ETH would be '1000000000000000000' (true) vs 1 (false)
	abi, // Definition string or an ABI array from a solc build
	provider, // JSON RPC string, Web3 object, or Ethers.js fallback network (string)
	network, // Ethers.js fallback network provider, "provider" has precedence over "network"
	from, // Address that the Ethereum transaction is send from
	gasPrice, // Ethers.js override `Tropykus._ethers.utils.parseUnits('10.0', 'gwei')`
	gasLimit, // Ethers.js override - see https://docs.ethers.io/ethers.js/v5-beta/api-contract.html#overrides
	value, // Number or string
	data, // Number or string
	chainId, // Number
	nonce, // Number
	privateKey, // String, meant to be used with `Tropykus.eth.trx` (server side)
	mnemonic, // String, meant to be used with `Tropykus.eth.trx` (server side)
};
```

## Ethereum Read & Write

This SDK also includes some methods to read and write on the blockchain directly using JSON RPC.

### Read

```js
const Tropykus = require("@tropykus/tropykus-js"); // in Node.js
const kDOCAddress = Tropykus.util.getAddress(Tropykus.kDOC);

(async function () {
	let supplyRatePerBlock = await Tropykus.eth.read(
		kDOCAddress,
		"function supplyRatePerBlock() returns (uint)",
		[], // [optional] parameters
		{} // [optional] call options, provider, network, ethers.js "overrides"
	);

	console.log("DOC supplyRatePerBlock:", supplyRatePerBlock.toString());
})().catch(console.error);
```

### Write

```js
const toAddress = "0xa0df350d2637096571F7A701CBc1C5fdE30dF76A";

(async function () {
	const trx = await Tropykus.eth.trx(
		toAddress,
		"function send() external payable",
		[],
		{
			value: Tropykus._ethers.utils.parseEther("1.0"), // 1 ETH
			provider: window.ethereum, // in a web browser
		}
	);

	const toAddressEthBalance = await Tropykus.eth.getBalance(toAddress);
})().catch(console.error);
```

## Mantissas

Parameters of number values can be plain numbers or their scaled up mantissa values. There is a transaction option boolean to tell the SDK what the developer is passing.

```js
// 1 Dai
await tropykus.borrow(Tropykus.DOC, "1000000000000000000", { mantissa: true });

// `mantissa` defaults to false if it is not specified or if an options object is not passed
await tropykus.borrow(Tropykus.DOC, 1, { mantissa: false });
```

## Test

Tests are available in `./test/*.test.js`. The tests are configured in `./test/index.js`. Methods are tested using a forked chain using ganache-core. A JSON RPC provider URL needs to be configured as an environment variable before running the tests (`MAINNET_PROVIDER_URL`). Archive state must be available to run the tests. For free archive node access, get a provider URL from [Alchemy](http://alchemy.com/).

```
## Run all tests
npm test

## Run a single test (Mocha JS grep option)
npm test -- -g 'runs eth.getBalance'
```

## Build for Node.js & Web Browser

```
git clone git@github.com:@tropykus/tropykus-js.git
cd tropykus-js/
npm install
npm run build
```

### Web Browser Build

```html
<!-- Local build (do `npm install` first) -->
<script type="text/javascript" src="./dist/browser/tropykus.min.js"></script>

<!-- Public NPM -> jsdeliver build -->
<script
	type="text/javascript"
	src="https://cdn.jsdelivr.net/npm/@tropykus/tropykus-js@latest/dist/browser/tropykus.min.js"
></script>
```

### Node.js Build

```js
// Local build (do `npm install` first)
const Tropykus = require("./dist/nodejs/index.js");

// Public NPM build
const Tropykus = require("@tropykus/tropykus-js");
```
