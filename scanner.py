import asyncio
import logging
from datetime import datetime
import config
from database import (
    save_signal_to_db, 
    update_alert_milestone,
    get_last_milestone,
    get_price_one_hour_ago,
    get_price_5min_ago,
    get_price_24h_ago,
    save_price_to_history
)

logger = logging.getLogger(__name__)

class PumpScanner:
    def __init__(self, exchange_client, mc_provider, notifier):
        self.exchange = exchange_client
        self.mc_provider = mc_provider
        self.notifier = notifier
        self.is_running = False

    def get_milestone_tier(self, pct):
        """Определяет текущий порог роста"""
        if pct >= 50:
            return 50 + ((int(pct) - 50) // 20) * 20
        elif pct >= 30: return 30
        elif pct >= 15: return 15
        elif pct >= 7: return 7
        return 0

    def get_label(self, milestone, is_24h=False):
        """Возвращает заголовок. Если рост суточный, помечаем это."""
        suffix = " (24h Trend)" if is_24h else ""
        if milestone >= 50: return f"🔥 EXTRA PUMP {milestone}%+{suffix} 🔥"
        if milestone == 30: return f"🚀 MEGA PUMP{suffix} 🚀"
        if milestone == 15: return f"📈 PUMP{suffix}"
        if milestone == 7: return f"📉 Low Pump{suffix}"
        return "Pump"

    async def run(self):
        self.is_running = True
        logger.info("🚀 Triple-Timeframe Scanner (5m, 1h, 24h) started")
        
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
                    
                    # Получаем цены за разные периоды
                    p5m = await get_price_5min_ago(symbol)
                    p1h = await get_price_one_hour_ago(symbol)
                    p24h = await get_price_24h_ago(symbol)
                    
                    # Считаем рост для каждого таймфрейма
                    c5m = ((current_price - p5m) / p5m * 100) if p5m else 0
                    c1h = ((current_price - p1h) / p1h * 100) if p1h else 0
                    c24h = ((current_price - p24h) / p24h * 100) if p24h else 0
                    
                    # Берем максимальный рост из всех
                    max_change = max(c5m, c1h, c24h)
                    is_long_term = (c24h == max_change and c24h > c1h * 1.5) # Пометка, если основной рост - суточный
                    
                    current_milestone = self.get_milestone_tier(max_change)
                    
                    if current_milestone > 0:
                        last_sent_milestone = await get_last_milestone(symbol)
                        
                        if current_milestone > last_sent_milestone:
                            mc = self.mc_provider.get_market_cap(symbol)
                            
                            if mc >= config.MIN_MARKET_CAP and current_volume >= config.MIN_VOLUME_24H:
                                label = self.get_label(current_milestone, is_long_term)
                                
                                oi, rsi = None, None
                                try:
                                    oi = await self.exchange.fetch_open_interest(symbol)
                                    indicators = await self.exchange.get_indicators(symbol)
                                    rsi = indicators.get('rsi')
                                except: pass

                                url = self.exchange.get_trading_url(symbol)
                                
                                await self.notifier.send_signal(
                                    emoji=label,
                                    symbol=symbol,
                                    price=current_price,
                                    change_pct=max_change,
                                    market_cap=mc,
                                    volume_24h=current_volume,
                                    url=url,
                                    oi=oi,
                                    rsi=rsi
                                )
                                
                                await update_alert_milestone(symbol, current_milestone)
                                await save_signal_to_db(symbol, current_price, max_change, mc, current_volume, label, url)

                await asyncio.sleep(60)

            except Exception as e:
                logger.error(f"Error in scanner: {e}")
                await asyncio.sleep(30)

    def stop(self):
        self.is_running = False
