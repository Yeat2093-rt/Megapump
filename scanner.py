import asyncio
import logging
from exchange import BingXClient
from market_cap import MarketCapProvider
from database import (
    save_price, get_historical_price, can_send_alert, 
    update_alert_time, cleanup_history, save_signal_to_history,
    get_active_signal, save_active_signal, remove_active_signal
)
from notifier import TelegramNotifier
import state
import config
import time

logger = logging.getLogger(__name__)

class PumpScanner:
    def __init__(self, exchange: BingXClient, mc_provider: MarketCapProvider, notifier: TelegramNotifier):
        self.exchange = exchange
        self.mc_provider = mc_provider
        self.notifier = notifier

    async def run(self):
        logger.info("Starting Pump Scanner...")
        
        # Initial market cap update
        await self.mc_provider.update_market_caps()
        
        mc_update_counter = 0
        
        while True:
            try:
                # Update market caps every hour (roughly)
                mc_update_counter += 1
                if mc_update_counter >= 60: # 60 * 60 seconds = 1 hour
                    await self.mc_provider.update_market_caps()
                    mc_update_counter = 0
                    await cleanup_history(days=2) # Regular cleanup
                    # Cleanup old active signals (e.g., older than 2 hours)
                    # (Simplified for now)

                # Get current prices and volumes
                ticker_data = await self.exchange.get_all_tickers()
                
                for symbol, data in ticker_data.items():
                    current_price = data['price']
                    current_volume = data['volume']
                    
                    # Save current price to history
                    await save_price(symbol, current_price)
                    
                    # Check historical price (1 hour ago)
                    old_price = await get_historical_price(symbol, config.PRICE_HISTORY_MINUTES)
                    
                    if old_price:
                        change_pct = ((current_price - old_price) / old_price) * 100
                        
                        # Determine signal category
                        emoji = None
                        if change_pct >= config.MEGA_PUMP_THRESHOLD:
                            emoji = "🚨"
                        elif change_pct >= config.PUMP_THRESHOLD:
                            emoji = "⚠️"
                        elif change_pct >= config.LOW_PUMP_THRESHOLD:
                            emoji = "📈"
                            
                        if emoji:
                            # Filter by Market Cap and Volume
                            mc = self.mc_provider.get_market_cap(symbol)
                            
                            # Fetch additional data (OI, RSI, EMA) - Informational only
                            oi = await self.exchange.fetch_open_interest(symbol)
                            indicators = await self.exchange.get_indicators(symbol)
                            rsi = indicators.get('rsi')
                            ema = indicators.get('ema')

                            # Apply filters: Market Cap AND Volume
                            if mc >= config.MIN_MARKET_CAP and current_volume >= config.MIN_VOLUME_24H:
                                url = self.exchange.get_trading_url(symbol)
                                deep_link = self.exchange.get_deep_link(symbol)
                                active_sig = await get_active_signal(symbol)
                                
                                if active_sig:
                                    # Signal already exists, update it if growth continues
                                    msg_id, initial_price = active_sig
                                    await self.notifier.update_signal(
                                        msg_id, emoji, symbol, current_price, change_pct, mc, current_volume, url,
                                        oi=oi, rsi=rsi, ema=ema, deep_link=deep_link
                                    )
                                    logger.info(f"Updated signal for {symbol}: {change_pct:.2f}%")
                                else:
                                    # New signal
                                    if await can_send_alert(symbol, config.ALERT_COOLDOWN_MINUTES):
                                        msg_id = await self.notifier.send_signal(
                                            emoji, symbol, current_price, change_pct, mc, current_volume, url,
                                            oi=oi, rsi=rsi, ema=ema, deep_link=deep_link
                                        )
                                        
                                        if msg_id:
                                            await save_active_signal(symbol, msg_id, current_price)
                                            await save_signal_to_history(
                                                symbol, current_price, change_pct, mc, current_volume, emoji, url, msg_id
                                            )
                                            await update_alert_time(symbol)
                                            logger.info(f"New signal sent for {symbol}: {change_pct:.2f}%")
                            else:
                                if change_pct >= config.PUMP_THRESHOLD:
                                    logger.info(f"Skipping {symbol}: Growth {change_pct:.1f}%, but MC (${mc:,.0f}) or Vol (${current_volume:,.0f}) too low.")

            except Exception as e:
                logger.error(f"Error in scanner loop: {e}")
            
            await asyncio.sleep(config.SCAN_INTERVAL_SECONDS)
