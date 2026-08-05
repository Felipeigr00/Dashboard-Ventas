"""
theme.py
--------
Sistema de diseño de la Consola Ejecutiva. Centraliza la paleta de colores,
tipografías y componentes visuales reutilizables para que el resto de la app
(app.py y los módulos de vistas/) no repitan HTML/CSS suelto.

Paleta — "Espresso Ledger":
  Fondo casi negro con base cálida (espresso), acentos en caramelo tostado
  (no ámbar brillante) y verdes/terracotas apagados para variaciones
  positivas/negativas. Números en tipografía monoespaciada tipo "libro
  contable" para transmitir precisión financiera.

Tipografías:
  - Fraunces (serif editorial): SOLO para el título principal y como marca
    de las secciones (uso restringido, es el "acento" tipográfico).
  - Inter: texto de interfaz, labels, botones, tablas.
  - IBM Plex Mono: cifras grandes en las tarjetas KPI (venta, kilos, etc.)

Firma visual — "cinta de libro mayor":
  Una regla horizontal con marcas verticales cortas/largas alternadas,
  como la columna de un libro contable. Vive justo bajo el header y
  reaparece (más discreta) como separador entre bloques grandes.

v2: agrega kpi_row()/kpi_card() — tarjetas de indicador en HTML propio en
vez de st.metric(), para poder usar los colores de marca (verde salvia /
terracota) en las variaciones en vez del verde/rojo genérico de Streamlit.
Los usos existentes de st.metric() se pueden dejar tal cual: nada de esto
rompe compatibilidad, es una opción adicional para adoptar donde convenga.
"""

import html as _html

import streamlit as st

# --------------------------------------------------------------------------
# TOKENS DE DISEÑO
# --------------------------------------------------------------------------
COLOR_BG = "#0B0A08"
COLOR_SURFACE = "#161310"
COLOR_SURFACE_RAISED = "#1D1812"
COLOR_BORDER = "#2C2419"
COLOR_LEDGER_LINE = "#6B5637"    # marcas de la cinta de libro mayor
COLOR_TEXT = "#F1EAD9"
COLOR_TEXT_MUTED = "#9A8D77"
COLOR_ACCENT = "#B9793B"        # caramelo tostado — color de marca
COLOR_ACCENT_STRONG = "#D89552"  # hover / énfasis
COLOR_POSITIVE = "#7C9A78"      # verde salvia apagado
COLOR_NEGATIVE = "#B25C46"      # terracota apagado
COLOR_FOCUS = "#E8B54D"         # foco de teclado (accesibilidad)

# Colores fijos para Periodo A / Periodo B en los gráficos (se mantienen
# estables sin importar qué filtros se apliquen)
COLOR_PERIODO_A = "#4F8FBF"   # azul apagado
COLOR_PERIODO_B = COLOR_ACCENT  # caramelo — coherente con la marca


def inyectar_css():
    """Inyecta la hoja de estilos completa de la app. Llamar una sola vez,
    justo después de st.set_page_config()."""
    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500;600&display=swap');

        :root {{
            --bg: {COLOR_BG};
            --surface: {COLOR_SURFACE};
            --surface-raised: {COLOR_SURFACE_RAISED};
            --border: {COLOR_BORDER};
            --ledger-line: {COLOR_LEDGER_LINE};
            --text: {COLOR_TEXT};
            --text-muted: {COLOR_TEXT_MUTED};
            --accent: {COLOR_ACCENT};
            --accent-strong: {COLOR_ACCENT_STRONG};
            --positive: {COLOR_POSITIVE};
            --negative: {COLOR_NEGATIVE};
            --focus: {COLOR_FOCUS};
        }}

        /* ---------- Base ---------- */
        html, body, .stApp {{
            background-color: var(--bg);
            color: var(--text);
            font-family: 'Inter', -apple-system, sans-serif;
        }}
        .stApp * {{ letter-spacing: 0.001em; }}

        h1, h2, h3 {{ font-family: 'Fraunces', Georgia, serif; letter-spacing: -0.01em; }}
        h1 {{ font-weight: 600 !important; }}

        /* ---------- Encabezado de marca ---------- */
        .app-header {{ margin-bottom: 4px; }}
        .app-header h1 {{
            font-size: 2.1rem; margin-bottom: 2px; color: var(--text);
            display: flex; align-items: center; gap: 12px;
        }}
        .app-header .marca-icono {{
            display: inline-flex; align-items: center; justify-content: center;
            width: 40px; height: 40px; border-radius: 10px;
            background: var(--surface-raised); border: 1px solid var(--border);
            font-size: 1.3rem;
        }}
        .app-subtitulo {{
            font-family: 'Inter', sans-serif; font-size: 0.78rem; font-weight: 600;
            text-transform: uppercase; letter-spacing: 0.14em; color: var(--text-muted);
            margin: 0 0 16px 52px;
        }}

        /* ---------- Firma visual: cinta de libro mayor ---------- */
        .ledger-tape {{
            position: relative; height: 16px; margin: 0 0 26px 0;
        }}
        .ledger-tape::before {{
            content: ""; position: absolute; left: 0; right: 0; top: 7px;
            height: 1px; background: var(--border);
        }}
        .ledger-tape .marcas {{
            position: absolute; inset: 0; display: flex; justify-content: space-between;
        }}
        .ledger-tape .marcas span {{
            width: 1px; background: var(--ledger-line);
        }}
        .ledger-tape .marcas span:nth-child(odd) {{ height: 14px; }}
        .ledger-tape .marcas span:nth-child(even) {{ height: 9px; align-self: flex-start; }}
        .ledger-tape.compacta {{ height: 10px; margin: 18px 0; opacity: 0.6; }}
        .ledger-tape.compacta .marcas span:nth-child(odd) {{ height: 10px; }}
        .ledger-tape.compacta .marcas span:nth-child(even) {{ height: 6px; }}

        /* ---------- Título de sección ---------- */
        .sub-seccion {{
            display: flex; align-items: center; gap: 9px;
            font-family: 'Inter', sans-serif; font-size: 0.82rem; font-weight: 700;
            text-transform: uppercase; letter-spacing: 0.09em; color: var(--text);
            border-bottom: 1px solid var(--border);
            padding-bottom: 9px; margin: 22px 0 16px 0;
        }}
        .sub-seccion::before {{
            content: ""; width: 7px; height: 7px; flex-shrink: 0;
            background: var(--accent); border-radius: 1.5px;
        }}

        /* ---------- Banner de periodo ---------- */
        .periodo-header {{
            font-family: 'Inter', sans-serif; font-size: 0.95rem; font-weight: 600;
            color: var(--text); background: var(--surface);
            padding: 12px 16px; border-radius: 6px; margin-bottom: 22px;
            border: 1px solid var(--border); border-left: 3px solid var(--accent);
        }}

        /* ---------- Tarjetas KPI (st.metric nativo, se deja por compatibilidad) ---------- */
        [data-testid="stMetric"] {{
            background: var(--surface);
            padding: 16px 18px; border-radius: 8px;
            border: 1px solid var(--border);
            border-left: 3px solid var(--accent);
        }}
        [data-testid="stMetricLabel"] {{
            font-family: 'Inter', sans-serif !important; font-size: 0.72rem !important;
            font-weight: 600 !important; text-transform: uppercase; letter-spacing: 0.08em;
            color: var(--text-muted) !important;
        }}
        [data-testid="stMetricValue"] {{
            font-family: 'IBM Plex Mono', monospace !important; font-weight: 600 !important;
            color: var(--text) !important; font-size: 1.55rem !important;
        }}
        [data-testid="stMetricDelta"] {{ font-family: 'IBM Plex Mono', monospace !important; font-size: 0.82rem !important; }}

        /* ---------- Tarjetas KPI propias (kpi_card / kpi_row) ---------- */
        .kpi-grid {{
            display: grid; grid-template-columns: repeat(var(--kpi-cols, 4), 1fr);
            gap: 12px; margin-bottom: 4px;
        }}
        .kpi-card {{
            background: var(--surface); border: 1px solid var(--border);
            border-left: 3px solid var(--accent); border-radius: 8px;
            padding: 14px 16px;
        }}
        .kpi-card .kpi-label {{
            font-family: 'Inter', sans-serif; font-size: 0.68rem; font-weight: 600;
            text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-muted);
            margin-bottom: 6px;
        }}
        .kpi-card .kpi-valor {{
            font-family: 'IBM Plex Mono', monospace; font-weight: 600;
            color: var(--text); font-size: 1.5rem; line-height: 1.2;
        }}
        .kpi-card .kpi-delta {{
            font-family: 'IBM Plex Mono', monospace; font-size: 0.78rem;
            margin-top: 5px; font-weight: 600;
        }}
        .kpi-card .kpi-delta.pos {{ color: var(--positive); }}
        .kpi-card .kpi-delta.neg {{ color: var(--negative); }}
        .kpi-card .kpi-delta.neutro {{ color: var(--text-muted); }}

        /* ---------- Expanders ---------- */
        [data-testid="stExpander"] {{
            background-color: var(--surface); border: 1px solid var(--border);
            border-radius: 8px;
        }}
        .streamlit-expanderHeader {{
            background-color: var(--surface) !important; border-radius: 8px;
            font-weight: 600 !important;
        }}

        /* ---------- Tabs ---------- */
        .stTabs [data-baseweb="tab-list"] {{ gap: 6px; border-bottom: 1px solid var(--border); }}
        .stTabs [data-baseweb="tab"] {{
            height: 44px; font-size: 0.95rem; font-weight: 600; color: var(--text-muted);
            border-radius: 6px 6px 0 0;
        }}
        .stTabs [aria-selected="true"] {{
            color: var(--text) !important;
            border-bottom: 2px solid var(--accent) !important;
        }}

        /* ---------- Botones ---------- */
        .stButton button, .stDownloadButton button {{
            background-color: var(--surface); color: var(--text);
            border: 1px solid var(--border); border-radius: 6px;
            font-weight: 600; transition: border-color 0.15s ease, color 0.15s ease;
        }}
        .stButton button:hover, .stDownloadButton button:hover {{
            border-color: var(--accent); color: var(--accent-strong);
        }}

        /* ---------- Selects, inputs, file uploader ---------- */
        [data-testid="stFileUploaderDropzone"] {{
            background: var(--surface); border: 1px dashed var(--border) !important;
            border-radius: 8px;
        }}
        [data-testid="stFileUploaderDropzone"]:hover {{ border-color: var(--accent) !important; }}
        .stSelectbox div[data-baseweb="select"] > div, .stMultiSelect div[data-baseweb="select"] > div {{
            background-color: var(--surface); border-color: var(--border);
        }}
        .stTextInput input {{ background-color: var(--surface); border-color: var(--border); color: var(--text); }}

        /* ---------- Accesibilidad: foco de teclado visible ---------- */
        *:focus-visible {{ outline: 2px solid var(--focus) !important; outline-offset: 2px; }}

        /* ---------- Tablas ---------- */
        [data-testid="stDataFrame"] {{ border: 1px solid var(--border); border-radius: 6px; overflow: hidden; }}

        /* ---------- Pie de página ---------- */
        .app-footer {{
            margin-top: 34px; padding-top: 12px; border-top: 1px solid var(--border);
            font-size: 0.72rem; color: var(--text-muted); display: flex;
            justify-content: space-between; flex-wrap: wrap; gap: 6px;
        }}
        </style>
    """, unsafe_allow_html=True)


def render_header():
    """Encabezado de marca: título + subtítulo + cinta de libro mayor (firma visual)."""
    st.markdown(
        '<div class="app-header"><h1><span class="marca-icono">☕</span>'
        'Consola Ejecutiva · Dark Coffee BI</h1></div>'
        '<div class="app-subtitulo">Business Intelligence · Ventas &amp; Rendimiento Comercial</div>',
        unsafe_allow_html=True
    )
    ledger_tape()


def ledger_tape(compacta: bool = False):
    """La firma visual del sistema: una regla tipo columna de libro contable.
    Úsala bajo el header (default) o como separador discreto entre bloques
    grandes de contenido pasando compacta=True."""
    clase = "ledger-tape compacta" if compacta else "ledger-tape"
    marcas = "".join("<span></span>" for _ in range(14))
    st.markdown(f'<div class="{clase}"><div class="marcas">{marcas}</div></div>', unsafe_allow_html=True)


def section_title(texto: str):
    """Título de sección con la marca visual del sistema (cuadradito de acento)."""
    st.markdown(f'<div class="sub-seccion">{texto}</div>', unsafe_allow_html=True)


def periodo_banner(texto: str):
    """Banner que muestra el/los periodo(s) analizado(s)."""
    st.markdown(f'<div class="periodo-header">📌 {texto}</div>', unsafe_allow_html=True)


def kpi_row(items: list):
    """
    Fila de tarjetas KPI con color de marca propio (reemplazo opcional de
    st.metric para las 4 métricas clave: Venta, Kilos, Ticket, Clientes).

    items: lista de dicts, cada uno:
      {
        "label": "Venta Total (A)",
        "valor": "$211.083.192 CLP",
        "delta": "+4.3% vs A",       # opcional
        "signo": "pos" | "neg" | "neutro",   # opcional, define el color del delta
      }

    Ejemplo de uso (reemplaza a kpi_a1.metric(...) etc.):
        theme.kpi_row([
            {"label": "Venta Total (A)", "valor": f"${v_a:,.0f} CLP"},
            {"label": "Volumen Kilos (A)", "valor": f"{k_a:,.0f} kg"},
            {"label": "Ticket Promedio (A)", "valor": f"${t_a:,.0f} CLP"},
            {"label": "Clientes Activos (A)", "valor": f"{c_a:,}"},
        ])
    """
    tarjetas = []
    for item in items:
        label = _html.escape(str(item.get("label", "")))
        valor = _html.escape(str(item.get("valor", "")))
        delta_html = ""
        if item.get("delta"):
            signo = item.get("signo", "neutro")
            delta_html = f'<div class="kpi-delta {signo}">{_html.escape(str(item["delta"]))}</div>'
        tarjetas.append(
            f'<div class="kpi-card"><div class="kpi-label">{label}</div>'
            f'<div class="kpi-valor">{valor}</div>{delta_html}</div>'
        )
    st.markdown(
        f'<div class="kpi-grid" style="--kpi-cols:{len(items)};">{"".join(tarjetas)}</div>',
        unsafe_allow_html=True
    )


def signo_delta(delta_pct: float) -> str:
    """Traduce un % de variación al signo de color esperado por kpi_row
    ('pos'/'neg'/'neutro'), evitando repetir este if/else en cada vista."""
    if delta_pct > 0:
        return "pos"
    if delta_pct < 0:
        return "neg"
    return "neutro"


def render_footer(nombre_archivo: str = None, filas: int = None):
    """Pie de página discreto con contexto de la sesión (qué archivo se
    cargó y cuántas filas), útil para que quien lee el dashboard sepa qué
    datos está viendo sin tener que desplazarse hacia arriba."""
    izquierda = "☕ Dark Coffee BI · procesado localmente en tu navegador"
    derecha = ""
    if nombre_archivo:
        derecha = _html.escape(nombre_archivo)
        if filas is not None:
            derecha += f" · {filas:,} filas"
    st.markdown(
        f'<div class="app-footer"><span>{izquierda}</span><span>{derecha}</span></div>',
        unsafe_allow_html=True
    )