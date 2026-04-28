from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
import logging
from datetime import datetime
from database import get_last_signal_from_db
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from chart_generator import generate_chart

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
        self.dp.message.register(self.check_coin, Command("check"))

    async def send_welcome(self, message: types.Message):
        """Ответ на команду /start"""
        await message.reply(
            "Привет! Я бот для мониторинга пампов на BingX.\n\n"
            "🚀 <b>/test</b> — прислать последний памп или лидера роста.\n"
            "🔍 <b>/check SYMBOL</b> — проверить данные конкретной монеты (например: /check APE)",
            parse_mode="HTML"
        )

    async def check_coin(self, message: types.Message):
        """Проверка параметров конкретной монеты для диагностики"""
        if not self.exchange or not self.mc_provider:
            await message.reply("⏳ Бот еще загружается...")
            return

        args = message.text.split()
        if len(args) < 2:
            await message.reply("Введите символ после команды, например: /check APE")
            return

        symbol_to_check = args[1].upper()
        await message.reply(f"🔍 Проверяю данные для <b>{symbol_to_check}</b>...", parse_mode="HTML")

        try:
            # Ищем тикер на бирже
            tickers = await self.exchange.get_all_tickers()
            found_symbol = None
            for s in tickers.keys():
                if symbol_to_check in s.upper():
                    found_symbol = s
                    break
            
            if not found_symbol:
                await message.reply(f"❌ Монета {symbol_to_check} не найдена на BingX (USDT).")
                return

            price = tickers[found_symbol]['price']
            volume = tickers[found_symbol]['volume']
            mc = self.mc_provider.get_market_cap(found_symbol)
            
            from config import MIN_MARKET_CAP, MIN_VOLUME_24H
            
            status_mc = "✅ OK" if mc >= MIN_MARKET_CAP else f"❌ LOW (Need ${MIN_MARKET_CAP:,.0f})"
            status_vol = "✅ OK" if volume >= MIN_VOLUME_24H else f"❌ LOW (Need ${MIN_VOLUME_24H:,.0f})"

            response = (
                f"📊 <b>Данные для {found_symbol}:</b>\n\n"
                f"💰 <b>Цена:</b> {price:.6f} USDT\n"
                f"💎 <b>Market Cap:</b> ${mc:,.0f} ({status_mc})\n"
                f"📈 <b>Volume 24h:</b> ${volume:,.0f} ({status_vol})\n\n"
                f"<i>Если всё OK, бот пришлет сигнал при росте цены более 7% за час.</i>"
            )
            await message.reply(response, parse_mode="HTML")
            
        except Exception as e:
            logger.error(f"Error in check_coin: {e}")
            await message.reply(f"Ошибка при проверке: {e}")

    async def send_test_signal(self, message: types.Message):
        """Поиск последнего сигнала в базе или поиск топ-гейнера на рынке прямо сейчас"""
        last_data = await get_last_signal_from_db()
        
        if last_data:
            dt_object = datetime.fromtimestamp(last_data["timestamp"])
            formatted_time = dt_object.strftime("%d.%m.%Y %H:%M:%S")
            await message.reply(f"✅ Нашел последний сохраненный памп (от {formatted_time}). Отправляю...")
            await self.send_signal(
                emoji=last_data["emoji"],
                symbol=last_data["symbol"],
                price=last_data["price"],
                change_pct=last_data["change_pct"],
                market_cap=last_data["mc"],
                volume_24h=last_data["volume"],
                url=last_data["url"]
            )
            return

        # Если истории нет, ищем лидера роста на рынке прямо сейчас
        if not self.exchange or not self.mc_provider:
            await message.reply("⏳ Бот еще инициализируется, подождите пару секунд...")
            return

        await message.reply("🔍 В истории пока пусто. Ищу лидера роста на рынке прямо сейчас...")
        
        try:
            tickers = await self.exchange.exchange.fetch_tickers()
            usdt_tickers = [t for s, t in tickers.items() if ('/USDT' in s or ':USDT' in s) and t['percentage'] is not None]
            
            if not usdt_tickers:
                await message.reply("Не удалось получить данные с биржи.")
                return

            top_coin = max(usdt_tickers, key=lambda x: x['percentage'])
            symbol = top_coin['symbol']
            price = top_coin['last']
            change_24h = top_coin['percentage']
            volume = top_coin['quoteVolume']
            mc = self.mc_provider.get_market_cap(symbol)
            url = self.exchange.get_trading_url(symbol)
            
            await self.send_signal(
                emoji="📈",
                symbol=symbol,
                price=price,
                change_pct=change_24h,
                market_cap=mc,
                volume_24h=volume,
                url=url
            )
        except Exception as e:
            logger.error(f"Error in live test: {e}")
            await message.reply(f"Ошибка при поиске данных: {e}")

    async def send_signal(self, emoji, symbol, price, change_pct, market_cap, volume_24h, url):
        """Стандартный метод для реального сканера с генерацией графика"""
        now_str = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        
        text = (
            f"{emoji} <b>PUMP ALERT!</b> {emoji}\n\n"
            f"<b>Ticker:</b> {symbol}\n"
            f"<b>Price:</b> {price:.6f} USDT\n"
            f"<b>Change:</b> {change_pct:+.2f}%\n"
            f"<b>Volume 24h:</b> ${volume_24h:,.0f}\n"
            f"<b>Market Cap:</b> ${market_cap:,.0f}\n"
            f"<b>Time:</b> {now_str}\n"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📈 Trade on BingX", url=url),
                InlineKeyboardButton(text="📊 TradingView", url=f"https://www.tradingview.com/chart/?symbol=BINGX:{symbol.replace('/', '').replace(':USDT', '')}")
            ]
        ])

        chart_buf = None
        if self.exchange:
            try:
                ohlcv = await self.exchange.fetch_ohlcv(symbol)
                if ohlcv:
                    chart_buf = generate_chart(ohlcv, symbol)
            except Exception as e:
                logger.error(f"Could not generate chart for {symbol}: {e}")

        try:
            sent_msg = None
            if chart_buf:
                photo = BufferedInputFile(chart_buf.read(), filename=f"{symbol}_chart.png")
                sent_msg = await self.bot.send_photo(
                    chat_id=self.chat_id,
                    photo=photo,
                    caption=text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                sent_msg = await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            return sent_msg.message_id if sent_msg else None
        except Exception as e:
            logger.error(f"Error sending signal to Telegram: {e}")
            return None

    async def update_signal(self, message_id, emoji, symbol, price, change_pct, market_cap, volume_24h, url):
        """Обновление существующего сообщения при продолжении пампа"""
        now_str = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        
        text = (
            f"{emoji} <b>PUMP UPDATE! (STILL GROWING)</b> {emoji}\n\n"
            f"<b>Ticker:</b> {symbol}\n"
            f"<b>Current Price:</b> {price:.6f} USDT\n"
            f"<b>New Change:</b> {change_pct:+.2f}%\n"
            f"<b>Volume 24h:</b> ${volume_24h:,.0f}\n"
            f"<b>Market Cap:</b> ${market_cap:,.0f}\n"
            f"<b>Updated At:</b> {now_str}\n"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📈 Trade on BingX", url=url),
                InlineKeyboardButton(text="📊 TradingView", url=f"https://www.tradingview.com/chart/?symbol=BINGX:{symbol.replace('/', '').replace(':USDT', '')}")
            ]
        ])

        try:
            await self.bot.edit_message_caption(
                chat_id=self.chat_id,
                message_id=message_id,
                caption=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except Exception as e:
            try:
                await self.bot.edit_message_text(
                    chat_id=self.chat_id,
                    message_id=message_id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            except Exception as e2:
                logger.error(f"Error updating signal {message_id}: {e2}")

    async def close(self):
        session = await self.bot.get_session()
        await session.close()
