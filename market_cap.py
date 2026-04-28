import aiohttp
import asyncio
import logging
import os
from typing import Dict

logger = logging.getLogger(__name__)

class MarketCapProvider:
    def __init__(self):
        self.market_caps: Dict[str, float] = {}
        self.cmc_api_key = os.getenv("COINMARKETCAP_API_KEY")
        
    async def update_market_caps(self):
        """Fetches market cap data. Prefers CMC if API key is present."""
        if self.cmc_api_key:
            await self.update_via_cmc()
        else:
            await self.update_via_coingecko()

    async def update_via_cmc(self):
        """Fetches top 500 coins via CoinMarketCap API."""
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
        params = {
            "start": "1",
            "limit": "1000",
            "convert": "USD"
        }
        headers = {
            "X-CMC_PRO_API_KEY": self.cmc_api_key,
            "Accept": "application/json"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        new_caps = {}
                        for coin in data["data"]:
                            symbol = coin["symbol"].upper()
                            mcap = coin["quote"]["USD"]["market_cap"]
                            # Если символ уже есть, сохраняем тот, у которого капа больше (защита от щиткоинов-дублей)
                            if symbol not in new_caps or mcap > new_caps[symbol]:
                                new_caps[symbol] = mcap
                        
                        self.market_caps.update(new_caps)
                        logger.info(f"Market caps updated via CMC. Total coins: {len(self.market_caps)}")
                    else:
                        logger.error(f"CMC API error: {response.status}")
        except Exception as e:
            logger.error(f"Error updating via CMC: {e}")

    async def update_via_coingecko(self):
        """Fallback to CoinGecko (less reliable on Render)."""
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {"vs_currency": "usd", "order": "market_cap_desc", "per_page": 250, "page": 1}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        new_caps = {coin["symbol"].upper(): coin.get("market_cap", 0) for coin in data}
                        self.market_caps.update(new_caps)
                        logger.info(f"Market caps updated via CoinGecko. Total coins: {len(self.market_caps)}")
                    else:
                        logger.error(f"⚠️ CoinGecko failed ({response.status}). Market Cap filtering will NOT work. Add COINMARKETCAP_API_KEY to Environment Variables on Render!")
        except Exception as e:
            logger.error(f"❌ Error updating via CoinGecko: {e}")

    def get_market_cap(self, ticker: str) -> float:
        # 1. Сначала убираем USDT, двоеточия и слэши
        symbol = ticker.split('/')[0].split('-')[0].split(':')[0].upper()
        
        # 2. Убираем числовые префиксы (например, 1000PEPE -> PEPE)
        import re
        symbol = re.sub(r'^\d+', '', symbol)
        
        # Fallback for majors if API is down
        majors = {"BTC": 1000000000000, "ETH": 300000000000, "SOL": 60000000000, "BNB": 80000000000}
        cap = self.market_caps.get(symbol, 0)
        if cap == 0 and symbol in majors:
            return majors[symbol]
        return cap
