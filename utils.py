import pandas as pd
import streamlit as st
import re

def _limpiar_numero(valor):
    """
    Convierte un valor a float detectando paréntesis contables o signos menos
    en CUALQUIER parte del texto, y usa expresiones regulares para limpiar
    toda la "basura" o caracteres invisibles que exporta SAP.
    """
    if pd.isna(valor):
        return 0.0
    
    if isinstance(valor, (int, float)):
        return float(valor)

    texto = str(valor).strip().replace('\xa0', ' ')
    if texto == '':
        return 0.0

    es_negativo = False

    # Detecta negativo si hay paréntesis O un signo menos en cualquier lado
    if '(' in texto and ')' in texto:
        es_negativo = True
    elif '-' in texto:
        es_negativo = True

    # OPCIÓN NUCLEAR: Borra todo lo que NO sea número, coma o punto
    texto = re.sub(r'[^\d,\.]', '', texto)

    if texto == '':
        return 0.0

    # Lógica estricta para formato LATAM/Chile
    if ',' in texto and '.' in texto:
        if texto.rfind(',') > texto.rfind('.'):
            # 1.234,56 -> el punto es separador de miles, la coma es decimal
            texto = texto.replace('.', '').replace(',', '.')
        else:
            # 1,234.56 -> la coma es separador de miles
            texto = texto.replace(',', '')
    elif '.' in texto:
        partes = texto.split('.')
        if len(partes[-1]) == 3:
            # Asume que es separador de miles si tiene exactamente 3 dígitos después del punto
            texto = texto.replace('.', '')
    elif ',' in texto:
        # Solo hay coma (1234,56) -> es decimal
        texto = texto.replace(',', '.')

    try:
        numero = float(texto)
    except ValueError:
        return 0.0

    # Como la expresión regular borró los signos, "numero" siempre es positivo.
    # Aquí le devolvemos el signo negativo si detectamos que era necesario.
    return -numero if es_negativo else numero

@st.cache_data(show_spinner=False)
def cargar_y_limpiar_datos(uploaded_file):
    """
    Lee el archivo Excel o CSV, limpia la fila de 'Total' de SAP, 
    normaliza textos, fuerza notas de crédito a negativo y maneja fechas.
    """
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        xls = pd.ExcelFile(uploaded_file)
        # Lee TODAS las hojas del archivo y las junta (por si alguien separó
        # los años o los meses en distintas hojas dentro del mismo Excel,
        # como una hoja "2025" y otra "2026").
        hojas = [pd.read_excel(xls, sheet_name=nombre) for nombre in xls.sheet_names]
        df = pd.concat(hojas, ignore_index=True) if len(hojas) > 1 else hojas[0]
    
    # 1. Elimina filas de resumen tipo "Total" que SAP agrega al final del export
    col_texto = next((c for c in ['Detalle', 'Cliente', 'Nombre Cliente', 'Vendedor', 'Zona'] if c in df.columns), None)
    if col_texto:
        mask_total = df[col_texto].astype(str).str.strip().str.lower().isin(['total', 'totales', 'total general'])
        df = df[~mask_total]

    # 1b. Red de seguridad: algunos exportadores (SAP/BI) agregan al final filas
    # de texto libre como "Total", "Filtros aplicados: ..." o el aviso
    # "Exported data exceeded the allowed volume. Some data may have been
    # omitted." Estas filas no son datos y hay que botarlas SIEMPRE,
    # independiente de en qué columna hayan caído.
    patron_footer = r'exported data exceeded|filtros aplicados|allowed volume'
    mask_footer = df.apply(
        lambda fila: fila.astype(str).str.lower().str.contains(patron_footer, regex=True, na=False).any(),
        axis=1
    )
    if mask_footer.any():
        df = df[~mask_footer]

    # 2. Limpiador numérico avanzado (Atrapa los paréntesis y signos)
    cols_numericas = [c for c in ['Total Línea', 'Kilos', 'Cantidad'] if c in df.columns]
    for c in cols_numericas:
        df[c] = df[c].apply(_limpiar_numero)

    # 3. REGLA ESTRICTA "INDICADOR": FORZAR NOTAS DE CRÉDITO A NEGATIVO
    cantidad_nc = 0
    col_ind = next((c for c in df.columns if 'indicador' in str(c).strip().lower()), None)
    if col_ind:
        # Busca palabras clave perdonando tildes y mayúsculas.
        # OJO: se excluye explícitamente "débito"/"debito"/"debit" porque
        # "Nota de Débito" también contiene la palabra "nota", y una nota
        # de débito SUMA (no debe forzarse a negativo como una de crédito).
        texto_ind = df[col_ind].astype(str).str.lower()
        mask_nc = (
            texto_ind.str.contains('crédito|credito|credit', na=False, regex=True)
            & ~texto_ind.str.contains('débito|debito|debit', na=False, regex=True)
        )
        cantidad_nc = mask_nc.sum()

        for c in cols_numericas:
            # Fuerza matemáticamente a que sea negativo (-abs)
            df.loc[mask_nc, c] = -df.loc[mask_nc, c].abs()

    # 4. Normalización de texto y llenado de nulos en columnas de agrupación
    cols_agrupacion = ['Zona', 'Categoría', 'Vendedor', 'Nombre Cliente']
    col_prod = next((c for c in ['Detalle', 'Producto', 'Descripción', 'Articulo', 'Nombre Artículo', 'Material', 'Desc. Artículo', 'Item'] if c in df.columns), None)
    if col_prod:
        cols_agrupacion.append(col_prod)
        
    for c in cols_agrupacion:
        if c in df.columns:
            df[c] = df[c].fillna(f'Sin {c}')
            if df[c].dtype == 'object':
                df[c] = df[c].astype(str).str.strip().str.title()
    
    # 5. Limpieza y parseo de fechas
    # OJO: si alguien arma el Excel a mano y la columna de fecha pierde el
    # formato de "Fecha" en Excel, pandas la lee como un número plano
    # (ej: 45659, el "número de serie" interno de Excel para el 2-ene-2025).
    # pd.to_datetime normal interpretaría ese número como nanosegundos desde
    # 1970 y arruinaría todo. Por eso primero detectamos esos números de
    # serie de Excel (rango razonable ~año 2000 a ~2040) y los convertimos
    # con el origen correcto (30-dic-1899), y solo el resto lo tratamos
    # como texto de fecha normal.
    def _convertir_fecha_mixta(serie):
        def _es_serial_excel(v):
            if isinstance(v, bool) or pd.isna(v):
                return False
            if isinstance(v, (int, float)):
                return 36526 <= v <= 51544  # aprox. año 2000 a 2041
            return False

        mask_serial = serie.apply(_es_serial_excel)
        resultado = pd.Series(pd.NaT, index=serie.index, dtype='datetime64[ns]')
        if mask_serial.any():
            resultado.loc[mask_serial] = pd.to_datetime(
                serie[mask_serial].astype(float), unit='D', origin='1899-12-30', errors='coerce'
            )
        resto = ~mask_serial
        if resto.any():
            resultado.loc[resto] = pd.to_datetime(serie[resto], dayfirst=True, errors='coerce')
        return resultado

    for col in df.columns:
        if df[col].dtype == 'object':
            try:
                converted = _convertir_fecha_mixta(df[col])
                if converted.notna().sum() > (len(df) * 0.1): 
                    df[col] = converted
            except Exception:
                pass
    
    cols_fecha = df.select_dtypes(include=['datetime64']).columns.tolist()
    
    df_descartadas = pd.DataFrame()
    if cols_fecha:
        col_f = next((c for c in cols_fecha if 'fecha' in c.lower()), cols_fecha[0])
        
        df_descartadas = df[df[col_f].isna()].copy()
        df = df.dropna(subset=[col_f])
        
        df['Año'] = df[col_f].dt.year
        df['Mes_Num'] = df[col_f].dt.month
        df['Día'] = df[col_f].dt.day
        
        meses_map = {1:'Enero', 2:'Febrero', 3:'Marzo', 4:'Abril', 5:'Mayo', 6:'Junio', 
                     7:'Julio', 8:'Agosto', 9:'Septiembre', 10:'Octubre', 11:'Noviembre', 12:'Diciembre'}
        df['Mes_Nombre'] = df['Mes_Num'].map(meses_map)

    return df, df_descartadas, int(cantidad_nc)


def detectar_meses_incompletos(df: pd.DataFrame, umbral: float = 0.5) -> list:
    """
    Revisa si algún mes tiene muchas menos filas que el promedio de los demás
    meses del mismo archivo. Esto casi siempre delata un export truncado por
    el sistema de origen (SAP/BI), NO una caída real de ventas.
    Devuelve una lista de strings con los meses sospechosos, para mostrar
    como advertencia en el dashboard.
    """
    if 'Año' not in df.columns or 'Mes_Num' not in df.columns:
        return []

    conteo = df.groupby(['Año', 'Mes_Num']).size()
    if len(conteo) < 2:
        return []

    promedio = conteo.median()
    avisos = []
    meses_map = {1:'Enero', 2:'Febrero', 3:'Marzo', 4:'Abril', 5:'Mayo', 6:'Junio',
                 7:'Julio', 8:'Agosto', 9:'Septiembre', 10:'Octubre', 11:'Noviembre', 12:'Diciembre'}
    for (anio, mes), cantidad in conteo.items():
        if cantidad < promedio * umbral:
            avisos.append(f"{meses_map.get(int(mes), mes)} {int(anio)} (solo {int(cantidad):,} filas vs. mediana de {int(promedio):,})")
    return avisos


def calcular_kpis(df: pd.DataFrame) -> dict:
    venta = df['Total Línea'].sum() if 'Total Línea' in df.columns else 0
    kilos = df['Kilos'].sum() if 'Kilos' in df.columns else 0
    
    col_doc = next((c for c in ['Folio', 'Documento', 'Nro Documento', 'Nº Doc', 'Factura', 'Boleta', 'Ticket'] if c in df.columns), None)
    if col_doc and len(df) > 0:
        pedidos_unicos = df[col_doc].nunique()
        ticket = (venta / pedidos_unicos) if pedidos_unicos > 0 else 0
    else:
        ticket = df['Total Línea'].mean() if 'Total Línea' in df.columns else 0
        
    clientes = df['Cod Cliente'].nunique() if 'Cod Cliente' in df.columns else 0
    return {'venta': venta, 'kilos': kilos, 'ticket': ticket, 'clientes': clientes}


def generar_excel_bonito(hojas: dict) -> bytes:
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