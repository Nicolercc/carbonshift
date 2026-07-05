import { useEffect, useState, type CSSProperties } from "react";
import { fetchBuildingDetail } from "./buildingDetail";
import {
  DEMO_BIN,
  RISK_COLORS,
  RISK_LABELS,
  VIOLATION_DISPLAY_CAP,
  type BackendRiskLabel,
} from "./mapConfig";
import {
  asbestosBrief,
  carbonSignalValue,
  complianceSignalLine,
  confidenceBrief,
  formatBoroughLabel,
  formatRecordCapNote,
  resolveAsbestosViolationFlags,
  resolveViolationTotal,
  riskSignalValue,
  whyFlaggedSentence,
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
  const violations = detail?.records.violations ?? [];

  if (loading) {
    return (
      <div style={styles.card} role="dialog" aria-label="Building brief loading" aria-busy="true">
        <div style={{ ...styles.accentBar, backgroundColor: accent }} />
        <p style={styles.loadingEyebrow}>Loading intelligence brief…</p>
        <div style={styles.skeletonHero} />
        <div style={styles.skeletonGrid}>
          <div style={styles.skeletonMetric} />
          <div style={styles.skeletonMetric} />
          <div style={styles.skeletonMetric} />
          <div style={styles.skeletonMetric} />
        </div>
        <div style={styles.skeletonBlock} />
      </div>
    );
  }

  if (error || !signals) {
    const isNoData =
      !error ||
      error.toLowerCase().includes("no building detail found");
    return (
      <div style={styles.card} role="dialog" aria-label="Building brief unavailable">
        <button type="button" onClick={onClose} style={styles.closeButton} aria-label="Close">
          ×
        </button>
        <div style={{ ...styles.accentBar, backgroundColor: "#6B7580" }} />
        <p style={styles.errorTitle}>No building detail found</p>
        <p style={styles.errorBody}>
          {isNoData
            ? `BIN ${bin} is not in the current NYC dataset, or the API returned an empty profile.`
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

  const address = String(building.full_address || fallback?.address || `BIN ${bin}`);
  const borough = formatBoroughLabel(building.borough);
  const isDemo = bin === DEMO_BIN;
  const riskScore = signals.risk.score ?? fallback?.risk_score ?? null;
  const euiSource = String(signals.carbon.eui_source || fallback?.ghg_source || "");
  const ghgValue = signals.carbon.estimated_ghg_metric_tons ?? fallback?.ghg ?? null;

  const returnedViolationCount = signals.compliance.violation_count_returned;
  const displayedViolationCount = Math.min(violations.length, VIOLATION_DISPLAY_CAP);
  const totalViolationCount = resolveViolationTotal(
    fallback,
    building,
    returnedViolationCount,
  );

  const asbestosRecords = detail?.records.asbestos ?? [];
  const returnedAsbestosFilings = asbestosRecords.length;
  const totalAsbestosViolationFlags = resolveAsbestosViolationFlags(
    fallback,
    signals.compliance.asbestos_related_violation_count_returned,
  );

  const risk = riskSignalValue(riskScore, RISK_LABELS[riskLabel]);
  const carbon = carbonSignalValue(ghgValue, euiSource);
  const compliance = complianceSignalLine(totalViolationCount);
  const asbestos = asbestosBrief(totalAsbestosViolationFlags, returnedAsbestosFilings);
  const confidence = confidenceBrief(
    signals.data_completeness,
    signals.risk.confidence,
  );
  const whyFlagged = whyFlaggedSentence(riskLabel, signals.risk.drivers, riskScore);
  const violationCapNote = formatRecordCapNote(
    displayedViolationCount,
    totalViolationCount,
    "violation records",
  );
  const visibleViolations = violations.slice(0, VIOLATION_DISPLAY_CAP);

  return (
    <div style={styles.card} role="dialog" aria-label="Building intelligence brief">
      <button type="button" onClick={onClose} style={styles.closeButton} aria-label="Close">
        ×
      </button>
      <div style={{ ...styles.accentBar, backgroundColor: accent }} />

      <header style={styles.header}>
        {isDemo && <span style={styles.demoChip}>Demo</span>}
        <h2 style={styles.address}>{address}</h2>
        <p style={styles.metaLine}>
          {borough} · BIN {bin}
        </p>
      </header>

      <section style={styles.hero} aria-label="Risk summary">
        <div style={styles.heroTop}>
          <div style={styles.heroScoreBlock}>
            <span style={styles.heroScore}>{risk.value}</span>
            <span style={styles.heroScoreUnit}>risk score</span>
          </div>
          <span
            style={{
              ...styles.heroBadge,
              backgroundColor: `${accent}22`,
              color: accent,
              borderColor: `${accent}55`,
            }}
          >
            {RISK_LABELS[riskLabel]}
          </span>
        </div>
        <p style={styles.whyFlagged}>{whyFlagged}</p>
      </section>

      <section style={styles.signalGrid} aria-label="Four signals">
        <SignalCard title="Risk" value={risk.value} hint={risk.hint} />
        <SignalCard
          title="Carbon"
          value={carbon.value}
          badge={carbon.badge}
          badgeStyle={TIER_STYLES[carbon.tier]}
        />
        <SignalCard title="Compliance" value={compliance.value} hint={compliance.hint} />
        <SignalCard title="Asbestos" value={asbestos.value} hint={asbestos.hint} />
      </section>

      <section style={styles.confidenceBlock} aria-label="Data confidence">
        <span style={styles.confidenceLabel}>{confidence.label}</span>
        <span style={styles.confidenceDetail}>{confidence.detail}</span>
      </section>

      <section style={styles.evidenceSection} aria-label="Evidence">
        <h3 style={styles.sectionTitle}>Evidence</h3>

        {visibleViolations.length > 0 ? (
          <>
            <p style={styles.evidenceLead}>
              Violations
              {totalViolationCount > displayedViolationCount
                ? ` · ${displayedViolationCount} of ${totalViolationCount}`
                : ` · ${totalViolationCount}`}
            </p>
            <ul style={styles.violationList}>
              {visibleViolations.map((v, i) => (
                <ViolationRow key={`${v.source_dataset}-${v.issue_date}-${i}`} violation={v} />
              ))}
            </ul>
            {violationCapNote && <p style={styles.capNote}>{violationCapNote}</p>}
          </>
        ) : (
          <p style={styles.emptyEvidence}>No violation records in the returned sample.</p>
        )}

        <p style={{ ...styles.evidenceLead, marginTop: 12 }}>Asbestos</p>
        {returnedAsbestosFilings > 0 ? (
          <ul style={styles.violationList}>
            {asbestosRecords.slice(0, VIOLATION_DISPLAY_CAP).map((record, i) => (
              <AsbestosRow key={`asbestos-${i}`} record={record} />
            ))}
          </ul>
        ) : (
          <p style={styles.emptyEvidence}>
            No known asbestos filings in current dataset
          </p>
        )}
      </section>

      <footer style={styles.footer}>
        <a href={`/building/${bin}`} style={styles.detailLink}>
          Full profile →
        </a>
      </footer>
    </div>
  );
}

function SignalCard({
  title,
  value,
  hint,
  badge,
  badgeStyle,
}: {
  title: string;
  value: string;
  hint?: string;
  badge?: string;
  badgeStyle?: CSSProperties;
}) {
  return (
    <div style={styles.signalCard}>
      <span style={styles.signalTitle}>{title}</span>
      <div style={styles.signalValueRow}>
        <span style={styles.signalValue}>{value}</span>
        {badge && (
          <span style={{ ...styles.signalBadge, ...badgeStyle }}>{badge}</span>
        )}
      </div>
      {hint && <span style={styles.signalHint}>{hint}</span>}
    </div>
  );
}

function ViolationRow({ violation }: { violation: ViolationRecord }) {
  const agency = violation.source_dataset?.trim();
  const issueDate = violation.issue_date?.trim()?.slice(0, 10);
  const description = violation.violation_description?.trim();
  const status = violation.current_status?.trim();

  return (
    <li style={styles.evidenceItem}>
      <div style={styles.evidenceTop}>
        {agency && <span style={styles.evidenceAgency}>{agency}</span>}
        {issueDate && <span style={styles.evidenceDate}>{issueDate}</span>}
      </div>
      {description && (
        <p style={styles.evidenceDesc}>
          {violation.is_asbestos_related ? "⚠ " : ""}
          {description.slice(0, 100)}
        </p>
      )}
      {status && <span style={styles.evidenceStatus}>{status}</span>}
    </li>
  );
}

function AsbestosRow({ record }: { record: Record<string, unknown> }) {
  const status = String(record.project_status || "").trim();
  const date = String(record.project_start_date || "").trim().slice(0, 10);
  const control = String(record.control_number || "").trim();

  return (
    <li style={styles.evidenceItem}>
      <div style={styles.evidenceTop}>
        {control && <span style={styles.evidenceAgency}>Filing {control}</span>}
        {date && <span style={styles.evidenceDate}>{date}</span>}
      </div>
      {status && <span style={styles.evidenceStatus}>{status}</span>}
    </li>
  );
}

const styles: Record<string, CSSProperties> = {
  card: {
    position: "absolute",
    top: 48,
    right: 10,
    width: 400,
    maxWidth: "calc(100% - 20px)",
    maxHeight: "calc(100% - 64px)",
    overflowY: "auto",
    background: "rgba(12, 15, 20, 0.97)",
    backdropFilter: "blur(18px)",
    borderRadius: 14,
    border: "1px solid rgba(255, 255, 255, 0.08)",
    boxShadow: "0 20px 56px rgba(0, 0, 0, 0.55)",
    color: "#E8ECF0",
    padding: "16px 18px 14px",
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
    top: 8,
    right: 10,
    background: "transparent",
    border: "none",
    color: "#8B949E",
    fontSize: 22,
    lineHeight: 1,
    cursor: "pointer",
    padding: "4px 8px",
  },
  header: { marginBottom: 12 },
  demoChip: {
    display: "inline-block",
    marginBottom: 6,
    padding: "2px 7px",
    borderRadius: 999,
    fontSize: 9,
    fontWeight: 700,
    letterSpacing: "0.06em",
    textTransform: "uppercase" as const,
    background: "rgba(110, 207, 196, 0.14)",
    color: "#6ECFC4",
    border: "1px solid rgba(110, 207, 196, 0.28)",
  },
  address: {
    margin: "0 0 4px",
    fontSize: 17,
    fontWeight: 600,
    lineHeight: 1.3,
    color: "#F2F5F8",
  },
  metaLine: {
    margin: 0,
    fontSize: 11,
    color: "#7D8794",
  },
  hero: {
    marginBottom: 12,
    padding: "12px 14px",
    borderRadius: 12,
    background: "rgba(255, 255, 255, 0.035)",
    border: "1px solid rgba(255, 255, 255, 0.06)",
  },
  heroTop: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 10,
    marginBottom: 8,
  },
  heroScoreBlock: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 2,
  },
  heroScore: {
    fontSize: 34,
    fontWeight: 700,
    lineHeight: 1,
    color: "#F2F5F8",
    fontVariantNumeric: "tabular-nums",
  },
  heroScoreUnit: {
    fontSize: 10,
    letterSpacing: "0.06em",
    textTransform: "uppercase" as const,
    color: "#7D8794",
  },
  heroBadge: {
    fontSize: 11,
    fontWeight: 600,
    padding: "5px 9px",
    borderRadius: 999,
    border: "1px solid",
    whiteSpace: "nowrap" as const,
  },
  whyFlagged: {
    margin: 0,
    fontSize: 12,
    lineHeight: 1.45,
    color: "#B8C2CC",
  },
  signalGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: 8,
    marginBottom: 10,
  },
  signalCard: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 4,
    padding: "9px 10px",
    borderRadius: 10,
    background: "rgba(255, 255, 255, 0.025)",
    border: "1px solid rgba(255, 255, 255, 0.05)",
    minHeight: 72,
  },
  signalTitle: {
    fontSize: 9,
    fontWeight: 600,
    letterSpacing: "0.07em",
    textTransform: "uppercase" as const,
    color: "#7D8794",
  },
  signalValueRow: {
    display: "flex",
    flexWrap: "wrap" as const,
    alignItems: "center",
    gap: "4px 6px",
  },
  signalValue: {
    fontSize: 13,
    fontWeight: 600,
    color: "#E8ECF0",
    lineHeight: 1.25,
  },
  signalBadge: {
    fontSize: 9,
    fontWeight: 600,
    padding: "2px 6px",
    borderRadius: 999,
    whiteSpace: "nowrap" as const,
  },
  signalHint: {
    fontSize: 10,
    lineHeight: 1.35,
    color: "#9AA5B1",
  },
  confidenceBlock: {
    display: "flex",
    alignItems: "baseline",
    justifyContent: "space-between",
    gap: 10,
    marginBottom: 12,
    padding: "8px 10px",
    borderRadius: 10,
    background: "rgba(110, 207, 196, 0.06)",
    border: "1px solid rgba(110, 207, 196, 0.12)",
  },
  confidenceLabel: {
    fontSize: 11,
    fontWeight: 600,
    color: "#6ECFC4",
  },
  confidenceDetail: {
    fontSize: 10,
    color: "#9AA5B1",
    textAlign: "right" as const,
  },
  evidenceSection: { marginBottom: 8 },
  sectionTitle: {
    margin: "0 0 8px",
    fontSize: 9,
    fontWeight: 600,
    letterSpacing: "0.08em",
    textTransform: "uppercase" as const,
    color: "#7D8794",
  },
  evidenceLead: {
    margin: "0 0 6px",
    fontSize: 10,
    fontWeight: 600,
    color: "#9AA5B1",
  },
  emptyEvidence: {
    margin: "0 0 4px",
    fontSize: 11,
    color: "#7D8794",
    lineHeight: 1.4,
  },
  violationList: {
    listStyle: "none",
    margin: 0,
    padding: 0,
    display: "flex",
    flexDirection: "column" as const,
    gap: 6,
  },
  evidenceItem: {
    padding: "7px 9px",
    borderRadius: 8,
    background: "rgba(255, 255, 255, 0.025)",
    border: "1px solid rgba(255, 255, 255, 0.04)",
  },
  evidenceTop: {
    display: "flex",
    justifyContent: "space-between",
    gap: 8,
    marginBottom: 3,
  },
  evidenceAgency: {
    fontSize: 10,
    fontWeight: 600,
    color: "#CDD5DE",
  },
  evidenceDate: {
    fontSize: 10,
    color: "#7D8794",
  },
  evidenceDesc: {
    margin: "0 0 3px",
    fontSize: 11,
    lineHeight: 1.4,
    color: "#B8C2CC",
  },
  evidenceStatus: {
    fontSize: 10,
    color: "#9AA5B1",
  },
  capNote: {
    margin: "6px 0 0",
    fontSize: 10,
    color: "#7D8794",
  },
  footer: {
    display: "flex",
    justifyContent: "flex-end",
    marginTop: 6,
  },
  detailLink: {
    fontSize: 12,
    fontWeight: 500,
    color: "#6ECFC4",
    textDecoration: "none",
  },
  loadingEyebrow: {
    margin: "0 0 12px",
    fontSize: 12,
    color: "#9AA5B1",
  },
  skeletonHero: {
    height: 88,
    borderRadius: 12,
    marginBottom: 12,
    background: "linear-gradient(90deg, rgba(255,255,255,0.04) 25%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0.04) 75%)",
    backgroundSize: "200% 100%",
    animation: "cs-skeleton 1.4s ease infinite",
  },
  skeletonGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: 8,
    marginBottom: 12,
  },
  skeletonMetric: {
    height: 72,
    borderRadius: 10,
    background: "linear-gradient(90deg, rgba(255,255,255,0.04) 25%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0.04) 75%)",
    backgroundSize: "200% 100%",
    animation: "cs-skeleton 1.4s ease infinite",
  },
  skeletonBlock: {
    height: 48,
    borderRadius: 10,
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
