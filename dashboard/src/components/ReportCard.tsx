import React, { useState } from "react";
import { UnifiedDiagnosticReport } from "../types/protocol";

interface ReportCardProps {
  report: UnifiedDiagnosticReport | null;
  loading: boolean;
}

export const ReportCard: React.FC<ReportCardProps> = ({ report, loading }) => {
  const [copied, setCopied] = useState<boolean>(false);

  if (loading) {
    return (
      <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D] p-6 space-y-4 animate-pulse">
        <div className="h-4 bg-[#E5E5E3] dark:bg-[#2A2A2D] w-1/3"></div>
        <div className="h-8 bg-[#E5E5E3] dark:bg-[#2A2A2D] w-3/4"></div>
        <div className="h-24 bg-[#E5E5E3] dark:bg-[#2A2A2D] w-full"></div>
        <div className="grid grid-cols-2 gap-4">
          <div className="h-16 bg-[#E5E5E3] dark:bg-[#2A2A2D]"></div>
          <div className="h-16 bg-[#E5E5E3] dark:bg-[#2A2A2D]"></div>
        </div>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D] p-8 text-center text-xs font-mono text-[#6B6B66] dark:text-[#888884]">
        Select a scenario and click "Run Diagnosis" to generate the diagnostic report card.
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
    let md = `# Diagnostic Report: ${report.incident_id}\n\n`;
    md += `- **Network ID**: \`${report.network_id}\`\n`;
    md += `- **Timestamp UTC**: \`${report.timestamp_utc}\`\n`;
    md += `- **Diagnostic Status**: **${report.status.toUpperCase()}**\n`;
    md += `- **Probable Cause**: ${report.probable_cause || "None (Insufficient Evidence)"}\n`;
    md += `- **Calibrated Confidence**: ${(report.confidence * 100).toFixed(1)}%\n`;
    md += `- **Affected Devices**: ${report.affected_devices.join(", ") || "None"}\n`;
    md += `- **Affected Interfaces**: ${report.affected_interfaces.join(", ") || "None"}\n`;
    md += `- **Processing Time**: ${report.processing_time_ms.toFixed(2)} ms\n\n`;

    md += `## Executive Summary\n${report.summary}\n\n`;

    md += `## Corroborated Evidence (${report.evidence.length})\n`;
    for (const ev of report.evidence) {
      md += `- **[${ev.source_agent}]** \`${ev.entity}\` (${ev.category}): ${ev.finding}`;
      if (ev.value !== undefined && ev.unit) {
        md += ` [Observed: ${ev.value} ${ev.unit}]`;
      }
      md += ` (Severity: ${ev.severity})\n`;
    }
    md += `\n`;

    if (report.uncertainty.missing_evidence.length > 0) {
      md += `## Prerequisite Evidence Missing\n`;
      for (const m of report.uncertainty.missing_evidence) {
        md += `- ${m}\n`;
      }
      md += `\n`;
    }

    if (report.remediation_actions.length > 0) {
      md += `## Simulated Remediation Actions\n`;
      for (const act of report.remediation_actions) {
        md += `### ${act.title} (Device: ${act.device}, Risk: ${act.risk_level})\n`;
        md += `${act.description}\n\n`;
        md += `**Commands (Simulated)**:\n\`\`\`bash\n${act.commands.join("\n")}\n\`\`\`\n\n`;
        md += `**Rollback Commands**:\n\`\`\`bash\n${act.rollback_commands.join("\n")}\n\`\`\`\n\n`;
        md += `**Blast Radius**: ${act.blast_radius_devices.join(", ")}\n\n`;
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

  return (
    <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D] p-5 space-y-6">
      {/* Top Header & Actions */}
      <div className="flex flex-wrap items-center justify-between border-b border-[#E5E5E3] dark:border-[#2A2A2D] pb-3 gap-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold uppercase tracking-wider font-mono text-[#111111] dark:text-[#EDEDEA]">
              Final Diagnostic Report
            </span>
            <span className={`px-2 py-0.5 border text-[10px] font-mono uppercase font-semibold ${statusColor}`}>
              {report.status.replace("_", " ")}
            </span>
          </div>
          <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] font-mono">
            Incident: {report.incident_id} | Network: {report.network_id} | Time: {report.processing_time_ms.toFixed(1)}ms
          </div>
        </div>

        {/* Export Buttons */}
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

      {/* Probable Cause & Confidence Banner */}
      <div className="p-4 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="text-[10px] uppercase font-mono text-[#6B6B66] dark:text-[#888884]">
            Probable Root Cause
          </div>
          <div className="text-base font-bold font-mono text-[#111111] dark:text-[#EDEDEA] mt-0.5">
            {report.probable_cause || "INSUFFICIENT_EVIDENCE"}
          </div>
          <div className="text-xs text-[#6B6B66] dark:text-[#888884] font-mono mt-1">
            Impacted Devices: {report.affected_devices.join(", ") || "None"}
          </div>
        </div>

        <div className="text-right font-mono shrink-0">
          <div className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">
            Calibrated Confidence
          </div>
          <div className="text-2xl font-bold text-[#111111] dark:text-[#EDEDEA]">
            {Math.round(report.confidence * 100)}%
          </div>
        </div>
      </div>

      {/* Executive Summary */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-semibold uppercase tracking-wider font-mono text-[#6B6B66] dark:text-[#888884]">
            Executive Summary
          </span>
          <button
            onClick={handleCopySummary}
            className="text-[10px] font-mono text-[#475569] hover:underline"
          >
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
        <p className="text-xs font-mono leading-relaxed p-3 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] text-[#111111] dark:text-[#EDEDEA]">
          {report.summary}
        </p>
      </div>

      {/* Uncertainty & Limitations */}
      <div className="space-y-2">
        <div className="text-[11px] font-semibold uppercase tracking-wider font-mono text-[#6B6B66] dark:text-[#888884]">
          Uncertainty Evaluation & Telemetry Gaps
        </div>
        <div className="p-3 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] text-xs font-mono space-y-2">
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-[#6B6B66] dark:text-[#888884]">Uncertainty Score:</span>
            <span className="font-semibold text-[#111111] dark:text-[#EDEDEA]">
              {(report.uncertainty.score * 100).toFixed(1)}%
            </span>
          </div>

          {report.uncertainty.missing_evidence.length > 0 && (
            <div className="pt-2 border-t border-[#E5E5E3] dark:border-[#2A2A2D]">
              <div className="text-[10px] uppercase text-[#A08A5B] font-semibold mb-1">
                Prerequisite Evidence Not Met:
              </div>
              <ul className="space-y-1">
                {report.uncertainty.missing_evidence.map((me, idx) => (
                  <li key={idx} className="text-[#6B6B66] dark:text-[#888884] flex items-center gap-1.5">
                    <span className="text-[#A08A5B]">-</span> {me}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>

      {/* Simulated Remediation Plans */}
      {report.remediation_actions.length > 0 && (
        <div className="space-y-3">
          <div className="text-[11px] font-semibold uppercase tracking-wider font-mono text-[#6B6B66] dark:text-[#888884]">
            Simulated Remediation Actions ({report.remediation_actions.length})
          </div>

          <div className="space-y-3">
            {report.remediation_actions.map((act) => (
              <div
                key={act.action_id}
                className="p-3 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] text-xs font-mono space-y-2"
              >
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-[#111111] dark:text-[#EDEDEA]">
                      {act.title}
                    </span>
                    <span className="px-1.5 py-0.2 border border-[#475569] text-[10px] text-[#475569] uppercase">
                      Risk: {act.risk_level}
                    </span>
                  </div>
                  <span className="text-[10px] text-[#6B6B66] dark:text-[#888884]">
                    Device: {act.device}
                  </span>
                </div>

                <div className="text-[11px] text-[#6B6B66] dark:text-[#888884]">
                  {act.description}
                </div>

                {/* Commands Preview */}
                <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D] p-2 text-[10px] space-y-1">
                  <div className="text-[#6B6B66] dark:text-[#888884] uppercase font-semibold">
                    Simulated Target Commands:
                  </div>
                  <pre className="text-[#111111] dark:text-[#EDEDEA] overflow-x-auto">
                    {act.commands.join("\n")}
                  </pre>
                </div>

                {/* Blast Radius */}
                <div className="text-[10px] text-[#6B6B66] dark:text-[#888884]">
                  Blast Radius: {act.blast_radius_devices.join(", ") || "Isolated"}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

