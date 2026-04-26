from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import logging
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self):
        self.bot = Bot(token=TELEGRAM_BOT_TOKEN)
        self.dp = Dispatcher()
        self.chat_id = TELEGRAM_CHAT_ID
        
        # Регистрируем обработчики
        self.dp.message.register(self.send_welcome, Command("start"))
        self.dp.message.register(self.send_test_signal, Command("test"))

    async def send_welcome(self, message: types.Message):
        """Ответ на команду /start"""
        await message.reply(
            "Привет! Я бот для мониторинга пампов на BingX.\n\n"
            "🚀 Отправь мне команду /test, чтобы я прислал пробный сигнал в твой канал."
        )

    async def send_test_signal(self, message: types.Message):
        """Отправка тестового сигнала в канал по команде /test"""
        await message.reply("Отправляю тестовый сигнал в канал...")
        await self.send_signal(
            emoji="🚨",
            symbol="BTC/USDT (TEST)",
            price=65432.10,
            change_pct=35.5,
            market_cap=1200000000000,
            volume_24h=35000000000,
            url="https://bingx.com/en-us/futures/forward/BTC-USDT"
        )

    async def send_signal(self, 
                          emoji: str, 
                          symbol: str, 
                          price: float, 
                          change_pct: float, 
                          market_cap: float, 
                          volume_24h: float,
                          url: str):
        """Send a pump signal to Telegram."""
        message = (
            f"{emoji} <b>PUMP ALERT!</b> {emoji}\n\n"
            f"<b>Ticker:</b> {symbol}\n"
            f"<b>Price:</b> {price:.6f} USDT\n"
            f"<b>1h Change:</b> {change_pct:+.2f}%\n"
            f"<b>Volume 24h:</b> ${volume_24h:,.0f}\n"
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
