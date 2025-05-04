# app.py
import streamlit as st
from telegram import Bot
from bot_logic import (
    init_client, obtener_capital_usdt, obtener_datos,
    procesar_estrategia
)

# ——— Configuración inicial ———
st.set_page_config(layout="wide")
API_KEY    = st.secrets["BINANCE_API_KEY"]
API_SECRET = st.secrets["BINANCE_API_SECRET"]
client     = init_client(API_KEY, API_SECRET)

bot        = Bot(token=st.secrets["TELEGRAM_TOKEN"])
CHAT_ID    = st.secrets["TELEGRAM_CHAT_ID"]

# Estado persistente en sesión
if "state" not in st.session_state:
    st.session_state.state = {
        "in_position": False,
        "entry_price": 0,
        "max_price": 0,
        "entry_time": None,
        "ultima_entrada": None,
        "operaciones": []
    }

st.title("📊 Rebote Controlado Dashboard")
st.markdown("Controla tu bot y recibe notificaciones en Telegram")

# —— Saldo
saldo = obtener_capital_usdt(client)
st.metric("Saldo USDT disponible", round(saldo,4))

# —— Botón de una iteración
if st.button("Ejecutar estrategia"):
    df       = obtener_datos(client)
    logs     = procesar_estrategia(client, df, st.session_state.state)
    for linea in logs:
        st.write(linea)
        # envía cada evento a Telegram
        bot.send_message(chat_id=CHAT_ID, text=linea)

# —— Mostrar últimas 10 operaciones ejecutadas
ops = st.session_state.state["operaciones"]
if ops:
    st.subheader("Historial de operaciones")
    df_ops = (
        st.session_state.state["operaciones"]
    )
    st.table(df_ops[-10:])  # muestro solo las 10 más recientes
