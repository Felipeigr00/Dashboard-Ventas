import pandas as pd
import streamlit as st

@st.cache_data
def cargar_y_limpiar_datos(uploaded_file):
    """
    Lee el archivo Excel o CSV, limpia la fila de 'Total' de SAP, 
    normaliza textos y estandariza las fechas de forma segura.
    """
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        xls = pd.ExcelFile(uploaded_file)
        # Por defecto leemos la primera hoja, pero devolvemos el objeto xls para elegir
        df = pd.read_excel(xls, sheet_name=0)
    
    # 1. Elimina filas de resumen tipo "Total" que SAP agrega al final del export
    col_texto = next((c for c in ['Detalle', 'Cliente', 'Nombre Cliente', 'Vendedor', 'Zona'] if c in df.columns), None)
    if col_texto:
        mask_total = df[col_texto].astype(str).str.strip().str.lower().isin(['total', 'totales', 'total general'])
        df = df[~mask_total]

    # 2. Normalización de texto y llenado de nulos en columnas de agrupación
    cols_agrupacion = ['Zona', 'Categoría', 'Vendedor', 'Nombre Cliente']
    col_prod = next((c for c in ['Detalle', 'Producto', 'Descripción', 'Articulo', 'Nombre Artículo', 'Material', 'Desc. Artículo', 'Item'] if c in df.columns), None)
    if col_prod:
        cols_agrupacion.append(col_prod)
        
    for c in cols_agrupacion:
        if c in df.columns:
            df[c] = df[c].fillna(f'Sin {c}')
            if df[c].dtype == 'object':
                # Normaliza: quita espacios extra y pone formato Título para agrupar bien
                df[c] = df[c].astype(str).str.strip().str.title()
    
    # 3. Limpieza y parseo de fechas
    for col in df.columns:
        if df[col].dtype == 'object':
            try:
                converted = pd.to_datetime(df[col], dayfirst=True, errors='coerce')
                if converted.notna().sum() > (len(df) * 0.1): 
                    df[col] = converted
            except Exception:
                pass
    
    cols_fecha = df.select_dtypes(include=['datetime64']).columns.tolist()
    
    df_descartadas = pd.DataFrame()
    if cols_fecha:
        # Priorizar una columna que realmente se llame 'Fecha'
        col_f = next((c for c in cols_fecha if 'fecha' in c.lower()), cols_fecha[0])
        
        # Guardamos las filas que tienen NaT (Not a Time) en la fecha antes de borrarlas
        df_descartadas = df[df[col_f].isna()].copy()
        
        # Mantenemos solo las válidas
        df = df.dropna(subset=[col_f])
        
        df['Año'] = df[col_f].dt.year
        df['Mes_Num'] = df[col_f].dt.month
        df['Día'] = df[col_f].dt.day
        
        meses_map = {1:'Enero', 2:'Febrero', 3:'Marzo', 4:'Abril', 5:'Mayo', 6:'Junio', 
                     7:'Julio', 8:'Agosto', 9:'Septiembre', 10:'Octubre', 11:'Noviembre', 12:'Diciembre'}
        df['Mes_Nombre'] = df['Mes_Num'].map(meses_map)

    # Ahora devolvemos también el DataFrame de las filas descartadas
    return df, df_descartadas


def calcular_kpis(df: pd.DataFrame) -> dict:
    """
    Calcula los 4 indicadores clave. Ahora incluye lógica avanzada para 
    el Ticket Promedio agrupando por número de documento si existe.
    """
    venta = df['Total Línea'].sum() if 'Total Línea' in df.columns else 0
    kilos = df['Kilos'].sum() if 'Kilos' in df.columns else 0
    
    # Mejora para Ticket Promedio Real (agrupado por folio/documento)
    col_doc = next((c for c in ['Folio', 'Documento', 'Nro Documento', 'Nº Doc', 'Factura', 'Boleta', 'Ticket'] if c in df.columns), None)
    if col_doc and len(df) > 0:
        pedidos_unicos = df[col_doc].nunique()
        ticket = (venta / pedidos_unicos) if pedidos_unicos > 0 else 0
    else:
        # Fallback a promedio por línea si no hay identificador de documento
        ticket = df['Total Línea'].mean() if 'Total Línea' in df.columns else 0
        
    clientes = df['Cod Cliente'].nunique() if 'Cod Cliente' in df.columns else 0
    return {'venta': venta, 'kilos': kilos, 'ticket': ticket, 'clientes': clientes}


def generar_excel_bonito(hojas: dict) -> bytes:
    """
    Genera un archivo .xlsx en memoria con formato profesional:
    encabezados en negrita con fondo oscuro, columnas de moneda/kilos/porcentaje
    formateadas, ancho de columna automático y encabezado congelado.

    hojas: dict {nombre_hoja: (dataframe, formatos)}
        formatos: dict opcional {nombre_columna: 'moneda' | 'kilos' | 'porcentaje'}
    """
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    wb.remove(wb.active)

    header_font = Font(bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='1C1917', end_color='1C1917', fill_type='solid')

    for nombre_hoja, contenido in hojas.items():
        df_hoja, formatos = contenido if isinstance(contenido, tuple) else (contenido, {})
        formatos = formatos or {}

        ws = wb.create_sheet(title=str(nombre_hoja)[:31])
        ws.append(list(df_hoja.columns))
        for col_idx in range(1, len(df_hoja.columns) + 1):
            celda = ws.cell(row=1, column=col_idx)
            celda.font = header_font
            celda.fill = header_fill
            celda.alignment = Alignment(horizontal='center')

        for _, fila in df_hoja.iterrows():
            ws.append(list(fila))

        for col_idx, col_nombre in enumerate(df_hoja.columns, start=1):
            letra = get_column_letter(col_idx)
            valores_str = [str(v) for v in df_hoja[col_nombre]] if len(df_hoja) else []
            largo_max = max([len(str(col_nombre))] + [len(v) for v in valores_str])
            ws.column_dimensions[letra].width = min(largo_max + 4, 45)

            formato = formatos.get(col_nombre)
            if formato and len(df_hoja) > 0:
                num_formato = {
                    'moneda': '$#,##0',
                    'kilos': '#,##0',
                    'porcentaje': '0.0"%"',
                }.get(formato)
                if num_formato:
                    for row_idx in range(2, len(df_hoja) + 2):
                        ws.cell(row=row_idx, column=col_idx).number_format = num_formato

        ws.freeze_panes = 'A2'

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()