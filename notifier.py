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
            "📌 <b>Основные команды:</b>\n"
            "🔍 /check [SYMBOL] — данные монеты\n"
            "🛠 /debug [SYMBOL] — почему нет сигналов по монете\n"
            "⚙️ /settings — настройки фильтров"
        )
        await message.reply(text, parse_mode="HTML")

    async def debug_info(self, message: types.Message):
        """Детальная диагностика конкретной монеты"""
        if not self.exchange or not self.mc_provider:
            await message.reply("⏳ Загрузка...")
            return

        args = message.text.split()
        symbol_to_search = args[1].upper() if len(args) > 1 else None

        try:
            tickers = await self.exchange.get_all_tickers()
            
            if symbol_to_search:
                # Поиск конкретной монеты
                found_symbol = next((s for s in tickers.keys() if symbol_to_search in s.upper()), None)
                
                if not found_symbol:
                    await message.reply(f"❌ Монета <b>{symbol_to_search}</b> не найдена на фьючерсах BingX.\n"
                                      f"Проверьте, торгуется ли она именно в разделе Futures (Swap).", parse_mode="HTML")
                    return

                data = tickers[found_symbol]
                mc = self.mc_provider.get_market_cap(found_symbol)
                vol = data['volume']
                
                status_mc = "✅" if mc >= config.MIN_MARKET_CAP else "❌ ТУТ ОШИБКА: Слишком низкая капа"
                status_vol = "✅" if vol >= config.MIN_VOLUME_24H else "❌ ТУТ ОШИБКА: Слишком низкий объем"

                response = (
                    f"🛠 <b>Диагностика {found_symbol}:</b>\n\n"
                    f"💎 <b>Market Cap:</b> ${mc:,.0f} {status_mc}\n"
                    f"📊 <b>Volume 24h:</b> ${vol:,.0f} {status_vol}\n"
                    f"💰 <b>Цена:</b> {data['price']:.6f}\n\n"
                    f"Если везде стоят ✅, значит бот видит монету, но рост еще не достиг порога {config.PUMP_THRESHOLD}% за час."
                )
            else:
                # Общий дебаг лидеров
                usdt_tickers = [t for s, t in tickers.items() if t['price'] is not None]
                top_gainers = sorted(tickers.items(), key=lambda x: x[1].get('percentage', 0) or 0, reverse=True)[:5]
                
                response = "🛠 <b>Debug: Топ-5 лидеров роста</b>\n\n"
                for sym, data in top_gainers:
                    mc = self.mc_provider.get_market_cap(sym)
                    status = "✅" if (mc >= config.MIN_MARKET_CAP and data['volume'] >= config.MIN_VOLUME_24H) else "❌"
                    response += f"• {sym}: MC ${mc:,.0f} | {status}\n"
                
                response += f"\nИспользуйте <code>/debug ORCA</code> для проверки конкретной монеты."

            await message.reply(response, parse_mode="HTML")
            
        except Exception as e:
            await message.reply(f"Ошибка дебага: {e}")

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
            
            response = (
                f"📊 <b>{found_symbol}:</b>\n\n"
                f"💰 <b>Цена:</b> {price:.6f}\n"
                f"💎 <b>MC:</b> ${mc:,.0f}\n"
                f"📈 <b>Vol:</b> ${volume:,.0f}\n"
                f"📊 <b>OI:</b> ${oi:,.0f if oi else 0}\n"
                f"📉 <b>RSI:</b> {indicators.get('rsi', 0):.2f}\n"
            )
            await message.reply(response, parse_mode="HTML")
        except Exception as e:
            await message.reply(f"Ошибка: {e}")

    async def change_settings(self, message: types.Message):
        """Команда для изменения настроек"""
        args = message.text.split()
        if len(args) < 3:
            await message.reply(
                f"📈 <b>Настройки:</b>\n"
                f"Min MC: ${config.MIN_MARKET_CAP:,.0f}\n"
                f"Min Vol: ${config.MIN_VOLUME_24H:,.0f}\n"
                f"Pump: {config.PUMP_THRESHOLD}%",
                parse_mode="HTML"
            )
            return

        cmd_type, val = args[1].lower(), float(args[2])
        if cmd_type == 'mc': config.MIN_MARKET_CAP = val
        elif cmd_type == 'vol': config.MIN_VOLUME_24H = val
        elif cmd_type == 'pump': config.PUMP_THRESHOLD = val
        await message.reply(f"✅ Настройка {cmd_type} обновлена.")

    async def send_test_signal(self, message: types.Message):
        """Тест на лидере роста"""
        tickers = await self.exchange.get_all_tickers()
        top_sym = max(tickers, key=lambda x: tickers[x].get('price', 0)) # Упрощенно для теста
        await self.send_signal("📈", top_sym, tickers[top_sym]['price'], 5.0, 10000000, 5000000, self.exchange.get_trading_url(top_sym))

    async def send_signal(self, emoji, symbol, price, change_pct, market_cap, volume_24h, url, oi=None, rsi=None, ema=None):
        now_str = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        text = (
            f"{emoji} <b>PUMP!</b> {emoji}\n\n"
            f"<b>Ticker:</b> {symbol}\n"
            f"<b>Price:</b> {price:.6f}\n"
            f"<b>Change:</b> {change_pct:+.2f}%\n"
            f"<b>Vol 24h:</b> ${volume_24h:,.0f}\n"
            f"<b>MC:</b> ${market_cap:,.0f}\n"
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
        pass # Упрощено

    async def close(self):
        await (await self.bot.get_session()).close()
