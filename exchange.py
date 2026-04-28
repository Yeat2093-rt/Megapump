import ccxt.async_support as ccxt
import logging
import pandas as pd
from typing import List, Dict, Optional

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

    async def get_indicators(self, symbol: str) -> Dict[str, float]:
        """Calculate RSI and EMA for a symbol."""
        try:
            ohlcv = await self.fetch_ohlcv(symbol, timeframe='15m', limit=100)
            if not ohlcv:
                return {}
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # RSI Calculation
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            # EMA Calculation
            ema_20 = df['close'].ewm(span=20, adjust=False).mean()
            
            return {
                'rsi': rsi.iloc[-1],
                'ema': ema_20.iloc[-1]
            }
        except Exception as e:
            logger.error(f"Error calculating indicators for {symbol}: {e}")
            return {}

    async def fetch_open_interest(self, symbol: str) -> Optional[float]:
        """Fetch Open Interest for a symbol."""
        try:
            # BingX Open Interest via CCXT
            # Some exchanges have fetch_open_interest, some require implicit calls
            oi_data = await self.exchange.fetch_open_interest(symbol)
            if oi_data and 'openInterestAmount' in oi_data:
                return float(oi_data['openInterestAmount'])
            elif isinstance(oi_data, dict) and 'value' in oi_data:
                return float(oi_data['value'])
            return None
        except Exception as e:
            # Try alternative way if fetch_open_interest fails
            try:
                # Some versions of ccxt or BingX API might use different method
                params = {'symbol': symbol.replace('/', '-').replace(':USDT', '')}
                response = await self.exchange.public_get_open_interest(params)
                if response and 'data' in response and response['data']:
                    return float(response['data'][0].get('openInterest', 0))
            except:
                pass
            logger.debug(f"Could not fetch Open Interest for {symbol}: {e}")
            return None

    def get_trading_url(self, symbol: str) -> str:
        """Generate BingX trading URL for a symbol."""
        # Symbol format e.g., BTC/USDT:USDT -> BTC-USDT
        clean_symbol = symbol.replace('/', '-').replace(':USDT', '')
        return f"https://bingx.com/en-us/futures/forward/{clean_symbol}/"

    def get_deep_link(self, symbol: str) -> str:
        """Generate BingX deep link for mobile app."""
        clean_symbol = symbol.replace('/', '-').replace(':USDT', '')
        # Basic deep link to trade terminal
        return f"bingx://futures/trade?symbol={clean_symbol}"
