"""
Router Service for Yield Tracker
Optimizes service calls by gathering evidence first and only running necessary services
"""

import requests
import logging
from typing import Dict, Any, List, Optional
from nft_service import NFTService
from merkle_rewards_service import MerkleRewardsService
from yield_token_service import YieldTokenService
from lending_service import LendingService

logger = logging.getLogger(__name__)

class RouterService:
    def __init__(self):
        self.nft_service = None
        self.merkle_service = None
        self.yield_service = None
        self.lending_service = None
        
        # API endpoints
        self.ROOTSTOCK_API_BASE = "https://rootstock.blockscout.com/api/v2"
        self.ROOTSTOCK_EXPLORER_API = "https://be.explorer.rootstock.io/api/v3"
    
    def _is_positive(self, value: str) -> bool:
        """Check if a token value is positive"""
        try:
            return float(value) > 0
        except (ValueError, TypeError):
            return False
    
    def _looks_like_lending_receipt(self, balance: dict) -> bool:
        """
        Heuristics that avoid hardcoding addresses:
          - Token type must be ERC-20.
          - Symbol/name patterns commonly used by money markets (kRBTC, kUSDT, lBTC, lUSDC, etc.).
        """
        token = balance.get("token", {})
        if token.get("type") != "ERC-20":
            return False
        sym = (token.get("symbol") or "").lower()
        name = (token.get("name") or "").lower()
        patterns = ("k", "c", "a", "l", "variable")  # kTokens (Tropykus), cTokens, aTokens, lTokens (LayerBank), variable debt tokens
        return (
            self._is_positive(balance.get("value", 0))
            and (sym.startswith(patterns) or "ktoken" in name or "ltoken" in name or "atoken" in name or "layerbank" in name or "avalon" in name or "tropykus" in name or "variable" in name or "debt" in name)
        )
    
    def gather_evidence(self, address: str, token_balances: List[Dict]) -> Dict[str, bool]:
        """
        Gather evidence about what services are needed for this address
        
        Args:
            address: Wallet address to analyze
            token_balances: List of token balances from Blockscout
            
        Returns:
            Dictionary with evidence flags
        """
        evidence = {
            "has_yield_token": False,
            "has_lending": False,
            "has_nfts": False,
            "has_merkle_rewards": False
        }
        
        try:
            # Check for yield tokens in token balances
            yield_keywords = ["midas"]
            for balance in token_balances:
                token_name = balance.get("token", {}).get("name", "").lower()
                if any(keyword in token_name for keyword in yield_keywords):
                    evidence["has_yield_token"] = True
                    break
            
            # Check for lending receipt tokens using heuristics
            for balance in token_balances:
                if self._looks_like_lending_receipt(balance):
                    evidence["has_lending"] = True
                    break
            
            # Check for NFTs in token balances
            for balance in token_balances:
                if balance.get("token", {}).get("type") == "ERC-721":
                    evidence["has_nfts"] = True
                    break
            
            # Quick check for Merkle rewards (lightweight API call)
            try:
                merkle_url = f"https://api.merkl.xyz/v4/users/{address}/rewards"
                params = {
                    "chainId": "30",
                    "test": "false",
                    "claimableOnly": "true",
                    "breakdownPage": "0"
                }
                response = requests.get(merkle_url, params=params, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    # Merkle API returns a list, not a dict
                    if isinstance(data, list) and len(data) > 0:
                        # Check if any chain has rewards
                        for chain_data in data:
                            if chain_data.get("rewards") and len(chain_data["rewards"]) > 0:
                                evidence["has_merkle_rewards"] = True
                                break
            except Exception as e:
                logger.warning(f"Could not check Merkle rewards for {address}: {str(e)}")
            
            logger.info(f"Evidence gathered for {address}: {evidence}")
            return evidence
            
        except Exception as e:
            logger.error(f"Error gathering evidence for {address}: {str(e)}")
            # Return all True as fallback to ensure all services run
            return {
                "has_yield_token": True,
                "has_lending": True,
                "has_nfts": True,
                "has_merkle_rewards": True
            }
    
    def initialize_services(self, evidence: Dict[str, bool]) -> None:
        """
        Initialize only the services that are needed based on evidence
        
        Args:
            evidence: Dictionary with evidence flags
        """
        try:
            if evidence["has_nfts"] and not self.nft_service:
                logger.info("Initializing NFT service")
                self.nft_service = NFTService()
            
            if evidence["has_merkle_rewards"] and not self.merkle_service:
                logger.info("Initializing Merkle rewards service")
                self.merkle_service = MerkleRewardsService()
            
            if evidence["has_yield_token"] and not self.yield_service:
                logger.info("Initializing yield token service")
                self.yield_service = YieldTokenService()
            
            if evidence["has_lending"] and not self.lending_service:
                logger.info("Initializing lending service")
                self.lending_service = LendingService()
                
        except Exception as e:
            logger.error(f"Error initializing services: {str(e)}")
    
    def get_nft_data(self, address: str) -> List[Dict]:
        """Get NFT data if service is available"""
        if self.nft_service:
            try:
                return self.nft_service.get_address_nft_valuations(address)
            except Exception as e:
                logger.error(f"Error getting NFT data: {str(e)}")
        return []
    
    def get_merkle_data(self, address: str) -> Dict[str, Any]:
        """Get Merkle rewards data if service is available"""
        if self.merkle_service:
            try:
                return self.merkle_service.get_address_rewards_summary(address)
            except Exception as e:
                logger.error(f"Error getting Merkle data: {str(e)}")
        return {"rewards": [], "total_rewards": 0, "total_usd_value": 0}
    
    def get_yield_data(self, address: str) -> Dict[str, Any]:
        """Get yield token data if service is available"""
        if self.yield_service:
            try:
                return self.yield_service.get_yield_token_data(address)
            except Exception as e:
                logger.error(f"Error getting yield data: {str(e)}")
        return {"yield_tokens": [], "total_yield_tokens": 0}
    
    def get_lending_data(self, address: str) -> Dict[str, Any]:
        """Get lending data if service is available"""
        if self.lending_service:
            try:
                data = self.lending_service.get_lending_data_for_address(address)
                # Ensure the structure has campaign_breakdowns
                if isinstance(data, dict) and "campaign_breakdowns" not in data:
                    data["campaign_breakdowns"] = {}
                return data
            except Exception as e:
                logger.error(f"Error getting lending data: {str(e)}")
        return {"campaign_breakdowns": {}}
    
    def get_tropykus_data(self, address: str) -> Dict[str, Any]:
        """Get Tropykus portfolio data if service is available"""
        if self.lending_service:
            try:
                return self.lending_service.get_tropykus_portfolio_data(address)
            except Exception as e:
                logger.error(f"Error getting Tropykus data: {str(e)}")
        return {"protocol": "Tropykus", "portfolio_items": [], "total_items": 0}
    
    def process_address(self, address: str, token_balances: List[Dict]) -> Dict[str, Any]:
        """
        Main processing function that gathers evidence and runs only necessary services
        
        Args:
            address: Wallet address to process
            token_balances: List of token balances from Blockscout
            
        Returns:
            Dictionary with all processed data
        """
        try:
            # Step 1: Gather evidence
            evidence = self.gather_evidence(address, token_balances)
            
            # Step 2: Initialize only needed services
            self.initialize_services(evidence)
            
            # Step 3: Run services in parallel where possible
            results = {
                "address": address,
                "evidence": evidence,
                "nft_valuations": [],
                "merkle_rewards": {"rewards": [], "total_rewards": 0, "total_usd_value": 0},
                "yield_tokens": {"yield_tokens": [], "total_yield_tokens": 0},
                "lending_portfolio": {
                    "layerbank": {"campaign_breakdowns": {}},
                    "tropykus": {"protocol": "Tropykus", "portfolio_items": [], "total_items": 0}
                }
            }
            
            # Run services based on evidence
            if evidence["has_nfts"]:
                results["nft_valuations"] = self.get_nft_data(address)
            
            if evidence["has_merkle_rewards"]:
                results["merkle_rewards"] = self.get_merkle_data(address)
            
            if evidence["has_yield_token"]:
                results["yield_tokens"] = self.get_yield_data(address)
            
            if evidence["has_lending"]:
                results["lending_portfolio"]["layerbank"] = self.get_lending_data(address)
                results["lending_portfolio"]["tropykus"] = self.get_tropykus_data(address)
            
            logger.info(f"Successfully processed {address} with evidence: {evidence}")
            return results
            
        except Exception as e:
            logger.error(f"Error processing address {address}: {str(e)}")
            # Return empty results on error
            return {
                "address": address,
                "evidence": {"has_yield_token": False, "has_lending": False, "has_nfts": False, "has_merkle_rewards": False},
                "nft_valuations": [],
                "merkle_rewards": {"rewards": [], "total_rewards": 0, "total_usd_value": 0},
                "yield_tokens": {"yield_tokens": [], "total_yield_tokens": 0},
                "lending_portfolio": {
                    "layerbank": {"campaign_breakdowns": {}},
                    "tropykus": {"protocol": "Tropykus", "portfolio_items": [], "total_items": 0}
                }
            }
