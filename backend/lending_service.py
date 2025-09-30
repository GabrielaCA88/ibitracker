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
    """Tropykus protocol module for APR and price calculations using GraphQL"""
    
    def __init__(self):
        self.protocol_name = "Tropykus"
        self.logger = logging.getLogger(__name__)
        self.graphql_endpoint = "https://graphql1.tropykus.com/"
    
    def get_graphql_data(self, user_address: str) -> Dict[str, Any]:
        """
        Get user data from Tropykus using GraphQL
        
        Args:
            user_address: User wallet address
            
        Returns:
            Dictionary containing user balance data with markets, deposits, borrows, and rates
        """
        try:
            self.logger.info(f"Getting Tropykus data for {user_address}")
            
            query = """
            query FindManyUserBalances($where: User_balancesWhereInput!) {
              findManyUser_balances(where: $where) {
                markets {
                  name
                  supply_rate
                  borrow_rate
                  underlying_token_price
                  underlying_token_name 
                }
                deposits
                brute_deposits
                brute_deposits_historic
                brute_borrows_historic
                borrows
                brute_borrows
                users {
                  address_lowercase
                }
              }
            }
            """
            
            variables = {
                "where": {
                    "users": {
                        "is": {
                            "address_lowercase": { "equals": user_address.lower() }
                        }
                    }
                }
            }
            
            payload = {"query": query, "variables": variables}
            
            response = requests.post(self.graphql_endpoint, json=payload, timeout=30)
            
            if response.status_code != 200:
                self.logger.error(f"GraphQL request failed with status {response.status_code}: {response.text}")
                return {"error": f"GraphQL request failed with status {response.status_code}"}
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"GraphQL request error: {e}")
            return {"error": str(e)}
        except Exception as e:
            self.logger.error(f"Error getting Tropykus data: {e}")
            return {"error": str(e)}
    
    def get_apr_data(self, campaign_ids: List[str], user_address: str = None) -> Dict[str, Any]:
        """Get APR data for the protocol"""
        return {"campaign_breakdowns": {}}
    
    def get_price_data(self, campaign_ids: List[str], user_address: str = None) -> Dict[str, Any]:
        """Get price data for the protocol"""
        return {"token_prices": {}}
    
    def get_user_portfolio_data(self, user_address: str, token_balances: List[Dict] = None) -> Dict[str, Any]:
        """
        Get user portfolio data for Tropykus protocol
        
        Args:
            user_address: User wallet address
            token_balances: List of token balances to find corresponding k-token addresses
            
        Returns:
            Dictionary containing portfolio data with balances, prices, and APR
        """
        try:
            self.logger.info(f"Getting Tropykus portfolio data for user: {user_address}")
            
            # Get GraphQL data
            graphql_data = self.get_graphql_data(user_address)
            if "error" in graphql_data:
                self.logger.info(f"User {user_address} has no Tropykus positions or error occurred: {graphql_data.get('error', 'Unknown error')}")
                return {
                    "protocol": self.protocol_name,
                    "portfolio_items": [],
                    "total_items": 0
                }
            
            # Process user balance data
            user_data = graphql_data.get("data", {}).get("findManyUser_balances", [])
            portfolio_items = []
            
            for market_data in user_data:
                market_name = market_data.get("markets", {}).get("name", "")
                deposits = float(market_data.get("deposits", "0"))
                borrows = float(market_data.get("borrows", "0"))
                
                # Only include markets where user has deposits > 0
                if deposits > 0:
                    underlying_token_name = market_data.get("markets", {}).get("underlying_token_name", market_name)
                    underlying_token_price = float(market_data.get("markets", {}).get("underlying_token_price", "0"))
                    supply_rate = float(market_data.get("markets", {}).get("supply_rate", "0"))
                    
                    # Calculate USD value
                    usd_value = deposits * underlying_token_price
                    
                    # Find the corresponding k-token address from token balances
                    token_address = None
                    if token_balances:
                        for token_balance in token_balances:
                            token_name = token_balance.get("token", {}).get("name", "").lower()
                            token_symbol = token_balance.get("token", {}).get("symbol", "").lower()
                            
                            # Match k-token to underlying token
                            # For DOC market, look for kDOC token
                            # For USDRIF market, look for kUSDRIF token
                            if (token_name.startswith("tropykus") and 
                                token_name.endswith(underlying_token_name.lower()) and
                                "k" in token_name):
                                token_address = token_balance.get("token", {}).get("address_hash")
                                break
                            elif (token_symbol.startswith("k") and 
                                  underlying_token_name.lower() in token_symbol):
                                token_address = token_balance.get("token", {}).get("address_hash")
                                break
                    
                    portfolio_item = {
                        "protocol": "Tropykus",
                        "market_name": market_name,
                        "underlying_token_name": underlying_token_name,
                        "balance": deposits,
                        "price": underlying_token_price,
                        "apr": supply_rate,
                        "usd_value": usd_value,
                        "action": "LEND",
                        "token_address": token_address
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
        self.logger = logging.getLogger(__name__)
        
        # Web3 setup for GetBlock
        self.getblock_api_key = os.getenv("GETBLOCK_API_KEY")
        self.getblock_url = f"https://go.getblock.io/{self.getblock_api_key}"
        self.w3 = Web3(Web3.HTTPProvider(self.getblock_url))
        
        # LayerBank contract details
        self.contract_address = "0x526D06C65777ea6D56D7A1dd47CD79230dDf72e9"
        self.contract_abi = None  # Will be loaded from JSON file
    
    def get_apr_data(self, campaign_ids: List[str], user_address: str = None, token_balances: List[Dict] = None) -> Dict[str, Any]:
        """
        Calculate LayerBank APR (organic + incentivized)
        
        Args:
            campaign_ids: List of campaign IDs from Merkle API
            user_address: User address to check for active LayerBank positions
            token_balances: List of user's token balances from router service
            
        Returns:
            Dictionary containing APR data for LayerBank
        """
        try:
            logger.info(f"LayerBank get_apr_data called with {len(token_balances) if token_balances else 0} token balances")
            # Get organic APR from LayerBank contract via Web3
            organic_data = self._get_organic_apr_from_contract(user_address, token_balances)
            
            # Get both incentivized APR and price data from Merkle opportunities API in single call
            merkle_data = self._get_merkle_data(campaign_ids)
            incentivized_data = {
                "total_apr": merkle_data["total_apr"],
                "breakdown": merkle_data["breakdown"]
            }
            
            # Merge user tokens with campaign data
            merged_data = self._merge_user_tokens_with_campaigns(organic_data, incentivized_data, campaign_ids, token_balances)
            
            apr_data = {
                "protocol": self.protocol_name,
                "campaign_ids": campaign_ids,
                "portfolio_entries": merged_data.get("portfolio_entries", []),
                "last_updated": None
            }
            
            total_entries = len(apr_data['portfolio_entries'])
            logger.info(f"LayerBank APR data: {total_entries} portfolio entries")
            return apr_data
            
        except Exception as e:
            logger.error(f"Error getting LayerBank APR data: {str(e)}")
            return {
                "protocol": self.protocol_name,
                "campaign_ids": campaign_ids,
                "portfolio_entries": [],
                "last_updated": None,
                "error": str(e)
            }
    
    def _get_merkle_data(self, campaign_ids: List[str]) -> Dict[str, Any]:
        """
        Get both incentivized APR and price data from Merkle opportunities API in a single call
        
        Args:
            campaign_ids: List of campaign IDs to query
            
        Returns:
            Dictionary containing both incentivized APR breakdown and price data
        """
        try:
            total_incentivized_apr = 0.0
            breakdown = []
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
                        
                        # Extract required fields (we already have the correct opportunity from campaignId query)
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
                            logger.info(f"Campaign {campaign_id}: Token 0 address: {tokens[0].get('address', 'N/A')}, Token 1 address: {tokens[1].get('address', 'N/A')}")
                            logger.info(f"Campaign {campaign_id}: Set explorer_address to: {explorer_address}")
                        
                        if status == "LIVE" and apr > 0:
                            total_incentivized_apr += apr
                            breakdown.append({
                                "campaign_id": campaign_id,
                                "status": status,
                                "action": action,
                                "apr": apr,
                                "explorer_address": explorer_address,
                                "price": price,
                                "reserve_address": reserve_address
                            })
                            
                            logger.info(f"Campaign {campaign_id}: {apr:.4f}% APR, Status: {status}, Action: {action}, Price: {price}, Reserve: {reserve_address}")
                        
                        # Store price data for price_data method
                        if explorer_address and price > 0:
                            token_prices[explorer_address] = {
                                "price": price,
                                "campaign_id": campaign_id,
                                "reserve_address": reserve_address.lower()
                            }
                    
                except Exception as e:
                    logger.error(f"Error processing campaign {campaign_id}: {str(e)}")
                    continue
            
            return {
                "total_apr": total_incentivized_apr,
                "breakdown": breakdown,
                "token_prices": token_prices
            }
            
        except Exception as e:
            logger.error(f"Error getting Merkle data: {str(e)}")
            return {
                "total_apr": 0.0,
                "breakdown": [],
                "token_prices": {}
            }
    
    def _load_contract_abi(self) -> Dict[str, Any]:
        """
        Load LayerBank contract ABI from JSON file
        
        Returns:
            Dictionary containing contract ABI
        """
        try:
            # Look for ABI file in the same directory
            abi_file_path = os.path.join(os.path.dirname(__file__), "layerbank_abi.json")
            
            if os.path.exists(abi_file_path):
                with open(abi_file_path, 'r') as f:
                    self.contract_abi = json.load(f)
                    logger.info(f"Loaded LayerBank contract ABI from {abi_file_path}")
                    return self.contract_abi
            else:
                logger.error(f"LayerBank ABI file not found at {abi_file_path}")
                return {}
                
        except Exception as e:
            logger.error(f"Error loading LayerBank contract ABI: {str(e)}")
            return {}
    
    def _get_organic_apr_from_contract(self, user_address: str = None, token_balances: List[Dict] = None) -> Dict[str, Any]:
        """
        Get organic APR data from LayerBank contract via Web3
        
        Args:
            user_address: User address to check for active positions
            token_balances: List of user's token balances from router service
            
        Returns:
            Dictionary containing organic APR breakdown
        """
        try:
            # Load contract ABI if not already loaded
            if not self.contract_abi:
                self._load_contract_abi()
            
            if not self.contract_abi:
                logger.error("LayerBank contract ABI not available")
                return {"breakdown": []}
            
            # Check Web3 connection
            if not self.w3.is_connected():
                logger.error("Web3 not connected to GetBlock")
                return {"breakdown": []}
            
            logger.info(f"Connected to Rootstock via GetBlock: {self.w3.is_connected()}")
            
            # Create contract instance
            contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(self.contract_address),
                abi=self.contract_abi
            )
            
            # Extract user's LayerBank token addresses from token balances
            user_layerbank_tokens = set()
            if token_balances:
                for balance in token_balances:
                    token_address = balance.get("token", {}).get("address_hash", "").lower()
                    token = balance.get("token", {})
                    symbol = token.get("symbol", "")
                    name = token.get("name", "")
                    value = balance.get("value", "0")
                    
                    logger.info(f"Checking token: {symbol} ({name}) - {value}")
                    logger.info(f"  Token address: '{token_address}'")
                    
                    if token_address:
                        user_layerbank_tokens.add(token_address)
                        logger.info(f"Found user LayerBank token: {token_address}")
                    else:
                        logger.info(f"  Not adding token: address='{token_address}'")
            
            logger.info(f"User has {len(user_layerbank_tokens)} LayerBank tokens: {list(user_layerbank_tokens)}")
            
            breakdown = []
            found_user_positions = set()
            
            # Get reserves list
            logger.info("Calling getReservesList() on LayerBank contract...")
            reserves_list = contract.functions.getReservesList().call()
            logger.info(f"Found {len(reserves_list)} reserves in LayerBank")
                        
            # Process each reserve until we find matching wallet tokens
            for i, reserve_address in enumerate(reserves_list):
                try:
                    logger.info(f"Processing reserve {i+1}/{len(reserves_list)}: {reserve_address}")
                    
                    # Get reserve data
                    reserve_data = contract.functions.getReserveData(reserve_address).call()
                    
                    # Extract data from ReserveDataLegacy struct
                    # Structure: (configuration, liquidityIndex, currentLiquidityRate, variableBorrowIndex, 
                    #           currentVariableBorrowRate, currentStableBorrowRate, lastUpdateTimestamp, 
                    #           id, aTokenAddress, stableDebtTokenAddress, variableDebtTokenAddress, 
                    #           interestRateStrategyAddress, accruedToTreasury, unbacked, isolationModeTotalDebt)
                    
                    current_liquidity_rate = reserve_data[2]  # currentLiquidityRate
                    current_variable_borrow_rate = reserve_data[4]  # currentVariableBorrowRate
                    a_token_address = reserve_data[8]  # aTokenAddress
                    variable_debt_token_address = reserve_data[10]  # variableDebtTokenAddress
                    last_update_timestamp = reserve_data[6]  # lastUpdateTimestamp
                    
                    # Convert rates from Ray (27 decimals) to percentage
                    # Ray = 10^27, so divide by 10^25 to get percentage (10^27 / 10^25 = 100)
                    liquidity_rate_percentage = (current_liquidity_rate / 10**25) if current_liquidity_rate > 0 else 0.0
                    variable_borrow_rate_percentage = (current_variable_borrow_rate / 10**25) if current_variable_borrow_rate > 0 else 0.0
                    
                    # Convert timestamp to readable format
                    from datetime import datetime
                    last_update = datetime.fromtimestamp(last_update_timestamp).isoformat() if last_update_timestamp > 0 else ""
                    
                    # Check if user has positions in this reserve
                    user_has_position = False
                    if user_layerbank_tokens:
                        a_token_lower = a_token_address.lower()
                        variable_debt_token_lower = variable_debt_token_address.lower()
                        
                        if a_token_lower in user_layerbank_tokens:
                            user_has_position = True
                            found_user_positions.add(a_token_lower)
                            logger.info(f"User has LEND position: {a_token_lower}")
                        
                        if variable_debt_token_lower in user_layerbank_tokens:
                            user_has_position = True
                            found_user_positions.add(variable_debt_token_lower)
                            logger.info(f"User has BORROW position: {variable_debt_token_lower}")
                    
                    # Always include reserves since we only reach this service if user has lending evidence
                    reserve_entry = {
                        "reserve": reserve_address.lower(),
                        "liquidity_rate": liquidity_rate_percentage / 100,  # Convert to decimal for consistency
                        "variable_borrow_rate": variable_borrow_rate_percentage / 100,  # Convert to decimal for consistency
                        "latest_update": last_update,
                        "a_token_address": a_token_address.lower(),
                        "variable_debt_token_address": variable_debt_token_address.lower()
                    }
                    
                    breakdown.append(reserve_entry)
                    
                    logger.info(f"Reserve {reserve_address}: liquidity_rate={liquidity_rate_percentage:.4f}%, variable_borrow_rate={variable_borrow_rate_percentage:.4f}%")
                    logger.info(f"  aToken: {a_token_address}, variableDebtToken: {variable_debt_token_address}")
                    
                    # Stop processing if we found all user's LayerBank positions
                    if user_layerbank_tokens and len(found_user_positions) >= len(user_layerbank_tokens):
                        logger.info(f"Found all user positions ({len(found_user_positions)}/{len(user_layerbank_tokens)}), stopping reserve processing")
                        break
                    
                    # If no user tokens provided, stop after processing first few reserves to save time
                    if not user_layerbank_tokens and i >= 2:
                        logger.info("No user tokens provided, stopping reserve processing after first few reserves")
                        break
                    
                except Exception as e:
                    logger.error(f"Error processing reserve {reserve_address}: {str(e)}")
                    continue
            
            logger.info(f"Processed {len(breakdown)} reserves from LayerBank contract (found {len(found_user_positions)} user positions)")
            return {"breakdown": breakdown}
            
        except Exception as e:
            logger.error(f"Error getting organic APR from contract: {str(e)}")
            return {"breakdown": []}
    
    
    
    def _merge_user_tokens_with_campaigns(self, organic_data: Dict[str, Any], incentivized_data: Dict[str, Any], campaign_ids: List[str], token_balances: List[Dict]) -> Dict[str, Any]:
        """
        Merge user's token positions with campaign data to create portfolio entries
        
        Args:
            organic_data: Organic APR data from GetBlock contract
            incentivized_data: Incentivized APR data from Merkle opportunities
            campaign_ids: List of campaign IDs from Merkle rewards service
            token_balances: List of user's token balances
            
        Returns:
            Dictionary containing merged APR data grouped by campaign ID
        """
        try:
            portfolio_entries = []
            organic_breakdown = organic_data.get("breakdown", [])
            incentivized_breakdown = incentivized_data.get("breakdown", [])
            
            # Create lookup for organic data by token addresses
            organic_lookup = {}
            for org_data in organic_breakdown:
                a_token = org_data.get("a_token_address", "").lower()
                variable_debt_token = org_data.get("variable_debt_token_address", "").lower()
                if a_token:
                    organic_lookup[a_token] = org_data
                if variable_debt_token:
                    organic_lookup[variable_debt_token] = org_data
            
            # Create lookup for incentivized data by explorer_address
            incentivized_lookup = {}
            for inc_data in incentivized_breakdown:
                explorer_address = inc_data.get("explorer_address", "").lower()
                if explorer_address:
                    incentivized_lookup[explorer_address] = inc_data
            
            # Process each user token
            if not token_balances:
                logger.warning(f"No token balances provided for merging. Type: {type(token_balances)}, Value: {token_balances}")
                return {"portfolio_entries": []}
            
            logger.info(f"Processing {len(token_balances)} token balances for merging")
            
            for balance in token_balances:
                token_address = balance.get("token", {}).get("address_hash", "").lower()
                if not token_address:
                    continue
                
                # Get organic data for this token
                organic_data_for_token = organic_lookup.get(token_address)
                if not organic_data_for_token:
                    logger.warning(f"No organic data found for user token: {token_address}")
                    continue
                
                # Get incentivized data for this token
                incentivized_data_for_token = incentivized_lookup.get(token_address)
                
                # Create portfolio entry
                reserve_address = organic_data_for_token["reserve"]
                
                # Determine if this is a LEND or BORROW token based on address match
                a_token_address = organic_data_for_token.get("a_token_address", "").lower()
                variable_debt_token_address = organic_data_for_token.get("variable_debt_token_address", "").lower()
                
                is_lend_token = token_address == a_token_address
                is_borrow_token = token_address == variable_debt_token_address
                
                # Calculate organic APR based on token type
                organic_apr = 0.0
                if is_lend_token:
                    organic_apr = organic_data_for_token.get("liquidity_rate", 0.0) * 100
                elif is_borrow_token:
                    organic_apr = -(organic_data_for_token.get("variable_borrow_rate", 0.0) * 100)
                
                # Get incentivized APR (0 if no campaign data)
                incentivized_apr = 0.0
                price = 0.0
                status = ""
                campaign_id = ""
                
                if incentivized_data_for_token:
                    incentivized_apr = incentivized_data_for_token.get("apr", 0.0)
                    price = incentivized_data_for_token.get("price", 0.0)
                    status = incentivized_data_for_token.get("status", "")
                    campaign_id = incentivized_data_for_token.get("campaign_id", "")
                
                # Calculate total APR
                total_apr = organic_apr + incentivized_apr
                
                # Use first campaign ID if no specific campaign found
                if not campaign_id and campaign_ids:
                    campaign_id = campaign_ids[0]
                
                # Create portfolio entry
                portfolio_entry = {
                    "explorer_address": token_address,
                    "organic_apr": organic_apr,
                    "incentivized_apr": incentivized_apr,
                    "total_apr": total_apr
                }
                
                # Add portfolio entry
                portfolio_entries.append(portfolio_entry)
                
                token_type = "LEND" if is_lend_token else "BORROW" if is_borrow_token else "UNKNOWN"
                logger.info(f"User token {token_address}: {organic_apr:.4f}% organic + {incentivized_apr:.4f}% incentivized = {total_apr:.4f}% total ({token_type})")
            
            return {
                "portfolio_entries": portfolio_entries
            }
            
        except Exception as e:
            logger.error(f"Error merging user tokens with campaigns: {str(e)}")
            return {
                "portfolio_entries": []
            }
    
    def get_price_data(self, campaign_ids: List[str], user_address: str = None) -> Dict[str, Any]:
        """
        Get LayerBank token price data from cached Merkle data
        
        Args:
            campaign_ids: List of campaign IDs from Merkle API
            user_address: User address (not used for LayerBank price data)
            
        Returns:
            Dictionary containing price data for LayerBank tokens
        """
        try:
            # Get price data from the same Merkle API call used for APR data
            merkle_data = self._get_merkle_data(campaign_ids)
            token_prices = merkle_data["token_prices"]
            
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
    
    def get_lending_data_for_address(self, address: str, token_balances: List[Dict] = None) -> Dict[str, Any]:
        """
        Get comprehensive lending data for an address by extracting campaign IDs from Merkle rewards
        
        Args:
            address: Wallet address to get lending data for
            token_balances: List of user's token balances from router service
            
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
            
            # Get lending data using campaign IDs and token balances
            return self.get_lending_data(campaign_ids, address, token_balances)
            
        except Exception as e:
            self.logger.error(f"Error getting lending data for address {address}: {str(e)}")
            return {
                "campaign_ids": [],
                "protocols": {},
                "total_protocols": 0,
                "last_updated": None,
                "error": str(e)
            }
    
    def get_tropykus_portfolio_data(self, address: str, token_balances: List[Dict] = None) -> Dict[str, Any]:
        """
        Get Tropykus portfolio data for an address
        
        Args:
            address: Wallet address to get Tropykus portfolio data for
            token_balances: List of token balances to find corresponding k-token addresses
            
        Returns:
            Dictionary containing Tropykus portfolio data
        """
        try:
            tropykus_module = self.protocols.get("tropykus")
            if not tropykus_module:
                return {"error": "Tropykus module not available"}
            
            return tropykus_module.get_user_portfolio_data(address, token_balances)
            
        except Exception as e:
            self.logger.error(f"Error getting Tropykus portfolio data for address {address}: {str(e)}")
            return {"error": str(e)}
    
    def get_lending_data(self, campaign_ids: List[str], user_address: str = None, token_balances: List[Dict] = None) -> Dict[str, Any]:
        """
        Get comprehensive lending data for all supported protocols
        
        Args:
            campaign_ids: List of campaign IDs from Merkle API
            user_address: User address to filter active positions
            token_balances: List of user's token balances from router service
            
        Returns:
            Dictionary containing APR and price data for all protocols
        """
        try:
            # DEBUG: Print all input parameters
            logger.info(f"=== get_lending_data DEBUG ===")
            logger.info(f"campaign_ids: {campaign_ids}")
            logger.info(f"user_address: {user_address}")
            logger.info(f"token_balances count: {len(token_balances) if token_balances else 0}")
            if token_balances:
                for i, balance in enumerate(token_balances):
                    token = balance.get('token', {})
                    logger.info(f"  token_balances[{i}]: {token.get('symbol', 'N/A')} ({token.get('name', 'N/A')}) - {balance.get('value', '0')}")
            logger.info(f"=== END get_lending_data DEBUG ===")
            lending_data = {
                "campaign_ids": campaign_ids,
                "protocols": {},
                "total_protocols": len(self.protocols),
                "last_updated": None
            }
            
            # Get data from each protocol
            for protocol_name, protocol_module in self.protocols.items():
                try:
                    # Pass token balances to LayerBank module for position filtering
                    if protocol_name == "layerbank" and hasattr(protocol_module, 'get_apr_data'):
                        logger.info(f"Lending service passing {len(token_balances) if token_balances else 0} token balances to LayerBank module")
                        if token_balances:
                            for i, balance in enumerate(token_balances):
                                token = balance.get('token', {})
                                logger.info(f"  Token {i}: {token.get('symbol', 'N/A')} ({token.get('name', 'N/A')}) - {balance.get('value', '0')}")
                        apr_data = protocol_module.get_apr_data(campaign_ids, user_address, token_balances)
                    else:
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
