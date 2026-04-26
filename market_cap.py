import aiohttp
import logging
from typing import Dict

logger = logging.getLogger(__name__)

class MarketCapProvider:
    def __init__(self):
        self.market_caps: Dict[str, float] = {}
        self.last_update = 0
        self.api_url = "https://api.coingecko.com/api/v3/coins/markets"
        
    async def update_market_caps(self):
        """Fetches market cap for top 1000 coins from CoinGecko."""
        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    "vs_currency": "usd",
                    "order": "market_cap_desc",
                    "per_page": 250,
                    "page": 1,
                    "sparkline": "false"
                }
                # CoinGecko allows 250 per page. We can fetch 2-4 pages to cover most coins.
                new_caps = {}
                for page in range(1, 5): 
                    params["page"] = page
                    async with session.get(self.api_url, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            for coin in data:
                                symbol = coin["symbol"].upper()
                                new_caps[symbol] = coin.get("market_cap", 0)
                        else:
                            logger.error(f"CoinGecko API error: {response.status}")
                            break
                
                if new_caps:
                    self.market_caps = new_caps
                    logger.info(f"Updated market caps for {len(self.market_caps)} coins.")
        except Exception as e:
            logger.error(f"Error updating market caps: {e}")

    def get_market_cap(self, ticker: str) -> float:
        """Returns market cap for a given ticker (e.g., 'BTC')."""
        # Ticker on BingX is usually 'BTC/USDT' or 'BTC-USDT'
        symbol = ticker.split('/')[0].split('-')[0].upper()
        return self.market_caps.get(symbol, 0)
