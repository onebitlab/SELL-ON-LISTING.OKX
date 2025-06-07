import asyncio
import aiohttp
import hmac
import base64
import hashlib
import json
from decimal import Decimal, ROUND_DOWN
from datetime import datetime, timezone
from config import okx_api_key, okx_api_secret, okx_passphrase, pair, tokens_to_sell, offset_percent
from colorama import init, Fore, Style

init(autoreset=True)

BASE_URL = "https://www.okx.com"

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

def build_headers(api_key, secret_key, passphrase, method, path, body=''):
    timestamp = get_timestamp()
    signature = sign(secret_key, timestamp, method, path, body)
    return {
        'OK-ACCESS-KEY': api_key,
        'OK-ACCESS-SIGN': signature,
        'OK-ACCESS-TIMESTAMP': timestamp,
        'OK-ACCESS-PASSPHRASE': passphrase,
        'Content-Type': 'application/json'
    }

async def wait_for_pair(session, symbol):
    log_info(f"Waiting for {symbol} to become live...")
    url = f"{BASE_URL}/api/v5/public/instruments?instType=SPOT"
    while True:
        async with session.get(url) as resp:
            data = await resp.json()
            instruments = data.get("data", [])
            for item in instruments:
                if item['instId'].upper() == symbol.upper():
                    log_success(f"{symbol} is now live!")
                    return
        await asyncio.sleep(1)

async def wait_for_trading_start(session, symbol):
    log_info(f"Waiting for official trading to start for {symbol}...")
    url = f"{BASE_URL}/api/v5/market/ticker?instId={symbol}"
    while True:
        async with session.get(url) as resp:
            data = await resp.json()
            if data.get('code') == '0' and data.get('data'):
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
                    log_warning(f"Ticker 'last' value not valid: {last}")
            else:
                log_warning(f"Invalid ticker data: {data}")
        await asyncio.sleep(0.5)

async def place_limit_order(session, inst_id, size, px):
    path = "/api/v5/trade/order"
    body = {
        "instId": inst_id,
        "tdMode": "cash",
        "side": "sell",
        "ordType": "limit",
        "sz": str(size),
        "px": str(px)
    }
    body_json = json.dumps(body)
    headers = build_headers(okx_api_key, okx_api_secret, okx_passphrase, "POST", path, body_json)
    async with session.post(BASE_URL + path, headers=headers, data=body_json) as resp:
        return await resp.json()

async def main():
    symbol = pair.strip().upper()

    tokens_to_sell_dec = Decimal(str(tokens_to_sell))
    offset_percent_dec = Decimal(str(offset_percent))

    async with aiohttp.ClientSession() as session:
        try:
            await wait_for_pair(session, symbol)
            market_price = await wait_for_trading_start(session, symbol)

            offset = (market_price * offset_percent_dec / Decimal("100")).quantize(Decimal('1e-8'), rounding=ROUND_DOWN)
            target_price = (market_price - offset).quantize(Decimal('1e-8'), rounding=ROUND_DOWN)
            log_info(f"Target sell price: {target_price} (market: {market_price})")

            result = await place_limit_order(session, symbol, tokens_to_sell_dec, target_price)
            if result.get("code") == "0":
                log_success(f"Order placed: {json.dumps(result['data'], indent=2)}")
            else:
                log_error(f"Order failed: {json.dumps(result, indent=2)}")

        except KeyboardInterrupt:
            log_warning("Interrupted by user. Exiting.")

if __name__ == "__main__":
    asyncio.run(main())