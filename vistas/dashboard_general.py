"""Pestaña 1: Dashboard General — KPIs globales + gráficos por Zona, Vendedor y Categoría."""

import pandas as pd
import streamlit as st
import plotly.express as px

from utils import calcular_kpis, generar_excel_bonito
import theme
import plan_ventas

MESES_MAP = {1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
             7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'}


def render(df_a, df_b, df_dual, modo, label_a, label_b, color_map, df_completo):
    v_a = df_a['Total Línea'].sum() if 'Total Línea' in df_a.columns else 0
    k_a = df_a['Kilos'].sum() if 'Kilos' in df_a.columns else 0
    kpis_a = calcular_kpis(df_a)

    if modo == "Comparativa (A vs B)":
        theme.section_title(f"🟠 Indicadores Clave: {label_a} (Periodo Base)")
        theme.kpi_row([
            {"label": "Venta Total (A)", "valor": f"${v_a:,.0f} CLP"},
            {"label": "Volumen Kilos (A)", "valor": f"{k_a:,.0f} kg"},
            {"label": "Ticket Promedio (A)", "valor": f"${kpis_a['ticket']:,.0f} CLP"},
            {"label": "Clientes Activos (A)", "valor": f"{kpis_a['clientes']:,}"},
        ])

        v_b = df_b['Total Línea'].sum() if 'Total Línea' in df_b.columns else 0
        k_b = df_b['Kilos'].sum() if 'Kilos' in df_b.columns else 0
        kpis_b = calcular_kpis(df_b)

        d_v = ((v_b - v_a) / v_a * 100) if v_a > 0 else 0
        d_k = ((k_b - k_a) / k_a * 100) if k_a > 0 else 0
        d_t = ((kpis_b['ticket'] - kpis_a['ticket']) / kpis_a['ticket'] * 100) if kpis_a['ticket'] > 0 else 0
        d_c = ((kpis_b['clientes'] - kpis_a['clientes']) / kpis_a['clientes'] * 100) if kpis_a['clientes'] > 0 else 0

        theme.section_title(f"🟢 Indicadores Clave: {label_b} (Periodo Comparativo)")
        theme.kpi_row([
            {"label": "Venta Total (B)", "valor": f"${v_b:,.0f} CLP", "delta": f"{d_v:+.1f}% vs A", "signo": theme.signo_delta(d_v)},
            {"label": "Volumen Kilos (B)", "valor": f"{k_b:,.0f} kg", "delta": f"{d_k:+.1f}% vs A", "signo": theme.signo_delta(d_k)},
            {"label": "Ticket Promedio (B)", "valor": f"${kpis_b['ticket']:,.0f} CLP", "delta": f"{d_t:+.1f}% vs A", "signo": theme.signo_delta(d_t)},
            {"label": "Clientes Activos (B)", "valor": f"{kpis_b['clientes']:,}", "delta": f"{d_c:+.1f}% vs A", "signo": theme.signo_delta(d_c)},
        ])
    else:
        theme.section_title("🔵 Indicadores Clave")
        theme.kpi_row([
            {"label": "Venta Total", "valor": f"${v_a:,.0f} CLP"},
            {"label": "Volumen Kilos", "valor": f"{k_a:,.0f} kg"},
            {"label": "Ticket Promedio", "valor": f"${kpis_a['ticket']:,.0f} CLP"},
            {"label": "Clientes Activos", "valor": f"{kpis_a['clientes']:,}"},
        ])

    theme.ledger_tape(compacta=True)

    _seccion_plan_mensual(df_completo)

    theme.ledger_tape(compacta=True)

    _seccion_ventas_mensuales_por_anio(df_completo)

    st.divider()

    col_dash1, col_dash2 = st.columns(2)

    with col_dash1:
        st.subheader("🗺️ Rendimiento Comercial por Zona")
        if 'Zona' in df_dual.columns and 'Total Línea' in df_dual.columns:
            df_zona = df_dual.groupby(['Zona', 'Periodo'], as_index=False)['Total Línea'].sum()
            fig_zona = px.bar(df_zona, x='Zona', y='Total Línea', color='Periodo', barmode='group',
                              labels={'Total Línea': 'Venta ($ CLP)', 'Zona': 'Zona'},
                              color_discrete_map=color_map)
            fig_zona.update_layout(**theme.plotly_layout_kwargs(), yaxis_tickprefix="$", yaxis_tickformat=",.", height=450)
            st.plotly_chart(fig_zona, width='stretch', theme=None)

            excel_zona = generar_excel_bonito({'Zonas': (df_zona, {'Total Línea': 'moneda'})})
            st.download_button("📥 Descargar Datos Excel", excel_zona, "grafico_zonas.xlsx", key="dl_zona", width='stretch')

    with col_dash2:
        st.subheader("🏆 Rendimiento de Todos los Vendedores")
        if 'Vendedor' in df_dual.columns and 'Total Línea' in df_dual.columns:
            df_vend = df_dual.groupby(['Vendedor', 'Periodo'], as_index=False)['Total Línea'].sum()
            fig_vend = px.bar(df_vend, x='Vendedor', y='Total Línea', color='Periodo', barmode='group',
                              labels={'Total Línea': 'Venta ($ CLP)'}, color_discrete_map=color_map)
            layout_vend = theme.plotly_layout_kwargs()
            layout_vend['xaxis'] = {**layout_vend['xaxis'], 'categoryorder': 'total descending'}
            fig_vend.update_layout(**layout_vend, yaxis_tickprefix="$", yaxis_tickformat=",.", height=450)
            st.plotly_chart(fig_vend, width='stretch', theme=None)

            excel_vend = generar_excel_bonito({'Vendedores': (df_vend, {'Total Línea': 'moneda'})})
            st.download_button("📥 Descargar Datos Excel", excel_vend, "grafico_vendedores.xlsx", key="dl_vend", width='stretch')

    st.divider()

    st.subheader("🥧 Participación Mix de Categorías")
    if 'Categoría' in df_dual.columns and 'Total Línea' in df_dual.columns:
        df_cat = df_dual.groupby(['Categoría', 'Periodo'], as_index=False)['Total Línea'].sum()
        fig_cat = px.bar(df_cat, x='Categoría', y='Total Línea', color='Periodo', barmode='group',
                         labels={'Total Línea': 'Venta ($ CLP)'}, color_discrete_map=color_map)
        layout_cat = theme.plotly_layout_kwargs()
        layout_cat['xaxis'] = {**layout_cat['xaxis'], 'categoryorder': 'total descending'}
        fig_cat.update_layout(**layout_cat, yaxis_tickprefix="$", yaxis_tickformat=",.", height=450)
        st.plotly_chart(fig_cat, width='stretch', theme=None)

        excel_cat = generar_excel_bonito({'Categorías': (df_cat, {'Total Línea': 'moneda'})})
        st.download_button("📥 Descargar Datos Excel", excel_cat, "grafico_categorias.xlsx", key="dl_cat", width='stretch')


def _seccion_plan_mensual(df: pd.DataFrame):
    if 'Vendedor' not in df.columns or 'Fecha' not in df.columns or 'Total Línea' not in df.columns:
        return

    fecha_ref = df['Fecha'].max().normalize()
    theme.section_title(f"🎯 Cumplimiento de Meta Mensual ({MESES_MAP[fecha_ref.month]} {fecha_ref.year})")

    _uploader_plan_mensual()

    plan = plan_ventas.cargar_plan()
    if plan.empty:
        st.info("Todavía no has subido un Plan de Ventas. Sube el Excel de metas mensuales arriba para activar esta sección.")
        return

    df_mes = df[(df['Año'] == fecha_ref.year) & (df['Mes_Num'] == fecha_ref.month)]

    # Ojo: antes esto cruzaba por ['Zona', 'Vendedor']. El problema es que
    # la Zona de un vendedor en el plan no siempre calza con la Zona que
    # trae ese mismo vendedor en las ventas de ese mes (typos, "RM" vs
    # "Región Metropolitana", una venta puntual registrada con otra zona,
    # etc.) — y cuando no calzan, el mismo vendedor termina en DOS filas:
    # una con su Meta pero sin Venta, y otra con su Venta pero sin Meta,
    # en vez de una sola fila con ambas cosas juntas. Por eso el cruce va
    # solo por Vendedor (normalizado: sin espacios extra, sin distinguir
    # mayúsculas/minúsculas); si un vendedor aparece más de una vez en el
    # plan (varias zonas) se suman sus metas, y la Zona que se muestra es
    # la del plan (o la de las ventas si no está en el plan).
    hay_zona = 'Zona' in plan.columns or ('Zona' in df_mes.columns)

    plan = plan.copy()
    plan['Vendedor'] = plan['Vendedor'].astype(str).str.strip()
    if 'Zona' in plan.columns:
        plan['Zona'] = plan['Zona'].astype(str).str.strip()
    plan['_vend_key'] = plan['Vendedor'].str.casefold()

    df_mes = df_mes.copy()
    df_mes['Vendedor'] = df_mes['Vendedor'].astype(str).str.strip()
    if 'Zona' in df_mes.columns:
        df_mes['Zona'] = df_mes['Zona'].astype(str).str.strip()
    df_mes['_vend_key'] = df_mes['Vendedor'].str.casefold()

    agg_plan = {'Meta': ('Meta', 'sum'), 'Vendedor': ('Vendedor', 'first')}
    if 'Zona' in plan.columns:
        agg_plan['Zona'] = ('Zona', 'first')
    plan_agg = plan.groupby('_vend_key', as_index=False).agg(**agg_plan)

    agg_venta = {'Venta': ('Total Línea', 'sum'), 'Vendedor': ('Vendedor', 'first')}
    if 'Zona' in df_mes.columns:
        agg_venta['Zona'] = ('Zona', 'first')
    venta_mes = df_mes.groupby('_vend_key', as_index=False).agg(**agg_venta)

    comparativo = pd.merge(plan_agg, venta_mes, on='_vend_key', how='outer', suffixes=('', '_venta'))
    comparativo['Vendedor'] = comparativo['Vendedor'].fillna(comparativo.pop('Vendedor_venta'))
    if 'Zona_venta' in comparativo.columns:
        if 'Zona' in comparativo.columns:
            comparativo['Zona'] = comparativo['Zona'].fillna(comparativo.pop('Zona_venta'))
        else:
            comparativo['Zona'] = comparativo.pop('Zona_venta')
    comparativo = comparativo.drop(columns=['_vend_key'])
    if not hay_zona:
        comparativo['Zona'] = comparativo.get('Zona', '')

    comparativo['Zona'] = comparativo['Zona'].fillna('Sin Zona')
    comparativo['Vendedor'] = comparativo['Vendedor'].fillna('Sin Vendedor')
    comparativo['Venta'] = comparativo['Venta'].fillna(0)
    comparativo['Meta'] = comparativo['Meta'].fillna(0)
    comparativo['% Cumplimiento'] = (comparativo['Venta'] / comparativo['Meta'] * 100).where(comparativo['Meta'] > 0, 0)
    comparativo = comparativo.sort_values('% Cumplimiento', ascending=False)

    total_meta = comparativo['Meta'].sum()
    total_venta = comparativo['Venta'].sum()
    pct_total = (total_venta / total_meta * 100) if total_meta > 0 else 0

    theme.kpi_row([
        {"label": "Meta Total del Mes", "valor": f"${total_meta:,.0f} CLP"},
        {"label": "Venta Acumulada del Mes", "valor": f"${total_venta:,.0f} CLP"},
        {"label": "Cumplimiento Global", "valor": f"{pct_total:,.1f}%", "signo": theme.signo_delta(pct_total - 100)},
    ])

    col_tabla, col_grafico = st.columns([1, 1])

    with col_tabla:
        tabla = comparativo[['Zona', 'Vendedor', 'Meta', 'Venta', '% Cumplimiento']]
        st.dataframe(
            tabla.style.format({'Meta': '${:,.0f}', 'Venta': '${:,.0f}', '% Cumplimiento': '{:,.1f}%'}),
            width='stretch', hide_index=True, height=380, key="tabla_plan_mensual"
        )

    with col_grafico:
        orden = comparativo.sort_values('% Cumplimiento', ascending=True)['Vendedor'].tolist()
        fig = px.bar(
            comparativo, y='Vendedor', x='% Cumplimiento', orientation='h',
            category_orders={'Vendedor': orden},
            labels={'% Cumplimiento': 'Cumplimiento (%)'},
            color_discrete_sequence=[theme.COLOR_ACCENT],
        )
        fig.add_vline(x=100, line_dash="dash", line_color=theme.COLOR_POSITIVE)
        fig.update_layout(**theme.plotly_layout_kwargs(), height=380, margin=dict(l=0, r=10, t=10, b=0))
        st.plotly_chart(fig, width='stretch', key="chart_plan_mensual", theme=None)

    excel_plan = generar_excel_bonito({'Cumplimiento Meta': (tabla, {'Meta': 'moneda', 'Venta': 'moneda', '% Cumplimiento': 'porcentaje'})})
    st.download_button(
        "📥 Descargar Excel", excel_plan, "cumplimiento_meta_mensual.xlsx",
        key="dl_plan_mensual", width='stretch'
    )


def _seccion_ventas_mensuales_por_anio(df: pd.DataFrame):
    if 'Año' not in df.columns or 'Mes_Num' not in df.columns or 'Total Línea' not in df.columns:
        return

    theme.section_title("📈 Ventas Mensuales por Año")

    df_mensual = df.groupby(['Año', 'Mes_Num'], as_index=False)['Total Línea'].sum()
    df_mensual['Mes'] = df_mensual['Mes_Num'].map(MESES_MAP)
    df_mensual['Año'] = df_mensual['Año'].astype(int).astype(str)
    orden_meses = list(MESES_MAP.values())

    paleta_anios = [theme.COLOR_PERIODO_A, theme.COLOR_PERIODO_B, theme.COLOR_ACCENT,
                    theme.COLOR_FOCUS, theme.COLOR_NEGATIVE, theme.COLOR_ACCENT_STRONG]
    anios_ordenados = sorted(df_mensual['Año'].unique().tolist())
    color_map_anios = {anio: paleta_anios[i % len(paleta_anios)] for i, anio in enumerate(anios_ordenados)}

    fig = px.bar(
        df_mensual, x='Mes', y='Total Línea', color='Año', barmode='group',
        category_orders={'Mes': orden_meses},
        labels={'Total Línea': 'Venta ($ CLP)', 'Mes': ''},
        color_discrete_map=color_map_anios,
    )
    fig.update_layout(**theme.plotly_layout_kwargs(), yaxis_tickprefix="$", yaxis_tickformat=",.", height=450)
    st.plotly_chart(fig, width='stretch', theme=None)

    excel_mensual = generar_excel_bonito({'Ventas Mensuales': (df_mensual[['Año', 'Mes', 'Total Línea']], {'Total Línea': 'moneda'})})
    st.download_button("📥 Descargar Datos Excel", excel_mensual, "ventas_mensuales_por_anio.xlsx", key="dl_ventas_mensuales", width='stretch')


def _uploader_plan_mensual():
    info = plan_ventas.info_plan()
    if info:
        st.caption(f"📌 Plan actual guardado el {info['actualizado'].strftime('%d-%m-%Y %H:%M')}. Solo hace falta volver a subirlo cuando cambie el plan del mes.")

    with st.expander("📋 Subir / Actualizar Plan de Ventas Mensual", expanded=not plan_ventas.existe_plan()):
        st.caption("Sube el Excel de metas por vendedor (columnas Zona, Vendedor, Ppto Tactico). Se guarda en la app y no hace falta volver a subirlo cada día — solo cuando cambie el plan del mes.")
        archivo_plan = st.file_uploader("Excel del Plan de Ventas", type=["xlsx", "xls"], key="uploader_plan_mensual")
        if archivo_plan is not None and st.button("💾 Guardar Plan", key="btn_guardar_plan"):
            plan_ventas.guardar_plan(archivo_plan)
            st.success("✅ Plan de Ventas guardado.")
            st.rerun()