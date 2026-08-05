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
import plan_ventas

MESES_MAP = {1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
             7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'}

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

    st.divider()

    theme.section_title(f"🎯 Cumplimiento de Meta Mensual ({MESES_MAP[fecha_ref.month]} {fecha_ref.year})")
    _seccion_plan_mensual(df, fecha_ref)


def _seccion_plan_mensual(df: pd.DataFrame, fecha_ref: pd.Timestamp):
    _uploader_plan_mensual()

    plan = plan_ventas.cargar_plan()
    if plan.empty:
        st.info("Todavía no has subido un Plan de Ventas. Sube el Excel de metas mensuales arriba para activar esta sección.")
        return

    df_mes = df[(df['Año'] == fecha_ref.year) & (df['Mes_Num'] == fecha_ref.month)]
    venta_mes = df_mes.groupby('Vendedor', as_index=False).agg(Venta=('Total Línea', 'sum'))

    comparativo = pd.merge(plan, venta_mes, on='Vendedor', how='left')
    comparativo['Venta'] = comparativo['Venta'].fillna(0)
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
            comparativo, y='Vendedor', x='% Cumplimiento', orientation='h', template="plotly_dark",
            category_orders={'Vendedor': orden},
            labels={'% Cumplimiento': 'Cumplimiento (%)'},
            color_discrete_sequence=[theme.COLOR_ACCENT],
        )
        fig.add_vline(x=100, line_dash="dash", line_color=theme.COLOR_POSITIVE)
        fig.update_layout(height=380, margin=dict(l=0, r=10, t=10, b=0))
        st.plotly_chart(fig, width='stretch', key="chart_plan_mensual")

    excel_plan = generar_excel_bonito({'Cumplimiento Meta': (tabla, {'Meta': 'moneda', 'Venta': 'moneda', '% Cumplimiento': 'porcentaje'})})
    st.download_button(
        "📥 Descargar Excel", excel_plan, "cumplimiento_meta_mensual.xlsx",
        key="dl_plan_mensual", width='stretch'
    )


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

    hojas = {'Resumen por Vendedor': (resumen, {'Venta': 'moneda', 'Kilos': 'kilos'})}

    detalle = _detalle_por_cliente(df_periodo)
    if detalle is not None:
        formatos_detalle = {'Venta': 'moneda'}
        if 'Kilos' in detalle.columns:
            formatos_detalle['Kilos'] = 'kilos'
        hojas['Detalle por Cliente'] = (detalle, formatos_detalle)

    excel_bytes = generar_excel_bonito(hojas)
    st.download_button(
        "📥 Descargar Excel", excel_bytes, f"venta_vendedores_{sufijo}.xlsx",
        key=f"dl_vend_{sufijo}", width='stretch'
    )


def _detalle_por_cliente(df_periodo: pd.DataFrame):
    """Desglose fila a fila: Zona, Vendedor y Cliente, con venta ($) y
    unidades (Kilos/Unidades), para que quien descargue el Excel pueda ver
    exactamente qué se facturó a cada cliente sin tener que cruzar datos."""
    if 'Nombre Cliente' not in df_periodo.columns:
        return None

    cols_agrupacion = [c for c in ['Zona', 'Vendedor', 'Nombre Cliente'] if c in df_periodo.columns]
    if 'Vendedor' not in cols_agrupacion or 'Nombre Cliente' not in cols_agrupacion:
        return None

    agg = {'Venta': ('Total Línea', 'sum')}
    if 'Kilos' in df_periodo.columns:
        agg['Kilos'] = ('Kilos', 'sum')
    if 'Unidades' in df_periodo.columns:
        agg['Unidades'] = ('Unidades', 'sum')

    detalle = df_periodo.groupby(cols_agrupacion, as_index=False).agg(**agg)
    return detalle.sort_values(['Vendedor', 'Venta'], ascending=[True, False])
