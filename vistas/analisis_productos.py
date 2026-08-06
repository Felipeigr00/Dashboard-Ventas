"""Pestaña 2: Análisis de Productos — rendimiento por producto y clientes por producto."""

import streamlit as st
import plotly.express as px

from utils import generar_excel_bonito
import theme


def render(df_dual, modo, label_a, label_b, color_map, col_sort_tabla, col_prod):
    theme.section_title("👤 Filtro de Vendedor (Aplica a Rendimiento Productos y Clientes)")

    if 'Vendedor' in df_dual.columns:
        vendedores_disp = sorted(df_dual['Vendedor'].dropna().astype(str).unique().tolist())
        opciones_v2 = ["Todos"] + vendedores_disp
        idx_v2 = opciones_v2.index(st.session_state.mem_vend_t2) if st.session_state.mem_vend_t2 in opciones_v2 else 0

        vend_sel = st.selectbox(
            "Selecciona un vendedor para ver sus productos vendidos",
            opciones_v2, index=idx_v2, key="widget_vend_t2"
        )
        st.session_state.mem_vend_t2 = vend_sel

        df_tab2 = df_dual.copy() if vend_sel == "Todos" else df_dual[df_dual['Vendedor'].astype(str) == vend_sel].copy()
    else:
        df_tab2 = df_dual.copy()
        vend_sel = "Todos"

    theme.ledger_tape(compacta=True)

    etiqueta_vend = "(Todos los Vendedores)" if vend_sel == "Todos" else f"(Vendedor: {vend_sel})"
    st.subheader(f"🛍️ Rendimiento de Todos los Productos {etiqueta_vend}")

    if col_prod and 'Total Línea' in df_tab2.columns:
        df_prod = df_tab2.groupby([col_prod, 'Periodo'], as_index=False)['Total Línea'].sum()

        if not df_prod.empty:
            num_productos_unicos = df_prod[col_prod].nunique()
            alto_dinamico = max(600, num_productos_unicos * 25)

            fig_prod = px.bar(df_prod, x='Total Línea', y=col_prod, color='Periodo', barmode='group',
                              orientation='h', labels={'Total Línea': 'Venta ($ CLP)', col_prod: 'Producto'},
                              color_discrete_map=color_map)
            layout_prod = theme.plotly_layout_kwargs()
            layout_prod['yaxis'] = {**layout_prod['yaxis'], 'categoryorder': 'total ascending'}
            fig_prod.update_layout(**layout_prod, xaxis_tickprefix="$", xaxis_tickformat=",.", height=alto_dinamico)
            st.plotly_chart(fig_prod, width='stretch', theme=None)

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
            st.info(f"El vendedor {vend_sel} no registra ventas de productos en este periodo.")
    else:
        st.info("No se detectó la columna de Productos (Descripción/Articulo) en el archivo.")

    st.divider()

    st.subheader(f"🧑‍🤝‍🧑 Clientes por Producto {etiqueta_vend}")
    if col_prod and 'Nombre Cliente' in df_tab2.columns and 'Total Línea' in df_tab2.columns:
        productos_disponibles = df_tab2.groupby(col_prod)['Total Línea'].sum().sort_values(ascending=False).index.tolist()

        if productos_disponibles:
            idx_p2 = productos_disponibles.index(st.session_state.mem_prod_t2) if st.session_state.mem_prod_t2 in productos_disponibles else 0

            producto_sel = st.selectbox(
                "Selecciona un producto para ver qué clientes lo compraron",
                productos_disponibles, index=idx_p2, key='widget_prod_t2'
            )
            st.session_state.mem_prod_t2 = producto_sel

            df_prod_cli = df_tab2[df_tab2[col_prod] == producto_sel]
            df_prod_cli_agg = df_prod_cli.groupby(['Nombre Cliente', 'Periodo'], as_index=False)['Total Línea'].sum()

            top_clientes_prod = df_prod_cli_agg.groupby('Nombre Cliente')['Total Línea'].sum().nlargest(20).index
            df_prod_cli_agg = df_prod_cli_agg[df_prod_cli_agg['Nombre Cliente'].isin(top_clientes_prod)]

            if not df_prod_cli_agg.empty:
                fig_prod_cli = px.bar(
                    df_prod_cli_agg, x='Total Línea', y='Nombre Cliente', color='Periodo', barmode='group',
                    orientation='h',
                    labels={'Total Línea': 'Venta ($ CLP)', 'Nombre Cliente': 'Cliente'},
                    color_discrete_map=color_map
                )
                layout_prod_cli = theme.plotly_layout_kwargs()
                layout_prod_cli['yaxis'] = {**layout_prod_cli['yaxis'], 'categoryorder': 'total ascending'}
                fig_prod_cli.update_layout(**layout_prod_cli, xaxis_tickprefix="$", xaxis_tickformat=",.", height=550)
                st.plotly_chart(fig_prod_cli, width='stretch', theme=None)

                if 'Cod Cliente' in df_prod_cli.columns:
                    base = df_prod_cli[df_prod_cli['Nombre Cliente'].isin(top_clientes_prod)].groupby(
                        ['Cod Cliente', 'Nombre Cliente', 'Periodo'], as_index=False
                    )['Total Línea'].sum()
                    tabla_cli_prod_export = base.pivot(
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