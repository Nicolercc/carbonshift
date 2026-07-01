import type {
  ExpressionSpecification,
  FillExtrusionLayerSpecification,
  LineLayerSpecification,
} from "maplibre-gl";
import {
  BUILDING_EXTRUSION_LAYER_ID,
  BUILDING_OUTLINE_LAYER_ID,
  BUILDING_SOURCE_ID,
  RISK_COLORS,
  SELECTED_BUILDING_LAYER_ID,
} from "./mapConfig";

const riskColorExpression: ExpressionSpecification = [
  "match",
  ["get", "risk_label"],
  "Low",
  RISK_COLORS.Low,
  "Moderate",
  RISK_COLORS.Moderate,
  "High",
  RISK_COLORS.High,
  "Critical",
  RISK_COLORS.Critical,
  RISK_COLORS.Unscored,
];

export function createBuildingExtrusionLayer(): FillExtrusionLayerSpecification {
  return {
    id: BUILDING_EXTRUSION_LAYER_ID,
    type: "fill-extrusion",
    source: BUILDING_SOURCE_ID,
    paint: {
      "fill-extrusion-color": riskColorExpression,
      "fill-extrusion-height": ["get", "height_m"],
      "fill-extrusion-base": 0,
      "fill-extrusion-opacity": 0.92,
      "fill-extrusion-vertical-gradient": true,
    },
  };
}

export function createBuildingOutlineLayer(): LineLayerSpecification {
  return {
    id: BUILDING_OUTLINE_LAYER_ID,
    type: "line",
    source: BUILDING_SOURCE_ID,
    paint: {
      "line-color": "rgba(255, 255, 255, 0.22)",
      "line-width": 1,
    },
  };
}

export function createSelectedBuildingLayer(): LineLayerSpecification {
  return {
    id: SELECTED_BUILDING_LAYER_ID,
    type: "line",
    source: BUILDING_SOURCE_ID,
    filter: ["==", ["get", "id"], ""],
    paint: {
      "line-color": "#E8ECF0",
      "line-width": 2.5,
      "line-opacity": 1,
    },
  };
}
