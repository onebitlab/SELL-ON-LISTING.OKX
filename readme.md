
# 🚀 OKX Sell on Listing Bot

This Python script automatically places a limit sell order immediately after a new token is listed on OKX, at a configurable price below the market. It's built for speed, precision, and safety during high-volatility listing events.

## ⚡️ Features

  * **Async/await** — Built using asynchronous programming for maximum responsiveness with the OKX API.
  * **Time synchronization** — Syncs with OKX server time before starting the countdown to avoid clock drift.
  * **Configurable Pre-Launch Pooling** — Begins checking for the trading pair a specified number of seconds (`pre_launch_pooling`) before your exact `launch_time`.
  * **Continuous Monitoring** — Polls the OKX REST API for the appearance of the trading pair at a defined `pair_check_interval`.
  * **Smart Price and Quantity Calculation** — Applies OKX's instrument rules (`tickSz` for price and `lotSz` for quantity) to ensure your order meets exchange requirements and avoids errors.
  * **Infinite Price Retrieval Retries** — Continuously attempts to fetch the current price until successful or program interruption, with a configurable `price_check_interval` between attempts.
  * **Automatic Order Cancellation** — If the order isn't filled within a configurable `order_timeout`, it is automatically cancelled.
  * **API Key Pre-Checks** — Verifies the validity of your API key, secret, and passphrase using a lightweight balance check before starting the main bot logic.

## ⚙️ Configuration

1. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

2.  **Create a `config.py` file in the root directory:**

    ```python
    # OKX API Credentials
    api_key = 'YOUR_OKX_API_KEY'
    api_secret = 'YOUR_OKX_SECRET_KEY'
    passphrase = 'YOUR_OKX_PASSPHRASE'

    # Trading configuration
    pair = 'ALT/USDT'                       # Trading pair, e.g.: 'ALT/USDT'
    tokens_for_sale = '100'                 # Amount of tokens to sell
    price_offset = '1.0'                    # Percentage below market price (e.g., '1.0' means 1% below)

    # Timing configuration
    launch_time = '2025-05-29 12:00:00'     # Exact trading start time (UTC) in 'YYYY-MM-DD HH:MM:SS' format
    pre_launch_pooling = 10                 # How many seconds before launch_time to start checking for the pair listing
    pair_check_interval = 0.5               # Interval (in seconds) between trade pair availability checks
    price_check_interval = 1.0              # Interval (in seconds) between price retrieval attempts upon error
    order_timeout = 30                      # Cancel order after this many seconds if not filled
    ```

## ⚠️ Important: API Key Permissions

Make sure your OKX API key has **"Trade"** permission enabled.

If you encounter an `"Invalid Sign"` error (code: `50113`), it is highly likely that your `api_key`, `api_secret`, or `passphrase` are incorrect. Double-check them carefully. Also, ensure any IP restrictions for the API key match your server's IP address.

## ▶️ Usage

Simply rename the script file to `main.py` and run:

```bash
python main.py
```

## 🛠 Notes

  * The `passphrase` is not your login password. It is a specific password you create for the API key on the OKX website.
  * The time format for `launch_time` must be `"YYYY-MM-DD HH:MM:SS"` in UTC.
  * If you launch the bot after `launch_time` has passed, it will immediately begin checking for the pair.
  * The script uses modern Python `asyncio` and `aiohttp` for robust operation.
  * Order details are displayed in a readable table format using `tabulate`.

## 📄 License

MIT License — free to use, modify, and distribute.

## 🛑 Disclaimer

Cryptocurrency trading carries significant risks and may result in the loss of capital. Use this bot at your own risk. The author is not responsible for any financial losses caused by the use of this program. Always understand the risks associated with automated trading and API interaction.