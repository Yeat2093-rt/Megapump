import pandas as pd
import mplfinance as mpf
import io
import logging

logger = logging.getLogger(__name__)

def generate_chart(ohlcv, symbol):
    """
    Генерирует график свечей (Candlestick) на основе данных OHLCV.
    """
    try:
        # Превращаем данные в DataFrame
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)

        # Настройка стиля (темная тема)
        style = mpf.make_mpf_style(
            base_mpf_style='charles',
            gridstyle='',
            facecolor='#131722',
            edgecolor='#2f333d',
            figcolor='#131722',
            marketcolors=mpf.make_marketcolors(up='#089981', down='#f23645', inherit=True)
        )

        # Создаем буфер в памяти для сохранения картинки
        buf = io.BytesIO()
        
        # Рисуем график
        mpf.plot(
            df,
            type='candle',
            style=style,
            title=f"\n{symbol} Price Chart",
            ylabel='',
            volume=False,
            savefig=dict(fname=buf, format='png', dpi=100),
            figsize=(8, 4.5),
            tight_layout=True
        )
        
        buf.seek(0)
        return buf
    except Exception as e:
        logger.error(f"Error generating chart for {symbol}: {e}")
        return None
