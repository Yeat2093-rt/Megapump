import ccxt.async_support as ccxt
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class BingXClient:
    def __init__(self):
        self.exchange = ccxt.bingx({
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',  # Фокусируемся на фьючерсах (бессрочные свопы)
            }
        })

    async def get_all_tickers(self) -> Dict[str, Dict[str, float]]:
        """Fetch all USDT-M swap tickers and their current prices and volumes."""
        try:
            # Load markets first to ensure we have all symbols
            await self.exchange.load_markets()
            
            # Fetch tickers
            tickers = await self.exchange.fetch_tickers()
            
            # Filter for USDT pairs (usually futures/swaps on BingX have :USDT or /USDT)
            usdt_data = {}
            for symbol, data in tickers.items():
                # Проверяем, есть ли USDT в названии и не является ли это какой-то другой валютой
                if 'USDT' in symbol.upper():
                    if data['last'] is not None and data['quoteVolume'] is not None:
                        usdt_data[symbol] = {
                            'price': data['last'],
                            'volume': data['quoteVolume']
                        }
            
            logger.info(f"Total USDT pairs found on BingX: {len(usdt_data)}")
            return usdt_data
        except Exception as e:
            logger.error(f"Error fetching tickers from BingX: {e}")
            return {}

    async def close(self):
        await self.exchange.close()

    def get_trading_url(self, symbol: str) -> str:
        """Generate BingX trading URL for a symbol."""
        # Symbol format e.g., BTC/USDT:USDT -> BTC-USDT
        clean_symbol = symbol.replace('/', '-').replace(':USDT', '')
        return f"https://bingx.com/en-us/futures/forward/{clean_symbol}/"

    async def fetch_ohlcv(self, symbol: str, timeframe: str = '15m', limit: int = 60):
        """Fetch OHLCV data for a symbol."""
        try:
            ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            return ohlcv
        except Exception as e:
            logger.error(f"Error fetching OHLCV for {symbol}: {e}")
            return None
