"""
Lending Service - Multi-protocol APR and price calculation service

This service provides APR and price data for various lending protocols
by integrating with their respective APIs and campaign data.
"""

import requests
import logging
import os
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod
from dotenv import load_dotenv

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


class LayerBankModule(ProtocolModule):
    """LayerBank protocol module for APR and price calculations"""
    
    def __init__(self):
        self.protocol_name = "LayerBank"
        self.merkle_api_base = "https://api.merkl.xyz/v4"
        self.footprint_api_base = "https://www.footprint.network/api/v1/dataApi/card"
        self.footprint_api_key = os.getenv("FOOTPRINT_API_KEY", "HERE_GOES_THE_PASSWORD")
        self.footprint_card_id = "52841"  # LayerBank card ID
    
    def get_apr_data(self, campaign_ids: List[str]) -> Dict[str, Any]:
        """
        Calculate LayerBank APR (organic + incentivized)
        
        Args:
            campaign_ids: List of campaign IDs from Merkle API
            
        Returns:
            Dictionary containing APR data for LayerBank
        """
        try:
            # Get incentivized APR from Merkle opportunities API
            incentivized_data = self._get_incentivized_apr(campaign_ids)
            
            # Get organic APR from Footprint Analytics API
            organic_data = self._get_organic_apr()
            
            # Merge organic and incentivized APR data
            merged_data = self._merge_organic_and_incentivized_apr(organic_data, incentivized_data, campaign_ids)
            
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
                                # First token has the price
                                price = tokens[0].get("price", 0.0)
                                # Second token has the reserve address
                                reserve_address = tokens[1].get("address", "")
                                
                                # Always use Token 0 address as explorer_address (matches portfolio cards)
                                explorer_address = tokens[0].get("address", "").lower()
                            
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
                    # Create LEND entry
                    self._create_merged_entry(org_data, None, "LEND", campaign_breakdowns, campaign_ids)
                    # Create BORROW entry  
                    self._create_merged_entry(org_data, None, "BORROW", campaign_breakdowns, campaign_ids)
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
    
    def _create_merged_entry(self, org_data, inc_data, action, campaign_breakdowns, campaign_ids):
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
                "explorer_address": inc_data.get("explorer_address", "").lower() if inc_data else "",
                "price": inc_data.get("price", 0.0) if inc_data else 0.0
            }
            
            # Group by campaign ID
            if merkle_campaign_id not in campaign_breakdowns:
                campaign_breakdowns[merkle_campaign_id] = []
            campaign_breakdowns[merkle_campaign_id].append(merged_entry)
            
            logger.info(f"Merged {reserve_address}: {organic_apr:.4f}% organic + {incentivized_apr:.4f}% incentivized = {total_reserve_apr:.4f}% total ({action})")
            
        except Exception as e:
            logger.error(f"Error creating merged entry: {str(e)}")
    
    def get_price_data(self, campaign_ids: List[str]) -> Dict[str, Any]:
        """
        Get LayerBank token price data from Merkle opportunities API
        
        Args:
            campaign_ids: List of campaign IDs from Merkle API
            
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
    
    def get_lending_data(self, campaign_ids: List[str]) -> Dict[str, Any]:
        """
        Get comprehensive lending data for all supported protocols
        
        Args:
            campaign_ids: List of campaign IDs from Merkle API
            
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
                    apr_data = protocol_module.get_apr_data(campaign_ids)
                    price_data = protocol_module.get_price_data(campaign_ids)
                    
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
    
    def get_protocol_data(self, protocol_name: str, campaign_ids: List[str]) -> Dict[str, Any]:
        """
        Get data for a specific protocol
        
        Args:
            protocol_name: Name of the protocol (e.g., "layerbank")
            campaign_ids: List of campaign IDs from Merkle API
            
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
            apr_data = protocol_module.get_apr_data(campaign_ids)
            price_data = protocol_module.get_price_data(campaign_ids)
            
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
    
    # Test with sample campaign IDs
    test_campaign_ids = ["12345", "67890"]
    
    # Get data for all protocols
    all_data = lending_service.get_lending_data(test_campaign_ids)
    print("All protocols data:", all_data)
    
    # Get data for specific protocol
    layerbank_data = lending_service.get_protocol_data("layerbank", test_campaign_ids)
    print("LayerBank data:", layerbank_data)
