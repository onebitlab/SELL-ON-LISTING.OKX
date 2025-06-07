# Sell on Listing OKX

This Python script automatically places a limit sell order for a specified token pair on OKX as soon as the token is listed and trading becomes available.

## Features

- Waits for a new token pair to become live on OKX.
- Monitors for the start of trading.
- Places a limit sell order at a configurable percentage below the market price.
- Uses asynchronous requests for fast response.
- Colorful terminal output for better readability.

## Requirements

- Python 3.8+

## Installation

1. Clone the repository:
    ```sh
    git clone https://github.com/yourusername/sell-on-listing.OKX.git
    cd sell-on-listing.OKX
    ```

2. Install dependencies:
    ```sh
    pip install -r requirements.txt
    ```

## Configuration

1. Copy `config_sample.py` to `config.py`:
    ```sh
    cp config_sample.py config.py
    ```
2. Edit `config.py` and fill in your OKX API credentials and trading parameters:
    ```python
    okx_api_key = "your_okx_api_key"
    okx_api_secret = "your_okx_api_secret"
    okx_passphrase = "your_okx_api_passphrase"

    pair = "SOPH-USDT"
    tokens_to_sell = 10000
    offset_percent = 1.0  # Percent below market price
    ```

**Never share your `config.py` or commit it to version control.**  
The `.gitignore` file already excludes `config.py` for your safety.

## Usage

Run the script:
```sh
python main.py
```

The script will:
- Wait for the specified token pair to be listed.
- Wait for trading to start.
- Place a limit sell order at the configured price.

## Disclaimer

This project is for educational purposes only. Use at your own risk. The author is not responsible for any financial losses.

## License

MIT License