class IBITracker {
    constructor() {
        // Use relative URLs for API calls when served from same domain
        this.apiBaseUrl = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
            ? 'http://localhost:8001' 
            : '';
        this.currentAddress = null;
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadDefaultAddress();
    }

    bindEvents() {
        const searchBtn = document.getElementById('searchBtn');
        const addressInput = document.getElementById('addressInput');
        const downloadBtn = document.getElementById('downloadBtn');

        searchBtn.addEventListener('click', () => this.searchAddress());
        addressInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.searchAddress();
            }
        });
        downloadBtn.addEventListener('click', () => this.downloadExcel());
    }

    loadDefaultAddress() {
        // Load the default address that has Merkle rewards for testing
        const defaultAddress = '0x26d2e5bd1a418aff98523a70ec4d12cb370cdd85';
        document.getElementById('addressInput').value = defaultAddress;
    }

    async searchAddress() {
        const address = document.getElementById('addressInput').value.trim();
        
        if (!address) {
            this.showError('Please enter a valid address');
            return;
        }

        if (!this.isValidAddress(address)) {
            this.showError('Please enter a valid Ethereum/Rootstock address');
            return;
        }

        this.currentAddress = address;
        await this.loadAddressData(address);
    }

    isValidAddress(address) {
        return /^0x[a-fA-F0-9]{40}$/.test(address);
    }

    async loadAddressData(address) {
        this.showLoading(true);
        this.hideError();
        this.hideAllStates();

        try {
            const response = await fetch(`${this.apiBaseUrl}/api/address-info/${address}`);
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to fetch address data');
            }

            const data = await response.json();
            this.displayAddressInfo(data);
            this.displayTokenBalances(data.token_balances, data.nft_valuations, data.merkle_rewards, data.yield_tokens);

        } catch (error) {
            console.error('Error loading address data:', error);
            this.showError(`Failed to load address data: ${error.message}`);
        } finally {
            this.showLoading(false);
        }
    }

    displayAddressInfo(data) {
        document.getElementById('addressDisplay').textContent = data.address;
        document.getElementById('addressDisplay').classList.remove('hidden');
        document.getElementById('addressStats').classList.remove('hidden');
        document.getElementById('downloadBtn').classList.remove('hidden');
        this.currentAddress = data.address;
    }

    async downloadExcel() {
        if (!this.currentAddress) {
            this.showError('No address data available for download');
            return;
        }

        try {
            const downloadBtn = document.getElementById('downloadBtn');
            const originalText = downloadBtn.innerHTML;
            
            // Show loading state
            downloadBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Generating...';
            downloadBtn.disabled = true;

            // Create download link
            const downloadUrl = `${this.apiBaseUrl}/api/export-excel/${this.currentAddress}`;
            
            // Create temporary link element
            const link = document.createElement('a');
            link.href = downloadUrl;
            link.download = `portfolio_${this.currentAddress.slice(0, 8)}_${new Date().toISOString().slice(0, 10)}.xlsx`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

            // Reset button state
            downloadBtn.innerHTML = originalText;
            downloadBtn.disabled = false;

        } catch (error) {
            console.error('Error downloading Excel file:', error);
            this.showError('Failed to download Excel file');
            
            // Reset button state
            const downloadBtn = document.getElementById('downloadBtn');
            downloadBtn.innerHTML = '<i class="fas fa-download mr-2"></i>Export Excel';
            downloadBtn.disabled = false;
        }
    }

    displayTokenBalances(tokenBalances, nftValuations = [], merkleRewards = [], yieldTokensData = []) {
        const tokenList = document.getElementById('tokenList');
        const portfolioList = document.getElementById('portfolioList');
        tokenList.innerHTML = '';
        portfolioList.innerHTML = '';

        if (tokenBalances.length === 0 && nftValuations.length === 0 && merkleRewards.length === 0 && yieldTokensData.length === 0) {
            this.showEmptyState('No token balances, NFTs, rewards, or yield tokens found for this address');
            return;
        }

        // Separate yield tokens from regular tokens
        const { yieldTokens: regularYieldTokens, regularTokens } = this.separateTokens(tokenBalances);

        // Combine Midas data: merge Blockscout balance with yield token service data
        const combinedYieldTokens = this.combineMidasData(regularYieldTokens, yieldTokensData);

        // Calculate values including NFTs, Merkle rewards, and yield tokens
        this.calculateAndDisplayValues(tokenBalances, combinedYieldTokens, regularTokens, nftValuations, merkleRewards, yieldTokensData);

        // Display regular tokens in Wallet
        if (regularTokens.length > 0) {
            regularTokens.forEach(tokenData => {
                const tokenCard = this.createTokenCard(tokenData);
                tokenList.appendChild(tokenCard);
            });
            document.getElementById('tokenBalances').classList.remove('hidden');
        }

        // Display yield tokens in Portfolio
        if (combinedYieldTokens.length > 0) {
            combinedYieldTokens.forEach(tokenData => {
                const portfolioCard = this.createPortfolioCard(tokenData);
                portfolioList.appendChild(portfolioCard);
            });
        }

        // Display NFTs in Portfolio
        if (nftValuations.length > 0) {
            nftValuations.forEach(nftData => {
                const nftCard = this.createNFTCard(nftData);
                portfolioList.appendChild(nftCard);
            });
        }

        // Display Merkle rewards in Portfolio
        if (merkleRewards.length > 0) {
            merkleRewards.forEach(rewardData => {
                const rewardCard = this.createMerkleRewardCard(rewardData);
                portfolioList.appendChild(rewardCard);
            });
        }

        // Show portfolio section if there are yield tokens, NFTs, or rewards
        if (combinedYieldTokens.length > 0 || nftValuations.length > 0 || merkleRewards.length > 0) {
            document.getElementById('portfolioBalances').classList.remove('hidden');
        }
    }

    calculateAndDisplayValues(allTokens, yieldTokens, regularTokens, nftValuations = [], merkleRewards = [], yieldTokensData = []) {
        // Calculate total tokens (ERC-20s only, excluding native rBTC)
        const erc20Tokens = allTokens.filter(token => token.token.type !== 'native');
        const totalTokens = erc20Tokens.length;
        
        // Calculate total value (sum of all tokens with prices)
        let totalValue = 0;
        let productiveValue = 0;
        let idleValue = 0;
        
        allTokens.forEach(tokenData => {
            const balance = parseFloat(tokenData.value) / Math.pow(10, parseInt(tokenData.token.decimals) || 18);
            const price = tokenData.token.exchange_rate ? parseFloat(tokenData.token.exchange_rate) : 0;
            const tokenValue = balance * price;
            
            if (tokenValue > 0) {
                totalValue += tokenValue;
                
                // Check if it's a yield token
                const isYieldToken = yieldTokens.some(yt => yt.token.address_hash === tokenData.token.address_hash);
                if (isYieldToken) {
                    productiveValue += tokenValue;
                } else {
                    idleValue += tokenValue;
                }
            }
        });

        // Add NFT values to productive value (NFTs are considered productive assets)
        nftValuations.forEach(nftData => {
            const nftValue = parseFloat(nftData.total_value_usd) || 0;
            if (nftValue > 0) {
                totalValue += nftValue;
                productiveValue += nftValue;
            }
        });

        // Add Merkle rewards to productive value (rewards are considered productive assets)
        merkleRewards.forEach(rewardData => {
            const rewardValue = parseFloat(rewardData.usd_value) || 0;
            if (rewardValue > 0) {
                totalValue += rewardValue;
                productiveValue += rewardValue;
            }
        });

        // Add yield tokens data to productive value (yield tokens are considered productive assets)
        yieldTokensData.forEach(yieldTokenData => {
            // Note: yield tokens from the service don't have balance info, only price and APR
            // We'll need to get the balance from the regular token balances
            const matchingToken = allTokens.find(token => 
                token.token.address_hash && 
                token.token.address_hash.toLowerCase() === yieldTokenData.token_address.toLowerCase()
            );
            
            if (matchingToken) {
                const balance = parseFloat(matchingToken.value) / Math.pow(10, parseInt(matchingToken.token.decimals) || 18);
                const price = yieldTokenData.price || 0;
                const tokenValue = balance * price;
                
                if (tokenValue > 0) {
                    totalValue += tokenValue;
                    productiveValue += tokenValue;
                }
            }
        });
        
        // Update the display
        document.getElementById('totalTokens').textContent = totalTokens;
        document.getElementById('totalValue').textContent = `$${this.formatUSDValue(totalValue)}`;
        document.getElementById('productiveValue').textContent = `$${this.formatUSDValue(productiveValue)}`;
        document.getElementById('idleValue').textContent = `$${this.formatUSDValue(idleValue)}`;
    }

    createTokenCard(tokenData) {
        try {
            const { token, value } = tokenData;
            
            const line = document.createElement('div');
            line.className = 'grid grid-cols-5 gap-4 items-center py-3 px-4 border-b border-gray-100 last:border-b-0 hover:bg-gray-50 transition-colors token-line';
            line.setAttribute('data-token-address', token.address_hash || '');
            
            const balance = this.formatTokenBalance(value, token.decimals);
            const symbol = token.symbol || 'Unknown';
            const name = token.name || 'Unknown Token';
            const iconUrl = token.icon_url;
            const price = token.exchange_rate;
            
            // Calculate USD value
            const balanceNum = parseFloat(value) / Math.pow(10, parseInt(token.decimals) || 18);
            const priceNum = price ? parseFloat(price) : 0;
            const usdValue = balanceNum * priceNum;
            
            // Determine price source
            const priceSource = this.getPriceSource(token);
            
            line.innerHTML = `
                    <div class="flex items-center space-x-3">
                        <div class="token-icon flex items-center justify-center">
                            ${iconUrl ? 
                                `<img src="${iconUrl}" alt="${symbol}" class="w-6 h-6 rounded-full">` : 
                                `<i class="fas fa-coins text-white text-sm"></i>`
                            }
                        </div>
                </div>
                <div class="text-left">
                    <div class="font-semibold text-gray-800">${name}</div>
                </div>
                <div class="text-center">
                    <div class="font-semibold text-gray-800">${balance}</div>
                </div>
                <div class="text-center">
                                ${price ? `
                        <div class="flex items-center justify-center space-x-1">
                            <span class="font-semibold text-gray-800">$${this.formatPrice(price)}</span>
                            <i class="fas fa-info-circle text-blue-500 cursor-help" 
                                           title="Price source: ${priceSource}"></i>
                        </div>
                    ` : '<div class="font-semibold text-gray-800">N/A</div>'}
                    </div>
                <div class="text-center">
                    <div class="font-semibold text-gray-800">
                            ${usdValue > 0 ? `$${this.formatUSDValue(usdValue)}` : 'N/A'}
                    </div>
                </div>
            `;
            
            return line;
        } catch (error) {
            console.error('Error in createTokenCard:', error);
            const errorLine = document.createElement('div');
            errorLine.className = 'bg-red-50 border border-red-200 rounded-lg p-4';
            errorLine.innerHTML = `<div class="text-red-700">Error creating token line: ${error.message}</div>`;
            return errorLine;
        }
    }

    formatTokenBalance(value, decimals) {
        const numValue = parseFloat(value);
        const divisor = Math.pow(10, parseInt(decimals) || 18);
        const balance = numValue / divisor;
        
        if (balance >= 1000000) {
            return (balance / 1000000).toFixed(2) + 'M';
        } else if (balance >= 1000) {
            return (balance / 1000).toFixed(2) + 'K';
        } else if (balance >= 1) {
            return balance.toFixed(4);
        } else {
            return balance.toFixed(8);
        }
    }

    formatPrice(price) {
        const numPrice = parseFloat(price);
        if (numPrice >= 1000) {
            return numPrice.toLocaleString(undefined, { maximumFractionDigits: 0 });
        } else if (numPrice >= 1) {
            return numPrice.toFixed(2);
        } else {
            return numPrice.toFixed(6);
        }
    }

    formatUSDValue(value) {
        if (value >= 1000000) {
            return (value / 1000000).toFixed(2) + 'M';
        } else if (value >= 1000) {
            return (value / 1000).toFixed(2) + 'K';
        } else if (value >= 1) {
            return value.toFixed(2);
        } else {
            return value.toFixed(4);
        }
    }

    separateTokens(tokenBalances) {
        const yieldKeywords = ['Midas', 'LayerBank', 'Avalon'];
        const uniswapNftContracts = [
            '0x0389879e0156033202c44bf784ac18fc02edee4f',
            '0x19b683a2f45012318d9b2ae1280d68d3ec54d663',
            '0x9d9386c042f194b460ec424a1e57acde25f5c4b1'
        ];
        const yieldTokens = [];
        const regularTokens = [];

        tokenBalances.forEach(tokenData => {
            const tokenName = tokenData.token.name || '';
            const tokenSymbol = tokenData.token.symbol || '';
            const tokenAddress = tokenData.token.address_hash || '';
            
            // Check if token is a yield-generating token by name/symbol
            const isYieldTokenByName = yieldKeywords.some(keyword => 
                tokenName.toLowerCase().includes(keyword.toLowerCase()) ||
                tokenSymbol.toLowerCase().includes(keyword.toLowerCase())
            );
            
            // Check if token is a Uniswap NFT by contract address
            const isUniswapNft = uniswapNftContracts.some(contract => 
                tokenAddress.toLowerCase() === contract.toLowerCase()
            );

            if (isYieldTokenByName || isUniswapNft) {
                yieldTokens.push(tokenData);
            } else {
                regularTokens.push(tokenData);
            }
        });

        return { yieldTokens, regularTokens };
    }

    combineMidasData(regularYieldTokens, yieldTokensData) {
        const combinedTokens = [];
        
        regularYieldTokens.forEach(tokenData => {
            const tokenAddress = tokenData.token.address_hash || '';
            
            // Check if this is a Midas token that has yield data
            const matchingYieldData = yieldTokensData.find(yieldData => 
                yieldData.token_address.toLowerCase() === tokenAddress.toLowerCase()
            );
            
            if (matchingYieldData) {
                // Combine Blockscout data with yield service data
                const combinedToken = {
                    ...tokenData,
                    yieldData: {
                        price: matchingYieldData.price,
                        apr: matchingYieldData.apr,
                        protocol: matchingYieldData.protocol
                    }
                };
                combinedTokens.push(combinedToken);
            } else {
                // Keep regular yield tokens without yield service data
                combinedTokens.push(tokenData);
            }
        });
        
        return combinedTokens;
    }

    createPortfolioCard(tokenData) {
        const { token, value, yieldData } = tokenData;
        
        const card = document.createElement('div');
        card.className = 'bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg shadow-md p-4 card-hover border-l-4 border-blue-500';
        
        const balance = this.formatTokenBalance(value, token.decimals);
        const symbol = token.symbol || 'Unknown';
        const name = token.name || 'Unknown Token';
        const iconUrl = token.icon_url;
        
        // Use yield data price if available, otherwise use exchange_rate
        const price = yieldData ? yieldData.price : token.exchange_rate;
        const apr = yieldData ? yieldData.apr : null;
        const protocol = yieldData ? yieldData.protocol : this.getProtocol(token);
        
        // Calculate USD value
        const balanceNum = parseFloat(value) / Math.pow(10, parseInt(token.decimals) || 18);
        const priceNum = price ? parseFloat(price) : 0;
        const usdValue = balanceNum * priceNum;
        
        const protocolLogo = this.getProtocolLogo(protocol);
        const protocolLink = this.getProtocolLink(protocol);
        
        card.innerHTML = `
            <div class="grid grid-cols-5 gap-4 items-center">
                <div class="flex items-center space-x-3">
                    <div class="token-icon flex items-center justify-center">
                        ${protocolLogo}
                    </div>
                    <div>
                        <div class="flex items-center space-x-2">
                            <span class="font-semibold text-gray-800">${protocol}</span>
                            <span class="cursor-pointer text-sm hover:text-blue-600 transition-colors" onclick="window.open('${protocolLink}', '_blank')" title="Visit ${protocol}">🔗</span>
                        </div>
                        <div class="text-sm text-gray-600">${name}</div>
                    </div>
                </div>
                <div class="text-center">
                    <div class="text-sm text-gray-500">Holdings</div>
                    <div class="font-semibold text-gray-800">${balance}</div>
                </div>
                <div class="text-center">
                    <div class="text-sm text-gray-500">Price</div>
                    <div class="font-semibold text-gray-800">$${this.formatPrice(price)}</div>
                </div>
                <div class="text-center">
                    <div class="text-sm text-gray-500">APR</div>
                    <div class="font-semibold text-gray-800">${apr ? `${apr.toFixed(2)}%` : 'N/A'}</div>
                </div>
                <div class="text-center">
                    <div class="text-sm text-gray-500">USD Value</div>
                    <div class="font-semibold text-gray-800">$${this.formatUSDValue(usdValue)}</div>
                </div>
            </div>
        `;
        
        return card;
    }

    createNFTCard(nftData) {
        const card = document.createElement('div');
        card.className = 'bg-gradient-to-r from-purple-50 to-pink-50 rounded-lg shadow-md p-4 card-hover border-l-4 border-purple-500 cursor-pointer';
        
        const nftName = nftData.name || `NFT #${nftData.nft_id}`;
        const tokenName = nftData.token_name || 'Unknown NFT';
        const tokenSymbol = nftData.token_symbol || 'NFT';
        const usdValue = parseFloat(nftData.total_value_usd) || 0;
        const uncollectedFees = parseFloat(nftData.uncollected_usd_fees) || 0;
        
        // Determine protocol based on token name
        const protocol = this.getNFTProtocol(nftData);
        const protocolLogo = this.getProtocolLogo(protocol);
        const protocolLink = this.getProtocolLink(protocol);
        
        // Add click handler for protocol link
        card.addEventListener('click', () => {
            window.open(protocolLink, '_blank');
        });
        
        card.innerHTML = `
            <div class="flex items-center justify-between">
                <div class="flex items-center space-x-3">
                    <div class="token-icon flex items-center justify-center bg-purple-500">
                        ${protocolLogo}
                    </div>
                    <div class="flex-1">
                        <div class="flex items-center space-x-2">
                            <span class="font-semibold text-gray-800">${protocol}</span>
                            <span class="text-sm text-gray-600">${nftName}</span>
                            <i class="fas fa-external-link-alt text-xs text-gray-400"></i>
                        </div>
                        <div class="text-sm text-gray-500">${tokenName} (${tokenSymbol})</div>
                        ${uncollectedFees > 0 ? `
                            <div class="text-xs text-green-600 mt-1">
                                <i class="fas fa-coins mr-1"></i>
                                Uncollected Fees: $${this.formatUSDValue(uncollectedFees)}
                            </div>
                        ` : ''}
                    </div>
                </div>
                <div class="text-right">
                    <div class="text-lg font-bold text-gray-800">
                        $${this.formatUSDValue(usdValue)}
                    </div>
                    <div class="text-xs text-gray-500">USD Value</div>
                </div>
            </div>
        `;
        
        return card;
    }

    createMerkleRewardCard(rewardData) {
        const card = document.createElement('div');
        card.className = 'bg-gradient-to-r from-green-50 to-emerald-50 rounded-lg shadow-md p-4 card-hover border-l-4 border-green-500';
        
        const amountFormatted = rewardData.amount_formatted || '0';
        const tokenSymbol = rewardData.token.symbol || 'Unknown';
        const tokenPrice = rewardData.token.price || 0;
        const usdValue = parseFloat(rewardData.usd_value) || 0;
        
        const protocolLogo = this.getProtocolLogo('Merkle');
        const protocolLink = this.getProtocolLink('Merkle');
        
        card.innerHTML = `
            <div class="flex items-center justify-between">
                <div class="flex items-center space-x-3">
                    <div class="token-icon flex items-center justify-center bg-green-500">
                        ${protocolLogo}
                    </div>
                    <div class="flex-1">
                        <div class="flex items-center space-x-2">
                            <span class="font-semibold text-gray-800">Merkle Rewards</span>
                            <span class="cursor-pointer text-sm hover:text-blue-600 transition-colors" onclick="window.open('${protocolLink}', '_blank')" title="Visit Merkle">🔗</span>
                            <span class="text-sm text-gray-600">${amountFormatted}</span>
                        </div>
                        <div class="text-sm text-gray-500">${tokenSymbol} @ $${this.formatPrice(tokenPrice)}</div>
                        <div class="text-xs text-green-600 mt-1">
                            <i class="fas fa-coins mr-1"></i>
                            Claimable Reward
                        </div>
                    </div>
                </div>
                <div class="text-right">
                    <div class="text-lg font-bold text-gray-800">
                        $${this.formatUSDValue(usdValue)}
                    </div>
                    <div class="text-xs text-gray-500">USD Value</div>
                </div>
            </div>
        `;
        
        return card;
    }

    createYieldTokenCard(yieldTokenData) {
        const card = document.createElement('div');
        card.className = 'bg-gradient-to-r from-yellow-50 to-orange-50 rounded-lg shadow-md p-4 card-hover border-l-4 border-yellow-500 cursor-pointer';
        
        const tokenSymbol = yieldTokenData.token_symbol || 'Unknown';
        const protocol = yieldTokenData.protocol || 'Unknown';
        const price = yieldTokenData.price || 0;
        const apr = yieldTokenData.apr || 0;
        
        const protocolLogo = this.getProtocolLogo(protocol);
        const protocolLink = this.getProtocolLink(protocol);
        
        // Add click handler for protocol link
        card.addEventListener('click', () => {
            window.open(protocolLink, '_blank');
        });
        
        // Get token balance from regular token balances
        let balance = '0';
        let usdValue = 0;
        
        // Try to find the matching token in the current token balances
        const allTokenElements = document.querySelectorAll('.token-line');
        for (let tokenElement of allTokenElements) {
            const tokenAddress = tokenElement.getAttribute('data-token-address');
            if (tokenAddress && tokenAddress.toLowerCase() === yieldTokenData.token_address.toLowerCase()) {
                const balanceElement = tokenElement.querySelector('.token-balance');
                if (balanceElement) {
                    balance = balanceElement.textContent.trim();
                    const balanceNum = parseFloat(balance.replace(/,/g, ''));
                    usdValue = balanceNum * price;
                }
                break;
            }
        }
        
        card.innerHTML = `
            <div class="flex items-center justify-between">
                <div class="flex items-center space-x-3">
                    <div class="token-icon flex items-center justify-center">
                        ${protocolLogo}
                    </div>
                    <div class="flex-1">
                        <div class="flex items-center space-x-2">
                            <span class="font-semibold text-gray-800">${protocol}</span>
                            <span class="text-sm text-gray-600">${tokenSymbol}</span>
                            <i class="fas fa-external-link-alt text-xs text-gray-400"></i>
                        </div>
                        <div class="text-sm text-gray-500">Holdings: ${balance} ${tokenSymbol}</div>
                        <div class="text-sm text-gray-500">Price: $${this.formatPrice(price)}</div>
                        <div class="text-sm text-gray-500">APR: ${apr.toFixed(2)}%</div>
                    </div>
                </div>
                <div class="text-right">
                    <div class="text-lg font-bold text-gray-800">
                        $${this.formatUSDValue(usdValue)}
                    </div>
                    <div class="text-xs text-gray-500">USD Value</div>
                </div>
            </div>
        `;
        
        return card;
    }

    getProtocolLogo(protocol) {
        switch (protocol.toLowerCase()) {
            case 'uniswap':
                return `<img src="assets/logos/Uniswap_icon_pink.png" alt="Uniswap" class="protocol-logo">`;
            case 'merkle':
                return `<img src="assets/logos/merkl-symbol-light-theme-margin.png" alt="Merkle" class="protocol-logo">`;
            case 'midas':
                return `<img src="assets/logos/midas_symbol-blue_transparent-bcg.png" alt="Midas" class="protocol-logo">`;
            case 'layerbank':
                return `<img src="assets/logos/LayerBank.svg" alt="LayerBank" class="protocol-logo">`;
            case 'avalon':
                return `<img src="assets/logos/ICON_light BG.png" alt="Avalon" class="protocol-logo">`;
            default:
                return `<i class="fas fa-chart-line text-white text-sm"></i>`;
        }
    }

    getProtocolLink(protocol) {
        switch (protocol.toLowerCase()) {
            case 'uniswap':
                return 'https://oku.trade/info/rootstock/overview';
            case 'merkle':
                return 'https://app.merkl.xyz/?chain=30';
            case 'midas':
                return 'https://midas.app/mbtc';
            case 'layerbank':
                return 'https://app.layerbank.finance/bank?chain=rootstock';
            case 'avalon':
                return 'https://avalon.finance/';
            default:
                return '#';
        }
    }

    getNFTProtocol(nftData) {
        const tokenName = nftData.token_name || '';
        const tokenSymbol = nftData.token_symbol || '';
        
        if (tokenName.toLowerCase().includes('uniswap') || tokenSymbol.toLowerCase().includes('uni')) {
            return 'Uniswap';
        } else if (tokenName.toLowerCase().includes('midas') || tokenSymbol.toLowerCase().includes('midas')) {
            return 'Midas';
        } else if (tokenName.toLowerCase().includes('layerbank') || tokenSymbol.toLowerCase().includes('layerbank')) {
            return 'LayerBank';
        } else if (tokenName.toLowerCase().includes('avalon') || tokenSymbol.toLowerCase().includes('avalon')) {
            return 'Avalon';
        } else {
            return 'NFT Protocol';
        }
    }

    getProtocol(token) {
        const tokenName = token.name || '';
        const tokenSymbol = token.symbol || '';
        const tokenAddress = token.address_hash || '';
        
        const uniswapNftContracts = [
            '0x0389879e0156033202c44bf784ac18fc02edee4f',
            '0x19b683a2f45012318d9b2ae1280d68d3ec54d663',
            '0x9d9386c042f194b460ec424a1e57acde25f5c4b1'
        ];
        
        // Check if it's a Uniswap NFT by contract address
        const isUniswapNft = uniswapNftContracts.some(contract => 
            tokenAddress.toLowerCase() === contract.toLowerCase()
        );
        
        if (isUniswapNft) {
            return 'Uniswap';
        } else if (tokenName.toLowerCase().includes('midas') || tokenSymbol.toLowerCase().includes('midas')) {
            return 'Midas';
        } else if (tokenName.toLowerCase().includes('layerbank') || tokenSymbol.toLowerCase().includes('layerbank')) {
            return 'LayerBank';
        } else if (tokenName.toLowerCase().includes('avalon') || tokenSymbol.toLowerCase().includes('avalon')) {
            return 'Avalon';
        } else {
            return 'Yield Protocol';
        }
    }

    getPriceSource(token) {
        try {
            // Determine price source based on token characteristics
            if (token.symbol === 'rBTC' || token.name?.includes('Rootstock Smart Bitcoin')) {
                return 'Blockscout';
            } else if (token.symbol === 'WRBTC' || token.name?.includes('Wrapped Rootstock Smart Bitcoin')) {
                return 'Blockscout';
            } else if (token.symbol === 'mBTC' || token.name?.includes('Midas')) {
                return 'Midas Protocol';
            } else if (token.symbol?.includes('lRoo') || token.name?.includes('LayerBank')) {
                return 'LayerBank';
            } else {
                return 'Blockscout';
            }
        } catch (error) {
            console.error('Error in getPriceSource:', error);
            return 'Unknown';
        }
    }

    showLoading(show) {
        const loadingState = document.getElementById('loadingState');
        if (show) {
            loadingState.classList.remove('hidden');
        } else {
            loadingState.classList.add('hidden');
        }
    }

    showError(message) {
        const errorState = document.getElementById('errorState');
        const errorMessage = document.getElementById('errorMessage');
        errorMessage.textContent = message;
        errorState.classList.remove('hidden');
    }

    hideError() {
        document.getElementById('errorState').classList.add('hidden');
    }

    showEmptyState(message) {
        const emptyState = document.getElementById('emptyState');
        emptyState.innerHTML = `
            <i class="fas fa-coins text-6xl text-gray-300 mb-4"></i>
            <h3 class="text-xl font-semibold text-gray-600 mb-2">No Tokens Found</h3>
            <p class="text-gray-500">${message}</p>
        `;
        emptyState.classList.remove('hidden');
    }

    hideAllStates() {
        document.getElementById('addressDisplay').classList.add('hidden');
        document.getElementById('addressStats').classList.add('hidden');
        document.getElementById('downloadBtn').classList.add('hidden');
        document.getElementById('tokenBalances').classList.add('hidden');
        document.getElementById('portfolioBalances').classList.add('hidden');
        document.getElementById('emptyState').classList.add('hidden');
    }
}

// Initialize the application when the DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new IBITracker();
});