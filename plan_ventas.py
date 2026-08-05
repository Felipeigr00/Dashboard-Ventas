"""
plan_ventas.py
---------------
Maneja el Plan de Ventas mensual (meta/presupuesto por vendedor): se sube
UNA vez al mes y queda guardado en disco (data/plan_ventas.xlsx), a
diferencia del archivo de ventas que se sube todos los días. La app lee
este archivo guardado en cada sesión sin que el usuario tenga que volver
a subirlo, hasta que se reemplace por uno nuevo.
"""

import os

import pandas as pd
import streamlit as st

CARPETA_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
RUTA_PLAN = os.path.join(CARPETA_DATA, 'plan_ventas.xlsx')

ETIQUETAS_TOTAL = {'total', 'zona', 'totales', 'total general'}


def guardar_plan(uploaded_file) -> None:
    """Guarda el Excel subido en disco, reemplazando el plan anterior."""
    os.makedirs(CARPETA_DATA, exist_ok=True)
    uploaded_file.seek(0)
    with open(RUTA_PLAN, 'wb') as f:
        f.write(uploaded_file.read())
    cargar_plan.clear()


def existe_plan() -> bool:
    return os.path.isfile(RUTA_PLAN)


def info_plan() -> dict | None:
    """Nombre y fecha de última modificación del plan guardado, para
    mostrarle al usuario qué plan está activo sin tener que abrirlo."""
    if not existe_plan():
        return None
    mtime = os.path.getmtime(RUTA_PLAN)
    return {'actualizado': pd.Timestamp.fromtimestamp(mtime)}


@st.cache_data(show_spinner=False)
def cargar_plan() -> pd.DataFrame:
    """
    Lee el Excel de plan de ventas y lo normaliza a columnas
    ['Zona', 'Vendedor', 'Meta'].

    El archivo trae una fila en blanco arriba y una fila de encabezado real
    más abajo (Zona_Local / Vendedor / Ppto Tactico), además de filas de
    subtotal por zona y un total general que hay que descartar.
    """
    if not existe_plan():
        return pd.DataFrame(columns=['Zona', 'Vendedor', 'Meta'])

    crudo = pd.read_excel(RUTA_PLAN, header=None)

    fila_header = None
    for idx, fila in crudo.iterrows():
        valores = fila.astype(str).str.strip().str.lower().tolist()
        if 'vendedor' in valores:
            fila_header = idx
            break

    if fila_header is None:
        return pd.DataFrame(columns=['Zona', 'Vendedor', 'Meta'])

    encabezados = crudo.iloc[fila_header].astype(str).str.strip()
    datos = crudo.iloc[fila_header + 1:].copy()
    datos.columns = encabezados

    col_zona = next((c for c in datos.columns if 'zona' in str(c).lower()), None)
    col_vendedor = next((c for c in datos.columns if 'vendedor' in str(c).lower()), None)
    col_meta = next((c for c in datos.columns if c not in (col_zona, col_vendedor) and str(c).strip() and str(c) != 'nan'), None)

    if col_vendedor is None or col_meta is None:
        return pd.DataFrame(columns=['Zona', 'Vendedor', 'Meta'])

    plan = pd.DataFrame({
        'Zona': datos[col_zona].astype(str).str.strip() if col_zona else '',
        'Vendedor': datos[col_vendedor].astype(str).str.strip(),
        'Meta': pd.to_numeric(datos[col_meta], errors='coerce'),
    })

    mask_valido = (
        plan['Vendedor'].notna()
        & ~plan['Vendedor'].str.strip().str.lower().isin(ETIQUETAS_TOTAL)
        & ~plan['Zona'].str.strip().str.lower().isin(ETIQUETAS_TOTAL)
        & plan['Meta'].notna()
    )
    plan = plan[mask_valido].copy()
    plan['Vendedor'] = plan['Vendedor'].str.title()
    plan = plan.groupby(['Zona', 'Vendedor'], as_index=False)['Meta'].sum()

    return plan
