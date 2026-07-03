# CarbonShift — Product, Data, and Frontend Direction

A shared source of truth for the CarbonShift MVP, user experience, data model, frontend redesign, and implementation priorities.

CarbonShift should become a visual-first civic climate intelligence tool.

The app has enough backend data now that the frontend should stop behaving like a text-heavy project demo. The next version should make the map the center of the experience, compress backend complexity into clear visual signals, and help users understand building risk without needing to understand the database.

The main idea is simple:

> Bigger map. Less text. More visual explanation.

The user should never feel like they are navigating 10 backend tables. The user should feel like they are exploring a city map where building risk, supporting evidence, and next-best areas to inspect are obvious.

## 1. Current Product Direction

CarbonShift turns fragmented NYC public records into building-level risk intelligence.

The current backend already supports a serious product direction:

- Building identity and location
- Building profiles
- Building footprints
- Housing and building violations
- Asbestos-related signals
- Energy/emissions records
- Carbon estimates
- Risk scoring
- Summary stats
- Map-ready GeoJSON

The frontend should translate that backend complexity into a calm, visual, map-first experience.

## 2. MVP Definition

The MVP is a map-first building risk explorer.

The MVP should let a user answer five questions quickly:

1. Where is building risk concentrated?
2. Which buildings are highest priority?
3. Why is a selected building risky?
4. What evidence supports the score?
5. What should be inspected next?

The MVP should not try to expose every table, every raw field, or every methodology detail in the primary view. Those things can exist, but the main experience should be product-shaped.

## 3. Recommended Frontend Stack

Recommended stack:

```txt
Next.js App Router
React
TypeScript
Tailwind CSS
shadcn/ui
lucide-react
MapLibre GL JS
TanStack Query
Zod
Recharts or visx
Playwright
Vitest
```

Why this stack:

- Next.js gives a modern app foundation, routing, layouts, and Vercel deployment.
- TypeScript keeps API contracts and map data safer.
- Tailwind and shadcn/ui make it possible to move fast while keeping UI quality high.
- MapLibre matches the existing map direction and avoids unnecessary vendor lock-in.
- TanStack Query should own frontend server-state: loading, caching, refetching, retries, and stale data.
- Zod should validate API responses at the boundary so backend/frontend contract drift is caught early.
- Playwright should cover the core map/search/detail flow.

Avoid for the MVP:

- Redux
- GraphQL
- A custom map renderer
- A separate design system package
- Exposing raw tables directly to the frontend

## 4. Target Architecture

The architecture should be a clean frontend/backend split:

```txt
User
  -> Next.js frontend
    -> Flask JSON API
      -> Postgres/PostGIS/Supabase
```

Flask remains the data API. Next.js becomes the product UI.

Flask owns:

- Ingestion
- Scoring
- Database access
- PostGIS queries
- Map GeoJSON
- Building detail data
- Search
- Stats
- Data health

Next.js owns:

- Product shell
- Map-first layout
- Filters
- Building detail panel
- Visual risk explanation
- Frontend state
- Loading, empty, and error states
- Methodology and data-health UI

## 5. Target User Experience

The first screen should open directly into the product.

No giant hero. No "learn more" path before the useful interface. No wall of explanatory text.

The first viewport should include:

- Large NYC map
- Risk-colored buildings or clusters
- Search by address, BIN, BBL, or location text
- Compact summary metrics
- Filters
- Legend
- Building detail panel state

The map should feel like the center of gravity.

## 6. Core User Flow

1. User opens CarbonShift.
2. User sees NYC building risk distribution immediately.
3. User filters by borough, risk, violations, asbestos signal, carbon estimate band, or data completeness.
4. User clicks or searches for a building.
5. A side panel explains the selected building through four signals.
6. User compares the selected building to nearby or borough-level context.
7. User understands what deserves attention next.

## 7. Data Complexity: How To Make 10 Tables Understandable

The frontend should not model the backend as 10 separate tables.

Frontend mental model:

- Building identity
- Geometry and map footprint
- Risk score
- Carbon signal
- Compliance/violation signal
- Asbestos signal
- Data completeness
- Derived summaries

The frontend should consume product-shaped API responses:

- `BuildingMapFeature`
- `BuildingSearchResult`
- `BuildingDetail`
- `RiskSummary`
- `DataHealthStatus`

Raw schema complexity should stay behind Flask.

## 8. Frontend Redesign Principles

- The map is the product surface.
- Text explains only what visuals cannot.
- Risk should be visible before it is explained.
- Every page should have one clear job.
- Detail should be progressive: summary first, evidence next, raw records last.
- Empty and missing data states are first-class product states.
- If a component does not help users explore, compare, or understand building risk, question whether it belongs in the MVP.

## 9. Map-First Experience

The Map Explorer should include:

- Full-height map area
- Persistent risk legend
- Search
- Filter controls
- Visible result count
- Selected-building highlight
- Hover tooltip
- Click-to-open detail panel
- Loading, empty, and error states

Risk colors:

- Low: green
- Moderate: amber
- Elevated: orange
- High/Critical: red
- Unknown or incomplete: gray

## 10. Building Detail Experience

The building detail panel should explain one selected building through four signals:

1. Carbon signal
2. Compliance/violation signal
3. Asbestos signal
4. Data completeness/confidence signal

The panel should show:

- Address or building identifier
- BIN and BBL
- Risk score and label
- Top risk drivers
- Estimated carbon signal
- Violation count and recent evidence
- Asbestos signal
- Data completeness
- Link to the existing full Flask building page if deeper raw records are needed

The panel should not dump raw database fields into the primary UI.

## 11. Data Visualization Requirements

The frontend should use compact visual components:

- Risk legend
- Risk distribution bar
- Metric strip
- Signal chips
- Mini trend charts
- Evidence list
- Comparison cards
- Data completeness indicator

The visual system should make high-risk buildings easy to scan without forcing the user to read methodology first.

## 12. Backend Context The Frontend Should Know

The backend currently supports:

- Postgres/PostGIS through `DATABASE_URL`
- Map-ready GeoJSON from `/api/buildings.geojson`
- Search/detail query logic in `src/query/lookup.py`
- Scoring output in `building_risk_scores`
- Carbon estimate output in `carbon_estimates`
- Building footprint geometry through PostGIS

The backend should continue to own:

- Joins across raw tables
- Scoring logic
- Dataset ingestion
- Data normalization
- Data-health checks

The frontend should not reimplement scoring or raw joins.

## 13. API Contracts Needed From Flask

Phase 1 exposes the API surface the Next.js app needs:

- `GET /api/health`
- `GET /api/stats/summary`
- `GET /api/data-health`
- `GET /api/buildings/search`
- `GET /api/buildings/<bin>`
- `GET /api/buildings.geojson`

See [API Contracts](api-contracts.md) for request and response details.

## 14. Frontend Implementation Priorities

### Phase 0: Handoff + Docs Foundation

Time: 2-4 hours

Outcome:

- Shared docs exist.
- Product direction is explicit.
- Backend/frontend split is clear.
- Phase plan is documented.
- LLM agents know where to start.

### Phase 1: Flask API Readiness

Time: 4-8 hours

Outcome:

- Flask exposes stable JSON endpoints for the Next.js frontend.
- CORS is environment-driven.
- Existing Flask/Jinja pages remain intact.
- API contracts are documented.
- The frontend has real endpoints to call.

### Phase 2: Next.js Frontend Foundation

Time: 0.5-1.5 days

Outcome:

- Next.js app exists.
- App shell, routes, types, mock data, and API adapter exist.
- The frontend can call Flask locally.
- The first screen is prepared for the map-first product.

### Phase 3: Map-First Product Shell

Time: 1-2 days

Outcome:

- Map is the primary surface.
- Existing MapLibre logic is ported or reused.
- Filters, legend, tooltip, selected state, and search are wired.

### Phase 4: Building Detail / Four-Signal Panel

Time: 1-2 days

Outcome:

- Selected-building panel explains carbon, compliance, asbestos, and data completeness.
- Panel uses the Flask building detail API.
- Raw records stay secondary.

### Phase 5: Data Visualization + Polish

Time: 2-4 days

Outcome:

- Text-heavy product areas become visual.
- Summary metrics, risk distribution, comparison blocks, and evidence states feel coherent.
- Responsive and accessibility behavior is acceptable for MVP.

### Phase 6: Production Hardening

Time: 1-2 days

Outcome:

- Build passes.
- Smoke tests pass.
- API errors are handled.
- Deployment environment variables are documented.
- Render/Vercel or equivalent deploy path is clear.

## 15. Acceptance Criteria

MVP acceptance criteria:

- Opening the app shows the map-first product surface.
- Search returns real buildings.
- Clicking a building opens a detail panel.
- Risk drivers are understandable without reading raw tables.
- Missing data does not break the UI.
- Flask remains the source of truth for data.
- Next.js frontend does not perform raw backend joins.
- API contracts are documented and stable enough for frontend work.

## 16. Shared Open Questions

- Should the initial map open to all supported boroughs or a bounded NYC viewport?
- Should risk labels stay `Low`, `Moderate`, `High`, `Critical`, or become `Low`, `Moderate`, `Elevated`, `High`?
- Should the frontend call Flask directly with CORS or through a Next.js proxy route?
- Which deployment should be canonical for the MVP: Replit, Vercel, Render, or a split Render/Vercel deployment?
- What level of raw evidence should be visible in the primary detail panel?

## 17. Document Directory

Use [docs/README.md](README.md) as the docs directory.

Core docs:

- [Product, Data, and Frontend Direction](product-direction.md)
- [Frontend Implementation Plan](frontend-implementation-plan.md)
- [API Contracts](api-contracts.md)
- [Backend Context](backend-context.md)

