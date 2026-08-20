"""
mi_dashboard.py
----------------
Pestaña "Mi Dashboard": constructor de gráficos ad-hoc. El usuario elige
tipo de gráfico, columna X, columna Y, agregación y agrupación/color, y arma
cualquier vista que necesite sin que la app la tenga anticipada de antemano.

También permite guardar esas configuraciones con un nombre ("Mi Dashboard")
y volver a verlas en otra sesión — se guarda la CONFIGURACIÓN del gráfico
(qué columnas, qué tipo, qué agregación) en un JSON en disco
(data/mis_dashboards.json), no los datos: al reabrir, se recalcula con lo
que haya cargado en ese momento. Mismo patrón de persistencia en disco que
ya usa plan_ventas.py para el plan de ventas mensual.
"""

import json
import os
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

import ia_graficos
import plan_ventas
import theme
from utils import generar_excel_bonito

CARPETA_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
RUTA_GUARDADOS = os.path.join(CARPETA_DATA, 'mis_dashboards.json')

TIPOS_GRAFICO = ["Barra", "Línea", "Torta", "Dispersión", "Área"]
AGREGACIONES = ["Suma", "Promedio", "Conteo", "Máximo", "Mínimo"]
_AGG_FUNC = {"Suma": "sum", "Promedio": "mean", "Máximo": "max", "Mínimo": "min"}

# Columnas que sabemos que son identificadores internos, no métricas de
# negocio (aunque sean numéricas) — para que no salgan sugeridas como Y.
_PATRONES_ID = ['cod', 'nro', 'folio', 'id', 'documento', 'sap', 'rut', 'num']

# Orden de preferencia para sugerir defaults con sentido de negocio.
_METRICAS_PREFERIDAS = ['Total Línea', 'Kilos', 'Cantidad']
_DIMENSIONES_PREFERIDAS = ['Zona', 'Categoría', 'Vendedor', 'Nombre Cliente', 'Fecha', 'Mes_Nombre', 'Año']

_COLS_INTERNAS = {'__Archivo Origen', 'Periodo', 'Mes_Num', 'Día'}
# Numéricas pero conceptualmente son dimensiones (año), no métricas que
# tenga sentido sumar/promediar — se excluyen solo de las sugerencias de Y.
_COLS_NO_METRICA = {'Año'}

MESES_ORDEN = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio',
               'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
MESES_MAP = {i + 1: nombre for i, nombre in enumerate(MESES_ORDEN)}

# Cuando la columna X es una fecha real (ej. 'Fecha'), agrupamos por esta
# granularidad para que el gráfico no quede con un punto por cada día — sin
# esto, un año de datos diarios se ve como una nube ilegible de puntos.
GRANULARIDADES_FECHA = ["Día", "Semana", "Mes", "Año"]
_TICKFORMAT_FECHA = {"Día": "%d-%m-%Y", "Semana": "%d-%m-%Y", "Mes": "%b %Y", "Año": "%Y"}


def _bucket_fecha(serie: pd.Series, granularidad: str) -> pd.Series:
    if granularidad == "Semana":
        return serie.dt.to_period('W').dt.start_time
    if granularidad == "Mes":
        return serie.dt.to_period('M').dt.to_timestamp()
    if granularidad == "Año":
        return serie.dt.to_period('Y').dt.to_timestamp()
    return serie.dt.normalize()


def _es_columna_id(nombre: str) -> bool:
    bajo = str(nombre).strip().lower()
    return any(p in bajo for p in _PATRONES_ID)


def _columnas_metricas(df: pd.DataFrame) -> list:
    numericas = [
        c for c in df.columns
        if pd.api.types.is_numeric_dtype(df[c]) and not _es_columna_id(c)
        and c not in _COLS_INTERNAS and c not in _COLS_NO_METRICA
    ]
    preferidas = [c for c in _METRICAS_PREFERIDAS if c in numericas]
    resto = [c for c in numericas if c not in preferidas]
    return preferidas + resto


def _columnas_dimension(df: pd.DataFrame) -> list:
    candidatas = [
        c for c in df.columns
        if c not in _COLS_INTERNAS and not _es_columna_id(c)
        and (
            pd.api.types.is_object_dtype(df[c]) or pd.api.types.is_string_dtype(df[c])
            or pd.api.types.is_datetime64_any_dtype(df[c])
            or c in ('Año', 'Mes_Nombre')
        )
    ]
    preferidas = [c for c in _DIMENSIONES_PREFERIDAS if c in candidatas]
    resto = [c for c in candidatas if c not in preferidas]
    return preferidas + resto


def _cargar_guardados() -> list:
    if not os.path.isfile(RUTA_GUARDADOS):
        return []
    try:
        with open(RUTA_GUARDADOS, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _guardar_lista(lista: list) -> None:
    os.makedirs(CARPETA_DATA, exist_ok=True)
    with open(RUTA_GUARDADOS, 'w', encoding='utf-8') as f:
        json.dump(lista, f, ensure_ascii=False, indent=2)


def _eliminar_guardado(nombre: str) -> None:
    lista = [g for g in _cargar_guardados() if g['nombre'] != nombre]
    _guardar_lista(lista)


def _paleta_categorica() -> list:
    return [theme.COLOR_ACCENT, theme.COLOR_PERIODO_A, theme.COLOR_PERIODO_B,
            theme.COLOR_FOCUS, theme.COLOR_NEGATIVE, theme.COLOR_ACCENT_STRONG]


def _preparar_datos(df: pd.DataFrame, config: dict):
    """Agrupa el DataFrame según la config y devuelve (df_agrupado, col_valor,
    etiqueta_valor) listo para graficar, o (None, None, None) si falta algo."""
    col_x = config.get('col_x')
    col_y = config.get('col_y')
    agregacion = config.get('agregacion', 'Suma')
    color_por = config.get('color_por') or None
    granularidad_fecha = config.get('granularidad_fecha')
    filtro_anios = config.get('filtro_anios') or []
    filtro_meses = config.get('filtro_meses') or []

    if not col_x or col_x not in df.columns:
        return None, None, None
    if color_por == col_x:
        color_por = None
    if color_por and color_por not in df.columns:
        color_por = None
    if agregacion != 'Conteo' and (not col_y or col_y not in df.columns or not pd.api.types.is_numeric_dtype(df[col_y])):
        return None, None, None

    cols_necesarias = {col_x} | ({color_por} if color_por else set()) | ({col_y} if agregacion != 'Conteo' else set())
    if filtro_anios and 'Año' in df.columns:
        cols_necesarias.add('Año')
    if filtro_meses and 'Mes_Num' in df.columns:
        cols_necesarias.add('Mes_Num')
    trabajo = df[list(cols_necesarias)].copy()

    # Filtro de Año/Mes: independiente de qué columna se use en X — permite,
    # por ejemplo, graficar por Zona pero solo con datos de ciertos meses.
    if filtro_anios and 'Año' in trabajo.columns:
        trabajo = trabajo[trabajo['Año'].isin(filtro_anios)]
    if filtro_meses and 'Mes_Num' in trabajo.columns:
        meses_num = [k for k, v in MESES_MAP.items() if v in filtro_meses]
        trabajo = trabajo[trabajo['Mes_Num'].isin(meses_num)]

    # Columna X de fecha real: sin agrupar por día/semana/mes/año, un año de
    # datos diarios se ve como una nube de puntos ilegible en el gráfico.
    if pd.api.types.is_datetime64_any_dtype(trabajo[col_x]) and granularidad_fecha:
        trabajo[col_x] = _bucket_fecha(trabajo[col_x], granularidad_fecha)

    # Año o una fecha usados como color/agrupación: Plotly los trata como
    # escala continua (degradado) en vez de colores discretos por grupo si
    # se dejan numéricos/fecha — se castean a texto para forzar categórico.
    if color_por and (pd.api.types.is_datetime64_any_dtype(trabajo[color_por]) or color_por == 'Año'):
        trabajo[color_por] = trabajo[color_por].astype(str)

    cols_agrupar = [col_x] + ([color_por] if color_por else [])

    if agregacion == 'Conteo':
        agrupado = trabajo.groupby(cols_agrupar, as_index=False).size().rename(columns={'size': 'Conteo'})
        return agrupado, 'Conteo', 'Conteo de registros'

    func = _AGG_FUNC.get(agregacion, 'sum')
    agrupado = trabajo.groupby(cols_agrupar, as_index=False)[col_y].agg(func)
    return agrupado, col_y, f"{col_y} ({agregacion.lower()})"


def _construir_figura(df_agrupado: pd.DataFrame, col_valor: str, etiqueta_valor: str, config: dict):
    tipo = config['tipo']
    col_x = config['col_x']
    color_por = config.get('color_por') or None
    if color_por == col_x or (color_por and color_por not in df_agrupado.columns):
        color_por = None
    titulo = config.get('titulo') or ''
    granularidad_fecha = config.get('granularidad_fecha')

    # Mes_Nombre es texto ('Enero', 'Febrero', ...) — sin esto, Plotly lo
    # ordena alfabéticamente (Abril, Agosto, Diciembre...) en vez de
    # cronológicamente.
    category_orders = {}
    if col_x == 'Mes_Nombre':
        category_orders[col_x] = MESES_ORDEN
    if color_por == 'Mes_Nombre':
        category_orders[color_por] = MESES_ORDEN

    labels = {col_valor: etiqueta_valor}
    kwargs = dict(labels=labels, title=titulo or None)
    if category_orders:
        kwargs['category_orders'] = category_orders
    if color_por:
        kwargs['color'] = color_por
        kwargs['color_discrete_sequence'] = _paleta_categorica()
    else:
        kwargs['color_discrete_sequence'] = [theme.COLOR_ACCENT]

    if tipo == "Barra":
        fig = px.bar(df_agrupado, x=col_x, y=col_valor, barmode='group', **kwargs)
    elif tipo == "Línea":
        fig = px.line(df_agrupado, x=col_x, y=col_valor, markers=True, **kwargs)
    elif tipo == "Torta":
        kwargs.pop('color', None)
        kwargs.pop('color_discrete_sequence', None)
        fig = px.pie(df_agrupado, names=col_x, values=col_valor, title=titulo or None,
                     color_discrete_sequence=_paleta_categorica())
    elif tipo == "Dispersión":
        fig = px.scatter(df_agrupado, x=col_x, y=col_valor, size=col_valor if not color_por else None, **kwargs)
    else:  # Área
        fig = px.area(df_agrupado, x=col_x, y=col_valor, **kwargs)

    layout = theme.plotly_layout_kwargs()
    if tipo != "Torta":
        es_moneda = any(p in col_valor.lower() for p in ['total línea', 'monto', 'venta', 'clp'])
        if es_moneda:
            fig.update_layout(yaxis_tickprefix="$", yaxis_tickformat=",.")
        if granularidad_fecha and pd.api.types.is_datetime64_any_dtype(df_agrupado[col_x]):
            fig.update_layout(xaxis_tickformat=_TICKFORMAT_FECHA.get(granularidad_fecha, "%d-%m-%Y"))
        fig.update_layout(**layout, height=460)
    else:
        fig.update_layout(**{k: v for k, v in layout.items() if k in ('paper_bgcolor', 'plot_bgcolor', 'font')}, height=460)
    return fig


def _panel_constructor(df: pd.DataFrame, metricas: list, dimensiones: list) -> dict:
    theme.section_title("🧩 Constructor de Gráfico")

    col1, col2, col3 = st.columns(3)
    with col1:
        tipo = st.selectbox("Tipo de gráfico", TIPOS_GRAFICO, key="md_tipo")
    with col2:
        opciones_x = dimensiones or list(df.columns)
        col_x = st.selectbox("Columna X (eje / categoría)", opciones_x, key="md_col_x")
    with col3:
        agregacion = st.selectbox("Agregación", AGREGACIONES, key="md_agregacion")

    granularidad_fecha = None
    if col_x in df.columns and pd.api.types.is_datetime64_any_dtype(df[col_x]):
        granularidad_fecha = st.selectbox(
            "Agrupar fecha por", GRANULARIDADES_FECHA, index=GRANULARIDADES_FECHA.index("Mes"),
            key="md_granularidad_fecha",
            help="Junta las fechas individuales en día / semana / mes / año para que el gráfico no quede saturado de puntos."
        )

    col4, col5 = st.columns(2)
    with col4:
        if agregacion == 'Conteo':
            st.selectbox("Columna Y (métrica)", ["(no aplica — se cuentan filas)"], disabled=True, key="md_col_y_disabled")
            col_y = None
        else:
            opciones_y = metricas or [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
            if not opciones_y:
                st.warning("No se encontraron columnas numéricas para usar como métrica.")
                col_y = None
            else:
                col_y = st.selectbox("Columna Y (métrica)", opciones_y, key="md_col_y")
    with col5:
        opciones_color = ["Ninguno"] + [d for d in dimensiones if d != col_x]
        color_sel = st.selectbox("Agrupar / colorear por (opcional)", opciones_color, key="md_color_por")
        color_por = None if color_sel == "Ninguno" else color_sel

    filtro_anios, filtro_meses = _panel_filtro_tiempo(df)

    titulo = st.text_input("Título del gráfico (opcional)", key="md_titulo")

    return {
        "tipo": tipo, "col_x": col_x, "col_y": col_y,
        "agregacion": agregacion, "color_por": color_por, "titulo": titulo,
        "granularidad_fecha": granularidad_fecha,
        "filtro_anios": filtro_anios, "filtro_meses": filtro_meses,
    }


def _panel_filtro_tiempo(df: pd.DataFrame):
    """Filtro de Año/Mes independiente de qué columnas se usen en el
    gráfico — para poder, por ejemplo, graficar Venta por Zona pero solo
    con los meses de un año en particular. Vacío = incluye todo (no filtra).
    Mismo estilo de selector (segmented_control) que usa el dashboard
    principal para elegir Año/Mes."""
    tiene_anio = 'Año' in df.columns
    tiene_mes = 'Mes_Num' in df.columns
    if not tiene_anio and not tiene_mes:
        return [], []

    st.caption("📅 Filtrar por Año / Mes (opcional) — deja vacío para incluir todo. Aplica solo a este gráfico.")
    col_f1, col_f2 = st.columns(2)

    filtro_anios = []
    with col_f1:
        if tiene_anio:
            años_disponibles = sorted(df['Año'].dropna().unique().tolist())
            filtro_anios = st.segmented_control(
                "Año(s)", años_disponibles, key="md_filtro_anios", selection_mode='multi'
            ) or []

    filtro_meses = []
    with col_f2:
        if tiene_mes:
            # Ojo: los 12 meses se muestran SIEMPRE (no solo los que ya
            # tienen datos) — así puedes seleccionar, ej., Diciembre para
            # un año que todavía no llega hasta ahí, y te avisamos abajo en
            # vez de simplemente no dejarte elegir ese mes.
            filtro_meses = st.segmented_control(
                "Mes(es)", MESES_ORDEN, key="md_filtro_meses", selection_mode='multi'
            ) or []

    # Los selectores de Año y de Mes son independientes entre sí (para poder
    # comparar, ej., Diciembre de varios años a la vez) — pero eso significa
    # que una combinación puntual (ej. "Diciembre 2026") puede no tener
    # datos aunque Diciembre y 2026 sí existan por separado en otros meses/
    # años. Se avisa acá, junto al filtro, en vez de un mensaje genérico de
    # "no hay datos" más abajo que no dice cuál combinación falló.
    if filtro_anios and filtro_meses and tiene_anio and tiene_mes:
        meses_num_sel = [k for k, v in MESES_MAP.items() if v in filtro_meses]
        combos_existentes = set(zip(df['Año'], df['Mes_Num']))
        combos_faltantes = sorted(
            (a, m) for a in filtro_anios for m in meses_num_sel
            if (a, m) not in combos_existentes
        )
        if combos_faltantes:
            combos_txt = ', '.join(f"{MESES_MAP[m]} {a}" for a, m in combos_faltantes)
            st.caption(f"⚠️ Todavía no hay datos cargados para: {combos_txt}.")

    return filtro_anios, filtro_meses


def _mostrar_grafico(df: pd.DataFrame, config: dict, key_prefix: str) -> bool:
    """Arma y muestra el gráfico para la config dada. Devuelve True si se
    pudo graficar (para no ofrecer 'guardar' sobre algo que no rendereó)."""
    df_agrupado, col_valor, etiqueta_valor = _preparar_datos(df, config)
    if df_agrupado is None:
        st.info("Selecciona una Columna Y válida (numérica) para poder graficar, o usa la agregación 'Conteo'.")
        return False
    if df_agrupado.empty:
        st.info("No hay datos para graficar con esta combinación de filtros/columnas.")
        return False

    fig = _construir_figura(df_agrupado, col_valor, etiqueta_valor, config)
    st.plotly_chart(fig, width='stretch', theme=None, key=f"{key_prefix}_chart")
    return True


def _aplicar_config_ia(config_ia: dict, df: pd.DataFrame, metricas: list, dimensiones: list) -> list:
    """Valida la config que devolvió la IA contra las columnas REALES del
    archivo cargado (defensa extra además del responseSchema de la API) y
    la aplica al session_state de los widgets del constructor, para que al
    hacer rerun aparezcan ya seleccionados. Devuelve una lista de avisos
    para lo que la IA sugirió pero no era válido y se ignoró."""
    avisos = []

    tipo = config_ia.get('tipo')
    if tipo in TIPOS_GRAFICO:
        st.session_state['md_tipo'] = tipo

    col_x = config_ia.get('col_x')
    if col_x in dimensiones:
        st.session_state['md_col_x'] = col_x
    else:
        avisos.append(f"la columna X sugerida ('{col_x}') no es válida, revísala a mano")

    agregacion = config_ia.get('agregacion')
    if agregacion in AGREGACIONES:
        st.session_state['md_agregacion'] = agregacion

    col_y = config_ia.get('col_y')
    if col_y in metricas:
        st.session_state['md_col_y'] = col_y
    elif agregacion != 'Conteo':
        avisos.append(f"la columna Y sugerida ('{col_y}') no es válida, revísala a mano")

    color_por = config_ia.get('color_por')
    if color_por == 'Ninguno' or color_por in dimensiones:
        st.session_state['md_color_por'] = color_por

    if 'Año' in df.columns:
        años_validos = set(df['Año'].dropna().unique().tolist())
        filtro_anios = [a for a in (config_ia.get('filtro_anios') or []) if a in años_validos]
        st.session_state['md_filtro_anios'] = filtro_anios

    filtro_meses = [m for m in (config_ia.get('filtro_meses') or []) if m in MESES_ORDEN]
    st.session_state['md_filtro_meses'] = filtro_meses

    titulo = config_ia.get('titulo')
    if titulo:
        st.session_state['md_titulo'] = str(titulo)[:120]

    return avisos


def _panel_claves_ia() -> dict:
    """Panel único de API keys (Gemini + Groq como respaldo), compartido
    por el generador de gráfico simple y el análisis avanzado — se pega
    una vez acá y ambos lo usan. Devuelve {'gemini': key, 'groq': key}
    (cualquiera puede quedar vacío)."""
    with st.expander("🔑 API keys de IA (Gemini + Groq de respaldo, opcional)", expanded=False):
        st.caption(
            "Con solo Gemini alcanza. Agregar también Groq es opcional: si Gemini se queda sin "
            "cupo (límite gratis por minuto) o está saturado, la app reintenta automáticamente con "
            "Groq antes de mostrar un error — cada uno tiene su propio límite por separado."
        )
        api_keys = {}
        for proveedor in ia_graficos.PROVEEDORES:
            guardada = ia_graficos.cargar_api_key(proveedor)
            col_campo, col_estado = st.columns([4, 1])
            with col_campo:
                valor = st.text_input(
                    f"API key de {ia_graficos.NOMBRE_PROVEEDOR[proveedor]}"
                    + (" (gratis, sin tarjeta)" if proveedor == "gemini" else " (respaldo, opcional)"),
                    value=guardada, type="password", key=f"md_ia_key_{proveedor}",
                    help=f"Consíguela en {ia_graficos.URL_API_KEY[proveedor]}"
                )
            with col_estado:
                st.write("")
                st.caption("✅ Guardada" if guardada else "➖ Sin guardar")
            api_keys[proveedor] = valor.strip() or guardada

        if st.button("💾 Guardar API keys", key="md_ia_guardar_keys"):
            algo_guardado = False
            for proveedor in ia_graficos.PROVEEDORES:
                valor = st.session_state.get(f"md_ia_key_{proveedor}", "").strip()
                if valor:
                    ia_graficos.guardar_api_key(valor, proveedor)
                    algo_guardado = True
            if algo_guardado:
                st.success("API key(s) guardada(s).")
                st.rerun()
            else:
                st.warning("Pega al menos una API key antes de guardar.")

        return api_keys


def _panel_ia(df: pd.DataFrame, metricas: list, dimensiones: list, api_keys: dict):
    with st.expander("🤖 Pedir el gráfico con IA (opcional)", expanded=False):
        prompt_ia = st.text_area(
            "Describe el gráfico que quieres", key="md_ia_prompt",
            placeholder="Ej: top clientes por venta total, o cuántos pedidos hizo cada vendedor en 2025"
        )
        if st.button("✨ Generar con IA", key="md_ia_generar", width='stretch'):
            try:
                config_ia, proveedor = ia_graficos.interpretar_prompt(
                    prompt_ia, api_keys, metricas, dimensiones,
                    TIPOS_GRAFICO, AGREGACIONES, MESES_ORDEN,
                )
                avisos = _aplicar_config_ia(config_ia, df, metricas, dimensiones)
                for aviso in avisos:
                    st.warning(f"⚠️ {aviso}")
                nota_proveedor = f" (respondido por {ia_graficos.NOMBRE_PROVEEDOR[proveedor]})" if proveedor != "gemini" else ""
                st.success(f"✅ Listo{nota_proveedor} — el constructor de abajo ya quedó configurado, revísalo antes de guardar.")
                st.rerun()
            except ia_graficos.ErrorIA as e:
                st.error(str(e))


# Heurística de nombre de columna para saber si una cifra del resultado de
# la IA avanzada se muestra en pesos chilenos o como porcentaje — la IA
# arma tablas con nombres de columna arbitrarios, así que no hay una lista
# fija de columnas como en el resto de la app.
_PATRONES_MONEDA = ['línea', 'linea', 'venta', 'monto', 'meta', 'proyec', 'presupuesto',
                     'ppto', 'precio', 'costo', 'clp', 'ticket', 'ingreso']
_PATRONES_PORCENTAJE = ['%', 'porcentaje', 'cumplimiento', 'pct']


def _tipo_columna_valor(nombre: str) -> str:
    bajo = str(nombre).lower()
    if any(p in bajo for p in _PATRONES_PORCENTAJE):
        return 'porcentaje'
    if any(p in bajo for p in _PATRONES_MONEDA):
        return 'moneda'
    return None


def _formato_streamlit(resultado: pd.DataFrame) -> dict:
    """Formatos para pandas Styler (st.dataframe) — pesos chilenos con
    separador de miles para columnas de plata, % para columnas de
    cumplimiento, y separador de miles simple para el resto de números."""
    formatos = {}
    for c in resultado.columns:
        if not pd.api.types.is_numeric_dtype(resultado[c]):
            continue
        tipo = _tipo_columna_valor(c)
        if tipo == 'moneda':
            formatos[c] = '${:,.0f}'
        elif tipo == 'porcentaje':
            formatos[c] = '{:,.1f}%'
        else:
            formatos[c] = '{:,.0f}'
    return formatos


def _formato_excel(resultado: pd.DataFrame) -> dict:
    """Mismo criterio que _formato_streamlit, pero en las etiquetas que
    espera utils.generar_excel_bonito ('moneda'/'porcentaje')."""
    formatos = {}
    for c in resultado.columns:
        if not pd.api.types.is_numeric_dtype(resultado[c]):
            continue
        tipo = _tipo_columna_valor(c)
        if tipo:
            formatos[c] = tipo
    return formatos


def _autografico_resultado(resultado: pd.DataFrame):
    """Intenta un gráfico de barras simple sobre el resultado de la IA
    avanzada (primera columna no-numérica como X, primera numérica como Y).
    Si la forma de la tabla no se presta para eso, no rompe — solo no
    dibuja nada y se queda con la tabla."""
    cols_num = [c for c in resultado.columns if pd.api.types.is_numeric_dtype(resultado[c])]
    cols_cat = [c for c in resultado.columns if c not in cols_num]
    if not cols_num or not cols_cat or len(resultado) > 60:
        return
    try:
        col_y = cols_num[0]
        fig = px.bar(resultado, x=cols_cat[0], y=col_y, color_discrete_sequence=[theme.COLOR_ACCENT])
        layout = theme.plotly_layout_kwargs()
        if _tipo_columna_valor(col_y) == 'moneda':
            fig.update_layout(yaxis_tickprefix="$", yaxis_tickformat=",.")
        fig.update_layout(**layout, height=420)
        st.plotly_chart(fig, width='stretch', theme=None, key="ia_avanzada_chart")
    except Exception:
        pass


def _mostrar_resultado_ia_avanzada(resultado: pd.DataFrame, key_prefix: str, codigo: str = ""):
    st.dataframe(resultado.style.format(_formato_streamlit(resultado)), width='stretch', hide_index=True)
    _autografico_resultado(resultado)
    excel_resultado = generar_excel_bonito({'Resultado IA': (resultado, _formato_excel(resultado))})
    st.download_button("📥 Descargar Excel", excel_resultado, "analisis_ia.xlsx", key=f"{key_prefix}_dl")
    if codigo:
        with st.expander("Ver código generado"):
            st.code(codigo, language='python')


def _panel_ia_avanzada(df: pd.DataFrame, api_keys: dict):
    with st.expander("🧠 Análisis avanzado con IA (opcional) — cruces, Plan de Ventas, cálculos propios", expanded=False):
        st.caption(
            "Para preguntas que el constructor simple no puede armar (ej. comparar contra el "
            "Plan de Ventas, promedios, proporciones). La IA escribe un cálculo en pandas que "
            "corre en un entorno restringido — solo puede tocar tus datos ya cargados, sin "
            "acceso a archivos, red ni el sistema."
        )
        plan = plan_ventas.cargar_plan()
        tiene_plan = not plan.empty
        if tiene_plan:
            st.caption("✅ Plan de Ventas cargado — la IA puede cruzarlo si tu pregunta lo necesita.")
        else:
            st.caption("ℹ️ No tienes un Plan de Ventas cargado (se sube en el Dashboard General) — la IA solo verá tus datos de ventas.")

        pregunta = st.text_area(
            "¿Qué quieres calcular?", key="md_ia_av_prompt",
            placeholder="Ej: venta acumulada de agosto 2026 por vendedor comparada contra su meta del plan"
        )
        if st.button("🧠 Analizar con IA", key="md_ia_av_generar", width='stretch'):
            try:
                with st.spinner("Escribiendo el cálculo..."):
                    codigo, proveedor = ia_graficos.generar_codigo_analisis(
                        pregunta, api_keys, list(df.columns),
                        tiene_plan, list(plan.columns) if tiene_plan else [],
                    )
                with st.spinner("Ejecutando..."):
                    resultado = ia_graficos.ejecutar_codigo_pandas(codigo, df, plan)
                st.session_state['md_ia_av_resultado'] = resultado
                st.session_state['md_ia_av_codigo'] = codigo
                st.session_state['md_ia_av_proveedor'] = proveedor
            except ia_graficos.ErrorIA as e:
                st.session_state.pop('md_ia_av_resultado', None)
                st.error(str(e))

        resultado = st.session_state.get('md_ia_av_resultado')
        if resultado is not None:
            codigo_actual = st.session_state.get('md_ia_av_codigo', '')
            proveedor_usado = st.session_state.get('md_ia_av_proveedor', 'gemini')
            if proveedor_usado != 'gemini':
                st.caption(f"↩️ Respondido por {ia_graficos.NOMBRE_PROVEEDOR[proveedor_usado]} (Gemini no estaba disponible).")
            _mostrar_resultado_ia_avanzada(resultado, key_prefix="ia_av_preview", codigo=codigo_actual)

            col_nombre_ia, col_btn_ia = st.columns([3, 1])
            with col_nombre_ia:
                nombre_ia = st.text_input(
                    "Nombre para guardar este análisis", key="md_ia_av_nombre",
                    placeholder="Ej: Proyección Agosto 2026 vs Plan"
                )
            with col_btn_ia:
                st.write("")
                st.write("")
                if st.button("💾 Guardar en Mi Dashboard", key="md_ia_av_guardar", width='stretch'):
                    if not nombre_ia or not nombre_ia.strip():
                        st.warning("Ponle un nombre al análisis antes de guardarlo.")
                    else:
                        guardados = _cargar_guardados()
                        guardados = [g for g in guardados if g['nombre'] != nombre_ia.strip()]
                        guardados.append({
                            "tipo_entrada": "ia_codigo",
                            "nombre": nombre_ia.strip(),
                            "pregunta": pregunta,
                            "codigo": codigo_actual,
                            "creado": datetime.now().isoformat(timespec='seconds'),
                        })
                        _guardar_lista(guardados)
                        st.success(f"✅ Análisis '{nombre_ia.strip()}' guardado.")
                        st.rerun()


def render(df: pd.DataFrame):
    if df is None or df.empty:
        st.info("Todavía no hay datos cargados.")
        return

    metricas = _columnas_metricas(df)
    dimensiones = _columnas_dimension(df)

    if not dimensiones:
        st.warning("No se encontraron columnas de tipo texto/categoría en tus datos para armar un gráfico.")
        return

    api_keys = _panel_claves_ia()
    _panel_ia(df, metricas, dimensiones, api_keys)
    _panel_ia_avanzada(df, api_keys)

    config = _panel_constructor(df, metricas, dimensiones)

    st.divider()
    theme.section_title("👁️ Vista Previa")
    se_graficó = _mostrar_grafico(df, config, key_prefix="preview")

    if se_graficó:
        col_nombre, col_btn = st.columns([3, 1])
        with col_nombre:
            nombre_guardar = st.text_input("Nombre para guardar este gráfico", key="md_nombre_guardar", placeholder="Ej: Venta por Zona 2025")
        with col_btn:
            st.write("")
            st.write("")
            if st.button("💾 Guardar en Mi Dashboard", key="md_btn_guardar", width='stretch'):
                if not nombre_guardar or not nombre_guardar.strip():
                    st.warning("Ponle un nombre al gráfico antes de guardarlo.")
                else:
                    guardados = _cargar_guardados()
                    guardados = [g for g in guardados if g['nombre'] != nombre_guardar.strip()]
                    guardados.append({
                        **config, "nombre": nombre_guardar.strip(),
                        "creado": datetime.now().isoformat(timespec='seconds'),
                    })
                    _guardar_lista(guardados)
                    st.success(f"✅ Gráfico '{nombre_guardar.strip()}' guardado.")
                    st.rerun()

    guardados = _cargar_guardados()
    if guardados:
        theme.ledger_tape(compacta=True)
        theme.section_title(f"📌 Mi Dashboard ({len(guardados)} gráfico{'s' if len(guardados) != 1 else ''} guardado{'s' if len(guardados) != 1 else ''})")

        plan_para_guardados = None  # se carga una sola vez, solo si hace falta (perezoso)

        for i, g in enumerate(guardados):
            es_ia_codigo = g.get('tipo_entrada') == 'ia_codigo'
            with st.container(border=True):
                col_titulo, col_borrar = st.columns([5, 1])
                with col_titulo:
                    if es_ia_codigo:
                        st.markdown(f"**{g['nombre']}** &nbsp;·&nbsp; 🧠 Análisis IA &nbsp;·&nbsp; _{g.get('pregunta', '')}_")
                    else:
                        col_x_desc = g['col_x'] + (f" ({g['granularidad_fecha']})" if g.get('granularidad_fecha') else "")
                        filtro_bits = []
                        if g.get('filtro_anios'):
                            filtro_bits.append(', '.join(str(a) for a in g['filtro_anios']))
                        if g.get('filtro_meses'):
                            filtro_bits.append(', '.join(g['filtro_meses']))
                        filtro_desc = f" &nbsp;·&nbsp; 📅 {' — '.join(filtro_bits)}" if filtro_bits else ""
                        st.markdown(f"**{g['nombre']}** &nbsp;·&nbsp; {g['tipo']} &nbsp;·&nbsp; {col_x_desc}"
                                     + (f" / {g['col_y']}" if g.get('col_y') else "")
                                     + f" &nbsp;·&nbsp; {g['agregacion']}" + filtro_desc)
                with col_borrar:
                    if st.button("🗑️ Eliminar", key=f"md_del_{i}", width='stretch'):
                        _eliminar_guardado(g['nombre'])
                        st.rerun()

                if es_ia_codigo:
                    if plan_para_guardados is None:
                        plan_para_guardados = plan_ventas.cargar_plan()
                    try:
                        resultado_guardado = ia_graficos.ejecutar_codigo_pandas(g.get('codigo', ''), df, plan_para_guardados)
                        _mostrar_resultado_ia_avanzada(resultado_guardado, key_prefix=f"saved_ia_{i}", codigo=g.get('codigo', ''))
                    except ia_graficos.ErrorIA as e:
                        st.warning(f"⚠️ No se pudo recalcular este análisis con los datos actuales: {e}")
                else:
                    _mostrar_grafico(df, g, key_prefix=f"saved_{i}")
