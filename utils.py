import pandas as pd
import streamlit as st

@st.cache_data
def cargar_y_limpiar_datos(uploaded_file):
    """
    Lee el archivo Excel o CSV, limpia la fila de 'Total' de SAP 
    y estandariza las fechas de forma segura.
    """
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        xls = pd.ExcelFile(uploaded_file)
        # Por defecto leemos la primera hoja, pero devolvemos el objeto xls para elegir
        df = pd.read_excel(xls, sheet_name=0)
    
    # Limpieza de filas de resumen tipo "Total" y parseo de fechas
    for col in df.columns:
        if df[col].dtype == 'object':
            try:
                converted = pd.to_datetime(df[col], dayfirst=True, errors='coerce')
                if converted.notna().sum() > (len(df) * 0.1): 
                    df[col] = converted
            except:
                pass
    
    cols_fecha = df.select_dtypes(include=['datetime64']).columns.tolist()
    
    if cols_fecha:
        col_f = cols_fecha[0]
        df = df.dropna(subset=[col_f])
        
        df['Año'] = df[col_f].dt.year
        df['Mes_Num'] = df[col_f].dt.month
        df['Día'] = df[col_f].dt.day
        
        meses_map = {1:'Enero', 2:'Febrero', 3:'Marzo', 4:'Abril', 5:'Mayo', 6:'Junio', 
                     7:'Julio', 8:'Agosto', 9:'Septiembre', 10:'Octubre', 11:'Noviembre', 12:'Diciembre'}
        df['Mes_Nombre'] = df['Mes_Num'].map(meses_map)

    # Corrección: 'Zona' puede venir vacía en ~859 filas del export.
    # Sin este fillna, groupby('Zona') las descarta silenciosamente
    # y esas ventas desaparecen de los gráficos por zona sin aviso.
    if 'Zona' in df.columns:
        df['Zona'] = df['Zona'].fillna('Sin Zona')

    return df