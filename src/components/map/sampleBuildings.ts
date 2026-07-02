import type { BuildingFeatureCollection } from "./mapTypes";

function footprint(
  lng: number,
  lat: number,
  widthDeg = 0.00014,
  depthDeg = 0.0001,
) {
  const hw = widthDeg / 2;
  const hd = depthDeg / 2;
  return {
    type: "Polygon" as const,
    coordinates: [
      [
        [lng - hw, lat - hd],
        [lng + hw, lat - hd],
        [lng + hw, lat + hd],
        [lng - hw, lat + hd],
        [lng - hw, lat - hd],
      ],
    ],
  };
}

/** Fallback demo footprints when Flask API is unavailable or empty. */
export const sampleBuildings: BuildingFeatureCollection = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      geometry: footprint(-73.9482, 40.7448),
      properties: {
        id: "4100123",
        bin: "4100123",
        address: "28-10 Jackson Ave",
        zip: "11101",
        year_built: 1962,
        building_class: "O4",
        building_area: 420000,
        risk_score: 22,
        risk_label: "Critical",
        ghg: 1840,
        ghg_source: "class_median",
        violations: 14,
        asbestos: 2,
        height_m: 128,
        primary_driver:
          "2 asbestos-related violations · Elevated estimated emissions (1,840 mt CO₂e/yr) · Pre-war building systems (1962)",
        suggested_action:
          "Commission asbestos survey and align abatement with envelope/HVAC retrofit planning.",
      },
    },
    {
      type: "Feature",
      geometry: footprint(-73.9264, 40.7641),
      properties: {
        id: "4100456",
        bin: "4100456",
        address: "31-09 31st Ave",
        zip: "11106",
        year_built: 1938,
        building_class: "C1",
        building_area: 18500,
        risk_score: 7,
        risk_label: "Moderate",
        ghg: 312,
        ghg_source: "borough_median",
        violations: 3,
        asbestos: 0,
        height_m: 19,
        primary_driver:
          "3 open violations · Pre-war building stock (1938) · Class C1 use profile",
        suggested_action:
          "Resolve outstanding violations while scoping HVAC and envelope improvements.",
      },
    },
    {
      type: "Feature",
      geometry: footprint(-73.8305, 40.7582),
      properties: {
        id: "4100789",
        bin: "4100789",
        address: "136-20 Roosevelt Ave",
        zip: "11354",
        year_built: 1985,
        building_class: "D4",
        building_area: 95000,
        risk_score: 15,
        risk_label: "High",
        ghg: 920,
        ghg_source: "measured",
        violations: 8,
        asbestos: 0,
        height_m: 45,
        primary_driver:
          "8 open violations · Class D4 use profile · Risk score 15",
        suggested_action:
          "Schedule comprehensive energy audit and prioritize electrification as part of ongoing capital planning.",
      },
    },
    {
      type: "Feature",
      geometry: footprint(-73.7948, 40.7063),
      properties: {
        id: "4101024",
        bin: "4101024",
        address: "90-01 Sutphin Blvd",
        zip: "11435",
        year_built: 1972,
        building_class: "B2",
        building_area: 52000,
        risk_score: 6,
        risk_label: "Moderate",
        ghg: 485,
        ghg_source: "class_median",
        violations: 1,
        asbestos: 0,
        height_m: 26,
        primary_driver:
          "1 open violation · Legacy building systems (1972) · Class B2 use profile",
        suggested_action:
          "Target operational efficiency upgrades and heat-pump readiness assessment.",
      },
    },
    {
      type: "Feature",
      geometry: footprint(-73.8491, 40.7204),
      properties: {
        id: "4101155",
        bin: "4101155",
        address: "71-35 Austin St",
        zip: "11375",
        year_built: 2018,
        building_class: "C0",
        building_area: 12000,
        risk_score: 2,
        risk_label: "Low",
        ghg: 118,
        ghg_source: "measured",
        violations: 0,
        asbestos: 0,
        height_m: 14,
        primary_driver: "Class C0 use profile",
        suggested_action:
          "Maintain performance; plan heat-pump conversion at end of equipment life.",
      },
    },
    {
      type: "Feature",
      geometry: footprint(-73.941, 40.751),
      properties: {
        id: "4101288",
        bin: "4101288",
        address: "43-10 Crescent St",
        zip: "11101",
        year_built: 2008,
        building_class: "R9",
        building_area: 78000,
        risk_score: 11,
        risk_label: "High",
        ghg: 640,
        ghg_source: "class_median",
        violations: 5,
        asbestos: 0,
        height_m: 68,
        primary_driver:
          "5 open violations · Class R9 use profile · Risk score 11",
        suggested_action:
          "Schedule comprehensive energy audit and prioritize electrification as part of ongoing capital planning.",
      },
    },
    {
      type: "Feature",
      geometry: footprint(-73.912, 40.772),
      properties: {
        id: "4101310",
        bin: "4101310",
        address: "23-12 Broadway",
        zip: "11106",
        year_built: null,
        building_class: "A5",
        building_area: null,
        risk_score: null,
        risk_label: "Unscored",
        ghg: null,
        ghg_source: "",
        violations: 0,
        asbestos: 0,
        height_m: 10,
        primary_driver:
          "Building lacks sufficient scoring inputs for a confident assessment.",
        suggested_action:
          "Request LL84 filing status and schedule baseline energy audit.",
      },
    },
  ],
};
