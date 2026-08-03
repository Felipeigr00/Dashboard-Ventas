import streamlit as st
import pandas as pd
import plotly.express as px
from utils import cargar_y_limpiar_datos, generar_excel_bonito, calcular_kpis, detectar_meses_incompletos

# Configuración inicial de la página
st.set_page_config(page_title="Dashboard Ejecutivo · Dark Coffee BI", layout="wide", page_icon="☕")

# --- INICIALIZACIÓN DE MEMORIA DE FILTROS ---
# Esto permite que los filtros de las pestañas no se reinicien al cambiar los meses o zonas arriba
if 'mem_vend_t2' not in st.session_state:
    st.session_state.mem_vend_t2 = "Todos"
if 'mem_prod_t2' not in st.session_state:
    st.session_state.mem_prod_t2 = None
if 'mem_vend_t3' not in st.session_state:
    st.session_state.mem_vend_t3 = "Todos"

# DISEÑO UI/UX: Estética Black & Pastel Coffee (Dark Luxury)
st.markdown("""
    <style>
    .stApp { background-color: #0c0a09; color: #e7e5e4; }
    .stMetric { 
        background: linear-gradient(135deg, #1c1917 0%, #12100e 100%);
        padding: 16px; border-radius: 12px; border: 1px solid #292524;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
    }
    .periodo-header { 
        font-size: 1.1rem; font-weight: 600; color: #d97706; 
        background: rgba(217, 119, 6, 0.1); padding: 10px 15px; 
        border-radius: 8px; border: 1px solid rgba(217, 119, 6, 0.2);
        margin-bottom: 20px; 
    }
    .sub-seccion { font-size: 1.2rem; font-weight: 700; color: #f59e0b; margin-top: 15px; margin-bottom: 10px; }
    .streamlit-expanderHeader { background-color: #1c1917; border: 1px solid #292524; border-radius: 8px; }
    [data-testid="stExpander"] { background-color: #12100e; border: 1px solid #292524; border-radius: 12px; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; font-size: 1.1rem; font-weight: 600; }
    </style>
""", unsafe_allow_html=True)

st.title("☕ Consola Ejecutiva · Dark Coffee BI")

uploaded_files = st.file_uploader(
    "Sube tu(s) archivo(s) de ventas (.xlsx, .xls o .csv)",
    type=["xlsx", "xls", "csv"],
    accept_multiple_files=True,
    help="Si tu histórico no cabe en un solo export (por el límite de 150.000 filas de Power BI), "
         "sube aquí varios archivos (por trimestre, por año, etc.) y la app los junta automáticamente."
)

if uploaded_files:
    try:
        # --- CARGAMOS Y UNIMOS TODOS LOS ARCHIVOS SUBIDOS ---
        # (cada archivo queda en caché: si vuelves a tocar un filtro, no se
        # vuelve a leer/limpiar desde cero, solo la primera vez es lenta)
        listas_df, listas_desc = [], []
        total_notas_credito = 0
        for f in uploaded_files:
            with st.spinner(f"Procesando {f.name}... (puede tardar la primera vez)"):
                df_f, desc_f, nc_f = cargar_y_limpiar_datos(f)
            total_notas_credito += nc_f
            if not df_f.empty:
                df_f['__Archivo Origen'] = f.name
                listas_df.append(df_f)
            if not desc_f.empty:
                desc_f['__Archivo Origen'] = f.name
                listas_desc.append(desc_f)

        if not listas_df:
            st.error("Ninguno de los archivos subidos contenía filas válidas después de la limpieza.")
            st.stop()

        df = pd.concat(listas_df, ignore_index=True)
        df_descartadas = pd.concat(listas_desc, ignore_index=True) if listas_desc else pd.DataFrame()

        if total_notas_credito > 0:
            st.toast(f"✅ Se detectaron y forzaron a negativo {total_notas_credito:,} Notas de Crédito.")

        if len(uploaded_files) > 1:
            st.success(f"✅ Se combinaron {len(uploaded_files)} archivos: {', '.join(f.name for f in uploaded_files)}")

            # --- QUITA DUPLICADOS SI DOS ARCHIVOS TRAEN LAS MISMAS FILAS (periodos que se pisan) ---
            cols_clave_dup = [c for c in ['Fecha', 'Nro SAP', 'Folio SII', 'Cod.', 'Cod Cliente', 'Total Línea'] if c in df.columns]
            if cols_clave_dup:
                filas_antes = len(df)
                df = df.drop_duplicates(subset=cols_clave_dup)
                duplicados_quitados = filas_antes - len(df)
                if duplicados_quitados > 0:
                    st.warning(
                        f"⚠️ Se detectaron y quitaron {duplicados_quitados:,} filas duplicadas entre los archivos "
                        "(probablemente por periodos que se superponen entre los archivos que subiste)."
                    )
        
        # Muestra la advertencia y las filas si hubo descartes
        if not df_descartadas.empty:
            st.warning(f"⚠️ Atención: Se descartaron {len(df_descartadas)} filas del archivo original porque no tenían una fecha válida registrada. Puedes inspeccionarlas abajo.")
            with st.expander("👀 Ver las filas descartadas"):
                df_mostrar = df_descartadas.copy()
                for c in df_mostrar.columns:
                    df_mostrar[c] = df_mostrar[c].astype(str)
                st.dataframe(df_mostrar, width='stretch')
                excel_desc = generar_excel_bonito({'Filas Descartadas': (df_descartadas, {})})
                st.download_button("📥 Descargar Filas Descartadas (Excel)", excel_desc, "filas_sin_fecha_valida.xlsx", key="dl_desc")
            
        cols_fecha = df.select_dtypes(include=['datetime64']).columns.tolist()
        if not cols_fecha:
            st.error("El archivo no contiene una columna de fecha válida (después de la limpieza).")
            st.stop()

        # --- AVISO DE MESES POSIBLEMENTE INCOMPLETOS (export truncado en el origen) ---
        meses_incompletos = detectar_meses_incompletos(df)
        if meses_incompletos:
            st.error(
                "🚨 **Atención: el archivo parece venir incompleto para uno o más meses.** "
                "Esto normalmente pasa cuando el exportador de origen (SAP/BI) corta el archivo "
                "por límite de volumen, no porque hayan bajado las ventas.\n\n"
                "Meses sospechosos:\n" + "\n".join(f"- {m}" for m in meses_incompletos) +
                "\n\nSi vas a comparar alguno de estos meses contra otro periodo, los resultados "
                "no serán confiables hasta re-exportar los datos completos (por ejemplo en tandas "
                "más chicas por trimestre) y volver a subir el archivo."
            )

        meses_map = {1:'Enero', 2:'Febrero', 3:'Marzo', 4:'Abril', 5:'Mayo', 6:'Junio', 
                     7:'Julio', 8:'Agosto', 9:'Septiembre', 10:'Octubre', 11:'Noviembre', 12:'Diciembre'}

        # --- PANEL DE CONTROLES (Filtros Globales Arriba) ---
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
            meses_disponibles_nombres = [meses_map[m] for m in meses_disponibles_nums]

            if modo == "Comparativa (A vs B)":
                col_periodo_a, col_periodo_b = st.columns(2)

                with col_periodo_a:
                    st.markdown("##### 🟦 Periodo A (Base)")
                    anio_a = st.selectbox("Año Periodo A", anos_disponibles, index=0, key='anio_a')
                    meses_a_nombres = st.multiselect("Mes(es) Periodo A", meses_disponibles_nombres, default=[meses_disponibles_nombres[0]], key='mes_a')
                    mes_a_num = [k for k, v in meses_map.items() if v in meses_a_nombres]

                with col_periodo_b:
                    st.markdown("##### 🟧 Periodo B (Comparación)")
                    anio_b = st.selectbox("Año Periodo B", anos_disponibles, index=len(anos_disponibles)-1, key='anio_b')
                    sincronizar_meses = st.checkbox("Usar los mismos meses que Periodo A", value=True, key='sync_meses')
                    if sincronizar_meses:
                        meses_b_nombres = meses_a_nombres
                        st.caption(f"Meses B = {', '.join(meses_a_nombres) if meses_a_nombres else '(ninguno)'}")
                    else:
                        meses_b_nombres = st.multiselect("Mes(es) Periodo B", meses_disponibles_nombres, default=[meses_disponibles_nombres[-1]], key='mes_b')
                    mes_b_num = [k for k, v in meses_map.items() if v in meses_b_nombres]

                if not meses_a_nombres or not meses_b_nombres:
                    st.warning("Selecciona al menos un mes para el Periodo A y para el Periodo B.")
                    st.stop()
            else:
                st.markdown("##### 🟦 Periodo Único")
                anio_a = st.selectbox("Año", anos_disponibles, index=0, key='anio_unico')
                meses_a_nombres = st.multiselect("Mes(es)", meses_disponibles_nombres, default=[meses_disponibles_nombres[0]], key='mes_unico')
                mes_a_num = [k for k, v in meses_map.items() if v in meses_a_nombres]

                # Variables de seguridad
                anio_b = anio_a
                meses_b_nombres = []
                mes_b_num = []

                if not meses_a_nombres:
                    st.warning("Selecciona al menos un mes.")
                    st.stop()

        # Etiqueta ordenada cronológicamente
        meses_a_ordenados = [meses_map[n] for n in sorted(mes_a_num)]
        label_a = f"{', '.join(meses_a_ordenados)} {anio_a}"

        # Filtrado de DataFrames según el modo
        df_a = df_filtrado[(df_filtrado['Año'] == anio_a) & (df_filtrado['Mes_Num'].isin(mes_a_num))].copy()
        
        if modo == "Comparativa (A vs B)":
            df_b = df_filtrado[(df_filtrado['Año'] == anio_b) & (df_filtrado['Mes_Num'].isin(mes_b_num))].copy()
            meses_b_ordenados = [meses_map[n] for n in sorted(mes_b_num)]
            label_b = f"{', '.join(meses_b_ordenados)} {anio_b}"
            
            st.markdown(f'<div class="periodo-header">📌 Periodo Analizado: [{label_a}]  vs  [{label_b}]</div>', unsafe_allow_html=True)
            
            df_a['Periodo'] = label_a
            df_b['Periodo'] = label_b
            df_dual = pd.concat([df_a, df_b])
        else:
            df_b = pd.DataFrame() 
            label_b = ""
            
            st.markdown(f'<div class="periodo-header">📌 Periodo Analizado: [{label_a}]</div>', unsafe_allow_html=True)
            
            df_a['Periodo'] = label_a
            df_dual = df_a.copy()

        # Mapeo de color FIJO
        color_map = {label_a: '#38bdf8'}
        if modo == "Comparativa (A vs B)":
            color_map[label_b] = '#d97706'

        col_sort_tabla = label_b if modo == "Comparativa (A vs B)" else label_a
        col_prod = next((c for c in ['Detalle', 'Producto', 'Descripción', 'Articulo', 'Nombre Artículo', 'Material', 'Desc. Artículo', 'Item'] if c in df_dual.columns), None)

        if not df_a.empty or (modo == "Comparativa (A vs B)" and not df_b.empty):
            
            tab1, tab2, tab3, tab4 = st.tabs([
                "📊 Dashboard General", 
                "🛍️ Análisis de Productos", 
                "👥 Análisis de Clientes", 
                "📂 Datos y Resúmenes"
            ])

            # ---------------------------------------------------------------------
            # PESTAÑA 1: DASHBOARD GENERAL
            # ---------------------------------------------------------------------
            with tab1:
                if modo == "Comparativa (A vs B)":
                    st.markdown(f'<div class="sub-seccion">🔵 Indicadores Clave: {label_a} (Periodo Base)</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="sub-seccion">🔵 Indicadores Clave: {label_a}</div>', unsafe_allow_html=True)
                    
                kpi_a1, kpi_a2, kpi_a3, kpi_a4 = st.columns(4)
                
                v_a = df_a['Total Línea'].sum() if 'Total Línea' in df_a.columns else 0
                k_a = df_a['Kilos'].sum() if 'Kilos' in df_a.columns else 0
                
                kpis_a = calcular_kpis(df_a)

                kpi_a1.metric("Venta Total (A)" if modo == "Comparativa (A vs B)" else "Venta Total", f"${v_a:,.0f} CLP")
                kpi_a2.metric("Volumen Kilos (A)" if modo == "Comparativa (A vs B)" else "Volumen Kilos", f"{k_a:,.0f} kg")
                kpi_a3.metric("Ticket Promedio (A)" if modo == "Comparativa (A vs B)" else "Ticket Promedio", f"${kpis_a['ticket']:,.0f} CLP")
                kpi_a4.metric("Clientes Activos (A)" if modo == "Comparativa (A vs B)" else "Clientes Activos", f"{kpis_a['clientes']:,}")

                if modo == "Comparativa (A vs B)":
                    st.markdown(f'<div class="sub-seccion">🟠 Indicadores Clave: {label_b} (Periodo Comparativo)</div>', unsafe_allow_html=True)
                    kpi_b1, kpi_b2, kpi_b3, kpi_b4 = st.columns(4)
                    
                    v_b = df_b['Total Línea'].sum() if 'Total Línea' in df_b.columns else 0
                    k_b = df_b['Kilos'].sum() if 'Kilos' in df_b.columns else 0
                    kpis_b = calcular_kpis(df_b)

                    d_v = ((v_b - v_a) / v_a * 100) if v_a > 0 else 0
                    d_k = ((k_b - k_a) / k_a * 100) if k_a > 0 else 0
                    d_t = ((kpis_b['ticket'] - kpis_a['ticket']) / kpis_a['ticket'] * 100) if kpis_a['ticket'] > 0 else 0
                    d_c = ((kpis_b['clientes'] - kpis_a['clientes']) / kpis_a['clientes'] * 100) if kpis_a['clientes'] > 0 else 0

                    kpi_b1.metric("Venta Total (B)", f"${v_b:,.0f} CLP", f"{d_v:+.1f}% vs A")
                    kpi_b2.metric("Volumen Kilos (B)", f"{k_b:,.0f} kg", f"{d_k:+.1f}% vs A")
                    kpi_b3.metric("Ticket Promedio (B)", f"${kpis_b['ticket']:,.0f} CLP", f"{d_t:+.1f}% vs A")
                    kpi_b4.metric("Clientes Activos (B)", f"{kpis_b['clientes']:,}", f"{d_c:+.1f}% vs A")

                st.divider()

                col_dash1, col_dash2 = st.columns(2)
                
                with col_dash1:
                    st.subheader("🗺️ Rendimiento Comercial por Zona")
                    if 'Zona' in df_dual.columns and 'Total Línea' in df_dual.columns:
                        df_zona = df_dual.groupby(['Zona', 'Periodo'], as_index=False)['Total Línea'].sum()
                        fig_zona = px.bar(df_zona, x='Zona', y='Total Línea', color='Periodo', barmode='group', template="plotly_dark",
                                          labels={'Total Línea': 'Venta ($ CLP)', 'Zona': 'Zona'},
                                          color_discrete_map=color_map)
                        fig_zona.update_layout(yaxis_tickprefix="$", yaxis_tickformat=",.", height=450)
                        st.plotly_chart(fig_zona, width='stretch')
                        
                        excel_zona = generar_excel_bonito({'Zonas': (df_zona, {'Total Línea': 'moneda'})})
                        st.download_button("📥 Descargar Datos Excel", excel_zona, "grafico_zonas.xlsx", key="dl_zona", width='stretch')

                with col_dash2:
                    titulo_vend = "🏆 Rendimiento de Todos los Vendedores"
                    st.subheader(titulo_vend)
                    if 'Vendedor' in df_dual.columns and 'Total Línea' in df_dual.columns:
                        df_vend = df_dual.groupby(['Vendedor', 'Periodo'], as_index=False)['Total Línea'].sum()
                        fig_vend = px.bar(df_vend, x='Vendedor', y='Total Línea', color='Periodo', barmode='group', template="plotly_dark",
                                          labels={'Total Línea': 'Venta ($ CLP)'}, color_discrete_map=color_map)
                        fig_vend.update_layout(xaxis={'categoryorder':'total descending'}, yaxis_tickprefix="$", yaxis_tickformat=",.", height=450)
                        st.plotly_chart(fig_vend, width='stretch')
                        
                        excel_vend = generar_excel_bonito({'Vendedores': (df_vend, {'Total Línea': 'moneda'})})
                        st.download_button("📥 Descargar Datos Excel", excel_vend, "grafico_vendedores.xlsx", key="dl_vend", width='stretch')

                st.divider()
                
                st.subheader("🥧 Participación Mix de Categorías")
                if 'Categoría' in df_dual.columns and 'Total Línea' in df_dual.columns:
                    df_cat = df_dual.groupby(['Categoría', 'Periodo'], as_index=False)['Total Línea'].sum()
                    fig_cat = px.bar(df_cat, x='Categoría', y='Total Línea', color='Periodo', barmode='group', template="plotly_dark",
                                     labels={'Total Línea': 'Venta ($ CLP)'}, color_discrete_map=color_map)
                    fig_cat.update_layout(xaxis={'categoryorder':'total descending'}, yaxis_tickprefix="$", yaxis_tickformat=",.", height=450)
                    st.plotly_chart(fig_cat, width='stretch')
                    
                    excel_cat = generar_excel_bonito({'Categorías': (df_cat, {'Total Línea': 'moneda'})})
                    st.download_button("📥 Descargar Datos Excel", excel_cat, "grafico_categorias.xlsx", key="dl_cat", width='stretch')

            # ---------------------------------------------------------------------
            # PESTAÑA 2: ANÁLISIS DE PRODUCTOS
            # ---------------------------------------------------------------------
            with tab2:
                st.markdown('<div class="sub-seccion">👤 Filtro de Vendedor (Aplica a Rendimiento Productos y Clientes)</div>', unsafe_allow_html=True)
                if 'Vendedor' in df_dual.columns:
                    vendedores_disp_tab2 = sorted(df_dual['Vendedor'].dropna().astype(str).unique().tolist())
                    opciones_v2 = ["Todos"] + vendedores_disp_tab2
                    
                    # Recupera de la memoria si el valor existe en las opciones actuales
                    idx_v2 = opciones_v2.index(st.session_state.mem_vend_t2) if st.session_state.mem_vend_t2 in opciones_v2 else 0
                    
                    vend_sel_tab2 = st.selectbox(
                        "Selecciona un vendedor para ver sus productos vendidos", 
                        opciones_v2, 
                        index=idx_v2,
                        key="widget_vend_t2"
                    )
                    st.session_state.mem_vend_t2 = vend_sel_tab2  # Guarda en memoria
                    
                    if vend_sel_tab2 == "Todos":
                        df_tab2 = df_dual.copy()
                    else:
                        df_tab2 = df_dual[df_dual['Vendedor'].astype(str) == vend_sel_tab2].copy()
                else:
                    df_tab2 = df_dual.copy()
                    vend_sel_tab2 = "Todos"

                st.divider()

                # --- ELIMINADA LA RESTRICCIÓN DE "TOP 20" AHORA MUESTRA TODOS LOS PRODUCTOS ---
                st.subheader(f"🛍️ Rendimiento de Todos los Productos {'(Todos los Vendedores)' if vend_sel_tab2 == 'Todos' else f'(Vendedor: {vend_sel_tab2})'}")
                if col_prod and 'Total Línea' in df_tab2.columns:
                    df_prod = df_tab2.groupby([col_prod, 'Periodo'], as_index=False)['Total Línea'].sum()
                    
                    if not df_prod.empty:
                        # Cálculo de altura dinámica para que el gráfico no se aplaste si hay muchos productos
                        num_productos_unicos = df_prod[col_prod].nunique()
                        alto_dinamico_grafico = max(600, num_productos_unicos * 25)

                        fig_prod = px.bar(df_prod, x='Total Línea', y=col_prod, color='Periodo', barmode='group', template="plotly_dark",
                                          orientation='h', labels={'Total Línea': 'Venta ($ CLP)', col_prod: 'Producto'},
                                          color_discrete_map=color_map)
                        fig_prod.update_layout(yaxis={'categoryorder':'total ascending'}, xaxis_tickprefix="$", xaxis_tickformat=",.", height=alto_dinamico_grafico)
                        st.plotly_chart(fig_prod, width='stretch')
                        
                        # --- EXCEL: pivoteamos para que cada Periodo/Año quede en su propia columna ---
                        tabla_prod_export = df_prod.pivot(index=col_prod, columns='Periodo', values='Total Línea').fillna(0)
                        if col_sort_tabla in tabla_prod_export.columns:
                            tabla_prod_export = tabla_prod_export.sort_values(by=col_sort_tabla, ascending=False)
                        tabla_prod_export = tabla_prod_export.reset_index()

                        formatos_prod_export = {label_a: 'moneda'}
                        if modo == "Comparativa (A vs B)":
                            formatos_prod_export[label_b] = 'moneda'

                        excel_prod = generar_excel_bonito({'Productos': (tabla_prod_export, formatos_prod_export)})
                        st.download_button("📥 Descargar Datos Excel", excel_prod, "grafico_todos_productos.xlsx", key="dl_prod", width='stretch')
                    else:
                        st.info(f"El vendedor {vend_sel_tab2} no registra ventas de productos en este periodo.")
                else:
                    st.info("No se detectó la columna de Productos (Descripción/Articulo) en el archivo.")

                st.divider()

                st.subheader(f"🧑‍🤝‍🧑 Clientes por Producto {'(Todos los Vendedores)' if vend_sel_tab2 == 'Todos' else f'(Vendedor: {vend_sel_tab2})'}")
                if col_prod and 'Nombre Cliente' in df_tab2.columns and 'Total Línea' in df_tab2.columns:
                    productos_disponibles = df_tab2.groupby(col_prod)['Total Línea'].sum().sort_values(ascending=False).index.tolist()
                    
                    if productos_disponibles:
                        idx_p2 = productos_disponibles.index(st.session_state.mem_prod_t2) if st.session_state.mem_prod_t2 in productos_disponibles else 0
                        
                        producto_sel = st.selectbox(
                            "Selecciona un producto para ver qué clientes lo compraron", 
                            productos_disponibles, 
                            index=idx_p2,
                            key='widget_prod_t2'
                        )
                        st.session_state.mem_prod_t2 = producto_sel  # Guarda en memoria

                        df_prod_cli = df_tab2[df_tab2[col_prod] == producto_sel]
                        df_prod_cli_agg = df_prod_cli.groupby(['Nombre Cliente', 'Periodo'], as_index=False)['Total Línea'].sum()

                        top_clientes_prod = df_prod_cli_agg.groupby('Nombre Cliente')['Total Línea'].sum().nlargest(20).index
                        df_prod_cli_agg = df_prod_cli_agg[df_prod_cli_agg['Nombre Cliente'].isin(top_clientes_prod)]

                        if not df_prod_cli_agg.empty:
                            fig_prod_cli = px.bar(
                                df_prod_cli_agg, x='Total Línea', y='Nombre Cliente', color='Periodo', barmode='group',
                                orientation='h', template="plotly_dark",
                                labels={'Total Línea': 'Venta ($ CLP)', 'Nombre Cliente': 'Cliente'},
                                color_discrete_map=color_map
                            )
                            fig_prod_cli.update_layout(yaxis={'categoryorder': 'total ascending'}, xaxis_tickprefix="$", xaxis_tickformat=",.", height=550)
                            st.plotly_chart(fig_prod_cli, width='stretch')
                            
                            # --- EXCEL: pivoteamos por Periodo en columnas ---
                            if 'Cod Cliente' in df_prod_cli.columns:
                                df_prod_cli_export_base = df_prod_cli[df_prod_cli['Nombre Cliente'].isin(top_clientes_prod)].groupby(
                                    ['Cod Cliente', 'Nombre Cliente', 'Periodo'], as_index=False
                                )['Total Línea'].sum()
                                tabla_cli_prod_export = df_prod_cli_export_base.pivot(
                                    index=['Cod Cliente', 'Nombre Cliente'], columns='Periodo', values='Total Línea'
                                ).fillna(0)
                            else:
                                tabla_cli_prod_export = df_prod_cli_agg.pivot(index='Nombre Cliente', columns='Periodo', values='Total Línea').fillna(0)

                            if col_sort_tabla in tabla_cli_prod_export.columns:
                                tabla_cli_prod_export = tabla_cli_prod_export.sort_values(by=col_sort_tabla, ascending=False)
                            tabla_cli_prod_export = tabla_cli_prod_export.reset_index()

                            formatos_cli_prod_export = {label_a: 'moneda'}
                            if modo == "Comparativa (A vs B)":
                                formatos_cli_prod_export[label_b] = 'moneda'

                            excel_cli_prod = generar_excel_bonito({'Clientes_Prod': (tabla_cli_prod_export, formatos_cli_prod_export)})
                            st.download_button("📥 Descargar Datos Excel", excel_cli_prod, f"clientes_producto_{producto_sel[:10]}.xlsx", key="dl_cli_prod", width='stretch')
                        else:
                            st.info("No hay clientes registrados para este producto con los filtros actuales.")
                    else:
                        st.info("No hay productos disponibles para los filtros seleccionados.")
                else:
                    st.info("No se detectó columna de Cliente o Producto para generar este gráfico.")

            # ---------------------------------------------------------------------
            # PESTAÑA 3: ANÁLISIS DE CLIENTES
            # ---------------------------------------------------------------------
            with tab3:
                st.markdown('<div class="sub-seccion">👤 Filtro de Vendedor (Aplica a toda esta pestaña)</div>', unsafe_allow_html=True)
                
                if 'Vendedor' in df_dual.columns:
                    vendedores_disponibles_tab3 = sorted(df_dual['Vendedor'].dropna().astype(str).unique().tolist())
                    opciones_v3 = ["Todos"] + vendedores_disponibles_tab3
                    idx_v3 = opciones_v3.index(st.session_state.mem_vend_t3) if st.session_state.mem_vend_t3 in opciones_v3 else 0
                    
                    filtro_vendedor_tab3 = st.selectbox(
                        "Selecciona un vendedor para analizar exclusivamente su cartera de clientes:",
                        opciones_v3,
                        index=idx_v3,
                        key="widget_vend_t3"
                    )
                    st.session_state.mem_vend_t3 = filtro_vendedor_tab3 # Guarda en memoria
                    
                    if filtro_vendedor_tab3 == "Todos":
                        df_a_tab3 = df_a.copy()
                        df_b_tab3 = df_b.copy() if not df_b.empty else pd.DataFrame()
                        df_dual_tab3 = df_dual.copy()
                    else:
                        df_a_tab3 = df_a[df_a['Vendedor'].astype(str) == filtro_vendedor_tab3].copy()
                        df_b_tab3 = df_b[df_b['Vendedor'].astype(str) == filtro_vendedor_tab3].copy() if not df_b.empty else pd.DataFrame()
                        df_dual_tab3 = df_dual[df_dual['Vendedor'].astype(str) == filtro_vendedor_tab3].copy()
                else:
                    df_a_tab3 = df_a.copy()
                    df_b_tab3 = df_b.copy() if not df_b.empty else pd.DataFrame()
                    df_dual_tab3 = df_dual.copy()

                st.divider()

                if modo == "Comparativa (A vs B)":
                    st.markdown(f'<div class="sub-seccion">🔵 Indicadores del Vendedor: {label_a} (Periodo Base)</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="sub-seccion">🔵 Indicadores del Vendedor: {label_a}</div>', unsafe_allow_html=True)

                kpis_a_vend = calcular_kpis(df_a_tab3)

                if modo == "Comparativa (A vs B)":
                    kpis_b_vend = calcular_kpis(df_b_tab3)

                    kv_a1, kv_a2, kv_a3, kv_a4 = st.columns(4)
                    kv_a1.metric("Venta Total (A)", f"${kpis_a_vend['venta']:,.0f} CLP")
                    kv_a2.metric("Volumen Kilos (A)", f"{kpis_a_vend['kilos']:,.0f} kg")
                    kv_a3.metric("Ticket Promedio (A)", f"${kpis_a_vend['ticket']:,.0f} CLP")
                    kv_a4.metric("Clientes Activos (A)", f"{kpis_a_vend['clientes']:,}")

                    d_v_vend = ((kpis_b_vend['venta'] - kpis_a_vend['venta']) / kpis_a_vend['venta'] * 100) if kpis_a_vend['venta'] > 0 else 0
                    d_k_vend = ((kpis_b_vend['kilos'] - kpis_a_vend['kilos']) / kpis_a_vend['kilos'] * 100) if kpis_a_vend['kilos'] > 0 else 0
                    d_t_vend = ((kpis_b_vend['ticket'] - kpis_a_vend['ticket']) / kpis_a_vend['ticket'] * 100) if kpis_a_vend['ticket'] > 0 else 0
                    d_c_vend = ((kpis_b_vend['clientes'] - kpis_a_vend['clientes']) / kpis_a_vend['clientes'] * 100) if kpis_a_vend['clientes'] > 0 else 0

                    st.markdown(f'<div class="sub-seccion">🟠 Indicadores del Vendedor: {label_b} (Periodo Comparativo)</div>', unsafe_allow_html=True)

                    kv_b1, kv_b2, kv_b3, kv_b4 = st.columns(4)
                    kv_b1.metric("Venta Total (B)", f"${kpis_b_vend['venta']:,.0f} CLP", f"{d_v_vend:+.1f}% vs A")
                    kv_b2.metric("Volumen Kilos (B)", f"{kpis_b_vend['kilos']:,.0f} kg", f"{d_k_vend:+.1f}% vs A")
                    kv_b3.metric("Ticket Promedio (B)", f"${kpis_b_vend['ticket']:,.0f} CLP", f"{d_t_vend:+.1f}% vs A")
                    kv_b4.metric("Clientes Activos (B)", f"{kpis_b_vend['clientes']:,}", f"{d_c_vend:+.1f}% vs A")
                else:
                    kv1, kv2, kv3, kv4 = st.columns(4)
                    kv1.metric("Venta Total", f"${kpis_a_vend['venta']:,.0f} CLP")
                    kv2.metric("Volumen Kilos", f"{kpis_a_vend['kilos']:,.0f} kg")
                    kv3.metric("Ticket Promedio", f"${kpis_a_vend['ticket']:,.0f} CLP")
                    kv4.metric("Clientes Activos", f"{kpis_a_vend['clientes']:,}")

                st.divider()

                st.subheader("🔄 Clientes Nuevos y Perdidos")
                if modo == "Comparativa (A vs B)":
                    st.caption("Compara la cartera de clientes entre el Periodo A y el Periodo B configurados en la parte superior.")
                    if 'Nombre Cliente' in df_a_tab3.columns and 'Nombre Cliente' in df_b_tab3.columns:
                        clientes_a_set = set(df_a_tab3['Nombre Cliente'].dropna().unique())
                        clientes_b_set = set(df_b_tab3['Nombre Cliente'].dropna().unique())

                        clientes_nuevos = clientes_b_set - clientes_a_set
                        clientes_perdidos = clientes_a_set - clientes_b_set
                        clientes_retenidos = clientes_a_set & clientes_b_set

                        m1, m2, m3 = st.columns(3)
                        m1.metric("🟢 Clientes Nuevos", f"{len(clientes_nuevos):,}")
                        m2.metric("🔴 Clientes Perdidos", f"{len(clientes_perdidos):,}")
                        m3.metric("🔵 Clientes Retenidos", f"{len(clientes_retenidos):,}")

                        with st.expander("Ver lista de Clientes Nuevos y Perdidos", expanded=False):
                            col_nuevos, col_perdidos = st.columns(2)
                            df_nuevos = pd.DataFrame(columns=['Cod Cliente', 'Nombre Cliente', 'Vendedor', f'Venta {label_b}', f'Kilos {label_b}'])
                            df_perdidos = pd.DataFrame(columns=['Cod Cliente', 'Nombre Cliente', 'Vendedor', f'Venta {label_a}', f'Kilos {label_a}'])

                            # ----- PROCESAR CLIENTES NUEVOS -----
                            with col_nuevos:
                                st.markdown(f"##### 🟢 Nuevos en {label_b}")
                                if clientes_nuevos:
                                    agg_dict_n = {f'Venta {label_b}': ('Total Línea', 'sum')}
                                    if 'Cod Cliente' in df_b_tab3.columns:
                                        agg_dict_n['Cod Cliente'] = ('Cod Cliente', 'first')
                                    if 'Vendedor' in df_b_tab3.columns:
                                        agg_dict_n['Vendedor'] = ('Vendedor', 'first')
                                    if 'Kilos' in df_b_tab3.columns:
                                        agg_dict_n[f'Kilos {label_b}'] = ('Kilos', 'sum')
                                        
                                    df_nuevos = df_b_tab3[df_b_tab3['Nombre Cliente'].isin(clientes_nuevos)].groupby('Nombre Cliente', as_index=False).agg(**agg_dict_n)
                                    df_nuevos = df_nuevos.sort_values(f'Venta {label_b}', ascending=False)
                                    
                                    # Reordenar columnas para visualización limpia
                                    cols_ordenadas_n = ['Cod Cliente', 'Nombre Cliente', 'Vendedor', f'Venta {label_b}', f'Kilos {label_b}']
                                    cols_finales_n = [c for c in cols_ordenadas_n if c in df_nuevos.columns]
                                    df_nuevos = df_nuevos[cols_finales_n]

                                    formato = {f'Venta {label_b}': '${:,.0f}'}
                                    if f'Kilos {label_b}' in df_nuevos.columns:
                                        formato[f'Kilos {label_b}'] = '{:,.0f}'
                                    st.dataframe(df_nuevos.style.format(formato), width='stretch', hide_index=True)
                                else:
                                    st.caption("No hay clientes nuevos en este periodo.")

                            # ----- PROCESAR CLIENTES PERDIDOS -----
                            with col_perdidos:
                                st.markdown(f"##### 🔴 Perdidos de {label_a}")
                                if clientes_perdidos:
                                    agg_dict_p = {f'Venta {label_a}': ('Total Línea', 'sum')}
                                    if 'Cod Cliente' in df_a_tab3.columns:
                                        agg_dict_p['Cod Cliente'] = ('Cod Cliente', 'first')
                                    if 'Vendedor' in df_a_tab3.columns:
                                        agg_dict_p['Vendedor'] = ('Vendedor', 'first')
                                    if 'Kilos' in df_a_tab3.columns:
                                        agg_dict_p[f'Kilos {label_a}'] = ('Kilos', 'sum')
                                        
                                    df_perdidos = df_a_tab3[df_a_tab3['Nombre Cliente'].isin(clientes_perdidos)].groupby('Nombre Cliente', as_index=False).agg(**agg_dict_p)
                                    df_perdidos = df_perdidos.sort_values(f'Venta {label_a}', ascending=False)
                                    
                                    # Reordenar columnas para visualización limpia
                                    cols_ordenadas_p = ['Cod Cliente', 'Nombre Cliente', 'Vendedor', f'Venta {label_a}', f'Kilos {label_a}']
                                    cols_finales_p = [c for c in cols_ordenadas_p if c in df_perdidos.columns]
                                    df_perdidos = df_perdidos[cols_finales_p]

                                    formato = {f'Venta {label_a}': '${:,.0f}'}
                                    if f'Kilos {label_a}' in df_perdidos.columns:
                                        formato[f'Kilos {label_a}'] = '{:,.0f}'
                                    st.dataframe(df_perdidos.style.format(formato), width='stretch', hide_index=True)
                                else:
                                    st.caption("No hay clientes perdidos en este periodo.")

                            st.divider()
                            formatos_nuevos = {f'Venta {label_b}': 'moneda', f'Kilos {label_b}': 'kilos'}
                            formatos_perdidos = {f'Venta {label_a}': 'moneda', f'Kilos {label_a}': 'kilos'}
                            excel_bytes = generar_excel_bonito({
                                'Clientes Nuevos': (df_nuevos, formatos_nuevos),
                                'Clientes Perdidos': (df_perdidos, formatos_perdidos),
                            })
                            st.download_button(
                                "📥 Descargar Excel (Nuevos y Perdidos)",
                                data=excel_bytes,
                                file_name="clientes_nuevos_perdidos.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key="descarga_nuevos_perdidos",
                                width='stretch'
                            )
                    else:
                        st.info("No se detectó la columna 'Nombre Cliente' para calcular clientes nuevos/perdidos.")
                else:
                    st.info("El análisis de Clientes Nuevos/Perdidos solo está disponible en modo Comparativa (A vs B).")

                st.divider()

                st.subheader("👥 Top 20 Clientes con Mayor Venta")
                if 'Nombre Cliente' in df_a_tab3.columns and 'Total Línea' in df_a_tab3.columns:
                    cli_a_tab3_agg = df_a_tab3.groupby('Nombre Cliente', as_index=False).agg(**{
                        f'Venta {label_a}': ('Total Línea', 'sum'),
                        f'Kilos {label_a}': ('Kilos', 'sum')
                    })
                    
                    if modo == "Comparativa (A vs B)":
                        cli_b_tab3_agg = df_b_tab3.groupby('Nombre Cliente', as_index=False).agg(**{
                            f'Venta {label_b}': ('Total Línea', 'sum'),
                            f'Kilos {label_b}': ('Kilos', 'sum')
                        })
                        resumen_cli_tab3 = pd.merge(cli_a_tab3_agg, cli_b_tab3_agg, on='Nombre Cliente', how='outer').fillna(0)
                        resumen_cli_tab3['Venta Total'] = resumen_cli_tab3[f'Venta {label_a}'] + resumen_cli_tab3[f'Venta {label_b}']
                        top20_cli_tab3 = resumen_cli_tab3.sort_values('Venta Total', ascending=False).head(20)
                    else:
                        cli_a_tab3_agg['Venta Total'] = cli_a_tab3_agg[f'Venta {label_a}']
                        top20_cli_tab3 = cli_a_tab3_agg.sort_values('Venta Total', ascending=False).head(20)

                    df_cli_plot = df_dual_tab3[df_dual_tab3['Nombre Cliente'].isin(top20_cli_tab3['Nombre Cliente'])]
                    df_cli_plot = df_cli_plot.groupby(['Nombre Cliente', 'Periodo'], as_index=False)['Total Línea'].sum()
                    orden_clientes = top20_cli_tab3.sort_values('Venta Total', ascending=True)['Nombre Cliente'].tolist()
                    
                    if not df_cli_plot.empty:
                        fig_cli = px.bar(
                            df_cli_plot, y='Nombre Cliente', x='Total Línea', color='Periodo', barmode='group',
                            orientation='h', template="plotly_dark",
                            category_orders={'Nombre Cliente': orden_clientes},
                            labels={'Total Línea': 'Venta ($ CLP)', 'Nombre Cliente': 'Cliente'},
                            color_discrete_map=color_map
                        )
                        fig_cli.update_layout(height=650, xaxis_tickprefix="$", xaxis_tickformat=",.")
                        st.plotly_chart(fig_cli, width='stretch')
                        
                        excel_top_cli = generar_excel_bonito({'Top20_Clientes': (df_cli_plot, {'Total Línea': 'moneda'})})
                        st.download_button("📥 Descargar Datos Excel", excel_top_cli, "grafico_top20_clientes.xlsx", key="dl_top_cli", width='stretch')
                    else:
                        st.info("No hay ventas registradas para generar el gráfico de clientes.")

            # ---------------------------------------------------------------------
            # PESTAÑA 4: DATOS Y RESÚMENES (TABLAS)
            # ---------------------------------------------------------------------
            with tab4:
                # Top 20 Clientes general para Tablas
                top20_cli = None
                if 'Nombre Cliente' in df_a.columns and 'Total Línea' in df_a.columns:
                    cli_a = df_a.groupby('Nombre Cliente', as_index=False).agg(**{
                        f'Venta {label_a}': ('Total Línea', 'sum'),
                        f'Kilos {label_a}': ('Kilos', 'sum')
                    })
                    if modo == "Comparativa (A vs B)":
                        cli_b = df_b.groupby('Nombre Cliente', as_index=False).agg(**{
                            f'Venta {label_b}': ('Total Línea', 'sum'),
                            f'Kilos {label_b}': ('Kilos', 'sum')
                        })
                        resumen_cli = pd.merge(cli_a, cli_b, on='Nombre Cliente', how='outer').fillna(0)
                        resumen_cli['Venta Total'] = resumen_cli[f'Venta {label_a}'] + resumen_cli[f'Venta {label_b}']
                        top20_cli = resumen_cli.sort_values('Venta Total', ascending=False).head(20)
                    else:
                        cli_a['Venta Total'] = cli_a[f'Venta {label_a}']
                        top20_cli = cli_a.sort_values('Venta Total', ascending=False).head(20)

                st.subheader("📋 Resumen de Ventas por Categoría")
                if 'Categoría' in df_a.columns and 'Total Línea' in df_a.columns:
                    cat_a = df_a.groupby('Categoría', as_index=False).agg(**{
                        f'Venta {label_a}': ('Total Línea', 'sum'),
                        f'Kilos {label_a}': ('Kilos', 'sum')
                    })
                    
                    if modo == "Comparativa (A vs B)":
                        cat_b = df_b.groupby('Categoría', as_index=False).agg(**{
                            f'Venta {label_b}': ('Total Línea', 'sum'),
                            f'Kilos {label_b}': ('Kilos', 'sum')
                        })
                        resumen_cat = pd.merge(cat_a, cat_b, on='Categoría', how='outer').fillna(0)
                        resumen_cat['Δ Venta %'] = resumen_cat.apply(
                            lambda r: ((r[f'Venta {label_b}'] - r[f'Venta {label_a}']) / r[f'Venta {label_a}'] * 100)
                            if r[f'Venta {label_a}'] != 0 else 0, axis=1
                        )
                        resumen_cat = resumen_cat.sort_values(f'Venta {label_b}', ascending=False)

                        fila_total = pd.DataFrame([{
                            'Categoría': 'Total',
                            f'Venta {label_a}': resumen_cat[f'Venta {label_a}'].sum(),
                            f'Kilos {label_a}': resumen_cat[f'Kilos {label_a}'].sum(),
                            f'Venta {label_b}': resumen_cat[f'Venta {label_b}'].sum(),
                            f'Kilos {label_b}': resumen_cat[f'Kilos {label_b}'].sum(),
                        }])
                        v_a_tot = fila_total[f'Venta {label_a}'].iloc[0]
                        v_b_tot = fila_total[f'Venta {label_b}'].iloc[0]
                        fila_total['Δ Venta %'] = ((v_b_tot - v_a_tot) / v_a_tot * 100) if v_a_tot != 0 else 0

                        resumen_cat_final = pd.concat([resumen_cat, fila_total], ignore_index=True)

                        st.dataframe(
                            resumen_cat_final.style.format({
                                f'Venta {label_a}': '${:,.0f}',
                                f'Venta {label_b}': '${:,.0f}',
                                f'Kilos {label_a}': '{:,.0f}',
                                f'Kilos {label_b}': '{:,.0f}',
                                'Δ Venta %': '{:+.1f}%'
                            }),
                            width='stretch', hide_index=True
                        )
                        
                        excel_res_cat = generar_excel_bonito({'Resumen_Categorias': (resumen_cat_final, {f'Venta {label_a}': 'moneda', f'Venta {label_b}': 'moneda', 'Δ Venta %': 'porcentaje'})})
                        st.download_button("📥 Descargar Tabla Excel", excel_res_cat, "tabla_categorias.xlsx", key="dl_tab_cat", width='stretch')
                    else:
                        cat_a = cat_a.sort_values(f'Venta {label_a}', ascending=False)
                        fila_total = pd.DataFrame([{
                            'Categoría': 'Total',
                            f'Venta {label_a}': cat_a[f'Venta {label_a}'].sum(),
                            f'Kilos {label_a}': cat_a[f'Kilos {label_a}'].sum(),
                        }])
                        resumen_cat_final = pd.concat([cat_a, fila_total], ignore_index=True)
                        
                        st.dataframe(
                            resumen_cat_final.style.format({
                                f'Venta {label_a}': '${:,.0f}',
                                f'Kilos {label_a}': '{:,.0f}'
                            }),
                            width='stretch', hide_index=True
                        )
                        excel_res_cat = generar_excel_bonito({'Resumen_Categorias': (resumen_cat_final, {f'Venta {label_a}': 'moneda'})})
                        st.download_button("📥 Descargar Tabla Excel", excel_res_cat, "tabla_categorias.xlsx", key="dl_tab_cat_simple", width='stretch')

                st.divider()

                col_tab1, col_tab2 = st.columns(2)
                with col_tab1:
                    st.subheader("🛍️ Datos: Todos los Productos")
                    if col_prod and 'Total Línea' in df_dual.columns:
                        tabla_prod = df_dual.groupby([col_prod, 'Periodo'], as_index=False)['Total Línea'].sum()
                        tabla_prod = tabla_prod.pivot(index=col_prod, columns='Periodo', values='Total Línea').fillna(0)
                        if col_sort_tabla in tabla_prod.columns:
                            tabla_prod = tabla_prod.sort_values(by=col_sort_tabla, ascending=False)
                        st.dataframe(tabla_prod.style.format("${:,.0f}"), width='stretch')
                        
                        excel_tab_prod = generar_excel_bonito({'Productos': (tabla_prod.reset_index(), {label_a: 'moneda', label_b: 'moneda'} if modo == "Comparativa (A vs B)" else {label_a: 'moneda'})})
                        st.download_button("📥 Descargar Excel", excel_tab_prod, "tabla_todos_productos.xlsx", key="dl_tab_prod", width='stretch')

                with col_tab2:
                    st.subheader("👥 Datos: Top 20 Clientes")
                    if 'Nombre Cliente' in df_dual.columns and 'Total Línea' in df_dual.columns:
                        if modo == "Comparativa (A vs B)":
                            st.dataframe(
                                top20_cli.drop(columns=['Venta Total']).style.format({
                                    f'Venta {label_a}': '${:,.0f}',
                                    f'Venta {label_b}': '${:,.0f}',
                                    f'Kilos {label_a}': '{:,.0f}',
                                    f'Kilos {label_b}': '{:,.0f}',
                                    'Δ Venta %': '{:+.1f}%'
                                }),
                                width='stretch', hide_index=True
                            )
                            excel_tab_cli = generar_excel_bonito({'Top_Clientes': (top20_cli.drop(columns=['Venta Total']), {f'Venta {label_a}': 'moneda', f'Venta {label_b}': 'moneda', 'Δ Venta %': 'porcentaje'})})
                            st.download_button("📥 Descargar Excel", excel_tab_cli, "tabla_top20_clientes.xlsx", key="dl_tab_cli", width='stretch')
                        else:
                            st.dataframe(
                                top20_cli.drop(columns=['Venta Total']).style.format({
                                    f'Venta {label_a}': '${:,.0f}',
                                    f'Kilos {label_a}': '{:,.0f}'
                                }),
                                width='stretch', hide_index=True
                            )
                            excel_tab_cli = generar_excel_bonito({'Top_Clientes': (top20_cli.drop(columns=['Venta Total']), {f'Venta {label_a}': 'moneda'})})
                            st.download_button("📥 Descargar Excel", excel_tab_cli, "tabla_top20_clientes.xlsx", key="dl_tab_cli_smp", width='stretch')

                st.divider()
                
                titulo_tabla_final = "📂 Inspeccionar Tabla Consolidada (Base de Datos Procesada)"
                st.subheader(titulo_tabla_final)
                df_vista = df_dual.copy()
                cols_busqueda = [c for c in ['Cod Cliente', 'Nombre Cliente', 'Zona'] if c in df_vista.columns]
                
                busqueda = st.text_input("🔎 Buscar por RUT (Cod Cliente), Nombre Cliente o Zona", key="busqueda_tabla")
                if busqueda:
                    q = busqueda.strip().lower()
                    mascara = pd.Series(False, index=df_vista.index)
                    for c in cols_busqueda:
                        mascara |= df_vista[c].astype(str).str.lower().str.contains(q, na=False)
                    df_vista = df_vista[mascara]
                    st.caption(f"{len(df_vista):,} filas encontradas")

                st.dataframe(df_vista, width='stretch')
                excel_vista = generar_excel_bonito({'Consolidado': (df_vista, {'Total Línea': 'moneda', 'Kilos': 'kilos'})})
                st.download_button("📥 Descargar Base de Datos Completa (Excel)", excel_vista, "base_datos_consolidada.xlsx", key="dl_tab_vista")

        else:
            st.warning("No se encontraron registros para los periodos seleccionados.")

    except Exception as e:
        st.error(f"Error crítico en el motor de comparación: {e}")