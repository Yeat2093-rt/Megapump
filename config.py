import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Pump thresholds
MEGA_PUMP_THRESHOLD = 30.0
PUMP_THRESHOLD = 15.0
LOW_PUMP_THRESHOLD = 7.0

# Market Cap filter
MIN_MARKET_CAP = 5_000_000

# Cache settings
SCAN_INTERVAL_SECONDS = 60 # How often to check for current prices
PRICE_HISTORY_MINUTES = 60 # Comparison window
ALERT_COOLDOWN_MINUTES = 60 # Don't repeat alert for the same coin within this window

# Database path
DB_PATH = "bot_data.db"
