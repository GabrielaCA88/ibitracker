import requests
from typing import List, Dict, Any, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MerkleRewardsService:
    """
    Service for retrieving Merkle rewards data from Merkl API
    """
    
    def __init__(self):
        self.merkle_api_base = "https://api.merkl.xyz/v4"
        self.rootstock_chain_id = "30"
    
    def get_user_rewards(self, address: str) -> List[Dict[str, Any]]:
        """
        Fetch Merkle rewards for a given address
        
        Args:
            address: Ethereum address to fetch rewards for
            
        Returns:
            List of reward dictionaries containing amount, token info, and USD value
        """
        try:
            # Convert address to lowercase for API consistency
            lowercase_address = address.lower()
            url = f"{self.merkle_api_base}/users/{lowercase_address}/rewards"
            
            params = {
                "chainId": self.rootstock_chain_id,
                "test": "false",
                "claimableOnly": "true",
                "breakdownPage": "0"
            }
            
            logger.info(f"Fetching Merkle rewards for address: {lowercase_address}")
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch Merkle rewards: {response.status_code} - {response.text}")
                return []
            
            data = response.json()
            
            # Extract rewards from the response
            rewards = []
            # The API returns an array of chain objects, each containing rewards
            if isinstance(data, list):
                for chain_data in data:
                    if "rewards" in chain_data:
                        for reward_data in chain_data["rewards"]:
                            reward_info = self._process_reward(reward_data)
                            if reward_info:
                                rewards.append(reward_info)
            elif isinstance(data, dict) and "rewards" in data:
                # Handle case where response is a single object with rewards
                for reward_data in data["rewards"]:
                    reward_info = self._process_reward(reward_data)
                    if reward_info:
                        rewards.append(reward_info)
            
            logger.info(f"Found {len(rewards)} Merkle rewards")
            return rewards
            
        except requests.RequestException as e:
            logger.error(f"Request error fetching Merkle rewards: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Error fetching Merkle rewards: {str(e)}")
            return []
    
    def _process_reward(self, reward_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process individual reward data and calculate USD value
        
        Args:
            reward_data: Raw reward data from API
            
        Returns:
            Processed reward dictionary or None if invalid
        """
        try:
            amount = reward_data.get("amount", "0")
            token_info = reward_data.get("token", {})
            
            if not token_info:
                logger.warning("Reward missing token information")
                return None
            
            # Extract token details
            token_address = token_info.get("address", "")
            token_symbol = token_info.get("symbol", "Unknown")
            token_decimals = token_info.get("decimals", 18)
            token_price = token_info.get("price", 0)
            
            # Calculate USD value
            amount_num = float(amount) / (10 ** int(token_decimals))
            price_num = float(token_price) if token_price else 0
            usd_value = amount_num * price_num
            
            # Format values
            formatted_amount = self._format_token_amount(amount_num, token_symbol)
            formatted_usd_value = self._format_usd_value(usd_value)
            
            reward_info = {
                "amount": amount,
                "amount_formatted": formatted_amount,
                "amount_numeric": amount_num,
                "token": {
                    "address": token_address,
                    "symbol": token_symbol,
                    "decimals": token_decimals,
                    "price": token_price
                },
                "usd_value": usd_value,
                "usd_value_formatted": formatted_usd_value
            }
            
            logger.info(f"Processed reward: {formatted_amount} {token_symbol} = {formatted_usd_value}")
            return reward_info
            
        except Exception as e:
            logger.error(f"Error processing reward: {str(e)}")
            return None
    
    def _format_token_amount(self, amount: float, symbol: str) -> str:
        """
        Format token amount in a human-readable format
        
        Args:
            amount: Token amount as float
            symbol: Token symbol
            
        Returns:
            Formatted string (e.g., "1.05 WRBTC", "4.50 mBTC")
        """
        if amount >= 1_000_000:
            return f"{amount / 1_000_000:.2f}M {symbol}"
        elif amount >= 1_000:
            return f"{amount / 1_000:.2f}K {symbol}"
        elif amount >= 1:
            return f"{amount:.4f} {symbol}"
        else:
            return f"{amount:.8f} {symbol}"
    
    def _format_usd_value(self, value: float) -> str:
        """
        Format USD value in a human-readable format
        
        Args:
            value: USD value as float
            
        Returns:
            Formatted string (e.g., "1.22K", "444.88K")
        """
        if value >= 1_000_000:
            return f"{value / 1_000_000:.2f}M"
        elif value >= 1_000:
            return f"{value / 1_000:.2f}K"
        else:
            return f"{value:.2f}"
    
    def get_address_rewards_summary(self, address: str) -> Dict[str, Any]:
        """
        Get summary of all rewards for an address
        
        Args:
            address: Ethereum address to analyze
            
        Returns:
            Dictionary containing rewards summary
        """
        try:
            rewards = self.get_user_rewards(address)
            
            if not rewards:
                logger.info(f"No Merkle rewards found for address: {address}")
                return {
                    "address": address,
                    "rewards": [],
                    "total_rewards": 0,
                    "total_usd_value": 0,
                    "total_usd_value_formatted": "$0.00"
                }
            
            # Calculate totals
            total_usd_value = sum(reward["usd_value"] for reward in rewards)
            
            summary = {
                "address": address,
                "rewards": rewards,
                "total_rewards": len(rewards),
                "total_usd_value": total_usd_value,
                "total_usd_value_formatted": f"${self._format_usd_value(total_usd_value)}"
            }
            
            logger.info(f"Found {len(rewards)} rewards totaling {summary['total_usd_value_formatted']}")
            return summary
            
        except Exception as e:
            logger.error(f"Error getting rewards summary: {str(e)}")
            return {
                "address": address,
                "rewards": [],
                "total_rewards": 0,
                "total_usd_value": 0,
                "total_usd_value_formatted": "$0.00"
            }


# Example usage and testing
if __name__ == "__main__":
    merkle_service = MerkleRewardsService()
    
    # Test with the provided address
    test_address = "0x26d2e5bd1a418aff98523a70ec4d12cb370cdd85"
    
    print(f"Testing Merkle rewards service with address: {test_address}")
    
    # Get rewards summary
    summary = merkle_service.get_address_rewards_summary(test_address)
    
    print(f"\nFound {summary['total_rewards']} rewards totaling {summary['total_usd_value_formatted']}:")
    for reward in summary['rewards']:
        print(f"- {reward['amount_formatted']} = {reward['usd_value_formatted']}")
        print(f"  Token: {reward['token']['symbol']} @ ${reward['token']['price']}")
        print()
