import asyncio
import logging
from scanner import PumpScanner
from exchange import BingXClient
from market_cap import MarketCapProvider
from bot import TelegramNotifier
from database import init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

async def main():
    # Initialize Database
    await init_db()
    
    # Initialize components
    exchange = BingXClient()
    mc_provider = MarketCapProvider()
    notifier = TelegramNotifier()
    
    scanner = PumpScanner(exchange, mc_provider, notifier)
    
    try:
        await scanner.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        await exchange.close()
        await notifier.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
