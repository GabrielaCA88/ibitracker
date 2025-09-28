import requests
from typing import List, Dict, Any, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NFTService:
    """
    Service for retrieving and valuing NFT positions from Rootstock blockchain
    """
    
    def __init__(self):
        self.blockscout_api_base = "https://rootstock.blockscout.com/api/v2"
        self.icarus_api_base = "https://omni.icarus.tools/rootstock/cush/analyticsPosition"
    
    def get_nft_data(self, address: str) -> List[Dict[str, Any]]:
        """
        Fetch NFT data for a given address from Rootstock Blockscout API
        
        Args:
            address: Ethereum address to fetch NFTs for
            
        Returns:
            List of NFT data dictionaries containing id and token address_hash
        """
        try:
            # Convert address to lowercase for API consistency
            lowercase_address = address.lower()
            url = f"{self.blockscout_api_base}/addresses/{lowercase_address}/nft?type=ERC-721%2CERC-404%2CERC-1155"
            
            logger.info(f"Fetching NFT data for address: {lowercase_address}")
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch NFT data: {response.status_code} - {response.text}")
                return []
            
            data = response.json()
            nft_items = data.get("items", [])
            
            logger.info(f"Found {len(nft_items)} NFT items")
            
            # Extract relevant data
            nft_data = []
            for item in nft_items:
                nft_info = {
                    "id": item.get("id"),
                    "address_hash": item.get("token", {}).get("address_hash"),
                    "name": item.get("name"),
                    "token_type": item.get("token_type"),
                    "token_name": item.get("token", {}).get("name"),
                    "token_symbol": item.get("token", {}).get("symbol")
                }
                nft_data.append(nft_info)
            
            return nft_data
            
        except requests.RequestException as e:
            logger.error(f"Request error fetching NFT data: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Error fetching NFT data: {str(e)}")
            return []
    
    def get_nft_valuation(self, token_id: str, contract_address: str) -> Optional[Dict[str, Any]]:
        """
        Get NFT position valuation from Icarus Tools API
        
        Args:
            token_id: The NFT token ID
            contract_address: The contract address of the NFT
            
        Returns:
            Dictionary containing valuation data or None if not found
        """
        try:
            payload = {
                "params": [
                    {
                        "token_id": int(token_id)
                    }
                ]
            }
            
            logger.info(f"Fetching valuation for token_id: {token_id}, contract: {contract_address}")
            response = requests.post(self.icarus_api_base, json=payload, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch valuation: {response.status_code} - {response.text}")
                return None
            
            data = response.json()
            
            # Look for the position with matching owner address
            lowercase_contract_address = contract_address.lower()
            
            if "result" in data and "position" in data["result"]:
                position = data["result"]["position"]
                position_events = position.get("position_events", [])
                
                # Check if any position event has matching owner
                for event in position_events:
                    owner = event.get("owner")
                    if owner and owner.lower() == lowercase_contract_address:
                        current_values = event.get("current_values", {})
                        current_liquidity = position.get("current_liquidity", 0)
                        
                        # Only return positions with non-zero liquidity
                        if float(current_liquidity) != 0:
                            total_value = current_values.get("total_value_current", 0)
                            
                            # Extract uncollected fees from position_profit
                            position_profit = position.get("position_profit", {})
                            uncollected_fees = position_profit.get("uncollected_usd_fees", 0)
                            
                            logger.info(f"Found position with liquidity: {current_liquidity}, value: {total_value}, uncollected fees: {uncollected_fees}")
                            
                            return {
                                "token_id": token_id,
                                "contract_address": contract_address,
                                "owner": event.get("owner"),
                                "current_liquidity": current_liquidity,
                                "total_value_current": total_value,
                                "uncollected_usd_fees": uncollected_fees,
                                "current_values": current_values,
                                "position_data": position
                            }
            
            logger.info(f"No matching position found for token_id: {token_id}")
            return None
            
        except requests.RequestException as e:
            logger.error(f"Request error fetching valuation: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error fetching valuation: {str(e)}")
            return None
    
    def get_address_nft_valuations(self, address: str) -> List[Dict[str, Any]]:
        """
        Get all NFT valuations for a given address
        
        Args:
            address: Ethereum address to analyze
            
        Returns:
            List of NFT valuation dictionaries
        """
        try:
            # Get NFT data first
            nft_data = self.get_nft_data(address)
            
            if not nft_data:
                logger.info(f"No NFTs found for address: {address}")
                return []
            
            valuations = []
            
            for nft in nft_data:
                token_id = nft.get("id")
                contract_address = nft.get("address_hash")
                
                if not token_id or not contract_address:
                    logger.warning(f"Skipping NFT with missing data: {nft}")
                    continue
                
                # Get valuation for this NFT
                valuation = self.get_nft_valuation(token_id, contract_address)
                
                if valuation:
                    # Format the result
                    formatted_result = {
                        "nft_id": token_id,
                        "contract_address": contract_address,
                        "name": nft.get("name"),
                        "token_name": nft.get("token_name"),
                        "token_symbol": nft.get("token_symbol"),
                        "token_type": nft.get("token_type"),
                        "current_liquidity": valuation["current_liquidity"],
                        "total_value_usd": valuation["total_value_current"],
                        "total_value_formatted": self._format_value(valuation["total_value_current"]),
                        "uncollected_usd_fees": valuation["uncollected_usd_fees"],
                        "uncollected_fees_formatted": self._format_value(valuation["uncollected_usd_fees"])
                    }
                    valuations.append(formatted_result)
            
            logger.info(f"Found {len(valuations)} valued NFTs for address: {address}")
            return valuations
            
        except Exception as e:
            logger.error(f"Error getting NFT valuations: {str(e)}")
            return []
    
    def _format_value(self, value: float) -> str:
        """
        Format USD value in a human-readable format
        
        Args:
            value: USD value as float
            
        Returns:
            Formatted string (e.g., "444.76K", "1.23M")
        """
        if value >= 1_000_000:
            return f"{value / 1_000_000:.2f}M"
        elif value >= 1_000:
            return f"{value / 1_000:.2f}K"
        else:
            return f"{value:.2f}"


# Example usage and testing
if __name__ == "__main__":
    nft_service = NFTService()
    
    # Test with the provided address
    test_address = "0xA14088fc853059A2D3361ac145eEE1530c866ba4"
    
    print(f"Testing NFT service with address: {test_address}")
    
    # Get NFT valuations
    valuations = nft_service.get_address_nft_valuations(test_address)
    
    print(f"\nFound {len(valuations)} valued NFTs:")
    for valuation in valuations:
        print(f"- NFT ID: {valuation['nft_id']}")
        print(f"  Contract: {valuation['contract_address']}")
        print(f"  Name: {valuation['name']}")
        print(f"  Value: ${valuation['total_value_formatted']}")
        print(f"  Liquidity: {valuation['current_liquidity']}")
        print()
