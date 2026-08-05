"""Pestaña 5: Análisis de Vendedor — venta de hoy y de esta semana por vendedor.

A diferencia de las demás pestañas, esta NO usa el Periodo A/B configurado
arriba: siempre mira el día y la semana más recientes presentes en el
archivo subido, para dar una foto de control diario/semanal de cada
vendedor sin que el usuario tenga que tocar los filtros de periodo.
"""

import pandas as pd
import streamlit as st
import plotly.express as px

from utils import generar_excel_bonito
import theme

DIAS_SEMANA = {0: 'Lunes', 1: 'Martes', 2: 'Miércoles', 3: 'Jueves', 4: 'Viernes', 5: 'Sábado', 6: 'Domingo'}


def render(df: pd.DataFrame):
    if 'Vendedor' not in df.columns or 'Fecha' not in df.columns or 'Total Línea' not in df.columns:
        st.info("No se detectaron las columnas necesarias (Vendedor, Fecha, Total Línea) para este análisis.")
        return

    fecha_ref = df['Fecha'].max().normalize()
    inicio_semana = fecha_ref - pd.Timedelta(days=fecha_ref.weekday())

    df_hoy = df[df['Fecha'].dt.normalize() == fecha_ref]
    df_semana = df[(df['Fecha'].dt.normalize() >= inicio_semana) & (df['Fecha'].dt.normalize() <= fecha_ref)]

    theme.periodo_banner(
        f"Control de Vendedores — Hoy: {DIAS_SEMANA[fecha_ref.weekday()]} {fecha_ref.strftime('%d-%m-%Y')} · "
        f"Semana: {inicio_semana.strftime('%d-%m')} al {fecha_ref.strftime('%d-%m-%Y')}"
    )
    st.caption(
        "\"Hoy\" y \"esta semana\" se calculan a partir de la fecha más reciente que trae el archivo subido, "
        "no de la fecha del calendario del computador — así el control sigue siendo correcto aunque subas "
        "el archivo un día después."
    )

    theme.ledger_tape(compacta=True)

    theme.section_title(f"🔵 Venta de Hoy ({fecha_ref.strftime('%d-%m-%Y')})")
    _resumen_por_vendedor(df_hoy, sufijo="hoy")

    st.divider()

    theme.section_title(f"🟠 Venta de Esta Semana ({inicio_semana.strftime('%d-%m')} al {fecha_ref.strftime('%d-%m-%Y')})")
    _resumen_por_vendedor(df_semana, sufijo="semana")


def _resumen_por_vendedor(df_periodo: pd.DataFrame, sufijo: str):
    if df_periodo.empty:
        st.info("No hay ventas registradas en este periodo.")
        return

    venta_total = df_periodo['Total Línea'].sum()
    kilos_total = df_periodo['Kilos'].sum() if 'Kilos' in df_periodo.columns else 0
    clientes_total = df_periodo['Cod Cliente'].nunique() if 'Cod Cliente' in df_periodo.columns else 0
    vendedores_activos = df_periodo['Vendedor'].nunique()

    theme.kpi_row([
        {"label": "Venta Total", "valor": f"${venta_total:,.0f} CLP"},
        {"label": "Volumen Kilos", "valor": f"{kilos_total:,.0f} kg"},
        {"label": "Clientes Atendidos", "valor": f"{clientes_total:,}"},
        {"label": "Vendedores con Venta", "valor": f"{vendedores_activos:,}"},
    ])

    agg = {'Venta': ('Total Línea', 'sum')}
    if 'Kilos' in df_periodo.columns:
        agg['Kilos'] = ('Kilos', 'sum')
    if 'Cod Cliente' in df_periodo.columns:
        agg['Clientes'] = ('Cod Cliente', 'nunique')

    resumen = df_periodo.groupby('Vendedor', as_index=False).agg(**agg)
    resumen = resumen.sort_values('Venta', ascending=False)

    col_tabla, col_grafico = st.columns([1, 1])

    with col_tabla:
        formato = {'Venta': '${:,.0f}'}
        if 'Kilos' in resumen.columns:
            formato['Kilos'] = '{:,.0f}'
        st.dataframe(resumen.style.format(formato), width='stretch', hide_index=True, height=380, key=f"tabla_vend_{sufijo}")

    with col_grafico:
        orden = resumen.sort_values('Venta', ascending=True)['Vendedor'].tolist()
        fig = px.bar(
            resumen, y='Vendedor', x='Venta', orientation='h', template="plotly_dark",
            category_orders={'Vendedor': orden},
            labels={'Venta': 'Venta ($ CLP)'},
            color_discrete_sequence=[theme.COLOR_ACCENT],
        )
        fig.update_layout(height=380, xaxis_tickprefix="$", xaxis_tickformat=",.", margin=dict(l=0, r=10, t=10, b=0))
        st.plotly_chart(fig, width='stretch', key=f"chart_vend_{sufijo}")

    excel_bytes = generar_excel_bonito({'Vendedores': (resumen, {'Venta': 'moneda', 'Kilos': 'kilos'})})
    st.download_button(
        "📥 Descargar Excel", excel_bytes, f"venta_vendedores_{sufijo}.xlsx",
        key=f"dl_vend_{sufijo}", width='stretch'
    )
