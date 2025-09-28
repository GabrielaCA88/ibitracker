from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
import requests
from typing import List, Dict, Any
import os
import tempfile
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from dotenv import load_dotenv
import logging
from nft_service import NFTService
from merkle_rewards_service import MerkleRewardsService
from yield_token_service import YieldTokenService
from lending_service import LendingService

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# Initialize services
nft_service = NFTService()
merkle_service = MerkleRewardsService()
yield_service = YieldTokenService()
lending_service = LendingService()

# Rootstock APIs
ROOTSTOCK_API_BASE = "https://rootstock.blockscout.com/api/v2"
ROOTSTOCK_EXPLORER_API = "https://be.explorer.rootstock.io/api/v3"

class TokenBalance:
    def __init__(self, data):
        self.token = data.get("token", {})
        self.value = data.get("value", "0")

    def to_dict(self):
        return {
            "token": {
                "address_hash": self.token.get("address_hash"),
                "circulating_market_cap": self.token.get("circulating_market_cap"),
                "decimals": self.token.get("decimals"),
                "exchange_rate": self.token.get("exchange_rate"),
                "holders_count": self.token.get("holders_count"),
                "icon_url": self.token.get("icon_url"),
                "name": self.token.get("name"),
                "symbol": self.token.get("symbol"),
                "total_supply": self.token.get("total_supply"),
                "type": self.token.get("type"),
                "volume_24h": self.token.get("volume_24h"),
            },
            "token_id": self.token.get("token_id"),
            "token_instance": self.token.get("token_instance"),
            "value": self.value,
        }

@app.route("/")
def root():
    """Serve the main frontend page"""
    try:
        return app.send_static_file('index.html')
    except Exception as e:
        return f"Error serving frontend: {str(e)}", 500

@app.route("/health")
def health_check():
    return jsonify({"status": "healthy"})

@app.route("/api/token-balances/<address>")
def get_token_balances(address: str):
    """
    Fetch token balances for a given address from Rootstock Blockscout API
    """
    try:
        url = f"{ROOTSTOCK_API_BASE}/addresses/{address}/token-balances"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            return jsonify({
                "error": f"Failed to fetch token balances: {response.text}"
            }), response.status_code
        
        data = response.json()
        
        # Process and format the data, excluding ERC-721 tokens (NFTs)
        token_balances = []
        for item in data:
            # Skip ERC-721 tokens as they are handled by the NFT service
            if item.get("token", {}).get("type") == "ERC-721":
                continue
                
            token_balance = TokenBalance(item)
            token_balances.append(token_balance.to_dict())
        
        return jsonify({
            "address": address,
            "token_balances": token_balances,
            "total_tokens": len(token_balances)
        })
        
    except requests.RequestException as e:
        return jsonify({"error": f"Request error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

def get_native_rbtc_balance(address):
    """
    Fetch native rBTC balance from Rootstock explorer API
    """
    try:
        # Explorer API requires lowercase addresses
        lowercase_address = address.lower()
        url = f"{ROOTSTOCK_EXPLORER_API}/balances/address/{lowercase_address}?take=1"
        
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        
        if "data" in data and len(data["data"]) > 0:
            # Get the latest balance (first item in the list)
            latest_balance = data["data"][0]
            balance_str = latest_balance.get("balance", "0")
            
            # Balance is already formatted as decimal string in v3 API
            balance_rbtc = float(balance_str)
            
            return {
                "balance": balance_str,
                "balance_formatted": balance_rbtc,
                "symbol": "rBTC",
                "name": "Rootstock Smart Bitcoin",
                "decimals": "18",
                "is_native": True
            }
        
        return None
        
    except Exception as e:
        return None

@app.route("/api/nft-valuations/<address>")
def get_nft_valuations(address: str):
    """
    Get NFT valuations for a given address
    """
    try:
        valuations = nft_service.get_address_nft_valuations(address)
        
        return jsonify({
            "address": address,
            "nft_valuations": valuations,
            "total_nfts": len(valuations),
            "total_value_usd": sum(v["total_value_usd"] for v in valuations)
        })
        
    except Exception as e:
        return jsonify({"error": f"Error fetching NFT valuations: {str(e)}"}), 500

@app.route("/api/merkle-rewards/<address>")
def get_merkle_rewards(address: str):
    """
    Get Merkle rewards for a given address
    """
    try:
        rewards_summary = merkle_service.get_address_rewards_summary(address)
        
        return jsonify(rewards_summary)
        
    except Exception as e:
        return jsonify({"error": f"Error fetching Merkle rewards: {str(e)}"}), 500

@app.route("/api/address-info/<address>")
def get_address_info(address: str):
    """
    Get basic address information and token balances
    """
    try:
        # Get token balances from Blockscout
        token_balances_response = get_token_balances(address)
        
        if isinstance(token_balances_response, tuple):
            # If there was an error, return it
            return token_balances_response
        
        # Extract the JSON data from the response
        token_balances_data = token_balances_response.get_json()
        all_balances = token_balances_data["token_balances"].copy()
        
        # Get native rBTC balance from Explorer
        native_rbtc = get_native_rbtc_balance(address)
        
        # Get NFT valuations
        nft_valuations = nft_service.get_address_nft_valuations(address)
        
        # Get Merkle rewards
        merkle_rewards = merkle_service.get_address_rewards_summary(address)
        
        if native_rbtc:
            # Add native rBTC to the beginning of the list
            native_token_data = {
                "token": {
                    "address_hash": "0x0000000000000000000000000000000000000000",  # Native token address
                    "circulating_market_cap": "0.0",
                    "decimals": "18",
                    "exchange_rate": None,  # Will be set from RBTC price
                    "holders_count": None,
                    "icon_url": "https://assets.coingecko.com/coins/images/5070/small/RBTC-logo.png?1718152038",
                    "name": "Rootstock Smart Bitcoin",
                    "symbol": "rBTC",
                    "total_supply": None,
                    "type": "native",
                    "volume_24h": None
                },
                "token_id": None,
                "token_instance": None,
                "value": native_rbtc["balance"]
            }
            
            # Find RBTC or WRBTC price from existing tokens to use for native rBTC
            rbtc_price = None
            for balance in all_balances:
                if balance["token"]["symbol"] in ["RBTC", "WRBTC"]:
                    rbtc_price = balance["token"]["exchange_rate"]
                    break
            
            # If no RBTC/WRBTC price found in existing tokens, try to get WRBTC price from Blockscout API
            if not rbtc_price:
                try:
                    # Get WRBTC price from Blockscout API using the WRBTC contract address - as the API has no price for the native asset. 
                    wrbtc_address = "0x542fda317318ebf1d3deaf76e0b632741a7e677d"
                    wrbtc_url = f"https://rootstock.blockscout.com/api/v2/tokens/{wrbtc_address}"
                    
                    logger.info(f"Fetching WRBTC price from: {wrbtc_url}")
                    response = requests.get(wrbtc_url, timeout=10)
                    logger.info(f"Blockscout API response status: {response.status_code}")
                    
                    if response.status_code == 200:
                        data = response.json()
                        logger.info(f"Blockscout API response: {data}")
                        if "exchange_rate" in data and data["exchange_rate"]:
                            rbtc_price = float(data["exchange_rate"])
                            logger.info(f"Retrieved WRBTC price from Blockscout: ${rbtc_price}")
                        else:
                            logger.warning(f"No exchange_rate found in Blockscout response: {data}")
                    else:
                        logger.warning(f"Blockscout API returned status {response.status_code}: {response.text}")
                except Exception as e:
                    logger.warning(f"Could not fetch WRBTC price from Blockscout API: {str(e)}")
            
            if rbtc_price:
                native_token_data["token"]["exchange_rate"] = rbtc_price
            
            # Rename RBTC to Wrapped Rootstock Smart Bitcoin
            for balance in all_balances:
                if balance["token"]["symbol"] == "RBTC":
                    balance["token"]["name"] = "Wrapped Rootstock Smart Bitcoin"
                    balance["token"]["symbol"] = "WRBTC"
                    break
            
            all_balances.insert(0, native_token_data)
        
        return jsonify({
            "address": address,
            "total_value_usd": len(all_balances),  # Placeholder
            "token_count": len(all_balances),
            "token_balances": all_balances,
            "nft_valuations": nft_valuations,
            "nft_count": len(nft_valuations),
            "nft_total_value_usd": sum(v["total_value_usd"] for v in nft_valuations),
            "merkle_rewards": merkle_rewards["rewards"],
            "merkle_rewards_count": merkle_rewards["total_rewards"],
            "merkle_rewards_total_usd": merkle_rewards["total_usd_value"],
            "yield_tokens": yield_service.get_yield_token_data(address)["yield_tokens"],
            "yield_tokens_count": yield_service.get_yield_token_data(address)["total_yield_tokens"]
        })
        
    except Exception as e:
        return jsonify({"error": f"Error fetching address info: {str(e)}"}), 500

@app.route("/api/yield-tokens/<address>")
def get_yield_tokens(address: str):
    try:
        yield_data = yield_service.get_yield_token_data(address)
        return jsonify(yield_data)
    except Exception as e:
        return jsonify({"error": f"Error fetching yield tokens: {str(e)}"}), 500

@app.route("/api/lending-data/<address>")
def get_lending_data(address: str):
    """
    Get lending protocol data (APR and prices) for an address
    """
    try:
        # Get lending data directly from the service (it will handle campaign ID extraction)
        lending_data = lending_service.get_lending_data_for_address(address)
        
        return jsonify({
            "address": address,
            "lending_data": lending_data
        })
        
    except Exception as e:
        return jsonify({"error": f"Error fetching lending data: {str(e)}"}), 500

@app.route("/api/tropykus-portfolio/<address>")
def get_tropykus_portfolio(address: str):
    """
    Get Tropykus portfolio data for an address
    """
    try:
        # Get Tropykus portfolio data
        tropykus_module = lending_service.protocols.get("tropykus")
        if not tropykus_module:
            return jsonify({"error": "Tropykus module not available"}), 500
        
        portfolio_data = lending_service.get_tropykus_portfolio_data(address)
        
        return jsonify({
            "address": address,
            "tropykus_portfolio": portfolio_data
        })
        
    except Exception as e:
        return jsonify({"error": f"Error fetching Tropykus portfolio data: {str(e)}"}), 500

@app.route("/api/export-excel/<address>")
def export_to_excel(address: str):
    """
    Export portfolio data to Excel spreadsheet
    """
    try:
        # Get all portfolio data
        url = f"{ROOTSTOCK_API_BASE}/addresses/{address}/token-balances"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            return jsonify({"error": "Failed to fetch token balances"}), response.status_code
        
        data = response.json()
        
        # Filter out ERC-721 tokens
        token_balances = []
        for item in data:
            if item.get("token", {}).get("type") == "ERC-721":
                continue
            token_balances.append(TokenBalance(item).to_dict())
        
        # Get additional data
        nft_valuations = nft_service.get_address_nft_valuations(address)
        merkle_rewards = merkle_service.get_address_rewards_summary(address)
        yield_tokens = yield_service.get_yield_token_data(address)
        
        # Create Excel workbook
        wb = Workbook()
        
        # Remove default sheet
        wb.remove(wb.active)
        
        # Create sheets
        create_wallet_sheet(wb, token_balances)
        create_portfolio_sheet(wb, token_balances, nft_valuations, merkle_rewards, yield_tokens)
        create_summary_sheet(wb, address, token_balances, nft_valuations, merkle_rewards, yield_tokens)
        
        # Save to temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
        wb.save(temp_file.name)
        temp_file.close()
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"portfolio_{address[:8]}_{timestamp}.xlsx"
        
        return send_file(
            temp_file.name,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        return jsonify({"error": f"Error creating Excel file: {str(e)}"}), 500

def create_wallet_sheet(wb, token_balances):
    """Create Wallet sheet with token balances"""
    ws = wb.create_sheet("Wallet")
    
    # Headers
    headers = ["Token", "Name", "Holdings", "Price", "USD Value"]
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
        cell.alignment = Alignment(horizontal="center")
    
    # Data
    for row, token_data in enumerate(token_balances, 2):
        token = token_data["token"]
        value = token_data["value"]
        
        # Calculate values
        balance = float(value) / (10 ** int(token.get("decimals", 18)))
        price = float(token.get("exchange_rate", 0)) if token.get("exchange_rate") else 0
        usd_value = balance * price
        
        ws.cell(row=row, column=1, value=token.get("symbol", ""))
        ws.cell(row=row, column=2, value=token.get("name", ""))
        ws.cell(row=row, column=3, value=round(balance, 8))
        ws.cell(row=row, column=4, value=f"${price:,.2f}" if price > 0 else "N/A")
        ws.cell(row=row, column=5, value=f"${usd_value:,.2f}" if usd_value > 0 else "N/A")
    
    # Auto-adjust column widths
    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[column_letter].width = adjusted_width

def create_portfolio_sheet(wb, token_balances, nft_valuations, merkle_rewards, yield_tokens):
    """Create Portfolio sheet with yield tokens, NFTs, and rewards"""
    ws = wb.create_sheet("Portfolio")
    
    # Headers
    headers = ["Type", "Protocol", "Name", "Holdings", "Price", "APR", "USD Value"]
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
        cell.alignment = Alignment(horizontal="center")
    
    row = 2
    
    # Yield tokens
    for token_data in token_balances:
        token = token_data["token"]
        if any(keyword in token.get("name", "").lower() for keyword in ["midas", "layerbank", "avalon"]):
            value = token_data["value"]
            balance = float(value) / (10 ** int(token.get("decimals", 18)))
            price = float(token.get("exchange_rate", 0)) if token.get("exchange_rate") else 0
            usd_value = balance * price
            
            ws.cell(row=row, column=1, value="Yield Token")
            ws.cell(row=row, column=2, value="Midas")  # Default protocol
            ws.cell(row=row, column=3, value=token.get("name", ""))
            ws.cell(row=row, column=4, value=round(balance, 8))
            ws.cell(row=row, column=5, value=f"${price:,.2f}" if price > 0 else "N/A")
            ws.cell(row=row, column=6, value="N/A")  # APR not available in basic data
            ws.cell(row=row, column=7, value=f"${usd_value:,.2f}" if usd_value > 0 else "N/A")
            row += 1
    
    # NFTs
    for nft_data in nft_valuations:
        ws.cell(row=row, column=1, value="NFT")
        ws.cell(row=row, column=2, value="Uniswap")
        ws.cell(row=row, column=3, value=nft_data.get("name", f"NFT #{nft_data.get('nft_id', '')}"))
        ws.cell(row=row, column=4, value="1")
        ws.cell(row=row, column=5, value="N/A")
        ws.cell(row=row, column=6, value="N/A")
        ws.cell(row=row, column=7, value=f"${float(nft_data.get('total_value_usd', 0)):,.2f}")
        row += 1
    
    # Merkle rewards
    for reward_data in merkle_rewards.get("rewards", []):
        ws.cell(row=row, column=1, value="Reward")
        ws.cell(row=row, column=2, value="Merkle")
        ws.cell(row=row, column=3, value=f"Merkle Rewards ({reward_data.get('token', {}).get('symbol', '')})")
        ws.cell(row=row, column=4, value=reward_data.get("amount_formatted", "0"))
        ws.cell(row=row, column=5, value=f"${float(reward_data.get('token', {}).get('price', 0)):,.2f}")
        ws.cell(row=row, column=6, value="N/A")
        ws.cell(row=row, column=7, value=f"${float(reward_data.get('usd_value', 0)):,.2f}")
        row += 1
    
    # Auto-adjust column widths
    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[column_letter].width = adjusted_width

def create_summary_sheet(wb, address, token_balances, nft_valuations, merkle_rewards, yield_tokens):
    """Create Summary sheet with totals and overview"""
    ws = wb.create_sheet("Summary")
    
    # Title
    ws.cell(row=1, column=1, value=f"Portfolio Summary - {address}")
    ws.cell(row=1, column=1).font = Font(bold=True, size=16)
    
    # Summary data
    row = 3
    
    # Calculate totals
    total_tokens = len(token_balances)
    total_value = sum(
        float(t["value"]) / (10 ** int(t["token"].get("decimals", 18))) * 
        (float(t["token"].get("exchange_rate", 0)) if t["token"].get("exchange_rate") else 0) 
        for t in token_balances
    )
    nft_count = len(nft_valuations)
    nft_value = sum(float(nft.get("total_value_usd", 0)) for nft in nft_valuations)
    reward_count = merkle_rewards.get("total_rewards", 0)
    reward_value = merkle_rewards.get("total_usd_value", 0)
    
    summary_data = [
        ("Total Tokens", total_tokens),
        ("Total Token Value", f"${total_value:,.2f}"),
        ("NFT Count", nft_count),
        ("NFT Value", f"${nft_value:,.2f}"),
        ("Reward Count", reward_count),
        ("Reward Value", f"${reward_value:,.2f}"),
        ("Total Portfolio Value", f"${total_value + nft_value + reward_value:,.2f}"),
        ("Export Date", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    ]
    
    for label, value in summary_data:
        ws.cell(row=row, column=1, value=label)
        ws.cell(row=row, column=1).font = Font(bold=True)
        ws.cell(row=row, column=2, value=value)
        row += 1
    
    # Auto-adjust column widths
    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[column_letter].width = adjusted_width

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8001))
    debug = os.environ.get("FLASK_ENV") == "development"
    app.run(host="0.0.0.0", port=port, debug=debug)