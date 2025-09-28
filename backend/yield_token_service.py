import requests
import logging
from typing import Dict, List, Any, Optional

class YieldTokenService:
    def __init__(self):
        self.midas_api_base = "https://api-prod.midas.app/api/data"
        self.merkl_api_base = "https://api.merkl.xyz/v4"
        self.logger = logging.getLogger(__name__)
        
        # Midas token addresses mapping
        self.midas_tokens = {
            "0xEF85254Aa4a8490bcC9C02Ae38513Cae8303FB53": "mbtc",  # mBTC
            # Add other Midas tokens as needed
        }
    
    def get_yield_token_data(self, address: str) -> Dict[str, Any]:
        """
        Get yield token data including APR and price for Midas tokens
        """
        try:
            # Get APR data from Midas API
            apr_data = self._get_midas_apr_data()
            
            # Get price data from Merkle API
            price_data = self._get_merkle_price_data(address)
            
            # Process yield tokens
            yield_tokens = []
            
            for token_address, token_symbol in self.midas_tokens.items():
                if token_address in price_data:
                    token_info = {
                        "token_address": token_address,
                        "token_symbol": token_symbol,
                        "price": price_data[token_address]["price"],
                        "apr": apr_data.get(token_symbol, 0) * 100,  # Convert to percentage
                        "protocol": "Midas"
                    }
                    yield_tokens.append(token_info)
            
            return {
                "address": address,
                "yield_tokens": yield_tokens,
                "total_yield_tokens": len(yield_tokens)
            }
            
        except Exception as e:
            self.logger.error(f"Error fetching yield token data: {str(e)}")
            return {
                "address": address,
                "yield_tokens": [],
                "total_yield_tokens": 0,
                "error": str(e)
            }
    
    def _get_midas_apr_data(self) -> Dict[str, float]:
        """
        Get APR data from Midas API
        """
        try:
            response = requests.get(f"{self.midas_api_base}/apys", timeout=10)
            response.raise_for_status()
            
            data = response.json()
            self.logger.info(f"Retrieved Midas APR data: {data}")
            
            return data
            
        except Exception as e:
            self.logger.error(f"Error fetching Midas APR data: {str(e)}")
            return {}
    
    def _get_merkle_price_data(self, address: str) -> Dict[str, Dict[str, Any]]:
        """
        Get price data from Merkle API for the given address
        """
        try:
            response = requests.get(
                f"{self.merkl_api_base}/users/{address}/rewards",
                params={
                    "chainId": "30",
                    "test": "false",
                    "claimableOnly": "true",
                    "breakdownPage": "0"
                },
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            price_data = {}
            
            if isinstance(data, list):
                for chain_data in data:
                    if "rewards" in chain_data:
                        for reward_data in chain_data["rewards"]:
                            token_info = reward_data.get("token", {})
                            token_address = token_info.get("address")
                            if token_address and token_address in self.midas_tokens:
                                price_data[token_address] = {
                                    "price": token_info.get("price", 0),
                                    "symbol": token_info.get("symbol", ""),
                                    "decimals": token_info.get("decimals", 18)
                                }
            
            self.logger.info(f"Retrieved Merkle price data: {price_data}")
            return price_data
            
        except Exception as e:
            self.logger.error(f"Error fetching Merkle price data: {str(e)}")
            return {}
    
    def get_token_apr(self, token_symbol: str) -> float:
        """
        Get APR for a specific token symbol
        """
        try:
            apr_data = self._get_midas_apr_data()
            return apr_data.get(token_symbol, 0) * 100  # Convert to percentage
        except Exception as e:
            self.logger.error(f"Error getting APR for {token_symbol}: {str(e)}")
            return 0
    
    def get_token_price(self, address: str, token_address: str) -> float:
        """
        Get price for a specific token address
        """
        try:
            price_data = self._get_merkle_price_data(address)
            return price_data.get(token_address, {}).get("price", 0)
        except Exception as e:
            self.logger.error(f"Error getting price for {token_address}: {str(e)}")
            return 0


# Example usage and testing
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Test with a real address
    test_address = "0x26d2e5bd1a418aff98523a70ec4d12cb370cdd85"
    
    print(f"Testing YieldTokenService with address: {test_address}")
    
    # Create service instance
    yield_service = YieldTokenService()
    
    # Test getting yield token data
    print(f"\n=== YIELD TOKEN DATA TEST ===")
    yield_data = yield_service.get_yield_token_data(test_address)
    print("Yield Token Data Result:", yield_data)
    
    # Test getting specific token APR
    print(f"\n=== TOKEN APR TEST ===")
    mbtc_apr = yield_service.get_token_apr("mbtc")
    print(f"mBTC APR: {mbtc_apr}%")
    
    # Test getting specific token price
    print(f"\n=== TOKEN PRICE TEST ===")
    mbtc_address = "0xEF85254Aa4a8490bcC9C02Ae38513Cae8303FB53"
    mbtc_price = yield_service.get_token_price(test_address, mbtc_address)
    print(f"mBTC Price: ${mbtc_price}")
