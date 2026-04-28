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
                symbol TEXT PRIMARY KEY, 
                last_alert_time INTEGER,
                last_milestone INTEGER DEFAULT 0
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS signal_history (
                symbol TEXT, price REAL, change_pct REAL, 
                market_cap REAL, volume REAL, emoji TEXT, 
                url TEXT, timestamp INTEGER, message_id INTEGER
            )
        ''')
        await db.commit()

async def get_price_24h_ago(symbol: str):
    target_time = int(time.time()) - (24 * 60 * 60)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('''
            SELECT price FROM price_history 
            WHERE symbol = ? AND timestamp <= ? 
            ORDER BY timestamp DESC LIMIT 1
        ''', (symbol, target_time)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

# ... (Остальные функции без изменений)
async def get_last_milestone(symbol: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT last_milestone FROM alerts WHERE symbol = ?', (symbol,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def update_alert_milestone(symbol: str, milestone: int):
    current_time = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT OR REPLACE INTO alerts (symbol, last_alert_time, last_milestone) 
            VALUES (?, ?, ?)
        ''', (symbol, current_time, milestone))
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
