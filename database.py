import aiosqlite
import time
from config import DB_PATH

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # Table for price history
        await db.execute('''
            CREATE TABLE IF NOT EXISTS price_history (
                symbol TEXT,
                price REAL,
                timestamp INTEGER
            )
        ''')
        # Table for alert cooldowns
        await db.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                symbol TEXT,
                last_alert_time INTEGER
            )
        ''')
        # Index for faster lookups
        await db.execute('CREATE INDEX IF NOT EXISTS idx_price_history_symbol ON price_history(symbol)')
        await db.execute('CREATE INDEX IF NOT EXISTS idx_price_history_timestamp ON price_history(timestamp)')
        await db.commit()

async def save_price(symbol: str, price: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT INTO price_history (symbol, price, timestamp) VALUES (?, ?, ?)',
                         (symbol, price, int(time.time())))
        await db.commit()

async def get_historical_price(symbol: str, minutes_ago: int):
    target_time = int(time.time()) - (minutes_ago * 60)
    async with aiosqlite.connect(DB_PATH) as db:
        # Get the closest price to target_time within a 5-minute window
        async with db.execute('''
            SELECT price FROM price_history 
            WHERE symbol = ? AND timestamp <= ? 
            ORDER BY timestamp DESC LIMIT 1
        ''', (symbol, target_time)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def can_send_alert(symbol: str, cooldown_minutes: int):
    cooldown_seconds = cooldown_minutes * 60
    current_time = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT last_alert_time FROM alerts WHERE symbol = ?', (symbol,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return True
            return (current_time - row[0]) > cooldown_seconds

async def update_alert_time(symbol: str):
    current_time = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT OR REPLACE INTO alerts (symbol, last_alert_time) VALUES (?, ?)',
                         (symbol, current_time))
        await db.commit()

async def cleanup_history(days: int = 1):
    # Keep history for X days
    cutoff_time = int(time.time()) - (days * 24 * 3600)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM price_history WHERE timestamp < ?', (cutoff_time,))
        await db.commit()
