# CarbonShift — Backend Context

This document explains what the backend currently owns and what the frontend should rely on instead of reimplementing.

## Backend Role

The backend is the data platform.

It should continue to own:

- NYC Open Data ingestion
- ArcGIS building footprint ingestion
- Postgres/PostGIS storage
- Supabase connection handling
- Dataset normalization
- BIN/BBL/building joins
- Carbon estimates
- Risk scoring
- Data health checks
- JSON API contracts

The frontend should treat Flask as the source of truth for building intelligence.

## Current Backend Stack

```txt
Python
Flask
PostgreSQL
PostGIS
Supabase-compatible DATABASE_URL
psycopg2
NYC Open Data Socrata APIs
NYC ArcGIS building footprints
```

SQLite is no longer supported. Building footprints require PostGIS.

## Core Tables

The backend contains roughly these product areas:

- `building_crosswalk`: BIN/BBL/base BBL relationship
- `buildings`: identity, address, location
- `building_profiles`: PLUTO-derived building attributes
- `building_violations`: unified HPD/DOB/DOB legacy/ECB violations
- `asbestos_projects`: ACP-7 asbestos project notifications
- `energy_emissions`: LL84/LL97 measured energy/emissions rows
- `carbon_estimates`: estimated or measured carbon signal per building
- `building_risk_scores`: generated risk score, label, confidence, and detail
- `building_footprints`: PostGIS building footprint geometry

The frontend should not expose these as separate product concepts. The frontend should consume product-shaped API responses.

## Product Concepts The Frontend Should Use

Frontend-facing concepts:

- Building identity
- Map geometry
- Risk score
- Carbon signal
- Compliance signal
- Asbestos signal
- Data completeness
- Summary stats
- Data health

## Existing Query Layer

Shared query logic lives in:

```txt
src/query/lookup.py
```

Important functions:

- `search_buildings`
- `get_building`
- `get_violations`
- `get_energy`
- `get_asbestos`
- `stats_summary`
- `carbon_source_counts`
- `data_health_summary`
- `buildings_geojson`

Flask routes live in:

```txt
src/web/app.py
```

## API-Only Direction

Flask does not need to disappear. It should become API-first while still serving the existing Flask/Jinja pages during the transition.

The current browser pages can remain useful:

- `/`
- `/search`
- `/building/<bin>`
- `/charts`
- `/methodology`
- `/map`
- `/query`

The new frontend should use:

- `/api/health`
- `/api/stats/summary`
- `/api/data-health`
- `/api/buildings/search`
- `/api/buildings/<bin>`
- `/api/buildings.geojson`

## What Not To Rebuild In The Frontend

Do not rebuild:

- Risk scoring
- Carbon estimation
- Cross-table joins
- PostGIS geometry selection
- Violation aggregation
- Asbestos keyword logic
- Data health checks

If the frontend needs a new product concept, add or adjust a Flask API endpoint rather than duplicating backend logic in React.

## Known Backend Gaps

- Manhattan energy/emissions ingestion is not complete yet.
- Some page copy and map defaults may still be Queens-first.
- `.env.example` may still contain SQLite-era language and should be updated before a polished handoff.
- API contracts are now documented, but frontend Zod schemas still need to be created in the Next.js app.

## Operating Principle

Keep backend complexity behind a small API.

The frontend should never need to know all 10 tables to render the product.

