import asyncio
import logging
import os
from aiohttp import web
from scanner import PumpScanner
from exchange import BingXClient
from market_cap import MarketCapProvider
from notifier import TelegramNotifier
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

# Web server for Render health checks
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.add_routes([web.get('/', handle)])
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"Web server started on port {port}")

async def main():
    # Initialize Database
    await init_db()
    
    # Start web server in background
    asyncio.create_task(start_web_server())
    
    # Initialize components
    exchange = BingXClient()
    mc_provider = MarketCapProvider()
    notifier = TelegramNotifier()
    
    # Give notifier access to exchange for live tests
    notifier.exchange = exchange
    notifier.mc_provider = mc_provider
    
    # Start Telegram bot polling in background (to handle /start command)
    asyncio.create_task(notifier.dp.start_polling(notifier.bot))
    
    scanner = PumpScanner(exchange, mc_provider, notifier)
    
    try:
        await scanner.run()
    except Exception as e:
        logger.error(f"Unexpected error in scanner: {e}")
    finally:
        await exchange.close()
        await notifier.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
