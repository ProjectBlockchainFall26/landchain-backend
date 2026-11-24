"""Geometry (task C6, spec 6.4 and 9.5): area in acres, plots, Ghana box, overlap and duplicate checks.

The area uses the frontend's formula (geo.ts areaAcres): shoelace area on a local projection around Berekuso,
so the area shown before submitting equals the acresX100 stored on chain. Overlap uses PostGIS with touching
edges allowed (ST_Intersects AND NOT ST_Touches), as in the frontend's strict segment test.
"""
from __future__ import annotations

import json
import math
from decimal import ROUND_HALF_UP, Decimal

from django.db import connection

from landchain.chain.encoding import MAX_LAT, MAX_LNG, MAX_PILLARS, MIN_LAT, MIN_LNG, MIN_PILLARS, to_micro

ORIGIN = (5.7505, -0.2275)  # Berekuso, Eastern Region
M_PER_DEG_LAT = 110540
SQM_PER_ACRE = 4046.8564
SQM_PER_PLOT = 100 * 70 * 0.092903          # a 100 x 70 ft plot


def _m_per_deg_lng(lat: float) -> float:
    return 111320 * math.cos(lat * math.pi / 180)


def project(lat: float, lng: float) -> tuple[float, float]:
    return (lng - ORIGIN[1]) * _m_per_deg_lng(ORIGIN[0]), -(lat - ORIGIN[0]) * M_PER_DEG_LAT


def area_acres(pillars) -> float:
    if len(pillars) < 3:
        return 0.0
    p = [project(a, b) for a, b in pillars]
    s = 0.0
    for i in range(len(p)):
        x1, y1 = p[i]
        x2, y2 = p[(i + 1) % len(p)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2 / SQM_PER_ACRE


def js_round(x: float) -> int:
    """JavaScript Math.round (halves round up)."""
    return math.floor(x + 0.5)


def acres_x100(pillars) -> int:
    return max(1, js_round(area_acres(pillars) * 100))


def plots(acres: float) -> str:
    v = Decimal(str(acres / (SQM_PER_PLOT / SQM_PER_ACRE))).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return f"{v}"


def inside_ghana(lat: float, lng: float) -> bool:
    return MIN_LAT <= to_micro(lat) <= MAX_LAT and MIN_LNG <= to_micro(lng) <= MAX_LNG


def geojson_polygon(pillars) -> str:
    ring = [[float(b), float(a)] for a, b in pillars]
    ring.append(ring[0])
    return json.dumps({"type": "Polygon", "coordinates": [ring]})


def overlapping_parcel(pillars, ignore_parcel_id: str | None = None) -> str | None:
    """Parcel ID of a current, non-rejected parcel whose boundary overlaps (touching edges allowed)."""
    if len(pillars) < 3:
        return None
    gj = geojson_polygon(pillars)
    sql = ("SELECT parcel_id FROM parcel WHERE is_current AND status <> 3 AND boundary IS NOT NULL "
           "AND ST_Intersects(boundary, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)) "
           "AND NOT ST_Touches(boundary, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))")
    params = [gj, gj]
    if ignore_parcel_id:
        sql += " AND parcel_id <> %s"
        params.append(ignore_parcel_id.upper())
    sql += " ORDER BY parcel_id LIMIT 1"
    try:
        with connection.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
    except Exception:  # invalid (self-intersecting) polygon: GEOS refuses; treat as no overlap found
        return None
    return row[0] if row else None


def duplicate_boundary(pillars, ignore_parcel_id: str | None = None) -> bool:
    from .models import Parcel
    lats = [to_micro(a) for a, _ in pillars]
    lngs = [to_micro(b) for _, b in pillars]
    qs = Parcel.objects.filter(lats_micro=lats, lngs_micro=lngs).exclude(status=3)
    if ignore_parcel_id:
        qs = qs.exclude(parcel_id=ignore_parcel_id.upper())
    return qs.exists()


def check_boundary(pillars, ignore_parcel_id: str | None = None) -> dict:
    """Body of POST /parcels/boundary-check."""
    pillars = [[float(a), float(b)] for a, b in pillars]
    acres = area_acres(pillars)
    ax100 = acres_x100(pillars) if len(pillars) >= 3 else 0
    inside = all(inside_ghana(a, b) for a, b in pillars) if pillars else False
    out = {"ok": False, "acres": f"{Decimal(ax100) / 100:.2f}", "acres_x100": ax100, "plots_100x70ft": plots(acres),
           "pillar_count": len(pillars), "inside_ghana": inside, "overlaps": None, "duplicate_boundary": False,
           "error": None}
    if len(pillars) < MIN_PILLARS:
        out["error"] = "A boundary needs at least 3 corner pillars"
        return out
    if len(pillars) > MAX_PILLARS:
        out["error"] = "A boundary can have at most 32 corner pillars"
        return out
    if not inside:
        out["error"] = "All pillars must be inside Ghana"
        return out
    out["duplicate_boundary"] = duplicate_boundary(pillars, ignore_parcel_id)
    if out["duplicate_boundary"]:
        out["error"] = "This boundary is already registered"
        return out
    out["overlaps"] = overlapping_parcel(pillars, ignore_parcel_id)
    if out["overlaps"]:
        out["error"] = f"Boundary overlaps neighbouring parcel {out['overlaps']}"
        return out
    out["ok"] = True
    return out


def centroid(pillars) -> list[float]:
    n = len(pillars) or 1
    return [round(sum(p[0] for p in pillars) / n, 6), round(sum(p[1] for p in pillars) / n, 6)]
