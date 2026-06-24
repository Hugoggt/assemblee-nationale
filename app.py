"""
Assemblée Nationale — application Streamlit de visualisation interactive.
Run: streamlit run app.py
"""

import json
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Assemblée Nationale",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

OUTPUT_DIR = Path(__file__).parent / "output"

# Political order left → right in the hemicycle
POLITICAL_ORDER = [
    "LFI-NFP", "GDR", "VEC", "SOC", "ECOS", "LIOT",
    "DEM", "HOR", "EPR", "DR", "UDDPLR", "RN", "NI",
]

COLORS = {
    "RN":      "#003189",
    "DR":      "#1a3a6b",
    "EPR":     "#0066CC",
    "HOR":     "#FF8C00",
    "DEM":     "#E85D04",
    "LIOT":    "#228B22",
    "SOC":     "#C41E3A",
    "ECOS":    "#2d6a4f",
    "GDR":     "#8B0000",
    "LFI-NFP": "#CC0000",
    "VEC":     "#2CA02C",
    "UDDPLR":  "#5B2C8C",
    "NI":      "#808080",
}

VOTE_COLORS = {
    "pour": "#27ae60", "contre": "#e74c3c",
    "abstention": "#f39c12", "non_votant": "#95a5a6",
}
VOTE_EMOJI = {
    "pour": "✅", "contre": "❌", "abstention": "🟡", "non_votant": "⬜",
}

# Known non-political-group organe refs to exclude from vote stats
_INVALID_GROUPS = {"PO0", "PO847173"}

# Simplify statut for display
_STATUT_SHORT = {
    "Promulgation de la loi": "✅ Promulguée",
    "Commission Mixte Paritaire": "🔄 CMP",
    "Conseil constitutionnel": "⚖️ Cons. const.",
    "Travaux": "📊 Rapport",
    "Débat": "💬 Débat",
}

# ── Institutional info (17th legislature) ─────────────────────────────────────
# Sources: assemblee-nationale.fr, décret de dissolution du 9 juin 2024
_LEGISLATURE_INFO = {
    "dissolution": "9 juin 2024",
    "elections_1er_tour": "30 juin 2024",
    "elections_2e_tour": "7 juillet 2024",
    "debut_legislature": "18 juillet 2024",
    "fin_prevue": "2029 (sauf dissolution anticipée)",
    "sieges_total": 577,
    "majorite_absolue": 289,
    "president_an": "Yaël Braun-Pivet",
    "groupe_president_an": "EPR",
    "premier_ministre": "François Bayrou (depuis déc. 2024)",
    "vice_presidents": [
        "Naïma Moutchou (HOR)",
        "Sébastien Chenu (RN)",
        "Valérie Rabault (SOC)",
        "Charles de Courson (LIOT)",
        "Annie Genevard (DR)",
        "Éric Coquerel (LFI-NFP)",
    ],
}

# Group presidents as of start of 17th legislature (July 2024) — may evolve
_GROUP_PRESIDENTS = {
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

_GROUP_FULL_NAMES = {
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


def _short_statut(s: str) -> str:
    if not s:
        return "—"
    sl = s.lower()
    if "promulgation" in sl:
        return "✅ Promulguée"
    if "commission mixte paritaire" in sl:
        return "🔄 CMP"
    if "conseil constitutionnel" in sl:
        return "⚖️ Cons. const."
    if ("sénat" in sl or "senat" in sl) and "lecture" in sl:
        return "📘 Lecture Sénat"
    if "sénat" in sl or "senat" in sl:
        return "📤 Transmis Sénat"
    if "lecture" in sl:
        return "🔵 Lecture AN"
    if "dépôt" in sl or "depot" in sl:
        return "📄 Déposé"
    if "rapport" in sl or "travaux" in sl:
        return "📊 Rapport"
    if "débat" in sl or "debat" in sl:
        return "💬 Débat"
    return s[:35]


def gc(abrev: str) -> str:
    return COLORS.get(str(abrev), "#aaaaaa")


# ── Loaders ───────────────────────────────────────────────────────────────────

@st.cache_data
def load_deputes():
    df = pd.read_csv(OUTPUT_DIR / "deputes.csv", encoding="utf-8")
    df["age"] = pd.to_numeric(df["age"], errors="coerce")
    df["nom_complet"] = df["prenom"].fillna("") + " " + df["nom"].fillna("")
    return df


@st.cache_data
def load_organes():
    with open(OUTPUT_DIR / "organes.json", encoding="utf-8") as f:
        orgs = pd.DataFrame(json.load(f))
    # exclude non-political refs
    return orgs[~orgs["uid"].isin(_INVALID_GROUPS)].copy()


@st.cache_data
def load_scrutins():
    df = pd.read_csv(OUTPUT_DIR / "scrutins_summary.csv", encoding="utf-8")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for c in ["nb_votants", "pour", "contre", "abstention"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["adopte_bool"] = df["adopte"].str.lower().str.contains("adopt", na=False)
    df["titre_court"] = df["titre"].str[:90]
    df["dossier_ref"] = df["dossier_ref"].fillna("").astype(str)
    return df


@st.cache_data
def load_votes_groupe():
    df = pd.read_csv(OUTPUT_DIR / "scrutins_votes_groupe.csv", encoding="utf-8")
    for c in ["pour", "contre", "abstention"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    # Remove non-political-group rows
    return df[~df["groupe_ref"].isin(_INVALID_GROUPS)].copy()


@st.cache_data
def load_votes_depute():
    return pd.read_csv(
        OUTPUT_DIR / "scrutins_votes_depute.csv",
        encoding="utf-8",
        dtype={"scrutin_uid": "category", "depute_ref": "category",
               "groupe_ref": "category", "vote": "category"},
    )


@st.cache_data
def load_dossiers_themes():
    for fname in ["dossiers_themes.csv", "dossiers.csv"]:
        p = OUTPUT_DIR / fname
        if p.exists():
            df = pd.read_csv(p, encoding="utf-8")
            df["date_depot"] = pd.to_datetime(df["date_depot"], errors="coerce")
            if "theme" not in df.columns:
                df["theme"] = "Non classé"
                df["theme_emoji"] = "📌"
            return df
    return None


@st.cache_data(ttl=3600 * 24)
def load_dept_geojson():
    """96 metropolitan departments from gregoiredavid/france-geojson (proven reliable)."""
    url = "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/departements.geojson"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


_DOMTOM_CENTERS = {
    "Guadeloupe": {"lat": 16.17, "lon": -61.58, "zoom": 7.4},
    "Martinique":  {"lat": 14.65, "lon": -61.0,  "zoom": 8.0},
    "Guyane":      {"lat":  4.0,  "lon": -53.1,  "zoom": 4.0},
    "La Réunion":  {"lat": -21.1, "lon":  55.5,  "zoom": 7.4},
    "Mayotte":     {"lat": -12.8, "lon":  45.15, "zoom": 8.5},
}


def _carte_france(deputes):
    try:
        geo = load_dept_geojson()
    except Exception as e:
        st.error(f"Impossible de charger la carte (vérifiez la connexion) : {e}")
        return

    # Per-department dominant group + detail
    rows = []
    for dept, sub in deputes.groupby("departement"):
        counts = sub["groupe_abrev"].value_counts()
        rows.append({
            "departement": dept,
            "dominant": counts.index[0],
            "n_total": len(sub),
            "n_groupes": int(counts.nunique()),
            "detail": " · ".join(f"{g} {n}" for g, n in counts.items()),
        })
    dept_df = pd.DataFrame(rows)

    # gregoiredavid GeoJSON = 96 metro departments only
    geo_noms   = {f["properties"]["nom"] for f in geo["features"]}
    dept_metro = dept_df[dept_df["departement"].isin(geo_noms)].copy()
    dept_outre = dept_df[~dept_df["departement"].isin(geo_noms)].copy()

    # ── Main metro map ─────────────────────────────────────────────────────────
    fig = px.choropleth_mapbox(
        dept_metro,
        geojson=geo,
        locations="departement",
        featureidkey="properties.nom",
        color="dominant",
        color_discrete_map=COLORS,
        hover_name="departement",
        custom_data=["dominant", "n_total", "n_groupes", "detail"],
        mapbox_style="carto-positron",
        zoom=4.8,
        center={"lat": 46.5, "lon": 2.5},
        opacity=0.88,
    )
    fig.update_traces(
        hovertemplate=(
            "<b>%{hovertext}</b><br>"
            "<b>%{customdata[0]}</b> · %{customdata[1]} député(s)<br>"
            "<i style='font-size:11px'>%{customdata[3]}</i>"
            "<extra></extra>"
        ),
        marker_line_color="white",
        marker_line_width=0.6,
    )
    fig.update_layout(
        height=540,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    sel = st.plotly_chart(fig, on_select="rerun", key="france_map",
                          use_container_width=True)

    # Custom legend — cleaner than Plotly's built-in overlay
    groups_shown = [g for g in POLITICAL_ORDER if g in dept_metro["dominant"].values]
    legend_parts = []
    for g in groups_shown:
        color = COLORS.get(g, "#aaa")
        full = _GROUP_FULL_NAMES.get(g, g)
        legend_parts.append(
            f"<span style='display:inline-flex;align-items:center;gap:5px;"
            f"padding:2px 9px 2px 6px;border-radius:4px;border-left:4px solid {color};"
            f"background:#f7f7f7;font-size:0.76em'>"
            f"<b style='color:{color}'>{g}</b>"
            f"<span style='color:#555'>{full}</span></span>"
        )
    st.markdown(
        "<div style='display:flex;flex-wrap:wrap;gap:5px;margin:2px 0 6px 0'>"
        + "".join(legend_parts) + "</div>",
        unsafe_allow_html=True,
    )
    st.caption("Cliquez sur un département pour afficher ses circonscriptions et députés.")

    # ── DOM-TOM mini-maps (Scattermapbox — tiles show actual island geography) ─
    dom_in_data = [name for name in _DOMTOM_CENTERS
                   if name in dept_outre["departement"].values]
    if dom_in_data:
        st.markdown("**Outre-mer**")
        cols = st.columns(len(dom_in_data))
        for col, name in zip(cols, dom_in_data):
            cfg = _DOMTOM_CENTERS[name]
            row = dept_outre[dept_outre["departement"] == name].iloc[0]
            color_d = COLORS.get(str(row["dominant"]), "#aaa")

            fig_m = go.Figure(go.Scattermapbox(
                lat=[cfg["lat"]],
                lon=[cfg["lon"]],
                mode="markers",
                marker=go.scattermapbox.Marker(
                    size=28, color=color_d, opacity=0.75,
                ),
                text=[f"<b>{name}</b><br><b>{row['dominant']}</b>"
                      f" · {row['n_total']} député(s)<br>{row['detail']}"],
                hovertemplate="%{text}<extra></extra>",
            ))
            fig_m.update_layout(
                mapbox=dict(
                    style="carto-positron",
                    center=dict(lat=cfg["lat"], lon=cfg["lon"]),
                    zoom=cfg["zoom"],
                ),
                height=200,
                margin=dict(l=0, r=0, t=28, b=0),
                showlegend=False,
                paper_bgcolor="rgba(0,0,0,0)",
                title=dict(
                    text=(f"<b style='color:{color_d}'>{row['dominant']}</b>"
                          f" <span style='color:#555;font-size:0.85em'>{name}</span>"
                          f" <span style='color:#aaa;font-size:0.8em'>({row['n_total']})</span>"),
                    x=0.5, font=dict(size=11),
                ),
            )
            with col:
                st.plotly_chart(fig_m, use_container_width=True, key=f"dom_{name}")

    # Other overseas collectivités
    autres = dept_outre[~dept_outre["departement"].isin(_DOMTOM_CENTERS)].sort_values("departement")
    if not autres.empty:
        with st.expander(f"Autres territoires ({len(autres)})"):
            for _, row in autres.iterrows():
                color = COLORS.get(row["dominant"], "#aaa")
                st.markdown(
                    f"<span style='border-left:4px solid {color};padding:2px 10px;"
                    f"margin:2px;border-radius:0 4px 4px 0;background:#f8f8f8;"
                    f"display:inline-block;font-size:0.85em'>"
                    f"<b style='color:{color}'>{row['dominant']}</b> "
                    f"<span style='color:#555'>{row['departement']}</span> "
                    f"<small style='color:#999'>({row['n_total']})</small></span>",
                    unsafe_allow_html=True,
                )

    # ── Click → show constituencies ────────────────────────────────────────────
    selected_dept = None
    if sel:
        selection = getattr(sel, "selection", None) or {}
        pts = (selection.get("points", []) if isinstance(selection, dict)
               else getattr(selection, "points", []))
        if pts:
            pt = pts[0]
            selected_dept = pt.get("location") or pt.get("hovertext")

    if selected_dept:
        st.divider()
        dept_deps = deputes[deputes["departement"] == selected_dept].copy()
        dept_deps["_circ_num"] = pd.to_numeric(dept_deps["circonscription"], errors="coerce")
        dept_deps = dept_deps.sort_values("_circ_num").drop(columns="_circ_num")

        st.subheader(f"📍 {selected_dept} — {len(dept_deps)} député(s)")
        for _, dep in dept_deps.iterrows():
            color_d = gc(str(dep.get("groupe_abrev", "")))
            circ = str(dep.get("circonscription", "")).strip()
            circ_label = ("1ère circ." if circ == "1"
                          else f"{circ}e circ." if circ.isdigit() else circ)
            age_s = f"· {int(dep['age'])} ans" if pd.notna(dep.get("age")) else ""
            st.markdown(
                f"<div style='display:flex;align-items:center;gap:10px;"
                f"padding:7px 14px;border-radius:6px;background:#f5f5f5;margin:3px 0'>"
                f"<span style='background:{color_d};color:#fff;padding:2px 8px;"
                f"border-radius:4px;font-size:0.78em;font-weight:bold;"
                f"min-width:60px;text-align:center'>{dep.get('groupe_abrev', '')}</span>"
                f"<span style='font-weight:500;color:#111'>"
                f"{dep.get('prenom', '')} {dep.get('nom', '')}</span>"
                f"<span style='color:#888;font-size:0.82em'>{age_s}</span>"
                f"<span style='color:#aaa;font-size:0.8em;margin-left:auto'>{circ_label}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
        st.caption("Cliquez sur un autre département pour changer, ou sur le même pour désélectionner.")


@st.cache_data
def make_vote_pivot(_vd):
    v = _vd[_vd["vote"] != "non_votant"].copy()
    v["vote"] = v["vote"].astype(str)
    return v.pivot_table(
        index="scrutin_uid", columns="depute_ref",
        values="vote", aggfunc="first",
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def nav(page: str, **kw):
    st.session_state["page"] = page
    for k, v in kw.items():
        st.session_state[k] = v
    st.rerun()


def _fmt(v) -> str:
    return "—" if pd.isna(v) else f"{int(v):,}"


def _group_majority_position(vg: pd.DataFrame, org_uid_col="groupe_ref") -> pd.DataFrame:
    """Return a pivot scrutin_uid × group_abrev → 'pour'/'contre'/'abstention'."""
    v = vg.copy()
    v["position"] = "abstention"
    v.loc[v["pour"] > v["contre"], "position"] = "pour"
    v.loc[v["contre"] > v["pour"], "position"] = "contre"
    return v


def _hemicycle_fig(deputes):
    counts = deputes.groupby("groupe_abrev").size()
    ordered = [(g, int(counts[g])) for g in POLITICAL_ORDER if g in counts.index]
    others  = [(g, int(counts[g])) for g in counts.index if g not in POLITICAL_ORDER]
    all_groups = ordered + others
    total = sum(n for _, n in all_groups)

    # 10 rows from r=1.5 to r=3.5 → ~10px spacing at 6px markers (no overlap)
    n_rows = 10
    radii = np.linspace(1.5, 3.5, n_rows)
    weights = radii / radii.sum()

    fig = go.Figure()
    current_angle = np.pi

    for g, n in all_groups:
        if n == 0:
            continue
        span = np.pi * n / total
        end_angle = current_angle - span

        spr = np.round(weights * n).astype(int)
        spr[-1] += n - spr.sum()

        xs_g, ys_g = [], []
        # Minimum absolute gap of 0.04 rad between groups (≈ 2 seat-widths at r=2.5)
        gap = max(0.04, span * 0.04)
        for r, n_s in zip(radii, spr):
            if n_s <= 0:
                continue
            angles = np.linspace(current_angle - gap, end_angle + gap, n_s)
            for theta in angles:
                xs_g.append(r * np.cos(theta))
                ys_g.append(r * np.sin(theta))

        color = COLORS.get(g, "#aaa")
        full = _GROUP_FULL_NAMES.get(g, g)
        fig.add_trace(go.Scatter(
            x=xs_g, y=ys_g, mode="markers",
            name=f"{g} ({n})",
            marker=dict(color=color, size=6, line=dict(width=0.5, color="white")),
            hovertemplate=f"<b>{g}</b> — {full}<br>{n} sièges<extra></extra>",
        ))
        current_angle = end_angle

    fig.update_layout(
        height=460,
        legend=dict(orientation="v", x=1.01, y=0.95, font_size=12),
        xaxis=dict(visible=False, range=[-4.0, 4.0]),
        yaxis=dict(visible=False, range=[-0.4, 4.0], scaleanchor="x", scaleratio=1),
        margin=dict(l=0, r=150, t=10, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    for r_arc in [radii[0] * 0.87, radii[-1] * 1.06]:
        t = np.linspace(np.pi, 0, 150)
        fig.add_trace(go.Scatter(
            x=r_arc * np.cos(t), y=r_arc * np.sin(t),
            mode="lines", line=dict(color="#e0e0e0", width=1),
            showlegend=False, hoverinfo="skip",
        ))
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# ACCUEIL
# ══════════════════════════════════════════════════════════════════════════════

def page_accueil(deputes, scrutins, organes):
    st.title("🏛️ Assemblée Nationale — 17ème législature")
    st.caption("Données open data officiel · assemblee-nationale.fr")

    # ── Institutional banner ─────────────────────────────────────────────────
    info = _LEGISLATURE_INFO
    def _card(label: str, value: str, sub: str = "") -> str:
        sub_html = f"<div style='font-size:0.8em;color:#666;margin-top:2px'>{sub}</div>" if sub else ""
        return (
            f"<div style='background:#f0f4ff;border-radius:10px;padding:14px 16px'>"
            f"<div style='font-size:0.72em;color:#555;text-transform:uppercase;"
            f"letter-spacing:0.05em;font-weight:600'>{label}</div>"
            f"<div style='font-size:1.05em;font-weight:bold;color:#111;margin-top:4px'>{value}</div>"
            f"{sub_html}</div>"
        )

    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.markdown(_card("Présidente de l'AN", info["president_an"],
                         f"Groupe {info['groupe_president_an']}"), unsafe_allow_html=True)
    col_b.markdown(_card("Premier ministre", info["premier_ministre"]), unsafe_allow_html=True)
    col_c.markdown(_card("Élections législatives", info["elections_2e_tour"],
                         f"Dissolution : {info['dissolution']}"), unsafe_allow_html=True)
    col_d.markdown(_card("Fin prévue", info["fin_prevue"],
                         f"Début : {info['debut_legislature']}"), unsafe_allow_html=True)

    st.markdown("")

    # Vice-présidents
    with st.expander("Bureau de l'Assemblée Nationale — Vice-présidents & seuils"):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Vice-présidents**")
            for vp in info["vice_presidents"]:
                st.markdown(f"- {vp}")
        with c2:
            st.markdown("**Seuils clés**")
            st.markdown(f"- Sièges totaux : **{info['sieges_total']}**")
            st.markdown(f"- Majorité absolue : **{info['majorite_absolue']} voix** (50 % + 1)")
            st.markdown(f"- Majorité simple : nombre de voix le plus élevé (votes exprimés)")
            st.markdown(f"- Motion de censure : **{info['majorite_absolue']} signatures** minimum")

    st.divider()

    # ── KPIs from data ──────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Députés", f"{len(deputes):,}")
    c2.metric("Scrutins", f"{len(scrutins):,}")
    adoptes = int(scrutins["adopte_bool"].sum())
    c3.metric("Adoptés", f"{adoptes:,}", f"{100*adoptes/len(scrutins):.0f}% des votes")
    c4.metric("Groupes politiques", len(organes))

    st.divider()

    # Sièges par groupe — compact
    col_bar, _ = st.columns([2, 1])
    with col_bar:
        counts = deputes.groupby("groupe_abrev").size().reset_index(name="n")
        counts["order"] = counts["groupe_abrev"].map(
            lambda a: POLITICAL_ORDER.index(a) if a in POLITICAL_ORDER else 99)
        counts = counts.sort_values("order")
        fig = px.bar(
            counts, x="n", y="groupe_abrev", orientation="h",
            color="groupe_abrev", color_discrete_map=COLORS,
            labels={"n": "Sièges", "groupe_abrev": ""},
            text="n",
            title="Sièges par groupe politique",
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(
            showlegend=False, height=300,
            margin=dict(l=0, r=50, t=36, b=0),
            title_font_size=14,
            yaxis=dict(categoryorder="array",
                       categoryarray=list(reversed(counts["groupe_abrev"].tolist()))),
        )
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    ordered_org = sorted(
        organes.to_dict("records"),
        key=lambda r: POLITICAL_ORDER.index(r.get("libelle_abrev", ""))
        if r.get("libelle_abrev") in POLITICAL_ORDER else 99,
    )

    tab_hemi, tab_carte = st.tabs(["🏛️ Hémicycle", "🗺️ Carte"])

    with tab_hemi:
        col_hemi, col_list = st.columns([2, 1])
        with col_hemi:
            st.plotly_chart(_hemicycle_fig(deputes), use_container_width=True)
        with col_list:
            st.markdown("##### Composition")
            for org in ordered_org:
                abrev = str(org.get("libelle_abrev", ""))
                nb = len(deputes[deputes["groupe_abrev"] == abrev])
                color = gc(abrev)
                age_m = deputes[deputes["groupe_abrev"] == abrev]["age"].mean()
                age_s = f"· {age_m:.0f} ans" if pd.notna(age_m) else ""
                st.markdown(
                    f"<div style='border-left:5px solid {color};padding:4px 10px;"
                    f"margin:3px 0;border-radius:0 6px 6px 0'>"
                    f"<b style='color:{color}'>{abrev}</b> "
                    f"<span style='color:#555;font-size:0.82em'>{org.get('libelle','')}</span><br>"
                    f"<small style='color:#888'>{nb} sièges {age_s}</small></div>",
                    unsafe_allow_html=True,
                )

    with tab_carte:
        _carte_france(deputes)


# ══════════════════════════════════════════════════════════════════════════════
# DÉPUTÉS
# ══════════════════════════════════════════════════════════════════════════════

def page_deputes(deputes, votes_depute, scrutins):
    focus_id = st.session_state.get("focus_depute")
    if focus_id:
        dep_row = deputes[deputes["id"] == focus_id]
        if not dep_row.empty:
            if st.button("← Retour à la liste"):
                del st.session_state["focus_depute"]
                st.rerun()
            _detail_depute(dep_row.iloc[0], votes_depute, scrutins)
            return

    st.title("👥 Députés")
    c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
    search = c1.text_input("🔍 Rechercher", placeholder="Nom ou prénom…")
    groupes = ["Tous"] + [g for g in POLITICAL_ORDER if g in deputes["groupe_abrev"].values]
    grp = c2.selectbox("Groupe politique", groupes)
    depts = ["Tous"] + sorted(deputes["departement"].dropna().unique())
    dept = c3.selectbox("Département", depts)
    age_r = c4.slider("Tranche d'âge", 18, 90, (18, 90))

    df = deputes.copy()
    if search:
        df = df[df["nom_complet"].str.contains(search, case=False, na=False)]
    if grp != "Tous":
        df = df[df["groupe_abrev"] == grp]
    if dept != "Tous":
        df = df[df["departement"] == dept]
    df = df[df["age"].isna() | ((df["age"] >= age_r[0]) & (df["age"] <= age_r[1]))]

    st.caption(f"{len(df)} député(s) — cliquez pour voir le détail")
    disp = df[["nom_complet", "groupe_abrev", "age", "departement", "profession"]].copy()
    disp.columns = ["Nom complet", "Groupe", "Âge", "Département", "Profession"]
    sel = st.dataframe(disp, use_container_width=True, hide_index=True,
                       on_select="rerun", selection_mode="single-row",
                       key="deputes_table", height=440,
                       column_config={"Âge": st.column_config.NumberColumn(width="small", format="%d ans")})
    if sel.selection.rows:
        dep = df.iloc[sel.selection.rows[0]]
        st.divider()
        _detail_depute(dep, votes_depute, scrutins)


def _detail_depute(dep, votes_depute, scrutins):
    abrev = str(dep.get("groupe_abrev", ""))
    color = gc(abrev)
    st.markdown(
        f"<h2>{dep['prenom']} {dep['nom']} &nbsp;"
        f"<span style='background:{color};color:white;padding:3px 10px;"
        f"border-radius:6px;font-size:0.6em'>{abrev}</span></h2>",
        unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    c1.metric("Groupe", dep.get("groupe", "—"))
    c2.metric("Âge", f"{int(dep['age'])} ans" if pd.notna(dep.get("age")) else "—")
    c3.metric("Département", str(dep.get("departement", "—")))

    dep_id = dep["id"]
    dep_votes = votes_depute[votes_depute["depute_ref"] == dep_id].copy()
    if dep_votes.empty:
        st.info("Aucun vote nominatif enregistré.")
        return

    vc = dep_votes["vote"].value_counts()
    total = len(dep_votes)
    c1, c2, c3, c4 = st.columns(4)
    for col, key in [(c1, "pour"), (c2, "contre"), (c3, "abstention"), (c4, "non_votant")]:
        n = int(vc.get(key, 0))
        col.metric(f"{VOTE_EMOJI[key]} {key.replace('_',' ').title()}", n, f"{100*n/total:.0f}%")

    st.subheader("Historique des votes")
    history = dep_votes.merge(
        scrutins[["uid", "titre", "date", "adopte_bool", "adopte"]],
        left_on="scrutin_uid", right_on="uid", how="left",
    ).sort_values("date", ascending=False)
    disp = history[["date", "vote", "titre", "adopte"]].copy()
    disp["date"] = disp["date"].dt.strftime("%Y-%m-%d")
    disp["vote"] = disp["vote"].map(lambda v: f"{VOTE_EMOJI.get(str(v),'?')} {v}")
    disp.columns = ["Date", "Vote", "Titre du scrutin", "Résultat"]
    sel = st.dataframe(disp, use_container_width=True, hide_index=True,
                       on_select="rerun", selection_mode="single-row",
                       key=f"hist_{dep_id}", height=380,
                       column_config={"Titre du scrutin": st.column_config.TextColumn(width="large")})
    if sel.selection.rows:
        scr_uid = str(history.iloc[sel.selection.rows[0]]["scrutin_uid"])
        if st.button("📊 Voir ce scrutin →", key=f"goto_scr_{scr_uid}"):
            nav("Lois", focus_scrutin=scr_uid)


# ══════════════════════════════════════════════════════════════════════════════
# LOIS
# ══════════════════════════════════════════════════════════════════════════════

def page_lois(dossiers, scrutins, votes_groupe, votes_depute, deputes, organes):
    focus_scrutin = st.session_state.get("focus_scrutin")
    if focus_scrutin:
        scr = scrutins[scrutins["uid"] == focus_scrutin]
        if not scr.empty:
            if st.button("← Retour aux lois"):
                del st.session_state["focus_scrutin"]
                st.session_state.pop("focus_loi", None)
                st.rerun()
            _detail_scrutin(scr.iloc[0], votes_groupe, votes_depute, deputes, organes)
            return

    focus_loi = st.session_state.get("focus_loi")
    if focus_loi and dossiers is not None:
        dos = dossiers[dossiers["uid"] == focus_loi]
        if not dos.empty:
            if st.button("← Retour aux lois"):
                del st.session_state["focus_loi"]
                st.rerun()
            _detail_loi(dos.iloc[0], scrutins, votes_groupe, votes_depute, deputes, organes)
            return

    st.title("📋 Lois & Propositions")

    if dossiers is None:
        st.warning("Lancez `python main.py` pour télécharger les données.")
        return

    with st.expander("❓ Comment fonctionne cette page ?"):
        st.markdown("""
**Comment les statuts sont déterminés**

Chaque dossier législatif suit un parcours officiel enregistré dans les données open data de l'AN.
L'API fournit la liste des **actes législatifs** (étapes) que le texte a franchis.
Le **statut affiché** est la dernière étape connue :

| Statut | Signification |
|---|---|
| 🔵 En cours | 1ère ou 2ème lecture à l'AN ou au Sénat, pas encore adopté définitivement |
| 🔄 CMP | Commission Mixte Paritaire — AN et Sénat cherchent un accord |
| ⚖️ Cons. const. | Renvoi au Conseil Constitutionnel avant promulgation |
| ✅ Promulguée | Signée par le Président de la République — c'est la loi |
| 📊 Rapport | Rapport d'information, pas une loi (ex. mission de contrôle) |

**Loi, proposition, amendement — quelles différences ?**
- **Projet de loi** : texte déposé par le gouvernement
- **Proposition de loi** : texte déposé par un ou plusieurs députés
- **Amendement** : modification proposée à un article — chaque amendement fait l'objet d'un **scrutin séparé** dans l'hémicycle
- Un dossier peut concentrer **des dizaines de scrutins** (un par article ou amendement voté) avant le vote final "sur l'ensemble"

**Les colonnes 1er vote / Dernier vote** indiquent quand l'AN a commencé et terminé l'examen du texte.
""")

    st.markdown("")

    has_themes = "theme" in dossiers.columns

    # Agréger scrutins par dossier
    scr_linked = scrutins[scrutins["dossier_ref"].str.startswith("DLR", na=False)]
    scr_agg = (
        scr_linked.groupby("dossier_ref")
        .agg(
            nb_scrutins=("uid", "count"),
            premier_vote=("date", "min"),
            dernier_vote=("date", "max"),
        )
        .reset_index()
        .rename(columns={"dossier_ref": "uid"})
    )
    df = dossiers.merge(scr_agg, on="uid", how="left")
    df["nb_scrutins"] = df["nb_scrutins"].fillna(0).astype(int)
    df["statut_court"] = df["statut"].apply(_short_statut)

    # Filtres
    c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
    search = c1.text_input("🔍 Titre")
    if has_themes:
        themes = ["Tous"] + sorted(dossiers["theme"].dropna().unique())
        theme_f = c2.selectbox("🏷 Thème", themes)
    else:
        theme_f = "Tous"
    types = ["Tous"] + sorted(dossiers["type_dossier"].dropna().unique())
    type_f = c3.selectbox("Type", types)

    statuts_available = sorted(df["statut_court"].dropna().unique())
    statut_f = c4.selectbox("Statut", ["Tous"] + statuts_available)

    if search:
        df = df[df["titre"].str.contains(search, case=False, na=False)]
    if theme_f != "Tous":
        df = df[df["theme"] == theme_f]
    if type_f != "Tous":
        df = df[df["type_dossier"] == type_f]
    if statut_f != "Tous":
        df = df[df["statut_court"] == statut_f]

    sort_opts = {
        "Plus de scrutins": (["nb_scrutins", "premier_vote"], [False, False]),
        "Date de dépôt ↓": (["date_depot"], [False]),
        "Date de dépôt ↑": (["date_depot"], [True]),
        "Statut A→Z": (["statut_court", "premier_vote"], [True, False]),
    }
    cs, _ = st.columns([2, 6])
    sort_key = cs.selectbox("Trier par", list(sort_opts), key="lois_sort")
    sort_cols, sort_asc = sort_opts[sort_key]
    df = df.sort_values(sort_cols, ascending=sort_asc)

    st.caption(f"{len(df)} dossier(s) · {int(df['nb_scrutins'].sum())} scrutins liés · cliquez pour le détail")

    # Build display table
    has_urls = "url_an" in df.columns
    cols_show = ["date_depot", "titre", "type_dossier", "statut_court", "nb_scrutins", "premier_vote", "dernier_vote"]
    if has_themes:
        cols_show = ["date_depot", "theme", "titre", "type_dossier", "statut_court", "nb_scrutins", "premier_vote", "dernier_vote"]
    if has_urls:
        cols_show.append("url_an")

    disp = df[cols_show].copy()
    for dc in ["date_depot", "premier_vote", "dernier_vote"]:
        disp[dc] = pd.to_datetime(disp[dc], errors="coerce").dt.strftime("%Y-%m-%d")

    if has_themes:
        col_names = ["Dépôt", "Thème", "Titre", "Type", "Statut", "Scrutins", "1er vote", "Dernier vote"]
    else:
        col_names = ["Dépôt", "Titre", "Type", "Statut", "Scrutins", "1er vote", "Dernier vote"]
    if has_urls:
        col_names.append("Lien AN")
    disp.columns = col_names

    col_cfg = {"Titre": st.column_config.TextColumn(width="large")}
    if has_urls:
        col_cfg["Lien AN"] = st.column_config.LinkColumn(
            "Lien AN", display_text="🔗 assemblee-nationale.fr")

    sel = st.dataframe(
        disp, use_container_width=True, hide_index=True,
        on_select="rerun", selection_mode="single-row",
        key="lois_table", height=500,
        column_config=col_cfg,
    )
    if sel.selection.rows:
        dos = df.iloc[sel.selection.rows[0]]
        st.divider()
        _detail_loi(dos, scrutins, votes_groupe, votes_depute, deputes, organes)


def _detail_loi(dos, scrutins, votes_groupe, votes_depute, deputes, organes):
    has_themes = "theme" in dos.index
    url_an = str(dos.get("url_an", "") or "").strip()

    title_col, link_col = st.columns([5, 1])
    title_col.markdown(f"### {dos['titre']}")
    if url_an:
        link_col.markdown(
            f"<div style='text-align:right;padding-top:12px'>"
            f"<a href='{url_an}' target='_blank' style='font-size:0.85em;"
            f"background:#0066CC;color:white;padding:5px 12px;border-radius:6px;"
            f"text-decoration:none;font-weight:500'>🔗 Texte sur AN</a></div>",
            unsafe_allow_html=True,
        )

    if has_themes and pd.notna(dos.get("theme")):
        theme_tag = f"{dos.get('theme_emoji','')} {dos.get('theme','')}".strip()
        st.markdown(
            f"<span style='background:#eef;padding:3px 10px;border-radius:12px;font-size:0.85em'>"
            f"{theme_tag}</span>",
            unsafe_allow_html=True)

    # Metadata row
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Type", str(dos.get("type_dossier", "—")))
    c2.metric("Dépôt", str(dos.get("date_depot", "—"))[:10] if pd.notna(dos.get("date_depot")) else "—")
    c3.metric("Statut actuel", _short_statut(str(dos.get("statut", ""))))

    uid = dos["uid"]
    law_scruts = scrutins[scrutins["dossier_ref"] == uid].sort_values("date").copy()

    if law_scruts.empty:
        c4.metric("Scrutins", 0)
        st.info("Aucun scrutin lié à ce dossier.")
        return

    last = law_scruts.iloc[-1]
    c4.metric("Scrutins", len(law_scruts))

    # Explain the current state
    adopte_final = bool(last.get("adopte_bool", False))
    badge = "✅ Adopté(e)" if adopte_final else "❌ Rejeté(e) ou en cours"
    badge_color = "#27ae60" if adopte_final else "#555"
    st.markdown(
        f"<p style='color:{badge_color};font-size:1.05em'>"
        f"<b>{badge}</b> · Dernier scrutin le {str(last['date'])[:10]}</p>",
        unsafe_allow_html=True)

    # Explain loi/amendement distinction
    type_votes = law_scruts["type_vote"].value_counts().to_dict()
    vote_types_str = " · ".join(f"{v}× {k}" for k, v in type_votes.items())
    st.caption(
        f"**Comprendre les scrutins** : chaque ligne ci-dessous est un vote nominatif séparé "
        f"(vote sur l'ensemble du texte ou sur un amendement). Ici : {vote_types_str}."
    )

    # Timeline of scrutins
    st.subheader(f"Chronologie des {len(law_scruts)} scrutin(s)")
    disp = law_scruts[["date", "titre_court", "type_vote", "adopte", "pour", "contre", "abstention"]].copy()
    disp["date"] = disp["date"].dt.strftime("%Y-%m-%d")
    disp.columns = ["Date", "Objet", "Type de vote", "Résultat", "Pour ✅", "Contre ❌", "Abst. 🟡"]
    sel = st.dataframe(
        disp, use_container_width=True, hide_index=True,
        on_select="rerun", selection_mode="single-row",
        key=f"loi_scruts_{uid}", height=300,
        column_config={"Objet": st.column_config.TextColumn(width="large")},
    )
    if sel.selection.rows:
        scr = law_scruts.iloc[sel.selection.rows[0]]
        with st.expander(f"🔎 {str(scr['titre_court'])}…", expanded=True):
            _detail_scrutin(scr, votes_groupe, votes_depute, deputes, organes)


def _detail_scrutin(scr, votes_groupe, votes_depute, deputes, organes):
    adopte = bool(scr.get("adopte_bool", False))
    color = "#27ae60" if adopte else "#e74c3c"
    badge = "✅ Adopté" if adopte else "❌ Rejeté"
    st.markdown(f"<b style='color:{color}'>{badge}</b> · {scr.get('type_vote','')}",
                unsafe_allow_html=True)
    st.markdown(f"**{scr['titre']}**")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Votants", _fmt(scr.get("nb_votants")))
    c2.metric("✅ Pour", _fmt(scr.get("pour")))
    c3.metric("❌ Contre", _fmt(scr.get("contre")))
    c4.metric("🟡 Abstention", _fmt(scr.get("abstention")))

    uid = scr["uid"]
    gv = votes_groupe[votes_groupe["scrutin_uid"] == uid].copy()
    if not gv.empty:
        org_map = organes[["uid", "libelle_abrev"]].drop_duplicates("uid").set_index("uid")["libelle_abrev"]
        gv["abrev"] = gv["groupe_ref"].map(org_map).fillna(gv["groupe_ref"])
        gv["order"] = gv["abrev"].map(lambda a: POLITICAL_ORDER.index(a) if a in POLITICAL_ORDER else 99)
        gv = gv.sort_values("order")

        fig = go.Figure()
        for key, cv, label in [("pour", "#27ae60", "Pour ✅"),
                                ("contre", "#e74c3c", "Contre ❌"),
                                ("abstention", "#f39c12", "Abstention 🟡")]:
            fig.add_trace(go.Bar(name=label, x=gv["abrev"], y=gv[key].fillna(0),
                                 marker_color=cv, text=gv[key].fillna(0).astype(int),
                                 textposition="inside"))
        fig.update_layout(barmode="stack", height=240,
                          margin=dict(l=0, r=0, t=10, b=0),
                          legend=dict(orientation="h"))
        st.plotly_chart(fig, use_container_width=True)

    ind = votes_depute[votes_depute["scrutin_uid"] == uid].copy()
    ind = ind.merge(deputes[["id", "prenom", "nom", "groupe_abrev"]],
                    left_on="depute_ref", right_on="id", how="left")
    ind["nom_complet"] = ind["prenom"].fillna("") + " " + ind["nom"].fillna("")

    col_f1, col_f2 = st.columns(2)
    vote_tab = col_f1.radio("Filtre vote", ["Tous", "Pour ✅", "Contre ❌", "Abstention 🟡"],
                            horizontal=True, key=f"vf_{uid}")
    grp_opts = ["Tous"] + [g for g in POLITICAL_ORDER if g in ind["groupe_abrev"].values]
    grp_f = col_f2.selectbox("Groupe", grp_opts, key=f"gf_{uid}")

    vmap = {"Pour ✅": "pour", "Contre ❌": "contre", "Abstention 🟡": "abstention"}
    if vote_tab != "Tous":
        ind = ind[ind["vote"] == vmap[vote_tab]]
    if grp_f != "Tous":
        ind = ind[ind["groupe_abrev"] == grp_f]

    st.caption(f"{len(ind)} député(s)")
    disp2 = ind[["nom_complet", "groupe_abrev", "vote"]].copy()
    disp2.columns = ["Nom", "Groupe", "Vote"]
    sel2 = st.dataframe(disp2, use_container_width=True, hide_index=True,
                        on_select="rerun", selection_mode="single-row",
                        key=f"ind_{uid}", height=300)
    if sel2.selection.rows:
        dep_row = ind.iloc[sel2.selection.rows[0]]
        dep_id = str(dep_row.get("depute_ref", dep_row.get("id", "")))
        name = str(dep_row.get("nom_complet", "")).strip()
        if dep_id and st.button(f"👤 {name} →", key=f"goto_dep_{uid}_{dep_id}"):
            nav("Députés", focus_depute=dep_id)


# ══════════════════════════════════════════════════════════════════════════════
# GROUPES
# ══════════════════════════════════════════════════════════════════════════════

def page_groupes(organes, deputes, votes_groupe, scrutins):
    st.title("🎯 Groupes politiques")

    valid_abrevs = [g for g in POLITICAL_ORDER if g in deputes["groupe_abrev"].values]
    sel_abrev = st.selectbox(
        "Détail d'un groupe",
        valid_abrevs,
        format_func=lambda g: f"{g} — {_GROUP_FULL_NAMES.get(g, g)}",
    )
    if sel_abrev:
        members = deputes[deputes["groupe_abrev"] == sel_abrev].sort_values("nom")
        org_row = organes[organes["libelle_abrev"] == sel_abrev]
        uid_grp = org_row.iloc[0]["uid"] if not org_row.empty else None
        color = gc(sel_abrev)

        # ── Group header ──────────────────────────────────────────────────────
        full_name = _GROUP_FULL_NAMES.get(sel_abrev, sel_abrev)
        president = _GROUP_PRESIDENTS.get(sel_abrev, "—")
        st.markdown(
            f"<div style='border-left:6px solid {color};padding:10px 18px;"
            f"border-radius:0 8px 8px 0;background:#fafafa;margin-bottom:12px'>"
            f"<span style='font-size:1.3em;font-weight:bold;color:{color}'>{sel_abrev}</span> "
            f"<span style='font-size:1.1em;color:#333'>{full_name}</span><br>"
            f"<span style='color:#666;font-size:0.9em'>Président(e) du groupe : "
            f"<b>{president}</b></span>"
            f"</div>",
            unsafe_allow_html=True,
        )

        # ── KPIs ──────────────────────────────────────────────────────────────
        grp_v = votes_groupe[votes_groupe["groupe_ref"] == uid_grp] if uid_grp else pd.DataFrame()
        age_mean = members["age"].mean()
        age_min  = members["age"].min()
        age_max  = members["age"].max()
        n_femmes = (members["prenom"].str.strip().apply(
            lambda p: p in {"Marie", "Anne", "Sophie", "Claire", "Valérie",
                            "Sandrine", "Mathilde", "Isabelle", "Christine"})
        ).sum()  # rough proxy — just shows the field is interesting

        # Amendements = scrutins with "amendement" in title
        if uid_grp:
            scr_votes = votes_groupe[votes_groupe["groupe_ref"] == uid_grp]["scrutin_uid"].unique()
        else:
            scr_votes = []

        kc1, kc2, kc3, kc4, kc5 = st.columns(5)
        kc1.metric("Membres", len(members))
        kc2.metric("Âge moyen", f"{age_mean:.0f} ans" if pd.notna(age_mean) else "—")
        kc3.metric("Âge (min / max)", f"{int(age_min) if pd.notna(age_min) else '—'} / {int(age_max) if pd.notna(age_max) else '—'}")
        if not grp_v.empty:
            total_votes = grp_v["pour"].sum() + grp_v["contre"].sum() + grp_v["abstention"].sum()
            pct_pour = 100 * grp_v["pour"].sum() / total_votes if total_votes > 0 else 0
            kc4.metric("Taux de vote pour", f"{pct_pour:.0f}%")
            kc5.metric("Scrutins participés", f"{grp_v['scrutin_uid'].nunique():,}")
        kc1.caption("17ème législature · depuis juil. 2024")

        st.markdown("")

        c1, c2 = st.columns([1, 1])
        with c1:
            st.markdown("**Membres du groupe**")
            disp = members[["prenom", "nom", "age", "departement", "profession"]].copy()
            disp.columns = ["Prénom", "Nom", "Âge", "Dép.", "Profession"]
            sel2 = st.dataframe(disp, use_container_width=True, hide_index=True,
                               on_select="rerun", selection_mode="single-row",
                               key=f"grp_m_{sel_abrev}", height=320)
            if sel2.selection.rows:
                dep = members.iloc[sel2.selection.rows[0]]
                if st.button(f"👤 Fiche de {dep['prenom']} {dep['nom']} →"):
                    nav("Députés", focus_depute=str(dep["id"]))

            # Top professions
            st.markdown("**Professions les plus représentées**")
            top_prof = members["profession"].value_counts().head(5).reset_index()
            top_prof.columns = ["Profession", "N"]
            st.dataframe(top_prof, use_container_width=True, hide_index=True, height=200)

        with c2:
            if not grp_v.empty:
                st.markdown("**Votes du groupe**")
                tv = {"Pour ✅": int(grp_v["pour"].sum()),
                      "Contre ❌": int(grp_v["contre"].sum()),
                      "Abstention 🟡": int(grp_v["abstention"].sum())}
                fig2 = px.pie(values=list(tv.values()), names=list(tv.keys()),
                              color=list(tv.keys()),
                              color_discrete_map={"Pour ✅": "#27ae60",
                                                  "Contre ❌": "#e74c3c",
                                                  "Abstention 🟡": "#f39c12"},
                              hole=0.45)
                fig2.update_layout(height=260, margin=dict(l=0, r=0, t=10, b=0))
                st.plotly_chart(fig2, use_container_width=True)

                # Cohésion : on which scrutins did this group have unanimous vote?
                st.markdown("**Interprétation**")
                pct_pour_val = 100 * int(grp_v["pour"].sum()) / (int(grp_v["pour"].sum()) + int(grp_v["contre"].sum()) + int(grp_v["abstention"].sum()))
                if pct_pour_val > 55:
                    st.success(f"{sel_abrev} vote majoritairement **pour** ({pct_pour_val:.0f}% des votes exprimés sont des 'pour').")
                elif pct_pour_val < 40:
                    st.error(f"{sel_abrev} vote majoritairement **contre** ({100-pct_pour_val:.0f}% de votes contre).")
                else:
                    st.info(f"{sel_abrev} présente un profil de vote **équilibré** entre pour et contre.")


# ══════════════════════════════════════════════════════════════════════════════
# SIMILARITÉ
# ══════════════════════════════════════════════════════════════════════════════

def _sim_by_theme(scrutins, dossiers, compute_fn) -> pd.DataFrame:
    """
    For each theme, call compute_fn(scr_uids) → similarity float [0,1] or None.
    Returns DataFrame with columns [theme, similarite, n_scrutins].
    """
    if dossiers is None or "theme" not in dossiers.columns:
        return pd.DataFrame()
    rows = []
    scr_linked = scrutins[scrutins["dossier_ref"].str.startswith("DLR", na=False)]
    for theme in sorted(dossiers["theme"].dropna().unique()):
        dos_uids = set(dossiers[dossiers["theme"] == theme]["uid"].astype(str))
        scr_uids = set(scr_linked[scr_linked["dossier_ref"].isin(dos_uids)]["uid"].astype(str))
        if len(scr_uids) < 2:
            continue
        result = compute_fn(scr_uids)
        if result is not None:
            rows.append({"theme": theme, "similarite": result[0], "n_scrutins": result[1]})
    return pd.DataFrame(rows)


def page_similarite(votes_groupe, votes_depute, deputes, organes, scrutins, dossiers):
    st.title("🔗 Similarité de vote")

    tab_grp, tab_dep = st.tabs(["🎯 Entre groupes", "👥 Entre deux députés"])

    with tab_grp:
        _sim_groupes(votes_groupe, organes, scrutins, dossiers)
    with tab_dep:
        _sim_deputes(votes_depute, deputes, scrutins, dossiers)


def _sim_groupes(votes_groupe, organes, scrutins, dossiers):
    org_map = organes[["uid", "libelle_abrev"]].drop_duplicates("uid").set_index("uid")["libelle_abrev"]

    def _build_group_pivot(vg_subset):
        vg = vg_subset.copy()
        vg["position"] = "abstention"
        vg.loc[vg["pour"] > vg["contre"], "position"] = "pour"
        vg.loc[vg["contre"] > vg["pour"], "position"] = "contre"
        vg["abrev"] = vg["groupe_ref"].map(org_map).fillna("")
        vg = vg[vg["abrev"] != ""]
        vg = vg.drop_duplicates(subset=["scrutin_uid", "abrev"], keep="first")
        return vg.pivot_table(index="scrutin_uid", columns="abrev",
                              values="position", aggfunc="first")

    def _pair_sim(pivot, g1, g2):
        c1 = pivot[g1] if isinstance(pivot[g1], pd.Series) else pivot[g1].iloc[:, 0]
        c2 = pivot[g2] if isinstance(pivot[g2], pd.Series) else pivot[g2].iloc[:, 0]
        both = pd.concat([c1, c2], axis=1, keys=["a", "b"]).dropna()
        return float((both["a"] == both["b"]).mean()) if len(both) > 0 else float("nan")

    # ── Theme filter for the matrix ───────────────────────────────────────────
    matrix_vg = votes_groupe.copy()
    matrix_label = "tous scrutins"

    if dossiers is not None and "theme" in dossiers.columns:
        themes_opts = ["Tous les thèmes"] + sorted(dossiers["theme"].dropna().unique())
        theme_matrix = st.selectbox("🏷 Filtrer la matrice par thème", themes_opts,
                                    key="sim_matrix_theme")
        if theme_matrix != "Tous les thèmes":
            matrix_label = theme_matrix
            dos_uids = set(dossiers[dossiers["theme"] == theme_matrix]["uid"].astype(str))
            scr_uids = set(
                scrutins[scrutins["dossier_ref"].isin(dos_uids)]["uid"].astype(str))
            matrix_vg = matrix_vg[matrix_vg["scrutin_uid"].isin(scr_uids)]
            if matrix_vg.empty:
                st.warning("Aucun scrutin lié à ce thème.")
                return

    pivot_matrix = _build_group_pivot(matrix_vg)
    present = [g for g in POLITICAL_ORDER if g in pivot_matrix.columns]
    others  = [g for g in pivot_matrix.columns if g not in POLITICAL_ORDER]
    groups  = present + others
    pivot_matrix = pivot_matrix[groups]

    # Full names for hover
    full_names = [_GROUP_FULL_NAMES.get(g, g) for g in groups]

    # ── Similarity matrix ─────────────────────────────────────────────────────
    st.subheader(f"Matrice de similarité — {matrix_label}")
    st.caption(
        "Fraction des scrutins où deux groupes ont voté dans le même sens "
        "(groupe = position majoritaire pour/contre).")

    sim_vals = [[_pair_sim(pivot_matrix, g1, g2) for g2 in groups] for g1 in groups]
    sim_df = pd.DataFrame(sim_vals, index=groups, columns=groups)

    hover_text = [
        [
            (f"<b>{full_names[i]}</b> vs <b>{full_names[j]}</b><br>"
             f"Similarité : {sim_df.iloc[i, j]:.1%}")
            if not pd.isna(sim_df.iloc[i, j]) else ""
            for j in range(len(groups))
        ]
        for i in range(len(groups))
    ]

    fig = go.Figure(go.Heatmap(
        z=sim_df.values,
        x=[f"{g}<br><span style='font-size:9px'>{_GROUP_FULL_NAMES.get(g,'')}</span>"
           for g in groups],
        y=[f"{g}" for g in groups],
        colorscale="RdYlGn", zmin=0, zmax=1,
        text=[[f"{v:.0%}" if not pd.isna(v) else "" for v in row] for row in sim_df.values],
        texttemplate="%{text}", textfont={"size": 11},
        customdata=hover_text,
        hovertemplate="%{customdata}<extra></extra>",
    ))
    fig.update_layout(height=480, margin=dict(l=0, r=0, t=10, b=40))
    st.plotly_chart(fig, use_container_width=True)

    # ── Select 2 groups → similarity by theme ─────────────────────────────────
    if dossiers is not None and "theme" in dossiers.columns:
        st.divider()
        st.subheader("Comparer deux groupes par thème")
        ca, cb = st.columns(2)
        g_a = ca.selectbox("Groupe A", groups, key="sim_grp_a",
                           format_func=lambda g: f"{g} — {_GROUP_FULL_NAMES.get(g, g)}")
        g_b = cb.selectbox("Groupe B", [g for g in groups if g != g_a],
                           key="sim_grp_b",
                           format_func=lambda g: f"{g} — {_GROUP_FULL_NAMES.get(g, g)}")
        if g_a and g_b:
            pivot_all = _build_group_pivot(votes_groupe)
            overall = _pair_sim(pivot_all, g_a, g_b) if g_a in pivot_all.columns and g_b in pivot_all.columns else float("nan")
            ca.metric("Similarité globale A↔B", f"{overall:.1%}" if not pd.isna(overall) else "—")

            def compute_grp_pair(scr_uids):
                sub_vg = votes_groupe[votes_groupe["scrutin_uid"].isin(scr_uids)]
                if sub_vg.empty:
                    return None
                p = _build_group_pivot(sub_vg)
                if g_a not in p.columns or g_b not in p.columns:
                    return None
                both = pd.concat([p[g_a], p[g_b]], axis=1, keys=["a", "b"]).dropna()
                if len(both) < 2:
                    return None
                return float((both["a"] == both["b"]).mean()), len(both)

            theme_sim = _sim_by_theme(scrutins, dossiers, compute_grp_pair)
            if not theme_sim.empty:
                theme_sim = theme_sim.sort_values("similarite", ascending=True)
                fig2 = px.bar(
                    theme_sim, x="similarite", y="theme", orientation="h",
                    color="similarite", color_continuous_scale="RdYlGn",
                    range_color=[0, 1], range_x=[0, 1],
                    text=theme_sim["similarite"].map("{:.0%}".format),
                    labels={"similarite": "Similarité", "theme": "", "n_scrutins": "Scrutins"},
                    hover_data=["n_scrutins"],
                )
                if not pd.isna(overall):
                    fig2.add_vline(x=overall, line_dash="dash", line_color="#666",
                                   annotation_text="global", annotation_position="top right")
                fig2.update_traces(textposition="outside")
                fig2.update_coloraxes(showscale=False)
                fig2.update_layout(height=max(300, len(theme_sim) * 32 + 60),
                                   margin=dict(l=0, r=80, t=10, b=0))
                st.plotly_chart(fig2, use_container_width=True)


def _sim_deputes(votes_depute, deputes, scrutins, dossiers):
    pivot_all = make_vote_pivot(votes_depute)

    dep_options = sorted(deputes["nom_complet"].tolist())
    ca, cb = st.columns(2)

    dep_a_name = ca.selectbox("Député A", dep_options, key="sim_dep_a")
    dep_b_name = cb.selectbox("Député B", dep_options, key="sim_dep_b")

    dep_a_row = deputes[deputes["nom_complet"] == dep_a_name].iloc[0]
    dep_b_row = deputes[deputes["nom_complet"] == dep_b_name].iloc[0]
    dep_a_id = str(dep_a_row["id"])
    dep_b_id = str(dep_b_row["id"])
    ca.caption(f"Groupe : **{dep_a_row.get('groupe_abrev','—')}**")
    cb.caption(f"Groupe : **{dep_b_row.get('groupe_abrev','—')}**")

    if dep_a_id == dep_b_id:
        st.info("Sélectionnez deux députés différents.")
        return

    if dep_a_id not in pivot_all.columns or dep_b_id not in pivot_all.columns:
        st.warning("Votes nominatifs manquants pour l'un des deux députés.")
        return

    with st.spinner("Calcul…"):
        both_all = pd.concat([pivot_all[dep_a_id], pivot_all[dep_b_id]],
                              axis=1, keys=["a", "b"]).dropna()
        overall = float((both_all["a"] == both_all["b"]).mean()) if len(both_all) > 0 else float("nan")

    # ── Global score ──────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Similarité globale")
    col1, col2, col3 = st.columns(3)
    col1.metric("Similarité A ↔ B", f"{overall:.1%}" if not pd.isna(overall) else "—")
    col2.metric("Votes communs", f"{len(both_all):,}")
    col3.metric("Votes totaux analysés", f"{len(pivot_all):,}")

    # ── Similarity by theme ───────────────────────────────────────────────────
    if dossiers is not None and "theme" in dossiers.columns:
        st.divider()
        st.subheader("Similarité par thème")

        def compute_dep_pair(scr_uids):
            sub = pivot_all.loc[pivot_all.index.isin(scr_uids)]
            if dep_a_id not in sub.columns or dep_b_id not in sub.columns:
                return None
            both = pd.concat([sub[dep_a_id], sub[dep_b_id]],
                             axis=1, keys=["a", "b"]).dropna()
            if len(both) < 2:
                return None
            return float((both["a"] == both["b"]).mean()), len(both)

        theme_sim = _sim_by_theme(scrutins, dossiers, compute_dep_pair)
        if not theme_sim.empty:
            theme_sim = theme_sim.sort_values("similarite", ascending=True)
            fig = px.bar(
                theme_sim, x="similarite", y="theme", orientation="h",
                color="similarite", color_continuous_scale="RdYlGn",
                range_color=[0, 1], range_x=[0, 1],
                text=theme_sim["similarite"].map("{:.0%}".format),
                labels={"similarite": "Similarité", "theme": "", "n_scrutins": "Scrutins"},
                hover_data=["n_scrutins"],
            )
            fig.add_vline(x=overall, line_dash="dash", line_color="#666",
                          annotation_text="global", annotation_position="top right")
            fig.update_traces(textposition="outside")
            fig.update_coloraxes(showscale=False)
            fig.update_layout(height=max(300, len(theme_sim) * 32 + 60),
                              margin=dict(l=0, r=80, t=10, b=0))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Pas assez de scrutins liés à des dossiers classifiés pour calculer la similarité par thème.")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    if "page" not in st.session_state:
        st.session_state["page"] = "Accueil"

    try:
        deputes      = load_deputes()
        organes      = load_organes()
        scrutins     = load_scrutins()
        votes_groupe = load_votes_groupe()
        votes_depute = load_votes_depute()
        dossiers     = load_dossiers_themes()
    except FileNotFoundError as e:
        st.error(f"**Données manquantes** — lancez `python main.py`.\n\n`{e}`")
        st.stop()

    PAGES = {"Accueil": "🏠", "Députés": "👥", "Lois": "📋",
             "Groupes": "🎯", "Similarité": "🔗"}

    with st.sidebar:
        st.markdown("## 🏛️ AN Data")
        current = st.session_state["page"]
        for name, icon in PAGES.items():
            if st.button(f"{icon} {name}", use_container_width=True,
                         type="primary" if name == current else "secondary",
                         key=f"nav_{name}"):
                for k in ["focus_depute", "focus_loi", "focus_scrutin"]:
                    st.session_state.pop(k, None)
                st.session_state["page"] = name
                st.rerun()
        st.divider()
        st.caption("17ème législature")

    page = st.session_state["page"]
    if page == "Accueil":
        page_accueil(deputes, scrutins, organes)
    elif page == "Députés":
        page_deputes(deputes, votes_depute, scrutins)
    elif page == "Lois":
        page_lois(dossiers, scrutins, votes_groupe, votes_depute, deputes, organes)
    elif page == "Groupes":
        page_groupes(organes, deputes, votes_groupe, scrutins)
    elif page == "Similarité":
        page_similarite(votes_groupe, votes_depute, deputes, organes, scrutins, dossiers)


if __name__ == "__main__":
    main()
