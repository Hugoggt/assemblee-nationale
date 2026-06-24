"""
Assemblée Nationale — 17ème législature
Application Dash professionnelle

Lancement : python dash_app.py   (puis ouvrir http://localhost:8050)
Prérequis  : pip install dash dash-bootstrap-components
"""

import json
import re
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output, State, dash_table, no_update
import dash_bootstrap_components as dbc

# ─── CONSTANTS ────────────────────────────────────────────────────────────────

OUTPUT_DIR = Path(__file__).parent / "output"

POLITICAL_ORDER = [
    "LFI-NFP", "GDR", "VEC", "SOC", "ECOS", "LIOT",
    "DEM", "HOR", "EPR", "DR", "UDDPLR", "RN", "NI",
]

COLORS = {
    "RN":      "#003189", "DR":     "#1a3a6b", "EPR":    "#0066CC",
    "HOR":     "#FF8C00", "DEM":    "#E85D04", "LIOT":   "#228B22",
    "SOC":     "#C41E3A", "ECOS":   "#2d6a4f", "GDR":    "#8B0000",
    "LFI-NFP": "#CC0000", "VEC":    "#2CA02C", "UDDPLR": "#5B2C8C",
    "NI":      "#808080",
}

_INVALID_GROUPS = {"PO0", "PO847173"}

GROUP_FULL = {
    "RN":      "Rassemblement National",
    "DR":      "Droite Républicaine",
    "EPR":     "Ensemble pour la République",
    "HOR":     "Horizons & Indépendants",
    "DEM":     "Les Démocrates",
    "LIOT":    "Libertés, Indépendants, Outre-mer et Territoires",
    "SOC":     "Socialistes et apparentés",
    "ECOS":    "Écologiste et Social",
    "GDR":     "Gauche Démocrate et Républicaine",
    "LFI-NFP": "La France insoumise – Nouveau Front Populaire",
    "VEC":     "Les Verts",
    "UDDPLR":  "Union des Droites pour la République",
    "NI":      "Non inscrits",
}

GROUP_PRESIDENTS = {
    "RN":      "Marine Le Pen",
    "EPR":     "Gabriel Attal",
    "LFI-NFP": "Mathilde Panot",
    "SOC":     "Boris Vallaud",
    "DR":      "Laurent Wauquiez",
    "GDR":     "André Chassaigne",
    "DEM":     "Marc Fesneau",
    "HOR":     "Laurent Marcangeli",
    "ECOS":    "Cyrielle Chatelain",
    "LIOT":    "Bertrand Pancher",
    "UDDPLR":  "Nicolas Dupont-Aignan",
    "NI":      "—",
}

LEGISLATURE = {
    "dissolution":       "9 juin 2024",
    "elections":         "7 juillet 2024",
    "debut":             "18 juillet 2024",
    "fin_prevue":        "2029",
    "total_sieges":      577,
    "majorite_absolue":  289,
    "president_an":      "Yaël Braun-Pivet",
    "groupe_pres_an":    "EPR",
    "premier_ministre":  "Sébastien Lecornu",
    "debut_pm":          "mai 2025",
}

DOMTOM_CENTERS = {
    "Guadeloupe": {"lat": 16.17, "lon": -61.58, "zoom": 7.4},
    "Martinique":  {"lat": 14.65, "lon": -61.0,  "zoom": 8.0},
    "Guyane":      {"lat":  4.0,  "lon": -53.1,  "zoom": 4.0},
    "La Réunion":  {"lat": -21.1, "lon":  55.5,  "zoom": 7.4},
    "Mayotte":     {"lat": -12.8, "lon":  45.15, "zoom": 8.5},
}


# ─── DATA LOADING ─────────────────────────────────────────────────────────────

def _csv(name, **kw):
    p = OUTPUT_DIR / name
    return pd.read_csv(p, encoding="utf-8", **kw) if p.exists() else None


def load_deputes():
    df = _csv("deputes.csv", dtype={"id": str, "circonscription": str})
    if df is None:
        return pd.DataFrame()
    df["age"] = pd.to_numeric(df["age"], errors="coerce")
    df["nom_complet"] = (df["prenom"].fillna("") + " " + df["nom"].fillna("")).str.strip()
    return df[~df["groupe_abrev"].isin(_INVALID_GROUPS)]


def load_organes():
    p = OUTPUT_DIR / "organes.json"
    if not p.exists():
        return pd.DataFrame()
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    df = pd.DataFrame(data) if isinstance(data, list) else pd.DataFrame()
    if df.empty:
        return df
    df = df[~df["uid"].isin(_INVALID_GROUPS)]
    return df[df["libelle_abrev"].isin(POLITICAL_ORDER)]


def load_scrutins():
    df = _csv("scrutins_summary.csv")
    if df is None:
        return pd.DataFrame()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["adopte_bool"] = df["adopte"].astype(str).str.lower().str.replace("é", "e", regex=False).isin(["adopte", "true", "1"])
    df["titre_court"] = df["titre"].str[:90]
    return df


def load_votes_groupe():
    df = _csv("scrutins_votes_groupe.csv")
    if df is None:
        return pd.DataFrame()
    df = df[~df["groupe_ref"].isin(_INVALID_GROUPS)]
    for c in ["pour", "contre", "abstention"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    return df


def load_votes_depute():
    df = _csv("scrutins_votes_depute.csv",
              dtype={"scrutin_uid": str, "depute_ref": str, "vote": str})
    if df is None:
        return pd.DataFrame()
    return df[~df["groupe_ref"].isin(_INVALID_GROUPS)]


def load_dossiers():
    for name in ("dossiers_themes.csv", "dossiers.csv"):
        df = _csv(name)
        if df is not None:
            return df
    return None


def load_geo():
    url = ("https://raw.githubusercontent.com/gregoiredavid/"
           "france-geojson/master/departements.geojson")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except Exception:
        return None


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def gc(abrev: str) -> str:
    return COLORS.get(str(abrev), "#9ca3af")


def short_statut(s: str) -> str:
    if not s:
        return "—"
    sl = s.lower()
    if "promulgation" in sl or "mise en application" in sl:
        return "✅ Promulguée"
    if "commission mixte paritaire" in sl:
        return "🔄 CMP"
    if "conseil constitutionnel" in sl:
        return "⚖️ Cons. const."
    # "2ème assemblée saisie" → Sénat (l'AN est quasi toujours 1ère saisie)
    if "2" in sl and "assembl" in sl and "saisie" in sl:
        return "📘 Lecture Sénat"
    if "nouvelle lecture" in sl:
        return "🔁 Nouvelle lecture"
    if "deuxi" in sl and "lecture" in sl:
        return "🔄 2ème lecture"
    if "lecture unique" in sl:
        return "🔵 Lecture unique"
    if "1" in sl and "assembl" in sl and "saisie" in sl:
        return "🔵 Lecture AN"
    if "bat" in sl:     # "Débat"
        return "💬 Débat"
    if "travaux" in sl:
        return "📊 Travaux"
    return s[:35]


def group_badge(abrev: str, text: str = None):
    label = text or abrev
    return html.Span(label, style={
        "background": gc(abrev), "color": "white",
        "padding": "2px 9px", "borderRadius": "5px",
        "fontSize": "0.72rem", "fontWeight": "700",
        "letterSpacing": "0.02em", "whiteSpace": "nowrap",
        "display": "inline-block",
    })


def kpi_card(label, value, sub=None, color="#2563eb"):
    return html.Div([
        html.Div(label, className="kpi-label"),
        html.Div(str(value), className="kpi-value"),
        html.Div(sub, className="kpi-sub") if sub else None,
    ], className="kpi-card", style={"borderLeftColor": color})


def section_title(text: str):
    return html.Div(text, className="section-title")


def _dd(id_, options, value="Tous"):
    return dcc.Dropdown(
        id=id_,
        options=[{"label": o, "value": o} for o in options],
        value=value, clearable=False,
        style={"fontSize": "0.84rem"},
    )


def _table_style():
    return dict(
        style_table={"overflowX": "auto", "borderRadius": "10px"},
        style_header={
            "backgroundColor": "#f8f9fc", "fontWeight": "700",
            "fontSize": "0.68rem", "textTransform": "uppercase",
            "letterSpacing": "0.08em", "color": "#6b7280",
            "border": "none", "borderBottom": "2px solid #e5e7eb",
            "padding": "10px 14px",
        },
        style_cell={
            "fontFamily": "Inter, sans-serif", "fontSize": "0.83rem",
            "padding": "10px 14px", "border": "none",
            "borderBottom": "1px solid #f3f4f6", "textAlign": "left",
        },
        style_data_conditional=[
            {"if": {"state": "active"},
             "backgroundColor": "#eff6ff", "border": "none !important"},
            {"if": {"row_index": "odd"}, "backgroundColor": "#fafbfc"},
        ],
    )


# ─── CHART FUNCTIONS ──────────────────────────────────────────────────────────

def hemicycle_fig(deputes: pd.DataFrame) -> go.Figure:
    counts = deputes.groupby("groupe_abrev").size()
    all_groups = (
        [(g, int(counts[g])) for g in POLITICAL_ORDER if g in counts.index]
        + [(g, int(counts[g])) for g in counts.index if g not in POLITICAL_ORDER]
    )
    total = sum(n for _, n in all_groups)
    if total == 0:
        return go.Figure()

    n_rows = 10
    radii = np.linspace(1.5, 3.5, n_rows)
    weights = radii / radii.sum()

    fig = go.Figure()
    angle = np.pi

    for g, n in all_groups:
        if n == 0:
            continue
        span = np.pi * n / total
        end = angle - span
        spr = np.round(weights * n).astype(int)
        spr[-1] += n - spr.sum()
        xs, ys = [], []
        gap = max(0.04, span * 0.04)
        for r, ns in zip(radii, spr):
            if ns <= 0:
                continue
            for theta in np.linspace(angle - gap, end + gap, ns):
                xs.append(r * np.cos(theta))
                ys.append(r * np.sin(theta))

        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="markers",
            name=f"{g} ({n})",
            marker=dict(color=gc(g), size=6, line=dict(width=0.5, color="white")),
            hovertemplate=f"<b>{g}</b> — {GROUP_FULL.get(g, g)}<br>{n} sièges<extra></extra>",
        ))
        angle = end

    for r_arc in [radii[0] * 0.87, radii[-1] * 1.06]:
        t = np.linspace(np.pi, 0, 150)
        fig.add_trace(go.Scatter(
            x=r_arc * np.cos(t), y=r_arc * np.sin(t),
            mode="lines", line=dict(color="#e5e7eb", width=1),
            showlegend=False, hoverinfo="skip",
        ))

    fig.update_layout(
        height=420,
        legend=dict(
            orientation="v", x=1.02, y=0.98,
            font=dict(size=11, family="Inter"),
            bgcolor="rgba(255,255,255,0)",
        ),
        xaxis=dict(visible=False, range=[-4.0, 4.0]),
        yaxis=dict(visible=False, range=[-0.4, 4.0], scaleanchor="x", scaleratio=1),
        margin=dict(l=0, r=140, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def carte_fig(deputes: pd.DataFrame, geo: dict) -> go.Figure:
    if geo is None or deputes.empty:
        return go.Figure()

    rows = []
    for dept, sub in deputes.groupby("departement"):
        vc = sub["groupe_abrev"].value_counts()
        rows.append({
            "departement": dept,
            "dominant": vc.index[0],
            "n_total": len(sub),
            "detail": " · ".join(f"{g} {n}" for g, n in vc.items()),
        })
    ddf = pd.DataFrame(rows)

    geo_noms = {f["properties"]["nom"] for f in geo["features"]}
    metro = ddf[ddf["departement"].isin(geo_noms)].copy()

    fig = px.choropleth_mapbox(
        metro,
        geojson=geo,
        locations="departement",
        featureidkey="properties.nom",
        color="dominant",
        color_discrete_map=COLORS,
        hover_name="departement",
        custom_data=["dominant", "n_total", "detail"],
        mapbox_style="carto-positron",
        zoom=4.8,
        center={"lat": 46.5, "lon": 2.5},
        opacity=0.88,
    )
    fig.update_traces(
        hovertemplate=(
            "<b>%{hovertext}</b><br>"
            "<b>%{customdata[0]}</b> · %{customdata[1]} député(s)<br>"
            "<i>%{customdata[2]}</i><extra></extra>"
        ),
        marker_line_color="white",
        marker_line_width=0.7,
    )
    fig.update_layout(
        height=500, margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)", showlegend=False,
    )
    return fig


def seats_bar_fig(deputes: pd.DataFrame) -> go.Figure:
    counts = deputes.groupby("groupe_abrev").size().reset_index(name="n")
    counts["order"] = counts["groupe_abrev"].map(
        lambda a: POLITICAL_ORDER.index(a) if a in POLITICAL_ORDER else 99)
    counts = counts.sort_values("order")
    counts["full"] = counts["groupe_abrev"].map(lambda a: GROUP_FULL.get(a, a))

    fig = px.bar(
        counts, x="n", y="full", orientation="h",
        color="groupe_abrev", color_discrete_map=COLORS,
        text="n",
    )
    fig.update_traces(textposition="outside", textfont_size=11)
    fig.update_layout(
        showlegend=False, height=310,
        margin=dict(l=0, r=40, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            showgrid=False, zeroline=False,
            title=dict(text="Nombre de sièges", font=dict(size=11, family="Inter", color="#6b7280")),
            tickfont=dict(size=10, family="Inter", color="#9ca3af"),
        ),
        yaxis=dict(
            categoryorder="array",
            categoryarray=list(reversed(counts["full"].tolist())),
            tickfont=dict(size=12, family="Inter"),
            title=dict(text="Groupe politique", font=dict(size=11, family="Inter", color="#6b7280")),
        ),
    )
    return fig


# ─── STARTUP ──────────────────────────────────────────────────────────────────

print("Chargement des donnees...")
DEPUTES      = load_deputes()
ORGANES      = load_organes()
SCRUTINS     = load_scrutins()
VOTES_GROUPE = load_votes_groupe()
VOTES_DEPUTE = load_votes_depute()
DOSSIERS     = load_dossiers()
print("Chargement de la carte (gregoiredavid)...")
GEO = load_geo()
print("Pret.")


# ─── APP ──────────────────────────────────────────────────────────────────────

app = Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        "https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;1,400&display=swap",
    ],
    suppress_callback_exceptions=True,
    title="Assemblée Nationale — 17ème législature",
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)

server = app.server  # expose Flask server for production deployment


# ─── NAVIGATION ───────────────────────────────────────────────────────────────

NAV_PAGES = [
    ("/",           "Accueil"),
    ("/lois",       "Lois"),
    ("/deputes",    "Députés"),
    ("/groupes",    "Groupes"),
    ("/similarite", "Similarité"),
]


def navbar():
    return html.Header([
        html.Div(className="tricolor-bar"),
        dbc.Container([
            html.Div([
                html.A(
                    [html.Span("🏛️", style={"marginRight": "7px"}), "Assemblée Nationale"],
                    href="/", className="an-brand",
                ),
                html.Nav([
                    html.A(label, href=path, className="an-nav-link",
                           id=f"nav-link-{path.strip('/') or 'accueil'}")
                    for path, label in NAV_PAGES
                ], style={"display": "flex", "marginLeft": "auto"}),
            ], style={"display": "flex", "alignItems": "center", "width": "100%"}),
        ], fluid=False),
    ], className="an-header")


# ─── PAGE: ACCUEIL ────────────────────────────────────────────────────────────

def page_accueil():
    info = LEGISLATURE
    adoptes  = int(SCRUTINS["adopte_bool"].sum()) if not SCRUTINS.empty else 0
    total_sc = len(SCRUTINS) if not SCRUTINS.empty else 0
    pct_txt  = f"{100*adoptes/total_sc:.0f}% des scrutins" if total_sc else ""

    # ─ Banner
    banner = html.Div([
        dbc.Row([
            dbc.Col(html.Div([
                html.Div("Présidente de l'AN", className="info-banner-label"),
                html.Div(info["president_an"], className="info-banner-value"),
                html.Div(f"Groupe {info['groupe_pres_an']}", className="info-banner-sub"),
            ])),
            dbc.Col(html.Div([
                html.Div("Premier ministre", className="info-banner-label"),
                html.Div(info["premier_ministre"], className="info-banner-value"),
                html.Div(f"depuis {info['debut_pm']}", className="info-banner-sub"),
            ])),
            dbc.Col(html.Div([
                html.Div("Élections législatives", className="info-banner-label"),
                html.Div(info["elections"], className="info-banner-value"),
                html.Div(f"dissolution le {info['dissolution']}", className="info-banner-sub"),
            ])),
            dbc.Col(html.Div([
                html.Div("17ème législature", className="info-banner-label"),
                html.Div(f"depuis le {info['debut']}", className="info-banner-value"),
                html.Div(f"fin prévue {info['fin_prevue']}", className="info-banner-sub"),
            ])),
        ]),
    ], className="info-banner")

    # ─ KPIs
    kpis = dbc.Row([
        dbc.Col(kpi_card("Députés", f"{len(DEPUTES):,}",
                         f"{len(ORGANES)} groupes politiques"), width=3),
        dbc.Col(kpi_card("Scrutins nominatifs", f"{total_sc:,}",
                         "votes enregistrés", color="#059669"), width=3),
        dbc.Col(kpi_card("Textes adoptés", f"{adoptes:,}",
                         pct_txt, color="#059669"), width=3),
        dbc.Col(kpi_card("Majorité absolue", f"{info['majorite_absolue']}",
                         f"sur {info['total_sieges']} sièges", color="#dc2626"), width=3),
    ], className="g-3 mb-4")

    # ─ Group composition list
    ordered_org = sorted(
        ORGANES.to_dict("records"),
        key=lambda r: POLITICAL_ORDER.index(r.get("libelle_abrev", ""))
        if r.get("libelle_abrev") in POLITICAL_ORDER else 99,
    )

    comp_rows = []
    for org in ordered_org:
        abrev = str(org.get("libelle_abrev", ""))
        n_members = len(DEPUTES[DEPUTES["groupe_abrev"] == abrev])
        comp_rows.append(html.Div([
            html.Div(style={
                "width": "5px", "minWidth": "5px", "borderRadius": "3px",
                "background": gc(abrev), "marginRight": "10px", "alignSelf": "stretch",
            }),
            html.Div([
                html.Span(abrev, style={
                    "fontWeight": "700", "fontSize": "0.82rem",
                    "color": gc(abrev), "marginRight": "6px",
                }),
                html.Span(org.get("libelle", ""), style={
                    "color": "#6b7280", "fontSize": "0.8rem",
                }),
                html.Div(f"{n_members} siège{'s' if n_members > 1 else ''}",
                         style={"fontSize": "0.73rem", "color": "#9ca3af", "marginTop": "1px"}),
            ]),
        ], className="group-comp-row"))

    composition = html.Div([
        section_title("Composition"),
        html.Div(comp_rows, style={"overflowY": "auto", "maxHeight": "390px"}),
    ])

    # ─ Map legend
    groups_in_map = [g for g in POLITICAL_ORDER if g in DEPUTES["groupe_abrev"].values]
    legend = html.Div([
        html.Span([
            html.Span(style={
                "width": "11px", "height": "11px",
                "background": gc(g), "borderRadius": "3px",
                "display": "inline-block", "marginRight": "5px", "verticalAlign": "middle",
            }),
            html.Span(g, style={
                "fontWeight": "700", "fontSize": "0.72rem", "color": gc(g),
            }),
            html.Span(f" {GROUP_FULL.get(g, g)}", style={
                "fontSize": "0.72rem", "color": "#6b7280",
            }),
        ], className="legend-chip", style={"borderLeftColor": gc(g)})
        for g in groups_in_map
    ], style={"display": "flex", "flexWrap": "wrap", "marginTop": "10px"})

    # ─ Hemicycle / Carte tabs
    viz_tabs = dbc.Tabs([
        dbc.Tab([
            dbc.Row([
                dbc.Col(dcc.Graph(
                    figure=hemicycle_fig(DEPUTES),
                    config={"displayModeBar": False},
                    style={"marginTop": "12px"},
                ), width=8),
                dbc.Col(composition, width=4, style={"paddingTop": "12px"}),
            ]),
        ], label="🏛️ Hémicycle", tab_id="tab-hemi"),

        dbc.Tab([
            dcc.Graph(
                figure=carte_fig(DEPUTES, GEO),
                config={"displayModeBar": False},
                id="france-map",
                style={"marginTop": "12px"},
            ),
            legend,
            html.Div(id="dept-detail"),
        ], label="🗺️ Carte", tab_id="tab-carte"),
    ], active_tab="tab-hemi", className="mb-0")

    return html.Div([
        banner,
        kpis,
        html.Div(viz_tabs, className="an-card"),
        html.Div([
            section_title("Sièges par groupe politique"),
            dbc.Row([
                dbc.Col(dcc.Graph(
                    figure=seats_bar_fig(DEPUTES),
                    config={"displayModeBar": False},
                ), width=9),
            ]),
        ], className="an-card"),
    ])


# ─── PAGE: LOIS ───────────────────────────────────────────────────────────────

def page_lois():
    if DOSSIERS is None:
        return html.Div(
            "Données non disponibles — lancez main.py d'abord.",
            className="an-card", style={"color": "#6b7280"},
        )

    has_themes = "theme" in DOSSIERS.columns
    themes = ["Tous"] + (sorted(DOSSIERS["theme"].dropna().unique().tolist()) if has_themes else [])
    types  = ["Tous"] + sorted(DOSSIERS["type_dossier"].dropna().unique().tolist())

    sc_df = DOSSIERS.copy()
    sc_df["statut_court"] = sc_df["statut"].apply(short_statut)
    statuts = ["Tous"] + sorted(sc_df["statut_court"].dropna().unique().tolist())

    filters = html.Div([
        dbc.Row([
            dbc.Col([
                html.Div("Recherche", className="filter-label"),
                dcc.Input(id="lois-search", placeholder="Mot-clé dans le titre…",
                          debounce=True, className="filter-input",
                          style={"height": "36px"}),
            ], width=3),
            dbc.Col([html.Div("Thème", className="filter-label"), _dd("lois-theme", themes)], width=2),
            dbc.Col([html.Div("Type", className="filter-label"), _dd("lois-type", types)], width=2),
            dbc.Col([html.Div("Statut", className="filter-label"), _dd("lois-statut", statuts)], width=2),
            dbc.Col([
                html.Div("Trier par", className="filter-label"),
                dcc.Dropdown(
                    id="lois-sort",
                    options=[
                        {"label": "Activité récente ↓",  "value": "activite"},
                        {"label": "Date de dépôt ↓",     "value": "date_desc"},
                        {"label": "Date de dépôt ↑",     "value": "date_asc"},
                        {"label": "Plus de scrutins",    "value": "scrutins"},
                        {"label": "Statut A→Z",          "value": "statut"},
                    ],
                    value="activite", clearable=False,
                    style={"fontSize": "0.84rem"},
                ),
            ], width=2),
        ], className="g-2"),
    ], className="an-card", style={"marginBottom": "12px"})

    return html.Div([
        html.Div(id="loi-list-section", children=[
            html.Div("Lois & Propositions de loi", className="page-title"),
            filters,
            html.Div(id="lois-count",
                     style={"fontSize": "0.8rem", "color": "#9ca3af", "marginBottom": "10px"}),
            html.Div(id="lois-table-wrap"),
        ]),
        html.Div(id="loi-detail-section"),
    ])


# ─── PAGE: DEPUTÉS ────────────────────────────────────────────────────────────

def page_deputes():
    groupes = ["Tous"] + [g for g in POLITICAL_ORDER if g in DEPUTES["groupe_abrev"].values]
    depts   = ["Tous"] + sorted(DEPUTES["departement"].dropna().unique().tolist())

    filters = html.Div([
        dbc.Row([
            dbc.Col([
                html.Div("Recherche", className="filter-label"),
                dcc.Input(id="dep-search", placeholder="Nom ou prénom…",
                          debounce=True, className="filter-input",
                          style={"height": "36px"}),
            ], width=3),
            dbc.Col([html.Div("Groupe", className="filter-label"), _dd("dep-groupe", groupes)], width=3),
            dbc.Col([html.Div("Département", className="filter-label"), _dd("dep-dept", depts)], width=3),
        ], className="g-2"),
    ], className="an-card", style={"marginBottom": "12px"})

    return html.Div([
        html.Div(id="dep-list-section", children=[
            html.Div("Députés", className="page-title"),
            filters,
            html.Div(id="dep-count",
                     style={"fontSize": "0.8rem", "color": "#9ca3af", "marginBottom": "10px"}),
            html.Div(id="dep-table-wrap"),
        ]),
        html.Div(id="dep-detail-section"),
    ])


# ─── PAGE: GROUPES ────────────────────────────────────────────────────────────

def page_groupes():
    valid = [g for g in POLITICAL_ORDER if g in DEPUTES["groupe_abrev"].values]

    return html.Div([
        html.Div("Groupes politiques", className="page-title"),
        html.Div([
            html.Div("Sélectionner un groupe", className="filter-label"),
            dcc.Dropdown(
                id="grp-select",
                options=[{"label": f"{g} — {GROUP_FULL.get(g, g)}", "value": g} for g in valid],
                value=valid[0] if valid else None,
                clearable=False,
                style={"fontSize": "0.84rem"},
            ),
        ], className="an-card", style={"maxWidth": "520px", "marginBottom": "20px"}),
        html.Div(id="grp-detail"),
    ])


# ─── PAGE: SIMILARITÉ ─────────────────────────────────────────────────────────

def page_similarite():
    themes_opts = [{"label": "Tous les thèmes", "value": "Tous"}]
    if DOSSIERS is not None and "theme" in DOSSIERS.columns:
        for t in sorted(DOSSIERS["theme"].dropna().unique()):
            themes_opts.append({"label": t, "value": t})

    valid = [g for g in POLITICAL_ORDER if g in DEPUTES["groupe_abrev"].values]

    return html.Div([
        html.Div("Similarité de vote entre groupes", className="page-title"),
        html.Div([
            html.Div("Filtrer par thème", className="filter-label"),
            dcc.Dropdown(
                id="sim-theme", options=themes_opts, value="Tous",
                clearable=False, style={"fontSize": "0.84rem", "maxWidth": "360px"},
            ),
        ], className="an-card", style={"marginBottom": "20px"}),
        html.Div(id="sim-matrix"),

        # ─ Pairwise comparison ─
        html.Div([
            html.Div("Comparer deux groupes en détail", className="section-title"),
            dbc.Row([
                dbc.Col([
                    html.Div("Groupe A", className="filter-label"),
                    dcc.Dropdown(
                        id="pair-a",
                        options=[{"label": f"{g} — {GROUP_FULL.get(g, g)}", "value": g} for g in valid],
                        value=valid[0] if len(valid) > 0 else None,
                        clearable=False, style={"fontSize": "0.84rem"},
                    ),
                ], width=4),
                dbc.Col([
                    html.Div("Groupe B", className="filter-label"),
                    dcc.Dropdown(
                        id="pair-b",
                        options=[{"label": f"{g} — {GROUP_FULL.get(g, g)}", "value": g} for g in valid],
                        value=valid[1] if len(valid) > 1 else None,
                        clearable=False, style={"fontSize": "0.84rem"},
                    ),
                ], width=4),
            ], className="g-3 mb-3"),
            html.Div(id="pair-detail"),
        ], className="an-card", style={"marginTop": "20px"}),
    ])


# ─── APP LAYOUT ───────────────────────────────────────────────────────────────

app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    navbar(),
    html.Main(id="page-content", className="page-container"),
    html.Footer(
        dbc.Container([
            html.Div([
                "Assemblée Nationale · 17ème législature · Données ",
                html.A("data.assemblee-nationale.fr", target="_blank",
                       href="https://data.assemblee-nationale.fr"),
            ]),
        ]),
        className="an-footer",
    ),
])


# ─── ROUTING ──────────────────────────────────────────────────────────────────

@app.callback(Output("page-content", "children"), Input("url", "pathname"))
def render_page(path):
    if path in ("/", None): return page_accueil()
    if path == "/lois":       return page_lois()
    if path == "/deputes":    return page_deputes()
    if path == "/groupes":    return page_groupes()
    if path == "/similarite": return page_similarite()
    return html.Div(f"Page introuvable : {path}", className="an-card",
                    style={"color": "#6b7280"})


# ─── CALLBACKS: ACCUEIL ───────────────────────────────────────────────────────

@app.callback(
    Output("dept-detail", "children"),
    Input("france-map", "clickData"),
    prevent_initial_call=True,
)
def show_dept(click):
    if not click:
        return html.Div()
    pt = click["points"][0]
    dept = pt.get("location") or pt.get("hovertext", "")
    if not dept:
        return html.Div()

    sub = DEPUTES[DEPUTES["departement"] == dept].copy()
    sub["_c"] = pd.to_numeric(sub["circonscription"], errors="coerce")
    sub = sub.sort_values("_c")

    rows = []
    for _, d in sub.iterrows():
        abrev = str(d.get("groupe_abrev", ""))
        circ  = str(d.get("circonscription", "")).strip()
        circ_label = ("1ère circ." if circ == "1"
                      else f"{circ}e circ." if circ.isdigit()
                      else circ)
        rows.append(html.Div([
            html.Span(abrev, style={
                "background": gc(abrev), "color": "white",
                "padding": "2px 8px", "borderRadius": "4px",
                "fontSize": "0.7rem", "fontWeight": "700",
                "minWidth": "52px", "textAlign": "center",
                "display": "inline-block", "marginRight": "10px",
            }),
            html.Span(f"{d.get('prenom','')} {d.get('nom','')}", style={"fontWeight": "500"}),
            html.Span(
                f" · {int(d['age'])} ans" if pd.notna(d.get("age")) else "",
                style={"color": "#9ca3af", "fontSize": "0.8rem"},
            ),
            html.Span(circ_label, style={
                "marginLeft": "auto", "color": "#9ca3af",
                "fontSize": "0.74rem",
            }),
        ], style={
            "display": "flex", "alignItems": "center",
            "padding": "8px 12px", "borderRadius": "6px",
            "background": "#f8f9fc", "marginBottom": "4px",
        }))

    return html.Div([
        section_title(f"📍 {dept} — {len(sub)} député(s)"),
        *rows,
    ], className="an-card", style={"marginTop": "14px"})


# ─── CALLBACKS: LOIS ─────────────────────────────────────────────────────────

def _build_lois(search, theme, type_f, statut, sort_by):
    if DOSSIERS is None:
        return pd.DataFrame()

    scr_agg = (
        SCRUTINS[SCRUTINS["dossier_ref"].str.startswith("DLR", na=False)]
        .groupby("dossier_ref")
        .agg(nb_scrutins=("uid", "count"),
             premier_vote=("date", "min"),
             dernier_vote=("date", "max"))
        .reset_index()
        .rename(columns={"dossier_ref": "uid"})
    )
    df = DOSSIERS.merge(scr_agg, on="uid", how="left")
    df["nb_scrutins"]  = df["nb_scrutins"].fillna(0).astype(int)
    df["statut_court"] = df["statut"].apply(short_statut)

    if search:
        df = df[df["titre"].str.contains(search, case=False, na=False)]
    if theme and theme != "Tous" and "theme" in df.columns:
        df = df[df["theme"] == theme]
    if type_f and type_f != "Tous":
        df = df[df["type_dossier"] == type_f]
    if statut and statut != "Tous":
        df = df[df["statut_court"] == statut]

    sort_map = {
        "activite":  (["dernier_vote", "date_depot"], [False, False]),
        "scrutins":  (["nb_scrutins", "dernier_vote"], [False, False]),
        "date_desc": (["date_depot"],                  [False]),
        "date_asc":  (["date_depot"],                  [True]),
        "statut":    (["statut_court"],                [True]),
    }
    cols, asc = sort_map.get(sort_by, sort_map["activite"])
    return df.sort_values(cols, ascending=asc, na_position="last")


@app.callback(
    Output("lois-count", "children"),
    Output("lois-table-wrap", "children"),
    Input("lois-search", "value"),
    Input("lois-theme",  "value"),
    Input("lois-type",   "value"),
    Input("lois-statut", "value"),
    Input("lois-sort",   "value"),
)
def update_lois(search, theme, type_f, statut, sort_by):
    df = _build_lois(search, theme, type_f, statut, sort_by)
    if df.empty:
        return "Aucun résultat.", html.Div()

    # Format dates for display
    for col in ["date_depot", "premier_vote", "dernier_vote"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%d/%m/%Y")
    df["nb_scrutins"] = df["nb_scrutins"].fillna(0).astype(int)

    # All columns go into data (so selected row has everything for the detail view)
    all_data_cols = [c for c in ["uid", "titre", "type_dossier", "theme", "statut_court",
                                  "date_depot", "dernier_vote", "premier_vote",
                                  "nb_scrutins", "url_an"] if c in df.columns]
    disp = df[all_data_cols].copy()

    # Visible columns only
    visible = [
        {"name": "Titre",         "id": "titre"},
        {"name": "Statut",        "id": "statut_court"},
        {"name": "Dépôt",         "id": "date_depot"},
        {"name": "Dernier vote",  "id": "dernier_vote"},
        {"name": "Scrutins",      "id": "nb_scrutins"},
    ]
    if "theme" in disp.columns:
        visible.insert(1, {"name": "Thème", "id": "theme"})

    visible_ids = {c["id"] for c in visible}
    hidden = [c for c in all_data_cols if c not in visible_ids]

    ts = _table_style()
    table = dash_table.DataTable(
        id="lois-table",
        data=disp.to_dict("records"),
        columns=visible + [{"name": c, "id": c} for c in hidden],
        hidden_columns=hidden,
        page_size=25,
        sort_action="native",
        tooltip_header={"titre": "Cliquer sur une ligne pour voir le détail"},
        style_cell_conditional=[
            {"if": {"column_id": "titre"},
             "maxWidth": "0", "overflow": "hidden",
             "textOverflow": "ellipsis", "whiteSpace": "nowrap"},
            {"if": {"column_id": "statut_court"},
             "width": "140px", "whiteSpace": "nowrap"},
            {"if": {"column_id": "theme"},
             "width": "120px", "maxWidth": "120px",
             "overflow": "hidden", "textOverflow": "ellipsis", "whiteSpace": "nowrap"},
            {"if": {"column_id": "date_depot"},
             "width": "95px", "whiteSpace": "nowrap", "textAlign": "center"},
            {"if": {"column_id": "dernier_vote"},
             "width": "110px", "whiteSpace": "nowrap", "textAlign": "center"},
            {"if": {"column_id": "nb_scrutins"},
             "width": "80px", "textAlign": "center"},
        ],
        **ts,
    )

    count = f"{len(df):,} dossier(s) · {int(df['nb_scrutins'].sum()):,} scrutins au total  — cliquer sur une ligne pour voir le détail"
    return count, html.Div(table, className="an-card", style={"padding": "0"})


def _back_btn(btn_id):
    return html.Button(
        "← Retour à la liste", id=btn_id, n_clicks=0,
        style={
            "background": "none", "border": "none", "color": "#2563eb",
            "fontSize": "0.84rem", "fontWeight": "600", "cursor": "pointer",
            "padding": "0", "marginBottom": "18px", "display": "inline-flex",
            "alignItems": "center", "gap": "4px",
        },
    )


def _classify_scrutin(titre):
    """Returns (type_sc, article_ref, proposer_name) parsed from the full titre."""
    if not isinstance(titre, str) or not titre.strip():
        return "autre", None, None
    raw = titre
    t   = raw.lower().replace("’", "'").replace(" ", " ")

    # ─ type ─
    if re.match(r"l[e']?\s*sous[- ]amendement", t):
        type_sc = "sous-amendement"
    elif re.match(r"l[e']?\s*amendement", t) or "amendement n" in t:
        type_sc = "amendement"
    elif re.match(r"l[e']?\s*article", t):
        type_sc = "article"
    elif "ensemble" in t or "l'ensemble" in t:
        type_sc = "ensemble"
    elif "motion" in t or "renvoi" in t or "irrecevab" in t:
        type_sc = "motion"
    else:
        type_sc = "autre"

    # ─ article reference ─
    article_ref = None
    m = re.search(r"(?:à\s+)?l[e']?\s*article\s+(premier|unique|\d+\s*(?:e?r|bis|ter)?)", t)
    if m:
        art = m.group(1).strip()
        if art in ("premier", "1er", "1"):
            article_ref = "Article 1er"
        elif art == "unique":
            article_ref = "Article unique"
        else:
            article_ref = f"Article {art}"

    # ─ proposer ─
    proposer = None
    if "gouvernement" in t:
        proposer = "Gouvernement"
    elif re.search(r"\bla commission\b", t):
        proposer = "Commission"
    else:
        m2 = re.search(
            r"\bde\s+M(?:me?)?\.?\s+((?:[A-ZÀ-ÜA-Za-zà-ü\-]+\s+){0,2}[A-ZÀ-ÜA-Za-zà-ü\-]+)",
            raw)
        if m2:
            name = m2.group(1).strip()
            # Remove trailing prepositions/conjunctions captured by the greedy pattern
            name = re.sub(r'\s+(?:et|à|les|après|sur|au|aux)\s*$', '', name, flags=re.IGNORECASE)
            proposer = name.rstrip("., ")

    return type_sc, article_ref, proposer




def _scrutin_url(uid: str) -> str:
    """Build AN.fr scrutin URL from UID like VTANR5L17V465."""
    import re as _re
    m = _re.search(r'V(\d+)$', str(uid))
    return f"https://www.assemblee-nationale.fr/dyn/17/scrutins/vote{m.group(1)}" if m else ""

def _workflow_timeline(statut_raw: str, row: dict, law_sc) -> "html.Div":
    """Horizontal legislative workflow timeline card."""
    s = str(statut_raw).lower() if statut_raw else ""

    # Detect lecture unique (single-reading procedure)
    lecture_unique = "lecture unique" in s

    if lecture_unique:
        STAGES = [
            ("depot",    "Dépôt"),
            ("lu",       "Lecture\nunique"),
            ("promul",   "Promulguée"),
        ]
        if "promulg" in s or "mise en application" in s:
            current = 2
        else:
            current = 1
    else:
        STAGES = [
            ("depot",    "Dépôt"),
            ("an1",      "1ère lecture\nAN"),
            ("senat",    "Sénat"),
            ("navette",  "2ème lecture\n/ CMP"),
            ("promul",   "Promulguée"),
        ]
        if "promulg" in s or "mise en application" in s or "conseil constitutionnel" in s:
            current = 4
        elif "commission mixte paritaire" in s or "nouvelle lecture" in s or "deuxi" in s:
            current = 3
        elif "2" in s and "assembl" in s and "saisie" in s:
            current = 2
        else:
            current = 1

    # Dates per stage
    dates = [""] * len(STAGES)
    depot_val = str(row.get("date_depot", "") or "")
    if depot_val and depot_val != "—":
        try:
            import datetime
            dv = depot_val.strip()
            if "/" in dv:  # already DD/MM/YYYY from table formatting
                d = datetime.datetime.strptime(dv, "%d/%m/%Y").date()
            else:
                d = datetime.date.fromisoformat(dv[:10])
            dates[0] = d.strftime("%d/%m/%y")
        except Exception:
            dates[0] = depot_val[:8]
    if not law_sc.empty and "date" in law_sc.columns:
        valid_dates = law_sc["date"].dropna()
        if not valid_dates.empty:
            first_vote = valid_dates.min()
            if hasattr(first_vote, "strftime"):
                dates[min(1, len(STAGES) - 1)] = first_vote.strftime("%d/%m/%y")

    # Build nodes + connectors
    DONE_COL    = "#059669"
    ACTIVE_COL  = "#0066CC"
    PENDING_COL = "#d1d5db"

    nodes = []
    for i, (_, label) in enumerate(STAGES):
        done   = i < current
        active = i == current

        dot_bg  = DONE_COL if done else (ACTIVE_COL if active else "white")
        dot_bdr = DONE_COL if done else (ACTIVE_COL if active else PENDING_COL)
        lbl_col = "#111827" if (done or active) else "#9ca3af"
        lbl_wt  = "700" if active else ("600" if done else "400")

        node = html.Div([
            html.Div(
                "✓" if done else "",
                style={
                    "width": "26px", "height": "26px", "borderRadius": "50%",
                    "background": dot_bg, "border": f"2px solid {dot_bdr}",
                    "display": "flex", "alignItems": "center",
                    "justifyContent": "center",
                    "color": "white", "fontSize": "0.72rem", "fontWeight": "800",
                    "zIndex": "1", "flexShrink": "0",
                    "boxShadow": f"0 0 0 4px rgba(0,102,204,0.15)" if active else "none",
                }
            ),
            html.Div(label, style={
                "fontSize": "0.63rem", "fontWeight": lbl_wt,
                "color": lbl_col, "textAlign": "center",
                "marginTop": "5px", "whiteSpace": "pre-line", "lineHeight": "1.25",
            }),
            html.Div(dates[i], style={
                "fontSize": "0.6rem", "color": "#9ca3af",
                "textAlign": "center", "marginTop": "2px",
                "height": "14px",
            }),
        ], style={
            "display": "flex", "flexDirection": "column",
            "alignItems": "center", "flex": "1",
        })
        nodes.append(node)

        if i < len(STAGES) - 1:
            line_col = DONE_COL if (i < current - 1) else (ACTIVE_COL if i == current - 1 else PENDING_COL)
            nodes.append(html.Div(style={
                "flex": "2", "height": "2px",
                "background": line_col,
                "alignSelf": "flex-start", "marginTop": "12px",
            }))

    return html.Div([
        html.Div("Parcours législatif", style={
            "fontSize": "0.68rem", "fontWeight": "700", "color": "#6b7280",
            "textTransform": "uppercase", "letterSpacing": "0.07em",
            "marginBottom": "14px",
        }),
        html.Div(nodes, style={
            "display": "flex", "alignItems": "flex-start", "width": "100%",
        }),
    ], className="an-card", style={"marginBottom": "12px", "paddingBottom": "8px"})

def _render_loi_detail(uid, row):  # noqa: C901
    law_sc = SCRUTINS[SCRUTINS["dossier_ref"] == uid].sort_values("date").copy()

    url_an = str(row.get("url_an", "") or "")
    depot_val   = str(row.get("date_depot",   "—") or "—")
    dernier_val = str(row.get("dernier_vote", "—") or "—")
    n_sc        = int(row.get("nb_scrutins", 0) or 0)

    # ── Header card ─────────────────────────────────────────────────────────────
    link_btn = (
        html.A("Texte sur AN.fr →", href=url_an, target="_blank", style={
            "display": "inline-block", "background": "#0066CC", "color": "white",
            "padding": "5px 14px", "borderRadius": "6px", "fontSize": "0.8rem",
            "fontWeight": "600", "textDecoration": "none",
        }) if url_an and url_an.startswith("http") else html.Span()
    )
    header_card = html.Div([
        dbc.Row([
            dbc.Col([
                html.Div("Objet du texte", style={
                    "fontSize": "0.65rem", "fontWeight": "700", "color": "#9ca3af",
                    "textTransform": "uppercase", "letterSpacing": "0.06em",
                    "marginBottom": "4px",
                }),
                html.Div(row.get("titre", ""), style={
                    "fontWeight": "600", "fontSize": "0.98rem",
                    "lineHeight": "1.55", "marginBottom": "10px",
                    "whiteSpace": "normal", "color": "#111827",
                }),
                html.Div([
                    html.Span(row.get("theme", ""), className="theme-chip") if row.get("theme") else None,
                    html.Span(row.get("type_dossier", ""), style={
                        "background": "#f0f4ff", "color": "#3b4fc8", "padding": "2px 10px",
                        "borderRadius": "10px", "fontSize": "0.74rem", "fontWeight": "600",
                    }) if row.get("type_dossier") else None,
                    html.Span(row.get("statut_court", ""), style={
                        "background": "#f3f4f6", "color": "#374151", "padding": "2px 10px",
                        "borderRadius": "10px", "fontSize": "0.74rem", "fontWeight": "600",
                    }),
                ], style={"display": "flex", "flexWrap": "wrap", "gap": "6px"}),
            ], width=9),
            dbc.Col(link_btn, width=3,
                    className="d-flex justify-content-end align-items-start"),
        ]),
        dbc.Row([
            dbc.Col([html.Div("Déposé le",   className="kpi-label"), html.Div(depot_val,   style={"fontWeight": "600", "fontSize": "0.85rem"})]),
            dbc.Col([html.Div("Dernier vote", className="kpi-label"), html.Div(dernier_val, style={"fontWeight": "600", "fontSize": "0.85rem"})]),
            dbc.Col([html.Div("Scrutins nominatifs", className="kpi-label"), html.Div(str(n_sc), style={"fontWeight": "600", "fontSize": "0.85rem"})]),
        ], className="mt-3"),
    ], className="an-card", style={"marginBottom": "12px"})

    if law_sc.empty:
        return html.Div([
            _back_btn("loi-back-btn"), header_card,
            html.Div("Aucun scrutin nominatif disponible pour ce dossier.",
                     className="an-card", style={"color": "#6b7280"}),
        ])

    org_map = (ORGANES[["uid", "libelle_abrev"]]
               .drop_duplicates("uid").set_index("uid")["libelle_abrev"])

    # name → groupe lookup (best-effort, by last name)
    name_to_grp = {str(r["nom"]).upper(): str(r.get("groupe_abrev", ""))
                   for _, r in DEPUTES.iterrows()}

    # ── Classify and annotate each scrutin ──────────────────────────────────────
    law_sc = law_sc.copy()
    law_sc["_titre_full"] = law_sc["titre"].fillna(law_sc["titre_court"] if "titre_court" in law_sc.columns else "").fillna("").astype(str)
    parsed = law_sc["_titre_full"].apply(_classify_scrutin)
    law_sc["_type"]    = [p[0] for p in parsed]
    law_sc["_art_ref"] = [p[1] for p in parsed]
    law_sc["_proposer"]= [p[2] for p in parsed]

    # Collect all group votes
    all_sc_uids = law_sc["uid"].astype(str).tolist()
    all_gv = VOTES_GROUPE[VOTES_GROUPE["scrutin_uid"].isin(all_sc_uids)].copy()
    all_gv["abrev"] = all_gv["groupe_ref"].map(org_map).fillna("")
    all_gv = all_gv[all_gv["abrev"].isin(POLITICAL_ORDER)]

    def _adopte(val):
        return str(val).lower().replace("é", "e") == "adopte"

    def _result_chip(adopted):
        return html.Span("Adopté" if adopted else "Rejeté", style={
            "background": "#dcfce7" if adopted else "#fee2e2",
            "color": "#166534" if adopted else "#991b1b",
            "padding": "2px 8px", "borderRadius": "10px",
            "fontSize": "0.68rem", "fontWeight": "700", "flexShrink": "0",
        })

    def _group_badges(sc_uid, size="sm"):
        gv = all_gv[all_gv["scrutin_uid"] == sc_uid].copy()
        if gv.empty:
            return []
        gv["_ord"] = gv["abrev"].map(lambda a: POLITICAL_ORDER.index(a) if a in POLITICAL_ORDER else 99)
        gv = gv.sort_values("_ord")
        badges = []
        for _, g in gv.iterrows():
            abrev_g = str(g["abrev"])
            vals = {"pour": g["pour"], "contre": g["contre"], "abstention": g["abstention"]}
            dom  = max(vals, key=vals.get)
            col  = {"pour": "#059669", "contre": "#dc2626", "abstention": "#d97706"}[dom]
            lbl  = {"pour": "Pour", "contre": "Contre", "abstention": "Abst."}[dom]
            fsz  = "0.6rem" if size == "sm" else "0.7rem"
            badges.append(html.Span([
                html.Span(abrev_g, style={
                    "background": gc(abrev_g), "color": "white",
                    "padding": "1px 5px", "borderRadius": "3px",
                    "fontSize": fsz, "fontWeight": "700", "marginRight": "3px",
                }),
                html.Span(lbl, style={"color": col, "fontSize": fsz, "fontWeight": "700"}),
            ], style={"marginRight": "8px", "whiteSpace": "nowrap",
                      "display": "inline-flex", "alignItems": "center"}))
        return badges

    # ── SECTION 2: Articles + Vote final ────────────────────────────────────────
    art_sc = law_sc[law_sc["_type"].isin(["article", "ensemble", "autre"])].copy()
    # "autre" with no article_ref and matching "l'ensemble" → treat as ensemble
    # Sort: articles first (by position), then ensemble
    def _art_sort_key(r):
        if r["_type"] == "ensemble": return 9999
        if not isinstance(r["_art_ref"], str): return 9998
        num = re.search(r"\d+", r["_art_ref"])
        return int(num.group()) if num else 0
    art_sc = art_sc.copy()
    art_sc["_sort"] = art_sc.apply(_art_sort_key, axis=1)
    art_sc = art_sc.sort_values("_sort")

    art_rows = []
    for _, sc in art_sc.iterrows():
        sc_uid   = str(sc["uid"])
        titre_d  = str(sc.get("titre", "") or sc.get("titre_court", "") or "")
        adopted  = _adopte(sc.get("adopte", ""))
        pour_n   = int(sc.get("pour", 0) or 0)
        contre_n = int(sc.get("contre", 0) or 0)
        abst_n   = int(sc.get("abstention", 0) or 0)
        is_final = sc["_type"] == "ensemble"
        art_label = sc["_art_ref"] if isinstance(sc["_art_ref"], str) else ("Vote final" if is_final else "Vote")

        if is_final:
            bg = "#eff6ff" if adopted else "#fef2f2"
            border = "#0066CC" if adopted else "#dc2626"
        else:
            bg = "#f0fdf4" if adopted else "white"
            border = "#059669" if adopted else "#e5e7eb"

        art_rows.append(html.Div([
            html.Div([
                # LEFT: article label + full title
                html.Div([
                    html.Span(art_label, style={
                        "fontSize": "0.75rem", "fontWeight": "800",
                        "color": "#0066CC" if is_final else "#1a2744",
                        "whiteSpace": "nowrap", "marginRight": "8px", "flexShrink": "0",
                    }),
                    html.Div(titre_d, style={
                        "fontSize": "0.77rem", "color": "#374151",
                        "lineHeight": "1.4", "whiteSpace": "normal",
                    }) if titre_d else None,
                ], style={"flex": "1", "minWidth": "0", "display": "flex",
                          "alignItems": "flex-start", "flexWrap": "wrap", "gap": "4px"}),
                # RIGHT: vote counts + chip
                html.Div([
                    html.Span(f"{pour_n}✓ {contre_n}✗ {abst_n}~", style={
                        "fontSize": "0.66rem", "color": "#9ca3af", "whiteSpace": "nowrap",
                    }),
                    _result_chip(adopted),
                ], style={"display": "flex", "alignItems": "center", "gap": "6px",
                          "flexShrink": "0", "paddingLeft": "12px"}),
            ], style={"display": "flex", "alignItems": "flex-start",
                      "justifyContent": "space-between"}),
            html.Div(_group_badges(sc_uid, "md"),
                     style={"display": "flex", "flexWrap": "wrap", "marginTop": "5px"}),
        ], style={
            "padding": "10px 14px",
            "borderBottom": "1px solid #f3f4f6",
            "background": bg,
            "borderLeft": f"3px solid {border}",
        }))

    articles_card = html.Div([
        section_title(f"Structure du texte — {len(art_sc)} vote(s) sur articles et texte final"),
        html.Div(art_rows or [html.Span("Aucun vote d'article identifié.",
                                         style={"color": "#9ca3af", "fontSize": "0.83rem"})],
                 style={"borderRadius": "6px", "border": "1px solid #f3f4f6", "overflow": "hidden"}),
    ], className="an-card", style={"marginBottom": "12px"})

    # ── SECTION 3: Amendements groupés par article ───────────────────────────────
    amend_sc = law_sc[law_sc["_type"].isin(["amendement", "sous-amendement"])].copy()
    n_amend      = len(amend_sc)
    n_amend_adop = int(amend_sc["adopte"].apply(_adopte).sum()) if not amend_sc.empty else 0

    # Count proposers → try to resolve group
    proposer_grp_counts = {}
    for _, sc in amend_sc.iterrows():
        prop = sc["_proposer"]
        if not prop:
            continue
        grp = None
        if prop == "Gouvernement":
            grp = "Gouvernement"
        elif prop == "Commission":
            grp = "Commission"
        else:
            # Try full name then each word right-to-left (surname is last)
            grp = name_to_grp.get(str(prop).upper())
            if not grp:
                for w in reversed(str(prop).upper().split()):
                    if name_to_grp.get(w):
                        grp = name_to_grp[w]
                        break
        key = grp if grp else prop
        proposer_grp_counts[key] = proposer_grp_counts.get(key, 0) + 1

    # Build proposer summary chips
    proposer_chips = []
    for entity, cnt in sorted(proposer_grp_counts.items(), key=lambda x: -x[1])[:10]:
        bg = gc(entity) if entity in COLORS else "#6b7280"
        proposer_chips.append(html.Span([
            html.Span(entity, style={
                "background": bg, "color": "white",
                "padding": "1px 7px", "borderRadius": "3px",
                "fontSize": "0.7rem", "fontWeight": "700", "marginRight": "4px",
            }),
            html.Span(str(cnt), style={"fontSize": "0.7rem", "color": "#374151"}),
        ], style={"marginRight": "10px", "display": "inline-flex", "alignItems": "center"}))

    # Group amendments by article
    art_groups = {}
    for _, sc in amend_sc.iterrows():
        key = sc["_art_ref"] if isinstance(sc["_art_ref"], str) else "Sans article identifié"
        art_groups.setdefault(key, []).append(sc)

    def _art_order(k):
        if k == "Sans article identifié": return 9999
        m = re.search(r"\d+", k)
        return int(m.group()) if m else 0

    amend_sections = []
    for art_key in sorted(art_groups.keys(), key=_art_order):
        items = art_groups[art_key]
        n_adop_art = sum(1 for sc in items if _adopte(sc.get("adopte", "")))
        amend_item_rows = []
        for sc in items:
            sc_uid   = str(sc["uid"])
            titre_d  = str(sc.get("titre", "") or sc.get("titre_court", "") or "")
            adopted  = _adopte(sc.get("adopte", ""))
            pour_n   = int(sc.get("pour", 0) or 0)
            contre_n = int(sc.get("contre", 0) or 0)
            abst_n   = int(sc.get("abstention", 0) or 0)
            proposer = sc["_proposer"] or "—"
            is_sub   = sc["_type"] == "sous-amendement"

            # Resolve proposer group (try full name, then each word right-to-left)
            prop_grp = None
            if proposer not in ("Gouvernement", "Commission", "—"):
                prop_grp = name_to_grp.get(str(proposer).upper())
                if not prop_grp:
                    for _w in reversed(str(proposer).upper().split()):
                        if name_to_grp.get(_w):
                            prop_grp = name_to_grp[_w]
                            break
            prop_el = html.Span([
                html.Span(prop_grp, style={
                    "background": gc(prop_grp), "color": "white",
                    "padding": "0 4px", "borderRadius": "3px",
                    "fontSize": "0.58rem", "fontWeight": "700", "marginRight": "3px",
                }) if prop_grp else None,
                html.Span(("↳ " if is_sub else "") + proposer,
                          style={"fontSize": "0.7rem", "color": "#374151"}),
            ], style={"display": "inline-flex", "alignItems": "center",
                      "background": "#f9fafb", "padding": "1px 6px",
                      "borderRadius": "4px", "flexShrink": "0"})

            amend_item_rows.append(html.Div([
                html.Div([
                    # LEFT: proposer badge + title
                    html.Div([
                        prop_el,
                        html.Div(titre_d, style={
                            "fontSize": "0.72rem", "color": "#6b7280",
                            "lineHeight": "1.35", "whiteSpace": "normal",
                            "marginTop": "3px",
                        }) if titre_d else None,
                    ], style={"flex": "1", "minWidth": "0"}),
                    # RIGHT: vote counts + chip
                    html.Div([
                        html.Span(f"{pour_n}✓ {contre_n}✗", style={
                            "fontSize": "0.66rem", "color": "#9ca3af", "whiteSpace": "nowrap",
                        }),
                        _result_chip(adopted),
                    ], style={"display": "flex", "alignItems": "center", "gap": "6px",
                              "flexShrink": "0", "paddingLeft": "12px", "alignSelf": "flex-start"}),
                ], style={"display": "flex", "justifyContent": "space-between",
                          "alignItems": "flex-start"}),
                html.Div(_group_badges(sc_uid),
                         style={"display": "flex", "flexWrap": "wrap", "marginTop": "4px"}),
            ], style={
                "padding": "8px 12px", "borderBottom": "1px solid #f3f4f6",
                "background": "#f0fdf4" if adopted else "white",
                "borderLeft": f"3px solid {'#059669' if adopted else '#f3f4f6'}",
            }))

        amend_sections.append(html.Div([
            html.Div([
                html.Span(art_key, style={
                    "fontSize": "0.76rem", "fontWeight": "700", "color": "#1a2744",
                }),
                html.Span(
                    f"{len(items)} amendement(s) · {n_adop_art} adopté(s)",
                    style={"fontSize": "0.69rem", "color": "#9ca3af", "marginLeft": "10px"},
                ),
            ], style={"padding": "8px 14px", "background": "#f8f9fc",
                      "borderBottom": "1px solid #e5e7eb"}),
            html.Div(amend_item_rows),
        ], style={"borderBottom": "2px solid #e5e7eb"}))

    amend_card = html.Div([
        dbc.Row([
            dbc.Col(section_title(
                f"Amendements — {n_amend} votes "
                f"({n_amend_adop} adoptés · {n_amend - n_amend_adop} rejetés)"
            ), width=8),
            dbc.Col(html.Div([
                html.Span("Déposés par : ", style={"fontSize": "0.72rem", "color": "#9ca3af"}),
                *proposer_chips,
            ], style={"display": "flex", "flexWrap": "wrap", "alignItems": "center"}), width=4),
        ], className="g-2", style={"marginBottom": "10px"}),
        html.Div(amend_sections or [html.Span("Aucun amendement nominatif.",
                                               style={"color": "#9ca3af"})],
                 style={"borderRadius": "6px", "border": "1px solid #f3f4f6", "overflow": "hidden"}),
    ], className="an-card")

    return html.Div([
        _back_btn("loi-back-btn"),
        header_card,
        articles_card,
        amend_card,
    ])


# ─── CALLBACKS: LOIS (master-detail) ─────────────────────────────────────────

@app.callback(
    Output("loi-list-section", "style"),
    Output("loi-detail-section", "children"),
    Input("lois-table", "active_cell"),
    State("lois-table", "derived_virtual_data"),
    prevent_initial_call=True,
)
def show_loi_detail(active_cell, data):
    if not active_cell or not data:
        return {}, html.Div()
    row = data[active_cell["row"]]
    uid = str(row.get("uid", ""))
    if not uid:
        return {}, html.Div()
    try:
        detail = _render_loi_detail(uid, row)
    except Exception as e:
        detail = html.Div([
            _back_btn("loi-back-btn"),
            html.Div(f"Erreur: {e}", className="an-card"),
        ])
    return {"display": "none"}, detail


@app.callback(
    Output("loi-list-section", "style", allow_duplicate=True),
    Output("loi-detail-section", "children", allow_duplicate=True),
    Input("loi-back-btn", "n_clicks"),
    prevent_initial_call=True,
)
def loi_back(n):
    if not n:
        return no_update, no_update
    return {}, html.Div()


# ─── CALLBACKS: DEPUTÉS ───────────────────────────────────────────────────────

@app.callback(
    Output("dep-count", "children"),
    Output("dep-table-wrap", "children"),
    Input("dep-search", "value"),
    Input("dep-groupe", "value"),
    Input("dep-dept",   "value"),
)
def update_deputes(search, groupe, dept):
    df = DEPUTES.copy()
    if search:
        df = df[df["nom_complet"].str.contains(search, case=False, na=False)]
    if groupe and groupe != "Tous":
        df = df[df["groupe_abrev"] == groupe]
    if dept and dept != "Tous":
        df = df[df["departement"] == dept]
    df = df.sort_values(["groupe_abrev", "nom"])

    data_cols = ["id", "nom_complet", "groupe_abrev", "age", "departement", "profession"]
    disp = df[[c for c in data_cols if c in df.columns]].copy()
    disp["age"] = disp["age"].apply(lambda x: f"{int(x)}" if pd.notna(x) else "")

    ts = _table_style()
    style_grp = [
        {"if": {"filter_query": f'{{groupe_abrev}} = "{g}"', "column_id": "groupe_abrev"},
         "backgroundColor": COLORS.get(g, "#aaa"),
         "color": "white", "fontWeight": "700", "textAlign": "center"}
        for g in COLORS
    ]
    ts["style_data_conditional"] = ts["style_data_conditional"] + style_grp

    table = dash_table.DataTable(
        id="dep-table",
        data=disp.to_dict("records"),
        columns=[
            {"name": "Nom",          "id": "nom_complet"},
            {"name": "Groupe",       "id": "groupe_abrev"},
            {"name": "Âge",          "id": "age"},
            {"name": "Département",  "id": "departement"},
            {"name": "Profession",   "id": "profession"},
        ],
        page_size=30,
        sort_action="native",
        style_cell_conditional=[
            {"if": {"column_id": "nom_complet"},
             "maxWidth": "0", "overflow": "hidden",
             "textOverflow": "ellipsis", "whiteSpace": "nowrap"},
            {"if": {"column_id": "groupe_abrev"}, "width": "80px",
             "textAlign": "center"},
            {"if": {"column_id": "age"}, "width": "55px", "textAlign": "center"},
            {"if": {"column_id": "departement"}, "width": "160px"},
            {"if": {"column_id": "profession"},
             "maxWidth": "0", "overflow": "hidden",
             "textOverflow": "ellipsis", "whiteSpace": "nowrap"},
        ],
        **ts,
    )

    return (
        f"{len(df):,} député(s)  — cliquer sur une ligne pour voir le détail",
        html.Div(table, className="an-card", style={"padding": "0"}),
    )


def _render_dep_detail(d_id, row):
    abrev = str(row.get("groupe_abrev", ""))
    color = gc(abrev)

    dep_v = VOTES_DEPUTE[VOTES_DEPUTE["depute_ref"] == d_id].copy() if not VOTES_DEPUTE.empty else pd.DataFrame()

    header = html.Div([
        html.Div([
            html.Span(row.get("nom_complet", ""),
                      style={"fontSize": "1.2rem", "fontWeight": "800", "marginRight": "12px"}),
            group_badge(abrev, f"{abrev} — {GROUP_FULL.get(abrev, abrev)}"),
        ], style={"display": "flex", "alignItems": "center", "flexWrap": "wrap", "gap": "6px"}),
    ], style={"borderLeft": f"5px solid {color}", "paddingLeft": "14px", "marginBottom": "16px"})

    age_str = f"{row.get('age', '—')} ans" if row.get("age") else "—"
    meta = dbc.Row([
        dbc.Col([html.Div("Âge", className="kpi-label"),
                 html.Div(age_str, style={"fontWeight": "600", "fontSize": "0.85rem"})]),
        dbc.Col([html.Div("Département", className="kpi-label"),
                 html.Div(str(row.get("departement", "—")), style={"fontWeight": "600", "fontSize": "0.85rem"})]),
        dbc.Col([html.Div("Profession", className="kpi-label"),
                 html.Div(str(row.get("profession", "—"))[:50], style={"fontWeight": "600", "fontSize": "0.85rem"})]),
        dbc.Col([html.Div("Votes enregistrés", className="kpi-label"),
                 html.Div(f"{len(dep_v):,}", style={"fontWeight": "600", "fontSize": "0.85rem"})]),
    ], className="mb-3")

    # Vote stats bars
    vote_bars = []
    if not dep_v.empty:
        vc    = dep_v["vote"].value_counts()
        total = len(dep_v)
        for key, label, c in [("pour", "Pour", "#059669"),
                               ("contre", "Contre", "#dc2626"),
                               ("abstention", "Abst.", "#d97706")]:
            n   = int(vc.get(key, 0))
            pct = round(100 * n / total) if total else 0
            vote_bars.append(html.Div([
                html.Span(label, className="vote-bar-label"),
                html.Div(
                    html.Div(style={"width": f"{pct}%", "height": "100%",
                                    "background": c, "borderRadius": "5px"}),
                    className="vote-bar-track",
                ),
                html.Span(f"{n:,} ({pct}%)", className="vote-bar-num"),
            ], className="vote-bar-row"))
    vote_section = html.Div([
        section_title("Comportement de vote"),
        *(vote_bars or [html.Div("Aucun vote enregistré.",
                                  style={"color": "#6b7280", "fontSize": "0.84rem"})]),
    ])

    # Recent vote history (last 30 scrutins)
    history_section = html.Div()
    if not dep_v.empty and not SCRUTINS.empty:
        merged = dep_v.merge(
            SCRUTINS[["uid", "date", "titre_court", "adopte"]].rename(columns={"uid": "scrutin_uid"}),
            on="scrutin_uid", how="left",
        ).sort_values("date", ascending=False).head(30)

        VOTE_COLOR = {"pour": "#059669", "contre": "#dc2626", "abstention": "#d97706"}
        VOTE_LABEL = {"pour": "Pour", "contre": "Contre", "abstention": "Abst."}

        history_rows = []
        for _, r in merged.iterrows():
            vote_key  = str(r.get("vote", "")).lower()
            adopte_v  = "✅" if str(r.get("adopte", "")).lower().replace("é", "e") == "adopte" else "❌"
            date_str  = r["date"].strftime("%Y-%m-%d") if pd.notna(r.get("date")) else "—"
            history_rows.append(html.Div([
                html.Span(date_str, style={
                    "fontSize": "0.73rem", "color": "#9ca3af",
                    "minWidth": "90px", "flexShrink": "0",
                }),
                html.Span(str(r.get("titre_court", ""))[:80], style={
                    "fontSize": "0.82rem", "flex": "1",
                    "overflow": "hidden", "textOverflow": "ellipsis", "whiteSpace": "nowrap",
                }),
                html.Span(VOTE_LABEL.get(vote_key, vote_key), style={
                    "fontSize": "0.75rem", "fontWeight": "700",
                    "color": VOTE_COLOR.get(vote_key, "#6b7280"),
                    "minWidth": "52px", "textAlign": "right", "flexShrink": "0",
                }),
                html.Span(adopte_v, style={"marginLeft": "8px", "flexShrink": "0"}),
            ], style={"display": "flex", "alignItems": "center", "gap": "10px",
                      "padding": "7px 12px", "borderBottom": "1px solid #f3f4f6"}))

        history_section = html.Div([
            section_title(f"30 derniers votes (sur {len(dep_v):,})"),
            html.Div(history_rows, style={
                "background": "white", "borderRadius": "6px",
                "border": "1px solid #f3f4f6", "overflow": "hidden",
            }),
        ], style={"marginTop": "20px"})

    return html.Div([
        _back_btn("dep-back-btn"),
        html.Div([
            header, meta,
            html.Hr(style={"margin": "0 0 16px 0"}),
            dbc.Row([
                dbc.Col(vote_section, width=4),
                dbc.Col(history_section, width=8),
            ], className="g-3"),
        ], className="an-card"),
    ])


# ─── CALLBACKS: DEPUTÉS (master-detail) ──────────────────────────────────────

@app.callback(
    Output("dep-list-section", "style"),
    Output("dep-detail-section", "children"),
    Input("dep-table", "active_cell"),
    State("dep-table", "derived_virtual_data"),
    prevent_initial_call=True,
)
def show_dep_detail(active_cell, data):
    if not active_cell or not data:
        return {}, html.Div()
    row = data[active_cell["row"]]
    dep_id = str(row.get("id", ""))
    if not dep_id:
        return {}, html.Div()
    try:
        detail = _render_dep_detail(dep_id, row)
    except Exception as e:
        detail = html.Div([
            _back_btn("dep-back-btn"),
            html.Div(f"Erreur: {e}", className="an-card"),
        ])
    return {"display": "none"}, detail


@app.callback(
    Output("dep-list-section", "style", allow_duplicate=True),
    Output("dep-detail-section", "children", allow_duplicate=True),
    Input("dep-back-btn", "n_clicks"),
    prevent_initial_call=True,
)
def dep_back(n):
    if not n:
        return no_update, no_update
    return {}, html.Div()


# ─── CALLBACKS: GROUPES ───────────────────────────────────────────────────────

@app.callback(Output("grp-detail", "children"), Input("grp-select", "value"))
def show_groupe(sel):
    if not sel:
        return html.Div()

    members = DEPUTES[DEPUTES["groupe_abrev"] == sel].sort_values("nom")
    org_row = ORGANES[ORGANES["libelle_abrev"] == sel]
    uid_grp = org_row.iloc[0]["uid"] if not org_row.empty else None
    color   = gc(sel)

    gv = (VOTES_GROUPE[VOTES_GROUPE["groupe_ref"] == uid_grp]
          if uid_grp and not VOTES_GROUPE.empty else pd.DataFrame())

    header = html.Div([
        html.Div([
            html.Span(sel, style={
                "fontSize": "1.5rem", "fontWeight": "800",
                "color": color, "marginRight": "12px",
            }),
            html.Span(GROUP_FULL.get(sel, sel), style={
                "fontSize": "1.05rem", "color": "#1a2744", "fontWeight": "500",
            }),
        ]),
        html.Div(f"Président(e) du groupe : {GROUP_PRESIDENTS.get(sel, '—')}",
                 style={"color": "#6b7280", "marginTop": "4px", "fontSize": "0.86rem"}),
    ], style={"borderLeft": f"6px solid {color}", "paddingLeft": "16px",
              "marginBottom": "22px"})

    age_mean = members["age"].mean()
    n_scr    = gv["scrutin_uid"].nunique() if not gv.empty else 0
    t_pour   = gv["pour"].sum()  if not gv.empty else 0
    t_total  = (gv["pour"].sum() + gv["contre"].sum() + gv["abstention"].sum()) if not gv.empty else 0
    taux_pour = f"{100*t_pour/t_total:.0f}%" if t_total else "—"

    kpis = dbc.Row([
        dbc.Col(kpi_card("Membres", str(len(members)), color=color), width=3),
        dbc.Col(kpi_card("Âge moyen", f"{age_mean:.0f} ans" if pd.notna(age_mean) else "—",
                         color=color), width=3),
        dbc.Col(kpi_card("Scrutins", f"{n_scr:,}", color=color), width=3),
        dbc.Col(kpi_card("Taux de vote Pour", taux_pour, color=color), width=3),
    ], className="g-3 mb-4")

    # Members table
    m_disp = members[["prenom", "nom", "age", "departement", "profession"]].copy()
    m_disp["age"] = m_disp["age"].apply(lambda x: f"{int(x)}" if pd.notna(x) else "")
    ts = _table_style()
    members_table = dash_table.DataTable(
        data=m_disp.to_dict("records"),
        columns=[{"name": c, "id": c} for c in ["prenom", "nom", "age", "departement", "profession"]],
        page_size=20,
        sort_action="native",
        **ts,
    )

    # Vote pie
    vote_chart = html.Div(style={"height": "10px"})
    if not gv.empty:
        tv = {
            "Pour":       int(gv["pour"].sum()),
            "Contre":     int(gv["contre"].sum()),
            "Abstention": int(gv["abstention"].sum()),
        }
        fig_pie = go.Figure(go.Pie(
            labels=list(tv.keys()), values=list(tv.values()),
            marker_colors=["#059669", "#dc2626", "#d97706"],
            hole=0.55, textinfo="label+percent",
            textfont=dict(family="Inter, sans-serif", size=12),
        ))
        fig_pie.update_layout(
            height=240, showlegend=False,
            margin=dict(l=0, r=0, t=10, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
        )
        vote_chart = dcc.Graph(figure=fig_pie, config={"displayModeBar": False})

    return html.Div([
        header, kpis,
        dbc.Row([
            dbc.Col(html.Div([
                section_title(f"Membres du groupe ({len(members)})"),
                members_table,
            ], className="an-card"), width=8),
            dbc.Col(html.Div([
                section_title("Votes exprimés (cumul)"),
                vote_chart,
            ], className="an-card"), width=4),
        ], className="g-3"),
    ])


# ─── CALLBACKS: SIMILARITÉ ────────────────────────────────────────────────────

@app.callback(Output("sim-matrix", "children"), Input("sim-theme", "value"))
def update_sim(theme):
    if VOTES_GROUPE.empty or ORGANES.empty:
        return html.Div("Données non disponibles.", style={"color": "#6b7280"})

    vg = VOTES_GROUPE.copy()
    if theme and theme != "Tous" and DOSSIERS is not None and "theme" in DOSSIERS.columns:
        dos_uids = set(DOSSIERS[DOSSIERS["theme"] == theme]["uid"].astype(str))
        sc_uids  = set(SCRUTINS[SCRUTINS["dossier_ref"].isin(dos_uids)]["uid"].astype(str))
        vg = vg[vg["scrutin_uid"].isin(sc_uids)]

    if vg.empty:
        return html.Div("Aucun scrutin pour ce thème.", style={"color": "#6b7280"})

    org_map = (ORGANES[["uid", "libelle_abrev"]]
               .drop_duplicates("uid")
               .set_index("uid")["libelle_abrev"])
    vg = vg.copy()
    vg["abrev"] = vg["groupe_ref"].map(org_map).fillna("")
    vg = vg[vg["abrev"].isin(POLITICAL_ORDER)]

    grps = [g for g in POLITICAL_ORDER if g in vg["abrev"].unique()]
    if len(grps) < 2:
        return html.Div("Pas assez de groupes pour calculer la similarité.", style={"color": "#6b7280"})

    vg_idx = {g: vg[vg["abrev"] == g].set_index("scrutin_uid")[["pour", "contre", "abstention"]]
              for g in grps}

    def dominant(row):
        m = max(row["pour"], row["contre"], row["abstention"])
        if row["pour"] == m:      return "pour"
        if row["contre"] == m:    return "contre"
        return "abstention"

    dom_series = {g: df.apply(dominant, axis=1) for g, df in vg_idx.items()}

    matrix = np.full((len(grps), len(grps)), np.nan)
    for i, g1 in enumerate(grps):
        matrix[i, i] = 100.0
        for j, g2 in enumerate(grps):
            if i == j:
                continue
            common = dom_series[g1].index.intersection(dom_series[g2].index)
            if len(common) == 0:
                continue
            matrix[i, j] = (dom_series[g1][common] == dom_series[g2][common]).mean() * 100

    text = np.where(np.isnan(matrix), "—", np.round(matrix, 0).astype(int).astype(str) + "%")

    fig = go.Figure(go.Heatmap(
        z=matrix, x=grps, y=grps,
        colorscale=[[0, "#fef2f2"], [0.5, "#dbeafe"], [1, "#1e3a5f"]],
        zmin=0, zmax=100,
        text=text, texttemplate="%{text}",
        hovertemplate="<b>%{y} × %{x}</b><br>Accord : %{z:.1f}%<extra></extra>",
    ))
    fig.update_layout(
        height=520,
        margin=dict(l=80, r=20, t=10, b=70),
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(tickfont=dict(size=12, family="Inter"), tickangle=0),
        yaxis=dict(tickfont=dict(size=12, family="Inter"), autorange="reversed"),
    )

    return html.Div([
        html.Div(dcc.Graph(figure=fig, config={"displayModeBar": False}),
                 className="an-card"),
        html.Div(
            f"Basé sur {vg['scrutin_uid'].nunique():,} scrutins · "
            "Pourcentage d'accord sur le vote dominant de chaque groupe",
            style={"fontSize": "0.76rem", "color": "#9ca3af", "marginTop": "6px"},
        ),
    ])


# ─── CALLBACKS: PAIRWISE ─────────────────────────────────────────────────────

@app.callback(
    Output("pair-detail", "children"),
    Input("pair-a", "value"),
    Input("pair-b", "value"),
)
def show_pairwise(grp_a, grp_b):
    if not grp_a or not grp_b or grp_a == grp_b or VOTES_GROUPE.empty or ORGANES.empty:
        return html.Div()

    org_map = (ORGANES[["uid", "libelle_abrev"]]
               .drop_duplicates("uid")
               .set_index("uid")["libelle_abrev"])
    uid_map = {v: k for k, v in org_map.items()}

    uid_a = uid_map.get(grp_a)
    uid_b = uid_map.get(grp_b)
    if not uid_a or not uid_b:
        return html.Div("Groupes non trouvés dans les données.", style={"color": "#6b7280"})

    va = VOTES_GROUPE[VOTES_GROUPE["groupe_ref"] == uid_a].set_index("scrutin_uid")
    vb = VOTES_GROUPE[VOTES_GROUPE["groupe_ref"] == uid_b].set_index("scrutin_uid")

    def dominant(row):
        m = max(row["pour"], row["contre"], row["abstention"])
        if row["pour"] == m:    return "pour"
        if row["contre"] == m:  return "contre"
        return "abstention"

    da = va[["pour", "contre", "abstention"]].apply(dominant, axis=1)
    db = vb[["pour", "contre", "abstention"]].apply(dominant, axis=1)
    common = da.index.intersection(db.index)

    if len(common) == 0:
        return html.Div("Aucun scrutin commun entre ces deux groupes.", style={"color": "#6b7280"})

    agree_mask = da[common] == db[common]
    accord      = agree_mask.mean() * 100
    n_agree     = int(agree_mask.sum())
    n_disagree  = len(common) - n_agree

    # ─ Build scrutin → theme mapping ─────────────────────────────────────────
    has_themes = DOSSIERS is not None and "theme" in DOSSIERS.columns
    scr_theme: pd.Series | None = None
    if has_themes:
        dos_map = (DOSSIERS[["uid", "theme"]]
                   .dropna(subset=["theme"])
                   .rename(columns={"uid": "dossier_ref"})
                   .set_index("dossier_ref")["theme"])
        scr_theme = SCRUTINS[["uid", "dossier_ref"]].set_index("uid")["dossier_ref"].map(dos_map)

    # ─ KPI summary ───────────────────────────────────────────────────────────
    summary = dbc.Row([
        dbc.Col(kpi_card("Scrutins communs", f"{len(common):,}", color="#6b7280"), width=3),
        dbc.Col(kpi_card("Accord global",  f"{accord:.0f}%",
                         f"{n_agree:,} scrutins", color="#059669"), width=3),
        dbc.Col(kpi_card("Désaccord",      f"{100-accord:.0f}%",
                         f"{n_disagree:,} scrutins", color="#dc2626"), width=3),
    ], className="g-3 mb-4")

    # ─ Theme breakdown bar chart ──────────────────────────────────────────────
    theme_chart = html.Div()
    if scr_theme is not None:
        theme_df = pd.DataFrame({
            "agree": agree_mask.values,
            "theme": scr_theme.reindex(common).values,
        }).dropna(subset=["theme"])

        if not theme_df.empty:
            t_agg = (theme_df.groupby("theme")
                     .agg(n=("agree", "count"), ok=("agree", "sum"))
                     .reset_index())
            t_agg["pct_accord"]   = 100 * t_agg["ok"]   / t_agg["n"]
            t_agg["pct_desaccord"] = 100 - t_agg["pct_accord"]
            t_agg = t_agg.sort_values("pct_accord", ascending=True)

            fig = go.Figure()
            fig.add_trace(go.Bar(
                y=t_agg["theme"], x=t_agg["pct_accord"],
                name="Accord", orientation="h",
                marker_color="#059669",
                text=t_agg["pct_accord"].round(0).astype(int).astype(str) + "%",
                textposition="inside",
                insidetextanchor="end",
                hovertemplate="<b>%{y}</b><br>Accord : %{x:.0f}%<br>%{customdata} scrutins<extra></extra>",
                customdata=t_agg["n"],
            ))
            fig.add_trace(go.Bar(
                y=t_agg["theme"], x=t_agg["pct_desaccord"],
                name="Désaccord", orientation="h",
                marker_color="#dc2626",
                text=t_agg.apply(
                    lambda r: f"{r['pct_desaccord']:.0f}%" if r["pct_desaccord"] > 8 else "",
                    axis=1),
                textposition="inside",
                insidetextanchor="start",
                hovertemplate="<b>%{y}</b><br>Désaccord : %{x:.0f}%<extra></extra>",
            ))
            fig.update_layout(
                barmode="stack",
                height=max(260, len(t_agg) * 32 + 60),
                margin=dict(l=0, r=20, t=10, b=0),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                legend=dict(orientation="h", y=-0.06, x=0,
                            font=dict(size=12, family="Inter")),
                xaxis=dict(showgrid=False, showticklabels=False, zeroline=False, range=[0, 100]),
                yaxis=dict(tickfont=dict(size=12, family="Inter")),
            )
            theme_chart = html.Div([
                section_title("Accord par thème"),
                dcc.Graph(figure=fig, config={"displayModeBar": False}),
            ], className="an-card", style={"marginBottom": "16px"})

    # ─ Disagreement table ─────────────────────────────────────────────────────
    diverg_uids = common[~agree_mask]
    if len(diverg_uids) == 0:
        diverg_section = html.Div(
            "Ces deux groupes votent toujours ensemble sur les scrutins communs !",
            style={"color": "#059669", "fontWeight": "600"})
    else:
        scr_info = (SCRUTINS[SCRUTINS["uid"].isin(diverg_uids)]
                    [["uid", "date", "titre_court", "adopte"]].copy())
        scr_info["date"] = scr_info["date"].dt.strftime("%Y-%m-%d")
        scr_info["adopte"] = scr_info["adopte"].map(
            lambda x: "✅" if str(x).lower().replace("é", "e") == "adopte" else "❌")
        vote_fr = {"pour": "Pour", "contre": "Contre", "abstention": "Abst."}
        scr_info[grp_a] = scr_info["uid"].map(lambda u: vote_fr.get(da.get(u, ""), "—"))
        scr_info[grp_b] = scr_info["uid"].map(lambda u: vote_fr.get(db.get(u, ""), "—"))
        if scr_theme is not None:
            scr_info["theme"] = scr_info["uid"].map(scr_theme).fillna("—")
        scr_info = scr_info.sort_values("date", ascending=False)

        vote_colors = {"Pour": "#059669", "Contre": "#dc2626", "Abst.": "#d97706"}
        ts = _table_style()
        ts["style_data_conditional"] = ts["style_data_conditional"] + [
            *[{"if": {"filter_query": f'{{{col}}} = "{v}"', "column_id": col},
               "color": vote_colors[v], "fontWeight": "700"}
              for col in (grp_a, grp_b) for v in vote_colors],
        ]

        disp_cols = ["date", "titre_court"]
        col_defs  = [
            {"name": "Date",    "id": "date"},
            {"name": "Scrutin", "id": "titre_court"},
        ]
        if scr_theme is not None:
            disp_cols.append("theme")
            col_defs.append({"name": "Thème", "id": "theme"})
        disp_cols += ["adopte", grp_a, grp_b]
        col_defs  += [
            {"name": "",    "id": "adopte"},
            {"name": grp_a, "id": grp_a},
            {"name": grp_b, "id": grp_b},
        ]

        diverg_section = html.Div([
            section_title(f"Scrutins en désaccord ({len(diverg_uids)})"),
            dash_table.DataTable(
                data=scr_info[disp_cols].to_dict("records"),
                columns=col_defs,
                page_size=20,
                sort_action="native",
                filter_action="native",
                style_cell_conditional=[
                    {"if": {"column_id": "titre_court"},
                     "maxWidth": "300px", "overflow": "hidden",
                     "textOverflow": "ellipsis", "whiteSpace": "nowrap"},
                    {"if": {"column_id": "theme"},
                     "maxWidth": "150px", "overflow": "hidden",
                     "textOverflow": "ellipsis", "whiteSpace": "nowrap"},
                    {"if": {"column_id": "adopte"}, "textAlign": "center", "width": "36px"},
                    *[{"if": {"column_id": g}, "textAlign": "center", "width": "90px"}
                      for g in (grp_a, grp_b)],
                ],
                **ts,
            ),
        ], className="an-card", style={"padding": "20px 24px"})

    return html.Div([summary, theme_chart, diverg_section])


# ─── RUN ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=False, port=8050)
