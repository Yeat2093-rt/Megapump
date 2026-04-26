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
        self.exchange = None  # Будет установлено из main.py
        self.mc_provider = None # Будет установлено из main.py
        
        # Регистрируем обработчики
        self.dp.message.register(self.send_welcome, Command("start"))
        self.dp.message.register(self.send_test_signal, Command("test"))

    async def send_welcome(self, message: types.Message):
        """Ответ на команду /start"""
        await message.reply(
            "Привет! Я бот для мониторинга пампов на BingX.\n\n"
            "🚀 Отправь мне команду /test, чтобы я прислал самый свежий реальный пример из рынка."
        )

    async def send_test_signal(self, message: types.Message):
        """Поиск последнего сигнала в базе или поиск топ-гейнера на рынке прямо сейчас"""
        last_data = await get_last_signal_from_db()
        
        if last_data:
            dt_object = datetime.fromtimestamp(last_data["timestamp"])
            formatted_time = dt_object.strftime("%d.%m.%Y %H:%M:%S")
            await message.reply(f"✅ Нашел последний сохраненный памп (от {formatted_time}). Отправляю...")
            await self.send_signal_internal(
                emoji=last_data["emoji"],
                symbol=last_data["symbol"] + " (HISTORY)",
                price=last_data["price"],
                change_pct=last_data["change_pct"],
                market_cap=last_data["mc"],
                volume_24h=last_data["volume"],
                url=last_data["url"],
                time_str=formatted_time
            )
            return

        # Если истории нет, ищем лидера роста на рынке прямо сейчас
        if not self.exchange or not self.mc_provider:
            await message.reply("⏳ Бот еще инициализируется, подождите пару секунд...")
            return

        await message.reply("🔍 В истории пока пусто. Ищу лидера роста на рынке прямо сейчас...")
        
        try:
            # Получаем все тикеры
            tickers = await self.exchange.exchange.fetch_tickers()
            usdt_tickers = [t for s, t in tickers.items() if ('/USDT' in s or ':USDT' in s) and t['percentage'] is not None]
            
            if not usdt_tickers:
                await message.reply("Не удалось получить данные с биржи.")
                return

            # Находим топ-гейнера за 24ч
            top_coin = max(usdt_tickers, key=lambda x: x['percentage'])
            symbol = top_coin['symbol']
            price = top_coin['last']
            change_24h = top_coin['percentage']
            volume = top_coin['quoteVolume']
            mc = self.mc_provider.get_market_cap(symbol)
            url = self.exchange.get_trading_url(symbol)
            
            now_str = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
            
            await self.send_signal_internal(
                emoji="📈",
                symbol=symbol + " (LIVE TOP)",
                price=price,
                change_pct=change_24h,
                market_cap=mc,
                volume_24h=volume,
                url=url,
                time_str=now_str
            )
        except Exception as e:
            logger.error(f"Error in live test: {e}")
            await message.reply(f"Ошибка при поиске данных: {e}")

    async def send_signal_internal(self, emoji, symbol, price, change_pct, market_cap, volume_24h, url, time_str):
        """Внутренний метод для отправки оформленного сообщения"""
        message = (
            f"{emoji} <b>PUMP ALERT! (REAL DATA)</b> {emoji}\n\n"
            f"<b>Ticker:</b> {symbol}\n"
            f"<b>Price:</b> {price:.6f} USDT\n"
            f"<b>Change (24h/1h):</b> {change_pct:+.2f}%\n"
            f"<b>Volume 24h:</b> ${volume_24h:,.0f}\n"
            f"<b>Market Cap:</b> ${market_cap:,.0f}\n"
            f"<b>Data Time:</b> {time_str}\n\n"
            f"<a href='{url}'>Trade on BingX</a>"
        )
        await self.bot.send_message(chat_id=self.chat_id, text=message, parse_mode="HTML")

    async def send_signal(self, emoji, symbol, price, change_pct, market_cap, volume_24h, url):
        """Стандартный метод для реального сканера"""
        now_str = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        await self.send_signal_internal(emoji, symbol, price, change_pct, market_cap, volume_24h, url, now_str)

    async def close(self):
        session = await self.bot.get_session()
        await session.close()
