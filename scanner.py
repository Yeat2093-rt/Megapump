import asyncio
import logging
from datetime import datetime
import config
from database import (
    save_signal_to_db, 
    can_send_alert, 
    update_alert_time, 
    save_active_signal,
    get_price_one_hour_ago,
    get_price_5min_ago,
    save_price_to_history
)

logger = logging.getLogger(__name__)

class PumpScanner:
    def __init__(self, exchange_client, mc_provider, notifier):
        self.exchange = exchange_client
        self.mc_provider = mc_provider
        self.notifier = notifier
        self.is_running = False

    async def run(self):
        self.is_running = True
        logger.info("🚀 Pump Scanner started (5m & 60m check enabled)")
        
        await self.mc_provider.update_market_caps()
        
        while self.is_running:
            try:
                tickers = await self.exchange.get_all_tickers()
                if not tickers:
                    await asyncio.sleep(10)
                    continue

                for symbol, data in tickers.items():
                    current_price = data['price']
                    current_volume = data['volume']
                    
                    await save_price_to_history(symbol, current_price)
                    
                    # Получаем историю
                    price_1h = await get_price_one_hour_ago(symbol)
                    price_5m = await get_price_5min_ago(symbol)
                    
                    change_1h = 0
                    change_5m = 0
                    
                    if price_1h:
                        change_1h = ((current_price - price_1h) / price_1h) * 100
                    if price_5m:
                        change_5m = ((current_price - price_5m) / price_5m) * 100

                    is_pump = False
                    emoji = "📈"
                    
                    # Проверка по часу
                    if price_1h and change_1h >= config.PUMP_THRESHOLD:
                        is_pump = True
                        emoji = "🚀 MEGA PUMP" if change_1h > 15 else "📈 PUMP"
                    
                    # Проверка по 5 минутам (если часового пампа нет, проверяем быстрый всплеск)
                    if not is_pump and price_5m and change_5m >= (config.PUMP_THRESHOLD / 2):
                        is_pump = True
                        emoji = "⚡️ FAST SPIKE"

                    if is_pump:
                        mc = self.mc_provider.get_market_cap(symbol)
                        
                        if mc >= config.MIN_MARKET_CAP and current_volume >= config.MIN_VOLUME_24H:
                            if await can_send_alert(symbol, config.ALERT_COOLDOWN_MINUTES):
                                try:
                                    indicators = await self.exchange.get_indicators(symbol)
                                    rsi = indicators.get('rsi')
                                except:
                                    rsi = None

                                url = self.exchange.get_trading_url(symbol)
                                
                                # Отправляем сигнал
                                msg_id = await self.notifier.send_signal(
                                    emoji=emoji,
                                    symbol=symbol,
                                    price=current_price,
                                    change_pct=max(change_1h, change_5m),
                                    market_cap=mc,
                                    volume_24h=current_volume,
                                    url=url,
                                    rsi=rsi
                                )
                                
                                if msg_id:
                                    await save_active_signal(symbol, msg_id, current_price, mc, current_volume, emoji)
                                    await save_signal_to_db(symbol, current_price, max(change_1h, change_5m), mc, current_volume, emoji, url, msg_id)
                                    await update_alert_time(symbol)
                                    logger.info(f"Signal sent: {symbol} (1h: {change_1h:.2f}%, 5m: {change_5m:.2f}%)")

                if datetime.now().minute == 0:
                    await self.mc_provider.update_market_caps()

                await asyncio.sleep(60)

            except Exception as e:
                logger.error(f"Error in scanner: {e}")
                await asyncio.sleep(30)

    def stop(self):
        self.is_running = False
