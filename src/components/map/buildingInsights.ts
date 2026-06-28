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
      return "Critical retrofit priority";
    case "High":
      return "High retrofit priority";
    case "Moderate":
      return "Moderate retrofit priority";
    case "Low":
      return "Lower retrofit priority";
    default:
      return "Insufficient scoring data";
  }
}

export function ghgConfidenceLabel(source: string): string {
  if (source === "measured") return "High — measured LL84/97";
  if (source === "class_median") return "Medium — class median model";
  if (source === "borough_median") return "Low — borough median model";
  if (!source) return "Not available";
  return "Modeled estimate";
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
      return "Commission asbestos survey and align abatement with envelope/HVAC retrofit planning.";
    }
    return "Schedule comprehensive energy audit and prioritize electrification within 18 months.";
  }

  if (props.risk_label === "Moderate") {
    if (props.violations > 0) {
      return "Resolve outstanding violations while scoping HVAC and envelope improvements.";
    }
    return "Target operational efficiency upgrades and heat-pump readiness assessment.";
  }

  if (props.risk_label === "Low") {
    return "Maintain performance; plan heat-pump conversion at end of equipment life.";
  }

  if (!props.ghg_source) {
    return "Request LL84 filing status and schedule baseline energy audit.";
  }

  return "Gather additional disclosure data before prioritizing capital upgrades.";
}

export function formatGhg(ghg: number | null): string {
  if (ghg == null || ghg <= 0) return "Not available";
  return `${ghg.toLocaleString()} mt CO₂e / yr`;
}

export function formatBuildingArea(sqFt: number | null): string {
  if (sqFt == null || sqFt <= 0) return "—";
  return `${Math.round(sqFt).toLocaleString()} sq ft`;
}
