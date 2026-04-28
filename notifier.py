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
            "📌 <b>Команды:</b>\n"
            "🔍 /check [SYMBOL] — данные\n"
            "🛠 /debug [SYMBOL] — диагностика\n"
            "⚙️ /settings — фильтры"
        )
        await message.reply(text, parse_mode="HTML")

    async def debug_info(self, message: types.Message):
        """Диагностика монеты или топа"""
        if not self.exchange or not self.mc_provider:
            await message.reply("⏳ Загрузка...")
            return
        args = message.text.split()
        symbol_to_search = args[1].upper() if len(args) > 1 else None
        try:
            tickers = await self.exchange.get_all_tickers()
            if symbol_to_search:
                found_symbol = next((s for s in tickers.keys() if symbol_to_search in s.upper()), None)
                if not found_symbol:
                    await message.reply(f"❌ <b>{symbol_to_search}</b> не найдена на фьючерсах.")
                    return
                mc = self.mc_provider.get_market_cap(found_symbol)
                vol = tickers[found_symbol]['volume']
                status_mc = "✅" if mc >= config.MIN_MARKET_CAP else f"❌ Low (Need ${config.MIN_MARKET_CAP:,.0f})"
                status_vol = "✅" if vol >= config.MIN_VOLUME_24H else f"❌ Low (Need ${config.MIN_VOLUME_24H:,.0f})"
                await message.reply(f"🛠 <b>{found_symbol}:</b>\nMC: ${mc:,.0f} {status_mc}\nVol: ${vol:,.0f} {status_vol}", parse_mode="HTML")
            else:
                top_gainers = sorted(tickers.items(), key=lambda x: x[1].get('percentage', 0) or 0, reverse=True)[:5]
                res = "🛠 <b>Топ-5 лидеров:</b>\n"
                for sym, d in top_gainers:
                    mc = self.mc_provider.get_market_cap(sym)
                    status = "✅" if (mc >= config.MIN_MARKET_CAP and d['volume'] >= config.MIN_VOLUME_24H) else "❌"
                    res += f"• {sym}: MC ${mc:,.0f} | {status}\n"
                await message.reply(res, parse_mode="HTML")
        except Exception as e:
            await message.reply(f"Ошибка: {e}")

    async def check_coin(self, message: types.Message):
        """Данные по монете"""
        if not self.exchange or not self.mc_provider: return
        args = message.text.split()
        if len(args) < 2: return
        symbol = args[1].upper()
        try:
            tickers = await self.exchange.get_all_tickers()
            found = next((s for s in tickers.keys() if symbol in s.upper()), None)
            if not found:
                await message.reply(f"❌ {symbol} не найден.")
                return
            mc = self.mc_provider.get_market_cap(found)
            vol = tickers[found]['volume']
            indicators = await self.exchange.get_indicators(found)
            res = (f"📊 <b>{found}:</b>\nPrice: {tickers[found]['price']:.6f}\nMC: ${mc:,.0f}\nVol: ${vol:,.0f}\n"
                   f"RSI: {indicators.get('rsi', 0):.2f}")
            await message.reply(res, parse_mode="HTML")
        except Exception as e:
            await message.reply(f"Ошибка: {e}")

    async def change_settings(self, message: types.Message):
        """Изменение настроек"""
        args = message.text.split()
        if len(args) < 3:
            await message.reply(f"📈 <b>Настройки:</b>\nMC: ${config.MIN_MARKET_CAP:,.0f}\nVol: ${config.MIN_VOLUME_24H:,.0f}\nPump: {config.PUMP_THRESHOLD}%", parse_mode="HTML")
            return
        cmd, val = args[1].lower(), float(args[2])
        if cmd == 'mc': config.MIN_MARKET_CAP = val
        elif cmd == 'vol': config.MIN_VOLUME_24H = val
        elif cmd == 'pump': config.PUMP_THRESHOLD = val
        await message.reply(f"✅ {cmd} обновлен.")

    async def send_help(self, message: types.Message):
        await message.reply("📖 <b>Команды:</b> /test, /check, /debug, /settings", parse_mode="HTML")

    async def send_test_signal(self, message: types.Message):
        if not self.exchange: return
        tickers = await self.exchange.get_all_tickers()
        sym = list(tickers.keys())[0]
        await self.send_signal("📈", sym, tickers[sym]['price'], 5.0, 10000000, 5000000, self.exchange.get_trading_url(sym))

    async def send_signal(self, emoji, symbol, price, change_pct, market_cap, volume_24h, url, oi=None, rsi=None, ema=None):
        now = datetime.now().strftime("%d.%m %H:%M")
        text = (f"{emoji} <b>PUMP!</b> {emoji}\n\n<b>{symbol}</b>\nPrice: {price:.6f}\nChange: {change_pct:+.2f}%\n"
                f"Vol: ${volume_24h:,.0f}\nMC: ${market_cap:,.0f}\nTime: {now}")
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="📈 Trade", url=url),
            InlineKeyboardButton(text="📊 Chart", url=f"https://www.tradingview.com/chart/?symbol=BINGX:{symbol.replace('/', '').replace(':USDT', '')}")
        ]])
        try:
            sent_msg = None
            chart_buf = None
            if self.exchange:
                ohlcv = await self.exchange.fetch_ohlcv(symbol)
                if ohlcv: chart_buf = generate_chart(ohlcv, symbol)
            if chart_buf:
                photo = BufferedInputFile(chart_buf.read(), filename="chart.png")
                sent_msg = await self.bot.send_photo(self.chat_id, photo=photo, caption=text, reply_markup=kb, parse_mode="HTML")
            else:
                sent_msg = await self.bot.send_message(self.chat_id, text=text, reply_markup=kb, parse_mode="HTML")
            return sent_msg.message_id if sent_msg else None
        except Exception as e:
            logger.error(f"Error: {e}")
            return None

    async def update_signal(self, message_id, emoji, symbol, price, change_pct, market_cap, volume_24h, url, oi=None, rsi=None, ema=None):
        pass

    async def close(self):
        await (await self.bot.get_session()).close()
