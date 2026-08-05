"""
app.py
------
Punto de entrada de la Consola Ejecutiva · Dark Coffee BI.

Estructura del proyecto:
  app.py            -> este archivo: configuración, filtros globales, orquestación
  theme.py          -> sistema de diseño (CSS + componentes visuales)
  carga_datos.py     -> carga/limpieza/combinación de los archivos subidos
  utils.py          -> motor de datos: limpieza de celdas, KPIs, export a Excel
  vistas/           -> una vista por pestaña del dashboard
    dashboard_general.py
    analisis_productos.py
    analisis_clientes.py
    datos_resumen.py
"""

import pandas as pd
import streamlit as st

import theme
from carga_datos import procesar_archivos_subidos
from vistas import dashboard_general, analisis_productos, analisis_clientes, analisis_vendedores, datos_resumen

MESES_MAP = {1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
             7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'}

# --------------------------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA Y ESTILOS
# --------------------------------------------------------------------------
st.set_page_config(page_title="Venta por Zona F", layout="wide", page_icon="☕")
theme.inyectar_css()
theme.render_header()

# --------------------------------------------------------------------------
# MEMORIA DE FILTROS (para que las pestañas no se reinicien solas)
# --------------------------------------------------------------------------
st.session_state.setdefault('mem_vend_t2', "Todos")
st.session_state.setdefault('mem_prod_t2', None)
st.session_state.setdefault('mem_vend_t3', "Todos")

# --------------------------------------------------------------------------
# CARGA DE ARCHIVOS
# --------------------------------------------------------------------------
uploaded_files = st.file_uploader(
    "Sube tu(s) archivo(s) de ventas (.xlsx o .xls)",
    type=["xlsx", "xls"],
    accept_multiple_files=True,
    help="Si tu histórico no cabe en un solo export (por el límite de 150.000 filas de Power BI), "
         "sube aquí varios archivos (por trimestre, por año, etc.) y la app los junta automáticamente."
)

if not uploaded_files:
    st.stop()

try:
    df, df_descartadas = procesar_archivos_subidos(uploaded_files)

    cols_fecha = df.select_dtypes(include=['datetime64']).columns.tolist()
    if not cols_fecha:
        st.error("El archivo no contiene una columna de fecha válida (después de la limpieza).")
        st.stop()

    # ----------------------------------------------------------------------
    # PANEL DE FILTROS GLOBALES
    # ----------------------------------------------------------------------
    with st.expander("⚙️ Configuración Global del Dashboard", expanded=True):

        st.markdown("#### 🧭 Modo de Vista")
        modo = st.radio("Selecciona el modo:", ["Comparativa (A vs B)", "Vista Simple (1 Periodo)"], horizontal=True)

        st.divider()

        st.markdown("#### 🗺️ Filtro Operativo Opcional")
        df_filtrado = df.copy()
        if 'Zona' in df.columns:
            zonas_disponibles = sorted(df['Zona'].dropna().astype(str).unique().tolist())
            filtro_zona = st.selectbox("Filtrar por Zona", ["Todas"] + zonas_disponibles)
            if filtro_zona != "Todas":
                df_filtrado = df_filtrado[df_filtrado['Zona'].astype(str) == filtro_zona]

        st.divider()

        st.markdown("#### ⚖️ Configuración de Periodos")
        anos_disponibles = sorted(df['Año'].dropna().unique().tolist())
        meses_disponibles_nums = sorted(df['Mes_Num'].dropna().unique().tolist())
        meses_disponibles_nombres = [MESES_MAP[m] for m in meses_disponibles_nums]

        if modo == "Comparativa (A vs B)":
            col_periodo_a, col_periodo_b = st.columns(2)

            with col_periodo_a:
                st.markdown("##### 🟦 Periodo A (Base)")
                anio_a = st.selectbox("Año Periodo A", anos_disponibles, index=0, key='anio_a')
                meses_a_nombres = st.multiselect("Mes(es) Periodo A", meses_disponibles_nombres, default=[meses_disponibles_nombres[0]], key='mes_a')
                mes_a_num = [k for k, v in MESES_MAP.items() if v in meses_a_nombres]

            with col_periodo_b:
                st.markdown("##### 🟧 Periodo B (Comparación)")
                anio_b = st.selectbox("Año Periodo B", anos_disponibles, index=len(anos_disponibles) - 1, key='anio_b')
                sincronizar_meses = st.checkbox("Usar los mismos meses que Periodo A", value=True, key='sync_meses')
                if sincronizar_meses:
                    meses_b_nombres = meses_a_nombres
                    st.caption(f"Meses B = {', '.join(meses_a_nombres) if meses_a_nombres else '(ninguno)'}")
                else:
                    meses_b_nombres = st.multiselect("Mes(es) Periodo B", meses_disponibles_nombres, default=[meses_disponibles_nombres[-1]], key='mes_b')
                mes_b_num = [k for k, v in MESES_MAP.items() if v in meses_b_nombres]

            if not meses_a_nombres or not meses_b_nombres:
                st.warning("Selecciona al menos un mes para el Periodo A y para el Periodo B.")
                st.stop()
        else:
            st.markdown("##### 🟦 Periodo Único")
            anio_a = st.selectbox("Año", anos_disponibles, index=0, key='anio_unico')
            meses_a_nombres = st.multiselect("Mes(es)", meses_disponibles_nombres, default=[meses_disponibles_nombres[0]], key='mes_unico')
            mes_a_num = [k for k, v in MESES_MAP.items() if v in meses_a_nombres]

            anio_b, meses_b_nombres, mes_b_num = anio_a, [], []

            if not meses_a_nombres:
                st.warning("Selecciona al menos un mes.")
                st.stop()

    # ----------------------------------------------------------------------
    # ARMADO DE PERIODOS A / B
    # ----------------------------------------------------------------------
    meses_a_ordenados = [MESES_MAP[n] for n in sorted(mes_a_num)]
    label_a = f"{', '.join(meses_a_ordenados)} {anio_a}"

    df_a = df_filtrado[(df_filtrado['Año'] == anio_a) & (df_filtrado['Mes_Num'].isin(mes_a_num))].copy()

    if modo == "Comparativa (A vs B)":
        df_b = df_filtrado[(df_filtrado['Año'] == anio_b) & (df_filtrado['Mes_Num'].isin(mes_b_num))].copy()
        meses_b_ordenados = [MESES_MAP[n] for n in sorted(mes_b_num)]
        label_b = f"{', '.join(meses_b_ordenados)} {anio_b}"

        theme.periodo_banner(f"Periodo Analizado: [{label_a}]  vs  [{label_b}]")

        df_a['Periodo'] = label_a
        df_b['Periodo'] = label_b
        df_dual = pd.concat([df_a, df_b])
    else:
        df_b = pd.DataFrame()
        label_b = ""

        theme.periodo_banner(f"Periodo Analizado: [{label_a}]")

        df_a['Periodo'] = label_a
        df_dual = df_a.copy()

    color_map = {label_a: theme.COLOR_PERIODO_A}
    if modo == "Comparativa (A vs B)":
        color_map[label_b] = theme.COLOR_PERIODO_B

    col_sort_tabla = label_b if modo == "Comparativa (A vs B)" else label_a
    col_prod = next((c for c in ['Detalle', 'Producto', 'Descripción', 'Articulo', 'Nombre Artículo', 'Material', 'Desc. Artículo', 'Item'] if c in df_dual.columns), None)

    # ----------------------------------------------------------------------
    # PESTAÑAS
    # ----------------------------------------------------------------------
    if not df_a.empty or (modo == "Comparativa (A vs B)" and not df_b.empty):
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📊 Dashboard General",
            "🛍️ Análisis de Productos",
            "👥 Análisis de Clientes",
            "🧑‍💼 Análisis de Vendedor",
            "📂 Datos y Resúmenes"
        ])

        with tab1:
            dashboard_general.render(df_a, df_b, df_dual, modo, label_a, label_b, color_map, df_filtrado)

        with tab2:
            analisis_productos.render(df_dual, modo, label_a, label_b, color_map, col_sort_tabla, col_prod)

        with tab3:
            analisis_clientes.render(df_a, df_b, df_dual, modo, label_a, label_b, color_map)

        with tab4:
            analisis_vendedores.render(df_filtrado)

        with tab5:
            datos_resumen.render(df_a, df_b, df_dual, modo, label_a, label_b, col_sort_tabla, col_prod)
    else:
        st.warning("No se encontraron registros para los periodos seleccionados.")

except Exception as e:
    st.exception(e)
