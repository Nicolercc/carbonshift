# CarbonShift — Frontend Implementation Plan

This plan defines what gets built now, what gets handed off, how long each phase should take, and which commands should be used to verify work.

## Guiding Decision

Flask is not being replaced.

Flask becomes the data API. The Next.js frontend becomes the presentation layer.

```txt
Next.js frontend
  -> Flask JSON API
    -> Postgres/PostGIS/Supabase
```

This keeps the hard backend work intact while creating room for a modern map-first frontend.

## Current Build Scope

Build now:

- Phase 0 docs foundation
- Phase 1 Flask API readiness
- API contracts for the future Next.js frontend
- Clear commands and acceptance criteria

Hand off next:

- Phase 2 Next.js foundation
- Phase 3 map-first shell
- Phase 4 four-signal building panel
- Phase 5 visualization and polish
- Phase 6 production hardening

## Phase 0: Handoff + Docs Foundation

Time: 2-4 hours

Owner: current setup work

Goal:

Make the project understandable before more code is added.

Deliverables:

- `docs/README.md`
- `docs/product-direction.md`
- `docs/frontend-implementation-plan.md`
- `docs/api-contracts.md`
- `docs/backend-context.md`
- `CLAUDE.md` points future LLM agents toward the docs

Acceptance criteria:

- A new contributor can find the product direction in under 30 seconds.
- The MVP is described as a map-first building risk explorer.
- The backend/frontend split is explicit.
- Phase durations, commands, and acceptance criteria are documented.

## Phase 1: Flask API Readiness

Time: 4-8 hours

Owner: current setup work, with remaining endpoint refinements shared as needed

Goal:

Make Flask ready to serve a separate frontend without breaking the existing Flask/Jinja app.

Built in this phase:

- Environment-driven CORS
- Health endpoint
- Stats endpoint
- Data health endpoint
- Search endpoint
- Building detail endpoint
- Existing GeoJSON endpoint kept stable
- API contracts documented

API endpoints:

```txt
GET /api/health
GET /api/stats
GET /api/stats/summary
GET /api/data-health
GET /api/buildings/search
GET /api/buildings/<bin>
GET /api/buildings.geojson
```

Acceptance criteria:

- Existing Flask pages still work.
- `/api/buildings.geojson` still returns a GeoJSON FeatureCollection.
- `/api/buildings/search` returns JSON search results.
- `/api/buildings/<bin>` returns a product-shaped detail payload.
- `/api/stats/summary` returns compact summary metrics.
- `/api/data-health` returns table/readiness counts.
- CORS allows local Next.js/Vite dev origins by default and production origins through `CORS_ALLOWED_ORIGINS`.

Verification commands:

```bash
# From repo root
source venv/bin/activate
python web.py --debug
```

In another terminal:

```bash
curl http://127.0.0.1:5050/api/health
curl http://127.0.0.1:5050/api/stats/summary
curl http://127.0.0.1:5050/api/data-health
curl "http://127.0.0.1:5050/api/buildings/search?q=Queens&limit=5"
curl "http://127.0.0.1:5050/api/buildings.geojson?limit=5"
```

To test a real building detail endpoint:

```bash
curl "http://127.0.0.1:5050/api/buildings.geojson?limit=1"
```

Copy one `properties.bin` from the response:

```bash
curl "http://127.0.0.1:5050/api/buildings/<BIN_FROM_RESPONSE>?limit=25"
```

CORS smoke check:

```bash
curl -i \
  -H "Origin: http://localhost:3000" \
  http://127.0.0.1:5050/api/health
```

Expected:

```txt
Access-Control-Allow-Origin: http://localhost:3000
```

Production CORS setup:

```bash
CORS_ALLOWED_ORIGINS=https://your-frontend.vercel.app,https://your-replit-domain.replit.app
```

## Phase 2: Next.js Frontend Foundation

Time: 0.5-1.5 days

Owner: frontend continuation

Goal:

Create the modern frontend shell without trying to finish the whole app.

Recommended create command:

```bash
npx create-next-app@latest frontend \
  --ts \
  --tailwind \
  --eslint \
  --app \
  --src-dir \
  --import-alias "@/*"
```

Install app dependencies:

```bash
cd frontend
npm install maplibre-gl @tanstack/react-query zod lucide-react recharts
npx shadcn@latest init
```

Recommended shadcn components:

```bash
npx shadcn@latest add button input badge card separator sheet tabs tooltip select slider checkbox skeleton alert scroll-area
```

Required scripts:

```json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "lint": "next lint",
    "typecheck": "tsc --noEmit",
    "test": "vitest",
    "test:e2e": "playwright test"
  }
}
```

Environment variables:

```bash
NEXT_PUBLIC_CARBONSHIFT_API_BASE=http://127.0.0.1:5050
```

Recommended frontend structure:

```txt
frontend/
  src/
    app/
      page.tsx
      methodology/page.tsx
      data-health/page.tsx
    components/
      app-shell/
      map/
      building-detail/
      filters/
      metrics/
    lib/
      api/
        carbonshift.ts
        schemas.ts
      map/
      formatters/
    types/
      carbonshift.ts
```

Acceptance criteria:

- Next.js app starts locally.
- App shell renders.
- API base URL is environment-driven.
- TypeScript types exist for API responses.
- API adapter can call `/api/health` and `/api/stats/summary`.
- Mock data is isolated and easy to delete.

Verification commands:

```bash
cd frontend
npm run typecheck
npm run lint
npm run build
npm run dev
```

## Phase 3: Map-First Product Shell

Time: 1-2 days

Owner: frontend continuation

Goal:

Make the map the first screen and the dominant product surface.

Build:

- Full-screen app shell
- Map area using MapLibre
- Risk legend
- Compact metric strip
- Search input
- Filter controls
- Hover tooltip
- Selected-building state
- Empty/loading/error states

Reuse from current Flask island where possible:

```txt
src/components/map/CarbonMap.tsx
src/components/map/buildingDataAdapter.ts
src/components/map/mapTypes.ts
src/components/map/mapConfig.ts
src/components/map/mapLayers.ts
src/components/map/MapLegend.tsx
src/components/map/MapSearch.tsx
```

Acceptance criteria:

- First viewport is a usable product, not a landing page.
- Map consumes `/api/buildings.geojson`.
- Search can select or focus a building.
- Selected building is visually highlighted.
- Filters update the visible map data.

## Phase 4: Building Detail / Four-Signal Panel

Time: 1-2 days

Owner: frontend continuation

Goal:

Turn a clicked building into a clear, compact explanation.

Panel sections:

- Identity: address, BIN, BBL, borough/ZIP
- Risk: score, label, confidence, drivers
- Carbon: estimate, source, peer count
- Compliance: violation count and recent evidence
- Asbestos: project/violation signal
- Data completeness: which inputs exist or are missing

API:

```txt
GET /api/buildings/<bin>?limit=50
```

Acceptance criteria:

- Panel opens from map click or search selection.
- Four signals are visible without scrolling on normal laptop viewports.
- Raw records are secondary.
- Missing data is displayed gracefully.
- User can open the existing full Flask detail page for deeper inspection if needed.

## Phase 5: Data Visualization + Polish

Time: 2-4 days

Owner: frontend continuation

Goal:

Make the product feel like serious civic/climate intelligence, not a generic dashboard.

Build:

- Risk distribution visual
- Carbon source confidence visual
- Borough or viewport summary
- Data completeness indicator
- Filter chips
- Better empty states
- Error recovery states
- Responsive layout

Acceptance criteria:

- Main product surfaces are visual-first.
- Long explanatory copy is moved to Methodology.
- No component exposes raw table complexity.
- UI remains readable on laptop and desktop.
- Mobile/tablet fallback is usable even if desktop remains primary.

## Phase 6: Production Hardening

Time: 1-2 days

Owner: shared

Goal:

Make the MVP deployable and debuggable.

Build:

- Production env var docs
- CORS origin config
- Error boundaries
- API timeout behavior
- Smoke tests
- Build checks
- Deployment notes

Minimum checks:

```bash
# Flask
python -m compileall src
python web.py --debug

# Frontend
cd frontend
npm run typecheck
npm run lint
npm run build
npm run test:e2e
```

Acceptance criteria:

- Flask deploy can serve API.
- Frontend deploy can call Flask.
- CORS is restricted to known frontend origins.
- Core map/search/detail flow passes smoke tests.
- Docs explain how to run and debug both services.

## Handoff Notes

What is ready now:

- Flask remains the backend foundation.
- API contracts exist.
- CORS strategy exists.
- Product direction is written down.
- Frontend stack recommendation is explicit.

What should happen next:

1. Verify Phase 1 endpoints locally against the real database.
2. Create or update the Next.js frontend.
3. Port the existing MapLibre map logic.
4. Build the four-signal detail panel against real API responses.
5. Move methodology and raw evidence into secondary views.

