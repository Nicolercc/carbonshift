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
  if (!source) return "Source unavailable";
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
    return "Modeled from a borough-wide median — lower confidence than class peers.";
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

export function formatBoroughLabel(borough: unknown): string {
  const raw = String(borough || "").trim();
  if (!raw) return "NYC";
  const lower = raw.toLowerCase();
  if (lower === "qn" || lower === "queens") return "Queens";
  if (lower === "mn" || lower === "manhattan") return "Manhattan";
  if (lower === "bk" || lower === "brooklyn") return "Brooklyn";
  if (lower === "bx" || lower === "bronx") return "Bronx";
  if (lower === "si" || lower === "staten island") return "Staten Island";
  return raw.charAt(0).toUpperCase() + raw.slice(1).toLowerCase();
}

/** Parse scoring weight from strings like "pre-1940 (+3)" or "12 open violations (+8)". */
export function parseDriverPoints(driver: string): number | null {
  const match = driver.match(/\(\+(\d+)\)/);
  if (!match) return null;
  const points = Number.parseInt(match[1], 10);
  return Number.isFinite(points) ? points : null;
}

/** Pick the highest-weight driver without mutating the input array. */
export function selectTopRiskDriver(drivers: string[]): string | null {
  const candidates = drivers.map((d) => d.trim()).filter(Boolean);
  if (!candidates.length) return null;

  let topDriver: string | null = null;
  let topPoints = -Infinity;

  for (const driver of candidates) {
    const points = parseDriverPoints(driver);
    if (points == null) continue;
    if (points > topPoints) {
      topPoints = points;
      topDriver = driver;
    }
  }

  return topDriver ?? candidates[0];
}

function formatDriverHeadline(driver: string): string {
  return driver.replace(/\s*\(\+\d+\)\s*$/, "").trim();
}

export function whyFlaggedSentence(
  riskLabel: string,
  drivers: string[],
  riskScore: number | null,
): string {
  const lead = selectTopRiskDriver(drivers);
  if (lead) return formatDriverHeadline(lead);

  switch (riskLabel) {
    case "Critical":
      return "Multiple enforcement and emissions signals exceed critical thresholds.";
    case "High":
      return "Elevated risk score driven by compliance history and building profile.";
    case "Moderate":
      return "Mixed compliance and profile signals warrant closer review.";
    case "Low":
      return "Fewer enforcement signals than peer buildings in this sample.";
    default:
      return riskScore != null
        ? "Insufficient inputs to explain this score in plain language."
        : "Risk score not available for this building yet.";
  }
}

export function confidenceBrief(
  completeness: {
    has_location: boolean;
    has_profile: boolean;
    has_risk_score: boolean;
    has_carbon_estimate: boolean;
  },
  riskConfidence: string | null | undefined,
): { label: string; detail: string } {
  const flags = [
    completeness.has_location,
    completeness.has_profile,
    completeness.has_risk_score,
    completeness.has_carbon_estimate,
  ];
  const present = flags.filter(Boolean).length;
  const conf = (riskConfidence || "").trim().toLowerCase();

  if (present <= 2) {
    return {
      label: "Limited data",
      detail: `${present} of 4 core inputs on file`,
    };
  }
  if (conf.includes("high") || present === 4) {
    return {
      label: "High confidence",
      detail: present === 4 ? "Location, profile, risk, and carbon scored" : "Strong scoring inputs",
    };
  }
  if (conf.includes("medium") || conf.includes("moderate") || present === 3) {
    return {
      label: "Medium confidence",
      detail: `${present} of 4 core inputs on file`,
    };
  }
  if (conf.includes("low")) {
    return {
      label: "Limited data",
      detail: `${present} of 4 core inputs on file`,
    };
  }
  return {
    label: present >= 3 ? "Medium confidence" : "Limited data",
    detail: `${present} of 4 core inputs on file`,
  };
}

export function asbestosBrief(
  violationFlags: number,
  returnedFilings: number,
): { value: string; hint: string } {
  if (violationFlags <= 0 && returnedFilings <= 0) {
    return {
      value: "No known signal",
      hint: "No known asbestos filings in current dataset",
    };
  }
  const parts: string[] = [];
  if (violationFlags > 0) {
    parts.push(
      `${violationFlags} flagged violation${violationFlags === 1 ? "" : "s"}`,
    );
  }
  if (returnedFilings > 0) {
    parts.push(
      `${returnedFilings} filing${returnedFilings === 1 ? "" : "s"} in sample`,
    );
  }
  return {
    value: parts.join(" · "),
    hint:
      violationFlags > 0
        ? "Asbestos-related enforcement on record"
        : "Filings appear in returned sample only",
  };
}

export function riskSignalValue(
  score: number | null,
  label: string,
): { value: string; hint: string } {
  return {
    value: score != null ? String(score) : "—",
    hint: label,
  };
}

export function carbonSignalValue(
  ghg: number | null,
  source: string,
): { value: string; badge: string; tier: ReturnType<typeof ghgConfidenceTier> } {
  return {
    value: formatGhg(ghg),
    badge: ghgConfidenceLabel(source),
    tier: ghgConfidenceTier(source),
  };
}

export function complianceSignalLine(violationCount: number): {
  value: string;
  hint: string;
} {
  if (violationCount <= 0) {
    return {
      value: "No violations",
      hint: "No enforcement records in the current sample",
    };
  }
  if (violationCount === 1) {
    return { value: "1 violation", hint: "Enforcement history on file" };
  }
  return {
    value: `${violationCount} violations`,
    hint: "Compliance signal — review recent records below",
  };
}

export function asbestosSignalLine(
  hasSignal: boolean,
  totalProjectCount: number,
  totalViolationFlags: number,
): { value: string; chip: string } {
  if (!hasSignal) {
    return { value: "No asbestos signal", chip: "Clear" };
  }
  const parts: string[] = [];
  const sameTotal =
    totalProjectCount > 0 &&
    totalViolationFlags > 0 &&
    totalProjectCount === totalViolationFlags;

  if (sameTotal) {
    parts.push(
      `${totalViolationFlags} flagged violation${totalViolationFlags === 1 ? "" : "s"}`,
    );
  } else {
    if (totalProjectCount > 0) {
      parts.push(
        `${totalProjectCount} asbestos project${totalProjectCount === 1 ? "" : "s"}`,
      );
    }
    if (totalViolationFlags > 0) {
      parts.push(
        `${totalViolationFlags} flagged violation${totalViolationFlags === 1 ? "" : "s"}`,
      );
    }
  }
  return {
    value: parts.join(" · ") || "Signal detected",
    chip: "Review before capital work",
  };
}

export function dataCompletenessLine(
  completeness: {
    has_location: boolean;
    has_profile: boolean;
    has_risk_score: boolean;
    has_carbon_estimate: boolean;
  },
  riskConfidence: string | null | undefined,
): { value: string; chip: string } {
  const flags = [
    completeness.has_location,
    completeness.has_profile,
    completeness.has_risk_score,
    completeness.has_carbon_estimate,
  ];
  const present = flags.filter(Boolean).length;
  const missing: string[] = [];
  if (!completeness.has_location) missing.push("location");
  if (!completeness.has_profile) missing.push("profile");
  if (!completeness.has_risk_score) missing.push("risk");
  if (!completeness.has_carbon_estimate) missing.push("carbon");

  const confidence = riskConfidence?.trim()
    ? `${riskConfidence.trim()} confidence`
    : "Confidence unavailable";

  return {
    value: `${present}/4 inputs`,
    chip: missing.length ? `${confidence} · missing ${missing.join(", ")}` : confidence,
  };
}

export function buildingMetaLine(
  building: Record<string, unknown>,
  bin: string,
): string {
  const parts = [`BIN ${bin}`];
  const buildingClass = String(building.building_class || "").trim();
  const yearBuilt = building.year_built;
  if (buildingClass) parts.push(`Class ${buildingClass}`);
  if (yearBuilt != null && yearBuilt !== "") parts.push(String(yearBuilt));
  return parts.join(" · ");
}

export function isValidCount(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0;
}

/** True violation total for headline copy — not the capped detail payload. */
export function resolveViolationTotal(
  fallback: { violations?: number } | undefined,
  building: Record<string, unknown>,
  returnedCount: number,
): number {
  if (isValidCount(fallback?.violations)) return fallback.violations;
  const fromBuilding = building.violation_count ?? building.violations;
  if (isValidCount(fromBuilding)) return fromBuilding;
  if (isValidCount(returnedCount)) return returnedCount;
  return 0;
}

/** True asbestos project total for headline copy — not the capped detail payload. */
export function resolveAsbestosProjectTotal(
  fallback: { asbestos?: number } | undefined,
  building: Record<string, unknown>,
  returnedCount: number,
): number {
  if (isValidCount(fallback?.asbestos)) return fallback.asbestos;
  const fromBuilding =
    building.asbestos_project_count ?? building.asbestos_projects;
  if (isValidCount(fromBuilding)) return fromBuilding;
  if (isValidCount(returnedCount)) return returnedCount;
  return 0;
}

/** True asbestos-related violation flag total when available from map feature. */
export function resolveAsbestosViolationFlags(
  fallback: { asbestos?: number } | undefined,
  returnedCount: number,
): number {
  if (isValidCount(fallback?.asbestos)) return fallback.asbestos;
  if (isValidCount(returnedCount)) return returnedCount;
  return 0;
}

export function formatRecordCapNote(
  displayed: number,
  total: number,
  label: string,
): string | null {
  if (total <= displayed) return null;
  const noun = total === 1 ? label.replace(/s$/, "") : label;
  return `Showing ${displayed} of ${total} ${noun}`;
}
