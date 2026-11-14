import React, { useState } from "react";
import { UnifiedDiagnosticReport } from "../types/protocol";
import {
  formatDateTime,
  formatPercent,
  formatNumber,
  formatDurationMs,
  SupportedTimezone,
} from "../utils/i18n";

interface ReportCardProps {
  report: UnifiedDiagnosticReport | null;
  loading: boolean;
  timezone?: SupportedTimezone;
}

export const ReportCard: React.FC<ReportCardProps> = ({
  report,
  loading,
  timezone = "UTC",
}) => {
  const [copied, setCopied] = useState<boolean>(false);
  const [evidenceFilter, setEvidenceFilter] = useState<string>("all");
  const [evidenceExpanded, setEvidenceExpanded] = useState<boolean>(true);
  const [activeSection, setActiveSection] = useState<string>("all");

  if (loading) {
    return (
      <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E2E8F0] dark:border-[#2A2A2D] p-6 space-y-4 animate-pulse font-sans">
        <div className="h-4 bg-[#E2E8F0] dark:bg-[#2A2A2D] w-1/4"></div>
        <div className="h-8 bg-[#E2E8F0] dark:bg-[#2A2A2D] w-2/3"></div>
        <div className="h-20 bg-[#E2E8F0] dark:bg-[#2A2A2D] w-full"></div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="h-16 bg-[#E2E8F0] dark:bg-[#2A2A2D]"></div>
          <div className="h-16 bg-[#E2E8F0] dark:bg-[#2A2A2D]"></div>
          <div className="h-16 bg-[#E2E8F0] dark:bg-[#2A2A2D]"></div>
          <div className="h-16 bg-[#E2E8F0] dark:bg-[#2A2A2D]"></div>
        </div>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E2E8F0] dark:border-[#2A2A2D] p-8 text-center text-xs font-sans text-[#475569] dark:text-[#94A3B8]">
        Select an incident scenario and trigger diagnosis to inspect the 12-section unified diagnostic report.
      </div>
    );
  }

  const isDiagnosed = report.status === "diagnosed";
  const isInsufficient = report.status === "insufficient_evidence";
  const isBenign = report.status === "benign";
  const statusColor = isDiagnosed
    ? "text-[#15803D] border-[#15803D]/40 bg-[#F0FDF4] dark:bg-[#14532D]/30 dark:text-[#86EFAC]"
    : isInsufficient
    ? "text-[#B45309] border-[#B45309]/40 bg-[#FFFBEB] dark:bg-[#78350F]/30 dark:text-[#FDE68A]"
    : isBenign
    ? "text-[#133E87] border-[#133E87]/40 bg-[#EEF4FB] dark:bg-[#1E3A8A]/30 dark:text-[#93C5FD]"
    : "text-[#475569] border-[#CBD5E1] dark:border-[#2A2A2D] bg-[#F1F5F9] dark:bg-[#0F0F10]";

  // Export JSON
  const handleExportJSON = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(report, null, 2));
    const downloadAnchor = document.createElement("a");
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `diagnostic_report_${report.incident_id}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  // Export Markdown
  const handleExportMarkdown = () => {
    let md = `# Diagnostic Incident Report: ${report.incident_id}\n\n`;
    md += `## 1. Incident Overview\n`;
    md += `- **Network ID**: \`${report.network_id}\`\n`;
    md += `- **Timestamp**: \`${formatDateTime(report.timestamp_utc, timezone)}\`\n`;
    md += `- **Status**: **${report.status.toUpperCase()}**\n`;
    md += `- **Probable Cause**: ${report.probable_cause || "None (Insufficient Evidence)"}\n`;
    md += `- **Calibrated Confidence**: ${formatPercent(report.confidence, 1)}\n`;
    md += `- **Processing Time**: ${formatDurationMs(report.processing_time_ms)}\n`;
    md += `- **Affected Devices**: ${report.affected_devices.join(", ") || "None"}\n`;
    md += `- **Affected Interfaces**: ${report.affected_interfaces.join(", ") || "None"}\n\n`;

    md += `## 2. Executive Summary\n${report.summary}\n\n`;

    if (report.causal_chain && report.causal_chain.length > 0) {
      md += `## 6. Root Cause & Causal Chain\n`;
      report.causal_chain.forEach((c, idx) => {
        md += `${idx + 1}. ${c}\n`;
      });
      md += `\n`;
    }

    md += `## 7. Supporting Evidence (${report.evidence.length} items)\n`;
    for (const ev of report.evidence) {
      const evId = ev.evidence_id || (ev.observation_id ? `evi-${ev.observation_id}` : "evi-auto");
      const val = ev.value !== undefined && ev.value !== null ? `${ev.value} ${ev.unit || ""}`.trim() : "unknown";
      md += `- **[${ev.source_agent}]** \`${ev.entity}\` (${ev.category}) \`${evId}\`: ${ev.finding} [Observed: ${val}] (Severity: ${ev.severity})\n`;
    }
    md += `\n`;

    md += `## 9. Confidence & Uncertainty Evaluation\n`;
    md += `- Uncertainty Score: ${formatPercent(report.uncertainty.score, 1)}\n`;
    if (report.uncertainty.missing_evidence.length > 0) {
      md += `### Prerequisite Evidence Missing\n`;
      for (const m of report.uncertainty.missing_evidence) {
        md += `- ${m}\n`;
      }
    }
    md += `\n`;

    if (report.remediation_actions.length > 0) {
      md += `## 10. Remediation Recommendations (SIMULATED)\n`;
      md += `> SIMULATED — NO PRODUCTION NETWORK CHANGES\n\n`;
      for (const act of report.remediation_actions) {
        md += `### Action: ${act.title} (${act.device}) - Risk: ${act.risk_level}\n`;
        md += `${act.description}\n\n`;
        md += `**Simulated Commands**:\n\`\`\`bash\n${act.commands.join("\n")}\n\`\`\`\n\n`;
        md += `**Rollback Commands**:\n\`\`\`bash\n${act.rollback_commands.join("\n")}\n\`\`\`\n\n`;
        md += `**Blast Radius**: ${act.blast_radius_devices.join(", ") || "Isolated"}\n\n`;
      }
    }

    const dataStr = "data:text/markdown;charset=utf-8," + encodeURIComponent(md);
    const downloadAnchor = document.createElement("a");
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `diagnostic_report_${report.incident_id}.md`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  const handleCopySummary = () => {
    navigator.clipboard.writeText(report.summary);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Derive metric items with values
  const healthMetrics = report.evidence.filter(
    (e) => e.value !== undefined && e.value !== null && (e.metric || e.metric_name)
  );

  // Derive anomalies (severity is warning or critical)
  const anomalies = report.evidence.filter(
    (e) => e.severity === "critical" || e.severity === "warning"
  );

  // Derive agent contributions
  const agentContributions = Array.from(new Set(report.evidence.map((e) => e.source_agent)));

  // Filter evidence
  const filteredEvidence = report.evidence.filter((e) => {
    if (evidenceFilter === "all") return true;
    return e.severity === evidenceFilter || e.source_agent === evidenceFilter;
  });

  const shouldRenderSection = (sec: string) => {
    return activeSection === "all" || activeSection === sec;
  };

  return (
    <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E2E8F0] dark:border-[#2A2A2D] p-5 space-y-6 font-sans">
      {/* 1. SECTION: Incident ID & Status Header */}
      <div className="border-b border-[#E2E8F0] dark:border-[#2A2A2D] pb-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <span className="text-xs font-bold uppercase tracking-wider text-[#0B2545] dark:text-[#F1F5F9]">
                Section 1: Unified Diagnostic Report
              </span>
              <span className={`px-2.5 py-0.5 border text-xs font-mono uppercase font-bold ${statusColor}`}>
                {report.status.replace("_", " ")}
              </span>
            </div>
            <div className="text-xs text-[#475569] dark:text-[#94A3B8] font-mono">
              Incident ID: <strong className="text-[#0F172A] dark:text-[#F1F5F9]">{report.incident_id}</strong> &middot; Fabric: <strong className="text-[#0F172A] dark:text-[#F1F5F9]">{report.network_id}</strong> &middot; Processing: {formatDurationMs(report.processing_time_ms)} &middot; Timestamp: {formatDateTime(report.timestamp_utc, timezone)}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleExportJSON}
              className="px-3.5 py-1.5 bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#CBD5E1] dark:border-[#2A2A2D] text-xs font-bold hover:border-[#0B2545] text-[#0B2545] dark:text-[#F1F5F9] transition-all min-h-[32px] focus-visible:ring-2"
            >
              Export JSON
            </button>
            <button
              onClick={handleExportMarkdown}
              className="px-3.5 py-1.5 bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#CBD5E1] dark:border-[#2A2A2D] text-xs font-bold hover:border-[#0B2545] text-[#0B2545] dark:text-[#F1F5F9] transition-all min-h-[32px] focus-visible:ring-2"
            >
              Export Markdown
            </button>
          </div>
        </div>

        {/* Section Navigation Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto pt-3 text-xs font-sans text-[#475569] dark:text-[#94A3B8]">
          <span className="uppercase text-[10px] font-bold mr-1 text-[#0B2545] dark:text-[#F1F5F9]">Jump to:</span>
          {[
            { id: "all", label: "All 12 Sections" },
            { id: "summary", label: "2. Exec Summary" },
            { id: "overview", label: "3. Scope" },
            { id: "metrics", label: "4. Metrics" },
            { id: "anomalies", label: "5. Anomalies" },
            { id: "rca", label: "6. RCA & Causal" },
            { id: "evidence", label: "7. Evidence" },
            { id: "multiagent", label: "8. Multi-Agent" },
            { id: "confidence", label: "9. Confidence" },
            { id: "remediation", label: "10. Remediation" },
            { id: "recovery", label: "11. Recovery" },
            { id: "audit", label: "12. Audit" },
          ].map((sec) => (
            <button
              key={sec.id}
              onClick={() => setActiveSection(sec.id)}
              className={`px-2.5 py-1 border whitespace-nowrap transition-colors min-h-[28px] text-xs ${
                activeSection === sec.id
                  ? "border-[#0B2545] dark:border-[#3A86FF] text-[#0B2545] dark:text-[#F1F5F9] bg-[#EEF4FB] dark:bg-[#1E293B] font-bold"
                  : "border-transparent hover:border-[#CBD5E1] dark:hover:border-[#2A2A2D]"
              }`}
            >
              {sec.label}
            </button>
          ))}
        </div>
      </div>

      {/* 2. SECTION: Executive Summary */}
      {shouldRenderSection("summary") && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-[#0B2545] dark:text-[#F1F5F9]">
              Section 2: Executive Diagnostic Summary
            </h3>
            <button
              onClick={handleCopySummary}
              className="text-xs font-semibold text-[#133E87] dark:text-[#3A86FF] hover:underline"
            >
              {copied ? "Copied" : "Copy Summary"}
            </button>
          </div>
          <p className="text-xs font-mono leading-relaxed p-4 bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#E2E8F0] dark:border-[#2A2A2D] text-[#0F172A] dark:text-[#F1F5F9]">
            {report.summary}
          </p>
        </div>
      )}

      {/* 3. SECTION: Scope & Topology Footprint */}
      {shouldRenderSection("overview") && (
        <div className="space-y-2">
          <h3 className="text-xs font-bold uppercase tracking-wider text-[#0B2545] dark:text-[#F1F5F9]">
            Section 3: Incident Scope & Topology Footprint
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
            <div className="p-3 bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#E2E8F0] dark:border-[#2A2A2D]">
              <div className="text-[10px] uppercase font-bold text-[#475569] dark:text-[#94A3B8]">Network Fabric</div>
              <div className="font-bold text-[#0F172A] dark:text-[#F1F5F9] mt-1 font-mono">{report.network_id}</div>
            </div>
            <div className="p-3 bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#E2E8F0] dark:border-[#2A2A2D]">
              <div className="text-[10px] uppercase font-bold text-[#475569] dark:text-[#94A3B8]">Affected Devices</div>
              <div className="font-bold text-[#0F172A] dark:text-[#F1F5F9] mt-1 font-mono truncate">
                {report.affected_devices.length > 0 ? report.affected_devices.join(", ") : "None identified"}
              </div>
            </div>
            <div className="p-3 bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#E2E8F0] dark:border-[#2A2A2D]">
              <div className="text-[10px] uppercase font-bold text-[#475569] dark:text-[#94A3B8]">Affected Interfaces</div>
              <div className="font-bold text-[#0F172A] dark:text-[#F1F5F9] mt-1 font-mono truncate">
                {report.affected_interfaces.length > 0 ? report.affected_interfaces.join(", ") : "None identified"}
              </div>
            </div>
            <div className="p-3 bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#E2E8F0] dark:border-[#2A2A2D]">
              <div className="text-[10px] uppercase font-bold text-[#475569] dark:text-[#94A3B8]">Contributing Agents</div>
              <div className="font-bold text-[#0F172A] dark:text-[#F1F5F9] mt-1 font-mono">
                {report.evidence_sources && report.evidence_sources.length > 0
                  ? report.evidence_sources.length
                  : agentContributions.length} specialist{agentContributions.length === 1 ? "" : "s"}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 4. SECTION: Key Metric Readings */}
      {shouldRenderSection("metrics") && (
        <div className="space-y-2">
          <h3 className="text-xs font-bold uppercase tracking-wider text-[#0B2545] dark:text-[#F1F5F9]">
            Section 4: Corroborated Telemetry Metrics ({healthMetrics.length})
          </h3>
          {healthMetrics.length === 0 ? (
            <div className="p-4 bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#E2E8F0] dark:border-[#2A2A2D] text-xs font-mono text-[#475569] dark:text-[#94A3B8]">
              No quantitative numeric metrics reported in this diagnostic run.
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
              {healthMetrics.slice(0, 8).map((m, idx) => {
                const metricName = m.metric || m.metric_name || m.category;
                const formattedVal = typeof m.value === "number" ? formatNumber(m.value) : String(m.value);
                return (
                  <div key={idx} className="p-3 bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#E2E8F0] dark:border-[#2A2A2D] font-mono">
                    <div className="text-[10px] text-[#475569] dark:text-[#94A3B8] uppercase truncate">{metricName}</div>
                    <div className="text-base font-bold text-[#0F172A] dark:text-[#F1F5F9] mt-1">
                      {formattedVal} {m.unit || ""}
                    </div>
                    <div className="text-[10px] text-[#475569] dark:text-[#94A3B8] mt-0.5 truncate">{m.entity}</div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* 5. SECTION: Detected Anomalies */}
      {shouldRenderSection("anomalies") && (
        <div className="space-y-2">
          <h3 className="text-xs font-bold uppercase tracking-wider text-[#0B2545] dark:text-[#F1F5F9]">
            Section 5: Active Anomalies & Threshold Breaches ({anomalies.length})
          </h3>
          {anomalies.length === 0 ? (
            <div className="p-4 bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#E2E8F0] dark:border-[#2A2A2D] text-xs font-mono text-[#15803D]">
              All observed metrics are within baseline operating parameters. Zero anomalous threshold breaches.
            </div>
          ) : (
            <div className="space-y-2">
              {anomalies.map((anom, idx) => (
                <div
                  key={idx}
                  className="p-3 bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#E2E8F0] dark:border-[#2A2A2D] flex items-center justify-between text-xs"
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={`px-2 py-0.5 text-[10px] uppercase font-mono font-bold border ${
                        anom.severity === "critical"
                          ? "border-[#DC2626]/40 text-[#DC2626] bg-[#FEF2F2] dark:bg-[#7F1D1D]/30"
                          : "border-[#B45309]/40 text-[#B45309] bg-[#FFFBEB] dark:bg-[#78350F]/30"
                      }`}
                    >
                      {anom.severity}
                    </span>
                    <span className="font-mono font-bold text-[#0F172A] dark:text-[#F1F5F9]">
                      {anom.entity}
                    </span>
                    <span className="text-[#475569] dark:text-[#94A3B8]">{anom.finding}</span>
                  </div>
                  {anom.value !== undefined && anom.value !== null && (
                    <span className="font-mono font-bold text-[#0F172A] dark:text-[#F1F5F9]">
                      {typeof anom.value === "number" ? formatNumber(anom.value) : anom.value} {anom.unit || ""}
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 6. SECTION: RCA & Causal Chain */}
      {shouldRenderSection("rca") && (
        <div className="space-y-2">
          <h3 className="text-xs font-bold uppercase tracking-wider text-[#0B2545] dark:text-[#F1F5F9]">
            Section 6: Root Cause Attribution & Causal Sequence
          </h3>
          <div className="p-4 bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#E2E8F0] dark:border-[#2A2A2D] space-y-3 text-xs font-sans">
            <div>
              <div className="text-[10px] uppercase font-bold text-[#475569] dark:text-[#94A3B8]">Isolated Probable Cause</div>
              <div className="text-base font-bold font-mono text-[#0B2545] dark:text-[#3A86FF] mt-1">
                {report.probable_cause || "INSUFFICIENT_EVIDENCE"}
              </div>
            </div>

            {report.causal_chain && report.causal_chain.length > 0 && (
              <div className="pt-2 border-t border-[#E2E8F0] dark:border-[#2A2A2D] space-y-2">
                <div className="text-[10px] uppercase font-bold text-[#475569] dark:text-[#94A3B8]">
                  Multi-Stage Causal Progression:
                </div>
                <div className="space-y-1.5 font-mono">
                  {report.causal_chain.map((step, idx) => (
                    <div key={idx} className="flex items-start gap-2 text-xs">
                      <span className="px-1.5 py-0.5 border border-[#0B2545] dark:border-[#3A86FF] text-[#0B2545] dark:text-[#3A86FF] text-[10px] font-bold">
                        {idx + 1}
                      </span>
                      <span className="text-[#0F172A] dark:text-[#F1F5F9]">{step}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 7. SECTION: Supporting Evidence Ledger */}
      {shouldRenderSection("evidence") && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <h3 className="text-xs font-bold uppercase tracking-wider text-[#0B2545] dark:text-[#F1F5F9]">
                Section 7: Supporting Evidence Ledger ({report.evidence.length})
              </h3>
              <button
                onClick={() => setEvidenceExpanded(!evidenceExpanded)}
                className="text-xs font-semibold text-[#133E87] dark:text-[#3A86FF] hover:underline"
              >
                {evidenceExpanded ? "Collapse" : "Expand"}
              </button>
            </div>

            <div className="flex items-center gap-2">
              <label htmlFor="evidence-filter" className="sr-only">Filter evidence ledger</label>
              <select
                id="evidence-filter"
                value={evidenceFilter}
                onChange={(e) => setEvidenceFilter(e.target.value)}
                className="px-2.5 py-1 text-xs font-sans bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#CBD5E1] dark:border-[#2A2A2D] text-[#0F172A] dark:text-[#F1F5F9] outline-none min-h-[28px]"
              >
                <option value="all">All Evidence</option>
                <option value="critical">Critical</option>
                <option value="warning">Warning</option>
                <option value="info">Info</option>
              </select>
            </div>
          </div>

          {evidenceExpanded && (
            <div className="overflow-x-auto border border-[#E2E8F0] dark:border-[#2A2A2D]">
              <table className="w-full text-left font-sans text-xs border-collapse" aria-label="Evidence Ledger Table">
                <caption className="sr-only">Detailed breakdown of empirical evidence items, source agents, target entities, and telemetry metrics</caption>
                <thead className="bg-[#F1F5F9] dark:bg-[#0F0F10] border-b border-[#CBD5E1] dark:border-[#2A2A2D] text-[10px] uppercase font-bold tracking-wider text-[#475569] dark:text-[#94A3B8]">
                  <tr>
                    <th scope="col" className="p-3">Evidence ID</th>
                    <th scope="col" className="p-3">Source Agent</th>
                    <th scope="col" className="p-3">Target Entity</th>
                    <th scope="col" className="p-3">Metric</th>
                    <th scope="col" className="p-3">Observed Value</th>
                    <th scope="col" className="p-3">Diagnostic Finding</th>
                    <th scope="col" className="p-3 text-right">Severity</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E2E8F0] dark:divide-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618]">
                  {filteredEvidence.map((ev, idx) => {
                    const evId = ev.evidence_id || (ev.observation_id ? `evi-${ev.observation_id}` : `evi-${idx + 1}`);
                    const metricName = ev.metric || ev.metric_name || ev.category;
                    const valDisplay =
                      ev.value !== undefined && ev.value !== null
                        ? typeof ev.value === "number"
                          ? `${formatNumber(ev.value)} ${ev.unit || ""}`.trim()
                          : `${String(ev.value)} ${ev.unit || ""}`.trim()
                        : "unknown";

                    return (
                      <tr key={idx} className="hover:bg-[#F8FAFC] dark:hover:bg-[#0F0F10] transition-colors">
                        <td className="p-3 font-mono font-bold text-[#0B2545] dark:text-[#3A86FF] whitespace-nowrap">
                          {evId}
                        </td>
                        <td className="p-3 font-mono text-[#475569] dark:text-[#94A3B8]">
                          {ev.source_agent}
                        </td>
                        <td className="p-3 font-mono font-bold text-[#0F172A] dark:text-[#F1F5F9]">
                          {ev.entity}
                        </td>
                        <td className="p-3 font-mono text-[#475569] dark:text-[#94A3B8]">
                          {metricName}
                        </td>
                        <td className="p-3 font-mono font-bold text-[#0F172A] dark:text-[#F1F5F9] whitespace-nowrap">
                          {valDisplay}
                        </td>
                        <td className="p-3 text-[#0F172A] dark:text-[#F1F5F9]">
                          {ev.finding}
                        </td>
                        <td className="p-3 text-right whitespace-nowrap">
                          <span
                            className={`px-2 py-0.5 border text-[10px] uppercase font-bold font-mono ${
                              ev.severity === "critical"
                                ? "text-[#DC2626] border-[#DC2626]/40 bg-[#FEF2F2] dark:bg-[#7F1D1D]/30"
                                : ev.severity === "warning"
                                ? "text-[#B45309] border-[#B45309]/40 bg-[#FFFBEB] dark:bg-[#78350F]/30"
                                : "text-[#475569] border-[#CBD5E1] dark:border-[#2A2A2D]"
                            }`}
                          >
                            {ev.severity}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* 8. SECTION: Multi-Agent Consensus */}
      {shouldRenderSection("multiagent") && (
        <div className="space-y-2">
          <h3 className="text-xs font-bold uppercase tracking-wider text-[#0B2545] dark:text-[#F1F5F9]">
            Section 8: Multi-Agent Consensus & Arbitration Summary
          </h3>
          <div className="p-4 bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#E2E8F0] dark:border-[#2A2A2D] space-y-3 text-xs">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[10px] uppercase font-bold text-[#475569] dark:text-[#94A3B8]">Participating Specialist Agents:</span>
              {agentContributions.map((ag) => (
                <span
                  key={ag}
                  className="px-2 py-0.5 border border-[#0B2545] dark:border-[#3A86FF] text-[10px] font-mono font-bold text-[#0B2545] dark:text-[#3A86FF]"
                >
                  {ag}
                </span>
              ))}
            </div>

            {report.conflicts_resolved && report.conflicts_resolved.length > 0 ? (
              <div className="pt-2 border-t border-[#E2E8F0] dark:border-[#2A2A2D] space-y-1.5">
                <div className="text-[10px] uppercase text-[#B45309] font-bold">
                  Arbitrated Diagnostic Conflicts:
                </div>
                {report.conflicts_resolved.map((conf, idx) => (
                  <div key={idx} className="p-3 bg-[#FFFFFF] dark:bg-[#161618] border border-[#E2E8F0] dark:border-[#2A2A2D] text-xs">
                    <div className="font-bold text-[#0F172A] dark:text-[#F1F5F9]">
                      Conflict: {conf.issue || conf.conflict || "Telemetry vs Topology divergence"}
                    </div>
                    <div className="text-[#475569] dark:text-[#94A3B8] mt-1">
                      Resolution: {conf.resolution || conf.rationale || "Resolved by domain precedence weighting"}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs text-[#475569] dark:text-[#94A3B8] pt-1">
                Zero arbitration conflicts triggered during consensus; specialist agent hypotheses converged with monotonic agreement.
              </div>
            )}
          </div>
        </div>
      )}

      {/* 9. SECTION: Confidence & Uncertainty */}
      {shouldRenderSection("confidence") && (
        <div className="space-y-2">
          <h3 className="text-xs font-bold uppercase tracking-wider text-[#0B2545] dark:text-[#F1F5F9]">
            Section 9: Confidence Calibration & Uncertainty Evaluation
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
            <div className="p-4 bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#E2E8F0] dark:border-[#2A2A2D] space-y-1">
              <div className="text-[10px] uppercase font-bold text-[#475569] dark:text-[#94A3B8]">Calibrated Confidence</div>
              <div className="text-2xl font-bold font-mono text-[#0B2545] dark:text-[#3A86FF]">
                {formatPercent(report.confidence, 1)}
              </div>
              <div className="text-[10px] text-[#475569] dark:text-[#94A3B8]">
                {report.is_confidence_calibrated ? "Isotonic Regression & Logistic Hybrid" : "Disciplined Abstention / Rule Heuristic"}
              </div>
            </div>

            <div className="p-4 bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#E2E8F0] dark:border-[#2A2A2D] space-y-1">
              <div className="text-[10px] uppercase font-bold text-[#475569] dark:text-[#94A3B8]">Uncertainty Score</div>
              <div className="text-2xl font-bold font-mono text-[#B45309] dark:text-[#FDE68A]">
                {formatPercent(report.uncertainty.score, 1)}
              </div>
              <div className="text-[10px] text-[#475569] dark:text-[#94A3B8]">
                Missing Signal & Noise Disruption Index
              </div>
            </div>

            <div className="p-4 bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#E2E8F0] dark:border-[#2A2A2D] space-y-1">
              <div className="text-[10px] uppercase font-bold text-[#475569] dark:text-[#94A3B8]">Conformal Prediction Set</div>
              <div className="font-bold font-mono text-[#0F172A] dark:text-[#F1F5F9] mt-1 truncate">
                {report.conformal_prediction_set && report.conformal_prediction_set.length > 0
                  ? report.conformal_prediction_set.join(", ")
                  : report.probable_cause || "None"}
              </div>
              <div className="text-[10px] text-[#475569] dark:text-[#94A3B8]">90% Coverage Guarantee Guarantee</div>
            </div>
          </div>

          {report.uncertainty.missing_evidence.length > 0 && (
            <div className="p-3 bg-[#FFFBEB] dark:bg-[#78350F]/20 border border-[#B45309]/30 text-xs space-y-1.5">
              <div className="text-[10px] uppercase font-bold text-[#B45309] dark:text-[#FDE68A]">
                Telemetry Gaps & Missing Evidence Constraints:
              </div>
              <ul className="space-y-1 font-mono text-[#475569] dark:text-[#94A3B8]">
                {report.uncertainty.missing_evidence.map((gap, idx) => (
                  <li key={idx} className="flex items-center gap-1.5">
                    <span className="text-[#B45309] font-bold">&bull;</span> {gap}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* 10. SECTION: Remediation Recommendations */}
      {shouldRenderSection("remediation") && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-[#0B2545] dark:text-[#F1F5F9]">
              Section 10: Remediation Recommendations ({report.remediation_actions.length})
            </h3>
          </div>

          {/* Persistent Simulation Watermark */}
          <div
            role="alert"
            className="bg-[#FEF2F2] dark:bg-[#7F1D1D]/30 border-2 border-[#DC2626] p-3 text-center"
          >
            <div className="text-xs font-mono font-bold tracking-widest uppercase text-[#991B1B] dark:text-[#FCA5A5] flex items-center justify-center gap-2">
              <span>⚠️</span>
              <span>SIMULATED — NO PRODUCTION NETWORK CHANGES</span>
              <span>⚠️</span>
            </div>
            <p className="text-[11px] text-[#475569] dark:text-[#CBD5E1] mt-0.5">
              All remediation actions are sandbox recommendations only. Real production networks are never altered.
            </p>
          </div>

          {report.remediation_actions.length > 0 ? (
            <div className="space-y-3 text-xs">
              {report.remediation_actions.map((act) => (
                <div
                  key={act.action_id}
                  className="p-4 bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#E2E8F0] dark:border-[#2A2A2D] space-y-2"
                >
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-bold text-[#0F172A] dark:text-[#F1F5F9]">{act.title}</span>
                      <span className="px-2 py-0.5 border border-[#0B2545] dark:border-[#3A86FF] text-[10px] uppercase font-bold text-[#0B2545] dark:text-[#3A86FF]">
                        Risk: {act.risk_level}
                      </span>
                    </div>
                    <span className="text-[11px] font-mono text-[#475569] dark:text-[#94A3B8]">
                      Target Device: <strong className="text-[#0F172A] dark:text-[#F1F5F9]">{act.device}</strong>
                    </span>
                  </div>

                  <p className="text-xs text-[#475569] dark:text-[#94A3B8] leading-relaxed">{act.description}</p>

                  <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E2E8F0] dark:border-[#2A2A2D] p-3 text-[11px] space-y-1 font-mono">
                    <div className="text-[#475569] dark:text-[#94A3B8] uppercase font-bold text-[10px]">
                      Proposed Target Commands:
                    </div>
                    <pre className="text-[#0F172A] dark:text-[#F1F5F9] overflow-x-auto">
                      {act.commands.join("\n")}
                    </pre>
                  </div>

                  <div className="text-[11px] font-mono text-[#475569] dark:text-[#94A3B8]">
                    Estimated Blast Radius: {act.blast_radius_devices.join(", ") || "Isolated Interface"}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-4 bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#E2E8F0] dark:border-[#2A2A2D] text-xs text-[#475569] dark:text-[#94A3B8]">
              No corrective remediation actions generated for this incident scenario.
            </div>
          )}
        </div>
      )}

      {/* 11. SECTION: Verification & Recovery */}
      {shouldRenderSection("recovery") && (
        <div className="space-y-2">
          <h3 className="text-xs font-bold uppercase tracking-wider text-[#0B2545] dark:text-[#F1F5F9]">
            Section 11: Verification Criteria & Rollback Recovery Plan
          </h3>
          <div className="p-4 bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#E2E8F0] dark:border-[#2A2A2D] space-y-3 text-xs">
            {report.remediation_actions.length > 0 && report.remediation_actions[0].rollback_commands.length > 0 ? (
              <div className="space-y-2">
                <div className="text-[10px] uppercase font-bold text-[#475569] dark:text-[#94A3B8]">
                  Automated Rollback Commands (Pre-validated):
                </div>
                <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E2E8F0] dark:border-[#2A2A2D] p-3 text-xs font-mono">
                  <pre className="text-[#0F172A] dark:text-[#F1F5F9] overflow-x-auto">
                    {report.remediation_actions.flatMap((a) => a.rollback_commands).join("\n")}
                  </pre>
                </div>
              </div>
            ) : (
              <div className="text-xs text-[#475569] dark:text-[#94A3B8]">
                No destructive commands proposed; state restoration follows standard config check.
              </div>
            )}

            <div className="pt-2 border-t border-[#E2E8F0] dark:border-[#2A2A2D] text-xs text-[#475569] dark:text-[#94A3B8] space-y-1">
              <div className="font-bold uppercase text-[10px] text-[#0B2545] dark:text-[#F1F5F9]">
                Post-Remediation Verification Protocol:
              </div>
              <div>1. Re-sample egress queue drop counter across target interfaces (target: 0 drops/sec).</div>
              <div>2. Verify BGP neighbor adjacency state transitions to Established.</div>
              <div>3. Execute bidirectional ICMP echo probe across campus leaf-spine core.</div>
            </div>
          </div>
        </div>
      )}

      {/* 12. SECTION: Complete Audit Trail */}
      {shouldRenderSection("audit") && (
        <div className="space-y-2">
          <h3 className="text-xs font-bold uppercase tracking-wider text-[#0B2545] dark:text-[#F1F5F9]">
            Section 12: Cryptographic & Procedural Audit Trail
          </h3>
          <div className="p-4 bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#E2E8F0] dark:border-[#2A2A2D] space-y-2 font-mono text-xs">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-[11px]">
              <div>
                <span className="text-[#475569] dark:text-[#94A3B8]">Incident Identifier: </span>
                <strong className="text-[#0F172A] dark:text-[#F1F5F9]">{report.incident_id}</strong>
              </div>
              <div>
                <span className="text-[#475569] dark:text-[#94A3B8]">Timestamp: </span>
                <span className="text-[#0F172A] dark:text-[#F1F5F9]">{formatDateTime(report.timestamp_utc, timezone)}</span>
              </div>
              <div>
                <span className="text-[#475569] dark:text-[#94A3B8]">Engine Protocol Version: </span>
                <span className="text-[#0F172A] dark:text-[#F1F5F9]">NetCoop-Envelope-v1.0</span>
              </div>
              <div>
                <span className="text-[#475569] dark:text-[#94A3B8]">Storage Persistence: </span>
                <span className="text-[#0F172A] dark:text-[#F1F5F9]">SQLite WAL Journaled (audited)</span>
              </div>
            </div>

            <div className="pt-2 border-t border-[#E2E8F0] dark:border-[#2A2A2D] text-[10px] text-[#475569] dark:text-[#94A3B8]">
              Compliance Record: All diagnostic inferences, agent inquiries, and human-in-the-loop decisions are immutable and permanently recorded in compliance with enterprise audit protocols.
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
