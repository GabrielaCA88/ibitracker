#!/usr/bin/env node

// Debug: Check what's actually in the package
const fs = require('fs');
const path = require('path');

const packagePath = path.join(__dirname, 'node_modules', '@tropykus', 'tropykus-js');
console.log('Package path:', packagePath);
console.log('Package exists:', fs.existsSync(packagePath));

if (fs.existsSync(packagePath)) {
    console.log('Package contents:', fs.readdirSync(packagePath));
    
    const distPath = path.join(packagePath, 'dist');
    if (fs.existsSync(distPath)) {
        console.log('Dist contents:', fs.readdirSync(distPath));
        
        const nodejsPath = path.join(distPath, 'nodejs');
        if (fs.existsSync(nodejsPath)) {
            console.log('Nodejs contents:', fs.readdirSync(nodejsPath));
        }
    }
    
    const packageJsonPath = path.join(packagePath, 'package.json');
    if (fs.existsSync(packageJsonPath)) {
        const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
        console.log('Package.json main:', packageJson.main);
        console.log('Package.json files:', packageJson.files);
    }
}

// Try different import paths
let Tropykus;
try {
    Tropykus = require("@tropykus/tropykus-js");
    console.log('Success with @tropykus/tropykus-js');
} catch (e1) {
    try {
        Tropykus = require("@tropykus/tropykus-js/dist/index");
        console.log('Success with @tropykus/tropykus-js/dist/index');
    } catch (e2) {
        try {
            Tropykus = require("@tropykus/tropykus-js/lib/index");
            console.log('Success with @tropykus/tropykus-js/lib/index');
        } catch (e3) {
            try {
                Tropykus = require("@tropykus/tropykus-js/src/index");
                console.log('Success with @tropykus/tropykus-js/src/index');
            } catch (e4) {
                console.error(JSON.stringify({ 
                    error: "Cannot find @tropykus/tropykus-js module", 
                    attempts: [e1.message, e2.message, e3.message, e4.message] 
                }));
                process.exit(1);
            }
        }
    }
}

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
