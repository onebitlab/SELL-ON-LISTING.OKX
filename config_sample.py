# config.py
# OKX API Credentials
okx_api_key = "YOUR_API_KEY"
okx_api_secret = "YOUR_SECRET_KEY"
okx_passphrase = "YOUR_PASSPHRASE"

# Trading settings
pair = "ALT-USDT"        # Trading pair, e.g., "BTC-USDT", "ETH-USDT"
tokens_to_sell = 0.001   # Amount of tokens to sell
offset_percent = 0.5     # Percentage offset from market price (0.5% below market price)

# Time and interval settings
pair_check_interval_seconds = 1.0 # Interval (in seconds) between trade pair availability checks