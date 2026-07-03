# CarbonShift — API Contracts

This document defines the Flask JSON API surface that a separate Next.js frontend should consume.

Flask remains the data API. The frontend should call product-shaped endpoints instead of querying raw tables.

## Local Base URL

```bash
http://127.0.0.1:5050
```

## CORS

For local development, Flask allows common frontend dev origins:

```txt
http://localhost:3000
http://127.0.0.1:3000
http://localhost:5173
http://127.0.0.1:5173
```

For deployed frontend origins, set:

```bash
CORS_ALLOWED_ORIGINS=https://your-frontend.vercel.app,https://your-replit-domain.replit.app
```

Do not use wildcard CORS in production.

## Endpoint Summary

```txt
GET /api/health
GET /api/stats
GET /api/stats/summary
GET /api/data-health
GET /api/buildings/search?q=&limit=&zip=&class=&year_min=&year_max=&risk=&asbestos=1
GET /api/buildings/<bin>?limit=
GET /api/buildings.geojson?q=&limit=&zip=&class=&year_min=&year_max=&risk=&asbestos=1
```

## GET /api/health

Purpose:

Check whether Flask can boot and reach the database.

Example:

```bash
curl http://127.0.0.1:5050/api/health
```

Success response:

```json
{
  "ok": true,
  "service": "carbonshift-api",
  "database": "ok"
}
```

Failure response:

```json
{
  "ok": false,
  "service": "carbonshift-api",
  "database": "unavailable",
  "error": "..."
}
```

## GET /api/stats/summary

Purpose:

Return compact metrics for dashboard headers, map summary strips, and data source confidence UI.

Example:

```bash
curl http://127.0.0.1:5050/api/stats/summary
```

Response shape:

```json
{
  "stats": {
    "buildings": 0,
    "crosswalk": 0,
    "violations": 0,
    "asbestos_violations": 0,
    "asbestos_projects": 0,
    "energy_rows": 0,
    "buildings_with_energy": 0,
    "carbon_estimates": 0,
    "risk_scored": 0,
    "high_risk": 0
  },
  "carbon_sources": {
    "measured": 0,
    "class_median": 0,
    "borough_median": 0,
    "total": 0
  }
}
```

`GET /api/stats` is an alias.

## GET /api/data-health

Purpose:

Return table counts and map-readiness checks for internal/debug UI.

Example:

```bash
curl http://127.0.0.1:5050/api/data-health
```

Response shape:

```json
{
  "tables": {
    "building_crosswalk": 0,
    "buildings": 0,
    "building_profiles": 0,
    "building_violations": 0,
    "asbestos_projects": 0,
    "energy_emissions": 0,
    "carbon_estimates": 0,
    "building_risk_scores": 0,
    "building_footprints": 0
  },
  "map_readiness": {
    "buildings_with_coordinates": 0,
    "buildings_with_footprints": 0,
    "buildings_with_scores": 0,
    "buildings_with_carbon_estimates": 0
  },
  "known_gaps": []
}
```

If a table is missing, its count may be `null`.

## GET /api/buildings/search

Purpose:

Return search results for the global search box.

Query params:

| Param | Meaning |
|---|---|
| `q` | Address text, BIN, BBL, ZIP, or partial address |
| `limit` | Max results, capped at 100 |
| `zip` | Exact ZIP filter |
| `class` | Building class prefix |
| `year_min` | Minimum year built |
| `year_max` | Maximum year built |
| `risk` | Risk label |
| `asbestos=1` | Only records with asbestos-related violation signal |
| `violations=1` | Only records with violations |
| `energy=1` | Only records with measured energy rows |

Example:

```bash
curl "http://127.0.0.1:5050/api/buildings/search?q=Queens&limit=10"
```

Response shape:

```json
{
  "query": "Queens",
  "filters": {},
  "count": 10,
  "limit": 10,
  "results": [
    {
      "bin": "4000000",
      "bbl": "4000000000",
      "full_address": "...",
      "zip_code": "11101",
      "borough": "Queens",
      "latitude": 40.0,
      "longitude": -73.0,
      "year_built": 1970,
      "building_class": "D1",
      "building_area": 100000,
      "violation_count": 3,
      "asbestos_count": 1,
      "latest_ghg": 200.5,
      "risk_score": 10,
      "risk_label": "High",
      "estimated_ghg_metric_tons": 210.2,
      "eui_source": "class_median"
    }
  ]
}
```

## GET /api/buildings/<bin>

Purpose:

Return one product-shaped building detail payload for the side panel.

Query params:

| Param | Meaning |
|---|---|
| `limit` | Max violation/asbestos records returned, default 50, capped at 200 |

Example:

```bash
curl "http://127.0.0.1:5050/api/buildings/4012345?limit=25"
```

Response shape:

```json
{
  "building": {
    "bin": "4012345",
    "bbl": "...",
    "full_address": "...",
    "zip_code": "...",
    "latitude": 40.0,
    "longitude": -73.0,
    "year_built": 1930,
    "building_class": "C1",
    "building_area": 50000,
    "risk_score": 12,
    "risk_label": "High",
    "confidence_label": "High",
    "risk_detail": "...",
    "estimated_ghg_metric_tons": 300.1,
    "eui_source": "class_median"
  },
  "signals": {
    "risk": {
      "score": 12,
      "label": "High",
      "confidence": "High",
      "drivers": []
    },
    "carbon": {
      "estimated_ghg_metric_tons": 300.1,
      "eui_source": "class_median",
      "site_eui": null,
      "peer_building_count": 80
    },
    "compliance": {
      "violation_count_returned": 25,
      "asbestos_related_violation_count_returned": 1
    },
    "asbestos": {
      "project_count_returned": 1,
      "has_asbestos_signal": true
    },
    "data_completeness": {
      "has_location": true,
      "has_profile": true,
      "has_risk_score": true,
      "has_carbon_estimate": true
    }
  },
  "records": {
    "violations": [],
    "energy": [],
    "asbestos": []
  },
  "record_limit": 25
}
```

## GET /api/buildings.geojson

Purpose:

Return map-ready GeoJSON with building footprints or fallback points.

Query params:

| Param | Meaning |
|---|---|
| `q` | Address, BIN, BBL, ZIP, or partial address |
| `limit` | Max features, capped at 10,000 |
| `zip` | Exact ZIP filter |
| `class` | Building class prefix |
| `year_min` | Minimum year built |
| `year_max` | Maximum year built |
| `risk` | Risk label |
| `asbestos=1` | Only records with asbestos-related violation signal |

Example:

```bash
curl "http://127.0.0.1:5050/api/buildings.geojson?limit=100&risk=High"
```

Response shape:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Polygon",
        "coordinates": []
      },
      "properties": {
        "bin": "4012345",
        "address": "...",
        "zip": "11101",
        "year_built": 1930,
        "building_class": "C1",
        "building_area": 50000,
        "risk_score": 12,
        "risk_label": "High",
        "ghg": 300.1,
        "ghg_source": "class_median",
        "violations": 4,
        "asbestos": 1
      }
    }
  ]
}
```

## Frontend Consumption Guidance

The frontend should create a small API adapter:

```txt
src/lib/api/carbonshift.ts
```

Recommended adapter functions:

```ts
getHealth()
getStatsSummary()
getDataHealth()
searchBuildings(params)
getBuildingDetail(bin, options)
getBuildingGeoJSON(params)
```

Validate responses with Zod at the API boundary before rendering.

