"""Pestaña 1: Dashboard General — KPIs globales + gráficos por Zona, Vendedor y Categoría."""

import streamlit as st
import plotly.express as px

from utils import calcular_kpis, generar_excel_bonito
import theme


def render(df_a, df_b, df_dual, modo, label_a, label_b, color_map):
    theme.section_title(f"🔵 Indicadores Clave: {label_a}" + (" (Periodo Base)" if modo == "Comparativa (A vs B)" else ""))

    v_a = df_a['Total Línea'].sum() if 'Total Línea' in df_a.columns else 0
    k_a = df_a['Kilos'].sum() if 'Kilos' in df_a.columns else 0
    kpis_a = calcular_kpis(df_a)

    sufijo = " (A)" if modo == "Comparativa (A vs B)" else ""
    theme.kpi_row([
        {"label": f"Venta Total{sufijo}", "valor": f"${v_a:,.0f} CLP"},
        {"label": f"Volumen Kilos{sufijo}", "valor": f"{k_a:,.0f} kg"},
        {"label": f"Ticket Promedio{sufijo}", "valor": f"${kpis_a['ticket']:,.0f} CLP"},
        {"label": f"Clientes Activos{sufijo}", "valor": f"{kpis_a['clientes']:,}"},
    ])

    if modo == "Comparativa (A vs B)":
        theme.section_title(f"🟠 Indicadores Clave: {label_b} (Periodo Comparativo)")

        v_b = df_b['Total Línea'].sum() if 'Total Línea' in df_b.columns else 0
        k_b = df_b['Kilos'].sum() if 'Kilos' in df_b.columns else 0
        kpis_b = calcular_kpis(df_b)

        d_v = ((v_b - v_a) / v_a * 100) if v_a > 0 else 0
        d_k = ((k_b - k_a) / k_a * 100) if k_a > 0 else 0
        d_t = ((kpis_b['ticket'] - kpis_a['ticket']) / kpis_a['ticket'] * 100) if kpis_a['ticket'] > 0 else 0
        d_c = ((kpis_b['clientes'] - kpis_a['clientes']) / kpis_a['clientes'] * 100) if kpis_a['clientes'] > 0 else 0

        theme.kpi_row([
            {"label": "Venta Total (B)", "valor": f"${v_b:,.0f} CLP", "delta": f"{d_v:+.1f}% vs A", "signo": theme.signo_delta(d_v)},
            {"label": "Volumen Kilos (B)", "valor": f"{k_b:,.0f} kg", "delta": f"{d_k:+.1f}% vs A", "signo": theme.signo_delta(d_k)},
            {"label": "Ticket Promedio (B)", "valor": f"${kpis_b['ticket']:,.0f} CLP", "delta": f"{d_t:+.1f}% vs A", "signo": theme.signo_delta(d_t)},
            {"label": "Clientes Activos (B)", "valor": f"{kpis_b['clientes']:,}", "delta": f"{d_c:+.1f}% vs A", "signo": theme.signo_delta(d_c)},
        ])

    theme.ledger_tape(compacta=True)

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
        st.subheader("🏆 Rendimiento de Todos los Vendedores")
        if 'Vendedor' in df_dual.columns and 'Total Línea' in df_dual.columns:
            df_vend = df_dual.groupby(['Vendedor', 'Periodo'], as_index=False)['Total Línea'].sum()
            fig_vend = px.bar(df_vend, x='Vendedor', y='Total Línea', color='Periodo', barmode='group', template="plotly_dark",
                              labels={'Total Línea': 'Venta ($ CLP)'}, color_discrete_map=color_map)
            fig_vend.update_layout(xaxis={'categoryorder': 'total descending'}, yaxis_tickprefix="$", yaxis_tickformat=",.", height=450)
            st.plotly_chart(fig_vend, width='stretch')

            excel_vend = generar_excel_bonito({'Vendedores': (df_vend, {'Total Línea': 'moneda'})})
            st.download_button("📥 Descargar Datos Excel", excel_vend, "grafico_vendedores.xlsx", key="dl_vend", width='stretch')

    st.divider()

    st.subheader("🥧 Participación Mix de Categorías")
    if 'Categoría' in df_dual.columns and 'Total Línea' in df_dual.columns:
        df_cat = df_dual.groupby(['Categoría', 'Periodo'], as_index=False)['Total Línea'].sum()
        fig_cat = px.bar(df_cat, x='Categoría', y='Total Línea', color='Periodo', barmode='group', template="plotly_dark",
                         labels={'Total Línea': 'Venta ($ CLP)'}, color_discrete_map=color_map)
        fig_cat.update_layout(xaxis={'categoryorder': 'total descending'}, yaxis_tickprefix="$", yaxis_tickformat=",.", height=450)
        st.plotly_chart(fig_cat, width='stretch')

        excel_cat = generar_excel_bonito({'Categorías': (df_cat, {'Total Línea': 'moneda'})})
        st.download_button("📥 Descargar Datos Excel", excel_cat, "grafico_categorias.xlsx", key="dl_cat", width='stretch')