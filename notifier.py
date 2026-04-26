from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import logging
from datetime import datetime
from database import get_last_signal_from_db
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
            "🚀 Отправь мне команду /test, чтобы я прислал самый последний реальный памп из базы данных."
        )

    async def send_test_signal(self, message: types.Message):
        """Поиск самого последнего реального пампа в базе данных"""
        last_data = await get_last_signal_from_db()
        
        if not last_data:
            await message.reply(
                "❌ В базе данных пока нет реальных сигналов.\n"
                "Бот должен проработать какое-то время и найти первый памп, чтобы он сохранился в историю."
            )
            return

        # Форматируем дату
        dt_object = datetime.fromtimestamp(last_data["timestamp"])
        formatted_time = dt_object.strftime("%d.%m.%Y %H:%M:%S")

        await message.reply(f"Нашел последний реальный сигнал в базе (от {formatted_time}). Отправляю в канал...")
        
        # Специальный формат для теста с датой
        test_message = (
            f"{last_data['emoji']} <b>PUMP ALERT! (REAL TEST)</b> {last_data['emoji']}\n\n"
            f"<b>Ticker:</b> {last_data['symbol']}\n"
            f"<b>Price:</b> {last_data['price']:.6f} USDT\n"
            f"<b>1h Change:</b> {last_data['change_pct']:+.2f}%\n"
            f"<b>Volume 24h:</b> ${last_data['volume']:,.0f}\n"
            f"<b>Market Cap:</b> ${last_data['mc']:,.0f}\n"
            f"<b>Signal Date:</b> {formatted_time}\n\n"
            f"<a href='{last_data['url']}'>Trade on BingX</a>"
        )

        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=test_message,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Failed to send test message: {e}")

    async def send_signal(self, 
                          emoji: str, 
                          symbol: str, 
                          price: float, 
                          change_pct: float, 
                          market_cap: float, 
                          volume_24h: float,
                          url: str):
        """Стандартный формат сигнала для реального времени"""
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
