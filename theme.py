"""
theme.py
--------
Sistema de diseño de la Consola Ejecutiva — "Cauce Comercial", con soporte
de modo claro / oscuro conmutable desde la propia app.

Uso en app.py:

    import theme
    st.session_state.setdefault("modo_tema", "claro")
    theme.inyectar_css(st.session_state["modo_tema"])
    modo = theme.render_header(st.session_state["modo_tema"])  # dibuja título + interruptor y lo lee

El resto de funciones (ledger_tape, section_title, periodo_banner, kpi_row,
signo_delta, render_footer, plotly_layout_kwargs) no cambian de firma — no
hay que tocar vistas/.

Compatibilidad: las vistas que usan constantes de color directas
(theme.COLOR_ACCENT, theme.COLOR_POSITIVE, theme.COLOR_PERIODO_A/B, etc.)
siguen funcionando: se resuelven dinámicamente contra el modo activo
guardado en st.session_state.
"""

import html as _html

import streamlit as st

# --------------------------------------------------------------------------
# TOKENS DE DISEÑO — modo claro y modo oscuro
# --------------------------------------------------------------------------
TOKENS = {
    "claro": {
        "bg": "#F4F0E6", "surface": "#FDFCFA", "surface_raised": "#F8F4EC",
        "border": "#DED6C6", "ledger_line": "#A99B7E",
        "text": "#2B2620", "text_muted": "#7A7060",
        "accent": "#3D6B4E", "accent_strong": "#4C8562",
        "positive": "#3F7A54", "negative": "#B85A3E", "focus": "#D89A46",
        "periodo_a": "#C97B4A", "periodo_b": "#4C8562",
    },
    "oscuro": {
        "bg": "#1C1912", "surface": "#242019", "surface_raised": "#2B261D",
        "border": "#3A3325", "ledger_line": "#5C5138",
        "text": "#EDE8DB", "text_muted": "#A69C86",
        "accent": "#5FA47A", "accent_strong": "#74BA8F",
        "positive": "#6CB58C", "negative": "#D98A5E", "focus": "#E0AE5A",
        "periodo_a": "#D98A5E", "periodo_b": "#74BA8F",
    },
}

# Mapa de constantes de color "planas" (compatibilidad con vistas/ existentes)
# hacia la clave correspondiente en TOKENS.
_COLOR_ATTR_MAP = {
    "COLOR_BG": "bg", "COLOR_SURFACE": "surface", "COLOR_SURFACE_RAISED": "surface_raised",
    "COLOR_BORDER": "border", "COLOR_LEDGER_LINE": "ledger_line", "COLOR_TEXT": "text",
    "COLOR_TEXT_MUTED": "text_muted", "COLOR_ACCENT": "accent", "COLOR_ACCENT_STRONG": "accent_strong",
    "COLOR_POSITIVE": "positive", "COLOR_NEGATIVE": "negative", "COLOR_FOCUS": "focus",
    "COLOR_PERIODO_A": "periodo_a", "COLOR_PERIODO_B": "periodo_b",
}


def _modo_actual() -> str:
    return st.session_state.get("modo_tema", "claro")


def __getattr__(name):
    # PEP 562: permite theme.COLOR_ACCENT, theme.COLOR_PERIODO_A, etc.,
    # resolviéndolos contra el modo (claro/oscuro) activo en la sesión.
    if name in _COLOR_ATTR_MAP:
        modo = _modo_actual()
        return TOKENS.get(modo, TOKENS["claro"])[_COLOR_ATTR_MAP[name]]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def plotly_layout_kwargs() -> dict:
    """Kwargs de layout para pasarle a fig.update_layout(**...) en cualquier
    gráfico Plotly de la app, para que respete el modo claro/oscuro activo
    en vez de quedar fijo en un template. Solo toca colores/tipografía, no
    la estructura de los gráficos."""
    t = TOKENS.get(_modo_actual(), TOKENS["claro"])
    # automargin=True: sin template (antes era "plotly_dark", que lo trae
    # incluido por defecto), Plotly no reserva espacio para las etiquetas
    # de los ejes si el gráfico pide un margen chico (varios gráficos usan
    # margin=dict(l=0, ...)) — sin esto, las etiquetas quedan cortadas y
    # no se ven (ej. nombres de vendedor, % de cumplimiento).
    eje = dict(gridcolor=t["border"], linecolor=t["border"], zerolinecolor=t["border"], automargin=True)
    return dict(
        paper_bgcolor=t["surface"],
        plot_bgcolor=t["surface"],
        font=dict(family="Inter, sans-serif", color=t["text"]),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=t["text"])),
        xaxis=eje,
        yaxis=eje,
    )


def inyectar_css(modo: str = "claro"):
    """Inyecta la hoja de estilos completa de la app para el modo dado.
    Llamar una sola vez, justo después de st.set_page_config()."""
    t = TOKENS.get(modo, TOKENS["claro"])
    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Lora:wght@500;600&family=Inter:wght@400;500;600;700&display=swap');

        :root {{
            --bg: {t['bg']}; --surface: {t['surface']}; --surface-raised: {t['surface_raised']};
            --border: {t['border']}; --ledger-line: {t['ledger_line']};
            --text: {t['text']}; --text-muted: {t['text_muted']};
            --accent: {t['accent']}; --accent-strong: {t['accent_strong']};
            --positive: {t['positive']}; --negative: {t['negative']}; --focus: {t['focus']};
            --periodo-a: {t['periodo_a']}; --periodo-b: {t['periodo_b']};
        }}

        html, body, .stApp {{ background-color: var(--bg); color: var(--text); font-family: 'Inter', -apple-system, sans-serif; }}
        .stApp * {{ letter-spacing: 0.001em; }}
        h1, h2, h3 {{ font-family: 'Lora', Georgia, serif; letter-spacing: -0.005em; }}
        h1 {{ font-weight: 600 !important; }}

        .app-header {{ margin-bottom: 4px; }}
        .app-header h1 {{ font-size: 2.05rem; margin-bottom: 2px; color: var(--text); display: flex; align-items: center; gap: 12px; }}
        .app-header .marca-icono {{
            display: inline-flex; align-items: center; justify-content: center; width: 40px; height: 40px;
            border-radius: 50%; background: var(--surface); border: 2px solid var(--accent);
        }}
        .app-header .marca-icono::before {{ content: ""; width: 14px; height: 2px; background: var(--accent); }}
        .app-subtitulo {{
            font-family: 'Inter', sans-serif; font-size: 0.78rem; font-weight: 600; text-transform: uppercase;
            letter-spacing: 0.14em; color: var(--text-muted); margin: 0 0 16px 52px;
        }}

        .ledger-tape {{ position: relative; height: 16px; margin: 0 0 26px 0; }}
        .ledger-tape::before {{ content: ""; position: absolute; left: 0; right: 0; top: 7px; height: 1px; background: var(--border); }}
        .ledger-tape .marcas {{ position: absolute; inset: 0; display: flex; justify-content: space-between; }}
        .ledger-tape .marcas span {{ width: 1px; background: var(--ledger-line); }}
        .ledger-tape .marcas span:nth-child(odd) {{ height: 14px; }}
        .ledger-tape .marcas span:nth-child(even) {{ height: 9px; align-self: flex-start; }}
        .ledger-tape.compacta {{ height: 10px; margin: 18px 0; opacity: 0.6; }}
        .ledger-tape.compacta .marcas span:nth-child(odd) {{ height: 10px; }}
        .ledger-tape.compacta .marcas span:nth-child(even) {{ height: 6px; }}

        .sub-seccion {{
            display: flex; align-items: center; gap: 9px; font-family: 'Lora', serif; font-size: 1.15rem;
            font-weight: 700; color: var(--text); border-bottom: 1px solid var(--border); padding-bottom: 9px; margin: 22px 0 16px 0;
        }}
        .sub-seccion::before {{ content: ""; width: 7px; height: 7px; flex-shrink: 0; background: var(--accent); border-radius: 50%; }}

        .periodo-header {{
            font-family: 'Inter', sans-serif; font-size: 0.95rem; font-weight: 600; color: var(--text);
            background: var(--surface); padding: 12px 16px; border-radius: 6px; margin-bottom: 22px;
            border: 1px solid var(--border); border-left: 3px solid var(--accent);
        }}

        [data-testid="stMetric"] {{ background: var(--surface); padding: 16px 18px; border-radius: 10px; border: 1px solid var(--border); border-left: 3px solid var(--accent); }}
        [data-testid="stMetricLabel"] {{ font-family: 'Inter', sans-serif !important; font-size: 0.72rem !important; font-weight: 600 !important; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-muted) !important; }}
        [data-testid="stMetricValue"] {{ font-family: 'Lora', serif !important; font-weight: 600 !important; color: var(--text) !important; font-size: 1.55rem !important; }}
        [data-testid="stMetricDelta"] {{ font-family: 'Inter', sans-serif !important; font-size: 0.82rem !important; }}

        .kpi-grid {{ display: grid; grid-template-columns: repeat(var(--kpi-cols, 4), 1fr); gap: 12px; margin-bottom: 4px; }}
        .kpi-card {{ background: var(--surface); border: 1px solid var(--border); border-left: 3px solid var(--accent); border-radius: 10px; padding: 14px 16px; }}
        .kpi-card .kpi-label {{ font-family: 'Inter', sans-serif; font-size: 0.68rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-muted); margin-bottom: 6px; }}
        .kpi-card .kpi-valor {{ font-family: 'Lora', serif; font-weight: 600; color: var(--text); font-size: 1.5rem; line-height: 1.2; }}
        .kpi-card .kpi-delta {{ font-family: 'Inter', sans-serif; font-size: 0.78rem; margin-top: 5px; font-weight: 600; }}
        .kpi-card .kpi-delta.pos {{ color: var(--positive); }}
        .kpi-card .kpi-delta.neg {{ color: var(--negative); }}
        .kpi-card .kpi-delta.neutro {{ color: var(--text-muted); }}

        [data-testid="stExpander"] {{ background-color: var(--surface); border: 1px solid var(--border); border-radius: 10px; }}
        .streamlit-expanderHeader {{ background-color: var(--surface) !important; border-radius: 10px; font-weight: 600 !important; }}

        /* Streamlit 1.60 dejó de usar [data-baseweb="tab"/"select"] — ahora
           usa componentes react-aria (stTab, stSelectbox con role="tab" /
           role="combobox"). Los selectores viejos con data-baseweb nunca
           calzaban, así que estos elementos quedaban con el color nativo
           de Streamlit (fijo en claro) en vez del nuestro. */
        [data-testid="stTabs"] [role="tab"] {{ height: 52px; font-size: 1.1rem; font-weight: 700; color: var(--text-muted) !important; border-radius: 6px 6px 0 0; padding: 0 18px; }}
        [data-testid="stTabs"] [role="tab"][aria-selected="true"] {{ color: var(--text) !important; border-bottom: 4px solid var(--accent) !important; }}
        [data-testid="stTabs"] [role="tablist"] {{ gap: 6px; border-bottom: 2px solid var(--accent); width: 100%; opacity: 1; }}
        [data-testid="stTabs"] [role="tab"] p {{ font-size: 1.1rem !important; }}

        .stButton button, .stDownloadButton button {{ background-color: var(--surface); color: var(--text); border: 1px solid var(--border); border-radius: 6px; font-weight: 600; transition: border-color 0.15s ease, color 0.15s ease; }}
        .stButton button:hover, .stDownloadButton button:hover {{ border-color: var(--accent); color: var(--accent-strong); }}

        [data-testid="stFileUploaderDropzone"] {{ background: var(--surface); border: 1px dashed var(--border) !important; border-radius: 10px; }}
        [data-testid="stFileUploaderDropzone"]:hover {{ border-color: var(--accent) !important; }}

        [data-testid="stSelectbox"] input {{
            background-color: var(--surface) !important; color: var(--text) !important;
        }}
        [data-testid="stSelectbox"] [role="group"] {{
            background-color: var(--surface) !important; border-color: var(--border) !important;
        }}
        /* st.multiselect todavía usa BaseWeb (data-baseweb="select"), a
           diferencia de st.selectbox que migró a react-aria — necesita su
           propio selector. */
        [data-testid="stMultiSelect"] div[data-baseweb="select"] > div {{
            background-color: var(--surface) !important; border-color: var(--border) !important;
        }}
        [data-testid="stMultiSelect"] input {{ color: var(--text) !important; }}
        /* El listado desplegable (opciones) es un portal fuera de .stApp,
           igual que el popover — cubre tanto el combobox nuevo (role=listbox)
           como el menú de BaseWeb (data-baseweb="menu"). */
        [role="listbox"], [data-baseweb="menu"], [data-baseweb="popover"] {{ background: var(--surface) !important; border: 1px solid var(--border) !important; color: var(--text) !important; }}
        [role="option"], [data-baseweb="menu"] li {{ background: var(--surface) !important; color: var(--text) !important; }}
        [role="option"]:hover, [role="option"][aria-selected="true"], [data-baseweb="menu"] li:hover {{ background: var(--surface-raised) !important; }}

        .stTextInput input {{ background-color: var(--surface); border-color: var(--border); color: var(--text); }}

        *:focus-visible {{ outline: 2px solid var(--focus) !important; outline-offset: 2px; }}
        [data-testid="stDataFrame"] {{ border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }}

        /* ---------- Barra superior nativa de Streamlit (Deploy / menú ⋮) ---------- */
        [data-testid="stHeader"] {{ background: transparent; }}
        [data-testid="stAppDeployButton"] button, [data-testid="stMainMenuButton"] {{
            color: var(--text) !important; background: transparent !important;
        }}

        .app-footer {{ margin-top: 34px; padding-top: 12px; border-top: 1px solid var(--border); font-size: 0.72rem; color: var(--text-muted); display: flex; justify-content: space-between; flex-wrap: wrap; gap: 6px; }}

        /* ---------- Interruptor de modo (st.toggle) ---------- */
        [data-testid="stToggle"] {{ display: flex; justify-content: flex-end; }}

        /* ---------- Barra de control (contenedor con borde nativo) ---------- */
        [data-testid="stVerticalBlockBorderWrapper"] {{
            background: var(--surface); border: 1px solid var(--border) !important;
            border-radius: 10px;
        }}
        .control-bar-info {{ font-size: 0.92rem; color: var(--text); display: flex; align-items: center; height: 100%; }}
        .control-bar-info b {{ font-weight: 600; }}
        .periodo-dot {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin: 0 5px 0 10px; }}
        .periodo-dot:first-of-type {{ margin-left: 6px; }}
        .periodo-dot.a {{ background: var(--periodo-a); }}
        .periodo-dot.b {{ background: var(--periodo-b); }}

        /* ---------- st.segmented_control (toggle Vista/Comparar, píldoras de Año/Mes) ----------
           Ojo: el wrapper real tiene testid "stButtonGroup", no
           "stSegmentedControl" (ese testid no existe en esta versión de
           Streamlit) — por eso esto nunca calzaba antes. Selección única
           (Vista, Año) marca el botón con aria-checked="true"; selección
           múltiple (Mes(es)) lo marca con aria-pressed="true" en su lugar
           — hay que cubrir ambos o los meses elegidos no se remarcan. */
        [data-testid="stButtonGroup"] label {{ font-weight: 600 !important; }}
        [data-testid="stButtonGroup"] button {{
            background-color: var(--surface) !important; color: var(--text) !important;
            border-color: var(--border) !important;
        }}
        [data-testid="stButtonGroup"] button[aria-checked="true"],
        [data-testid="stButtonGroup"] button[aria-pressed="true"] {{
            background-color: var(--surface) !important; color: var(--accent-strong) !important;
            border: 2px solid var(--accent) !important; font-weight: 700 !important;
        }}

        /* ---------- Botón "Editar" (st.popover) ---------- */
        [data-testid="stPopover"] > div > button {{
            background-color: var(--surface-raised); border: 1px solid var(--border);
            color: var(--text); font-weight: 600; border-radius: 6px;
        }}
        [data-testid="stPopover"] > div > button:hover {{ border-color: var(--accent); color: var(--accent-strong); }}

        /* stPopoverBody se renderiza en un portal fuera de .stApp, así que
           el color: var(--text) heredado de html/body/.stApp no le llega
           — hay que fijarlo acá explícitamente o queda con el tema nativo
           de Streamlit (que sigue el modo claro/oscuro del sistema
           operativo, no nuestro interruptor). */
        [data-testid="stPopoverBody"] {{
            background: var(--surface) !important; border: 1px solid var(--border) !important;
            color: var(--text) !important;
        }}
        [data-testid="stPopoverBody"] * {{ color: var(--text); }}
        [data-testid="stPopoverBody"] [data-testid="stCaptionContainer"] {{ color: var(--text-muted) !important; }}

        /* ---------- Etiquetas de widgets (selectbox, multiselect, etc.) ---------- */
        [data-testid="stWidgetLabel"] p {{ color: var(--text) !important; }}
        [data-testid="stCaptionContainer"] {{ color: var(--text-muted) !important; }}

        /* ---------- Uploader de archivos: texto de instrucciones ---------- */
        [data-testid="stFileUploaderDropzoneInstructions"] {{ color: var(--text) !important; }}
        [data-testid="stFileUploaderDropzoneInstructions"] * {{ color: inherit !important; }}
        [data-testid="stFileUploaderDropzoneInstructions"] small {{ color: var(--text-muted) !important; }}

        /* ---------- Tablas (st.dataframe): el grid interno se dibuja en
           canvas y sigue el tema nativo de Streamlit (fijado en modo claro
           vía .streamlit/config.toml); esto solo cubre el marco/scrollbar. ---------- */
        [data-testid="stDataFrame"] {{ background: var(--surface); }}
        </style>
    """, unsafe_allow_html=True)


def render_header(modo_actual: str = "claro") -> str:
    """Encabezado de marca: título + subtítulo + interruptor claro/oscuro en
    la misma fila + cinta (firma visual). Devuelve el modo activo luego de
    leer el interruptor (puede haber cambiado en este mismo rerun)."""
    col_titulo, col_switch = st.columns([6, 1])
    with col_titulo:
        st.markdown(
            '<div class="app-header"><h1><span class="marca-icono"></span>'
            'Cauce Comercial</h1></div>'
            '<div class="app-subtitulo">Business Intelligence · Ventas &amp; Rendimiento Comercial</div>',
            unsafe_allow_html=True
        )
    with col_switch:
        oscuro = st.toggle(
            "Modo oscuro", value=(modo_actual == "oscuro"), key="switch_modo_tema"
        )
    modo_nuevo = "oscuro" if oscuro else "claro"
    st.session_state["modo_tema"] = modo_nuevo
    ledger_tape()
    return modo_nuevo


def ledger_tape(compacta: bool = False):
    clase = "ledger-tape compacta" if compacta else "ledger-tape"
    marcas = "".join("<span></span>" for _ in range(14))
    st.markdown(f'<div class="{clase}"><div class="marcas">{marcas}</div></div>', unsafe_allow_html=True)


def section_title(texto: str):
    st.markdown(f'<div class="sub-seccion">{texto}</div>', unsafe_allow_html=True)


def periodo_banner(texto: str):
    st.markdown(f'<div class="periodo-header">📌 {texto}</div>', unsafe_allow_html=True)


def kpi_row(items: list):
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
    if delta_pct > 0:
        return "pos"
    if delta_pct < 0:
        return "neg"
    return "neutro"


def render_footer(nombre_archivo: str = None, filas: int = None):
    izquierda = "Cauce Comercial · procesado localmente en tu navegador"
    derecha = ""
    if nombre_archivo:
        derecha = _html.escape(nombre_archivo)
        if filas is not None:
            derecha += f" · {filas:,} filas"
    st.markdown(
        f'<div class="app-footer"><span>{izquierda}</span><span>{derecha}</span></div>',
        unsafe_allow_html=True
    )
