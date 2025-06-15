import asyncio
import aiohttp
import hmac
import base64
import hashlib
import json
import sys
from decimal import Decimal, ROUND_DOWN
from datetime import datetime, timezone, timedelta
from config import okx_api_key, okx_api_secret, okx_passphrase, pair, tokens_to_sell, offset_percent
from colorama import init, Fore, Style
from tabulate import tabulate # Import tabulate for pretty printing tables

# Initialize colorama for colored console output
init(autoreset=True)

BASE_URL = "https://www.okx.com"

# Global variable to store the time offset between local PC and OKX server
# Initially 0, will be updated after synchronization.
_global_time_offset_ms = 0 

# --- Logging Functions for informative output ---
def log_info(message):
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} {message}")

def log_success(message):
    print(f"{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} {message}")

def log_warning(message):
    print(f"{Fore.YELLOW}[WARNING]{Style.RESET_ALL} {message}")

def log_error(message):
    print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} {message}")

# --- Helper functions for OKX API interaction ---

def get_timestamp():
    """
    Generates an ISO 8601 UTC timestamp for signing OKX requests.
    Applies _global_time_offset_ms for synchronization with OKX server time.
    """
    # Get current UTC time
    now_utc = datetime.now(timezone.utc)
    
    # Apply the global time offset (in milliseconds)
    # timedelta expects seconds or microseconds, so divide by 1000
    adjusted_now_utc = now_utc + timedelta(milliseconds=_global_time_offset_ms)
    
    return adjusted_now_utc.isoformat(timespec='milliseconds').replace('+00:00', 'Z')

def sign(secret_key, timestamp, method, path, body):
    """
    Generates the signature for an OKX API request.
    The request body (body) should be an empty string for GET requests.
    """
    if isinstance(body, dict):
        body = json.dumps(body)
    message = f'{timestamp}{method}{path}{body}'
    mac = hmac.new(secret_key.encode(), msg=message.encode(), digestmod=hashlib.sha256)
    return base64.b64encode(mac.digest()).decode()

def build_headers(api_key, secret_key, passphrase, method, path, body=''):
    """
    Constructs HTTP request headers, including authentication data.
    Uses get_timestamp() which now accounts for the time offset.
    """
    timestamp = get_timestamp()
    signature = sign(secret_key, timestamp, method, path, body)
    return {
        'OK-ACCESS-KEY': api_key,
        'OK-ACCESS-SIGN': signature,
        'OK-ACCESS-TIMESTAMP': timestamp,
        'OK-ACCESS-PASSPHRASE': passphrase,
        'Content-Type': 'application/json'
    }

# --- Functions for interacting with OKX API with improved error handling ---

async def fetch_data(session, url, method="GET", headers=None, data=None, retries=3, backoff_factor=0.5):
    """
    Universal asynchronous function for performing HTTP requests.
    Includes retries with exponential backoff and timeouts.

    Args:
        session (aiohttp.ClientSession): The aiohttp session.
        url (str): The URL for the request.
        method (str): The HTTP method ('GET', 'POST', etc.).
        headers (dict, optional): Request headers.
        data (str, optional): Request body (for POST, PUT).
        retries (int): Number of retries on error.
        backoff_factor (float): Multiplier for calculating delay between retries.

    Returns:
        dict: JSON response from the API or a dictionary with error information.
    """
    for attempt in range(retries):
        try:
            # Set timeout for the request (10 seconds total for the request)
            timeout = aiohttp.ClientTimeout(total=10)
            async with session.request(method, url, headers=headers, data=data, timeout=timeout) as resp:
                # raise_for_status() raises an exception if the response status is 4xx or 5xx
                resp.raise_for_status()
                return await resp.json()
        except asyncio.TimeoutError:
            log_warning(f"Timeout occurred for {url} (attempt {attempt + 1}/{retries})")
        except aiohttp.ClientError as e:
            log_warning(f"Network error when requesting {url}: {e} (attempt {attempt + 1}/{retries})")
        except json.JSONDecodeError:
            log_warning(f"Failed to decode JSON from response {url} (attempt {attempt + 1}/{retries})")
        except Exception as e:
            log_error(f"Unexpected error when requesting {url}: {e} (attempt {attempt + 1}/{retries})")

        # If it's not the last attempt, wait and retry
        if attempt < retries - 1:
            wait_time = backoff_factor * (2 ** attempt)
            log_info(f"Retrying in {wait_time:.2f} seconds...")
            await asyncio.sleep(wait_time)
    log_error(f"Failed to fetch data from {url} after {retries} attempts.")
    # Return a standard error format so the calling code can handle it
    return {"code": "-1", "msg": "Failed after multiple retries or unhandled error"}

async def fetch_okx_server_time(session):
    """
    Retrieves the current OKX server time in milliseconds.
    """
    url = f"{BASE_URL}/api/v5/public/time"
    # No authentication headers are needed to get server time
    result = await fetch_data(session, url, retries=5, backoff_factor=1) # More attempts and delay
    if result and result.get("code") == "0" and result.get("data"):
        try:
            server_time_ms = int(result["data"][0]["ts"])
            log_success(f"Received OKX server time: {server_time_ms} ms")
            return server_time_ms
        except (ValueError, KeyError):
            log_error(f"Failed to get or convert server time from response: {result}")
            return None
    else:
        log_error(f"Failed to get OKX server time: {result}")
        return None

async def wait_for_pair(session, symbol):
    """
    Waits until the trading pair becomes active on the exchange.
    """
    log_info(f"Waiting for trading pair {symbol} to become active...")
    url = f"{BASE_URL}/api/v5/public/instruments?instType=SPOT"
    while True:
        data = await fetch_data(session, url) # Use fetch_data with retries
        if data and data.get("code") == "0":
            instruments = data.get("data", [])
            for item in instruments:
                if item['instId'].upper() == symbol.upper():
                    log_success(f"Pair {symbol} is now active!")
                    return
            log_warning(f"Pair {symbol} not found in the instrument list yet.")
        else:
            log_warning(f"Invalid instrument data: {data}")
        await asyncio.sleep(1) # Short delay before the next check


async def wait_for_trading_start(session, symbol):
    """
    Waits for official trading to start for the given pair and returns the last price.
    """
    log_info(f"Waiting for official trading to start for {symbol}...")
    url = f"{BASE_URL}/api/v5/market/ticker?instId={symbol}"
    while True:
        data = await fetch_data(session, url)
        if data and data.get('code') == '0' and data.get('data'):
            ticker = data['data'][0]
            last = ticker.get('last')
            try:
                last_price = Decimal(last)
                if last_price > 0:
                    log_success(f"Trading started! Last price: {last_price}")
                    return last_price
                else:
                    log_warning(f"Trading not started yet. Last price: {last}")
            except Exception:
                log_warning(f"Ticker 'last' value is invalid: {last}")
        else:
            log_warning(f"Invalid ticker data: {data}")
        await asyncio.sleep(0.5)


async def place_limit_order(session, inst_id, size, px):
    """
    Places a limit sell order.
    """
    path = "/api/v5/trade/order"
    body = {
        "instId": inst_id,
        "tdMode": "cash",  # Trade mode: spot
        "side": "sell",    # Direction: sell
        "ordType": "limit",# Order type: limit
        "sz": str(size),   # Quantity (string)
        "px": str(px)      # Price (string)
    }
    body_json = json.dumps(body)
    # build_headers now uses get_timestamp() which accounts for the global time offset
    headers = build_headers(okx_api_key, okx_api_secret, okx_passphrase, "POST", path, body_json)
    
    # For placing an order, retries are usually not desired (retries=1)
    # to avoid duplicating orders. An order error should be handled immediately.
    result = await fetch_data(session, BASE_URL + path, method="POST", headers=headers, data=body_json, retries=1)
    return result

# --- Main program logic ---
async def main():
    """
    The main asynchronous function controlling the bot's logic.
    """
    global _global_time_offset_ms # Declare that we will modify the global variable

    # Validate input data from config.py
    if not all([okx_api_key, okx_api_secret, okx_passphrase, pair, tokens_to_sell is not None, offset_percent is not None]):
        log_error("One or more required configuration parameters are missing. Please check config.py")
        sys.exit(1) # Exit the program with an error code

    symbol = pair.strip().upper()

    try:
        tokens_to_sell_dec = Decimal(str(tokens_to_sell))
        offset_percent_dec = Decimal(str(offset_percent))
    except Exception as e:
        log_error(f"Invalid numerical values in configuration: {e}. Ensure tokens_to_sell and offset_percent are numbers.")
        sys.exit(1)

    # Additional checks for reasonable values
    if tokens_to_sell_dec <= 0:
        log_error("The quantity 'tokens_to_sell' must be greater than 0.")
        sys.exit(1)
    # Offset percentage must be within reasonable limits (e.g., from 0 to 99.99%)
    if not (Decimal("0") <= offset_percent_dec < Decimal("100")):
        log_error("The offset percentage (offset_percent) must be between 0 and 99.99.")
        sys.exit(1)

    async with aiohttp.ClientSession() as session:
        try:
            # --- Time Synchronization Step ---
            log_info("Starting time synchronization with OKX server...")
            local_time_before_request = datetime.now(timezone.utc)
            okx_server_time_ms = await fetch_okx_server_time(session)
            local_time_after_request = datetime.now(timezone.utc)

            if okx_server_time_ms is None:
                log_error("Failed to synchronize time with OKX server. Program halted.")
                sys.exit(1)
            
            # Average local request time for a more accurate offset calculation
            local_current_time_ms = int(((local_time_before_request.timestamp() + local_time_after_request.timestamp()) / 2) * 1000)
            
            _global_time_offset_ms = okx_server_time_ms - local_current_time_ms
            log_info(f"Time offset (OKX Server - Local): {_global_time_offset_ms} ms")
            log_success("Time synchronization with OKX completed.")

            # --- Main logic follows, using synchronized time ---
            await wait_for_pair(session, symbol)
            
            market_price = await wait_for_trading_start(session, symbol)
            if not market_price:
                log_error("Could not get a valid market price. Exiting.")
                return

            offset = (market_price * offset_percent_dec / Decimal("100")).quantize(Decimal('1e-8'), rounding=ROUND_DOWN)
            target_price = (market_price - offset).quantize(Decimal('1e-8'), rounding=ROUND_DOWN)
            
            if target_price <= 0:
                log_error(f"Calculated target price ({target_price}) is invalid. Market price: {market_price}, offset: {offset}")
                return

            log_info(f"Target sell price: {target_price} (market: {market_price})")

            log_info(f"Attempting to place a SELL limit order: {tokens_to_sell_dec} {symbol.split('-')[0]} at price {target_price} {symbol.split('-')[1]}")
            result = await place_limit_order(session, symbol, tokens_to_sell_dec, target_price)
            
            # Process the order placement result
            if result and result.get("code") == "0":
                log_success("Order placed successfully.")
                if result.get("data"):
                    # Assuming a single order for simplicity, take the first item
                    order_data = result["data"][0] 
                    table_headers = ["Field", "Value"]
                    table_data = [
                        ["Order ID", order_data.get("ordId", "N/A")],
                        ["Instrument ID", order_data.get("instId", "N/A")],
                        ["Client Order ID", order_data.get("clOrdId", "N/A")],
                        ["Order Type", order_data.get("ordType", "N/A")],
                        ["Side", order_data.get("sId", "N/A")], # Note: OKX API uses sId for side in response
                        ["State", order_data.get("state", "N/A")]
                    ]
                    log_info(f"\n{tabulate(table_data, headers=table_headers, tablefmt='grid')}")
                else:
                    log_warning("No detailed order data received in the response.")
            else:
                # Extract detailed error information if available
                error_msg = result.get("msg", "Error message not available.") if result else "No response received from API."
                log_error(f"Failed to place order. Code: {result.get('code', 'N/A')}, Message: {error_msg}")
                if result and result.get("data"):
                    log_error(f"Additional order data: {json.dumps(result['data'], indent=2)}")

        except KeyboardInterrupt:
            # Handle Ctrl+C interruption within the main loop
            log_warning("Program interrupted by user (Ctrl+C). Shutting down.")
            # Here you can add logic for a "clean" shutdown, for example,
            # canceling all open orders if necessary during an emergency shutdown.
            # Example: await cancel_all_open_orders(session)
        except Exception as e:
            # Catch any other unexpected errors in the main program loop
            log_error(f"An unexpected error occurred in the main program loop: {e}")
        finally:
            # This block is guaranteed to execute in any case:
            # upon normal completion, error, or user interruption.
            log_info("Program shutdown completed.")

# --- Program entry point ---
if __name__ == "__main__":
    try:
        # Run the main asynchronous function
        asyncio.run(main())
    except KeyboardInterrupt:
        # This outer catch is needed in case Ctrl+C is pressed
        # before main() starts execution or if main() finishes very quickly.
        log_warning("Program terminated by external interruption (Ctrl+C).")
    except Exception as e:
        # Catch critical errors that might occur during asyncio startup itself
        log_error(f"Critical error during program startup: {e}")
