"""Pestaña 4: Datos y Resúmenes — tablas de categorías, productos, top clientes y base consolidada."""

import pandas as pd
import streamlit as st

from utils import generar_excel_bonito


def render(df_a, df_b, df_dual, modo, label_a, label_b, col_sort_tabla, col_prod):
    top20_cli = _calcular_top20_clientes(df_a, df_b, modo, label_a, label_b)

    _tabla_categorias(df_a, df_b, modo, label_a, label_b)
    st.divider()

    col_tab1, col_tab2 = st.columns(2)
    with col_tab1:
        _tabla_todos_productos(df_dual, modo, label_a, label_b, col_sort_tabla, col_prod)
    with col_tab2:
        _tabla_top20_clientes(top20_cli, modo, label_a, label_b)

    st.divider()
    _tabla_consolidada(df_dual)


def _calcular_top20_clientes(df_a, df_b, modo, label_a, label_b):
    if 'Nombre Cliente' not in df_a.columns or 'Total Línea' not in df_a.columns:
        return None
    cli_a = df_a.groupby('Nombre Cliente', as_index=False).agg(**{
        f'Venta {label_a}': ('Total Línea', 'sum'), f'Kilos {label_a}': ('Kilos', 'sum')
    })
    if modo == "Comparativa (A vs B)":
        cli_b = df_b.groupby('Nombre Cliente', as_index=False).agg(**{
            f'Venta {label_b}': ('Total Línea', 'sum'), f'Kilos {label_b}': ('Kilos', 'sum')
        })
        resumen = pd.merge(cli_a, cli_b, on='Nombre Cliente', how='outer').fillna(0)
        resumen['Venta Total'] = resumen[f'Venta {label_a}'] + resumen[f'Venta {label_b}']
        return resumen.sort_values('Venta Total', ascending=False).head(20)
    cli_a['Venta Total'] = cli_a[f'Venta {label_a}']
    return cli_a.sort_values('Venta Total', ascending=False).head(20)


def _tabla_categorias(df_a, df_b, modo, label_a, label_b):
    st.subheader("📋 Resumen de Ventas por Categoría")
    if 'Categoría' not in df_a.columns or 'Total Línea' not in df_a.columns:
        return

    cat_a = df_a.groupby('Categoría', as_index=False).agg(**{
        f'Venta {label_a}': ('Total Línea', 'sum'), f'Kilos {label_a}': ('Kilos', 'sum')
    })

    if modo == "Comparativa (A vs B)":
        cat_b = df_b.groupby('Categoría', as_index=False).agg(**{
            f'Venta {label_b}': ('Total Línea', 'sum'), f'Kilos {label_b}': ('Kilos', 'sum')
        })
        resumen = pd.merge(cat_a, cat_b, on='Categoría', how='outer').fillna(0)
        resumen['Δ Venta %'] = resumen.apply(
            lambda r: ((r[f'Venta {label_b}'] - r[f'Venta {label_a}']) / r[f'Venta {label_a}'] * 100)
            if r[f'Venta {label_a}'] != 0 else 0, axis=1
        )
        resumen = resumen.sort_values(f'Venta {label_b}', ascending=False)

        fila_total = pd.DataFrame([{
            'Categoría': 'Total',
            f'Venta {label_a}': resumen[f'Venta {label_a}'].sum(),
            f'Kilos {label_a}': resumen[f'Kilos {label_a}'].sum(),
            f'Venta {label_b}': resumen[f'Venta {label_b}'].sum(),
            f'Kilos {label_b}': resumen[f'Kilos {label_b}'].sum(),
        }])
        v_a_tot, v_b_tot = fila_total[f'Venta {label_a}'].iloc[0], fila_total[f'Venta {label_b}'].iloc[0]
        fila_total['Δ Venta %'] = ((v_b_tot - v_a_tot) / v_a_tot * 100) if v_a_tot != 0 else 0

        resumen_final = pd.concat([resumen, fila_total], ignore_index=True)
        st.dataframe(
            resumen_final.style.format({
                f'Venta {label_a}': '${:,.0f}', f'Venta {label_b}': '${:,.0f}',
                f'Kilos {label_a}': '{:,.0f}', f'Kilos {label_b}': '{:,.0f}',
                'Δ Venta %': '{:+.1f}%'
            }), width='stretch', hide_index=True
        )
        excel = generar_excel_bonito({'Resumen_Categorias': (resumen_final, {
            f'Venta {label_a}': 'moneda', f'Venta {label_b}': 'moneda', 'Δ Venta %': 'porcentaje'
        })})
        st.download_button("📥 Descargar Tabla Excel", excel, "tabla_categorias.xlsx", key="dl_tab_cat", width='stretch')
    else:
        cat_a = cat_a.sort_values(f'Venta {label_a}', ascending=False)
        fila_total = pd.DataFrame([{
            'Categoría': 'Total',
            f'Venta {label_a}': cat_a[f'Venta {label_a}'].sum(),
            f'Kilos {label_a}': cat_a[f'Kilos {label_a}'].sum(),
        }])
        resumen_final = pd.concat([cat_a, fila_total], ignore_index=True)
        st.dataframe(
            resumen_final.style.format({f'Venta {label_a}': '${:,.0f}', f'Kilos {label_a}': '{:,.0f}'}),
            width='stretch', hide_index=True
        )
        excel = generar_excel_bonito({'Resumen_Categorias': (resumen_final, {f'Venta {label_a}': 'moneda'})})
        st.download_button("📥 Descargar Tabla Excel", excel, "tabla_categorias.xlsx", key="dl_tab_cat_simple", width='stretch')


def _tabla_todos_productos(df_dual, modo, label_a, label_b, col_sort_tabla, col_prod):
    st.subheader("🛍️ Datos: Todos los Productos")
    if not col_prod or 'Total Línea' not in df_dual.columns:
        return
    tabla = df_dual.groupby([col_prod, 'Periodo'], as_index=False)['Total Línea'].sum()
    tabla = tabla.pivot(index=col_prod, columns='Periodo', values='Total Línea').fillna(0)
    if col_sort_tabla in tabla.columns:
        tabla = tabla.sort_values(by=col_sort_tabla, ascending=False)
    st.dataframe(tabla.style.format("${:,.0f}"), width='stretch')

    formatos = {label_a: 'moneda', label_b: 'moneda'} if modo == "Comparativa (A vs B)" else {label_a: 'moneda'}
    excel = generar_excel_bonito({'Productos': (tabla.reset_index(), formatos)})
    st.download_button("📥 Descargar Excel", excel, "tabla_todos_productos.xlsx", key="dl_tab_prod", width='stretch')


def _tabla_top20_clientes(top20_cli, modo, label_a, label_b):
    st.subheader("👥 Datos: Top 20 Clientes")
    if top20_cli is None:
        return

    if modo == "Comparativa (A vs B)":
        st.dataframe(
            top20_cli.drop(columns=['Venta Total']).style.format({
                f'Venta {label_a}': '${:,.0f}', f'Venta {label_b}': '${:,.0f}',
                f'Kilos {label_a}': '{:,.0f}', f'Kilos {label_b}': '{:,.0f}',
                'Δ Venta %': '{:+.1f}%'
            }), width='stretch', hide_index=True
        )
        excel = generar_excel_bonito({'Top_Clientes': (top20_cli.drop(columns=['Venta Total']), {
            f'Venta {label_a}': 'moneda', f'Venta {label_b}': 'moneda', 'Δ Venta %': 'porcentaje'
        })})
        st.download_button("📥 Descargar Excel", excel, "tabla_top20_clientes.xlsx", key="dl_tab_cli", width='stretch')
    else:
        st.dataframe(
            top20_cli.drop(columns=['Venta Total']).style.format({
                f'Venta {label_a}': '${:,.0f}', f'Kilos {label_a}': '{:,.0f}'
            }), width='stretch', hide_index=True
        )
        excel = generar_excel_bonito({'Top_Clientes': (top20_cli.drop(columns=['Venta Total']), {f'Venta {label_a}': 'moneda'})})
        st.download_button("📥 Descargar Excel", excel, "tabla_top20_clientes.xlsx", key="dl_tab_cli_smp", width='stretch')


def _tabla_consolidada(df_dual):
    st.subheader("📂 Inspeccionar Tabla Consolidada (Base de Datos Procesada)")
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

    excel = generar_excel_bonito({'Consolidado': (df_vista, {'Total Línea': 'moneda', 'Kilos': 'kilos'})})
    st.download_button(
        "📥 Descargar (Excel, con formato)", excel, "base_datos_consolidada.xlsx",
        key="dl_tab_vista", width='stretch',
        help="Con estilo y formato de moneda — tarda más en generarse la primera vez con archivos grandes."
    )