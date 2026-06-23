"""Export cartographique HTML autonome de la solution validee."""

from __future__ import annotations

import json
import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any

from cc_formation_optimizer.config import OptimizerConfig
from cc_formation_optimizer.data_loading import load_communes
from cc_formation_optimizer.domain import Commune
from cc_formation_optimizer.export import build_assignment_export_rows, build_session_export_rows, build_statistics
from cc_formation_optimizer.model_builder import ModelBundle
from cc_formation_optimizer.solution_extractor import ExtractedSolution
from cc_formation_optimizer.validation import ValidationReport


class MapExportError(ValueError):
    """Erreur empechant l'export cartographique."""


@dataclass(frozen=True)
class MapExportResult:
    """Chemin du fichier HTML cartographique produit."""

    html_path: Path
    mapped_points: int
    missing_coordinates: int


def export_solution_map(
    solution: ExtractedSolution,
    validation_report: ValidationReport,
    model_bundle: ModelBundle,
    config: OptimizerConfig,
    communes: list[Commune],
    output_dir: str | Path | None = None,
) -> MapExportResult:
    """Genere `outputs/maps/solution_map.html` depuis une solution validee."""

    if not validation_report.is_valid:
        raise MapExportError("La solution n'a pas passe la validation; la carte ne sera pas produite.")

    root = Path(output_dir) if output_dir is not None else Path(config.exports.get("output_dir", "outputs"))
    maps_dir = root / "maps"
    maps_dir.mkdir(parents=True, exist_ok=True)
    html_path = maps_dir / "solution_map.html"

    commune_by_id = {commune.commune_id: commune for commune in communes}
    session_rows = build_session_export_rows(solution, model_bundle, config)
    assignment_rows = build_assignment_export_rows(solution, commune_by_id, config)
    statistics = build_statistics(solution, validation_report, config, session_rows, assignment_rows)
    points, missing = _build_points(solution, commune_by_id, config)
    summary = _build_summary(session_rows)
    global_stats = _build_global_stats(statistics, missing)
    validation_checks = _build_validation_checks(validation_report, global_stats)

    html_path.write_text(
        _render_html(global_stats, validation_checks, points, summary, missing),
        encoding="utf-8",
    )
    return MapExportResult(html_path=html_path, mapped_points=len(points), missing_coordinates=len(missing))


def render_map_from_exports(
    config: OptimizerConfig,
    solution_dir: str | Path | None = None,
    sessions_path: str | Path | None = None,
    assignments_path: str | Path | None = None,
    stats_path: str | Path | None = None,
    output_path: str | Path | None = None,
) -> MapExportResult:
    """Regenere la carte HTML depuis des exports existants, sans resoudre."""

    root = Path(solution_dir) if solution_dir is not None else Path(config.exports.get("output_dir", "outputs"))
    sessions_csv = Path(sessions_path) if sessions_path is not None else root / "solutions" / "sessions.csv"
    assignments_csv = Path(assignments_path) if assignments_path is not None else root / "solutions" / "communes_affectees.csv"
    statistics_json = Path(stats_path) if stats_path is not None else root / "reports" / "statistiques_solution.json"
    html_path = Path(output_path) if output_path is not None else root / "maps" / "solution_map.html"

    session_rows = _read_csv_dicts(sessions_csv)
    assignment_rows = _read_csv_dicts(assignments_csv)
    statistics = _read_json_dict(statistics_json)
    communes = load_communes(config)
    commune_by_id = {commune.commune_id: commune for commune in communes}

    points, missing = _build_points_from_export_rows(assignment_rows, session_rows, commune_by_id, config)
    summary = _build_summary(_coerce_session_rows(session_rows))
    global_stats = _build_global_stats(statistics, missing)
    validation_checks = _build_validation_checks_from_statistics(global_stats)

    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(
        _render_html(global_stats, validation_checks, points, summary, missing),
        encoding="utf-8",
    )
    return MapExportResult(html_path=html_path, mapped_points=len(points), missing_coordinates=len(missing))


def _build_points(
    solution: ExtractedSolution,
    commune_by_id: dict[str, Commune],
    config: OptimizerConfig,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sessions_by_id = {session.id_session: session for session in solution.sessions}
    open_pivot_ids = {session.code_pivot for session in solution.sessions}
    points: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for assignment in solution.assignments:
        commune = commune_by_id[assignment.code_commune]
        pivot = commune_by_id[assignment.code_pivot]
        session = sessions_by_id[assignment.id_session]
        reasons = _split_reasons(_assignment_alert_reasons(assignment, commune, pivot, config))
        payload = {
            "code_commune": assignment.code_commune,
            "nom_commune": assignment.nom_commune,
            "categorie": assignment.categorie,
            "territoire_EAR": assignment.territoire_EAR or "",
            "lat": commune.latitude,
            "lon": commune.longitude,
            "population": assignment.population,
            "logements": assignment.logements,
            "nombre_CC": assignment.nombre_CC,
            "id_session": assignment.id_session,
            "code_pivot": assignment.code_pivot,
            "nom_pivot": assignment.nom_pivot,
            "type_session": assignment.type_session,
            "rang_m": session.rang_m,
            "temps_trajet_minutes": assignment.temps_trajet_minutes,
            "is_pivot": assignment.code_commune in open_pivot_ids,
            "is_same_territory_as_pivot": _same_territory(commune, pivot),
            "is_travel_near_limit": assignment.temps_trajet_minutes / config.parameters.T
            >= config.exports["alerts"]["travel_close_ratio"],
            "is_category_mismatch": assignment.categorie != assignment.type_session,
            "alert_level": _level(reasons),
            "alert_reasons": reasons,
        }
        if commune.latitude is None or commune.longitude is None:
            missing.append(payload)
        else:
            points.append(payload)
    return points, missing


def _build_points_from_export_rows(
    assignment_rows: list[dict[str, str]],
    session_rows: list[dict[str, str]],
    commune_by_id: dict[str, Commune],
    config: OptimizerConfig,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sessions_by_id = {row["id_session"]: row for row in session_rows}
    open_pivot_ids = {row["code_pivot"] for row in session_rows}
    points: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for row in assignment_rows:
        commune = commune_by_id[row["code_commune"]]
        pivot = commune_by_id[row["code_pivot"]]
        session = sessions_by_id.get(row["id_session"], {})
        reasons = _split_reasons(row.get("alert_reasons", ""))
        travel_time = _to_int(row.get("temps_trajet_minutes"))
        payload = {
            "code_commune": row["code_commune"],
            "nom_commune": row["nom_commune"],
            "categorie": row["categorie"],
            "territoire_EAR": row.get("territoire_EAR", ""),
            "lat": commune.latitude,
            "lon": commune.longitude,
            "population": _to_int(row.get("population")),
            "logements": _to_optional_int(row.get("logements")),
            "nombre_CC": _to_int(row.get("nombre_CC")),
            "id_session": row["id_session"],
            "code_pivot": row["code_pivot"],
            "nom_pivot": row["nom_pivot"],
            "type_session": row["type_session"],
            "rang_m": _to_int(session.get("rang_m")),
            "temps_trajet_minutes": travel_time,
            "is_pivot": row["code_commune"] in open_pivot_ids,
            "is_same_territory_as_pivot": _same_territory(commune, pivot),
            "is_travel_near_limit": travel_time / config.parameters.T >= config.exports["alerts"]["travel_close_ratio"],
            "is_category_mismatch": row["categorie"] != row["type_session"],
            "alert_level": str(row.get("alert_level", "OK")).lower(),
            "alert_reasons": reasons,
        }
        if commune.latitude is None or commune.longitude is None:
            missing.append(payload)
        else:
            points.append(payload)
    return points, missing


def _coerce_session_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    coerced: list[dict[str, Any]] = []
    numeric_fields = {
        "rang_m",
        "nombre_communes",
        "nombre_CC",
        "capacite_Q",
        "places_restantes",
        "nombre_PC",
        "nombre_TPC",
        "nombre_CC_PC",
        "nombre_CC_TPC",
        "temps_trajet_min",
        "temps_trajet_max",
        "population_min",
        "population_max",
        "cout_eligibilite_pivot",
        "d_jm",
        "objectif_trajet_session",
        "objectif_eligibilite_session",
        "objectif_mixite_session",
    }
    float_fields = {"taux_remplissage", "temps_trajet_moyen", "temps_trajet_median", "population_moyenne", "population_mediane"}
    for row in rows:
        payload: dict[str, Any] = dict(row)
        for field in numeric_fields:
            payload[field] = _to_int(payload.get(field))
        for field in float_fields:
            payload[field] = _to_number(payload.get(field))
        coerced.append(payload)
    return coerced


def _build_validation_checks_from_statistics(global_stats: dict[str, Any]) -> list[dict[str, str]]:
    status = "ok" if global_stats.get("validation_status") == "OK" else "warning"
    constraints = (
        "unique_assignment",
        "opening",
        "capacity",
        "budgets",
        "pc_to_tpc_asymmetry",
        "travel",
        "compatibility",
        "session_type",
        "mixing",
        "objective",
    )
    return [
        {
            "name": name,
            "status": status,
            "value": str(global_stats.get("validation_status", "UNKNOWN")),
            "detail": "Reconstruit depuis les exports existants, sans relancer le solveur.",
        }
        for name in constraints
    ]


def _build_summary(session_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for row in session_rows:
        summary.append(
            {
                "id_session": row["id_session"],
                "code_pivot": row["code_pivot"],
                "nom_pivot": row["nom_pivot"],
                "type_session": row["type_session"],
                "territoire_majoritaire": row["territoire_majoritaire"],
                "nombre_communes": row["nombre_communes"],
                "nombre_CC": row["nombre_CC"],
                "capacite_Q": row["capacite_Q"],
                "taux_remplissage": row["taux_remplissage"],
                "places_restantes": row["places_restantes"],
                "nombre_PC": row["nombre_PC"],
                "nombre_TPC": row["nombre_TPC"],
                "nombre_CC_PC": row["nombre_CC_PC"],
                "nombre_CC_TPC": row["nombre_CC_TPC"],
                "temps_trajet_min": row["temps_trajet_min"],
                "temps_trajet_moyen": row["temps_trajet_moyen"],
                "temps_trajet_median": row["temps_trajet_median"],
                "temps_trajet_max": row["temps_trajet_max"],
                "population_min": row["population_min"],
                "population_median": row["population_mediane"],
                "population_max": row["population_max"],
                "cout_eligibilite": row["cout_eligibilite_pivot"],
                "d_jm": row["d_jm"],
                "objectif_trajet_session": row["objectif_trajet_session"],
                "objectif_eligibilite_session": row["objectif_eligibilite_session"],
                "objectif_mixite_session": row["objectif_mixite_session"],
                "alert_level": str(row["alert_level"]).lower(),
                "alert_reasons": _split_reasons(str(row["alert_reasons"])),
            }
        )
    return summary


def _build_global_stats(statistics: dict[str, Any], missing: list[dict[str, Any]]) -> dict[str, Any]:
    global_stats = dict(statistics)
    global_stats["communes_sans_coordonnees"] = len(missing)
    return global_stats


def _build_validation_checks(
    validation_report: ValidationReport,
    global_stats: dict[str, Any],
) -> list[dict[str, str]]:
    details = {
        "unique_assignment": f"{global_stats['nombre_communes_affectees']} communes affectees.",
        "capacity": f"Q={global_stats['Q']} respecte.",
        "budgets": f"{global_stats['sessions_ouvertes']} sessions / B={global_stats['B']}.",
        "objective": f"Objectif total recalcule={global_stats['objective_total']}.",
    }
    checks = []
    for name in validation_report.checked_constraints:
        checks.append(
            {
                "name": name,
                "status": "ok",
                "value": "OK",
                "detail": details.get(name, "Controle valide par validate_solution()."),
            }
        )
    return checks


def _render_html(
    global_stats: dict[str, Any],
    validation_checks: list[dict[str, Any]],
    points: list[dict[str, Any]],
    summary: list[dict[str, Any]],
    missing: list[dict[str, Any]],
) -> str:
    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Carte de controle - formations CC</title>
  <style>
    :root {{ --bg:#f6f7f9; --panel:#ffffff; --ink:#1f2937; --muted:#6b7280; --line:#d1d5db; --ok:#0f766e; --warn:#b45309; --err:#b91c1c; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:Segoe UI, Arial, sans-serif; color:var(--ink); background:var(--bg); }}
    header {{ display:grid; grid-template-columns:repeat(9, minmax(110px,1fr)); gap:8px; padding:10px; background:#111827; color:#fff; }}
    .kpi {{ padding:8px; border:1px solid #374151; border-radius:6px; min-height:58px; }}
    .kpi span {{ display:block; font-size:11px; color:#cbd5e1; }}
    .kpi strong {{ font-size:16px; }}
    main {{ display:grid; grid-template-columns:320px 1fr; min-height:calc(100vh - 80px); }}
    aside {{ background:var(--panel); border-right:1px solid var(--line); padding:12px; overflow:auto; }}
    section {{ padding:10px; }}
    label {{ display:block; font-size:12px; margin-top:8px; color:var(--muted); }}
    select, button {{ width:100%; padding:7px; border:1px solid var(--line); border-radius:6px; background:#fff; }}
    button {{ cursor:pointer; margin-top:8px; }}
    .check {{ display:flex; gap:8px; align-items:center; font-size:13px; margin-top:8px; }}
    .check input {{ width:auto; }}
    #mapWrap {{ position:relative; height:58vh; min-height:420px; border:1px solid var(--line); background:#eef2f7; overflow:hidden; border-radius:8px; }}
    #tileLayer, #svgLayer {{ position:absolute; inset:0; }}
    #tileLayer {{ z-index:1; }}
    #tileLayer img {{ position:absolute; width:256px; height:256px; opacity:.82; }}
    #svgLayer {{ width:100%; height:100%; z-index:2; }}
    .mapControls {{ position:absolute; right:10px; top:10px; width:88px; z-index:5; }}
    .mapControls button {{ margin:0 0 6px 0; }}
    #tileFallback {{ position:absolute; left:10px; bottom:10px; z-index:6; display:none; max-width:420px; }}
    .notice {{ background:#fff7ed; border:1px solid #fed7aa; padding:8px; border-radius:6px; margin:8px 0; }}
    .tooltip {{ position:absolute; display:none; pointer-events:none; background:#111827; color:#fff; padding:8px; border-radius:6px; font-size:12px; max-width:280px; z-index:10; }}
    .detail {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:10px; margin-top:10px; }}
    .debug {{ background:#fff; border:1px solid var(--line); border-radius:8px; padding:8px 10px; margin-top:10px; font-size:12px; }}
    .debug summary {{ cursor:pointer; font-weight:600; }}
    .debug dl {{ display:grid; grid-template-columns:180px 1fr; gap:4px 8px; margin:8px 0 0; }}
    .debug dt {{ color:var(--muted); }}
    .debug dd {{ margin:0; font-family:Consolas, monospace; }}
    .tables {{ display:grid; grid-template-columns:1fr; gap:12px; margin-top:12px; }}
    table {{ width:100%; border-collapse:collapse; background:#fff; font-size:12px; }}
    th, td {{ border:1px solid var(--line); padding:6px; text-align:left; }}
    th {{ background:#f3f4f6; cursor:pointer; }}
    .charts {{ display:grid; grid-template-columns:repeat(3, minmax(220px,1fr)); gap:10px; margin-top:12px; }}
    .chart {{ background:#fff; border:1px solid var(--line); border-radius:8px; padding:10px; }}
    .bar {{ display:flex; align-items:center; gap:6px; margin:4px 0; }}
    .bar i {{ display:block; height:10px; background:#2563eb; min-width:2px; }}
    .ok {{ color:var(--ok); }} .warning {{ color:var(--warn); }} .error {{ color:var(--err); }}
    @media (max-width: 900px) {{ header {{ grid-template-columns:repeat(2,1fr); }} main {{ grid-template-columns:1fr; }} aside {{ border-right:none; border-bottom:1px solid var(--line); }} .charts {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
<script>
const globalStats = {_json(global_stats)};
const validationChecks = {_json(validation_checks)};
const points = {_json(points)};
const summary = {_json(summary)};
const missingCoordinates = {_json(missing)};
</script>
<header id="kpis"></header>
<main>
  <aside>
    <h2>Controle</h2>
    <label>Territoire EAR</label><select id="territoryFilter"></select>
    <label>Type de session</label><select id="sessionTypeFilter"><option value="">Toutes</option><option>PC</option><option>TPC</option></select>
    <label>Categorie commune</label><select id="categoryFilter"><option value="">Toutes</option><option>PC</option><option>TPC</option></select>
    <label>Niveau d'alerte</label><select id="alertFilter"><option value="">Tous</option><option value="ok">ok</option><option value="warning">warning</option><option value="error">error</option></select>
    <div class="check"><input id="pivotOnly" type="checkbox"><span>Afficher les pivots seulement</span></div>
    <div class="check"><input id="showLinks" type="checkbox"><span>Afficher les liaisons commune -> pivot</span></div>
    <div class="check"><input id="selectedOnly" type="checkbox"><span>Afficher uniquement la session selectionnee</span></div>
    <button id="resetFilters">Reinitialiser les filtres</button>
    <h3>Controles du modele</h3>
    <div id="checks"></div>
    <h3>Communes sans coordonnees</h3>
    <div id="missing"></div>
  </aside>
  <section>
    <div id="mapWrap">
      <div id="tileLayer"></div>
      <svg id="svgLayer" role="img" aria-label="Carte des affectations"></svg>
      <div class="mapControls"><button id="zoomIn">+</button><button id="zoomOut">-</button><button id="resetMap">Reset</button></div>
      <div id="tileFallback" class="notice">Fond de carte non chargé. Vérifier l’accès réseau à data.geopf.fr.</div>
      <div id="tooltip" class="tooltip"></div>
    </div>
    <div id="noCoords"></div>
    <details id="mapDebug" class="debug"><summary>Debug carte</summary><dl id="mapDebugBody"></dl></details>
    <div id="detail" class="detail">Cliquez sur une commune ou une session pour afficher le detail.</div>
    <div class="charts" id="charts"></div>
    <div class="tables">
      <div><h3>Sessions</h3><table id="sessionTable"></table></div>
      <div><h3>Communes</h3><table id="communeTable"></table></div>
    </div>
  </section>
</main>
<script>
let state = {{ zoom:null, initialZoom:null, center:null, initialCenter:null, tx:0, ty:0, selectedSession:null, dragging:false, last:null, tilesAttempted:0, tileErrors:0, tileLoaded:0, tileErrorMessage:'' }};
const colors = new Map(summary.map((s,i)=>[s.id_session, `hsl(${{(i*67)%360}} 65% 43%)`]));
const wrap = document.getElementById('mapWrap'), tileLayer = document.getElementById('tileLayer'), svg = document.getElementById('svgLayer'), tip = document.getElementById('tooltip');
const tileFallback = document.getElementById('tileFallback'), mapDebugBody = document.getElementById('mapDebugBody');
const TILE_SIZE = 256;
const MIN_ZOOM = 2;
const MAX_ZOOM = 18;
function kpi(label, value) {{ return `<div class="kpi"><span>${{label}}</span><strong>${{value}}</strong></div>`; }}
document.getElementById('kpis').innerHTML = [
  kpi('Solveur', globalStats.solver_status), kpi('Validation', globalStats.validation_status),
  kpi('Communes', `${{globalStats.nombre_communes_affectees}}/${{globalStats.nombre_communes}}`),
  kpi('CC', globalStats.nombre_CC), kpi('Sessions / B', `${{globalStats.sessions_ouvertes}}/${{globalStats.B}}`),
  kpi('PC / f', `${{globalStats.sessions_PC}}/${{globalStats.f}}`), kpi('TPC / k', `${{globalStats.sessions_TPC}}/${{globalStats.k}}`),
  kpi('Temps moy/max', `${{globalStats.temps_moyen_global}} / ${{globalStats.temps_max_global}}`), kpi('Objectif', globalStats.objective_total)
].join('');
function setupFilters() {{
  const territories = [...new Set(points.map(p=>p.territoire_EAR).filter(Boolean))].sort();
  document.getElementById('territoryFilter').innerHTML = '<option value="">Tous</option>' + territories.map(t=>`<option>${{t}}</option>`).join('');
  ['territoryFilter','sessionTypeFilter','categoryFilter','alertFilter','pivotOnly','showLinks','selectedOnly'].forEach(id => document.getElementById(id).addEventListener('change', render));
  document.getElementById('resetFilters').onclick = () => {{ ['territoryFilter','sessionTypeFilter','categoryFilter','alertFilter'].forEach(id=>document.getElementById(id).value=''); ['pivotOnly','showLinks','selectedOnly'].forEach(id=>document.getElementById(id).checked=false); state.selectedSession=null; render(); }};
}}
function filteredPoints() {{
  const territory = document.getElementById('territoryFilter').value, type = document.getElementById('sessionTypeFilter').value, cat = document.getElementById('categoryFilter').value, alert = document.getElementById('alertFilter').value;
  const pivotsOnly = document.getElementById('pivotOnly').checked;
  const selectedOnly = document.getElementById('selectedOnly').checked;
  return points.filter(p => {{
    if (territory && p.territoire_EAR !== territory) return false;
    if (type && p.type_session !== type) return false;
    if (cat && p.categorie !== cat) return false;
    if (alert && p.alert_level !== alert) return false;
    if (pivotsOnly && p.is_pivot !== true) return false;
    if (selectedOnly && state.selectedSession && p.id_session !== state.selectedSession) return false;
    return true;
  }});
}}
function validGeoPoints() {{ return points.filter(p => Number.isFinite(Number(p.lat)) && Number.isFinite(Number(p.lon))); }}
function bounds(data) {{ const xs=data.map(p=>Number(p.lon)), ys=data.map(p=>Number(p.lat)); return {{ minLon:Math.min(...xs), maxLon:Math.max(...xs), minLat:Math.min(...ys), maxLat:Math.max(...ys) }}; }}
function lonLatToWorld(lon, lat, zoom) {{
  const scale = TILE_SIZE * Math.pow(2, zoom);
  const clampedLat = Math.max(-85.05112878, Math.min(85.05112878, Number(lat)));
  const x = (Number(lon) + 180) / 360 * scale;
  const sinLat = Math.sin(clampedLat * Math.PI / 180);
  const y = (0.5 - Math.log((1 + sinLat) / (1 - sinLat)) / (4 * Math.PI)) * scale;
  return {{ x, y }};
}}
function worldToScreen(world) {{
  const center = lonLatToWorld(state.center.lon, state.center.lat, state.zoom);
  return {{
    x: world.x - center.x + wrap.clientWidth / 2 + state.tx,
    y: world.y - center.y + wrap.clientHeight / 2 + state.ty
  }};
}}
function project(p) {{ return worldToScreen(lonLatToWorld(p.lon, p.lat, state.zoom)); }}
function chooseInitialView(b) {{
  const w = Math.max(1, wrap.clientWidth - 72), h = Math.max(1, wrap.clientHeight - 72);
  const center = {{ lon:(b.minLon + b.maxLon) / 2, lat:(b.minLat + b.maxLat) / 2 }};
  let zoom = MIN_ZOOM;
  for (let z = MAX_ZOOM; z >= MIN_ZOOM; z--) {{
    const nw = lonLatToWorld(b.minLon, b.maxLat, z);
    const se = lonLatToWorld(b.maxLon, b.minLat, z);
    if (Math.abs(se.x - nw.x) <= w && Math.abs(se.y - nw.y) <= h) {{ zoom = z; break; }}
  }}
  return {{ center, zoom }};
}}
function ensureInitialView() {{
  const geo = validGeoPoints();
  if (!geo.length) return null;
  const b = bounds(geo);
  if (state.zoom === null || state.center === null) {{
    const view = chooseInitialView(b);
    state.zoom = view.zoom;
    state.initialZoom = view.zoom;
    state.center = view.center;
    state.initialCenter = view.center;
  }}
  return b;
}}
function wmtsUrl(z, x, y) {{
  return `https://data.geopf.fr/wmts?SERVICE=WMTS&VERSION=1.0.0&REQUEST=GetTile&LAYER=GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2&STYLE=normal&FORMAT=image/png&TILEMATRIXSET=PM&TILEMATRIX=${{z}}&TILEROW=${{y}}&TILECOL=${{x}}`;
}}
function drawTiles() {{
  tileLayer.innerHTML = '';
  tileFallback.style.display = 'none';
  state.tilesAttempted = 0;
  state.tileErrors = 0;
  state.tileLoaded = 0;
  state.tileErrorMessage = '';
  if (state.zoom === null || state.center === null) return;
  const z = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, Math.round(state.zoom)));
  state.zoom = z;
  const centerWorld = lonLatToWorld(state.center.lon, state.center.lat, z);
  const leftWorld = centerWorld.x - wrap.clientWidth / 2 - state.tx;
  const topWorld = centerWorld.y - wrap.clientHeight / 2 - state.ty;
  const rightWorld = leftWorld + wrap.clientWidth;
  const bottomWorld = topWorld + wrap.clientHeight;
  const minTileX = Math.floor(leftWorld / TILE_SIZE);
  const maxTileX = Math.floor(rightWorld / TILE_SIZE);
  const minTileY = Math.max(0, Math.floor(topWorld / TILE_SIZE));
  const maxTileY = Math.min(Math.pow(2, z) - 1, Math.floor(bottomWorld / TILE_SIZE));
  const worldTiles = Math.pow(2, z);
  for (let ty = minTileY; ty <= maxTileY; ty++) {{
    for (let tx = minTileX; tx <= maxTileX; tx++) {{
      const wrappedX = ((tx % worldTiles) + worldTiles) % worldTiles;
      const img = document.createElement('img');
      img.width = TILE_SIZE;
      img.height = TILE_SIZE;
      img.alt = '';
      img.decoding = 'async';
      img.loading = 'lazy';
      img.src = wmtsUrl(z, wrappedX, ty);
      img.style.left = `${{tx * TILE_SIZE - leftWorld}}px`;
      img.style.top = `${{ty * TILE_SIZE - topWorld}}px`;
      img.onerror = () => {{ state.tileErrors += 1; state.tileErrorMessage = 'Fond de carte non chargé. Vérifier l’accès réseau à data.geopf.fr.'; updateTileFallback(); updateMapDebug(bounds(validGeoPoints())); }};
      img.onload = () => {{ state.tileLoaded += 1; updateTileFallback(); updateMapDebug(bounds(validGeoPoints())); }};
      state.tilesAttempted += 1;
      tileLayer.appendChild(img);
    }}
  }}
  updateTileFallback();
}}
function updateTileFallback() {{
  tileFallback.style.display = state.tilesAttempted > 0 && state.tileErrors > 0 && state.tileLoaded === 0 ? 'block' : 'none';
}}
function render() {{
  const data = filteredPoints(); svg.innerHTML = ''; svg.setAttribute('width', wrap.clientWidth); svg.setAttribute('height', wrap.clientHeight);
  if (!points.length) {{ document.getElementById('noCoords').innerHTML = '<div class="notice">Aucune coordonnee latitude/longitude disponible : controle sans carte geographique.</div>'; renderTables(data); return; }}
  document.getElementById('noCoords').innerHTML = globalStats.communes_sans_coordonnees ? `<div class="notice">${{globalStats.communes_sans_coordonnees}} commune(s) sans coordonnees non affichee(s) sur la carte.</div>` : '';
  const b = ensureInitialView();
  if (!b) {{ document.getElementById('noCoords').innerHTML = '<div class="notice">Aucune coordonnee latitude/longitude disponible : controle sans carte geographique.</div>'; renderTables(data); updateMapDebug(null); return; }}
  drawTiles();
  drawPoints(data);
  renderTables(data); renderCharts(); updateMapDebug(b);
}}
function drawPoints(data) {{
  const pivotsOnly = document.getElementById('pivotOnly').checked;
  if (document.getElementById('showLinks').checked && !pivotsOnly) {{
    data.forEach(p => {{ const pivot = points.find(q=>q.code_commune===p.code_pivot); if (!pivot) return; const a=project(p), c=project(pivot); svg.insertAdjacentHTML('beforeend', `<line x1="${{a.x}}" y1="${{a.y}}" x2="${{c.x}}" y2="${{c.y}}" stroke="${{colors.get(p.id_session)}}" stroke-width="1" opacity=".35"/>`); }});
  }}
  data.forEach(p => {{ const c=project(p), color=colors.get(p.id_session)||'#2563eb', size=p.is_pivot?12:8, stroke=p.alert_level==='warning'?'#b45309':p.alert_level==='error'?'#b91c1c':'#fff'; const shape=p.categorie==='PC'?`<rect class="mapPoint" x="${{c.x-size/2}}" y="${{c.y-size/2}}" width="${{size}}" height="${{size}}" rx="2"`:`<circle class="mapPoint" cx="${{c.x}}" cy="${{c.y}}" r="${{size/2}}"`; svg.insertAdjacentHTML('beforeend', `${{shape}} fill="${{color}}" stroke="${{stroke}}" stroke-width="${{p.alert_level==='ok'?1.5:3}}" data-code="${{p.code_commune}}" style="cursor:pointer"/>`); }});
  [...svg.querySelectorAll('.mapPoint')].forEach(el => {{ el.onmousemove = e => showTip(e, points.find(p=>p.code_commune===el.dataset.code)); el.onmouseleave = hideTip; el.onclick = () => {{ const p=points.find(q=>q.code_commune===el.dataset.code); state.selectedSession=p.id_session; showDetail(p); renderTables(data); }}; }});
}}
function updateMapDebug(b) {{
  const geo = validGeoPoints();
  const center = state.center || {{lat:null, lon:null}};
  const rows = [
    ['points_total', points.length],
    ['points_avec_coordonnees', geo.length],
    ['minLat', b ? b.minLat.toFixed(6) : ''],
    ['maxLat', b ? b.maxLat.toFixed(6) : ''],
    ['minLon', b ? b.minLon.toFixed(6) : ''],
    ['maxLon', b ? b.maxLon.toFixed(6) : ''],
    ['centre_initial', state.initialCenter ? `${{state.initialCenter.lat.toFixed(6)}}, ${{state.initialCenter.lon.toFixed(6)}}` : ''],
    ['centre_courant', center.lat !== null ? `${{center.lat.toFixed(6)}}, ${{center.lon.toFixed(6)}}` : ''],
    ['zoom_initial', state.initialZoom ?? ''],
    ['zoom_courant', state.zoom ?? ''],
    ['tuiles_tentees', state.tilesAttempted],
    ['tuiles_chargees', state.tileLoaded],
    ['erreurs_tuiles', state.tileErrors],
    ['message_erreur', state.tileErrorMessage]
  ];
  mapDebugBody.innerHTML = rows.map(([k,v]) => `<dt>${{k}}</dt><dd>${{v}}</dd>`).join('');
}}
function showTip(e,p) {{ if(!p) return; tip.style.display='block'; tip.style.left=(e.offsetX+15)+'px'; tip.style.top=(e.offsetY+15)+'px'; tip.innerHTML = `<b>${{p.nom_commune}}</b><br>Code: ${{p.code_commune}}<br>Categorie: ${{p.categorie}}<br>Territoire: ${{p.territoire_EAR}}<br>Population: ${{p.population}}<br>Logements: ${{p.logements??''}}<br>CC: ${{p.nombre_CC}}<br>Session: ${{p.id_session}}<br>Pivot: ${{p.nom_pivot}}<br>Type: ${{p.type_session}}<br>Temps: ${{p.temps_trajet_minutes}} min<br>Alertes: ${{p.alert_reasons.join(', ')||'aucune'}}`; }}
function hideTip() {{ tip.style.display='none'; }}
function showDetail(p) {{ const s=summary.find(x=>x.id_session===p.id_session), members=points.filter(x=>x.id_session===p.id_session).map(x=>x.nom_commune).join(', '); document.getElementById('detail').innerHTML = `<h3>${{p.nom_commune}}</h3><p>Session ${{p.id_session}}, pivot ${{p.nom_pivot}}, temps ${{p.temps_trajet_minutes}} min.</p><h4>Session</h4><p>${{s.nombre_communes}} communes, ${{s.nombre_CC}} CC, remplissage ${{s.taux_remplissage}}, temps max ${{s.temps_trajet_max}}.</p><p><b>Communes:</b> ${{members}}</p><p><b>Alertes session:</b> ${{s.alert_reasons.join(', ')||'aucune'}}</p>`; }}
function renderChecks() {{ document.getElementById('checks').innerHTML = validationChecks.map(c=>`<div class="${{c.status}}">● <b>${{c.name}}</b> - ${{c.value}}<br><small>${{c.detail}}</small></div>`).join(''); document.getElementById('missing').innerHTML = missingCoordinates.length ? missingCoordinates.map(p=>`<div>${{p.nom_commune}} (${{p.code_commune}})</div>`).join('') : 'Aucune commune sans coordonnees.'; }}
function renderTables(data) {{
  writeTable('sessionTable', ['session','pivot','type','territoire','communes','CC','remplissage','temps max','temps moyen','PC','TPC','mixite','population','alertes'], summary.map(s=>[s.id_session,s.nom_pivot,s.type_session,s.territoire_majoritaire,s.nombre_communes,s.nombre_CC,s.taux_remplissage,s.temps_trajet_max,s.temps_trajet_moyen,s.nombre_PC,s.nombre_TPC,s.d_jm,`${{s.population_min}}-${{s.population_max}}`,s.alert_reasons.join('; ')]));
  writeTable('communeTable', ['commune','code','categorie','territoire','population','CC','session','pivot','temps','alertes'], data.map(p=>[p.nom_commune,p.code_commune,p.categorie,p.territoire_EAR,p.population,p.nombre_CC,p.id_session,p.nom_pivot,p.temps_trajet_minutes,p.alert_reasons.join('; ')]));
}}
function writeTable(id, headers, rows) {{ const table=document.getElementById(id); table.innerHTML='<thead><tr>'+headers.map(h=>`<th>${{h}}</th>`).join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+r.map(v=>`<td>${{v??''}}</td>`).join('')+'</tr>').join('')+'</tbody>'; [...table.querySelectorAll('th')].forEach((th,i)=>th.onclick=()=>{{ rows.sort((a,b)=>String(a[i]).localeCompare(String(b[i]), undefined, {{numeric:true}})); writeTable(id,headers,rows); }}); }}
function renderCharts() {{
  const charts = [
    ['Histogramme temps de trajet', histogram(points.map(p=>p.temps_trajet_minutes), 10)],
    ['Histogramme taux de remplissage', histogram(summary.map(s=>s.taux_remplissage), .2)],
    ['Sessions par territoire', countBars(summary.map(s=>s.territoire_majoritaire||'N/A'))],
    ['Top 10 temps max', bars(summary.slice().sort((a,b)=>b.temps_trajet_max-a.temps_trajet_max).slice(0,10), 'id_session', 'temps_trajet_max')],
    ['Top 10 moins remplies', bars(summary.slice().sort((a,b)=>a.taux_remplissage-b.taux_remplissage).slice(0,10), 'id_session', 'taux_remplissage')],
    ['Contribution objectif', bars([{{name:'trajet',v:globalStats.obj_trajet}},{{name:'eligibilite',v:globalStats.obj_eligibilite}},{{name:'mixite',v:globalStats.obj_mixite}}], 'name', 'v')]
  ];
  document.getElementById('charts').innerHTML = charts.map(([title,body])=>`<div class="chart"><h3>${{title}}</h3>${{body}}</div>`).join('');
}}
function bars(rows,labelKey,valueKey) {{ const max=Math.max(1,...rows.map(r=>Number(r[valueKey]))); return rows.map(r=>`<div class="bar"><span style="width:90px">${{r[labelKey]}}</span><i style="width:${{Math.max(2,Number(r[valueKey])/max*150)}}px"></i><span>${{r[valueKey]}}</span></div>`).join(''); }}
function countBars(values) {{ const c={{}}; values.forEach(v=>c[v]=(c[v]||0)+1); return bars(Object.entries(c).map(([name,v])=>({{name,v}})), 'name', 'v'); }}
function histogram(values, step) {{ if(!values.length) return 'Aucune donnee'; const max=Math.max(...values), bins={{}}; values.forEach(v=>{{ const k=Math.floor(v/step)*step; bins[k]=(bins[k]||0)+1; }}); return bars(Object.entries(bins).map(([name,v])=>({{name,v}})), 'name', 'v'); }}
document.getElementById('zoomIn').onclick=()=>{{state.zoom=Math.min(MAX_ZOOM, (state.zoom ?? MIN_ZOOM)+1); render();}}; document.getElementById('zoomOut').onclick=()=>{{state.zoom=Math.max(MIN_ZOOM, (state.zoom ?? MIN_ZOOM)-1); render();}}; document.getElementById('resetMap').onclick=()=>{{state={{zoom:null,initialZoom:null,center:null,initialCenter:null,tx:0,ty:0,selectedSession:null,dragging:false,last:null,tilesAttempted:0,tileErrors:0,tileLoaded:0,tileErrorMessage:''}}; render();}};
wrap.addEventListener('mousedown', e=>{{ state.dragging=true; state.last=[e.clientX,e.clientY]; }}); window.addEventListener('mouseup',()=>state.dragging=false); window.addEventListener('mousemove', e=>{{ if(!state.dragging) return; state.tx += e.clientX-state.last[0]; state.ty += e.clientY-state.last[1]; state.last=[e.clientX,e.clientY]; render(); }});
window.addEventListener('resize', () => {{ state.zoom=null; state.center=null; state.tx=0; state.ty=0; render(); }});
setupFilters(); renderChecks(); render(); renderCharts();
</script>
</body>
</html>
"""


def _read_csv_dicts(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise MapExportError(f"Export introuvable pour la carte: {path}.")
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise MapExportError(f"Export CSV vide ou sans en-tete: {path}.")
        return [dict(row) for row in reader]


def _read_json_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise MapExportError(f"Statistiques JSON introuvables pour la carte: {path}.")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise MapExportError(f"Le fichier de statistiques doit contenir un objet JSON: {path}.")
    return payload


def _to_number(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    return float(str(value).replace(",", "."))


def _to_int(value: Any) -> int:
    return int(round(_to_number(value)))


def _to_optional_int(value: Any) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    return _to_int(value)


def _json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")


def _assignment_alert_reasons(
    assignment: Any,
    commune: Commune,
    pivot: Commune,
    config: OptimizerConfig,
) -> str:
    reasons: list[str] = []
    if not _same_territory(commune, pivot):
        reasons.append("commune affectee a un pivot d'un territoire different")
    if assignment.temps_trajet_minutes / config.parameters.T >= config.exports["alerts"]["travel_close_ratio"]:
        reasons.append("temps de trajet proche de T")
    if assignment.categorie != assignment.type_session:
        reasons.append("categorie commune differente du type de session")
    return "; ".join(reasons)


def _split_reasons(value: str) -> list[str]:
    return [reason for reason in value.split("; ") if reason]


def _same_territory(commune: Commune, pivot: Commune) -> bool:
    if not commune.territory_ear or not pivot.territory_ear:
        return False
    return commune.territory_ear == pivot.territory_ear


def _level(reasons: list[str]) -> str:
    return "warning" if reasons else "ok"
