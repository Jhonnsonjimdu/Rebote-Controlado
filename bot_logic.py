# bot_logic.py
import math
import pandas as pd
from datetime import datetime, timezone
from binance.client import Client

SYMBOL = "BTCUSDT"
INTERVAL = Client.KLINE_INTERVAL_15MINUTE

def init_client(api_key, api_secret):
    return Client(api_key, api_secret)

def obtener_capital_usdt(client):
    bal = client.get_asset_balance(asset="USDT")
    return float(bal["free"]) if bal else 0.0

def calcular_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def obtener_datos(client, limit=100):
    klines = client.get_klines(symbol=SYMBOL, interval=INTERVAL, limit=limit)
    df = pd.DataFrame(klines, columns=[
        'timestamp','open','high','low','close','volume',
        'close_time','quote_asset_volume','number_of_trades',
        'taker_buy_base_volume','taker_buy_quote_volume','ignore'
    ])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    df.set_index('timestamp', inplace=True)
    df = df[['open','high','low','close','volume']].astype(float)
    df['ema50']  = df['close'].ewm(span=50).mean()
    df['ema200'] = df['close'].ewm(span=200).mean()
    df['rsi']    = calcular_rsi(df['close'])
    return df

def obtener_precision_cantidad(client, symbol=SYMBOL):
    info = client.get_symbol_info(symbol)
    for f in info['filters']:
        if f['filterType']=="LOT_SIZE":
            step = float(f['stepSize'])
            return int(round(-math.log10(step)))
    return 6

def procesar_estrategia(client, df, state):
    """
    state es un dict con:
      - in_position (bool)
      - entry_price, max_price, entry_time, ultima_entrada (timestamp)
      - operaciones (lista de tuplas)
    Devuelve texto de log para Streamlit.
    """
    log = []
    row, prev = df.iloc[-1], df.iloc[-2]

    if state.get("ultima_entrada")==row.name:
        return log

    state["ultima_entrada"] = row.name

    if not state["in_position"]:
        cond = (
            row["ema50"] > row["ema200"] and
            30 < row["rsi"] < 45 and
            prev["rsi"] < row["rsi"]
        )
        if cond:
            state["in_position"] = True
            state["entry_price"] = row["close"]
            state["max_price"] = row["close"]
            state["entry_time"] = row.name
            log.append(f"📈 Entrada @ {row['close']} ({row.name})")
            # Ejecutar compra real
            usdt = obtener_capital_usdt(client)
            compr = round((usdt*0.98)/row["close"], obtener_precision_cantidad(client))
            try:
                client.order_market_buy(symbol=SYMBOL, quantity=compr)
                log.append(f"✅ Comprados {compr} BTC a {row['close']}")
            except Exception as e:
                log.append(f"❌ Error compra: {e}")
                state["in_position"] = False
    else:
        # Actualiza máximo
        if row["close"] > state["max_price"]:
            state["max_price"] = row["close"]
        change = (row["close"] - state["entry_price"]) / state["entry_price"]
        trailing = (row["close"] - state["max_price"]) / state["max_price"]
        if change <= -0.005:
            log.append(f"🔻 Stop Loss @ {row['close']}")
            state["operaciones"].append(("PERDIDA", state["entry_time"], row.name, row["close"]))
            state["in_position"] = False
        elif trailing <= -0.005:
            log.append(f"🔺 Trailing Stop @ {row['close']}")
            state["operaciones"].append(("GANANCIA", state["entry_time"], row.name, row["close"]))
            state["in_position"] = False

    return log
