from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
import logging
from datetime import datetime
from database import get_last_signal_from_db
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
import config  # Импортируем весь модуль для изменения настроек
from chart_generator import generate_chart

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self):
        self.bot = Bot(token=TELEGRAM_BOT_TOKEN)
        self.dp = Dispatcher()
        self.chat_id = TELEGRAM_CHAT_ID
        self.exchange = None  
        self.mc_provider = None 
        
        # Регистрируем обработчики
        self.dp.message.register(self.send_welcome, Command("start"))
        self.dp.message.register(self.send_test_signal, Command("test"))
        self.dp.message.register(self.check_coin, Command("check"))
        self.dp.message.register(self.change_settings, Command("settings"))

    async def send_welcome(self, message: types.Message):
        """Ответ на команду /start"""
        await message.reply(
            "Привет! Я бот для мониторинга пампов на BingX.\n\n"
            "🚀 <b>/test</b> — прислать лидер роста.\n"
            "🔍 <b>/check SYMBOL</b> — проверить данные монеты.\n"
            "⚙️ <b>/settings mc [число]</b> — изменить Min Market Cap.\n"
            "⚙️ <b>/settings vol [число]</b> — изменить Min Volume 24h.\n"
            "⚙️ <b>/settings pump [число]</b> — изменить порог пампа (в % за час).",
            parse_mode="HTML"
        )

    async def change_settings(self, message: types.Message):
        """Временная команда для изменения настроек модератором"""
        args = message.text.split()
        if len(args) < 3:
            await message.reply(
                "📈 <b>Текущие настройки:</b>\n"
                f"Min Market Cap: ${config.MIN_MARKET_CAP:,.0f}\n"
                f"Min Volume 24h: ${config.MIN_VOLUME_24H:,.0f}\n"
                f"Pump Threshold: {config.PUMP_THRESHOLD}%\n\n"
                "Использование:\n"
                "<code>/settings mc 1000000</code>\n"
                "<code>/settings vol 500000</code>\n"
                "<code>/settings pump 5</code>",
                parse_mode="HTML"
            )
            return

        cmd_type = args[1].lower()
        try:
            new_value = float(args[2])
            if cmd_type == 'mc':
                config.MIN_MARKET_CAP = new_value
                await message.reply(f"✅ Min Market Cap изменен на: <b>${new_value:,.0f}</b>", parse_mode="HTML")
            elif cmd_type == 'vol':
                config.MIN_VOLUME_24H = new_value
                await message.reply(f"✅ Min Volume 24h изменен на: <b>${new_value:,.0f}</b>", parse_mode="HTML")
            elif cmd_type == 'pump':
                config.PUMP_THRESHOLD = new_value
                await message.reply(f"✅ Порог пампа изменен на: <b>{new_value}%</b> за час", parse_mode="HTML")
            else:
                await message.reply("Неизвестный параметр. Используйте mc, vol или pump.")
        except ValueError:
            await message.reply("Ошибка: введите числовое значение.")

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
            tickers = await self.exchange.get_all_tickers()
            found_symbol = None
            for s in tickers.keys():
                if symbol_to_check in s.upper():
                    found_symbol = s
                    break
            
            if not found_symbol:
                await message.reply(f"❌ Монета {symbol_to_check} не найдена на BingX (Futures).")
                return

            price = tickers[found_symbol]['price']
            volume = tickers[found_symbol]['volume']
            mc = self.mc_provider.get_market_cap(found_symbol)
            
            oi = await self.exchange.fetch_open_interest(found_symbol)
            indicators = await self.exchange.get_indicators(found_symbol)
            rsi = indicators.get('rsi')
            ema = indicators.get('ema')
            
            status_mc = "✅ OK" if mc >= config.MIN_MARKET_CAP else f"❌ LOW (Need ${config.MIN_MARKET_CAP:,.0f})"
            status_vol = "✅ OK" if volume >= config.MIN_VOLUME_24H else f"❌ LOW (Need ${config.MIN_VOLUME_24H:,.0f})"

            oi_str = f"${oi:,.0f}" if oi else "N/A"
            rsi_str = f"{rsi:.2f}" if rsi else "N/A"
            ema_str = f"{ema:.6f}" if ema else "N/A"

            response = (
                f"📊 <b>Данные для {found_symbol}:</b>\n\n"
                f"💰 <b>Цена:</b> {price:.6f} USDT\n"
                f"💎 <b>Market Cap:</b> ${mc:,.0f} ({status_mc})\n"
                f"📈 <b>Volume 24h:</b> ${volume:,.0f} ({status_vol})\n"
                f"📊 <b>Open Interest:</b> {oi_str}\n"
                f"📉 <b>RSI (15m):</b> {rsi_str}\n"
                f"📈 <b>EMA 20 (15m):</b> {ema_str}\n\n"
                f"<i>Порог сигнала: {config.PUMP_THRESHOLD}% за час.</i>"
            )
            await message.reply(response, parse_mode="HTML")
            
        except Exception as e:
            logger.error(f"Error in check_coin: {e}")
            await message.reply(f"Ошибка при проверке: {e}")

    async def send_test_signal(self, message: types.Message):
        """Поиск лидера роста на рынке прямо сейчас"""
        if not self.exchange or not self.mc_provider:
            await message.reply("⏳ Бот еще инициализируется...")
            return

        await message.reply("🔍 Ищу лидера роста на рынке прямо сейчас...")
        
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
            
            oi = await self.exchange.fetch_open_interest(symbol)
            indicators = await self.exchange.get_indicators(symbol)
            
            await self.send_signal(
                emoji="📈",
                symbol=symbol,
                price=price,
                change_pct=change_24h,
                market_cap=mc,
                volume_24h=volume,
                url=url,
                oi=oi,
                rsi=indicators.get('rsi'),
                ema=indicators.get('ema')
            )
        except Exception as e:
            logger.error(f"Error in live test: {e}")
            await message.reply(f"Ошибка при поиске данных: {e}")

    async def send_signal(self, emoji, symbol, price, change_pct, market_cap, volume_24h, url, oi=None, rsi=None, ema=None):
        """Стандартный метод для реального сканера с генерацией графика"""
        now_str = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        
        oi_str = f"${oi:,.0f}" if oi else "N/A"
        rsi_str = f"{rsi:.2f}" if rsi else "N/A"
        ema_str = f"{ema:.6f}" if ema else "N/A"

        text = (
            f"{emoji} <b>PUMP ALERT!</b> {emoji}\n\n"
            f"<b>Ticker:</b> {symbol}\n"
            f"<b>Price:</b> {price:.6f} USDT\n"
            f"<b>Change:</b> {change_pct:+.2f}%\n"
            f"<b>Volume 24h:</b> ${volume_24h:,.0f}\n"
            f"<b>Market Cap:</b> ${market_cap:,.0f}\n"
            f"<b>Open Interest:</b> {oi_str}\n"
            f"<b>RSI (15m):</b> {rsi_str}\n"
            f"<b>EMA 20 (15m):</b> {ema_str}\n"
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

    async def update_signal(self, message_id, emoji, symbol, price, change_pct, market_cap, volume_24h, url, oi=None, rsi=None, ema=None):
        """Обновление существующего сообщения при продолжении пампа"""
        now_str = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        
        oi_str = f"${oi:,.0f}" if oi else "N/A"
        rsi_str = f"{rsi:.2f}" if rsi else "N/A"
        ema_str = f"{ema:.6f}" if ema else "N/A"

        text = (
            f"{emoji} <b>PUMP UPDATE! (STILL GROWING)</b> {emoji}\n\n"
            f"<b>Ticker:</b> {symbol}\n"
            f"<b>Current Price:</b> {price:.6f} USDT\n"
            f"<b>New Change:</b> {change_pct:+.2f}%\n"
            f"<b>Volume 24h:</b> ${volume_24h:,.0f}\n"
            f"<b>Market Cap:</b> ${market_cap:,.0f}\n"
            f"<b>Open Interest:</b> {oi_str}\n"
            f"<b>RSI (15m):</b> {rsi_str}\n"
            f"<b>EMA 20 (15m):</b> {ema_str}\n"
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
