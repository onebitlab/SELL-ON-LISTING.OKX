
# OKX Sell on Listing Bot

This Python bot is designed to automatically place a limit sell order on the OKX spot market. It's developed with reliability, precision, and safety in mind for trading operations.

## ⚡️ Features

* **Asynchronous Programming (`asyncio`, `aiohttp`):** Utilizes an asynchronous approach for high-performance and responsive interactions with the OKX API.
* **Time Synchronization:** Synchronizes local time with the OKX server to avoid time drift issues when signing API requests.
* **Continuous Monitoring:** Continuously checks for the availability of the trading pair and the start of official trading via the OKX REST API.
* **Precise Price and Quantity Calculation:** Uses the `Decimal` data type for accurate financial calculations of price and quantity, which is critical for avoiding floating-point errors.
* **Robust Retry Mechanism:** Includes an exponential backoff retry mechanism to enhance resilience against temporary network errors and API outages.
* **Graceful Shutdown:** Correctly handles `Ctrl+C` (`KeyboardInterrupt`) interruptions and ensures a clean program exit.
* **Tabular Order Output:** Uses the `tabulate` library for clear and structured display of key information about the placed order.
* **Configuration Validation:** Performs validation of necessary configuration parameters at startup, preventing errors due to incorrect settings.

## ⚙️ Configuration

1. **Install dependencies:**
    ```
    pip install -r requirements.txt
    ```
    The content of `requirements.txt` should be:
    ```
    aiohttp
    colorama
    tabulate
    ```

2. **Create a `config.py` file** in your project's root directory and add the following settings:
    ```python
    # config.py

    okx_api_key = "YOUR_API_KEY"
    okx_api_secret = "YOUR_SECRET_KEY"
    okx_passphrase = "YOUR_PASSPHRASE"

    # Trading settings
    pair = "BTC-USDT"        # Trading pair, e.g., "BTC-USDT", "ETH-USDT"
    tokens_to_sell = 0.001   # Amount of tokens to sell
    offset_percent = 0.5     # Percentage offset from market price (e.g., 0.5 means 0.5% below market price)

    # Time and interval settings
    pair_check_interval_seconds = 1.0 # Interval (in seconds) between trade pair availability checks
    ```

## ⚠️ Important: API Key Permissions

Ensure your OKX API key has **permissions to view market data and conduct spot trading**.

If you encounter an "Invalid API-key, IP, or permissions for action" error, please check your API key, secret, passphrase, and any IP restrictions on your OKX account.

## ▶️ Usage

Simply run the script:
```
python main.py
```
*(Replace `main.py` with the actual name of your main Python file if it differs.)*

The bot will start by synchronizing time with the exchange, then wait for the trading pair to become active and official trading to begin. After that, it will calculate the target price and attempt to place a limit sell order.

## 🛠 Notes

* The script uses modern asynchronous Python practices.
* Order details are displayed in an easy-to-read tabular format.

## 📄 License

MIT License — free to use, modify, and distribute.

## 🛑 Disclaimer

Cryptocurrency trading carries significant risks and may result in the loss of capital. Use this bot at your own risk. The author is not responsible for any financial losses caused by the use of this program. Always understand the risks associated with automated trading and API interaction.
