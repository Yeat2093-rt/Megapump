from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import logging
import state
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
            "🚀 Отправь мне команду /test, чтобы я повторно прислал в канал самый последний найденный реальный памп."
        )

    async def send_test_signal(self, message: types.Message):
        """Переотправка последнего реального сигнала"""
        last_data = state.get_last_signal()
        
        if not last_data:
            await message.reply(
                "❌ Реальных сигналов еще не было с момента запуска.\n"
                "Бот должен проработать минимум 60 минут, чтобы найти первый памп."
            )
            return

        await message.reply("Переотправляю последний реальный сигнал в канал...")
        await self.send_signal(
            emoji=last_data["emoji"],
            symbol=last_data["symbol"] + " (RE-TEST)",
            price=last_data["price"],
            change_pct=last_data["change_pct"],
            market_cap=last_data["mc"],
            volume_24h=last_data["volume"],
            url=last_data["url"]
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
