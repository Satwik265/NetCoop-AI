import React from "react";
import { UnifiedDiagnosticReport, EnvelopeLogItem } from "../types/protocol";
import { formatPercent } from "../utils/i18n";

interface CorrelationPanelProps {
  report: UnifiedDiagnosticReport | null;
  envelopes: EnvelopeLogItem[];
  currentIndex: number;
}

export const CorrelationPanel: React.FC<CorrelationPanelProps> = ({
  report,
  envelopes,
  currentIndex,
}) => {
  // Aggregate hypotheses from envelopes up to current scrub index
  const visibleEnvelopes = envelopes.slice(0, currentIndex + 1);

  // Collect hypotheses from all visible envelopes
  const allHypotheses: Array<{
    id: string;
    agent: string;
    cause: string;
    confidence: number;
    supporting: string[];
    refuting: string[];
    iteration: number;
  }> = [];

  // Collect inquiries from all visible envelopes
  const allInquiries: Array<{
    id: string;
    fromAgent: string;
    targetAgent: string;
    question: string;
    targetEntity: string;
    iteration: number;
  }> = [];

  for (const env of visibleEnvelopes) {
    if (env.payload?.hypotheses) {
      for (const h of env.payload.hypotheses) {
        allHypotheses.push({
          id: h.hypothesis_id || Math.random().toString(),
          agent: env.sender,
          cause: h.probable_cause,
          confidence: h.confidence ?? 0,
          supporting: h.supporting_observation_ids || [],
          refuting: h.refuting_observation_ids || [],
          iteration: env.context?.iteration ?? 0,
        });
      }
    }

    if (env.payload?.inquiries) {
      for (const inq of env.payload.inquiries) {
        allInquiries.push({
          id: inq.inquiry_id || Math.random().toString(),
          fromAgent: env.sender,
          targetAgent: inq.target_agent,
          question: inq.question,
          targetEntity: inq.target_entity,
          iteration: env.context?.iteration ?? 0,
        });
      }
    }
  }

  // Deduplicate latest hypothesis per cause
  const latestByCause: Record<string, typeof allHypotheses[0]> = {};
  for (const h of allHypotheses) {
    latestByCause[h.cause] = h;
  }
  const hypothesisList = Object.values(latestByCause).sort(
    (a, b) => b.confidence - a.confidence
  );

  // Confidence score from report or top hypothesis
  const finalConfidence = report ? report.confidence : hypothesisList[0]?.confidence || 0;
  const statusCategory = report ? report.status : hypothesisList.length > 0 ? "evaluating" : "idle";

  // Arc calculations for calibrated confidence
  const radius = 45;
  const strokeWidth = 5;
  const circumference = Math.PI * radius; // Semi-circle arc
  const strokeDashoffset = circumference * (1 - Math.min(Math.max(finalConfidence, 0), 1));

  const getStatusColor = (val: number, status: string) => {
    if (status === "insufficient_evidence" || status === "inconclusive") return "#B45309";
    if (val >= 0.8) return "#15803D";
    if (val >= 0.5) return "#133E87";
    return "#DC2626";
  };

  const arcColor = getStatusColor(finalConfidence, statusCategory);

  return (
    <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E2E8F0] dark:border-[#2A2A2D] p-5 space-y-6 font-sans">
      {/* Header and Calibrated Confidence Arc */}
      <div className="flex flex-wrap items-center justify-between border-b border-[#E2E8F0] dark:border-[#2A2A2D] pb-4 gap-4">
        <div>
          <h2 className="text-xs font-bold uppercase tracking-wider text-[#0B2545] dark:text-[#F1F5F9]">
            Evidence Correlation & Hypothesis Arbitration
          </h2>
          <div className="text-[11px] text-[#475569] dark:text-[#94A3B8]">
            Mediator Consensus Iteration: {visibleEnvelopes[visibleEnvelopes.length - 1]?.context?.iteration ?? 0} &middot; Evaluated Hypotheses: {hypothesisList.length}
          </div>
        </div>

        {/* Confidence Gauge */}
        <div className="flex items-center gap-4 bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#E2E8F0] dark:border-[#2A2A2D] px-4 py-2">
          <div className="relative w-24 h-14 flex items-end justify-center" aria-hidden="true">
            <svg className="w-24 h-14 overflow-visible" viewBox="0 0 100 55">
              {/* Background Arc */}
              <path
                d="M 5 50 A 45 45 0 0 1 95 50"
                fill="none"
                stroke="currentColor"
                className="text-[#E2E8F0] dark:text-[#2A2A2D]"
                strokeWidth={strokeWidth}
                strokeLinecap="round"
              />
              {/* Foreground Arc */}
              <path
                d="M 5 50 A 45 45 0 0 1 95 50"
                fill="none"
                stroke={arcColor}
                strokeWidth={strokeWidth}
                strokeDasharray={circumference}
                strokeDashoffset={strokeDashoffset}
                strokeLinecap="round"
                style={{ transition: "stroke-dashoffset 250ms ease-out" }}
              />
            </svg>
            <div className="absolute bottom-0 text-center font-mono">
              <span className="text-sm font-bold text-[#0F172A] dark:text-[#F1F5F9]">
                {formatPercent(finalConfidence, 0)}
              </span>
            </div>
          </div>

          <div className="text-left">
            <div className="text-[10px] text-[#475569] dark:text-[#94A3B8] uppercase font-bold tracking-wider">
              Calibrated Confidence
            </div>
            <div className="text-xs font-bold uppercase tracking-wide" style={{ color: arcColor }}>
              {statusCategory.replace("_", " ")}
            </div>
          </div>
        </div>
      </div>

      {/* Hypothesis Scores Bars */}
      <div>
        <h3 className="text-xs font-bold uppercase tracking-wider text-[#0B2545] dark:text-[#F1F5F9] mb-3">
          Domain Hypothesis Scores & Weights
        </h3>

        {hypothesisList.length === 0 ? (
          <div className="text-xs text-[#475569] dark:text-[#94A3B8] font-mono py-4 text-center border border-dashed border-[#CBD5E1] dark:border-[#2A2A2D]">
            Awaiting domain specialist agent hypotheses...
          </div>
        ) : (
          <div className="space-y-3">
            {hypothesisList.map((h, i) => {
              const pct = Math.round(h.confidence * 100);
              const isLead = i === 0 && h.confidence >= 0.7;

              return (
                <div
                  key={h.id || i}
                  className="p-3 bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#E2E8F0] dark:border-[#2A2A2D] text-xs font-sans"
                >
                  <div className="flex items-center justify-between gap-2 mb-1.5 flex-wrap">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-[#0B2545] dark:text-[#3A86FF] font-mono font-bold">[{h.agent}]</span>
                      <span className="font-bold text-[#0F172A] dark:text-[#F1F5F9]">
                        {h.cause}
                      </span>
                      {isLead && (
                        <span className="px-2 py-0.5 bg-[#F0FDF4] border border-[#15803D]/40 text-[#15803D] dark:bg-[#14532D]/30 dark:text-[#86EFAC] text-[10px] font-bold uppercase tracking-wider">
                          Leading Cause
                        </span>
                      )}
                    </div>
                    <span className="font-mono font-bold text-[#0F172A] dark:text-[#F1F5F9]">
                      {formatPercent(h.confidence, 1)}
                    </span>
                  </div>

                  {/* Progress Bar */}
                  <div
                    className="w-full bg-[#E2E8F0] dark:bg-[#2A2A2D] h-2 mb-2 overflow-hidden"
                    role="progressbar"
                    aria-valuenow={pct}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-label={`Confidence for hypothesis ${h.cause}`}
                  >
                    <div
                      className="bg-[#0B2545] dark:bg-[#3A86FF] h-full transition-all duration-200 ease-out"
                      style={{ width: `${pct}%` }}
                    />
                  </div>

                  {/* Supporting / Refuting Breakdown */}
                  <div className="flex items-center justify-between text-[11px] text-[#475569] dark:text-[#94A3B8] font-mono">
                    <span>
                      Supporting Evidence: {h.supporting.length > 0 ? h.supporting.join(", ") : "none"}
                    </span>
                    <span>
                      Refuting: {h.refuting.length > 0 ? h.refuting.join(", ") : "0"}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Conflict Resolution & Arbitration Section */}
      <div className="border-t border-[#E2E8F0] dark:border-[#2A2A2D] pt-4">
        <h3 className="text-xs font-bold uppercase tracking-wider text-[#0B2545] dark:text-[#F1F5F9] mb-2">
          Arbitration & Precedence Rules
        </h3>

        {hypothesisList.length > 1 ? (
          <div className="p-3 bg-[#FFFBEB] dark:bg-[#78350F]/20 border border-[#B45309]/30 text-xs font-sans space-y-1">
            <div className="text-[#B45309] dark:text-[#FDE68A] font-bold flex items-center gap-2">
              <span>Arbitration Applied:</span>
              <span className="text-[11px] uppercase tracking-wider font-semibold text-[#475569] dark:text-[#94A3B8]">
                Multi-agent hypothesis divergence detected
              </span>
            </div>
            <div className="text-[11px] text-[#0F172A] dark:text-[#F1F5F9] font-mono">
              Precedence Rule: Physical layer (CRC/optics) and queue saturation signatures supersede downstream route flaps and transient ping jitter.
            </div>
          </div>
        ) : (
          <div className="text-xs text-[#475569] dark:text-[#94A3B8] font-mono py-2">
            No active cross-domain conflicts. Agent consensus verified across all specialist domains.
          </div>
        )}
      </div>

      {/* Inter-Agent Inquiries */}
      <div className="border-t border-[#E2E8F0] dark:border-[#2A2A2D] pt-4">
        <h3 className="text-xs font-bold uppercase tracking-wider text-[#0B2545] dark:text-[#F1F5F9] mb-3">
          Cross-Agent Evidence Inquiries ({allInquiries.length})
        </h3>

        {allInquiries.length === 0 ? (
          <div className="text-xs text-[#475569] dark:text-[#94A3B8] font-mono py-2">
            Zero cross-inquiries initiated during this diagnostic run.
          </div>
        ) : (
          <div className="space-y-2">
            {allInquiries.map((inq, idx) => (
              <div
                key={inq.id || idx}
                className="p-3 bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#E2E8F0] dark:border-[#2A2A2D] text-xs font-sans"
              >
                <div className="flex items-center justify-between text-[11px] text-[#475569] dark:text-[#94A3B8] mb-1 font-mono">
                  <span>
                    Query from <strong className="text-[#0B2545] dark:text-[#3A86FF]">{inq.fromAgent}</strong> to <strong className="text-[#0B2545] dark:text-[#3A86FF]">{inq.targetAgent}</strong>
                  </span>
                  <span>Target Entity: {inq.targetEntity}</span>
                </div>
                <div className="text-[#0F172A] dark:text-[#F1F5F9] italic font-serif">
                  &ldquo;{inq.question}&rdquo;
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
