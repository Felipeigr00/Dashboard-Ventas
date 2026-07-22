import streamlit as st
import pandas as pd
import plotly.express as px
from utils import cargar_y_limpiar_datos  # <--- Importación del módulo externo

# Configuración inicial de la página
st.set_page_config(page_title="Dashboard Ejecutivo · Dark Coffee BI", layout="wide", page_icon="☕")

# Función para abrir gráficos en modal (Requiere Streamlit >= 1.34)
@st.dialog("Vista Ampliada del Gráfico", width="large")
def mostrar_grafico_modal(figura, altura=750):
    fig_ampliada = figura
    fig_ampliada.update_layout(height=altura)
    st.plotly_chart(fig_ampliada, use_container_width=True)

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

uploaded_file = st.file_uploader("Sube tu archivo de ventas (.xlsx, .xls o .csv)", type=["xlsx", "xls", "csv"])

if uploaded_file is not None:
    try:
        # --- CARGAMOS USANDO EL MÓDULO IMPORTADO ---
        df = cargar_y_limpiar_datos(uploaded_file)
        
        cols_fecha = df.select_dtypes(include=['datetime64']).columns.tolist()
        if not cols_fecha:
            st.error("El archivo no contiene una columna de fecha válida.")
            st.stop()

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

                # Variables de seguridad para no romper la lógica posterior
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
            df_b = pd.DataFrame() # Vacío para la vista simple
            label_b = ""
            
            st.markdown(f'<div class="periodo-header">📌 Periodo Analizado: [{label_a}]</div>', unsafe_allow_html=True)
            
            df_a['Periodo'] = label_a
            df_dual = df_a.copy()

        col_sort_tabla = label_b if modo == "Comparativa (A vs B)" else label_a
        col_prod = next((c for c in ['Detalle', 'Producto', 'Descripción', 'Articulo', 'Nombre Artículo', 'Material', 'Desc. Artículo', 'Item'] if c in df_dual.columns), None)

        if not df_a.empty or (modo == "Comparativa (A vs B)" and not df_b.empty):
            
            # =====================================================================
            # DECLARACIÓN DE PESTAÑAS
            # =====================================================================
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
                # --- KPIS ---
                if modo == "Comparativa (A vs B)":
                    st.markdown(f'<div class="sub-seccion">🔵 Indicadores Clave: {label_a} (Periodo Base)</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="sub-seccion">🔵 Indicadores Clave: {label_a}</div>', unsafe_allow_html=True)
                    
                kpi_a1, kpi_a2, kpi_a3, kpi_a4 = st.columns(4)
                
                v_a = df_a['Total Línea'].sum() if 'Total Línea' in df_a.columns else 0
                k_a = df_a['Kilos'].sum() if 'Kilos' in df_a.columns else 0
                t_a = df_a['Total Línea'].mean() if 'Total Línea' in df_a.columns else 0
                c_a = df_a['Cod Cliente'].nunique() if 'Cod Cliente' in df_a.columns else 0

                kpi_a1.metric("Venta Total (A)" if modo == "Comparativa (A vs B)" else "Venta Total", f"${v_a:,.0f} CLP")
                kpi_a2.metric("Volumen Kilos (A)" if modo == "Comparativa (A vs B)" else "Volumen Kilos", f"{k_a:,.0f} kg")
                kpi_a3.metric("Ticket Promedio (A)" if modo == "Comparativa (A vs B)" else "Ticket Promedio", f"${t_a:,.0f} CLP")
                kpi_a4.metric("Clientes Activos (A)" if modo == "Comparativa (A vs B)" else "Clientes Activos", f"{c_a:,}")

                if modo == "Comparativa (A vs B)":
                    st.markdown(f'<div class="sub-seccion">🟠 Indicadores Clave: {label_b} (Periodo Comparativo)</div>', unsafe_allow_html=True)
                    kpi_b1, kpi_b2, kpi_b3, kpi_b4 = st.columns(4)
                    
                    v_b = df_b['Total Línea'].sum() if 'Total Línea' in df_b.columns else 0
                    k_b = df_b['Kilos'].sum() if 'Kilos' in df_b.columns else 0
                    t_b = df_b['Total Línea'].mean() if 'Total Línea' in df_b.columns else 0
                    c_b = df_b['Cod Cliente'].nunique() if 'Cod Cliente' in df_b.columns else 0

                    d_v = ((v_b - v_a) / v_a * 100) if v_a > 0 else 0
                    d_k = ((k_b - k_a) / k_a * 100) if k_a > 0 else 0
                    d_t = ((t_b - t_a) / t_a * 100) if t_a > 0 else 0
                    d_c = ((c_b - c_a) / c_a * 100) if c_a > 0 else 0

                    kpi_b1.metric("Venta Total (B)", f"${v_b:,.0f} CLP", f"{d_v:+.1f}% vs A")
                    kpi_b2.metric("Volumen Kilos (B)", f"{k_b:,.0f} kg", f"{d_k:+.1f}% vs A")
                    kpi_b3.metric("Ticket Promedio (B)", f"${t_b:,.0f} CLP", f"{d_t:+.1f}% vs A")
                    kpi_b4.metric("Clientes Activos (B)", f"{c_b:,}", f"{d_c:+.1f}% vs A")

                st.divider()

                col_dash1, col_dash2 = st.columns(2)
                
                with col_dash1:
                    st.subheader("🗺️ Rendimiento Comercial por Zona")
                    if 'Zona' in df_dual.columns and 'Total Línea' in df_dual.columns:
                        df_zona = df_dual.groupby(['Zona', 'Periodo'], as_index=False)['Total Línea'].sum()
                        fig_zona = px.bar(df_zona, x='Zona', y='Total Línea', color='Periodo', barmode='group', template="plotly_dark",
                                          labels={'Total Línea': 'Venta ($ CLP)', 'Zona': 'Zona'},
                                          color_discrete_sequence=['#d97706', '#38bdf8'])
                        fig_zona.update_layout(yaxis_tickprefix="$", yaxis_tickformat=",.", height=450)
                        st.plotly_chart(fig_zona, width='stretch')
                        if st.button("🔍 Ampliar Gráfico de Zonas", key="btn_zona"):
                            mostrar_grafico_modal(fig_zona)

                with col_dash2:
                    titulo_vend = "🏆 Rendimiento de Todos los Vendedores"
                    st.subheader(titulo_vend)
                    if 'Vendedor' in df_dual.columns and 'Total Línea' in df_dual.columns:
                        df_vend = df_dual.groupby(['Vendedor', 'Periodo'], as_index=False)['Total Línea'].sum()
                        fig_vend = px.bar(df_vend, x='Vendedor', y='Total Línea', color='Periodo', barmode='group', template="plotly_dark",
                                          labels={'Total Línea': 'Venta ($ CLP)'}, color_discrete_sequence=['#d97706', '#38bdf8'])
                        fig_vend.update_layout(xaxis={'categoryorder':'total descending'}, yaxis_tickprefix="$", yaxis_tickformat=",.", height=450)
                        st.plotly_chart(fig_vend, width='stretch')
                        if st.button("🔍 Ampliar Gráfico de Vendedores", key="btn_vend"):
                            mostrar_grafico_modal(fig_vend)

                st.divider()
                
                st.subheader("🥧 Participación Mix de Categorías")
                if 'Categoría' in df_dual.columns and 'Total Línea' in df_dual.columns:
                    df_cat = df_dual.groupby(['Categoría', 'Periodo'], as_index=False)['Total Línea'].sum()
                    fig_cat = px.bar(df_cat, x='Categoría', y='Total Línea', color='Periodo', barmode='group', template="plotly_dark",
                                     labels={'Total Línea': 'Venta ($ CLP)'}, color_discrete_sequence=['#d97706', '#38bdf8'])
                    fig_cat.update_layout(xaxis={'categoryorder':'total descending'}, yaxis_tickprefix="$", yaxis_tickformat=",.", height=450)
                    st.plotly_chart(fig_cat, width='stretch')
                    if st.button("🔍 Ampliar Gráfico de Categorías", key="btn_cat"):
                        mostrar_grafico_modal(fig_cat)

            # ---------------------------------------------------------------------
            # PESTAÑA 2: ANÁLISIS DE PRODUCTOS
            # ---------------------------------------------------------------------
            with tab2:
                st.subheader("🛍️ Top 20 Productos Más Vendidos")
                if col_prod and 'Total Línea' in df_dual.columns:
                    top_prods = df_dual.groupby(col_prod)['Total Línea'].sum().nlargest(20).index
                    df_prod = df_dual[df_dual[col_prod].isin(top_prods)].groupby([col_prod, 'Periodo'], as_index=False)['Total Línea'].sum()
                    
                    fig_prod = px.bar(df_prod, x='Total Línea', y=col_prod, color='Periodo', barmode='group', template="plotly_dark",
                                      orientation='h', labels={'Total Línea': 'Venta ($ CLP)', col_prod: 'Producto'},
                                      color_discrete_sequence=['#d97706', '#38bdf8'])
                    fig_prod.update_layout(yaxis={'categoryorder':'total ascending'}, xaxis_tickprefix="$", xaxis_tickformat=",.", height=600)
                    st.plotly_chart(fig_prod, width='stretch')
                    if st.button("🔍 Ampliar Gráfico Top 20 Productos", key="btn_prod"):
                        mostrar_grafico_modal(fig_prod, altura=850)
                else:
                    st.info("No se detectó la columna de Productos (Descripción/Articulo) en el archivo.")

                st.divider()

                st.subheader("🧑‍🤝‍🧑 Clientes por Producto")
                if col_prod and 'Nombre Cliente' in df_dual.columns and 'Total Línea' in df_dual.columns:
                    productos_disponibles = df_dual.groupby(col_prod)['Total Línea'].sum().sort_values(ascending=False).index.tolist()
                    producto_sel = st.selectbox("Selecciona un producto para ver qué clientes lo compraron", productos_disponibles, key='producto_cliente_sel')

                    df_prod_cli = df_dual[df_dual[col_prod] == producto_sel]
                    df_prod_cli_agg = df_prod_cli.groupby(['Nombre Cliente', 'Periodo'], as_index=False)['Total Línea'].sum()

                    top_clientes_prod = df_prod_cli_agg.groupby('Nombre Cliente')['Total Línea'].sum().nlargest(20).index
                    df_prod_cli_agg = df_prod_cli_agg[df_prod_cli_agg['Nombre Cliente'].isin(top_clientes_prod)]

                    if not df_prod_cli_agg.empty:
                        fig_prod_cli = px.bar(
                            df_prod_cli_agg, x='Total Línea', y='Nombre Cliente', color='Periodo', barmode='group',
                            orientation='h', template="plotly_dark",
                            labels={'Total Línea': 'Venta ($ CLP)', 'Nombre Cliente': 'Cliente'},
                            color_discrete_sequence=['#d97706', '#38bdf8']
                        )
                        fig_prod_cli.update_layout(yaxis={'categoryorder': 'total ascending'}, xaxis_tickprefix="$", xaxis_tickformat=",.", height=550)
                        st.plotly_chart(fig_prod_cli, width='stretch')
                        if st.button("🔍 Ampliar Gráfico de Clientes por Producto", key="btn_cli_prod"):
                            mostrar_grafico_modal(fig_prod_cli)
                    else:
                        st.info("No hay clientes registrados para este producto en el periodo seleccionado.")
                else:
                    st.info("No se detectó columna de Cliente o Producto para generar este gráfico.")

            # ---------------------------------------------------------------------
            # PESTAÑA 3: ANÁLISIS DE CLIENTES
            # ---------------------------------------------------------------------
            with tab3:
                st.subheader("🔄 Clientes Nuevos y Perdidos")
                if modo == "Comparativa (A vs B)":
                    if 'Nombre Cliente' in df_a.columns and 'Nombre Cliente' in df_b.columns:
                        clientes_a_set = set(df_a['Nombre Cliente'].dropna().unique())
                        clientes_b_set = set(df_b['Nombre Cliente'].dropna().unique())

                        clientes_nuevos = clientes_b_set - clientes_a_set
                        clientes_perdidos = clientes_a_set - clientes_b_set
                        clientes_retenidos = clientes_a_set & clientes_b_set

                        m1, m2, m3 = st.columns(3)
                        m1.metric("🟢 Clientes Nuevos", f"{len(clientes_nuevos):,}")
                        m2.metric("🔴 Clientes Perdidos", f"{len(clientes_perdidos):,}")
                        m3.metric("🔵 Clientes Retenidos", f"{len(clientes_retenidos):,}")

                        with st.expander("Ver lista de Clientes Nuevos y Perdidos", expanded=False):
                            col_nuevos, col_perdidos = st.columns(2)

                            with col_nuevos:
                                st.markdown(f"##### 🟢 Nuevos en {label_b} (no compraron en {label_a})")
                                if clientes_nuevos:
                                    agg_dict = {f'Venta {label_b}': ('Total Línea', 'sum')}
                                    if 'Kilos' in df_b.columns:
                                        agg_dict[f'Kilos {label_b}'] = ('Kilos', 'sum')
                                    df_nuevos = df_b[df_b['Nombre Cliente'].isin(clientes_nuevos)].groupby('Nombre Cliente', as_index=False).agg(**agg_dict)
                                    df_nuevos = df_nuevos.sort_values(f'Venta {label_b}', ascending=False)
                                    formato = {f'Venta {label_b}': '${:,.0f}'}
                                    if f'Kilos {label_b}' in df_nuevos.columns:
                                        formato[f'Kilos {label_b}'] = '{:,.0f}'
                                    st.dataframe(df_nuevos.style.format(formato), width='stretch', hide_index=True)
                                else:
                                    st.caption("No hay clientes nuevos en este periodo.")

                            with col_perdidos:
                                st.markdown(f"##### 🔴 Perdidos de {label_a} (no compraron en {label_b})")
                                if clientes_perdidos:
                                    agg_dict = {f'Venta {label_a}': ('Total Línea', 'sum')}
                                    if 'Kilos' in df_a.columns:
                                        agg_dict[f'Kilos {label_a}'] = ('Kilos', 'sum')
                                    df_perdidos = df_a[df_a['Nombre Cliente'].isin(clientes_perdidos)].groupby('Nombre Cliente', as_index=False).agg(**agg_dict)
                                    df_perdidos = df_perdidos.sort_values(f'Venta {label_a}', ascending=False)
                                    formato = {f'Venta {label_a}': '${:,.0f}'}
                                    if f'Kilos {label_a}' in df_perdidos.columns:
                                        formato[f'Kilos {label_a}'] = '{:,.0f}'
                                    st.dataframe(df_perdidos.style.format(formato), width='stretch', hide_index=True)
                                else:
                                    st.caption("No hay clientes perdidos en este periodo.")
                    else:
                        st.info("No se detectó la columna 'Nombre Cliente' para calcular clientes nuevos/perdidos.")
                else:
                    st.info("El análisis de Clientes Nuevos/Perdidos solo está disponible en modo Comparativa (A vs B).")

                st.divider()

                st.subheader("👥 Top 20 Clientes con Mayor Venta")
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

                    df_cli_plot = df_dual[df_dual['Nombre Cliente'].isin(top20_cli['Nombre Cliente'])]
                    df_cli_plot = df_cli_plot.groupby(['Nombre Cliente', 'Periodo'], as_index=False)['Total Línea'].sum()
                    orden_clientes = top20_cli.sort_values('Venta Total', ascending=True)['Nombre Cliente'].tolist()
                    
                    fig_cli = px.bar(
                        df_cli_plot, y='Nombre Cliente', x='Total Línea', color='Periodo', barmode='group',
                        orientation='h', template="plotly_dark",
                        category_orders={'Nombre Cliente': orden_clientes},
                        labels={'Total Línea': 'Venta ($ CLP)', 'Nombre Cliente': 'Cliente'},
                        color_discrete_sequence=['#d97706', '#38bdf8']
                    )
                    fig_cli.update_layout(height=650, xaxis_tickprefix="$", xaxis_tickformat=",.")
                    st.plotly_chart(fig_cli, width='stretch')
                    if st.button("🔍 Ampliar Gráfico Top 20 Clientes", key="btn_top_cli"):
                        mostrar_grafico_modal(fig_cli, altura=850)

            # ---------------------------------------------------------------------
            # PESTAÑA 4: DATOS Y RESÚMENES (TABLAS)
            # ---------------------------------------------------------------------
            with tab4:
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

                st.divider()

                col_tab1, col_tab2 = st.columns(2)
                with col_tab1:
                    st.subheader("🛍️ Datos: Top 20 Productos")
                    if col_prod and 'Total Línea' in df_dual.columns:
                        tabla_prod = df_prod.pivot(index=col_prod, columns='Periodo', values='Total Línea').fillna(0)
                        if col_sort_tabla in tabla_prod.columns:
                            tabla_prod = tabla_prod.sort_values(by=col_sort_tabla, ascending=False)
                        st.dataframe(tabla_prod.style.format("${:,.0f}"), use_container_width=True)

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
                        else:
                            st.dataframe(
                                top20_cli.drop(columns=['Venta Total']).style.format({
                                    f'Venta {label_a}': '${:,.0f}',
                                    f'Kilos {label_a}': '{:,.0f}'
                                }),
                                width='stretch', hide_index=True
                            )

                st.divider()
                
                titulo_tabla_final = "📂 Inspeccionar Tabla Consolidada (Base de Datos Procesada)"
                st.subheader(titulo_tabla_final)
                df_vista = df_dual.copy()
                for col in df_vista.select_dtypes(include=['object']).columns:
                    df_vista[col] = df_vista[col].astype(str)

                busqueda = st.text_input("🔎 Buscar por RUT (Cod Cliente), Nombre Cliente o Zona", key="busqueda_tabla")
                if busqueda:
                    q = busqueda.strip().lower()
                    cols_busqueda = [c for c in ['Cod Cliente', 'Nombre Cliente', 'Zona'] if c in df_vista.columns]
                    mascara = pd.Series(False, index=df_vista.index)
                    for c in cols_busqueda:
                        mascara |= df_vista[c].str.lower().str.contains(q, na=False)
                    df_vista = df_vista[mascara]
                    st.caption(f"{len(df_vista):,} filas encontradas")

                st.dataframe(df_vista, width='stretch')

        else:
            st.warning("No se encontraron registros para los periodos seleccionados.")

    except Exception as e:
        st.error(f"Error crítico en el motor de comparación: {e}")