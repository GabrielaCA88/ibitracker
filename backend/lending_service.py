"""
Lending Service - Multi-protocol APR and price calculation service

This service provides APR and price data for various lending protocols
by integrating with their respective APIs and campaign data.
"""

import requests
import logging
import os
import subprocess
import json
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod
from dotenv import load_dotenv
from web3 import Web3

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


class ProtocolModule(ABC):
    """Abstract base class for protocol-specific modules"""
    
    @abstractmethod
    def get_apr_data(self, campaign_ids: List[str]) -> Dict[str, Any]:
        """Get APR data for the protocol"""
        pass
    
    @abstractmethod
    def get_price_data(self, campaign_ids: List[str]) -> Dict[str, Any]:
        """Get price data for the protocol"""
        pass


class TropykusModule(ProtocolModule):
    """Tropykus protocol module for APR and price calculations"""
    
    def __init__(self):
        self.protocol_name = "Tropykus"
        self.chain_id = 30  # RSK Mainnet
        self.logger = logging.getLogger(__name__)
        self.sdk_script_path = os.path.join(os.path.dirname(__file__), "tropykus_sdk.js")
        # Initialize Web3 connection to RSK mainnet
        self.w3 = Web3(Web3.HTTPProvider('https://public-node.rsk.co'))
        # Note: Token addresses will be dynamically retrieved from markets API
    
    def _run_node_script(self, command: str, *args) -> Dict[str, Any]:
        """
        Run the Node.js Tropykus SDK script
        
        Args:
            command: The command to run (getUserBalance, getMarkets, etc.)
            *args: Additional arguments for the command
            
        Returns:
            Dictionary containing the result or error
        """
        try:
            # Build the command
            cmd = ['node', self.sdk_script_path, command] + list(args)
            
            # Run the Node.js script
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=os.path.dirname(self.sdk_script_path)
            )
            
            if result.returncode == 0:
                # Parse JSON output
                return json.loads(result.stdout)
            else:
                # Parse error output
                error_data = json.loads(result.stderr) if result.stderr else {"error": "Unknown error"}
                self.logger.error(f"Node.js script error: {error_data}")
                return error_data
                
        except subprocess.TimeoutExpired:
            self.logger.error("Node.js script timeout")
            return {"error": "Script timeout"}
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error: {e}")
            self.logger.error(f"Script stdout: {result.stdout}")
            self.logger.error(f"Script stderr: {result.stderr}")
            return {"error": f"JSON decode error: {e}"}
        except Exception as e:
            self.logger.error(f"Error running Node.js script: {e}")
            return {"error": str(e)}
    
    def get_user_balance(self, user_address: str) -> Dict[str, Any]:
        """
        Get user balance from Tropykus using the SDK
        
        Args:
            user_address: User wallet address
            
        Returns:
            Dictionary containing user balance data
        """
        try:
            self.logger.info(f"Getting Tropykus user balance for {user_address}")
            result = self._run_node_script("getUserBalance", user_address, str(self.chain_id))
            return result
                
        except Exception as e:
            self.logger.error(f"Error getting Tropykus user balance: {str(e)}")
            return {"error": str(e)}
    
    def get_markets(self) -> Dict[str, Any]:
        """
        Get markets information from Tropykus using the SDK
        
        Returns:
            Dictionary containing markets data
        """
        try:
            self.logger.info("Getting Tropykus markets")
            result = self._run_node_script("getMarkets", str(self.chain_id))
            return result
                
        except Exception as e:
            self.logger.error(f"Error getting Tropykus markets: {str(e)}")
            return {"error": str(e)}
    
    def get_supply_rate_per_block(self, token_address: str) -> Dict[str, Any]:
        """
        Get supply rate per block for a specific token from Tropykus contract
        
        Args:
            token_address: Token contract address
            
        Returns:
            Dictionary containing supply rate data
        """
        try:
            self.logger.info(f"Getting Tropykus supply rate for token {token_address}")
            
            # Check if Web3 is connected
            if not self.w3.is_connected():
                self.logger.error("Web3 not connected to RSK network")
                return {"error": "Web3 connection failed"}
            
            # Contract ABI for supplyRatePerBlock function
            contract_abi = [
                {
                    "inputs": [],
                    "name": "supplyRatePerBlock",
                    "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                    "stateMutability": "view",
                    "type": "function"
                }
            ]
            
            # Create contract instance
            contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=contract_abi
            )
            
            # Call supplyRatePerBlock function
            supply_rate_per_block = contract.functions.supplyRatePerBlock().call()
            
            # Convert from wei to readable format (assuming 18 decimals)
            supply_rate_formatted = supply_rate_per_block / (10 ** 18)
            
            return {
                "token_address": token_address,
                "supply_rate_per_block": str(supply_rate_per_block),
                "supply_rate_formatted": supply_rate_formatted,
                "note": "Successfully retrieved from contract"
            }
            
        except Exception as e:
            self.logger.error(f"Error getting Tropykus supply rate: {str(e)}")
            return {"error": str(e)}
    
    def get_apr_data(self, campaign_ids: List[str], user_address: str = None) -> Dict[str, Any]:
        """
        Get APR data for Tropykus protocol, filtered by active user positions
        
        Args:
            campaign_ids: List of campaign IDs (not used for Tropykus)
            user_address: User address to filter active markets
            
        Returns:
            Dictionary containing APR data
        """
        try:
            self.logger.info(f"Getting Tropykus APR data for user: {user_address}")
            
            # Get user balance to determine active markets
            if user_address:
                user_balance = self.get_user_balance(user_address)
                if "error" in user_balance:
                    return user_balance
                
                # Extract active markets (where user has deposits or borrows > 0)
                active_markets = []
                user_data = user_balance.get("data", [])
                for market_data in user_data:
                    deposits = float(market_data.get("deposits", "0"))
                    borrows = float(market_data.get("borrows", "0"))
                    if deposits > 0 or borrows > 0:
                        active_markets.append(market_data.get("market"))
                
                self.logger.info(f"Active markets for user {user_address}: {active_markets}")
            else:
                # If no user address, return all markets
                active_markets = None
            
            # Get markets data
            markets_data = self.get_markets()
            
            if "error" in markets_data:
                return markets_data
            
            # Process markets data to extract APR information
            all_markets = markets_data.get("data", {}).get("findManyMarkets", [])
            
            # Filter markets based on active user positions
            if active_markets:
                filtered_markets = [market for market in all_markets if market.get("name") in active_markets]
            else:
                filtered_markets = all_markets
            
            # Process markets to extract APR data with both supply and borrow rates
            apr_breakdowns = {}
            for market in filtered_markets:
                market_name = market.get("name", "UNKNOWN")
                contract_address = market.get("contract_address", "").lower()
                supply_rate = float(market.get("supply_rate", "0"))
                borrow_rate = float(market.get("borrow_rate", "0"))
                
                # Create entries for both LEND and BORROW actions
                apr_breakdowns[f"{market_name}_LEND"] = {
                    "reserve_address": contract_address,
                    "action": "LEND",
                    "organic_apr": supply_rate,
                    "incentivized_apr": 0.0,  # Tropykus doesn't have incentivized APR
                    "total_apr": supply_rate,
                    "supply_rate": supply_rate,
                    "borrow_rate": borrow_rate,
                    "market_name": market_name,
                    "contract_address": contract_address
                }
                
                apr_breakdowns[f"{market_name}_BORROW"] = {
                    "reserve_address": contract_address,
                    "action": "BORROW", 
                    "organic_apr": -borrow_rate,  # Borrow rates are negative for users
                    "incentivized_apr": 0.0,  # Tropykus doesn't have incentivized APR
                    "total_apr": -borrow_rate,
                    "supply_rate": supply_rate,
                    "borrow_rate": borrow_rate,
                    "market_name": market_name,
                    "contract_address": contract_address
                }
            
            apr_data = {
                "campaign_breakdowns": apr_breakdowns,
                "protocol": self.protocol_name,
                "markets": {"findManyMarkets": filtered_markets}
            }
            
            self.logger.info(f"Retrieved Tropykus APR data for {len(filtered_markets)} markets")
            return apr_data
            
        except Exception as e:
            self.logger.error(f"Error getting Tropykus APR data: {str(e)}")
            return {"error": str(e)}
    
    def get_price_data(self, campaign_ids: List[str], user_address: str = None) -> Dict[str, Any]:
        """
        Get price data for Tropykus protocol, filtered by active user positions
        
        Args:
            campaign_ids: List of campaign IDs (not used for Tropykus)
            user_address: User address to filter active markets
            
        Returns:
            Dictionary containing price data
        """
        try:
            self.logger.info(f"Getting Tropykus price data for user: {user_address}")
            
            # Get user balance to determine active markets
            if user_address:
                user_balance = self.get_user_balance(user_address)
                if "error" in user_balance:
                    return user_balance
                
                # Extract active markets (where user has deposits or borrows > 0)
                active_markets = []
                user_data = user_balance.get("data", [])
                for market_data in user_data:
                    deposits = float(market_data.get("deposits", "0"))
                    borrows = float(market_data.get("borrows", "0"))
                    if deposits > 0 or borrows > 0:
                        active_markets.append(market_data.get("market"))
                
                self.logger.info(f"Active markets for user {user_address}: {active_markets}")
            else:
                # If no user address, return all markets
                active_markets = None
            
            # Get markets data
            markets_data = self.get_markets()
            
            if "error" in markets_data:
                return markets_data
            
            # Process markets data to extract price information
            all_markets = markets_data.get("data", {}).get("findManyMarkets", [])
            
            # Filter markets based on active user positions
            if active_markets:
                filtered_markets = [market for market in all_markets if market.get("name") in active_markets]
            else:
                filtered_markets = all_markets
            
            token_prices = {}
            for market in filtered_markets:
                if isinstance(market, dict):
                    token_address = market.get("underlying_token_address", "").lower()
                    price = market.get("underlying_token_price", "0")
                    
                    if token_address and price and token_address != "none":
                        token_prices[token_address] = {
                            "price": float(price),
                            "symbol": market.get("name", "UNKNOWN"),
                            "decimals": 18  # Default for most tokens
                        }
            
            price_data = {
                "token_prices": token_prices,
                "protocol": self.protocol_name,
                "markets_count": len(filtered_markets)
            }
            
            self.logger.info(f"Retrieved Tropykus price data for {len(token_prices)} tokens from {len(filtered_markets)} markets")
            return price_data
            
        except Exception as e:
            self.logger.error(f"Error getting Tropykus price data: {str(e)}")
            return {"error": str(e)}
    
    def get_user_portfolio_data(self, user_address: str) -> Dict[str, Any]:
        """
        Get user portfolio data for Tropykus protocol
        
        Args:
            user_address: User wallet address
            
        Returns:
            Dictionary containing portfolio data with balances, prices, and APR
        """
        try:
            self.logger.info(f"Getting Tropykus portfolio data for user: {user_address}")
            
            # Get user balance
            user_balance = self.get_user_balance(user_address)
            if "error" in user_balance:
                # If user has no Tropykus positions, return empty portfolio
                self.logger.info(f"User {user_address} has no Tropykus positions or error occurred: {user_balance.get('error', 'Unknown error')}")
                return {
                    "protocol": self.protocol_name,
                    "portfolio_items": [],
                    "total_items": 0
                }
            
            # Get markets data for prices and APR
            markets_data = self.get_markets()
            if "error" in markets_data:
                return markets_data
            
            # Get APR data
            apr_data = self.get_apr_data([], user_address)
            if "error" in apr_data:
                return apr_data
            
            # Get price data
            price_data = self.get_price_data([], user_address)
            if "error" in price_data:
                return price_data
            
            # Process user balance data
            user_data = user_balance.get("data", [])
            all_markets = markets_data.get("data", {}).get("findManyMarkets", [])
            apr_breakdowns = apr_data.get("campaign_breakdowns", {})
            token_prices = price_data.get("token_prices", {})
            
            portfolio_items = []
            
            for market_data in user_data:
                market_name = market_data.get("market", "")
                deposits = float(market_data.get("deposits", "0"))
                borrows = float(market_data.get("borrows", "0"))
                
                # Only include markets where user has deposits (for portfolio cards)
                if deposits > 0:
                    # Find market info
                    market_info = None
                    for market in all_markets:
                        if market.get("name") == market_name:
                            market_info = market
                            break
                    
                    if market_info:
                        underlying_token_address = market_info.get("underlying_token_address", "").lower()
                        underlying_token_symbol = market_info.get("name", "UNKNOWN")
                        underlying_token_price = float(market_info.get("underlying_token_price", "0"))
                        supply_rate = float(market_info.get("supply_rate", "0"))
                        
                        # Calculate USD value
                        usd_value = deposits * underlying_token_price
                        
                        portfolio_item = {
                            "protocol": "Tropykus",
                            "market_name": market_name,
                            "underlying_token_address": underlying_token_address,
                            "underlying_token_symbol": underlying_token_symbol,
                            "balance": deposits,
                            "price": underlying_token_price,
                            "apr": supply_rate,
                            "usd_value": usd_value,
                            "action": "LEND"
                        }
                        
                        portfolio_items.append(portfolio_item)
            
            return {
                "protocol": self.protocol_name,
                "portfolio_items": portfolio_items,
                "total_items": len(portfolio_items)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting Tropykus portfolio data: {str(e)}")
            return {"error": str(e)}


class LayerBankModule(ProtocolModule):
    """LayerBank protocol module for APR and price calculations"""
    
    def __init__(self):
        self.protocol_name = "LayerBank"
        self.merkle_api_base = "https://api.merkl.xyz/v4"
        self.footprint_api_base = "https://www.footprint.network/api/v1/dataApi/card"
        self.footprint_api_key = os.getenv("FOOTPRINT_API_KEY", "HERE_GOES_THE_PASSWORD")
        self.footprint_card_id = "52841"  # LayerBank card ID
        self.logger = logging.getLogger(__name__)
    
    def get_apr_data(self, campaign_ids: List[str], user_address: str = None) -> Dict[str, Any]:
        """
        Calculate LayerBank APR (organic + incentivized)
        
        Args:
            campaign_ids: List of campaign IDs from Merkle API
            user_address: User address to check for active LayerBank positions
            
        Returns:
            Dictionary containing APR data for LayerBank
        """
        try:
            # Check if user has active LayerBank positions
            has_layerbank_positions = False
            if user_address and campaign_ids:
                # If user has campaign IDs, they likely have LayerBank positions
                has_layerbank_positions = True
                self.logger.info(f"User {user_address} has {len(campaign_ids)} campaign IDs, assuming LayerBank positions")
            elif user_address:
                # No campaign IDs, likely no LayerBank positions
                has_layerbank_positions = False
                self.logger.info(f"User {user_address} has no campaign IDs, assuming no LayerBank positions")
            
            # Only run Footprint API if user has LayerBank positions or no user address provided
            if has_layerbank_positions or not user_address:
                # Get incentivized APR from Merkle opportunities API
                incentivized_data = self._get_incentivized_apr(campaign_ids)
                
                # Get organic APR from Footprint Analytics API
                organic_data = self._get_organic_apr()
                
                # Merge organic and incentivized APR data
                merged_data = self._merge_organic_and_incentivized_apr(organic_data, incentivized_data, campaign_ids)
            else:
                # No LayerBank positions, return empty data
                self.logger.info(f"No LayerBank positions found for user {user_address}, skipping Footprint API call")
                merged_data = {
                    "campaign_breakdowns": {},
                    "protocol": self.protocol_name,
                    "campaign_ids": campaign_ids
                }
            
            apr_data = {
                "protocol": self.protocol_name,
                "campaign_ids": campaign_ids,
                "campaign_breakdowns": merged_data.get("campaign_breakdowns", {}),
                "last_updated": None
            }
            
            total_entries = sum(len(entries) for entries in apr_data['campaign_breakdowns'].values())
            logger.info(f"LayerBank APR data: {total_entries} merged entries across {len(apr_data['campaign_breakdowns'])} campaigns")
            return apr_data
            
        except Exception as e:
            logger.error(f"Error getting LayerBank APR data: {str(e)}")
            return {
                "protocol": self.protocol_name,
                "campaign_ids": campaign_ids,
                "campaign_breakdowns": {},
                "last_updated": None,
                "error": str(e)
            }
    
    def _get_incentivized_apr(self, campaign_ids: List[str]) -> Dict[str, Any]:
        """
        Get incentivized APR data from Merkle opportunities API
        
        Args:
            campaign_ids: List of campaign IDs to query
            
        Returns:
            Dictionary containing incentivized APR breakdown
        """
        try:
            total_incentivized_apr = 0.0
            breakdown = []
            
            # Get opportunities for each campaign ID from Merkle API
            for campaign_id in campaign_ids:
                try:
                    # Call Merkle opportunities API with campaignId query parameter
                    url = f"{self.merkle_api_base}/opportunities/"
                    params = {"campaignId": campaign_id}
                    response = requests.get(url, params=params, timeout=10)
                    
                    if response.status_code == 200:
                        opportunities = response.json()
                        
                        # Handle both single opportunity and list of opportunities
                        if isinstance(opportunities, list) and len(opportunities) > 0:
                            opportunity = opportunities[0]  # Take the first opportunity
                        elif isinstance(opportunities, dict):
                            opportunity = opportunities
                        else:
                            continue
                        
                        # Extract required fields
                        opportunity_id = opportunity.get("id", "")
                        
                        # Check if this opportunity matches our campaign ID
                        # Note: campaign_id from Merkle rewards is hex string, opportunity_id from API is numeric
                        # We'll process the opportunity if it was found via the campaignId query parameter
                        if opportunity_id:  # If we got a valid opportunity, process it
                            # Extract required fields
                            status = opportunity.get("status", "")
                            apr = opportunity.get("apr", 0.0)
                            action = opportunity.get("action", "")  # LEND or BORROW
                            
                            # Extract price and reserve from tokens section
                            tokens = opportunity.get("tokens", [])
                            price = 0.0
                            reserve_address = ""
                            explorer_address = ""
                            
                            if len(tokens) >= 2:
                                # First token has the price and is the lending token
                                price = tokens[0].get("price", 0.0)
                                # Second token has the reserve address
                                reserve_address = tokens[1].get("address", "")
                                
                                # Always use Token 0 address as explorer_address (matches portfolio cards)
                                explorer_address = tokens[0].get("address", "").lower()
                                
                                # Debug logging
                                logger.info(f"Campaign {opportunity_id}: Token 0 address: {tokens[0].get('address', 'N/A')}, Token 1 address: {tokens[1].get('address', 'N/A')}")
                                logger.info(f"Campaign {opportunity_id}: Set explorer_address to: {explorer_address}")
                            
                            if status == "LIVE" and apr > 0:
                                total_incentivized_apr += apr
                                breakdown.append({
                                    "campaign_id": opportunity_id,
                                    "status": status,
                                    "action": action,
                                    "apr": apr,
                                    "explorer_address": explorer_address,
                                    "price": price,
                                    "reserve_address": reserve_address
                                })
                                
                                logger.info(f"Campaign {opportunity_id}: {apr:.4f}% APR, Status: {status}, Action: {action}, Price: {price}, Reserve: {reserve_address}")
                    
                except Exception as e:
                    logger.error(f"Error processing campaign {campaign_id}: {str(e)}")
                    continue
            
            return {
                "total_apr": total_incentivized_apr,
                "breakdown": breakdown
            }
            
        except Exception as e:
            logger.error(f"Error getting incentivized APR: {str(e)}")
            return {
                "total_apr": 0.0,
                "breakdown": []
            }
    
    def _get_organic_apr(self) -> Dict[str, Any]:
        """
        Get organic APR data from Footprint Analytics API
        
        Returns:
            Dictionary containing organic APR breakdown
        """
        try:
            # Query Footprint Analytics API
            url = f"{self.footprint_api_base}/{self.footprint_card_id}/query"
            
            headers = {
                "accept": "application/json",
                "api-key": self.footprint_api_key,
                "content-type": "application/json"
            }
            
            logger.info(f"Fetching organic APR data from Footprint Analytics for card {self.footprint_card_id}")
            response = requests.post(url, headers=headers, timeout=10)
            
            if response.status_code not in [200, 201]:
                logger.error(f"Failed to fetch organic APR data: {response.status_code} - {response.text}")
                return {"total_organic_apr": 0.0, "breakdown": []}
            
            data = response.json()
            rows_data = data.get("data", {}).get("rows", [])
            column_headers = [col.get("display_name", "") for col in data.get("data", {}).get("cols", [])]
            
            logger.info(f"Footprint API response: {len(rows_data)} rows, columns: {column_headers}")
            
            # Expected columns: ['latest_update', 'reserve', 'liquidityrate', 'variableborrowrate']
            total_organic_apr = 0.0
            breakdown = []
            
            for row in rows_data:
                try:
                    # Extract data from row (assuming row is a list in the same order as columns)
                    if len(row) >= 4:
                        latest_update = row[0] if len(row) > 0 else ""
                        reserve = row[1] if len(row) > 1 else ""
                        liquidity_rate = float(row[2]) if len(row) > 2 and row[2] is not None else 0.0
                        variable_borrow_rate = float(row[3]) if len(row) > 3 and row[3] is not None else 0.0
                        
                        # Use liquidity rate as the organic APR (lending rate)
                        # Convert from decimal to percentage (multiply by 100)
                        organic_apr = liquidity_rate * 100
                        
                        if organic_apr > 0:
                            total_organic_apr += organic_apr
                            breakdown.append({
                                "reserve": reserve,
                                "liquidity_rate": liquidity_rate,
                                "variable_borrow_rate": variable_borrow_rate,
                                "organic_apr": organic_apr,
                                "latest_update": latest_update
                            })
                            
                            logger.info(f"Reserve {reserve}: {organic_apr:.4f}% organic APR")
                
                except Exception as e:
                    logger.error(f"Error processing row {row}: {str(e)}")
                    continue
            
            return {
                "total_organic_apr": total_organic_apr,
                "breakdown": breakdown
            }
            
        except Exception as e:
            logger.error(f"Error getting organic APR: {str(e)}")
            return {
                "total_organic_apr": 0.0,
                "breakdown": []
            }
    
    def _merge_organic_and_incentivized_apr(self, organic_data: Dict[str, Any], incentivized_data: Dict[str, Any], campaign_ids: List[str]) -> Dict[str, Any]:
        """
        Merge organic APR data from Footprint with incentivized APR data from Merkle
        
        Args:
            organic_data: Organic APR data from Footprint Analytics
            incentivized_data: Incentivized APR data from Merkle opportunities
            campaign_ids: List of campaign IDs from Merkle rewards service
            
        Returns:
            Dictionary containing merged APR data grouped by campaign ID
        """
        try:
            # Group merged data by campaign ID
            campaign_breakdowns = {}
            
            # Get organic breakdown and incentivized breakdown
            organic_breakdown = organic_data.get("breakdown", [])
            incentivized_breakdown = incentivized_data.get("breakdown", [])
            
            # Create a lookup for organic data by reserve address (ensure lowercase)
            organic_lookup = {}
            for org_data in organic_breakdown:
                reserve_address = org_data.get("reserve", "").lower()
                if reserve_address:
                    # Ensure all addresses in the data are lowercase
                    org_data["reserve"] = reserve_address
                    organic_lookup[reserve_address] = org_data
            
            # Process each organic reserve and create entries for both LEND and BORROW actions
            for org_data in organic_breakdown:
                reserve_address = org_data.get("reserve", "").lower()
                if not reserve_address:
                    continue
                
                # Ensure organic data addresses are lowercase
                org_data["reserve"] = reserve_address
                
                # Find all incentivized campaigns for this reserve
                reserve_incentivized_campaigns = [
                    inc_data for inc_data in incentivized_breakdown 
                    if inc_data.get("reserve_address", "").lower() == reserve_address
                ]
                
                # If no incentivized campaigns, create entries for both LEND and BORROW with 0 incentivized APR
                if not reserve_incentivized_campaigns:
                    # No incentivized data for this reserve, create entries with organic data only
                    # For organic-only entries, we need to find the corresponding explorer_address
                    # from the incentivized data for the same reserve
                    explorer_address = ""
                    for other_reserve, other_campaigns in incentivized_data.items():
                        if other_reserve.lower() == reserve_address.lower():
                            for campaign in other_campaigns:
                                if campaign.get("explorer_address"):
                                    explorer_address = campaign.get("explorer_address", "").lower()
                                    logger.info(f"Found explorer_address for organic-only reserve {reserve_address}: {explorer_address}")
                                    break
                            break
                    
                    if not explorer_address:
                        logger.info(f"No explorer_address found for organic-only reserve {reserve_address}")
                    
                    # Create LEND entry
                    self._create_merged_entry(org_data, None, "LEND", campaign_breakdowns, campaign_ids, explorer_address)
                    # Create BORROW entry  
                    self._create_merged_entry(org_data, None, "BORROW", campaign_breakdowns, campaign_ids, explorer_address)
                else:
                    # Process each incentivized campaign for this reserve
                    for inc_data in reserve_incentivized_campaigns:
                        # Ensure all addresses in the data are lowercase
                        inc_data["reserve_address"] = inc_data.get("reserve_address", "").lower()
                        inc_data["explorer_address"] = inc_data.get("explorer_address", "").lower()
                        
                        action = inc_data.get("action", "LEND")
                        self._create_merged_entry(org_data, inc_data, action, campaign_breakdowns, campaign_ids)
            
            return {
                "campaign_breakdowns": campaign_breakdowns
            }
            
        except Exception as e:
            logger.error(f"Error merging organic and incentivized APR: {str(e)}")
            return {
                "campaign_breakdowns": {}
            }
    
    def _create_merged_entry(self, org_data, inc_data, action, campaign_breakdowns, campaign_ids, explorer_address=None):
        """
        Create a merged entry for a specific action (LEND or BORROW)
        
        Args:
            org_data: Organic data from Footprint
            inc_data: Incentivized data from Merkle (can be None)
            action: "LEND" or "BORROW"
            campaign_breakdowns: Dictionary to add the entry to
            campaign_ids: List of campaign IDs from Merkle rewards
        """
        try:
            reserve_address = org_data.get("reserve", "").lower()
            
            # Determine which APR to use based on action
            organic_apr = 0.0
            if action == "LEND":
                # Use liquidity rate for lending (convert from decimal to percentage)
                organic_apr = org_data.get("liquidity_rate", 0.0) * 100
            elif action == "BORROW":
                # Use variable borrow rate for borrowing (convert from decimal to percentage)
                # For BORROW, organic APR should be negative (cost)
                organic_apr = -(org_data.get("variable_borrow_rate", 0.0) * 100)
            else:
                # Default to liquidity rate if action is unknown (convert from decimal to percentage)
                organic_apr = org_data.get("liquidity_rate", 0.0) * 100
            
            # Get incentivized APR (0 if no incentivized data)
            incentivized_apr = inc_data.get("apr", 0.0) if inc_data else 0.0
            
            # Calculate total APR for this reserve
            # For LEND: organic + incentivized (both are positive)
            # For BORROW: organic is negative, incentivized is positive (incentivized reduces the cost)
            total_reserve_apr = organic_apr + incentivized_apr
            
            # Find the corresponding campaign ID from Merkle rewards
            # We need to match the numeric campaign_id from incentivized data with the hex campaign_ids
            numeric_campaign_id = inc_data.get("campaign_id", "") if inc_data else ""
            merkle_campaign_id = ""
            
            # For now, we'll use the first campaign_id if we can't match
            # TODO: Implement proper matching logic if needed
            if campaign_ids:
                merkle_campaign_id = campaign_ids[0]  # Use first campaign ID for now
            
            # Create merged entry (ensure all addresses are lowercase)
            merged_entry = {
                "reserve_address": reserve_address,
                "action": action,
                "organic_apr": organic_apr,
                "incentivized_apr": incentivized_apr,
                "total_apr": total_reserve_apr,
                "liquidity_rate": org_data.get("liquidity_rate", 0.0),
                "variable_borrow_rate": org_data.get("variable_borrow_rate", 0.0),
                "latest_update": org_data.get("latest_update", ""),
                "campaign_id": merkle_campaign_id,  # Use Merkle campaign ID
                "status": inc_data.get("status", "") if inc_data else "",
                "explorer_address": explorer_address or (inc_data.get("explorer_address", "").lower() if inc_data else reserve_address),
                "price": inc_data.get("price", 0.0) if inc_data else 0.0
            }
            
            # Group by campaign ID
            if merkle_campaign_id not in campaign_breakdowns:
                campaign_breakdowns[merkle_campaign_id] = []
            campaign_breakdowns[merkle_campaign_id].append(merged_entry)
            
            logger.info(f"Merged {reserve_address}: {organic_apr:.4f}% organic + {incentivized_apr:.4f}% incentivized = {total_reserve_apr:.4f}% total ({action})")
            
        except Exception as e:
            logger.error(f"Error creating merged entry: {str(e)}")
    
    def get_price_data(self, campaign_ids: List[str], user_address: str = None) -> Dict[str, Any]:
        """
        Get LayerBank token price data from Merkle opportunities API
        
        Args:
            campaign_ids: List of campaign IDs from Merkle API
            user_address: User address (not used for LayerBank price data)
            
        Returns:
            Dictionary containing price data for LayerBank tokens
        """
        try:
            token_prices = {}
            
            # Get opportunities for each campaign ID from Merkle API
            for campaign_id in campaign_ids:
                try:
                    # Call Merkle opportunities API with campaignId query parameter
                    url = f"{self.merkle_api_base}/opportunities/"
                    params = {"campaignId": campaign_id}
                    response = requests.get(url, params=params, timeout=10)
                    
                    if response.status_code == 200:
                        opportunities = response.json()
                        
                        # Handle both single opportunity and list of opportunities
                        if isinstance(opportunities, list) and len(opportunities) > 0:
                            opportunity = opportunities[0]  # Take the first opportunity
                        elif isinstance(opportunities, dict):
                            opportunity = opportunities
                        else:
                            continue
                        
                        # Extract price and reserve from tokens section
                        opportunity_id = opportunity.get("id", "")
                        
                        # Check if this opportunity matches our campaign ID
                        # Note: campaign_id from Merkle rewards is hex string, opportunity_id from API is numeric
                        # We'll process the opportunity if it was found via the campaignId query parameter
                        if opportunity_id:  # If we got a valid opportunity, process it
                            # Extract price and reserve from tokens section
                            tokens = opportunity.get("tokens", [])
                            action = opportunity.get("action", "")  # LEND or BORROW
                            
                            if len(tokens) >= 2:
                                # First token has the price
                                price = tokens[0].get("price", 0.0)
                                # Second token has the reserve address
                                reserve_address = tokens[1].get("address", "")
                                
                                # Always use Token 0 address as explorer_address (matches portfolio cards)
                                explorer_address = tokens[0].get("address", "").lower()
                                
                                if explorer_address and price > 0:
                                    # Store price by explorer_address (the token that matches portfolio cards)
                                    token_prices[explorer_address] = {
                                        "price": price,
                                        "campaign_id": opportunity_id,
                                        "reserve_address": reserve_address.lower()
                                    }
                    
                except Exception as e:
                    logger.error(f"Error getting price for campaign {campaign_id}: {str(e)}")
                    continue
            
            price_data = {
                "protocol": self.protocol_name,
                "token_prices": token_prices,
                "campaign_ids": campaign_ids,
                "last_updated": None
            }
            
            logger.info(f"LayerBank price data retrieved for {len(token_prices)} tokens from {len(campaign_ids)} campaigns")
            return price_data
            
        except Exception as e:
            logger.error(f"Error getting LayerBank price data: {str(e)}")
            return {
                "protocol": self.protocol_name,
                "token_prices": {},
                "campaign_ids": campaign_ids,
                "error": str(e)
            }


class LendingService:
    """Main lending service that coordinates multiple protocol modules"""
    
    def __init__(self):
        self.protocols = {
            "layerbank": LayerBankModule(),
            "tropykus": TropykusModule(),
            # Future protocols can be added here
            # "aave": AaveModule(),
            # "compound": CompoundModule(),
        }
        self.logger = logging.getLogger(__name__)
    
    def get_lending_data_for_address(self, address: str) -> Dict[str, Any]:
        """
        Get comprehensive lending data for an address by extracting campaign IDs from Merkle rewards
        
        Args:
            address: Wallet address to get lending data for
            
        Returns:
            Dictionary containing APR and price data for all protocols
        """
        try:
            # Import here to avoid circular imports
            from merkle_rewards_service import MerkleRewardsService
            
            # Get campaign IDs from Merkle rewards
            merkle_service = MerkleRewardsService()
            merkle_rewards = merkle_service.get_address_rewards_summary(address)
            campaign_ids = merkle_rewards.get("campaign_ids", [])
            
            # Get lending data using campaign IDs
            return self.get_lending_data(campaign_ids)
            
        except Exception as e:
            self.logger.error(f"Error getting lending data for address {address}: {str(e)}")
            return {
                "campaign_ids": [],
                "protocols": {},
                "total_protocols": 0,
                "last_updated": None,
                "error": str(e)
            }
    
    def get_lending_data(self, campaign_ids: List[str], user_address: str = None) -> Dict[str, Any]:
        """
        Get comprehensive lending data for all supported protocols
        
        Args:
            campaign_ids: List of campaign IDs from Merkle API
            user_address: User address to filter active positions
            
        Returns:
            Dictionary containing APR and price data for all protocols
        """
        try:
            lending_data = {
                "campaign_ids": campaign_ids,
                "protocols": {},
                "total_protocols": len(self.protocols),
                "last_updated": None
            }
            
            # Get data from each protocol
            for protocol_name, protocol_module in self.protocols.items():
                try:
                    apr_data = protocol_module.get_apr_data(campaign_ids, user_address)
                    price_data = protocol_module.get_price_data(campaign_ids, user_address)
                    
                    lending_data["protocols"][protocol_name] = {
                        "apr": apr_data,
                        "price": price_data
                    }
                    
                except Exception as e:
                    self.logger.error(f"Error processing {protocol_name}: {str(e)}")
                    lending_data["protocols"][protocol_name] = {
                        "error": str(e)
                    }
            
            self.logger.info(f"Retrieved lending data for {len(campaign_ids)} campaigns across {len(self.protocols)} protocols")
            return lending_data
            
        except Exception as e:
            self.logger.error(f"Error getting lending data: {str(e)}")
            return {
                "campaign_ids": campaign_ids,
                "protocols": {},
                "error": str(e)
            }
    
    def get_protocol_data(self, protocol_name: str, campaign_ids: List[str], user_address: str = None) -> Dict[str, Any]:
        """
        Get data for a specific protocol
        
        Args:
            protocol_name: Name of the protocol (e.g., "layerbank")
            campaign_ids: List of campaign IDs from Merkle API
            user_address: User address to filter active positions
            
        Returns:
            Dictionary containing APR and price data for the specific protocol
        """
        try:
            if protocol_name not in self.protocols:
                return {
                    "error": f"Protocol '{protocol_name}' not supported",
                    "available_protocols": list(self.protocols.keys())
                }
            
            protocol_module = self.protocols[protocol_name]
            apr_data = protocol_module.get_apr_data(campaign_ids, user_address)
            price_data = protocol_module.get_price_data(campaign_ids, user_address)
            
            return {
                "protocol": protocol_name,
                "apr": apr_data,
                "price": price_data
            }
            
        except Exception as e:
            self.logger.error(f"Error getting {protocol_name} data: {str(e)}")
            return {
                "protocol": protocol_name,
                "error": str(e)
            }


# Example usage and testing
if __name__ == "__main__":
    lending_service = LendingService()
    
    # Test with real address to get actual campaign IDs
    test_address = "0x7966d2547f2cc8dde74ebaeca8ce3cb1d5cae337"
    
    # Import merkle rewards service to get real campaign IDs
    try:
        from merkle_rewards_service import MerkleRewardsService
        merkle_service = MerkleRewardsService()
        campaign_ids = merkle_service._extract_campaign_ids(test_address)
        
        print(f"Found {len(campaign_ids)} campaign IDs for address {test_address}: {campaign_ids}")
        
        if campaign_ids:
            # Get data for all protocols with real campaign IDs
            all_data = lending_service.get_lending_data(campaign_ids, test_address)
            print("All protocols data:", all_data)
            
            # Get data for specific protocol
            layerbank_data = lending_service.get_protocol_data("layerbank", campaign_ids, test_address)
            print("LayerBank data:", layerbank_data)
        else:
            print(f"No campaign IDs found for address {test_address}")
            # Test with empty campaign IDs
            all_data = lending_service.get_lending_data([], test_address)
            print("All protocols data (no campaigns):", all_data)
            
    except ImportError:
        print("MerkleRewardsService not available, testing with empty campaign IDs")
        # Test with empty campaign IDs
        all_data = lending_service.get_lending_data([])
        print("All protocols data (no campaigns):", all_data)
    
    # Test Tropykus module directly
    print("\n=== TROPKUS MODULE TESTING ===")
    tropykus_module = lending_service.protocols["tropykus"]
    
    # Test user balance
    test_address = "0x7966d2547f2cc8dde74ebaeca8ce3cb1d5cae337"
    print(f"\nTesting Tropykus getUserBalance for address: {test_address}")
    user_balance = tropykus_module.get_user_balance(test_address)
    print("User Balance Result:", user_balance)
    
    # Test markets
    print(f"\nTesting Tropykus getMarkets:")
    markets = tropykus_module.get_markets()
    print("Markets Result:", markets)
    
    # Test supply rate per block with real Tropykus contract
    cusdrif_address = "0xDdf3CE45fcf080DF61ee61dac5Ddefef7ED4F46C"  # CUSDRIF contract
    print(f"\nTesting Tropykus getSupplyRatePerBlock for CUSDRIF: {cusdrif_address}")
    supply_rate = tropykus_module.get_supply_rate_per_block(cusdrif_address)
    print("Supply Rate Result:", supply_rate)
    
    # Test APR and price data with user address
    print(f"\nTesting Tropykus APR data:")
    apr_data = tropykus_module.get_apr_data([], test_address)  # Empty campaign IDs for Tropykus
    print("APR Data Result:", apr_data)
    
    print(f"\nTesting Tropykus Price data:")
    price_data = tropykus_module.get_price_data([], test_address)  # Empty campaign IDs for Tropykus
    print("Price Data Result:", price_data)
