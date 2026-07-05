import { useEffect, useState, type CSSProperties, type ReactNode } from "react";
import { fetchBuildingDetail } from "./buildingDetail";
import {
  DEMO_BIN,
  RISK_COLORS,
  RISK_DRIVER_DISPLAY_CAP,
  RISK_LABELS,
  VIOLATION_DISPLAY_CAP,
  type BackendRiskLabel,
} from "./mapConfig";
import {
  asbestosSignalLine,
  buildingMetaLine,
  complianceSignalLine,
  dataCompletenessLine,
  formatGhg,
  formatRecordCapNote,
  ghgConfidenceLabel,
  ghgConfidenceTier,
  resolveAsbestosProjectTotal,
  resolveAsbestosViolationFlags,
  resolveViolationTotal,
} from "./buildingInsights";
import type {
  BuildingDetailPayload,
  BuildingProperties,
  ViolationRecord,
} from "./mapTypes";

const TIER_STYLES: Record<string, CSSProperties> = {
  high: { background: "rgba(25, 135, 84, 0.15)", color: "#8FD9B0" },
  medium: { background: "rgba(255, 193, 7, 0.12)", color: "#E8D48A" },
  low: { background: "rgba(173, 181, 189, 0.12)", color: "#B8C2CC" },
  none: { background: "rgba(107, 117, 128, 0.12)", color: "#9AA5B1" },
};

interface BuildingInsightCardProps {
  bin: string;
  fallback?: BuildingProperties;
  onClose: () => void;
}

export function BuildingInsightCard({
  bin,
  fallback,
  onClose,
}: BuildingInsightCardProps) {
  const [detail, setDetail] = useState<BuildingDetailPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setDetail(null);

    fetchBuildingDetail(bin, VIOLATION_DISPLAY_CAP)
      .then((payload) => {
        if (!cancelled) {
          setDetail(payload);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Building detail could not be loaded.",
          );
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [bin, retryKey]);

  const handleRetry = () => setRetryKey((key) => key + 1);

  const building = detail?.building ?? {};
  const signals = detail?.signals;
  const riskLabel = (signals?.risk.label ||
    fallback?.risk_label ||
    "Unscored") as BackendRiskLabel;
  const accent = RISK_COLORS[riskLabel] ?? RISK_COLORS.Unscored;
  const address =
    String(building.full_address || fallback?.address || `BIN ${bin}`);
  const euiSource = String(
    signals?.carbon.eui_source || fallback?.ghg_source || "",
  );
  const sourceTier = ghgConfidenceTier(euiSource);
  const ghgValue =
    signals?.carbon.estimated_ghg_metric_tons ?? fallback?.ghg ?? null;
  const violations = detail?.records.violations ?? [];

  if (loading) {
    return (
      <div style={styles.card} role="dialog" aria-label="Building insight loading" aria-busy="true">
        <div style={{ ...styles.accentBar, backgroundColor: accent }} />
        <p style={styles.loadingEyebrow}>Loading building intelligence…</p>
        <div style={styles.skeletonBlock} />
        <div style={styles.skeletonBlockShort} />
        <div style={styles.skeletonRow}>
          <div style={styles.skeletonChip} />
          <div style={styles.skeletonChip} />
        </div>
        <div style={styles.skeletonGrid}>
          <div style={styles.skeletonMetric} />
          <div style={styles.skeletonMetric} />
          <div style={styles.skeletonMetric} />
          <div style={styles.skeletonMetric} />
          <div style={{ ...styles.skeletonMetric, gridColumn: "1 / -1" }} />
        </div>
        <div style={styles.skeletonFooter} />
      </div>
    );
  }

  if (error || !signals) {
    const isNoData =
      !error ||
      error.toLowerCase().includes("no building detail found");
    return (
      <div style={styles.card} role="dialog" aria-label="Building insight unavailable">
        <button type="button" onClick={onClose} style={styles.closeButton} aria-label="Close">
          ×
        </button>
        <div style={{ ...styles.accentBar, backgroundColor: "#6B7580" }} />
        <p style={styles.errorTitle}>No building detail found</p>
        <p style={styles.errorBody}>
          {isNoData
            ? `BIN ${bin} is not in the current Queens dataset, or the API returned an empty profile.`
            : error}
        </p>
        <p style={styles.errorHint}>
          {isNoData
            ? "Select another footprint on the map or use the demo building."
            : "Confirm Flask is running, then retry or pick another building."}
        </p>
        {!isNoData && (
          <button type="button" style={styles.retryButton} onClick={handleRetry}>
            Retry detail
          </button>
        )}
      </div>
    );
  }

  const riskScore = signals.risk.score ?? fallback?.risk_score ?? null;
  const riskDrivers = signals.risk.drivers.slice(0, RISK_DRIVER_DISPLAY_CAP);

  const returnedViolationCount = signals.compliance.violation_count_returned;
  const displayedViolationCount = Math.min(
    violations.length,
    VIOLATION_DISPLAY_CAP,
  );
  const totalViolationCount = resolveViolationTotal(
    fallback,
    building,
    returnedViolationCount,
  );

  const asbestosRecords = detail?.records.asbestos ?? [];
  const returnedAsbestosProjectCount = signals.asbestos.project_count_returned;
  const displayedAsbestosRecordCount = Math.min(
    asbestosRecords.length,
    VIOLATION_DISPLAY_CAP,
  );
  const totalAsbestosProjectCount = resolveAsbestosProjectTotal(
    fallback,
    building,
    returnedAsbestosProjectCount,
  );
  const totalAsbestosViolationFlags = resolveAsbestosViolationFlags(
    fallback,
    signals.compliance.asbestos_related_violation_count_returned,
  );
  const hasAsbestosSignal =
    signals.asbestos.has_asbestos_signal ||
    totalAsbestosProjectCount > 0 ||
    totalAsbestosViolationFlags > 0;

  const compliance = complianceSignalLine(totalViolationCount);
  const asbestos = asbestosSignalLine(
    hasAsbestosSignal,
    totalAsbestosProjectCount,
    totalAsbestosViolationFlags,
  );
  const violationCapNote = formatRecordCapNote(
    displayedViolationCount,
    totalViolationCount,
    "violation records",
  );
  const asbestosCapNote = formatRecordCapNote(
    displayedAsbestosRecordCount,
    totalAsbestosProjectCount,
    "asbestos records",
  );
  const completeness = dataCompletenessLine(
    signals.data_completeness,
    signals.risk.confidence,
  );
  const visibleViolations = violations.slice(0, VIOLATION_DISPLAY_CAP);
  const metaLine = buildingMetaLine(building, bin);
  const isDemo = bin === DEMO_BIN;
  const carbonBadge = ghgConfidenceLabel(euiSource);

  return (
    <div style={styles.card} role="dialog" aria-label="Building insight">
      <button type="button" onClick={onClose} style={styles.closeButton} aria-label="Close">
        ×
      </button>
      <div style={{ ...styles.accentBar, backgroundColor: accent }} />

      {isDemo && <span style={styles.demoChip}>Demo building</span>}
      <h2 style={styles.address}>{address}</h2>
      <p style={styles.metaLine}>{metaLine}</p>

      <div style={styles.riskHero}>
        <div style={styles.riskScoreBlock}>
          <span style={styles.riskScoreValue}>
            {riskScore != null ? riskScore : "—"}
          </span>
          <span style={styles.riskScoreUnit}>risk score</span>
        </div>
        <span
          style={{
            ...styles.riskLabelBadge,
            backgroundColor: `${accent}22`,
            color: accent,
            borderColor: `${accent}55`,
          }}
        >
          {RISK_LABELS[riskLabel]}
        </span>
      </div>

      {riskDrivers.length > 0 && (
        <div style={styles.driverSection}>
          <p style={styles.driverTitle}>Top drivers</p>
          <div style={styles.driverList}>
            {riskDrivers.map((driver) => (
              <span key={driver} style={styles.driverChip}>
                {driver}
              </span>
            ))}
          </div>
        </div>
      )}

      <div style={styles.signalStrip}>
        <SignalRow label="Carbon">
          <span style={styles.carbonValue}>{formatGhg(ghgValue)}</span>
          <span style={{ ...styles.inlineBadge, ...TIER_STYLES[sourceTier] }}>
            {carbonBadge}
          </span>
        </SignalRow>

        <SignalRow label="Compliance">
          <span style={styles.signalPrimary}>{compliance.value}</span>
          <span style={styles.signalHint}>{compliance.hint}</span>
        </SignalRow>

        <SignalRow label="Asbestos">
          <span style={styles.signalPrimary}>{asbestos.value}</span>
          <span style={styles.inlineBadgeMuted}>{asbestos.chip}</span>
          {asbestosCapNote && (
            <span style={styles.signalHint}>{asbestosCapNote}</span>
          )}
        </SignalRow>

        <SignalRow label="Confidence">
          <span style={styles.signalPrimary}>{completeness.value}</span>
          <span style={styles.signalHint}>{completeness.chip}</span>
        </SignalRow>
      </div>

      {visibleViolations.length > 0 && (
        <section style={styles.section}>
          <h3 style={styles.sectionTitle}>
            Recent violations
            <span style={styles.countBadge}>
              {displayedViolationCount}
              {totalViolationCount > displayedViolationCount
                ? ` of ${totalViolationCount}`
                : ""}
            </span>
          </h3>
          <ul style={styles.violationList}>
            {visibleViolations.map((v, i) => (
              <ViolationRow key={`${v.source_dataset}-${v.issue_date}-${i}`} violation={v} />
            ))}
          </ul>
          {violationCapNote && (
            <p style={styles.capNote}>
              {violationCapNote} — full history on building page.
            </p>
          )}
        </section>
      )}

      <div style={styles.footer}>
        <p style={styles.bin}>BIN {bin}</p>
        <a href={`/building/${bin}`} style={styles.detailLink}>
          Full profile →
        </a>
      </div>
    </div>
  );
}

function SignalRow({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div style={styles.signalRow}>
      <span style={styles.signalRowLabel}>{label}</span>
      <div style={styles.signalRowBody}>{children}</div>
    </div>
  );
}

function ViolationRow({ violation }: { violation: ViolationRecord }) {
  const source = violation.source_dataset?.trim();
  const issueDate = violation.issue_date?.trim();
  const violationClass = violation.violation_class?.trim();
  const status = violation.current_status?.trim();
  const description = violation.violation_description?.trim();
  const isOpen =
    status &&
    (status.toUpperCase().includes("OPEN") || status.toUpperCase().includes("ACTIVE"));
  const hasTopRow = Boolean(source || issueDate);
  const hasMetaRow = Boolean(violationClass || status);

  return (
    <li style={styles.violationItem}>
      {hasTopRow && (
        <div style={styles.violationTop}>
          {source && <span style={styles.violationSource}>{source}</span>}
          {issueDate && (
            <span style={styles.violationDate}>{issueDate.slice(0, 10)}</span>
          )}
        </div>
      )}
      {hasMetaRow && (
        <div style={styles.violationMeta}>
          {violationClass && <span>{violationClass}</span>}
          {status && (
            <span style={isOpen ? styles.statusOpen : styles.statusMuted}>{status}</span>
          )}
        </div>
      )}
      {description && (
        <p style={styles.violationDesc}>
          {violation.is_asbestos_related ? "⚠ " : ""}
          {description.slice(0, 120)}
        </p>
      )}
    </li>
  );
}

const styles: Record<string, CSSProperties> = {
  card: {
    position: "absolute",
    top: 52,
    right: 10,
    width: 392,
    maxWidth: "calc(100% - 20px)",
    maxHeight: "calc(100% - 64px)",
    overflowY: "auto",
    background: "rgba(14, 17, 22, 0.96)",
    backdropFilter: "blur(16px)",
    borderRadius: 14,
    border: "1px solid rgba(255, 255, 255, 0.07)",
    boxShadow: "0 24px 60px rgba(0, 0, 0, 0.5)",
    color: "#E8ECF0",
    padding: "18px 20px 16px",
    zIndex: 12,
    fontFamily:
      '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  },
  accentBar: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    height: 3,
    borderRadius: "14px 14px 0 0",
  },
  closeButton: {
    position: "absolute",
    top: 10,
    right: 12,
    background: "transparent",
    border: "none",
    color: "#8B949E",
    fontSize: 22,
    lineHeight: 1,
    cursor: "pointer",
    padding: "4px 8px",
  },
  demoChip: {
    display: "inline-block",
    marginBottom: 8,
    padding: "3px 8px",
    borderRadius: 999,
    fontSize: 10,
    fontWeight: 600,
    letterSpacing: "0.04em",
    textTransform: "uppercase" as const,
    background: "rgba(110, 207, 196, 0.14)",
    color: "#6ECFC4",
    border: "1px solid rgba(110, 207, 196, 0.28)",
  },
  eyebrow: {
    margin: "0 0 4px",
    fontSize: 11,
    letterSpacing: "0.07em",
    textTransform: "uppercase" as const,
    color: "#7D8794",
  },
  address: {
    margin: "0 0 6px",
    fontSize: 18,
    fontWeight: 600,
    lineHeight: 1.3,
    color: "#F2F5F8",
  },
  metaLine: {
    margin: "0 0 14px",
    fontSize: 11,
    color: "#7D8794",
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
  },
  riskHero: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
    marginBottom: 12,
    padding: "12px 14px",
    borderRadius: 12,
    background: "rgba(255, 255, 255, 0.03)",
    border: "1px solid rgba(255, 255, 255, 0.06)",
  },
  riskScoreBlock: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 2,
  },
  riskScoreValue: {
    fontSize: 32,
    fontWeight: 700,
    lineHeight: 1,
    color: "#F2F5F8",
    fontVariantNumeric: "tabular-nums",
  },
  riskScoreUnit: {
    fontSize: 10,
    letterSpacing: "0.06em",
    textTransform: "uppercase" as const,
    color: "#7D8794",
  },
  riskLabelBadge: {
    fontSize: 12,
    fontWeight: 600,
    padding: "6px 10px",
    borderRadius: 999,
    border: "1px solid",
    whiteSpace: "nowrap" as const,
  },
  driverSection: {
    marginBottom: 12,
  },
  driverTitle: {
    margin: "0 0 6px",
    fontSize: 10,
    fontWeight: 600,
    letterSpacing: "0.06em",
    textTransform: "uppercase" as const,
    color: "#7D8794",
  },
  signalStrip: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 8,
    marginBottom: 12,
  },
  signalRow: {
    display: "grid",
    gridTemplateColumns: "88px 1fr",
    gap: 10,
    alignItems: "start",
    padding: "8px 10px",
    borderRadius: 10,
    background: "rgba(255, 255, 255, 0.025)",
    border: "1px solid rgba(255, 255, 255, 0.04)",
  },
  signalRowLabel: {
    fontSize: 10,
    color: "#7D8794",
    textTransform: "uppercase" as const,
    letterSpacing: "0.05em",
    paddingTop: 2,
  },
  signalRowBody: {
    display: "flex",
    flexWrap: "wrap" as const,
    alignItems: "center",
    gap: "6px 8px",
    minWidth: 0,
  },
  carbonValue: {
    fontSize: 13,
    fontWeight: 600,
    color: "#E8ECF0",
  },
  signalPrimary: {
    fontSize: 13,
    fontWeight: 600,
    color: "#E8ECF0",
  },
  signalHint: {
    fontSize: 11,
    color: "#9AA5B1",
    lineHeight: 1.35,
  },
  inlineBadge: {
    fontSize: 10,
    fontWeight: 600,
    padding: "3px 8px",
    borderRadius: 999,
    whiteSpace: "nowrap" as const,
  },
  inlineBadgeMuted: {
    fontSize: 10,
    fontWeight: 500,
    padding: "3px 8px",
    borderRadius: 999,
    background: "rgba(107, 117, 128, 0.14)",
    color: "#B8C2CC",
    whiteSpace: "nowrap" as const,
  },
  driverList: {
    display: "flex",
    flexWrap: "wrap" as const,
    gap: 6,
    marginBottom: 12,
  },
  driverChip: {
    fontSize: 11,
    lineHeight: 1.35,
    padding: "5px 8px",
    borderRadius: 8,
    background: "rgba(255, 255, 255, 0.04)",
    color: "#B8C2CC",
    border: "1px solid rgba(255, 255, 255, 0.05)",
  },
  section: { marginBottom: 10 },
  sectionTitle: {
    margin: "0 0 8px",
    fontSize: 10,
    fontWeight: 600,
    letterSpacing: "0.06em",
    textTransform: "uppercase" as const,
    color: "#7D8794",
    display: "flex",
    alignItems: "center",
    gap: 8,
  },
  countBadge: {
    fontSize: 10,
    fontWeight: 500,
    color: "#9AA5B1",
    textTransform: "none" as const,
    letterSpacing: 0,
  },
  violationList: {
    listStyle: "none",
    margin: 0,
    padding: 0,
    display: "flex",
    flexDirection: "column" as const,
    gap: 8,
  },
  violationItem: {
    padding: "8px 10px",
    borderRadius: 8,
    background: "rgba(255, 255, 255, 0.03)",
    border: "1px solid rgba(255, 255, 255, 0.05)",
  },
  violationTop: {
    display: "flex",
    justifyContent: "space-between",
    gap: 8,
    marginBottom: 4,
  },
  violationSource: {
    fontSize: 11,
    fontWeight: 600,
    color: "#CDD5DE",
  },
  violationDate: {
    fontSize: 10,
    color: "#7D8794",
  },
  violationMeta: {
    display: "flex",
    gap: 8,
    fontSize: 10,
    color: "#9AA5B1",
    marginBottom: 4,
  },
  statusOpen: { color: "#E8B4B4" },
  statusMuted: { color: "#7D8794" },
  violationDesc: {
    margin: 0,
    fontSize: 11,
    lineHeight: 1.45,
    color: "#B8C2CC",
  },
  capNote: {
    margin: "8px 0 0",
    fontSize: 10,
    color: "#7D8794",
  },
  footer: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
    marginTop: 4,
    flexWrap: "wrap" as const,
  },
  bin: {
    margin: 0,
    fontSize: 11,
    color: "#5C6670",
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
  },
  detailLink: {
    fontSize: 13,
    fontWeight: 500,
    color: "#6ECFC4",
    textDecoration: "none",
  },
  loadingEyebrow: {
    margin: "0 0 12px",
    fontSize: 12,
    color: "#9AA5B1",
  },
  skeletonBlock: {
    height: 18,
    width: "70%",
    borderRadius: 6,
    marginBottom: 10,
    background: "linear-gradient(90deg, rgba(255,255,255,0.04) 25%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0.04) 75%)",
    backgroundSize: "200% 100%",
    animation: "cs-skeleton 1.4s ease infinite",
  },
  skeletonBlockShort: {
    height: 14,
    width: "48%",
    borderRadius: 6,
    marginBottom: 14,
    background: "linear-gradient(90deg, rgba(255,255,255,0.04) 25%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0.04) 75%)",
    backgroundSize: "200% 100%",
    animation: "cs-skeleton 1.4s ease infinite",
  },
  skeletonRow: {
    display: "flex",
    gap: 8,
    marginBottom: 12,
  },
  skeletonChip: {
    height: 24,
    width: 90,
    borderRadius: 999,
    background: "linear-gradient(90deg, rgba(255,255,255,0.04) 25%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0.04) 75%)",
    backgroundSize: "200% 100%",
    animation: "cs-skeleton 1.4s ease infinite",
  },
  skeletonGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: 8,
  },
  skeletonMetric: {
    height: 64,
    borderRadius: 10,
    background: "linear-gradient(90deg, rgba(255,255,255,0.04) 25%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0.04) 75%)",
    backgroundSize: "200% 100%",
    animation: "cs-skeleton 1.4s ease infinite",
  },
  skeletonFooter: {
    marginTop: 14,
    height: 12,
    width: "36%",
    borderRadius: 6,
    background: "linear-gradient(90deg, rgba(255,255,255,0.04) 25%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0.04) 75%)",
    backgroundSize: "200% 100%",
    animation: "cs-skeleton 1.4s ease infinite",
  },
  retryButton: {
    marginTop: 10,
    padding: "7px 12px",
    borderRadius: 8,
    border: "1px solid rgba(110, 207, 196, 0.35)",
    background: "rgba(110, 207, 196, 0.12)",
    color: "#6ECFC4",
    fontSize: 12,
    fontWeight: 600,
    cursor: "pointer",
    alignSelf: "flex-start",
  },
  errorTitle: {
    margin: "8px 0 6px",
    fontSize: 16,
    fontWeight: 600,
    color: "#F2F5F8",
  },
  errorBody: {
    margin: "0 0 8px",
    fontSize: 13,
    lineHeight: 1.5,
    color: "#B8C2CC",
  },
  errorHint: {
    margin: 0,
    fontSize: 11,
    color: "#7D8794",
  },
};
