import asyncio
import sys
import json
import hmac
import base64
import hashlib
import urllib.parse
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_DOWN
import pytz
import aiohttp
from config import (
    api_key,
    api_secret,
    passphrase,
    pair as cfg_pair,
    tokens_for_sale as cfg_tokens,
    price_offset as cfg_offset,
    order_timeout as cfg_timeout,
    pair_check_interval as cfg_pair_check_interval,
    launch_time as cfg_launch_time,
    pre_launch_pooling as cfg_pre_launch_pooling,
    price_check_interval as cfg_price_check_interval
)
from colorama import init, Fore, Style
from tabulate import tabulate

init(autoreset=True)
BASE_URL = "https://www.okx.com"

pair_from_config = cfg_pair.strip().upper()
pair = pair_from_config.replace('/', '-')
tokens_for_sale = Decimal(cfg_tokens)
price_offset = Decimal(cfg_offset)
order_timeout = int(cfg_timeout)
pair_check_interval = float(cfg_pair_check_interval)
pre_launch_pooling = int(cfg_pre_launch_pooling)
price_check_interval = float(cfg_price_check_interval)
launch_time_utc = datetime.strptime(cfg_launch_time, "%Y-%m-%d %H:%M:%S").replace(tzinfo=pytz.UTC)

def log_info(message):
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} {message}")

def log_success(message):
    print(f"{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} {message}")

def log_warning(message):
    print(f"{Fore.YELLOW}[WARNING]{Style.RESET_ALL} {message}")

def log_error(message):
    print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} {message}")

def get_timestamp():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')

def sign(secret_key, timestamp, method, path, body):
    if isinstance(body, dict):
        body = json.dumps(body)
    message = f'{timestamp}{method}{path}{body}'
    mac = hmac.new(secret_key.encode(), msg=message.encode(), digestmod=hashlib.sha256)
    return base64.b64encode(mac.digest()).decode()

def build_headers(method, path, body=''):
    timestamp = get_timestamp()
    signature = sign(api_secret, timestamp, method, path, body)
    return {
        'OK-ACCESS-KEY': api_key,
        'OK-ACCESS-SIGN': signature,
        'OK-ACCESS-TIMESTAMP': timestamp,
        'OK-ACCESS-PASSPHRASE': passphrase,
        'Content-Type': 'application/json'
    }

async def fetch_api(session, path, method="GET", params=None, data=None, retries=3):
    request_path = path
    if params:
        request_path += '?' + urllib.parse.urlencode(params)
    
    url = BASE_URL + path
    body_json = json.dumps(data) if data else ""
    headers = build_headers(method, request_path, body_json)
    
    for attempt in range(retries):
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with session.request(method, url, headers=headers, params=params, data=body_json, timeout=timeout) as resp:
                if resp.status // 100 != 2:
                    log_warning(f"API request to {url} failed with status {resp.status}. Response: {await resp.text()}")
                    if attempt < retries - 1:
                        await asyncio.sleep(1)
                        continue
                    return None
                
                response_json = await resp.json()
                if response_json.get("code") != "0":
                    log_warning(f"OKX API Error: {response_json.get('msg')} (Code: {response_json.get('code')})")
                    return None
                
                return response_json.get("data", [])
        except Exception as e:
            log_warning(f"Network error on attempt {attempt+1} for {url}: {e}")
            if attempt < retries - 1:
                await asyncio.sleep(1)
    return None

def print_order_details(order):
    order_table = [
        ["Symbol", order.get('instId', 'N/A')],
        ["Order ID", order.get('ordId', 'N/A')],
        ["Status", order.get('state', 'N/A')],
        ["Type", order.get('ordType', 'N/A')],
        ["Side", order.get('side', 'N/A')],
        ["Quantity", order.get('sz', 'N/A')],
        ["Price", order.get('px', 'N/A')],
        ["Filled Qty", order.get('accFillSz', 'N/A')],
        ["Avg. Fill Price", order.get('avgPx', 'N/A')],
        ["Time in Force", order.get('tif', 'N/A')],
    ]
    print("-" * 37)
    print(tabulate(order_table, tablefmt="fancy_grid"))
    print("-" * 37)

async def pre_launch_checks(session: aiohttp.ClientSession) -> bool:
    log_info("Performing pre-launch API key checks...")
    data = await fetch_api(session, "/api/v5/account/balance", params={'ccy': 'USDT'})
    if data is not None:
        log_success("API keys are valid and have necessary permissions.")
        return True
    else:
        log_error("API error during pre-launch API key check.")
        log_error("Please check your API key, secret, passphrase, and permissions.")
        return False

async def wait_until_launch(session: aiohttp.ClientSession):
    try:
        path = "/api/v5/public/time"
        server_time_data = await fetch_api(session, path)
        if not server_time_data:
            log_error("Could not fetch server time to start countdown. Proceeding immediately.")
            return

        server_now_ms = int(server_time_data[0]['ts'])
        server_now = datetime.fromtimestamp(server_now_ms / 1000, tz=pytz.UTC)
        wait_until = launch_time_utc - timedelta(seconds=pre_launch_pooling)

        if server_now >= wait_until:
            log_info(f"Launch time already reached or close (within {pre_launch_pooling}s). Skipping wait.")
            return

        while server_now < wait_until:
            remaining = wait_until - server_now
            if remaining.total_seconds() < 0:
                break
            
            total_seconds = int(remaining.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Waiting for launch: "
                  f"{str(hours).zfill(2)}:{str(minutes).zfill(2)}:{str(seconds).zfill(2)}", end="\r")
            await asyncio.sleep(1)
            
            server_time_data = await fetch_api(session, path)
            if server_time_data:
                server_now_ms = int(server_time_data[0]['ts'])
                server_now = datetime.fromtimestamp(server_now_ms / 1000, tz=pytz.UTC)

        print()
        log_info(f"{pre_launch_pooling} seconds left until launch time. Starting to check for listing...")
    except asyncio.CancelledError:
        log_warning("Waiting for launch time was cancelled.")
        raise
    except Exception as e:
        log_error(f"Error while waiting for launch time: {e}")
        raise

async def wait_for_pair_listing(session, symbol):
    log_info(f"Waiting for pair {symbol} to be listed (checking every {pair_check_interval}s)...")
    path = "/api/v5/public/instruments"
    params = {"instType": "SPOT"}
    while True:
        try:
            instruments = await fetch_api(session, path, params=params)
            if instruments:
                for inst in instruments:
                    if inst['instId'] == symbol:
                        log_success(f"Pair {symbol} found on OKX!")
                        return instruments
            await asyncio.sleep(pair_check_interval)
        except asyncio.CancelledError:
            log_warning("Waiting for pair listing was cancelled.")
            raise
        except Exception as e:
            log_error(f"Error querying instruments: {e}. Retrying in {pair_check_interval}s...")
            await asyncio.sleep(pair_check_interval)

async def get_current_price(session, symbol):
    path = f"/api/v5/market/ticker"
    params = {"instId": symbol}
    while True:
        try:
            ticker_data = await fetch_api(session, path, params=params)
            if ticker_data and 'last' in ticker_data[0]:
                price = Decimal(ticker_data[0]['last'])
                if price > 0:
                    return price
            log_warning(f"Waiting for a valid price... Retrying in {price_check_interval}s.")
            await asyncio.sleep(price_check_interval)
        except asyncio.CancelledError:
            raise
        except Exception:
            log_warning(f"Error getting current price. Retrying in {price_check_interval}s...")
            await asyncio.sleep(price_check_interval)

async def wait_for_order_fill_or_timeout(session, symbol, order_id, timeout):
    log_info(f"Waiting for order {order_id} to fill or timeout in {timeout} seconds...")
    start_time = asyncio.get_event_loop().time()
    path = "/api/v5/trade/order"
    params = {"instId": symbol, "ordId": order_id}

    while True:
        try:
            if asyncio.get_event_loop().time() - start_time > timeout:
                log_info(f"Timeout reached. Cancelling order {order_id}...")
                cancel_path = "/api/v5/trade/cancel-order"
                cancel_data = {"instId": symbol, "ordId": order_id}
                cancellation_result = await fetch_api(session, cancel_path, method="POST", data=cancel_data)
                if cancellation_result and cancellation_result[0].get('sCode') == "0":
                    log_info(f"Order {order_id} cancelled due to timeout.")
                else:
                    order_status = await fetch_api(session, path, params=params)
                    if order_status and order_status[0]['state'] == 'filled':
                        log_success(f"Order {order_id} was filled before it could be cancelled.")
                        print_order_details(order_status[0])
                    else:
                        log_error(f"Failed to cancel order {order_id}. Reason: {cancellation_result}")
                return

            order_status = await fetch_api(session, path, params=params)
            if order_status:
                state = order_status[0]['state']
                if state == 'filled':
                    log_success(f"Order {order_id} filled successfully.")
                    print_order_details(order_status[0])
                    return
                elif state in ['canceled', 'placed error']:
                    log_warning(f"Order {order_id} ended with status: {state}")
                    return
            
            await asyncio.sleep(1)

        except asyncio.CancelledError:
            log_warning(f"Waiting for order {order_id} fill/timeout was cancelled. Attempting to cancel order...")
            try:
                cancel_path = "/api/v5/trade/cancel-order"
                cancel_data = {"instId": symbol, "ordId": order_id}
                await fetch_api(session, cancel_path, method="POST", data=cancel_data)
                log_info(f"Order {order_id} cancelled due to task cancellation.")
            except Exception as e:
                log_warning(f"Could not cancel order {order_id} on task cancellation: {e}")
            raise
        except Exception as e:
            log_warning(f"Error checking order status for {order_id}: {e}")
            await asyncio.sleep(1)

def get_price_precision(symbol_info):
    tick_size = Decimal(symbol_info['tickSz'])
    return abs(tick_size.normalize().as_tuple().exponent)

def get_lot_size_precision(symbol_info):
    step_size = Decimal(symbol_info['lotSz'])
    return abs(step_size.normalize().as_tuple().exponent)

async def main():
    async with aiohttp.ClientSession() as session:
        try:
            if not await pre_launch_checks(session):
                log_error("API key pre-checks failed. Exiting.")
                return

            await wait_until_launch(session)

            all_instruments = await wait_for_pair_listing(session, pair)

            current_price = await get_current_price(session, pair)
            
            offset = current_price * price_offset / Decimal('100')
            target_price = current_price - offset
            
            quantity = tokens_for_sale

            symbol_info = next((inst for inst in all_instruments if inst['instId'] == pair), None)
            if not symbol_info:
                log_error(f"Symbol information for {pair} not found. Cannot apply filters.")
                return
            
            price_precision = get_price_precision(symbol_info)
            target_price = target_price.quantize(Decimal(f'1e-{price_precision}'), rounding=ROUND_DOWN)

            quantity_precision = get_lot_size_precision(symbol_info)
            quantity = quantity.quantize(Decimal(f'1e-{quantity_precision}'), rounding=ROUND_DOWN)

            if quantity <= 0:
                log_error(f"Calculated quantity is zero or less after applying precision rules. Check 'tokens_for_sale' and pair's lot size.")
                return

            log_info(f"Placing limit sell order for {quantity} {pair.split('-')[0]} at {target_price} USDT (market: {current_price})...")

            retries = 3
            for attempt in range(1, retries + 1):
                try:
                    log_info(f"Placing order (attempt {attempt}/{retries})...")
                    path = "/api/v5/trade/order"
                    order_data = {
                        "instId": pair, "tdMode": "cash", "side": "sell", "ordType": "limit",
                        "sz": str(quantity), "px": str(target_price)
                    }
                    order_response = await fetch_api(session, path, method="POST", data=order_data, retries=1)
                    
                    if order_response and order_response[0].get('sCode') == '0':
                        order_id = order_response[0]['ordId']
                        log_success(f"Order placed successfully! Order ID: {order_id}")
                        await wait_for_order_fill_or_timeout(session, pair, order_id, order_timeout)
                        break
                    else:
                        log_error(f"Failed to place order. Response: {order_response}")
                        if attempt == retries: return
                        await asyncio.sleep(1)

                except asyncio.CancelledError:
                    log_warning("Order placement was cancelled.")
                    raise

        except asyncio.CancelledError:
            log_warning("Main task was cancelled.")
        except Exception as e:
            log_error(f"A general error occurred in the main function: {e}")
        finally:
            log_info("Program shutdown completed.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log_warning("\nProgram interrupted by user (Ctrl+C). Shutting down.")
    except Exception as e:
        log_error(f"An unexpected error occurred in the main execution block: {e}")
    finally:
        log_info("Program terminated.")