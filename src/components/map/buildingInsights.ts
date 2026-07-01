import type { BackendRiskLabel } from "./mapConfig";

const VALID_RISK_LABELS = new Set<string>([
  "Low",
  "Moderate",
  "High",
  "Critical",
  "Unscored",
]);

export function normalizeRiskLabel(label: string | null | undefined): BackendRiskLabel {
  if (label && VALID_RISK_LABELS.has(label)) {
    return label as BackendRiskLabel;
  }
  return "Unscored";
}

export function riskHeadline(risk: BackendRiskLabel): string {
  switch (risk) {
    case "Critical":
      return "Critical building signal";
    case "High":
      return "High building signal";
    case "Moderate":
      return "Moderate building signal";
    case "Low":
      return "Lower building signal";
    default:
      return "Insufficient scoring data";
  }
}

export function ghgConfidenceLabel(source: string): string {
  if (source === "measured") return "Measured LL84/97";
  if (source === "class_median") return "Similar buildings (class median)";
  if (source === "borough_median") return "Borough fallback";
  if (!source) return "Not available";
  return "Modeled estimate";
}

export function ghgConfidenceDetail(source: string): string {
  if (source === "measured") {
    return "Actual LL84/97 disclosure on file — treat as measured emissions.";
  }
  if (source === "class_median") {
    return "Modeled from peer buildings with the same PLUTO class — medium confidence.";
  }
  if (source === "borough_median") {
    return "Modeled from a Queens-wide median — lower confidence than class peers.";
  }
  if (!source) {
    return "No emissions source on record for this building.";
  }
  return "Modeled estimate — confirm source before capital planning.";
}

export function ghgConfidenceTier(source: string): "high" | "medium" | "low" | "none" {
  if (source === "measured") return "high";
  if (source === "class_median") return "medium";
  if (source === "borough_median") return "low";
  return "none";
}

export function derivePrimaryDriver(props: {
  risk_score: number | null;
  risk_label: BackendRiskLabel;
  year_built: number | null;
  building_class: string;
  ghg: number | null;
  violations: number;
  asbestos: number;
}): string {
  const drivers: string[] = [];

  if (props.asbestos > 0) {
    drivers.push(
      `${props.asbestos} asbestos-related violation${props.asbestos === 1 ? "" : "s"}`,
    );
  }

  if (props.violations >= 10) {
    drivers.push(`${props.violations} total violations on record`);
  } else if (props.violations > 0) {
    drivers.push(`${props.violations} open violation${props.violations === 1 ? "" : "s"}`);
  }

  if (props.ghg != null && props.ghg >= 1000) {
    drivers.push(
      `Elevated estimated emissions (${props.ghg.toLocaleString()} mt CO₂e/yr)`,
    );
  }

  if (props.year_built != null && props.year_built < 1940) {
    drivers.push(`Pre-war building stock (${props.year_built})`);
  } else if (props.year_built != null && props.year_built < 1978) {
    drivers.push(`Legacy building systems (${props.year_built})`);
  }

  if (props.building_class) {
    drivers.push(`Class ${props.building_class} use profile`);
  }

  if (props.risk_score != null && props.risk_score >= 19) {
    drivers.push(`Risk score ${props.risk_score} — critical threshold`);
  }

  if (drivers.length === 0) {
    if (props.risk_label === "Unscored") {
      return "Building lacks sufficient scoring inputs for a confident assessment.";
    }
    return "No single dominant driver — composite building profile factors.";
  }

  return drivers.slice(0, 3).join(" · ");
}

export function deriveSuggestedAction(props: {
  risk_label: BackendRiskLabel;
  ghg_source: string;
  asbestos: number;
  violations: number;
  year_built: number | null;
}): string {
  if (props.risk_label === "Critical" || props.risk_label === "High") {
    if (props.asbestos > 0) {
      return "Review asbestos records before planning capital or energy work.";
    }
    return "Start with a building-level energy review and compare against peer buildings.";
  }

  if (props.risk_label === "Moderate") {
    if (props.violations > 0) {
      return "Check violation history before prioritizing efficiency upgrades.";
    }
    return "Look for operational efficiency signals before deeper retrofit planning.";
  }

  if (props.risk_label === "Low") {
    return "Monitor performance and revisit when newer disclosure data appears.";
  }

  if (!props.ghg_source) {
    return "Confirm whether this building has an LL84/97 filing before relying on the estimate.";
  }

  return "Gather additional disclosure data before making a capital-planning decision.";
}

export function formatGhg(ghg: number | null): string {
  if (ghg == null || ghg <= 0) return "Not available";
  return `${ghg.toLocaleString()} mt CO₂e / yr`;
}

export function formatBuildingArea(sqFt: number | null): string {
  if (sqFt == null || sqFt <= 0) return "—";
  return `${Math.round(sqFt).toLocaleString()} sq ft`;
}
