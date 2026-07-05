import type { BuildingDetailPayload } from "./mapTypes";

/** User-safe error text — never expose stack traces or raw server bodies. */
function userFacingDetailError(status: number): string {
  if (status === 404) {
    return "No building detail found for this BIN in the current dataset.";
  }
  if (status === 503) {
    return "The building detail service is temporarily unavailable.";
  }
  if (status >= 500) {
    return "Building detail could not be loaded right now. Try again in a moment.";
  }
  return "Building detail could not be loaded. Check your connection and retry.";
}

export async function fetchBuildingDetail(
  bin: string,
  limit = 5,
): Promise<BuildingDetailPayload> {
  let response: Response;
  try {
    response = await fetch(
      `/api/buildings/${encodeURIComponent(bin)}?limit=${limit}`,
      { headers: { Accept: "application/json" } },
    );
  } catch {
    throw new Error("Building detail could not be loaded. Check your connection and retry.");
  }

  if (!response.ok) {
    throw new Error(userFacingDetailError(response.status));
  }

  const payload = (await response.json()) as BuildingDetailPayload;
  if (!payload?.signals || !payload?.building) {
    throw new Error("No building detail found for this BIN in the current dataset.");
  }

  return payload;
}
