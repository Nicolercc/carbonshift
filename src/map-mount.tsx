import { StrictMode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { CarbonMap } from "./components/map";
import type { MapInitConfig } from "./components/map/mapTypes";
import "./map-island.css";

declare global {
  interface Window {
    __MAP_INIT__?: MapInitConfig;
  }
}

let root: Root | null = null;

/** Mount the MapLibre island into a Flask-provided container. */
export function mountCarbonMap(
  container: HTMLElement,
  init?: MapInitConfig,
): void {
  if (init) {
    window.__MAP_INIT__ = { ...window.__MAP_INIT__, ...init };
  }

  container.classList.add("carbon-map-island");

  if (!root) {
    root = createRoot(container);
  }

  root.render(
    <StrictMode>
      <CarbonMap />
    </StrictMode>,
  );
}

const flaskRoot = document.getElementById("carbon-map-root");
if (flaskRoot) {
  mountCarbonMap(flaskRoot);
}
