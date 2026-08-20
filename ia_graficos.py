"""
ia_graficos.py
---------------
Dos capacidades de IA para la pestaña "Mi Dashboard", con DOS proveedores
gratuitos configurables — Google Gemini (principal) y Groq (respaldo). Si
Gemini se queda sin cupo (límite por minuto) o sus servidores están
saturados, se reintenta automáticamente con Groq antes de mostrar un
error — cada proveedor tiene su propio límite gratuito, así que uno
raramente se satura justo cuando el otro también:

1. interpretar_prompt(): traduce una petición en lenguaje natural a la
   configuración estructurada que ya usa el constructor de gráficos
   (tipo, col_x, col_y, agregación...). La IA devuelve un JSON con
   opciones restringidas a las columnas reales del archivo — no puede
   inventar columnas ni ejecuta nada.

2. generar_codigo_analisis() + ejecutar_codigo_pandas(): para pedidos que
   no entran en ese esquema fijo (cruces con el Plan de Ventas, cálculos
   propios), la IA escribe un fragmento corto de código pandas que se
   ejecuta en un entorno restringido — sin acceso a archivos, red, ni el
   sistema, y con límite de tiempo. Solo puede tocar los DataFrames que ya
   están cargados en la app (df / plan). Pensado para uso LOCAL de una
   sola persona: no es una sandbox a prueba de un atacante activo, pero
   bloquea lo obvio y no expone nada fuera de tus propios datos.

Las API keys se guardan en texto plano en data/config_ia.json (carpeta que
ya está en .gitignore, igual que el plan de ventas) — pensado para uso
local de una sola persona, no para un servidor compartido.
"""

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturoTimeoutError

import pandas as pd
import requests

CARPETA_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
RUTA_CONFIG = os.path.join(CARPETA_DATA, 'config_ia.json')

PROVEEDORES = ["gemini", "groq"]
NOMBRE_PROVEEDOR = {"gemini": "Google Gemini", "groq": "Groq"}
URL_API_KEY = {
    "gemini": "https://aistudio.google.com/apikey",
    "groq": "https://console.groq.com/keys",
}

MODELO_DEFAULT = {"gemini": "gemini-flash-latest", "groq": "llama-3.3-70b-versatile"}
_URL_GEMINI_TMPL = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={key}"
_URL_GROQ = "https://api.groq.com/openai/v1/chat/completions"
_TIMEOUT_SEG = 30

# La capa gratis de estas IAs devuelve 503 ("modelo sobrecargado") o 429
# ("límite de peticiones por minuto") seguido de forma bastante común bajo
# carga — no son un fallo real, casi siempre se resuelven reintentando a
# los pocos segundos. Sin esto, cualquier pico momentáneo se le mostraba
# al usuario como un error, cuando bastaba con reintentar (o cambiar de
# proveedor, ver _llamar_ia_con_fallback).
_CODIGOS_REINTENTABLES = {429, 500, 502, 503, 504}
_INTENTOS = 3
_ESPERA_SEG = (1.5, 3.0)


class ErrorIA(Exception):
    """Cualquier fallo al hablar con la IA o al ejecutar lo que devolvió,
    con un mensaje ya en español listo para mostrarle al usuario con
    st.error()."""


def guardar_api_key(api_key: str, proveedor: str = "gemini") -> None:
    os.makedirs(CARPETA_DATA, exist_ok=True)
    config = _cargar_config()
    config[f"api_key_{proveedor}"] = api_key.strip()
    with open(RUTA_CONFIG, 'w', encoding='utf-8') as f:
        json.dump(config, f)


def cargar_api_key(proveedor: str = "gemini") -> str:
    config = _cargar_config()
    valor = config.get(f"api_key_{proveedor}", "")
    # Compatibilidad con el formato anterior (una sola key, sin distinguir
    # proveedor) — se trata como si fuera la de Gemini, que era la única
    # que existía antes de agregar el respaldo con Groq.
    if not valor and proveedor == "gemini":
        valor = config.get("api_key", "")
    return valor


def _cargar_config() -> dict:
    if not os.path.isfile(RUTA_CONFIG):
        return {}
    try:
        with open(RUTA_CONFIG, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _schema_a_instrucciones_texto(schema: dict) -> str:
    """Groq (a diferencia de Gemini) no soporta forzar un JSON contra un
    schema — solo puede pedírsele 'responde en JSON'. Convierte el mismo
    schema que ya usamos con Gemini en una descripción en texto de los
    campos/opciones válidas, para pedirle lo mismo a Groq por instrucción."""
    lineas = ["Responde ÚNICAMENTE con un JSON (sin markdown, sin texto fuera del JSON) con estos campos:"]
    for campo, spec in schema.get("properties", {}).items():
        if "enum" in spec:
            lineas.append(f'- "{campo}": uno de estos valores exactos: {", ".join(spec["enum"])}')
        elif spec.get("type") == "ARRAY":
            items = spec.get("items", {})
            if "enum" in items:
                lineas.append(f'- "{campo}": lista (puede ir vacía []) con valores de entre: {", ".join(items["enum"])}')
            else:
                lineas.append(f'- "{campo}": lista (puede ir vacía [])')
        else:
            lineas.append(f'- "{campo}": texto libre')
    return '\n'.join(lineas)


def _llamar_gemini(instrucciones: str, schema: dict, api_key: str, modelo: str) -> dict:
    """POST a Gemini pidiendo salida JSON forzada por 'schema', con
    reintento automático ante saturación temporal (ver _CODIGOS_REINTENTABLES).
    Devuelve el dict ya parseado, o lanza ErrorIA con un mensaje claro."""
    body = {
        "contents": [{"parts": [{"text": instrucciones}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": schema,
            "temperature": 0.1,
        },
    }
    url = _URL_GEMINI_TMPL.format(modelo=modelo, key=api_key)

    resp = None
    for intento in range(_INTENTOS):
        try:
            resp = requests.post(url, json=body, timeout=_TIMEOUT_SEG)
        except requests.exceptions.RequestException as e:
            raise ErrorIA(f"No se pudo contactar a Gemini (revisa tu conexión): {e}") from e

        if resp.status_code not in _CODIGOS_REINTENTABLES:
            break
        if intento < _INTENTOS - 1:
            time.sleep(_ESPERA_SEG[min(intento, len(_ESPERA_SEG) - 1)])

    if resp.status_code == 400:
        raise ErrorIA("La API key de Gemini no es válida, o la petición fue rechazada. Revisa que la copiaste completa.")
    if resp.status_code == 403:
        raise ErrorIA("La API key de Gemini no tiene permiso (¿la generaste en https://aistudio.google.com/apikey?).")
    if resp.status_code == 404:
        raise ErrorIA(f"El modelo '{modelo}' de Gemini no existe o ya no está disponible.")
    if resp.status_code == 429:
        raise ErrorIA("Se alcanzó el límite gratuito de Gemini (peticiones por minuto), incluso reintentando.")
    if resp.status_code >= 400:
        raise ErrorIA(f"Los servidores de Gemini están saturados (error {resp.status_code}), incluso reintentando.")

    try:
        data = resp.json()
        texto = data["candidates"][0]["content"]["parts"][0]["text"]
        resultado = json.loads(texto)
    except (KeyError, IndexError, json.JSONDecodeError, ValueError) as e:
        raise ErrorIA(f"Gemini respondió en un formato inesperado ({e}).") from e

    if not isinstance(resultado, dict):
        raise ErrorIA("Gemini no devolvió una respuesta válida.")

    return resultado


def _llamar_groq(instrucciones: str, schema: dict, api_key: str, modelo: str) -> dict:
    """POST a Groq (API compatible con OpenAI). Sin schema forzado como
    Gemini — se le describe el formato esperado en el propio texto (ver
    _schema_a_instrucciones_texto) y se valida la respuesta igual de
    estricto río abajo (mi_dashboard._aplicar_config_ia / ejecutar_codigo_pandas),
    así que una respuesta fuera de formato de Groq no es más riesgosa que
    la de Gemini — solo se descarta con un aviso."""
    texto_completo = f"{instrucciones}\n\n{_schema_a_instrucciones_texto(schema)}"
    body = {
        "model": modelo,
        "messages": [{"role": "user", "content": texto_completo}],
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
    }
    headers = {"Authorization": f"Bearer {api_key}"}

    resp = None
    for intento in range(_INTENTOS):
        try:
            resp = requests.post(_URL_GROQ, json=body, headers=headers, timeout=_TIMEOUT_SEG)
        except requests.exceptions.RequestException as e:
            raise ErrorIA(f"No se pudo contactar a Groq (revisa tu conexión): {e}") from e

        if resp.status_code not in _CODIGOS_REINTENTABLES:
            break
        if intento < _INTENTOS - 1:
            time.sleep(_ESPERA_SEG[min(intento, len(_ESPERA_SEG) - 1)])

    if resp.status_code == 401:
        raise ErrorIA("La API key de Groq no es válida. Revisa que la copiaste completa.")
    if resp.status_code == 404:
        raise ErrorIA(f"El modelo '{modelo}' de Groq no existe o ya no está disponible.")
    if resp.status_code == 429:
        raise ErrorIA("Se alcanzó el límite gratuito de Groq (peticiones por minuto), incluso reintentando.")
    if resp.status_code >= 400:
        raise ErrorIA(f"Los servidores de Groq están saturados (error {resp.status_code}), incluso reintentando.")

    try:
        data = resp.json()
        texto = data["choices"][0]["message"]["content"]
        resultado = json.loads(texto)
    except (KeyError, IndexError, json.JSONDecodeError, ValueError) as e:
        raise ErrorIA(f"Groq respondió en un formato inesperado ({e}).") from e

    if not isinstance(resultado, dict):
        raise ErrorIA("Groq no devolvió una respuesta válida.")

    return resultado


_LLAMAR_POR_PROVEEDOR = {"gemini": _llamar_gemini, "groq": _llamar_groq}


def _llamar_ia_con_fallback(instrucciones: str, schema: dict, api_keys: dict, modelos: dict = None) -> tuple:
    """Prueba cada proveedor en PROVEEDORES que tenga API key configurada,
    en orden (Gemini primero, Groq como respaldo). Devuelve (resultado_dict,
    proveedor_usado). Si todos fallan (o ninguno tiene key), lanza ErrorIA
    con el detalle de cada intento."""
    modelos = modelos or {}
    errores = []
    for proveedor in PROVEEDORES:
        api_key = (api_keys.get(proveedor) or "").strip()
        if not api_key:
            continue
        modelo = modelos.get(proveedor) or MODELO_DEFAULT[proveedor]
        try:
            resultado = _LLAMAR_POR_PROVEEDOR[proveedor](instrucciones, schema, api_key, modelo)
            return resultado, proveedor
        except ErrorIA as e:
            errores.append(f"{NOMBRE_PROVEEDOR[proveedor]}: {e}")

    if not errores:
        nombres = ' o '.join(NOMBRE_PROVEEDOR[p] for p in PROVEEDORES)
        raise ErrorIA(f"Falta la API key de {nombres} — pega al menos una en el panel de arriba.")
    raise ErrorIA(" — también falló ".join(errores))


# --------------------------------------------------------------------------
# 1) Modo simple: petición -> configuración fija del constructor
# --------------------------------------------------------------------------

def _construir_schema_grafico(tipos: list, agregaciones: list, metricas: list, dimensiones: list, meses: list) -> dict:
    return {
        "type": "OBJECT",
        "properties": {
            "tipo": {"type": "STRING", "enum": tipos},
            "col_x": {"type": "STRING", "enum": dimensiones},
            "col_y": {"type": "STRING", "enum": metricas + ["(ninguna)"]},
            "agregacion": {"type": "STRING", "enum": agregaciones},
            "color_por": {"type": "STRING", "enum": ["Ninguno"] + dimensiones},
            "filtro_anios": {"type": "ARRAY", "items": {"type": "INTEGER"}},
            "filtro_meses": {"type": "ARRAY", "items": {"type": "STRING", "enum": meses}},
            "titulo": {"type": "STRING"},
        },
        "required": ["tipo", "col_x", "agregacion", "color_por"],
    }


def _instrucciones_grafico(prompt_usuario: str, metricas: list, dimensiones: list) -> str:
    return (
        "Traduces una petición en español sobre UN gráfico de ventas a una "
        "configuración estructurada. Tu única tarea es elegir tipo de gráfico, "
        "columnas y agregación — nunca inventes columnas fuera de las listadas.\n\n"
        f"Columnas MÉTRICA disponibles (van en 'col_y', son números que se suman/promedian): {', '.join(metricas) or '(ninguna)'}\n"
        f"Columnas DIMENSIÓN disponibles (van en 'col_x' o 'color_por', son categorías): {', '.join(dimensiones) or '(ninguna)'}\n\n"
        "Reglas:\n"
        "- Si el usuario pide 'cuántos/conteo/cantidad de registros', usa agregacion='Conteo' y col_y='(ninguna)'.\n"
        "- Si no pide agrupar/colorear por nada más, usa color_por='Ninguno'.\n"
        "- Si no pide filtrar por año(s) o mes(es) específicos, deja esas listas vacías.\n"
        "- 'top N' o 'los mejores/peores' no es un tipo de dato — solo influye en qué "
        "columnas elegir, el orden/recorte no se controla desde acá.\n\n"
        f"Petición del usuario: {prompt_usuario.strip()}"
    )


def interpretar_prompt(prompt_usuario: str, api_keys: dict, metricas: list, dimensiones: list,
                        tipos: list, agregaciones: list, meses: list) -> tuple:
    """Devuelve (config_dict, proveedor_usado). api_keys: {'gemini': ..., 'groq': ...}
    (cualquiera puede venir vacío/faltar; se prueban en ese orden)."""
    if not prompt_usuario or not prompt_usuario.strip():
        raise ErrorIA("Describe qué gráfico quieres antes de generar.")
    if not dimensiones:
        raise ErrorIA("No hay columnas de categoría disponibles para armar un gráfico.")

    schema = _construir_schema_grafico(tipos, agregaciones, metricas, dimensiones, meses)
    instrucciones = _instrucciones_grafico(prompt_usuario, metricas, dimensiones)
    return _llamar_ia_con_fallback(instrucciones, schema, api_keys)


# --------------------------------------------------------------------------
# 2) Modo avanzado: petición -> código pandas -> se ejecuta en sandbox
# --------------------------------------------------------------------------

_SCHEMA_CODIGO = {
    "type": "OBJECT",
    "properties": {"codigo": {"type": "STRING"}},
    "required": ["codigo"],
}

# Lo que NUNCA debe aparecer en el código generado. No es una sandbox a
# prueba de balas (exec() en Python puro nunca lo es del todo), pero
# bloquea cualquier intento —incluso accidental— de tocar archivos, red,
# el sistema, u otros objetos de Python fuera de tus propios datos.
_PATRONES_PROHIBIDOS = [
    'import ', '__', 'open(', 'exec(', 'eval(', 'compile(', 'globals(', 'locals(',
    'getattr(', 'setattr(', 'delattr(', 'subprocess', 'os.', 'sys.', 'input(',
    'breakpoint(', 'exit(', 'quit(', 'help(', 'file(', 'socket', 'requests',
]

_TIMEOUT_CODIGO_SEG = 10
_MAX_FILAS_RESULTADO = 5000


def _instrucciones_codigo(prompt_usuario: str, columnas_df: list, tiene_plan: bool, columnas_plan: list) -> str:
    partes = [
        "Escribes SOLO código Python usando pandas para responder una pregunta sobre datos "
        "de ventas ya cargados en memoria. No expliques nada, no uses markdown, no hagas "
        "imports (pandas ya está disponible como 'pd').\n\n",
        f"Tienes un DataFrame llamado 'df' con estas columnas: {', '.join(columnas_df)}\n",
    ]
    if tiene_plan:
        partes.append(f"Tienes otro DataFrame llamado 'plan' (metas de venta) con estas columnas: {', '.join(columnas_plan)}\n")
    else:
        partes.append("No hay Plan de Ventas cargado — si la pregunta lo necesita, ignóralo y trabaja solo con 'df'.\n")
    partes.append(
        "\nReglas estrictas:\n"
        "- Usa ÚNICAMENTE columnas que existan en 'df' o 'plan' — nunca inventes una columna.\n"
        "- Guarda el resultado final en una variable llamada 'resultado', que debe ser un "
        "DataFrame de pandas (no una Serie, no un número suelto — envuélvelo en un DataFrame "
        "si hace falta).\n"
        "- No leas ni escribas archivos, no hagas peticiones de red, no uses input().\n"
        "- No hay datos de fechas futuras reales — si piden una 'proyección', calcúlala como "
        "un promedio/tendencia simple de los datos históricos existentes y dilo en el nombre "
        "de una columna del resultado (ej. 'Proyección (promedio histórico)'), nunca inventes "
        "cifras de la nada.\n\n"
        f"Pregunta del usuario: {prompt_usuario.strip()}"
    )
    return ''.join(partes)


def generar_codigo_analisis(prompt_usuario: str, api_keys: dict, columnas_df: list,
                             tiene_plan: bool, columnas_plan: list) -> tuple:
    """Devuelve (codigo, proveedor_usado)."""
    if not prompt_usuario or not prompt_usuario.strip():
        raise ErrorIA("Escribe qué quieres calcular antes de generar.")

    instrucciones = _instrucciones_codigo(prompt_usuario, columnas_df, tiene_plan, columnas_plan)
    resultado, proveedor = _llamar_ia_con_fallback(instrucciones, _SCHEMA_CODIGO, api_keys)
    codigo = resultado.get('codigo', '')
    if not codigo or not codigo.strip():
        raise ErrorIA("La IA no devolvió código, intenta reformular la petición.")
    return codigo.strip(), proveedor


def _builtins_seguros() -> dict:
    permitidos = [
        'len', 'range', 'sum', 'min', 'max', 'sorted', 'enumerate', 'zip', 'map', 'filter',
        'dict', 'list', 'tuple', 'set', 'frozenset', 'str', 'int', 'float', 'bool', 'abs',
        'round', 'True', 'False', 'None', 'isinstance', 'Exception', 'ValueError', 'TypeError',
        'KeyError', 'IndexError', 'reversed', 'any', 'all',
    ]
    return {nombre: __builtins__[nombre] if isinstance(__builtins__, dict) else getattr(__builtins__, nombre)
            for nombre in permitidos}


class _TiempoAgotado(Exception):
    """Interna: la usa el 'vigilante' de _ejecutar_en_hilo para cortar un
    bucle sin fin desde ADENTRO del código que se está ejecutando — un
    timeout de ThreadPoolExecutor por sí solo NO mata el hilo real, solo
    deja de esperarlo (y un `while True` se queda corriendo para siempre
    en segundo plano, comiendo CPU). Esto sí lo corta de verdad."""


def _ejecutar_en_hilo(codigo: str, df: pd.DataFrame, plan: pd.DataFrame, timeout_seg: float):
    inicio = time.time()

    def _vigilante(frame, evento, arg):
        if time.time() - inicio > timeout_seg:
            raise _TiempoAgotado()
        return _vigilante

    espacio = {
        '__builtins__': _builtins_seguros(),
        'pd': pd,
        'df': df.copy(),
        'plan': plan.copy() if plan is not None else pd.DataFrame(),
    }
    sys.settrace(_vigilante)
    try:
        exec(codigo, espacio)  # noqa: S102 — namespace restringido, ver _builtins_seguros/_PATRONES_PROHIBIDOS
    finally:
        sys.settrace(None)
    return espacio.get('resultado')


def ejecutar_codigo_pandas(codigo: str, df: pd.DataFrame, plan: pd.DataFrame = None) -> pd.DataFrame:
    """Corre el código que devolvió la IA en un entorno restringido: sin
    imports, sin acceso a archivos/red/sistema, con límite de tiempo real
    (un 'vigilante' interrumpe el código desde adentro, no solo deja de
    esperarlo), y solo puede ver copias de 'df' y 'plan'. Devuelve el
    DataFrame resultante o lanza ErrorIA con un mensaje claro."""
    bajo = codigo.lower()
    for patron in _PATRONES_PROHIBIDOS:
        if patron in bajo:
            raise ErrorIA(f"El código generado usa algo no permitido ('{patron.strip()}'), intenta reformular la petición.")

    pool = ThreadPoolExecutor(max_workers=1)
    futuro = pool.submit(_ejecutar_en_hilo, codigo, df, plan, _TIMEOUT_CODIGO_SEG)
    try:
        # Margen extra sobre _TIMEOUT_CODIGO_SEG: le da tiempo al vigilante
        # (que revisa entre líneas de Python) a notar el timeout y cortar
        # antes de que este result() se rinda de esperar.
        resultado = futuro.result(timeout=_TIMEOUT_CODIGO_SEG + 2)
    except (FuturoTimeoutError, _TiempoAgotado):
        raise ErrorIA(f"El cálculo tardó más de {_TIMEOUT_CODIGO_SEG}s y se canceló — intenta una pregunta más simple.")
    except Exception as e:
        raise ErrorIA(f"El código generado falló al ejecutarse, intenta reformular la petición ({e}).") from e
    finally:
        # wait=False: si el vigilante no alcanzó a cortar el hilo a tiempo
        # (ej. quedó atrapado en una sola llamada larga de C, donde el
        # vigilante no puede interrumpir), no nos quedamos colgados
        # esperándolo — el hilo sigue en el fondo, pero ya devolvimos el
        # error al usuario en vez de trabar la página.
        pool.shutdown(wait=False)

    if not isinstance(resultado, pd.DataFrame):
        raise ErrorIA("La IA no dejó un resultado en formato de tabla ('resultado'), intenta reformular la petición.")
    if resultado.empty:
        raise ErrorIA("El cálculo no arrojó ninguna fila con tus datos actuales.")

    if len(resultado) > _MAX_FILAS_RESULTADO:
        resultado = resultado.head(_MAX_FILAS_RESULTADO)

    return resultado
