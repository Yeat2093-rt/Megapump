import aiohttp
import asyncio
import logging
from typing import Dict

logger = logging.getLogger(__name__)

class MarketCapProvider:
    def __init__(self):
        self.market_caps: Dict[str, float] = {}
        self.last_update = 0
        self.api_url = "https://api.coingecko.com/api/v3/coins/markets"
        
    async def update_market_caps(self):
        """Fetches market cap for top coins from CoinGecko with rate limit handling."""
        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    "vs_currency": "usd",
                    "order": "market_cap_desc",
                    "per_page": 250,
                    "sparkline": "false"
                }
                
                new_caps = {}
                # Fetch only 2 pages (500 coins) to stay within limits and cover 99% of BingX assets
                for page in range(1, 3): 
                    params["page"] = page
                    async with session.get(self.api_url, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            for coin in data:
                                symbol = coin["symbol"].upper()
                                new_caps[symbol] = coin.get("market_cap", 0)
                            logger.info(f"Fetched page {page} from CoinGecko.")
                        elif response.status == 429:
                            logger.warning(f"CoinGecko rate limit hit (429) on page {page}. Waiting...")
                            break # Stop fetching for now
                        else:
                            logger.error(f"CoinGecko API error: {response.status}")
                            break
                    
                    # Small sleep between pages to be gentle
                    await asyncio.sleep(10) 
                
                if new_caps:
                    # Merge with existing instead of overwriting completely if partial success
                    self.market_caps.update(new_caps)
                    logger.info(f"Market caps updated. Total coins in cache: {len(self.market_caps)}")
                else:
                    logger.warning("No market cap data received in this cycle.")
                    
        except Exception as e:
            logger.error(f"Error updating market caps: {e}")

    def get_market_cap(self, ticker: str) -> float:
        """Returns market cap for a given ticker."""
        # Clean ticker: BTC/USDT:USDT -> BTC
        symbol = ticker.split('/')[0].split('-')[0].split(':')[0].upper()
        
        # Fallback for major coins if API fails
        majors = {"BTC": 1000000000000, "ETH": 300000000000, "SOL": 60000000000, "BNB": 80000000000}
        
        cap = self.market_caps.get(symbol, 0)
        if cap == 0 and symbol in majors:
            return majors[symbol]
            
        return cap
