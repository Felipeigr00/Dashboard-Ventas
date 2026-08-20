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

import html

import pandas as pd
import streamlit as st

import theme
from carga_datos import procesar_archivos_subidos
from vistas import dashboard_general, analisis_productos, analisis_clientes, analisis_vendedores, datos_resumen, mi_dashboard

MESES_MAP = {1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
             7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'}

# --------------------------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA Y ESTILOS
# --------------------------------------------------------------------------
st.set_page_config(page_title="Venta por Zona F", layout="wide", page_icon="☕")
st.session_state.setdefault("modo_tema", "claro")
# Ojo: render_header() dibuja el interruptor claro/oscuro y puede actualizar
# st.session_state["modo_tema"] en este mismo rerun. inyectar_css() tiene
# que llamarse DESPUÉS, con el valor ya actualizado — si no, la página se
# queda un paso atrás del interruptor (los gráficos sí quedan al día
# porque leen el session_state más abajo en el script).
modo_tema = theme.render_header(st.session_state["modo_tema"])
theme.inyectar_css(modo_tema)

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
    # BARRA DE CONTROL: modo de vista, filtro de zona y periodos
    # ----------------------------------------------------------------------
    anos_disponibles = sorted(df['Año'].dropna().unique().tolist())
    meses_disponibles_nums = sorted(df['Mes_Num'].dropna().unique().tolist())
    meses_disponibles_nombres = [MESES_MAP[m] for m in meses_disponibles_nums]

    df_filtrado = df.copy()
    filtro_zona = "Todas"

    with st.container(border=True):
        col_info, col_toggle = st.columns([3, 2])

        with col_toggle:
            modo_ui = st.segmented_control(
                "Vista", ["Vista simple", "Comparar periodos"],
                default="Vista simple", required=True, key="modo_vista_ui",
                label_visibility="collapsed", width='stretch'
            )
        modo = "Comparativa (A vs B)" if modo_ui == "Comparar periodos" else "Vista Simple (1 Periodo)"

        st.divider()

        if 'Zona' in df.columns:
            zonas_disponibles = sorted(df['Zona'].dropna().astype(str).unique().tolist())
            filtro_zona = st.selectbox("Filtrar por Zona", ["Todas"] + zonas_disponibles)
            if filtro_zona != "Todas":
                df_filtrado = df_filtrado[df_filtrado['Zona'].astype(str) == filtro_zona]

        if modo == "Comparativa (A vs B)":
            st.markdown("##### 🟠 Periodo A (Base)")
            st.caption("Año Periodo A")
            anio_a = st.segmented_control(
                "Año Periodo A", anos_disponibles, default=anos_disponibles[0],
                key='anio_a', required=True, label_visibility="collapsed"
            )
            st.caption("Mes(es) Periodo A")
            meses_a_nombres = st.segmented_control(
                "Mes(es) Periodo A", meses_disponibles_nombres, default=[meses_disponibles_nombres[0]],
                key='mes_a', selection_mode='multi', label_visibility="collapsed"
            ) or []
            mes_a_num = [k for k, v in MESES_MAP.items() if v in meses_a_nombres]

            st.markdown("##### 🟢 Periodo B (Comparación)")
            st.caption("Año Periodo B")
            anio_b = st.segmented_control(
                "Año Periodo B", anos_disponibles, default=anos_disponibles[-1],
                key='anio_b', required=True, label_visibility="collapsed"
            )
            sincronizar_meses = st.checkbox("Usar los mismos meses que Periodo A", value=True, key='sync_meses')
            if sincronizar_meses:
                meses_b_nombres = meses_a_nombres
                st.caption(f"Meses B = {', '.join(meses_a_nombres) if meses_a_nombres else '(ninguno)'}")
            else:
                st.caption("Mes(es) Periodo B")
                meses_b_nombres = st.segmented_control(
                    "Mes(es) Periodo B", meses_disponibles_nombres, default=[meses_disponibles_nombres[-1]],
                    key='mes_b', selection_mode='multi', label_visibility="collapsed"
                ) or []
            mes_b_num = [k for k, v in MESES_MAP.items() if v in meses_b_nombres]

            if not meses_a_nombres or not meses_b_nombres:
                st.warning("Selecciona al menos un mes para el Periodo A y para el Periodo B.")
                st.stop()
        else:
            st.markdown("##### 🔵 Periodo Único")
            st.caption("Año")
            anio_a = st.segmented_control(
                "Año", anos_disponibles, default=anos_disponibles[0],
                key='anio_unico', required=True, label_visibility="collapsed"
            )
            st.caption("Mes(es)")
            meses_a_nombres = st.segmented_control(
                "Mes(es)", meses_disponibles_nombres, default=[meses_disponibles_nombres[0]],
                key='mes_unico', selection_mode='multi', label_visibility="collapsed"
            ) or []
            mes_a_num = [k for k, v in MESES_MAP.items() if v in meses_a_nombres]

            anio_b, meses_b_nombres, mes_b_num = anio_a, [], []

            if not meses_a_nombres:
                st.warning("Selecciona al menos un mes.")
                st.stop()

        # --------------------------------------------------------------
        # ARMADO DE PERIODOS A / B (etiquetas usadas en la info y abajo)
        # --------------------------------------------------------------
        meses_a_ordenados = [MESES_MAP[n] for n in sorted(mes_a_num)]
        label_a = f"{', '.join(meses_a_ordenados)} {anio_a}"

        if modo == "Comparativa (A vs B)":
            meses_b_ordenados = [MESES_MAP[n] for n in sorted(mes_b_num)]
            label_b = f"{', '.join(meses_b_ordenados)} {anio_b}"
            if label_a == label_b:
                # Mismo año/meses en A y B (típico con un solo año de datos):
                # sin esto, las tablas que cruzan A y B (pd.merge con columnas
                # 'Venta {label}' repetidas) chocan de nombre y rompen la app.
                label_a += " (A)"
                label_b += " (B)"
        else:
            label_b = ""

        with col_info:
            n_archivos = len(uploaded_files)
            sufijo_archivos = "archivo" if n_archivos == 1 else "archivos"
            if modo == "Comparativa (A vs B)":
                periodo_html = (
                    f'<span class="periodo-dot a"></span>{html.escape(label_a)}'
                    f'&nbsp;&nbsp;vs&nbsp;&nbsp;'
                    f'<span class="periodo-dot b"></span>{html.escape(label_b)}'
                )
            else:
                periodo_html = f'Periodo <b>{html.escape(label_a)}</b>'
            st.markdown(
                f'<div class="control-bar-info">{periodo_html}'
                f' &nbsp;·&nbsp; Zona <b>{html.escape(filtro_zona)}</b>'
                f' &nbsp;·&nbsp; {n_archivos} {sufijo_archivos} cargados</div>',
                unsafe_allow_html=True
            )

    # ----------------------------------------------------------------------
    # FILTRADO DE DATOS SEGÚN PERIODOS SELECCIONADOS
    # ----------------------------------------------------------------------
    df_a = df_filtrado[(df_filtrado['Año'] == anio_a) & (df_filtrado['Mes_Num'].isin(mes_a_num))].copy()

    if modo == "Comparativa (A vs B)":
        df_b = df_filtrado[(df_filtrado['Año'] == anio_b) & (df_filtrado['Mes_Num'].isin(mes_b_num))].copy()
        df_a['Periodo'] = label_a
        df_b['Periodo'] = label_b
        df_dual = pd.concat([df_a, df_b])
    else:
        df_b = pd.DataFrame()
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
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "📊 Dashboard General",
            "🛍️ Análisis de Productos",
            "👥 Análisis de Clientes",
            "🧑‍💼 Análisis de Vendedor",
            "📂 Datos y Resúmenes",
            "🧩 Mi Dashboard"
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

        with tab6:
            # Histórico completo (df), no el filtrado por Zona/Periodo de
            # arriba: el constructor tiene su propio filtro de Año/Mes, y
            # así puede comparar entre zonas o periodos que el filtro global
            # de la parte de arriba ya haya dejado afuera.
            mi_dashboard.render(df)
    else:
        st.warning("No se encontraron registros para los periodos seleccionados.")

except Exception as e:
    st.exception(e)
