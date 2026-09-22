# Tableau de bord YJC (Yaakaar Jeunesse Citoyennete) - Consortium Jeunesse Senegal
# Lit en direct le Google Sheet "Dashboard YJC-Deploye" : feuille Global + 5 feuilles regionales
# + feuille "Fiche des inicateurs" (definitions). Lignes masquees exclues par defaut.

import re
import unicodedata

SHEETS = ["Global", "Tambacounda", "Dakar", "Kedougou", "Sedhiou", "Matam"]
REGIONS = SHEETS[1:]
REGION_LABELS = {"Global": "Global (projet)", "Tambacounda": "Tambacounda", "Dakar": "Dakar",
                 "Kedougou": "Kédougou", "Sedhiou": "Sédhiou", "Matam": "Matam"}


def norm(s):
    s = str(s or "").replace("\u2019", "'").replace("\u202f", " ").replace("\xa0", " ")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s.rstrip(" .:")


def num(v):
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _row_label(row, col):
    if col < len(row):
        v = row[col]["v"]
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _cell(row, col):
    return row[col] if col < len(row) else {"v": None, "pct": False, "align": None}


def detect_layout(grid):
    ind_col = None
    for r in range(min(5, len(grid))):
        for c, cell in enumerate(grid[r]):
            if isinstance(cell["v"], str) and norm(cell["v"]) == "indicateurs":
                ind_col, hdr_row = c, r
                break
        if ind_col is not None:
            break
    if ind_col is None:
        raise ValueError("Colonne 'Indicateurs' introuvable dans les 5 premières lignes")
    years_row = grid[hdr_row] if hdr_row < len(grid) else []
    q_row = grid[hdr_row + 1] if hdr_row + 1 < len(grid) else []
    year_starts = []
    for c, cell in enumerate(years_row):
        m = re.search(r"(20\d\d)", str(cell["v"] or ""))
        if m and c > ind_col:
            year_starts.append((c, int(m.group(1))))
    def year_of(col):
        y = None
        for c, yy in year_starts:
            if c <= col:
                y = yy
        return y
    quarters, annual = [], []
    for c, cell in enumerate(q_row):
        lab = str(cell["v"] or "").strip()
        if re.fullmatch(r"T\d+", lab):
            quarters.append({"q": lab, "n": int(lab[1:]), "year": year_of(c), "col": c})
        elif norm(lab).startswith("tot"):
            m = re.search(r"(20\d\d)", lab)
            annual.append({"year": int(m.group(1)) if m else year_of(c), "col": c})
    quarters.sort(key=lambda x: x["n"])
    return {"ind": ind_col, "cible": ind_col + 1, "att": ind_col + 2, "obs": ind_col + 3,
            "start": hdr_row + 3, "quarters": quarters, "annual": annual}


def classify(label, align):
    n = norm(label)
    if align == "CENTER" or n.startswith("appel a projet"):
        return "group"
    if align == "RIGHT" or n.startswith("dont") or n in {"pourcentage", "tambali", "dolele", "yaataal"}:
        return "sub"
    return "main"


def is_pct_label(label):
    n = norm(label)
    return n.startswith(("pourcentage", "%", "proportion"))


def parse_sheet(sheet, grid, hidden_rows):
    lay = detect_layout(grid)
    recs, main, group = [], None, None
    empty_run, main_count = 0, {}
    for r in range(lay["start"], len(grid)):
        row = grid[r]
        label = _row_label(row, lay["ind"])
        if not label:
            empty_run += 1
            if empty_run >= 15:
                break
            continue
        empty_run = 0
        ci, ca = _cell(row, lay["cible"]), _cell(row, lay["att"])
        kind = classify(label, _cell(row, lay["ind"])["align"])
        hidden = r in hidden_rows
        if kind == "main" or main is None:
            main_count[norm(label)] = main_count.get(norm(label), 0) + 1
            main = {"label": label, "hidden": hidden, "occ": main_count[norm(label)]}
            group, level, grp_label = None, 0, ""
        elif kind == "group":
            group = {"label": label}
            level, grp_label = 1, label
        else:
            level = 2 if group else 1
            grp_label = group["label"] if group else ""
        pct = bool(ci["pct"] or ca["pct"]) or (level == 0 and is_pct_label(label)) or norm(label) == "pourcentage"
        obs = _cell(row, lay["obs"])["v"]
        rec = {
            "sheet": sheet, "row": r + 1, "level": level, "kind": kind,
            "main": main["label"], "occ": main["occ"], "group": grp_label, "label": label,
            "cible": num(ci["v"]), "atteint": num(ca["v"]),
            "obs": obs.strip() if isinstance(obs, str) and obs.strip() else "",
            "pct": pct, "money": norm(main["label"]).startswith("montant"),
            "hidden": hidden or main["hidden"],
            "quarters": [], "annual": [],
        }
        for q in lay["quarters"]:
            rec["quarters"].append({"q": q["q"], "n": q["n"], "year": q["year"],
                                    "cible": num(_cell(row, q["col"])["v"]),
                                    "atteint": num(_cell(row, q["col"] + 1)["v"])})
        for a in lay["annual"]:
            rec["annual"].append({"year": a["year"], "cible": num(_cell(row, a["col"])["v"]),
                                  "atteint": num(_cell(row, a["col"] + 1)["v"])})
        recs.append(rec)
    return recs


def _assign_keys(recs):
    seen = {}
    for rec in recs:
        own = rec["canon"] if rec["level"] == 0 else rec["label"]
        base = f"{norm(rec['canon'])}#{rec['occ']}||{norm(rec['group'])}||{norm(own)}"
        k = (rec["sheet"], base)
        seen[k] = seen.get(k, 0) + 1
        rec["key"] = f"{base}||{seen[k]}"
        rec["main_key"] = f"{norm(rec['canon'])}#{rec['occ']}"
        c, a = rec["cible"], rec["atteint"]
        rec["taux"] = (a / c) if (c not in (None, 0) and a is not None) else None


def parse_all(grids, hidden):
    from difflib import SequenceMatcher
    out = []
    for s in SHEETS:
        if s in grids:
            out.extend(parse_sheet(s, grids[s], hidden.get(s, set())))
    ref = []
    for rec in out:
        if rec["sheet"] == "Global" and rec["level"] == 0 and rec["main"] not in ref:
            ref.append(rec["main"])
    ref_norm = {norm(x): x for x in ref}
    cache = {}
    for rec in out:
        m = rec["main"]
        if norm(m) in ref_norm or rec["sheet"] == "Global":
            rec["canon"] = m
            continue
        if m not in cache:
            best, score = m, 0.0
            for cand in ref:
                sc = SequenceMatcher(None, norm(m), norm(cand)).ratio()
                if sc > score:
                    best, score = cand, sc
            cache[m] = best if score >= 0.8 else m
        rec["canon"] = cache[m]
    _assign_keys(out)
    order = {}
    for rec in out:
        if rec["level"] == 0 and rec["main_key"] not in order:
            order[rec["main_key"]] = len(order) + 1
    for rec in out:
        rec["num"] = order.get(rec["main_key"])
    return out


def api_to_grids(payload):
    grids, hidden = {}, {}
    for sh in payload.get("sheets", []):
        title = sh["properties"]["title"]
        data = (sh.get("data") or [{}])[0]
        r0, c0 = data.get("startRow", 0), data.get("startColumn", 0)
        grid = [[] for _ in range(r0)]
        for rd in data.get("rowData", []):
            row = [{"v": None, "pct": False, "align": None} for _ in range(c0)]
            for val in rd.get("values", []) or []:
                ev = val.get("effectiveValue") or {}
                if "numberValue" in ev:
                    v = ev["numberValue"]
                elif "stringValue" in ev:
                    v = ev["stringValue"]
                elif "boolValue" in ev:
                    v = ev["boolValue"]
                else:
                    v = None
                fmt = val.get("effectiveFormat") or {}
                row.append({"v": v,
                            "pct": (fmt.get("numberFormat") or {}).get("type") == "PERCENT",
                            "align": fmt.get("horizontalAlignment")})
            grid.append(row)
        hid = set()
        for i, md in enumerate(data.get("rowMetadata", []) or []):
            if md.get("hiddenByUser"):
                hid.add(r0 + i)
        grids[title], hidden[title] = grid, hid
    return grids, hidden


def xlsx_to_grids(path, extra_sheets=()):
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True)
    grids, hidden = {}, {}
    for s in list(SHEETS) + list(extra_sheets):
        ws = wb[s]
        grid = []
        for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 300)):
            grid.append([{"v": c.value if not (isinstance(c.value, str) and c.value.startswith("#")) else None,
                          "pct": "%" in (c.number_format or ""),
                          "align": (c.alignment.horizontal or "").upper() or None} for c in row])
        grids[s] = grid
        hidden[s] = {r - 1 for r, d in ws.row_dimensions.items() if d.hidden}
    return grids, hidden


DEF_SHEET = "Fiche des inicateurs"


def parse_definitions(grid):
    out = {}
    for row in grid[1:]:
        lab = row[0]["v"] if len(row) > 0 else None
        if not isinstance(lab, str) or not lab.strip():
            continue
        get = lambda i: (row[i]["v"].strip() if i < len(row) and isinstance(row[i]["v"], str) and row[i]["v"].strip() else "")
        out[norm(lab)] = {
            "label": lab.strip(), "definition": get(1), "source": get(2),
            "outil": get(3), "frequence": get(4),
        }
    return out


def match_definition(label, defs):
    from difflib import SequenceMatcher
    n = norm(label)
    if n in defs:
        return defs[n]
    best, score = None, 0.0
    for k, v in defs.items():
        sc = SequenceMatcher(None, n, k).ratio()
        if sc > score:
            best, score = v, sc
    return best if score >= 0.82 else None


REGION_COORDS = {
    "Tambacounda": (13.7707, -13.6673),
    "Dakar": (14.7167, -17.4677),
    "Kedougou": (12.5556, -12.1746),
    "Sedhiou": (12.7081, -15.5569),
    "Matam": (15.6559, -13.2548),
}


GEO_B64 = "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"


def load_geo():
    import base64, json, zlib
    return json.loads(zlib.decompress(base64.b64decode(GEO_B64)).decode())

# ============================================================
#  INTERFACE
# ============================================================
import os
import html
from datetime import datetime, timezone, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

SPREADSHEET_ID = "1i-CBHtOvvTIZPpaEMelbumbV7il-ha4utJMAmq_FvvA"
C_OK, C_MID, C_LOW, C_NONE = "#1F7A5C", "#C98A1B", "#B23A48", "#8A94A6"
C_BLUE, C_TARGET = "#2F5D8A", "#9FB3C8"
DAKAR_TZ = timezone(timedelta(hours=0))

st.set_page_config(page_title="Tableau de bord YJC", page_icon="📊", layout="wide",
                   initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;500;600;700&display=swap');
html, body, [class*="css"], .stMarkdown, .stDataFrame, button, input, select, textarea {
  font-family: 'Public Sans', 'Segoe UI', Roboto, sans-serif !important;
}
.block-container { padding-top: 2.2rem; max-width: 1400px; }
.yjc-head h1 { font-size: 1.9rem; font-weight: 700; margin: 0 0 .2rem 0; letter-spacing: -.01em; }
.yjc-head p { margin: 0; opacity: .75; font-size: .98rem; }
.yjc-stats { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 14px; margin: 1.2rem 0 1.4rem; }
.yjc-stat { border: 1px solid rgba(127,127,127,.22); border-radius: 10px; padding: 14px 16px; }
.yjc-stat .v { font-size: 2rem; font-weight: 700; line-height: 1.1; font-variant-numeric: tabular-nums; }
.yjc-stat .l { font-size: .88rem; opacity: .75; margin-top: 2px; }
.yjc-grid { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 14px; }
.yjc-card { border: 1px solid rgba(127,127,127,.22); border-left: 5px solid var(--st); border-radius: 0 10px 10px 0;
            padding: 12px 14px 12px 14px; background: rgba(127,127,127,.04); display: flex; flex-direction: column; gap: 8px; }
.yjc-card .top { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; font-size: .78rem; }
.yjc-card .num { opacity: .6; font-variant-numeric: tabular-nums; }
.yjc-card .badge { color: var(--st); font-weight: 600; white-space: nowrap; }
.yjc-card .lab { font-size: .92rem; line-height: 1.35; min-height: 3.7em;
                 display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.yjc-card .vals { display: flex; justify-content: space-between; align-items: baseline; font-variant-numeric: tabular-nums; }
.yjc-card .att { font-size: 1.45rem; font-weight: 700; }
.yjc-card .cib { font-size: .85rem; opacity: .7; }
.yjc-card .pct { font-size: 1.05rem; font-weight: 700; color: var(--st); }
.yjc-bar { position: relative; height: 8px; border-radius: 4px; background: rgba(127,127,127,.18); overflow: visible; }
.yjc-bar .fill { height: 100%; border-radius: 4px; background: var(--st); }
.yjc-bar .tick { position: absolute; top: -3px; width: 2px; height: 14px; background: rgba(127,127,127,.7); }
.yjc-note { font-size: .85rem; opacity: .7; margin: .3rem 0 .8rem; }
.yjc-legend { display: flex; gap: 18px; flex-wrap: wrap; font-size: .85rem; margin: .2rem 0 1rem; }
.yjc-legend span::before { content: ""; display: inline-block; width: 10px; height: 10px; border-radius: 2px;
                           background: var(--c); margin-right: 6px; vertical-align: -1px; }
@media (max-width: 1100px) { .yjc-grid { grid-template-columns: repeat(2, minmax(0,1fr)); } }
@media (max-width: 700px) { .yjc-grid, .yjc-stats { grid-template-columns: minmax(0,1fr); } }
</style>
""", unsafe_allow_html=True)


# ---------- chargement ----------
FIELDS = ("sheets(properties(title),data(startRow,startColumn,rowMetadata(hiddenByUser),"
          "rowData(values(effectiveValue,effectiveFormat(horizontalAlignment,numberFormat(type))))))")


@st.cache_data(ttl=900, show_spinner="Lecture du Google Sheet...")
def load_records():
    local = os.environ.get("YJC_LOCAL_XLSX")
    if local:
        grids, hidden = xlsx_to_grids(local, extra_sheets=(DEF_SHEET,))
        defs = parse_definitions(grids.get(DEF_SHEET, []))
    else:
        from google.oauth2.service_account import Credentials
        from google.auth.transport.requests import AuthorizedSession
        creds = Credentials.from_service_account_info(
            dict(st.secrets["google_credentials"]),
            scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
        session = AuthorizedSession(creds)
        resp = session.get(
            f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}",
            params={"includeGridData": "true", "fields": FIELDS,
                    "ranges": [f"'{s}'!A1:BD400" for s in SHEETS] + [f"'{DEF_SHEET}'!A1:E900"]},
            timeout=60)
        if resp.status_code == 403:
            raise PermissionError("Accès refusé au Google Sheet. Partage-le en lecture avec l'adresse "
                                  "client_email du compte de service.")
        resp.raise_for_status()
        grids, hidden = api_to_grids(resp.json())
        defs = parse_definitions(grids.get(DEF_SHEET, []))
    recs = parse_all(grids, hidden)
    return recs, defs, datetime.now(timezone.utc).isoformat()


# ---------- formats ----------
def fmt_n(x, dec=0):
    if x is None:
        return "n.d."
    if abs(x - round(x)) < 1e-9:
        s = f"{int(round(x)):,}"
    else:
        s = f"{x:,.{dec or 1}f}"
    return s.replace(",", "\u202f").replace(".", ",")


def fmt_v(rec, x):
    if x is None:
        return "n.d."
    if rec["pct"]:
        return f"{fmt_n(x * 100, 1 if abs(x * 100 - round(x * 100)) > 0.05 else 0)}\u202f%"
    if rec["money"]:
        return f"{fmt_n(x / 1e6, 1)}\u202fM FCFA" if abs(x) >= 1e6 else f"{fmt_n(x)}\u202fFCFA"
    return fmt_n(x, 1)


def fmt_pct(t):
    if t is None:
        return "n.d."
    p = t * 100
    if p >= 100 or abs(p - round(p)) < 0.05:
        return f"{fmt_n(float(round(p)))}\u202f%"
    return f"{fmt_n(p, 1)}\u202f%"


def status(t):
    if t is None:
        return "Sans cible", C_NONE
    if t >= 1:
        return "Cible atteinte", C_OK
    if t >= 0.5:
        return "En progression", C_MID
    return "À renforcer", C_LOW


def short(s, n=90):
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def plot(fig, h=None):
    fig.update_layout(margin=dict(l=10, r=10, t=40, b=10), font=dict(family="Public Sans, sans-serif", size=13),
                      legend=dict(orientation="h", y=1.08, x=0), hoverlabel=dict(font_family="Public Sans"))
    if h:
        fig.update_layout(height=h)
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False})


# ---------- données ----------
try:
    RECS, DEFS, LOADED_AT = load_records()
except Exception as e:
    st.error(f"Impossible de lire le Google Sheet : {e}")
    st.info("Vérifie les secrets Streamlit (bloc [google_credentials]) et le partage du Sheet avec le compte de service.")
    st.stop()

with st.sidebar:
    st.markdown("### Paramètres")
    _scope_lab = st.selectbox("Périmètre", [REGION_LABELS[s] for s in SHEETS], key="scope",
                              help="Global regroupe toutes les régions et les activités nationales.")
    scope = next(s for s in SHEETS if REGION_LABELS[s] == _scope_lab)
    show_hidden = st.toggle("Inclure les lignes masquées", value=False,
                            help="Par défaut, les lignes masquées dans le Google Sheet sont exclues.")
    st.divider()
    if st.button("Actualiser les données", width="stretch"):
        st.cache_data.clear()
        st.rerun()
    loaded = datetime.fromisoformat(LOADED_AT).astimezone(DAKAR_TZ)
    st.caption(f"Données lues le {loaded:%d/%m/%Y à %H:%M} (heure de Dakar). "
               "Relecture automatique toutes les 15 minutes.")
    st.divider()
    st.markdown(f'<div class="yjc-legend" style="flex-direction:column;gap:6px">'
                f'<span style="--c:{C_OK}">Cible atteinte (100 % et plus)</span>'
                f'<span style="--c:{C_MID}">En progression (50 à 99 %)</span>'
                f'<span style="--c:{C_LOW}">À renforcer (moins de 50 %)</span>'
                f'<span style="--c:{C_NONE}">Sans cible définie</span></div>', unsafe_allow_html=True)

VIS = [r for r in RECS if show_hidden or not r["hidden"]]
by_sheet = {s: [r for r in VIS if r["sheet"] == s] for s in SHEETS}
mains = [r for r in by_sheet[scope] if r["level"] == 0]
ref_mains = {r["main_key"]: r for r in RECS if r["level"] == 0 and r["sheet"] == "Global"}


def main_label(mk):
    r = ref_mains.get(mk) or next((x for x in RECS if x["main_key"] == mk and x["level"] == 0), None)
    return f"{r['num']}. {short(r['label'], 110)}" if r else mk


def pick_box(label, keys, fmt, key):
    labels, seen = {}, {}
    for k in keys:
        l = fmt(k)
        seen[l] = seen.get(l, 0) + 1
        if seen[l] > 1:
            l = f"{l} ({seen[l]})"
        labels[l] = k
    if not labels:
        return None
    chosen = st.selectbox(label, list(labels), key=key)
    return labels[chosen]


st.markdown(f"""<div class="yjc-head"><h1>Yaakaar Jeunesse Citoyenneté</h1>
<p>Suivi des indicateurs du projet, périmètre : <b>{REGION_LABELS[scope]}</b></p></div>""",
            unsafe_allow_html=True)

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Vue d'ensemble", "Comparaison régionale", "Carte", "Évolution trimestrielle",
                                              "Fiche indicateur", "Données"])

# ============ 1. VUE D'ENSEMBLE ============
with tab1:
    with_target = [r for r in mains if r["taux"] is not None]
    n_ok = sum(r["taux"] >= 1 for r in with_target)
    n_mid = sum(0.5 <= r["taux"] < 1 for r in with_target)
    n_low = sum(r["taux"] < 0.5 for r in with_target)
    st.markdown(f"""<div class="yjc-stats">
      <div class="yjc-stat"><div class="v">{len(mains)}</div><div class="l">indicateurs suivis</div></div>
      <div class="yjc-stat"><div class="v" style="color:{C_OK}">{n_ok}</div><div class="l">cibles atteintes ou dépassées</div></div>
      <div class="yjc-stat"><div class="v" style="color:{C_MID}">{n_mid}</div><div class="l">en progression (50 à 99 %)</div></div>
      <div class="yjc-stat"><div class="v" style="color:{C_LOW}">{n_low}</div><div class="l">à renforcer (moins de 50 %)</div></div>
    </div>""", unsafe_allow_html=True)

    c1, c2, c3 = st.columns([2, 2, 1])
    q = c1.text_input("Rechercher un indicateur", placeholder="débats, cohorte, centres, Yaakaar...")
    stat_f = c2.multiselect("Statut", ["Cible atteinte", "En progression", "À renforcer", "Sans cible"],
                            placeholder="Tous les statuts")
    sort_by = c3.selectbox("Trier par", ["Ordre du Sheet", "Taux croissant", "Taux décroissant"])

    shown = [r for r in mains if (not q or norm(q) in norm(r["label"]))
             and (not stat_f or status(r["taux"])[0] in stat_f)]
    if sort_by != "Ordre du Sheet":
        shown.sort(key=lambda r: (r["taux"] is None, r["taux"] or 0), reverse=(sort_by == "Taux décroissant"))
        if sort_by == "Taux décroissant":
            shown.sort(key=lambda r: r["taux"] is None)

    if not shown:
        st.info("Aucun indicateur ne correspond à ces filtres. Modifie la recherche ou le statut.")
    cards = []
    for r in shown:
        lab, col = status(r["taux"])
        t = r["taux"] or 0
        scale = max(1.0, min(t, 2.0))
        fill = min(t, scale) / scale * 100
        tick = 100 / scale
        cards.append(f"""<div class="yjc-card" style="--st:{col}">
          <div class="top"><span class="num">Indicateur {r['num']}</span><span class="badge">{lab}</span></div>
          <div class="lab" title="{html.escape(r['label'])}">{html.escape(r['label'])}</div>
          <div class="vals"><span><span class="att">{fmt_v(r, r['atteint'])}</span>
            <span class="cib"> / {fmt_v(r, r['cible'])}</span></span><span class="pct">{fmt_pct(r['taux'])}</span></div>
          <div class="yjc-bar"><div class="fill" style="width:{fill:.1f}%"></div>
            <div class="tick" style="left:calc({tick:.1f}% - 1px)"></div></div>
        </div>""")
    st.markdown(f'<div class="yjc-grid">{"".join(cards)}</div>', unsafe_allow_html=True)
    st.markdown('<p class="yjc-note">Le trait vertical sur chaque barre marque la cible. '
                'Au-delà de 100 %, la barre est remise à l\'échelle pour montrer le dépassement.</p>',
                unsafe_allow_html=True)

    st.markdown("#### Désagrégations")
    subs = [r for r in by_sheet[scope] if r["level"] > 0]
    opts = ["Tous les indicateurs"] + [m["main_key"] for m in mains if any(s["main_key"] == m["main_key"] for s in subs)]
    pick = pick_box("Indicateur", opts, lambda k: k if k == "Tous les indicateurs" else main_label(k), "desag_pick")
    rows = []
    for r in by_sheet[scope]:
        if pick != "Tous les indicateurs" and r["main_key"] != pick:
            continue
        if pick == "Tous les indicateurs" and r["level"] == 0 and not any(s["main_key"] == r["main_key"] for s in subs):
            continue
        rows.append({"N°": r["num"],
                     "Niveau": "Indicateur" if r["level"] == 0 else ("Sous-groupe" if r["kind"] == "group" else "Désagrégation"),
                     "Libellé": ("" if r["level"] == 0 else ("    " if r["level"] == 1 else "        ")) + r["label"],
                     "Cible": fmt_v(r, r["cible"]), "Atteint": fmt_v(r, r["atteint"]),
                     "Taux": r["taux"] * 100 if r["taux"] is not None else None,
                     "Statut": status(r["taux"])[0]})
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch",
                     height=min(38 * len(rows) + 40, 620),
                     column_config={"Taux": st.column_config.ProgressColumn("Taux", format="%.0f %%",
                                                                            min_value=0, max_value=100),
                                    "Libellé": st.column_config.TextColumn(width="large")})
    else:
        st.info("Cet indicateur n'a pas de désagrégation.")

# ============ 2. COMPARAISON RÉGIONALE ============
with tab2:
    st.markdown("Taux de réalisation de chaque indicateur par région (valeur atteinte rapportée à la cible régionale).")
    reg_mains = []
    for mk, gm in ref_mains.items():
        if not show_hidden and gm["hidden"]:
            continue
        if any(r["main_key"] == mk and r["level"] == 0 for s in REGIONS for r in by_sheet[s]):
            reg_mains.append(mk)
    if not reg_mains:
        st.info("Aucun indicateur n'est suivi au niveau régional.")
    else:
        idx = {(r["sheet"], r["key"]): r for r in VIS}
        z, txt, ylab, hm_keys = [], [], [], []
        for mk in reg_mains:
            gm = ref_mains[mk]
            zr, tr = [], []
            for s in REGIONS:
                r = idx.get((s, gm["key"]))
                t = r["taux"] if r else None
                zr.append(None if t is None else (2 if t >= 1 else (1 if t >= 0.5 else 0)))
                tr.append("" if t is None else fmt_pct(t))
            if all(v is None for v in zr):
                continue
            ylab.append(f"{gm['num']}. {short(gm['label'], 62)}")
            z.append(zr)
            txt.append(tr)
            hm_keys.append(mk)
        no_target = [ref_mains[mk] for mk in reg_mains if mk not in hm_keys]
        fig = go.Figure(go.Heatmap(
            z=z, x=[REGION_LABELS[s] for s in REGIONS], y=ylab, text=txt, texttemplate="%{text}",
            zmin=0, zmax=2, xgap=3, ygap=3, showscale=False,
            colorscale=[[0, C_LOW], [0.3333, C_LOW], [0.3334, C_MID], [0.6666, C_MID], [0.6667, C_OK], [1, C_OK]],
            textfont=dict(color="white", size=13),
            hovertemplate="%{y}<br>%{x} : %{text}<extra></extra>"))
        fig.update_yaxes(autorange="reversed", tickfont=dict(size=12))
        fig.update_xaxes(side="top")
        plot(fig, h=max(420, 32 * len(ylab) + 80))
        if no_target:
            st.caption("Sans cible régionale renseignée, donc absents de la carte : "
                       + " ; ".join(f"{m['num']}. {short(m['label'], 60)}" for m in no_target))

        st.markdown("#### Détail d'un indicateur par région")
        mk = pick_box("Indicateur", reg_mains, main_label, "reg_pick")
        gkeys = [r for r in by_sheet["Global"] if r["main_key"] == mk]
        sub_opts = [r["key"] for r in gkeys]
        sub_lab = {r["key"]: ("Total de l'indicateur" if r["level"] == 0 else
                              (f"{r['group']} > {r['label']}" if r["level"] == 2 else r["label"])) for r in gkeys}
        sk = pick_box("Niveau de lecture", sub_opts, lambda k: sub_lab[k], "reg_sub")
        data = []
        for s in REGIONS:
            r = idx.get((s, sk))
            if r:
                data.append({"Région": REGION_LABELS[s], "Cible": r["cible"], "Atteint": r["atteint"],
                             "Taux": r["taux"], "rec": r})
        if data:
            ref = data[0]["rec"]
            fig = go.Figure()
            fig.add_bar(x=[d["Région"] for d in data], y=[d["Cible"] for d in data], name="Cible",
                        marker_color=C_TARGET, hovertemplate="%{x}<br>Cible : %{y:,.0f}<extra></extra>")
            fig.add_bar(x=[d["Région"] for d in data], y=[d["Atteint"] for d in data], name="Atteint",
                        marker_color=[status(d["Taux"])[1] for d in data],
                        text=[fmt_pct(d["Taux"]) for d in data], textposition="outside",
                        hovertemplate="%{x}<br>Atteint : %{y:,.0f}<extra></extra>")
            fig.update_layout(barmode="group", bargap=0.3, separators=", ")
            if ref["pct"]:
                fig.update_yaxes(tickformat=".0%")
            plot(fig, h=420)
            st.dataframe(pd.DataFrame([{"Région": d["Région"], "Cible": fmt_v(d["rec"], d["Cible"]),
                                        "Atteint": fmt_v(d["rec"], d["Atteint"]), "Taux": fmt_pct(d["Taux"]),
                                        "Statut": status(d["Taux"])[0]} for d in data]),
                         hide_index=True, width="stretch")
        else:
            st.info("Ce niveau de lecture n'existe pas dans les feuilles régionales.")

# ============ 3. CARTE ============
GEO = load_geo()
REG_NAME = {"Tambacounda": "Tambacounda", "Dakar": "Dakar", "Kedougou": "Kédougou",
            "Sedhiou": "Sédhiou", "Matam": "Matam"}
C_LAND_OUT, C_LAND_SN, C_OCEAN, C_RIVER, C_BORDER = "#E4E1D8", "#F7F5EF", "#D6E6F0", "#7FA9C9", "#FFFFFF"


def lines_xy(geom):
    xs, ys = [], []
    parts = [geom["coordinates"]] if geom["type"] == "LineString" else geom["coordinates"]
    for part in parts:
        for x, y in part:
            xs.append(x); ys.append(y)
        xs.append(None); ys.append(None)
    return xs, ys


with tab3:
    st.markdown("Taux de réalisation de l'indicateur choisi dans les 5 régions d'intervention. "
                "Survole une région pour afficher les valeurs.")
    cand = []
    for gm in [r for r in RECS if r["sheet"] == "Global" and r["level"] == 0]:
        if not show_hidden and gm["hidden"]:
            continue
        if any(r["main_key"] == gm["main_key"] and r["level"] == 0 for s in REGIONS for r in by_sheet[s]):
            cand.append(gm["main_key"])
    if not cand:
        st.info("Aucun indicateur n'est ventilé par région.")
    else:
        mk = pick_box("Indicateur", cand, main_label, "map_pick")
        gm = ref_mains[mk]
        idx = {(r["sheet"], r["key"]): r for r in VIS}
        fig = go.Figure()

        def rings(geom):
            polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
            xs, ys = [], []
            for poly in polys:
                for x, y in poly[0]:
                    xs.append(x); ys.append(y)
                xs.append(None); ys.append(None)
            return xs, ys

        def area(fill, line, width, geom, hover=None):
            xs, ys = rings(geom)
            fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", fill="toself", fillcolor=fill,
                                     line=dict(color=line, width=width), showlegend=False,
                                     hoveron="fills" if hover else None,
                                     hoverinfo="text" if hover else "skip", text=hover or ""))

        for f in GEO["countries"]:
            if f["id"] != "SEN":
                area(C_LAND_OUT, "#C9C5B9", 1, f["geometry"])
        proj = {REG_NAME[s]: s for s in REGIONS}
        for f in GEO["regions"]:
            if f["id"] not in proj:
                area(C_LAND_SN, "#CFCBBF", 0.8, f["geometry"], f"{f['id']} : hors zone d'intervention")
        for f in GEO["regions"]:
            if f["id"] in proj:
                r = idx.get((proj[f["id"]], gm["key"]))
                t = r["taux"] if r else None
                colr = status(t)[1] if r else C_NONE
                hov = (f"<b>{f['id']}</b><br>Atteint : {fmt_v(r, r['atteint'])}<br>Cible : {fmt_v(r, r['cible'])}"
                       f"<br>Taux : {fmt_pct(t)}<br>{status(t)[0]}") if r else f"<b>{f['id']}</b><br>Non renseigné"
                area(colr, "#FFFFFF", 2.2, f["geometry"], hov)
        for rv in GEO["rivers"]:
            xs, ys = lines_xy(rv["geometry"])
            fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=C_RIVER, width=1.8),
                                     hoverinfo="skip", showlegend=False))
        cen = {f["id"]: (f["properties"]["lon"], f["properties"]["lat"]) for f in GEO["regions"]}
        oth = [n for n in cen if n not in proj]
        fig.add_trace(go.Scatter(x=[cen[n][0] for n in oth], y=[cen[n][1] for n in oth], mode="text",
                                 text=oth, textfont=dict(size=11, color="#9A958A"), hoverinfo="skip",
                                 showlegend=False))
        px_, py_, pt = [], [], []
        for name, s in proj.items():
            r = idx.get((s, gm["key"]))
            lon, lat = (-17.75, 14.95) if name == "Dakar" else cen[name]
            px_.append(lon); py_.append(lat)
            pt.append(f"<b>{name}</b><br>{fmt_pct(r['taux']) if r else 'n.d.'}")
        fig.add_trace(go.Scatter(x=px_, y=py_, mode="text", text=pt, hoverinfo="skip", showlegend=False,
                                 textfont=dict(size=13, color="#FFFFFF")))
        fig.data[-1].textfont.color = ["#1B2A41" if n == "Dakar" else "#FFFFFF" for n in proj]
        fig.add_trace(go.Scatter(x=[-17.44], y=[14.69], mode="markers", showlegend=False,
                                 marker=dict(symbol="star", size=12, color="#1B2A41", line=dict(color="white", width=1)),
                                 hovertemplate="Dakar, capitale<extra></extra>"))
        labs = [("MAURITANIE", -13.8, 16.7), ("MALI", -10.9, 14.6), ("GUINÉE", -12.4, 11.75),
                ("GUINÉE-BISSAU", -15.1, 11.85), ("GAMBIE", -16.35, 13.62)]
        fig.add_trace(go.Scatter(x=[l[1] for l in labs], y=[l[2] for l in labs], mode="text", showlegend=False,
                                 text=[l[0] for l in labs], hoverinfo="skip",
                                 textfont=dict(size=11, color="#8C877B")))
        fig.add_trace(go.Scatter(x=[-17.35], y=[13.0], mode="text", hoverinfo="skip", showlegend=False,
                                 text=["<i>Océan<br>Atlantique</i>"], textfont=dict(size=12, color="#6F93AE")))
        fig.add_trace(go.Scatter(x=[-14.9], y=[16.25], mode="text", hoverinfo="skip", showlegend=False,
                                 text=["<i>Fleuve Sénégal</i>"], textfont=dict(size=10, color=C_RIVER)))
        fig.update_xaxes(visible=False, range=[-18.0, -10.9], fixedrange=True)
        fig.update_yaxes(visible=False, range=[11.5, 17.0], scaleanchor="x", scaleratio=1.03, fixedrange=True)
        fig.update_layout(height=620, margin=dict(l=0, r=0, t=0, b=0), showlegend=False,
                          plot_bgcolor=C_OCEAN, paper_bgcolor=C_OCEAN,
                          font=dict(family="Public Sans, sans-serif"),
                          hoverlabel=dict(bgcolor="white", font_size=13, font_color="#1B2A41"))
        st.plotly_chart(fig, width="stretch", config={"displaylogo": False, "scrollZoom": False})
        st.markdown(f'<div class="yjc-legend"><span style="--c:{C_OK}">Cible atteinte</span>'
                    f'<span style="--c:{C_MID}">En progression</span>'
                    f'<span style="--c:{C_LOW}">À renforcer</span>'
                    f'<span style="--c:{C_NONE}">Non renseigné</span>'
                    f'<span style="--c:{C_LAND_SN};outline:1px solid #CFCBBF">Hors zone d\'intervention</span></div>',
                    unsafe_allow_html=True)
        st.caption("Limites administratives : Natural Earth (domaine public), 14 régions du Sénégal.")

# ============ 4. ÉVOLUTION TRIMESTRIELLE ============
with tab4:
    def has_q(r):
        return any((q["atteint"] or 0) != 0 for q in r["quarters"])
    q_recs = [r for r in by_sheet[scope] if has_q(r)]
    if not q_recs:
        st.info(f"Aucune donnée trimestrielle n'est encore saisie pour {REGION_LABELS[scope]}.")
    else:
        st.markdown(f"{len({r['main_key'] for r in q_recs})} indicateurs disposent d'une saisie trimestrielle "
                    f"pour {REGION_LABELS[scope]}. Les autres sont renseignés uniquement en valeur cumulée.")
        q_mains = list(dict.fromkeys(r["main_key"] for r in q_recs))
        mk = pick_box("Indicateur", q_mains, main_label, "q_pick")
        lines = [r for r in q_recs if r["main_key"] == mk]
        lk = pick_box("Niveau de lecture", [r["key"] for r in lines],
                      lambda k: next(("Total de l'indicateur" if r["level"] == 0 else
                                      (f"{r['group']} > {r['label']}" if r["level"] == 2 else r["label"]))
                                     for r in lines if r["key"] == k), "q_sub")
        r = next(x for x in lines if x["key"] == lk)
        qs = r["quarters"]
        last = max((i for i, q in enumerate(qs) if (q["atteint"] or 0) != 0), default=len(qs) - 1)
        qs = qs[: max(last + 1, 4)]
        x = [f"{q['q']}<br>{q['year']}" for q in qs]
        att = [q["atteint"] or 0 for q in qs]
        cum, s_ = [], 0
        for a in att:
            s_ += a
            cum.append(s_)
        fig = go.Figure()
        fig.add_bar(x=x, y=att, name="Atteint sur le trimestre", marker_color=C_BLUE,
                    hovertemplate="%{x}<br>Atteint : %{y:,.0f}<extra></extra>")
        if any(q["cible"] for q in qs):
            fig.add_scatter(x=x, y=[q["cible"] for q in qs], name="Cible du trimestre", mode="lines+markers",
                            line=dict(color=C_MID, dash="dot", width=2))
        if not r["pct"]:
            fig.add_scatter(x=x, y=cum, name="Cumul depuis T1", mode="lines+markers", yaxis="y2",
                            line=dict(color=C_OK, width=3))
            fig.update_layout(yaxis2=dict(overlaying="y", side="right", showgrid=False, title="Cumul",
                                          rangemode="tozero", tickformat=",.0f"))
        fig.update_layout(separators=", ", yaxis=dict(rangemode="tozero", tickformat=",.0f"))
        plot(fig, h=450)
        st.caption(f"Affichage jusqu'au dernier trimestre renseigné ({qs[-1]['q']} {qs[-1]['year']}).")
        yrs = [a for a in r["annual"] if a["cible"] or a["atteint"]]
        if yrs:
            st.dataframe(pd.DataFrame([{"Année": str(a["year"]), "Cible annuelle": fmt_v(r, a["cible"]),
                                        "Atteint": fmt_v(r, a["atteint"]),
                                        "Taux": fmt_pct(a["atteint"] / a["cible"]) if a["cible"] and a["atteint"] is not None else "n.d."}
                                       for a in yrs]), hide_index=True, width="stretch")

# ============ 5. FICHE INDICATEUR ============
with tab5:
    all_mk = [m["main_key"] for m in mains]
    if not all_mk:
        st.info("Aucun indicateur pour ce périmètre.")
    else:
        mk = pick_box("Indicateur", all_mk, main_label, "fiche_pick")
        m = next(x for x in mains if x["main_key"] == mk)
        lab, col = status(m["taux"])
        st.markdown(f"##### {html.escape(m['label'])}")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Valeur atteinte", fmt_v(m, m["atteint"]))
        k2.metric("Cible", fmt_v(m, m["cible"]))
        k3.metric("Taux de réalisation", fmt_pct(m["taux"]))
        k4.markdown(f"<div style='padding-top:1.6rem;font-weight:600;color:{col}'>{lab}</div>", unsafe_allow_html=True)
        if m["obs"]:
            st.markdown(f"**Observations :** {html.escape(m['obs'])}")
        d = match_definition(m["label"], DEFS)
        if d and d["definition"]:
            with st.expander("Définition de l'indicateur", expanded=True):
                st.markdown(d["definition"])
        lines = [r for r in by_sheet[scope] if r["main_key"] == mk and r["level"] > 0]
        if lines:
            st.markdown("**Désagrégations**")
            fig = go.Figure(go.Bar(
                y=[(f"{r['group']} > " if r["level"] == 2 else "") + short(r["label"], 50) for r in lines],
                x=[(r["taux"] or 0) * 100 for r in lines], orientation="h",
                marker_color=[status(r["taux"])[1] for r in lines],
                text=[f"{fmt_v(r, r['atteint'])} / {fmt_v(r, r['cible'])}" if r["cible"] is not None
                      else fmt_v(r, r["atteint"]) for r in lines],
                textposition="outside", cliponaxis=False,
                hovertemplate="%{y}<br>Taux : %{x:.0f} %<extra></extra>"))
            fig.add_vline(x=100, line_dash="dot", line_color="#888")
            fig.update_yaxes(autorange="reversed")
            fig.update_xaxes(title="Taux de réalisation (%)", range=[0, max(130, max(((r["taux"] or 0) * 100 for r in lines), default=0) * 1.25)])
            plot(fig, h=max(260, 34 * len(lines) + 90))
        if scope == "Global":
            idx = {(r["sheet"], r["key"]): r for r in VIS}
            reg_rows = [{"Région": REGION_LABELS[s], "Cible": fmt_v(m, idx[(s, m["key"])]["cible"]),
                         "Atteint": fmt_v(m, idx[(s, m["key"])]["atteint"]),
                         "Taux": fmt_pct(idx[(s, m["key"])]["taux"])}
                        for s in REGIONS if (s, m["key"]) in idx]
            if reg_rows:
                st.markdown("**Répartition régionale**")
                st.dataframe(pd.DataFrame(reg_rows), hide_index=True, width="stretch")
            else:
                st.caption("Indicateur suivi uniquement au niveau du projet (pas de ventilation régionale).")

# ============ 6. DONNÉES ============
with tab6:
    df = pd.DataFrame([{"Périmètre": REGION_LABELS[r["sheet"]], "N°": r["num"],
                        "Indicateur principal": r["main"], "Sous-groupe": r["group"], "Libellé": r["label"],
                        "Niveau": r["level"], "Cible": r["cible"], "Atteint": r["atteint"],
                        "Taux (%)": round(r["taux"] * 100, 1) if r["taux"] is not None else None,
                        "Statut": status(r["taux"])[0], "Masqué dans le Sheet": r["hidden"],
                        "Ligne du Sheet": r["row"], "Observations": r["obs"]} for r in VIS])
    st.markdown(f"{len(df)} lignes lues sur les 6 feuilles (Global et 5 régions).")
    st.dataframe(df, hide_index=True, width="stretch", height=560)
    st.download_button("Télécharger en CSV", df.to_csv(index=False, sep=";").encode("utf-8-sig"),
                       file_name=f"indicateurs_yjc_{datetime.now():%Y%m%d}.csv", mime="text/csv")
