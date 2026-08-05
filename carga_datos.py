"""
carga_datos.py
---------------
Orquesta la carga de los archivos que sube el usuario: llama a la limpieza
de utils.py para cada archivo, junta todo en un solo DataFrame, quita filas
duplicadas si varios archivos se superponen en el tiempo, y muestra los
avisos correspondientes (notas de crédito, filas descartadas, meses
incompletos).
"""

import pandas as pd
import streamlit as st

from utils import cargar_y_limpiar_datos, generar_excel_bonito

COLUMNAS_CLAVE_DEDUP = ['Fecha', 'Nro SAP', 'Folio SII', 'Cod.', 'Cod Cliente', 'Total Línea']


def procesar_archivos_subidos(uploaded_files):
    """
    Recibe la lista de archivos subidos por st.file_uploader, los procesa y
    devuelve (df, df_descartadas). Muestra en pantalla los avisos relevantes.
    Si no hay datos válidos, muestra el error y hace st.stop().
    """
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
        df = _quitar_duplicados_entre_archivos(df)

    _mostrar_aviso_filas_descartadas(df_descartadas)

    return df, df_descartadas


def _quitar_duplicados_entre_archivos(df: pd.DataFrame) -> pd.DataFrame:
    cols_clave = [c for c in COLUMNAS_CLAVE_DEDUP if c in df.columns]
    if not cols_clave:
        return df
    filas_antes = len(df)
    df = df.drop_duplicates(subset=cols_clave)
    quitadas = filas_antes - len(df)
    if quitadas > 0:
        st.warning(
            f"⚠️ Se detectaron y quitaron {quitadas:,} filas duplicadas entre los archivos "
            "(probablemente por periodos que se superponen entre los archivos que subiste)."
        )
    return df


def _mostrar_aviso_filas_descartadas(df_descartadas: pd.DataFrame):
    if df_descartadas.empty:
        return
    st.warning(
        f"⚠️ Atención: Se descartaron {len(df_descartadas)} filas del archivo original porque "
        "no tenían una fecha válida registrada. Puedes inspeccionarlas abajo."
    )
    with st.expander("👀 Ver las filas descartadas"):
        df_mostrar = df_descartadas.copy()
        for c in df_mostrar.columns:
            df_mostrar[c] = df_mostrar[c].astype(str)
        st.dataframe(df_mostrar, width='stretch')
        excel_desc = generar_excel_bonito({'Filas Descartadas': (df_descartadas, {})})
        st.download_button("📥 Descargar Filas Descartadas (Excel)", excel_desc, "filas_sin_fecha_valida.xlsx", key="dl_desc")
