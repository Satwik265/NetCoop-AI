import React, { useState } from "react";
import { UnifiedDiagnosticReport } from "../types/protocol";

interface ReportCardProps {
  report: UnifiedDiagnosticReport | null;
  loading: boolean;
}

export const ReportCard: React.FC<ReportCardProps> = ({ report, loading }) => {
  const [copied, setCopied] = useState<boolean>(false);
  const [evidenceFilter, setEvidenceFilter] = useState<string>("all");
  const [evidenceExpanded, setEvidenceExpanded] = useState<boolean>(true);
  const [activeSection, setActiveSection] = useState<string>("all");

  if (loading) {
    return (
      <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D] p-6 space-y-4 animate-pulse font-mono">
        <div className="h-4 bg-[#E5E5E3] dark:bg-[#2A2A2D] w-1/4"></div>
        <div className="h-8 bg-[#E5E5E3] dark:bg-[#2A2A2D] w-2/3"></div>
        <div className="h-20 bg-[#E5E5E3] dark:bg-[#2A2A2D] w-full"></div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="h-16 bg-[#E5E5E3] dark:bg-[#2A2A2D]"></div>
          <div className="h-16 bg-[#E5E5E3] dark:bg-[#2A2A2D]"></div>
          <div className="h-16 bg-[#E5E5E3] dark:bg-[#2A2A2D]"></div>
          <div className="h-16 bg-[#E5E5E3] dark:bg-[#2A2A2D]"></div>
        </div>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D] p-8 text-center text-xs font-mono text-[#6B6B66] dark:text-[#888884]">
        Select an incident scenario and trigger diagnosis to inspect the 12-section unified diagnostic report.
      </div>
    );
  }

  const isDiagnosed = report.status === "diagnosed";
  const isInsufficient = report.status === "insufficient_evidence";
  const statusColor = isDiagnosed
    ? "text-[#5E7A6A] border-[#5E7A6A]/30 bg-[#5E7A6A]/10"
    : isInsufficient
    ? "text-[#A08A5B] border-[#A08A5B]/30 bg-[#A08A5B]/10"
    : "text-[#6B6B66] border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10]";

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
    md += `- **Timestamp (UTC)**: \`${report.timestamp_utc}\`\n`;
    md += `- **Status**: **${report.status.toUpperCase()}**\n`;
    md += `- **Probable Cause**: ${report.probable_cause || "None (Insufficient Evidence)"}\n`;
    md += `- **Calibrated Confidence**: ${(report.confidence * 100).toFixed(1)}%\n`;
    md += `- **Processing Time**: ${report.processing_time_ms.toFixed(2)} ms\n`;
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
      md += `- **[${ev.source_agent}]** \`${ev.entity}\` (${ev.category}): ${ev.finding}`;
      if (ev.value !== undefined && ev.value !== null) {
        md += ` [Observed: ${ev.value} ${ev.unit || ""}]`;
      }
      md += ` (Severity: ${ev.severity})\n`;
    }
    md += `\n`;

    md += `## 9. Confidence & Uncertainty Evaluation\n`;
    md += `- Uncertainty Score: ${(report.uncertainty.score * 100).toFixed(1)}%\n`;
    if (report.uncertainty.missing_evidence.length > 0) {
      md += `### Prerequisite Evidence Missing\n`;
      for (const m of report.uncertainty.missing_evidence) {
        md += `- ${m}\n`;
      }
    }
    md += `\n`;

    if (report.remediation_actions.length > 0) {
      md += `## 10. Remediation Recommendations\n`;
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
    (e) => e.value !== undefined && e.value !== null && e.metric_name
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
    <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D] p-5 space-y-6">
      {/* 1. SECTION: Incident ID & Status Header */}
      <div className="border-b border-[#E5E5E3] dark:border-[#2A2A2D] pb-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-mono font-bold uppercase tracking-wider text-[#111111] dark:text-[#EDEDEA]">
                Section 1: Final Unified Diagnostic Report
              </span>
              <span className={`px-2 py-0.5 border text-[10px] font-mono uppercase font-semibold ${statusColor}`}>
                {report.status.replace("_", " ")}
              </span>
            </div>
            <div className="text-xs text-[#6B6B66] dark:text-[#888884] font-mono">
              Incident ID: <span className="font-semibold text-[#111111] dark:text-[#EDEDEA]">{report.incident_id}</span> | Fabric: <span className="font-semibold text-[#111111] dark:text-[#EDEDEA]">{report.network_id}</span> | Latency: {report.processing_time_ms.toFixed(1)}ms
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleExportJSON}
              className="px-3 py-1 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] text-xs font-mono hover:border-[#475569] text-[#111111] dark:text-[#EDEDEA] transition-all"
            >
              Export JSON
            </button>
            <button
              onClick={handleExportMarkdown}
              className="px-3 py-1 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] text-xs font-mono hover:border-[#475569] text-[#111111] dark:text-[#EDEDEA] transition-all"
            >
              Export Markdown
            </button>
          </div>
        </div>

        {/* Section Navigation Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto pt-3 text-[10px] font-mono text-[#6B6B66] dark:text-[#888884]">
          <span className="uppercase text-[9px] mr-1">Jump to:</span>
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
              className={`px-2 py-0.5 border whitespace-nowrap transition-colors ${
                activeSection === sec.id
                  ? "border-[#475569] text-[#111111] dark:text-[#EDEDEA] bg-[#FAFAF9] dark:bg-[#0F0F10] font-semibold"
                  : "border-transparent hover:border-[#E5E5E3] dark:hover:border-[#2A2A2D]"
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
            <span className="text-xs font-semibold uppercase tracking-wider font-mono text-[#6B6B66] dark:text-[#888884]">
              Section 2: Executive Summary
            </span>
            <button
              onClick={handleCopySummary}
              className="text-[10px] font-mono text-[#475569] hover:underline"
            >
              {copied ? "Copied" : "Copy Summary"}
            </button>
          </div>
          <p className="text-xs font-mono leading-relaxed p-3.5 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] text-[#111111] dark:text-[#EDEDEA]">
            {report.summary}
          </p>
        </div>
      )}

      {/* 3. SECTION: Incident Overview & Scope */}
      {shouldRenderSection("overview") && (
        <div className="space-y-2">
          <span className="text-xs font-semibold uppercase tracking-wider font-mono text-[#6B6B66] dark:text-[#888884]">
            Section 3: Incident Scope & Topology Footprint
          </span>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 font-mono text-xs">
            <div className="p-3 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D]">
              <div className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">Network Fabric</div>
              <div className="font-bold text-[#111111] dark:text-[#EDEDEA] mt-1">{report.network_id}</div>
            </div>
            <div className="p-3 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D]">
              <div className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">Affected Devices</div>
              <div className="font-bold text-[#111111] dark:text-[#EDEDEA] mt-1 truncate">
                {report.affected_devices.length > 0 ? report.affected_devices.join(", ") : "None Detected"}
              </div>
            </div>
            <div className="p-3 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D]">
              <div className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">Affected Interfaces</div>
              <div className="font-bold text-[#111111] dark:text-[#EDEDEA] mt-1 truncate">
                {report.affected_interfaces.length > 0 ? report.affected_interfaces.join(", ") : "None"}
              </div>
            </div>
            <div className="p-3 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D]">
              <div className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">Diagnostic Timestamp</div>
              <div className="font-bold text-[#111111] dark:text-[#EDEDEA] mt-1 text-[11px] truncate">
                {report.timestamp_utc}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 4. SECTION: Network Health Metrics */}
      {shouldRenderSection("metrics") && (
        <div className="space-y-2">
          <span className="text-xs font-semibold uppercase tracking-wider font-mono text-[#6B6B66] dark:text-[#888884]">
            Section 4: Network Telemetry & Quantitative Health Metrics
          </span>
          {healthMetrics.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 font-mono text-xs">
              {healthMetrics.map((hm, idx) => (
                <div
                  key={idx}
                  className="p-3 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] space-y-1"
                >
                  <div className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884] truncate">
                    {hm.entity}: {hm.metric_name}
                  </div>
                  <div className="text-base font-bold text-[#111111] dark:text-[#EDEDEA]">
                    {String(hm.value)} <span className="text-xs font-normal text-[#6B6B66] dark:text-[#888884]">{hm.unit || ""}</span>
                  </div>
                  <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] truncate">
                    Domain: {hm.category}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-3 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] text-xs font-mono text-[#6B6B66] dark:text-[#888884]">
              No direct telemetry scalar metrics registered in this evidence envelope.
            </div>
          )}
        </div>
      )}

      {/* 5. SECTION: Detected Anomalies */}
      {shouldRenderSection("anomalies") && (
        <div className="space-y-2">
          <span className="text-xs font-semibold uppercase tracking-wider font-mono text-[#6B6B66] dark:text-[#888884]">
            Section 5: Correlated Anomalies ({anomalies.length} Detected)
          </span>
          <div className="divide-y divide-[#E5E5E3] dark:divide-[#2A2A2D] border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10]">
            {anomalies.length > 0 ? (
              anomalies.map((ano, idx) => (
                <div key={idx} className="p-3 flex items-start justify-between gap-3 font-mono text-xs">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-[#111111] dark:text-[#EDEDEA]">{ano.entity}</span>
                      <span className="text-[10px] text-[#6B6B66] dark:text-[#888884]">({ano.category})</span>
                    </div>
                    <div className="text-[#111111] dark:text-[#EDEDEA]">{ano.finding}</div>
                  </div>
                  <span
                    className={`px-2 py-0.5 border text-[10px] uppercase font-semibold shrink-0 ${
                      ano.severity === "critical"
                        ? "text-[#9A5B5B] border-[#9A5B5B]/30 bg-[#9A5B5B]/10"
                        : "text-[#A08A5B] border-[#A08A5B]/30 bg-[#A08A5B]/10"
                    }`}
                  >
                    {ano.severity}
                  </span>
                </div>
              ))
            ) : (
              <div className="p-3 text-xs font-mono text-[#6B6B66] dark:text-[#888884]">
                Zero warning or critical anomalies detected across telemetry windows.
              </div>
            )}
          </div>
        </div>
      )}

      {/* 6. SECTION: Root Cause Analysis & Causal Chain */}
      {shouldRenderSection("rca") && (
        <div className="space-y-2">
          <span className="text-xs font-semibold uppercase tracking-wider font-mono text-[#6B6B66] dark:text-[#888884]">
            Section 6: Root Cause Analysis & Inferred Causal Chain
          </span>
          <div className="p-4 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] space-y-3 font-mono">
            <div>
              <div className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">Primary Diagnosed Root Cause</div>
              <div className="text-base font-bold text-[#111111] dark:text-[#EDEDEA] mt-0.5">
                {report.probable_cause || "INSUFFICIENT_EVIDENCE"}
              </div>
            </div>

            {report.causal_chain && report.causal_chain.length > 0 && (
              <div className="pt-2 border-t border-[#E5E5E3] dark:border-[#2A2A2D] space-y-2">
                <div className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884] font-semibold">
                  Multi-Stage Causal Sequence
                </div>
                <div className="space-y-1.5">
                  {report.causal_chain.map((step, idx) => (
                    <div key={idx} className="flex items-start gap-2 text-xs">
                      <span className="px-1.5 py-0.2 border border-[#475569] text-[#475569] text-[10px] font-bold">
                        {idx + 1}
                      </span>
                      <span className="text-[#111111] dark:text-[#EDEDEA]">{step}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 7. SECTION: Supporting Evidence (expandable/searchable) */}
      {shouldRenderSection("evidence") && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold uppercase tracking-wider font-mono text-[#6B6B66] dark:text-[#888884]">
                Section 7: Supporting Evidence Ledger ({report.evidence.length})
              </span>
              <button
                onClick={() => setEvidenceExpanded(!evidenceExpanded)}
                className="text-[10px] font-mono text-[#475569] hover:underline"
              >
                {evidenceExpanded ? "Collapse" : "Expand"}
              </button>
            </div>

            <div className="flex items-center gap-2">
              <select
                value={evidenceFilter}
                onChange={(e) => setEvidenceFilter(e.target.value)}
                aria-label="Filter evidence ledger"
                className="px-2 py-0.5 text-[10px] font-mono bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] text-[#111111] dark:text-[#EDEDEA] outline-none"
              >
                <option value="all">All Evidence</option>
                <option value="critical">Critical</option>
                <option value="warning">Warning</option>
                <option value="info">Info</option>
              </select>
            </div>
          </div>

          {evidenceExpanded && (
            <div className="overflow-x-auto border border-[#E5E5E3] dark:border-[#2A2A2D]">
              <table className="w-full text-left font-mono text-xs">
                <thead className="bg-[#FAFAF9] dark:bg-[#0F0F10] border-b border-[#E5E5E3] dark:border-[#2A2A2D] text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">
                  <tr>
                    <th className="p-2.5">Domain</th>
                    <th className="p-2.5">Agent</th>
                    <th className="p-2.5">Entity</th>
                    <th className="p-2.5">Observed Metric</th>
                    <th className="p-2.5">Finding</th>
                    <th className="p-2.5 text-right">Severity</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E5E5E3]/60 dark:divide-[#2A2A2D]/60 bg-[#FFFFFF] dark:bg-[#161618]">
                  {filteredEvidence.map((ev, idx) => (
                    <tr key={idx} className="hover:bg-[#FAFAF9] dark:hover:bg-[#0F0F10]">
                      <td className="p-2.5 text-[10px] text-[#6B6B66] dark:text-[#888884]">{ev.category}</td>
                      <td className="p-2.5 text-[10px] text-[#475569]">{ev.source_agent}</td>
                      <td className="p-2.5 font-bold text-[#111111] dark:text-[#EDEDEA]">{ev.entity}</td>
                      <td className="p-2.5 text-[11px]">
                        {ev.value !== undefined && ev.value !== null ? (
                          <span>
                            {String(ev.value)} {ev.unit || ""}
                          </span>
                        ) : (
                          <span className="text-[#6B6B66] dark:text-[#888884]">-</span>
                        )}
                      </td>
                      <td className="p-2.5 text-[11px] text-[#111111] dark:text-[#EDEDEA]">{ev.finding}</td>
                      <td className="p-2.5 text-right">
                        <span
                          className={`px-1.5 py-0.2 border text-[9px] uppercase font-semibold ${
                            ev.severity === "critical"
                              ? "text-[#9A5B5B] border-[#9A5B5B]/30"
                              : ev.severity === "warning"
                              ? "text-[#A08A5B] border-[#A08A5B]/30"
                              : "text-[#6B6B66] border-[#E5E5E3] dark:border-[#2A2A2D]"
                          }`}
                        >
                          {ev.severity}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* 8. SECTION: Multi-Agent Investigation Summary */}
      {shouldRenderSection("multiagent") && (
        <div className="space-y-2">
          <span className="text-xs font-semibold uppercase tracking-wider font-mono text-[#6B6B66] dark:text-[#888884]">
            Section 8: Multi-Agent Consensus & Arbitration Summary
          </span>
          <div className="p-4 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] space-y-3 font-mono text-xs">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">Participating Agents:</span>
              {agentContributions.map((ag) => (
                <span
                  key={ag}
                  className="px-2 py-0.5 border border-[#475569] text-[10px] font-mono text-[#111111] dark:text-[#EDEDEA]"
                >
                  {ag}
                </span>
              ))}
            </div>

            {report.conflicts_resolved && report.conflicts_resolved.length > 0 ? (
              <div className="pt-2 border-t border-[#E5E5E3] dark:border-[#2A2A2D] space-y-1.5">
                <div className="text-[10px] uppercase text-[#A08A5B] font-semibold">
                  Arbitrated Diagnostic Conflicts:
                </div>
                {report.conflicts_resolved.map((conf, idx) => (
                  <div key={idx} className="p-2 bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D] text-[11px]">
                    <div className="font-semibold text-[#111111] dark:text-[#EDEDEA]">
                      Issue: {conf.issue || "Telemetry vs Topology conflict"}
                    </div>
                    <div className="text-[#6B6B66] dark:text-[#888884] mt-0.5">
                      Resolution: {conf.resolution || conf.rationale || "Resolved by confidence weighting and domain signature"}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-[11px] text-[#6B6B66] dark:text-[#888884] pt-1">
                Zero arbitration conflicts triggered during round consensus; all specialist agent hypotheses converged with monotonic agreement.
              </div>
            )}
          </div>
        </div>
      )}

      {/* 9. SECTION: Confidence & Uncertainty */}
      {shouldRenderSection("confidence") && (
        <div className="space-y-2">
          <span className="text-xs font-semibold uppercase tracking-wider font-mono text-[#6B6B66] dark:text-[#888884]">
            Section 9: Confidence Calibration & Telemetry Uncertainty
          </span>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 font-mono text-xs">
            <div className="p-3.5 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] space-y-1">
              <div className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">Calibrated Confidence</div>
              <div className="text-2xl font-bold text-[#111111] dark:text-[#EDEDEA]">
                {Math.round(report.confidence * 100)}%
              </div>
              <div className="text-[10px] text-[#6B6B66] dark:text-[#888884]">
                Isotonic Calibrator & Logistic Hybrid
              </div>
            </div>

            <div className="p-3.5 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] space-y-1">
              <div className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">Uncertainty Score</div>
              <div className="text-2xl font-bold text-[#111111] dark:text-[#EDEDEA]">
                {(report.uncertainty.score * 100).toFixed(1)}%
              </div>
              <div className="text-[10px] text-[#6B6B66] dark:text-[#888884]">
                Missing Signal & Noise Index
              </div>
            </div>

            <div className="p-3.5 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] space-y-1">
              <div className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">Conformal Prediction Set</div>
              <div className="font-bold text-[#111111] dark:text-[#EDEDEA] mt-1 truncate">
                {report.conformal_prediction_set && report.conformal_prediction_set.length > 0
                  ? report.conformal_prediction_set.join(", ")
                  : report.probable_cause || "None"}
              </div>
              <div className="text-[10px] text-[#6B6B66] dark:text-[#888884]">90% Coverage Guarantee</div>
            </div>
          </div>

          {report.uncertainty.missing_evidence.length > 0 && (
            <div className="p-3 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] text-xs font-mono space-y-1.5">
              <div className="text-[10px] uppercase text-[#A08A5B] font-semibold">
                Telemetry Gaps & Missing Evidence Constraints:
              </div>
              <ul className="space-y-1">
                {report.uncertainty.missing_evidence.map((gap, idx) => (
                  <li key={idx} className="text-[#6B6B66] dark:text-[#888884] flex items-center gap-1.5">
                    <span className="text-[#A08A5B]">-</span> {gap}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* 10. SECTION: Remediation Recommendations */}
      {shouldRenderSection("remediation") && (
        <div className="space-y-2">
          <span className="text-xs font-semibold uppercase tracking-wider font-mono text-[#6B6B66] dark:text-[#888884]">
            Section 10: Simulated Remediation Recommendations ({report.remediation_actions.length})
          </span>
          {report.remediation_actions.length > 0 ? (
            <div className="space-y-3 font-mono text-xs">
              {report.remediation_actions.map((act) => (
                <div
                  key={act.action_id}
                  className="p-3.5 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] space-y-2"
                >
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-[#111111] dark:text-[#EDEDEA]">{act.title}</span>
                      <span className="px-1.5 py-0.2 border border-[#475569] text-[10px] uppercase text-[#475569]">
                        Risk: {act.risk_level}
                      </span>
                    </div>
                    <span className="text-[10px] text-[#6B6B66] dark:text-[#888884]">
                      Target Device: {act.device}
                    </span>
                  </div>

                  <p className="text-[11px] text-[#6B6B66] dark:text-[#888884]">{act.description}</p>

                  <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D] p-2.5 text-[10px] space-y-1">
                    <div className="text-[#6B6B66] dark:text-[#888884] uppercase font-semibold">
                      Proposed Target Commands:
                    </div>
                    <pre className="text-[#111111] dark:text-[#EDEDEA] overflow-x-auto">
                      {act.commands.join("\n")}
                    </pre>
                  </div>

                  <div className="text-[10px] text-[#6B6B66] dark:text-[#888884]">
                    Estimated Blast Radius: {act.blast_radius_devices.join(", ") || "Isolated Interface"}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-3 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] text-xs font-mono text-[#6B6B66] dark:text-[#888884]">
              No corrective remediation actions generated for this scenario.
            </div>
          )}
        </div>
      )}

      {/* 11. SECTION: Verification & Recovery */}
      {shouldRenderSection("recovery") && (
        <div className="space-y-2">
          <span className="text-xs font-semibold uppercase tracking-wider font-mono text-[#6B6B66] dark:text-[#888884]">
            Section 11: Verification Criteria & Rollback Recovery Plan
          </span>
          <div className="p-4 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] space-y-3 font-mono text-xs">
            {report.remediation_actions.length > 0 && report.remediation_actions[0].rollback_commands.length > 0 ? (
              <div className="space-y-2">
                <div className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884] font-semibold">
                  Automated Rollback Commands (Pre-validated):
                </div>
                <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D] p-2.5 text-[10px]">
                  <pre className="text-[#111111] dark:text-[#EDEDEA] overflow-x-auto">
                    {report.remediation_actions.flatMap((a) => a.rollback_commands).join("\n")}
                  </pre>
                </div>
              </div>
            ) : (
              <div className="text-[11px] text-[#6B6B66] dark:text-[#888884]">
                No destructive commands proposed; state restoration follows standard config check.
              </div>
            )}

            <div className="pt-2 border-t border-[#E5E5E3] dark:border-[#2A2A2D] text-[11px] text-[#6B6B66] dark:text-[#888884] space-y-1">
              <div className="font-semibold uppercase text-[10px] text-[#111111] dark:text-[#EDEDEA]">
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
          <span className="text-xs font-semibold uppercase tracking-wider font-mono text-[#6B6B66] dark:text-[#888884]">
            Section 12: Complete Cryptographic & Procedural Audit Trail
          </span>
          <div className="p-4 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] space-y-2 font-mono text-xs">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-[11px]">
              <div>
                <span className="text-[#6B6B66] dark:text-[#888884]">Incident Identifier: </span>
                <span className="text-[#111111] dark:text-[#EDEDEA] font-semibold">{report.incident_id}</span>
              </div>
              <div>
                <span className="text-[#6B6B66] dark:text-[#888884]">Timestamp UTC: </span>
                <span className="text-[#111111] dark:text-[#EDEDEA]">{report.timestamp_utc}</span>
              </div>
              <div>
                <span className="text-[#6B6B66] dark:text-[#888884]">Engine Protocol Version: </span>
                <span className="text-[#111111] dark:text-[#EDEDEA]">NetCoop-Envelope-v1.0</span>
              </div>
              <div>
                <span className="text-[#6B6B66] dark:text-[#888884]">Storage Persistence: </span>
                <span className="text-[#111111] dark:text-[#EDEDEA]">SQLite WAL Journaled (audited)</span>
              </div>
            </div>

            <div className="pt-2 border-t border-[#E5E5E3] dark:border-[#2A2A2D] text-[10px] text-[#6B6B66] dark:text-[#888884]">
              Compliance Record: All diagnostic inferences, agent inquiries, and human-in-the-loop decisions are immutable and permanently recorded in compliance with enterprise audit protocols.
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
