from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
import logging
from datetime import datetime
from database import get_last_signal_from_db
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
import config
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
        self.dp.message.register(self.send_help, Command("help"))
        self.dp.message.register(self.send_test_signal, Command("test"))
        self.dp.message.register(self.check_coin, Command("check"))
        self.dp.message.register(self.change_settings, Command("settings"))
        self.dp.message.register(self.debug_info, Command("debug"))

    async def send_welcome(self, message: types.Message):
        """Ответ на команду /start"""
        text = (
            "👋 <b>Mega Pump Bot Online!</b>\n\n"
            "Я мониторю фьючерсы BingX (5м и 60м).\n\n"
            "📌 <b>Основные команды:</b>\n"
            "🚀 /test — тест сигнала\n"
            "🔍 /check [SYMBOL] — данные монеты\n"
            "🛠 /debug — текущая ситуация (почему нет сигналов)\n"
            "❓ /help — все команды"
        )
        await message.reply(text, parse_mode="HTML")

    async def debug_info(self, message: types.Message):
        """Показать текущее состояние рынка глазами бота"""
        if not self.exchange or not self.mc_provider:
            await message.reply("⏳ Бот еще загружается...")
            return

        try:
            tickers = await self.exchange.exchange.fetch_tickers()
            usdt_tickers = [t for s, t in tickers.items() if ('/USDT' in s or ':USDT' in s) and t['percentage'] is not None]
            
            # Сортируем по росту за 24ч
            top_gainers = sorted(usdt_tickers, key=lambda x: x['percentage'], reverse=True)[:5]
            
            response = "🛠 <b>Debug Mode: Топ-5 лидеров прямо сейчас</b>\n\n"
            
            for t in top_gainers:
                sym = t['symbol']
                pct = t['percentage']
                vol = t['quoteVolume']
                mc = self.mc_provider.get_market_cap(sym)
                
                status = "✅ Проходит"
                if mc < config.MIN_MARKET_CAP: status = f"❌ Low MC (${mc:,.0f})"
                elif vol < config.MIN_VOLUME_24H: status = f"❌ Low Vol (${vol:,.0f})"
                
                response += f"• <b>{sym}</b>: {pct:+.2f}% | MC: ${mc:,.0f} | {status}\n"
            
            response += f"\n⚙️ <b>Порог:</b> {config.PUMP_THRESHOLD}% за час\n"
            response += f"📊 <b>Фильтры:</b> MC > ${config.MIN_MARKET_CAP:,.0f}, Vol > ${config.MIN_VOLUME_24H:,.0f}"
            
            await message.reply(response, parse_mode="HTML")
            
        except Exception as e:
            await message.reply(f"Ошибка дебага: {e}")

    async def send_help(self, message: types.Message):
        """Ответ на команду /help"""
        text = (
            "📖 <b>Список команд:</b>\n\n"
            "🚀 <b>/test</b> — лидер роста\n"
            "🔍 <b>/check [SYMBOL]</b> — досье на монету\n"
            "🛠 <b>/debug</b> — статус фильтров для лидеров\n"
            "⚙️ <b>/settings</b> — текущие настройки\n"
            "🛠 <b>/settings mc [число]</b>\n"
            "🛠 <b>/settings vol [число]</b>\n"
            "🛠 <b>/settings pump [число]</b>"
        )
        await message.reply(text, parse_mode="HTML")

    async def change_settings(self, message: types.Message):
        """Команда для изменения настроек"""
        args = message.text.split()
        if len(args) < 3:
            await message.reply(
                "📈 <b>Текущие настройки:</b>\n\n"
                f"💎 <b>Min Market Cap:</b> ${config.MIN_MARKET_CAP:,.0f}\n"
                f"📊 <b>Min Volume 24h:</b> ${config.MIN_VOLUME_24H:,.0f}\n"
                f"⚡️ <b>Pump Threshold:</b> {config.PUMP_THRESHOLD}% за час\n\n"
                "Чтобы изменить, используйте:\n"
                "<code>/settings mc 5000000</code>",
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
                await message.reply(f"✅ Порог пампа изменен на: <b>{new_value}%</b>", parse_mode="HTML")
            else:
                await message.reply("Используйте mc, vol или pump.")
        except ValueError:
            await message.reply("Введите числовое значение.")

    async def check_coin(self, message: types.Message):
        """Проверка параметров монеты"""
        if not self.exchange or not self.mc_provider:
            await message.reply("⏳ Загрузка...")
            return

        args = message.text.split()
        if len(args) < 2:
            await message.reply("Введите символ, например: /check APE")
            return

        symbol_to_check = args[1].upper()
        try:
            tickers = await self.exchange.get_all_tickers()
            found_symbol = next((s for s in tickers.keys() if symbol_to_check in s.upper()), None)
            
            if not found_symbol:
                await message.reply(f"❌ {symbol_to_check} не найден.")
                return

            price = tickers[found_symbol]['price']
            volume = tickers[found_symbol]['volume']
            mc = self.mc_provider.get_market_cap(found_symbol)
            oi = await self.exchange.fetch_open_interest(found_symbol)
            indicators = await self.exchange.get_indicators(found_symbol)
            
            status_mc = "✅" if mc >= config.MIN_MARKET_CAP else "❌"
            status_vol = "✅" if volume >= config.MIN_VOLUME_24H else "❌"

            response = (
                f"📊 <b>{found_symbol}:</b>\n\n"
                f"💰 <b>Цена:</b> {price:.6f}\n"
                f"💎 <b>MC:</b> ${mc:,.0f} ({status_mc})\n"
                f"📈 <b>Vol:</b> ${volume:,.0f} ({status_vol})\n"
                f"📊 <b>OI:</b> ${oi:,.0f if oi else 0}\n"
                f"📉 <b>RSI:</b> {indicators.get('rsi', 0):.2f}\n"
            )
            await message.reply(response, parse_mode="HTML")
        except Exception as e:
            await message.reply(f"Ошибка: {e}")

    async def send_test_signal(self, message: types.Message):
        """Тест сигнала на лидере роста"""
        if not self.exchange or not self.mc_provider:
            await message.reply("⏳ Загрузка...")
            return
        
        try:
            tickers = await self.exchange.exchange.fetch_tickers()
            usdt_tickers = [t for s, t in tickers.items() if ('/USDT' in s or ':USDT' in s) and t['percentage'] is not None]
            top_coin = max(usdt_tickers, key=lambda x: x['percentage'])
            
            await self.send_signal(
                emoji="📈",
                symbol=top_coin['symbol'],
                price=top_coin['last'],
                change_pct=top_coin['percentage'],
                market_cap=self.mc_provider.get_market_cap(top_coin['symbol']),
                volume_24h=top_coin['quoteVolume'],
                url=self.exchange.get_trading_url(top_coin['symbol'])
            )
        except Exception as e:
            await message.reply(f"Ошибка теста: {e}")

    async def send_signal(self, emoji, symbol, price, change_pct, market_cap, volume_24h, url, oi=None, rsi=None, ema=None):
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
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="📈 Trade", url=url),
            InlineKeyboardButton(text="📊 Chart", url=f"https://www.tradingview.com/chart/?symbol=BINGX:{symbol.replace('/', '').replace(':USDT', '')}")
        ]])
        
        try:
            chart_buf = None
            if self.exchange:
                ohlcv = await self.exchange.fetch_ohlcv(symbol)
                if ohlcv: chart_buf = generate_chart(ohlcv, symbol)
            
            if chart_buf:
                photo = BufferedInputFile(chart_buf.read(), filename="chart.png")
                await self.bot.send_photo(self.chat_id, photo=photo, caption=text, reply_markup=keyboard, parse_mode="HTML")
            else:
                await self.bot.send_message(self.chat_id, text=text, reply_markup=keyboard, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Error: {e}")

    async def update_signal(self, message_id, emoji, symbol, price, change_pct, market_cap, volume_24h, url, oi=None, rsi=None, ema=None):
        now_str = datetime.now().strftime("%H:%M:%S")
        text = (
            f"{emoji} <b>PUMP UPDATE!</b> {emoji}\n\n"
            f"<b>Ticker:</b> {symbol}\n"
            f"<b>Price:</b> {price:.6f}\n"
            f"<b>New Change:</b> {change_pct:+.2f}%\n"
            f"<b>Updated At:</b> {now_str}\n"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📈 Trade", url=url)]])
        try:
            await self.bot.edit_message_caption(self.chat_id, message_id, caption=text, reply_markup=keyboard, parse_mode="HTML")
        except:
            pass

    async def close(self):
        await (await self.bot.get_session()).close()
