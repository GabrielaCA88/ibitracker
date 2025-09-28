#!/usr/bin/env node

const Tropykus = require("@tropykus/tropykus-js");

async function getUserBalance(userAddress, chainId = 30) {
    try {
        // Initialize Tropykus with RSK mainnet provider
        const tropykus = new Tropykus('https://public-node.rsk.co');
        
        // Get user balance
        const userBalance = await tropykus.getUserBalance(userAddress, chainId);
        
        console.log(JSON.stringify(userBalance, null, 2));
    } catch (error) {
        console.error(JSON.stringify({ error: error.message }));
    }
}

async function getMarkets(chainId = 30) {
    try {
        // Initialize Tropykus with RSK mainnet provider
        const tropykus = new Tropykus('https://public-node.rsk.co');
        
        // Get markets
        const markets = await tropykus.getMarkets(chainId);
        
        console.log(JSON.stringify(markets, null, 2));
    } catch (error) {
        console.error(JSON.stringify({ error: error.message }));
    }
}

// Get command line arguments
const command = process.argv[2];
const arg1 = process.argv[3];
const arg2 = process.argv[4];

// Execute based on command
if (command === 'getUserBalance') {
    getUserBalance(arg1, arg2 ? parseInt(arg2) : 30);
} else if (command === 'getMarkets') {
    getMarkets(arg1 ? parseInt(arg1) : 30);
} else {
    console.error(JSON.stringify({ error: 'Invalid command. Use: getUserBalance or getMarkets' }));
}
