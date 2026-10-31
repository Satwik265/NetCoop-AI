import React from "react";
import { UnifiedDiagnosticReport } from "../types/protocol";

interface Props {
  report: UnifiedDiagnosticReport | null;
  loading: boolean;
}

export const IncidentHeader: React.FC<Props> = ({ report, loading }) => {
  if (loading) {
    return (
      <div className="bg-[#161618] border border-[#2A2A2D] p-5 rounded-none animate-pulse">
        <div className="h-4 bg-[#2A2A2D] w-1/4 mb-3"></div>
        <div className="h-6 bg-[#2A2A2D] w-3/4"></div>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="bg-[#161618] border border-[#2A2A2D] p-6 text-center text-[#888884]">
        Select a network incident scenario or upload telemetry to begin multi-agent diagnosis.
      </div>
    );
  }

  const isDiagnosed = report.status === "diagnosed";
  const isInsufficient = report.status === "insufficient_evidence";

  const statusBg = isDiagnosed
    ? "bg-[#5E7A6A]/20 text-[#5E7A6A] border-[#5E7A6A]/40"
    : isInsufficient
    ? "bg-[#A08A5B]/20 text-[#A08A5B] border-[#A08A5B]/40"
    : "bg-[#9A5B5B]/20 text-[#9A5B5B] border-[#9A5B5B]/40";

  return (
    <div className="bg-[#161618] border border-[#2A2A2D] p-5">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#2A2A2D] pb-4 mb-4">
        <div>
          <div className="text-xs uppercase tracking-wider text-[#888884] font-mono mb-1">
            Incident: {report.incident_id} | Network: {report.network_id}
          </div>
          <h1 className="text-xl font-semibold text-[#EDEDEA]">
            {report.probable_cause || "Root Cause: Insufficient Evidence"}
          </h1>
        </div>

        <div className="flex items-center gap-4">
          <div className="text-right">
            <div className="text-xs text-[#888884] font-mono">Confidence</div>
            <div className="text-lg font-mono font-semibold text-[#EDEDEA]">
              {Math.round(report.confidence * 100)}%
            </div>
          </div>
          <span
            className={`px-3 py-1 border text-xs font-mono uppercase tracking-wider font-medium ${statusBg}`}
          >
            {report.status}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs font-mono text-[#888884]">
        <div>
          <span className="text-[#EDEDEA] font-medium">Affected Nodes:</span>{" "}
          {report.affected_devices.length > 0
            ? report.affected_devices.join(", ")
            : "None isolated"}
        </div>
        <div>
          <span className="text-[#EDEDEA] font-medium">Processing Time:</span>{" "}
          {report.processing_time_ms} ms
        </div>
        <div>
          <span className="text-[#EDEDEA] font-medium">Timestamp:</span>{" "}
          {report.timestamp_utc ? report.timestamp_utc.slice(0, 19).replace("T", " ") : "N/A"} UTC
        </div>
      </div>

      {report.summary && (
        <div className="mt-4 p-3 bg-[#0F0F10] border border-[#2A2A2D] text-xs text-[#EDEDEA] leading-relaxed">
          <span className="text-[#888884] font-mono uppercase block mb-1">
            Executive Summary
          </span>
          {report.summary}
        </div>
      )}
    </div>
  );
};

