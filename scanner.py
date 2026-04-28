import asyncio
import logging
from datetime import datetime
import config
from database import (
    save_signal_to_db, 
    can_send_alert, 
    update_alert_time, 
    get_active_signal, 
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
        logger.info("🚀 Pump Scanner started (Dual Timeframe: 5m & 60m)")
        
        # Первичная загрузка капитализации
        await self.mc_provider.update_market_caps()
        
        while self.is_running:
            try:
                # 1. Получаем все тикеры с BingX Futures
                tickers = await self.exchange.get_all_tickers()
                if not tickers:
                    await asyncio.sleep(10)
                    continue

                for symbol, data in tickers.items():
                    current_price = data['price']
                    current_volume = data['volume']
                    
                    # Сохраняем цену в историю для будущих проверок
                    await save_price_to_history(symbol, current_price)
                    
                    # 2. Получаем старые цены (5 мин и 60 мин назад)
                    price_1h = await get_price_one_hour_ago(symbol)
                    price_5m = await get_price_5min_ago(symbol)
                    
                    if not price_1h:
                        continue # Еще недостаточно данных в БД для этой монеты

                    # 3. Считаем рост
                    change_1h = ((current_price - price_1h) / price_1h) * 100
                    change_5m = ((current_price - price_5m) / price_5m) * 100 if price_5m else 0
                    
                    # Логируем подозрительные движения для отладки
                    if change_5m > 1.0 or change_1h > config.PUMP_THRESHOLD:
                        logger.info(f"Checking {symbol}: 5m growth: {change_5m:.2f}%, 1h growth: {change_1h:.2f}%")

                    # 4. Определяем, есть ли памп (по часу ИЛИ по 5 минутам)
                    is_pump = False
                    emoji = "📈"
                    
                    if change_1h >= config.PUMP_THRESHOLD:
                        is_pump = True
                        emoji = "🚀 MEGA PUMP" if change_1h > 15 else "📈 PUMP"
                    elif change_5m >= (config.PUMP_THRESHOLD / 2): # Быстрый всплеск (например >1% за 5 мин при пороге 2%)
                        is_pump = True
                        emoji = "⚡️ FAST SPIKE"

                    if is_pump:
                        mc = self.mc_provider.get_market_cap(symbol)
                        
                        # 5. Применяем фильтры (Market Cap и Volume)
                        if mc >= config.MIN_MARKET_CAP and current_volume >= config.MIN_VOLUME_24H:
                            
                            # Проверяем кулдаун (чтобы не спамить одной монетой)
                            if await can_send_alert(symbol, config.ALERT_COOLDOWN_MINUTES):
                                
                                # Собираем доп. данные
                                try:
                                    oi = await self.exchange.fetch_open_interest(symbol)
                                    indicators = await self.exchange.get_indicators(symbol)
                                    rsi = indicators.get('rsi')
                                    ema = indicators.get('ema')
                                except Exception:
                                    oi, rsi, ema = None, None, None

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
                                    oi=oi,
                                    rsi=rsi,
                                    ema=ema
                                )
                                
                                if msg_id:
                                    # Сохраняем в БД как активный и в историю
                                    await save_active_signal(symbol, msg_id, current_price, mc, current_volume, emoji)
                                    await save_signal_to_db(symbol, current_price, max(change_1h, change_5m), mc, current_volume, emoji, url)
                                    await update_alert_time(symbol)
                                    logger.info(f"Signal sent for {symbol}: 5m={change_5m:.2f}%, 1h={change_1h:.2f}%")
                        else:
                            # Лог для понимания, почему монета отсеялась
                            if change_1h >= config.PUMP_THRESHOLD or change_5m >= 1.5:
                                logger.info(f"Skipping {symbol}: Growth OK, but MC (${mc:,.0f}) or Vol (${current_volume:,.0f}) too low.")

                # 6. Обновляем капитализацию раз в час
                if datetime.now().minute == 0:
                    await self.mc_provider.update_market_caps()

                await asyncio.sleep(60) # Пауза между циклами сканирования

            except Exception as e:
                logger.error(f"Error in scanner loop: {e}")
                await asyncio.sleep(30)

    def stop(self):
        self.is_running = False
