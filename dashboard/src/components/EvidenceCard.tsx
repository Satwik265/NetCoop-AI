import React from "react";
import { EvidenceItem } from "../types/protocol";
import { formatDateTime, formatNumber, SupportedTimezone } from "../utils/i18n";

interface Props {
  evidence: EvidenceItem[];
  missingEvidence?: string[];
  onSelectEvidence?: (item: EvidenceItem) => void;
  timezone?: SupportedTimezone;
}

export const EvidenceCard: React.FC<Props> = ({
  evidence,
  missingEvidence = [],
  onSelectEvidence,
  timezone = "UTC",
}) => {
  return (
    <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E2E8F0] dark:border-[#2A2A2D] p-5 font-sans space-y-4">
      <div className="flex flex-wrap items-center justify-between border-b border-[#E2E8F0] dark:border-[#2A2A2D] pb-3 gap-3">
        <div>
          <h2 className="text-xs font-bold uppercase tracking-wider text-[#0B2545] dark:text-[#F1F5F9]">
            Corroborated Multi-Agent Evidence Ledger ({evidence.length} items)
          </h2>
          <div className="text-[11px] text-[#475569] dark:text-[#94A3B8]">
            Traceable empirical observations supporting root cause attribution and isolating failure domains.
          </div>
        </div>
      </div>

      {evidence.length === 0 ? (
        <div className="text-xs text-[#475569] dark:text-[#94A3B8] font-mono py-6 text-center border border-dashed border-[#CBD5E1] dark:border-[#2A2A2D]">
          Zero empirical evidence items recorded for this diagnostic session.
        </div>
      ) : (
        <div className="space-y-3" role="feed" aria-label="Evidence ledger items">
          {evidence.map((item, idx) => {
            const isCrit = item.severity === "critical";
            const isWarn = item.severity === "warning";
            const sevBadgeClass = isCrit
              ? "text-[#B91C1C] border-[#B91C1C]/40 bg-[#FEF2F2] dark:bg-[#7F1D1D]/30 dark:text-[#FCA5A5]"
              : isWarn
              ? "text-[#B45309] border-[#B45309]/40 bg-[#FFFBEB] dark:bg-[#78350F]/30 dark:text-[#FDE68A]"
              : "text-[#475569] border-[#CBD5E1] bg-[#F1F5F9] dark:border-[#2A2A2D] dark:bg-[#1E2024] dark:text-[#CBD5E1]";

            const sevIcon = isCrit ? "●" : isWarn ? "▲" : "■";

            const valDisplay =
              item.value !== undefined && item.value !== null
                ? typeof item.value === "number"
                  ? `${formatNumber(item.value)} ${item.unit || ""}`.trim()
                  : `${String(item.value)} ${item.unit || ""}`.trim()
                : "unknown";

            const evidenceId = item.evidence_id || (item.observation_id ? `evi-${item.observation_id}` : `evi-${idx + 1}`);
            const metricDisplay = item.metric || item.metric_name || item.category;

            return (
              <div
                key={evidenceId || idx}
                onClick={() => onSelectEvidence && onSelectEvidence(item)}
                tabIndex={0}
                role="article"
                aria-label={`Evidence ${evidenceId} from ${item.source_agent}: ${item.finding}`}
                className="p-3.5 bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#E2E8F0] dark:border-[#2A2A2D] flex flex-col md:flex-row md:items-start justify-between gap-4 text-xs transition-colors hover:border-[#0B2545] dark:hover:border-[#3A86FF] focus-visible:ring-2 focus-visible:ring-[#133E87]"
              >
                <div className="space-y-2 flex-1 min-w-0">
                  {/* Top metadata tags */}
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono font-bold text-[#0B2545] dark:text-[#3A86FF] uppercase text-[11px]">
                      [{item.source_agent}]
                    </span>
                    <span className="font-mono text-[10px] text-[#475569] dark:text-[#94A3B8] border border-[#CBD5E1] dark:border-[#2A2A2D] px-1.5 py-0.5 bg-[#FFFFFF] dark:bg-[#161618]">
                      {evidenceId}
                    </span>
                    <span className={`px-2 py-0.5 border text-[10px] font-mono font-bold uppercase flex items-center gap-1 ${sevBadgeClass}`}>
                      <span>{sevIcon}</span> {item.severity}
                    </span>
                    {item.timestamp_window && (
                      <span className="font-mono text-[10px] text-[#475569] dark:text-[#94A3B8]">
                        Window: {item.timestamp_window}
                      </span>
                    )}
                    {item.timestamp && (
                      <span className="font-mono text-[10px] text-[#475569] dark:text-[#94A3B8]">
                        Time: {formatDateTime(item.timestamp, timezone)}
                      </span>
                    )}
                  </div>

                  {/* Entity and Metric */}
                  <div className="text-[#0F172A] dark:text-[#F1F5F9] font-mono">
                    <span className="text-[#475569] dark:text-[#94A3B8] font-normal">Target Entity:</span>{" "}
                    <strong>{item.entity}</strong> &middot;{" "}
                    <span className="text-[#475569] dark:text-[#94A3B8] font-normal">Metric:</span>{" "}
                    <code>{metricDisplay}</code>
                  </div>

                  {/* Finding and Operator Interpretation */}
                  <div className="text-[#0F172A] dark:text-[#F1F5F9] font-medium leading-relaxed">
                    {item.finding}
                  </div>
                  {item.interpretation && item.interpretation !== item.finding && (
                    <div className="text-[11px] text-[#475569] dark:text-[#94A3B8] italic border-l-2 border-[#CBD5E1] dark:border-[#3A4668] pl-2.5">
                      Expert Interpretation: {item.interpretation}
                    </div>
                  )}

                  {/* Provenance references */}
                  {(item.observation_id || item.message_id || item.correlation_id) && (
                    <div className="text-[10px] font-mono text-[#64748B] flex flex-wrap items-center gap-3 pt-1">
                      {item.observation_id && <span>ObsID: <code>{item.observation_id}</code></span>}
                      {item.message_id && <span>MsgID: <code>{item.message_id}</code></span>}
                      {item.correlation_id && <span>CorrID: <code>{item.correlation_id}</code></span>}
                    </div>
                  )}
                </div>

                {/* Telemetry Metric Callout Box */}
                <div className="text-right font-mono bg-[#FFFFFF] dark:bg-[#161618] px-3.5 py-2.5 border border-[#E2E8F0] dark:border-[#2A2A2D] shrink-0 self-start md:min-w-[130px]">
                  <div className="text-[10px] text-[#475569] dark:text-[#94A3B8] uppercase font-bold tracking-wider">
                    Observed Metric
                  </div>
                  <div className="text-sm font-bold text-[#0F172A] dark:text-[#F1F5F9] mt-0.5">
                    {valDisplay}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Missing prerequisite evidence callout */}
      {missingEvidence.length > 0 && (
        <div className="mt-5 pt-4 border-t border-[#E2E8F0] dark:border-[#2A2A2D]">
          <h3 className="text-xs font-bold uppercase tracking-wider text-[#B45309] dark:text-[#FDE68A] mb-2 flex items-center gap-1.5">
            <span>⚠️</span> Prerequisite Corroboration Gaps ({missingEvidence.length})
          </h3>
          <ul className="space-y-1.5 text-xs font-mono text-[#475569] dark:text-[#94A3B8]">
            {missingEvidence.map((m, i) => (
              <li key={i} className="flex items-start gap-2">
                <span className="text-[#B45309] font-bold">&bull;</span> {m}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};
