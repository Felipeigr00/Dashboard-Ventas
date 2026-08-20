"""
preview_mi_dashboard.py
------------------------
App de prueba AISLADA para probar la pestaña "Mi Dashboard" sin tocar
app.py ni arriesgar nada de lo que ya funciona en producción.

Corre esto por separado:
    streamlit run preview_mi_dashboard.py

Usa el mismo pipeline de limpieza real (carga_datos.py) que tu app
principal, así que lo que veas acá se comporta igual que en la app de
verdad. Cuando confirmes que te gusta, se integra como 6ª pestaña en
app.py.
"""

import streamlit as st

import theme
from carga_datos import procesar_archivos_subidos
from vistas import mi_dashboard

st.set_page_config(page_title="Preview · Mi Dashboard", layout="wide", page_icon="🧩")
st.session_state.setdefault("modo_tema", "claro")
modo_tema = theme.render_header(st.session_state["modo_tema"])
theme.inyectar_css(modo_tema)

st.caption("🧪 Preview aislado — no toca tu app.py real.")

uploaded_files = st.file_uploader(
    "Sube tu(s) archivo(s) de ventas (.xlsx o .xls)",
    type=["xlsx", "xls"],
    accept_multiple_files=True,
)

if not uploaded_files:
    st.stop()

try:
    df, df_descartadas = procesar_archivos_subidos(uploaded_files)
except Exception as e:
    st.exception(e)
    st.stop()

st.divider()
mi_dashboard.render(df)
