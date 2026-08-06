"""Pestaña 3: Análisis de Clientes — cartera por vendedor, nuevos/perdidos, top 20."""

import pandas as pd
import streamlit as st
import plotly.express as px

from utils import calcular_kpis, generar_excel_bonito
import theme


def render(df_a, df_b, df_dual, modo, label_a, label_b, color_map):
    theme.section_title("👤 Filtro de Vendedor (Aplica a toda esta pestaña)")

    if 'Vendedor' in df_dual.columns:
        vendedores_disp = sorted(df_dual['Vendedor'].dropna().astype(str).unique().tolist())
        opciones_v3 = ["Todos"] + vendedores_disp
        idx_v3 = opciones_v3.index(st.session_state.mem_vend_t3) if st.session_state.mem_vend_t3 in opciones_v3 else 0

        filtro_vendedor = st.selectbox(
            "Selecciona un vendedor para analizar exclusivamente su cartera de clientes:",
            opciones_v3, index=idx_v3, key="widget_vend_t3"
        )
        st.session_state.mem_vend_t3 = filtro_vendedor

        if filtro_vendedor == "Todos":
            df_a_t3, df_b_t3, df_dual_t3 = df_a.copy(), (df_b.copy() if not df_b.empty else pd.DataFrame()), df_dual.copy()
        else:
            df_a_t3 = df_a[df_a['Vendedor'].astype(str) == filtro_vendedor].copy()
            df_b_t3 = df_b[df_b['Vendedor'].astype(str) == filtro_vendedor].copy() if not df_b.empty else pd.DataFrame()
            df_dual_t3 = df_dual[df_dual['Vendedor'].astype(str) == filtro_vendedor].copy()
    else:
        df_a_t3, df_b_t3, df_dual_t3 = df_a.copy(), (df_b.copy() if not df_b.empty else pd.DataFrame()), df_dual.copy()

    theme.ledger_tape(compacta=True)

    kpis_a_vend = calcular_kpis(df_a_t3)

    if modo == "Comparativa (A vs B)":
        theme.section_title(f"🟠 Indicadores del Vendedor: {label_a} (Periodo Base)")
        theme.kpi_row([
            {"label": "Venta Total (A)", "valor": f"${kpis_a_vend['venta']:,.0f} CLP"},
            {"label": "Volumen Kilos (A)", "valor": f"{kpis_a_vend['kilos']:,.0f} kg"},
            {"label": "Ticket Promedio (A)", "valor": f"${kpis_a_vend['ticket']:,.0f} CLP"},
            {"label": "Clientes Activos (A)", "valor": f"{kpis_a_vend['clientes']:,}"},
        ])

        kpis_b_vend = calcular_kpis(df_b_t3)

        d_v = ((kpis_b_vend['venta'] - kpis_a_vend['venta']) / kpis_a_vend['venta'] * 100) if kpis_a_vend['venta'] > 0 else 0
        d_k = ((kpis_b_vend['kilos'] - kpis_a_vend['kilos']) / kpis_a_vend['kilos'] * 100) if kpis_a_vend['kilos'] > 0 else 0
        d_t = ((kpis_b_vend['ticket'] - kpis_a_vend['ticket']) / kpis_a_vend['ticket'] * 100) if kpis_a_vend['ticket'] > 0 else 0
        d_c = ((kpis_b_vend['clientes'] - kpis_a_vend['clientes']) / kpis_a_vend['clientes'] * 100) if kpis_a_vend['clientes'] > 0 else 0

        theme.section_title(f"🟢 Indicadores del Vendedor: {label_b} (Periodo Comparativo)")
        theme.kpi_row([
            {"label": "Venta Total (B)", "valor": f"${kpis_b_vend['venta']:,.0f} CLP", "delta": f"{d_v:+.1f}% vs A", "signo": theme.signo_delta(d_v)},
            {"label": "Volumen Kilos (B)", "valor": f"{kpis_b_vend['kilos']:,.0f} kg", "delta": f"{d_k:+.1f}% vs A", "signo": theme.signo_delta(d_k)},
            {"label": "Ticket Promedio (B)", "valor": f"${kpis_b_vend['ticket']:,.0f} CLP", "delta": f"{d_t:+.1f}% vs A", "signo": theme.signo_delta(d_t)},
            {"label": "Clientes Activos (B)", "valor": f"{kpis_b_vend['clientes']:,}", "delta": f"{d_c:+.1f}% vs A", "signo": theme.signo_delta(d_c)},
        ])
    else:
        theme.section_title(f"🔵 Indicadores del Vendedor: {label_a}")
        theme.kpi_row([
            {"label": "Venta Total", "valor": f"${kpis_a_vend['venta']:,.0f} CLP"},
            {"label": "Volumen Kilos", "valor": f"{kpis_a_vend['kilos']:,.0f} kg"},
            {"label": "Ticket Promedio", "valor": f"${kpis_a_vend['ticket']:,.0f} CLP"},
            {"label": "Clientes Activos", "valor": f"{kpis_a_vend['clientes']:,}"},
        ])

    theme.ledger_tape(compacta=True)
    _seccion_nuevos_y_perdidos(df_a_t3, df_b_t3, modo, label_a, label_b)

    st.divider()
    _seccion_top20_clientes(df_a_t3, df_b_t3, df_dual_t3, modo, label_a, label_b, color_map)


def _seccion_nuevos_y_perdidos(df_a_t3, df_b_t3, modo, label_a, label_b):
    st.subheader("🔄 Clientes Nuevos y Perdidos")
    if modo != "Comparativa (A vs B)":
        st.info("El análisis de Clientes Nuevos/Perdidos solo está disponible en modo Comparativa (A vs B).")
        return

    st.caption("Compara la cartera de clientes entre el Periodo A y el Periodo B configurados en la parte superior.")
    if 'Nombre Cliente' not in df_a_t3.columns or 'Nombre Cliente' not in df_b_t3.columns:
        st.info("No se detectó la columna 'Nombre Cliente' para calcular clientes nuevos/perdidos.")
        return

    clientes_a = set(df_a_t3['Nombre Cliente'].dropna().unique())
    clientes_b = set(df_b_t3['Nombre Cliente'].dropna().unique())
    nuevos, perdidos, retenidos = clientes_b - clientes_a, clientes_a - clientes_b, clientes_a & clientes_b

    m1, m2, m3 = st.columns(3)
    m1.metric("🟢 Clientes Nuevos", f"{len(nuevos):,}")
    m2.metric("🔴 Clientes Perdidos", f"{len(perdidos):,}")
    m3.metric("🔵 Clientes Retenidos", f"{len(retenidos):,}")

    with st.expander("Ver lista de Clientes Nuevos y Perdidos", expanded=False):
        col_nuevos, col_perdidos = st.columns(2)
        df_nuevos = pd.DataFrame(columns=['Cod Cliente', 'Nombre Cliente', 'Vendedor', f'Venta {label_b}', f'Kilos {label_b}'])
        df_perdidos = pd.DataFrame(columns=['Cod Cliente', 'Nombre Cliente', 'Vendedor', f'Venta {label_a}', f'Kilos {label_a}'])

        with col_nuevos:
            st.markdown(f"##### 🟢 Nuevos en {label_b}")
            if nuevos:
                agg = {f'Venta {label_b}': ('Total Línea', 'sum')}
                if 'Cod Cliente' in df_b_t3.columns:
                    agg['Cod Cliente'] = ('Cod Cliente', 'first')
                if 'Vendedor' in df_b_t3.columns:
                    agg['Vendedor'] = ('Vendedor', 'first')
                if 'Kilos' in df_b_t3.columns:
                    agg[f'Kilos {label_b}'] = ('Kilos', 'sum')

                df_nuevos = df_b_t3[df_b_t3['Nombre Cliente'].isin(nuevos)].groupby('Nombre Cliente', as_index=False).agg(**agg)
                df_nuevos = df_nuevos.sort_values(f'Venta {label_b}', ascending=False)
                cols = ['Cod Cliente', 'Nombre Cliente', 'Vendedor', f'Venta {label_b}', f'Kilos {label_b}']
                df_nuevos = df_nuevos[[c for c in cols if c in df_nuevos.columns]]

                formato = {f'Venta {label_b}': '${:,.0f}'}
                if f'Kilos {label_b}' in df_nuevos.columns:
                    formato[f'Kilos {label_b}'] = '{:,.0f}'
                st.dataframe(df_nuevos.style.format(formato), width='stretch', hide_index=True)
            else:
                st.caption("No hay clientes nuevos en este periodo.")

        with col_perdidos:
            st.markdown(f"##### 🔴 Perdidos de {label_a}")
            if perdidos:
                agg = {f'Venta {label_a}': ('Total Línea', 'sum')}
                if 'Cod Cliente' in df_a_t3.columns:
                    agg['Cod Cliente'] = ('Cod Cliente', 'first')
                if 'Vendedor' in df_a_t3.columns:
                    agg['Vendedor'] = ('Vendedor', 'first')
                if 'Kilos' in df_a_t3.columns:
                    agg[f'Kilos {label_a}'] = ('Kilos', 'sum')

                df_perdidos = df_a_t3[df_a_t3['Nombre Cliente'].isin(perdidos)].groupby('Nombre Cliente', as_index=False).agg(**agg)
                df_perdidos = df_perdidos.sort_values(f'Venta {label_a}', ascending=False)
                cols = ['Cod Cliente', 'Nombre Cliente', 'Vendedor', f'Venta {label_a}', f'Kilos {label_a}']
                df_perdidos = df_perdidos[[c for c in cols if c in df_perdidos.columns]]

                formato = {f'Venta {label_a}': '${:,.0f}'}
                if f'Kilos {label_a}' in df_perdidos.columns:
                    formato[f'Kilos {label_a}'] = '{:,.0f}'
                st.dataframe(df_perdidos.style.format(formato), width='stretch', hide_index=True)
            else:
                st.caption("No hay clientes perdidos en este periodo.")

        st.divider()
        excel_bytes = generar_excel_bonito({
            'Clientes Nuevos': (df_nuevos, {f'Venta {label_b}': 'moneda', f'Kilos {label_b}': 'kilos'}),
            'Clientes Perdidos': (df_perdidos, {f'Venta {label_a}': 'moneda', f'Kilos {label_a}': 'kilos'}),
        })
        st.download_button(
            "📥 Descargar Excel (Nuevos y Perdidos)", data=excel_bytes,
            file_name="clientes_nuevos_perdidos.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="descarga_nuevos_perdidos", width='stretch'
        )


def _seccion_top20_clientes(df_a_t3, df_b_t3, df_dual_t3, modo, label_a, label_b, color_map):
    st.subheader("👥 Top 20 Clientes con Mayor Venta")
    if 'Nombre Cliente' not in df_a_t3.columns or 'Total Línea' not in df_a_t3.columns:
        return

    cli_a = df_a_t3.groupby('Nombre Cliente', as_index=False).agg(**{
        f'Venta {label_a}': ('Total Línea', 'sum'), f'Kilos {label_a}': ('Kilos', 'sum')
    })

    if modo == "Comparativa (A vs B)":
        cli_b = df_b_t3.groupby('Nombre Cliente', as_index=False).agg(**{
            f'Venta {label_b}': ('Total Línea', 'sum'), f'Kilos {label_b}': ('Kilos', 'sum')
        })
        resumen = pd.merge(cli_a, cli_b, on='Nombre Cliente', how='outer').fillna(0)
        resumen['Venta Total'] = resumen[f'Venta {label_a}'] + resumen[f'Venta {label_b}']
        top20 = resumen.sort_values('Venta Total', ascending=False).head(20)
    else:
        cli_a['Venta Total'] = cli_a[f'Venta {label_a}']
        top20 = cli_a.sort_values('Venta Total', ascending=False).head(20)

    df_plot = df_dual_t3[df_dual_t3['Nombre Cliente'].isin(top20['Nombre Cliente'])]
    df_plot = df_plot.groupby(['Nombre Cliente', 'Periodo'], as_index=False)['Total Línea'].sum()
    orden = top20.sort_values('Venta Total', ascending=True)['Nombre Cliente'].tolist()

    if df_plot.empty:
        st.info("No hay ventas registradas para generar el gráfico de clientes.")
        return

    fig = px.bar(
        df_plot, y='Nombre Cliente', x='Total Línea', color='Periodo', barmode='group',
        orientation='h',
        category_orders={'Nombre Cliente': orden},
        labels={'Total Línea': 'Venta ($ CLP)', 'Nombre Cliente': 'Cliente'},
        color_discrete_map=color_map
    )
    fig.update_layout(**theme.plotly_layout_kwargs(), height=650, xaxis_tickprefix="$", xaxis_tickformat=",.")
    st.plotly_chart(fig, width='stretch', theme=None)

    excel_top = generar_excel_bonito({'Top20_Clientes': (df_plot, {'Total Línea': 'moneda'})})
    st.download_button("📥 Descargar Datos Excel", excel_top, "grafico_top20_clientes.xlsx", key="dl_top_cli", width='stretch')