from aiogram import Bot, Dispatcher
import logging
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self):
        self.bot = Bot(token=TELEGRAM_BOT_TOKEN)
        self.dp = Dispatcher()
        self.chat_id = TELEGRAM_CHAT_ID

    async def send_signal(self, 
                          emoji: str, 
                          symbol: str, 
                          price: float, 
                          change_pct: float, 
                          market_cap: float, 
                          url: str):
        """Send a pump signal to Telegram."""
        message = (
            f"{emoji} <b>PUMP ALERT!</b> {emoji}\n\n"
            f"<b>Ticker:</b> {symbol}\n"
            f"<b>Price:</b> {price:.6f} USDT\n"
            f"<b>1h Change:</b> {change_pct:+.2f}%\n"
            f"<b>Market Cap:</b> ${market_cap:,.0f}\n\n"
            f"<a href='{url}'>Trade on BingX</a>"
        )
        
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode="HTML",
                disable_web_page_preview=False
            )
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")

    async def close(self):
        session = await self.bot.get_session()
        await session.close()
