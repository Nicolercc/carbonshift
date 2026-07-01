# Handoff — MapLibre island integration (June 30 audit)

- main = Flask/Jinja/Leaflet, working, unaffected by any of this.
- nr/map-integration = Flask now serves a MapLibre React island at /map,
  fully wired: app.py reads the Vite manifest, bundle is built and committed
  to src/web/static/map/, /methodology route exists and works.
- Verified live: all routes return 200, no server errors, no regressions.
- Decision made: MapLibre replaces Leaflet on merge. Three.js was
  considered and rejected (MapLibre's WebGL extrusions already deliver the
  same visual result with a fraction of the engineering cost).
- Remaining before merge to main: update README.md tech-stack table and
  TEST_PLAN.md to describe the Vite build step and /methodology route.
- Deploy blocker to solve: data/carbonshift.db (186MB SQLite) is gitignored
  and not present on a fresh clone — needs a host with persistent
  disk/volume, not serverless.
