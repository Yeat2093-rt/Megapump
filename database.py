import aiosqlite
import time
from datetime import datetime
from config import DB_PATH

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS price_history (
                symbol TEXT, price REAL, timestamp INTEGER
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                symbol TEXT, last_alert_time INTEGER
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS signal_history (
                symbol TEXT, price REAL, change_pct REAL, 
                market_cap REAL, volume REAL, emoji TEXT, 
                url TEXT, timestamp INTEGER, message_id INTEGER
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS active_signals (
                symbol TEXT PRIMARY KEY, message_id INTEGER, 
                last_update INTEGER, initial_price REAL,
                mc REAL, volume REAL, emoji TEXT
            )
        ''')
        await db.commit()

async def save_price_to_history(symbol: str, price: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT INTO price_history (symbol, price, timestamp) VALUES (?, ?, ?)',
                         (symbol, price, int(time.time())))
        await db.commit()

async def get_price_one_hour_ago(symbol: str):
    target_time = int(time.time()) - (60 * 60)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('''
            SELECT price FROM price_history 
            WHERE symbol = ? AND timestamp <= ? 
            ORDER BY timestamp DESC LIMIT 1
        ''', (symbol, target_time)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def get_price_5min_ago(symbol: str):
    target_time = int(time.time()) - (5 * 60)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('''
            SELECT price FROM price_history 
            WHERE symbol = ? AND timestamp <= ? 
            ORDER BY timestamp DESC LIMIT 1
        ''', (symbol, target_time)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def save_signal_to_db(symbol, price, change_pct, market_cap, volume, emoji, url, message_id=None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO signal_history 
            (symbol, price, change_pct, market_cap, volume, emoji, url, timestamp, message_id) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (symbol, price, change_pct, market_cap, volume, emoji, url, int(time.time()), message_id))
        await db.commit()

async def save_active_signal(symbol, message_id, price, mc, volume, emoji):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT OR REPLACE INTO active_signals (symbol, message_id, last_update, initial_price, mc, volume, emoji)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (symbol, message_id, int(time.time()), price, mc, volume, emoji))
        await db.commit()

async def get_active_signal(symbol):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT message_id, initial_price, mc, volume, emoji FROM active_signals WHERE symbol = ?', (symbol,)) as cursor:
            return await cursor.fetchone()

async def can_send_alert(symbol: str, cooldown_minutes: int):
    cooldown_seconds = cooldown_minutes * 60
    current_time = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT last_alert_time FROM alerts WHERE symbol = ?', (symbol,)) as cursor:
            row = await cursor.fetchone()
            if not row: return True
            return (current_time - row[0]) > cooldown_seconds

async def update_alert_time(symbol: str):
    current_time = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT OR REPLACE INTO alerts (symbol, last_alert_time) VALUES (?, ?)',
                         (symbol, current_time))
        await db.commit()

async def get_last_signal_from_db():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT * FROM signal_history ORDER BY timestamp DESC LIMIT 1') as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "symbol": row[0], "price": row[1], "change_pct": row[2],
                    "mc": row[3], "volume": row[4], "emoji": row[5],
                    "url": row[6], "timestamp": row[7]
                }
            return None
