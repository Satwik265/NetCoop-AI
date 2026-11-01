import React, { useState } from "react";
import { EnvelopeLogItem } from "../types/protocol";

interface EnvelopeSlideOverProps {
  envelope: EnvelopeLogItem | null;
  onClose: () => void;
}

export const EnvelopeSlideOver: React.FC<EnvelopeSlideOverProps> = ({
  envelope,
  onClose,
}) => {
  const [copied, setCopied] = useState<boolean>(false);
  const [activeView, setActiveView] = useState<"formatted" | "raw">("formatted");

  if (!envelope) return null;

  const handleCopy = () => {
    navigator.clipboard.writeText(JSON.stringify(envelope, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const payload = envelope.payload || {};
  const observations = payload.observations || [];
  const hypotheses = payload.hypotheses || [];
  const inquiries = payload.inquiries || [];
  const scope = payload.scope || {};

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-black/40 backdrop-blur-sm flex justify-end transition-opacity duration-200">
      <div
        className="w-full max-w-2xl bg-[#FFFFFF] dark:bg-[#161618] border-l border-[#E5E5E3] dark:border-[#2A2A2D] h-full flex flex-col font-mono shadow-2xl transition-transform duration-200"
        style={{ animation: "slideIn 200ms ease-out" }}
      >
        {/* Slide-over Header */}
        <div className="p-5 border-b border-[#E5E5E3] dark:border-[#2A2A2D] flex items-center justify-between gap-4">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider text-[#111111] dark:text-[#EDEDEA]">
              Agent Wire Envelope Inspector
            </div>
            <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] truncate max-w-sm">
              ID: {envelope.message_id || envelope.id}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleCopy}
              className="px-2.5 py-1 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] text-[11px] text-[#111111] dark:text-[#EDEDEA] hover:border-[#475569] transition-colors"
            >
              {copied ? "Copied" : "Copy JSON"}
            </button>
            <button
              onClick={onClose}
              className="px-2.5 py-1 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] text-[11px] text-[#111111] dark:text-[#EDEDEA] hover:border-[#475569] transition-colors"
            >
              Close
            </button>
          </div>
        </div>

        {/* Envelope Metadata Summary Bar */}
        <div className="bg-[#FAFAF9] dark:bg-[#0F0F10] border-b border-[#E5E5E3] dark:border-[#2A2A2D] px-5 py-3 grid grid-cols-2 sm:grid-cols-4 gap-3 text-[11px]">
          <div>
            <span className="text-[10px] text-[#6B6B66] dark:text-[#888884] block uppercase">Sender</span>
            <span className="font-semibold text-[#111111] dark:text-[#EDEDEA]">{envelope.sender}</span>
          </div>
          <div>
            <span className="text-[10px] text-[#6B6B66] dark:text-[#888884] block uppercase">Recipient</span>
            <span className="font-semibold text-[#475569]">{envelope.recipient}</span>
          </div>
          <div>
            <span className="text-[10px] text-[#6B6B66] dark:text-[#888884] block uppercase">Type</span>
            <span className="text-[#111111] dark:text-[#EDEDEA]">{envelope.message_type}</span>
          </div>
          <div>
            <span className="text-[10px] text-[#6B6B66] dark:text-[#888884] block uppercase">Priority</span>
            <span className="text-[#111111] dark:text-[#EDEDEA] uppercase">{envelope.priority}</span>
          </div>
        </div>

        {/* View Switcher Tabs */}
        <div className="flex border-b border-[#E5E5E3] dark:border-[#2A2A2D] px-5 gap-4 text-xs">
          <button
            onClick={() => setActiveView("formatted")}
            className={`py-2.5 font-medium border-b-2 transition-colors ${
              activeView === "formatted"
                ? "border-[#475569] text-[#111111] dark:text-[#EDEDEA]"
                : "border-transparent text-[#6B6B66] dark:text-[#888884]"
            }`}
          >
            Formatted Sections
          </button>
          <button
            onClick={() => setActiveView("raw")}
            className={`py-2.5 font-medium border-b-2 transition-colors ${
              activeView === "raw"
                ? "border-[#475569] text-[#111111] dark:text-[#EDEDEA]"
                : "border-transparent text-[#6B6B66] dark:text-[#888884]"
            }`}
          >
            Raw JSON
          </button>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5 text-xs">
          {activeView === "formatted" ? (
            <>
              {/* Scope */}
              <div className="space-y-1.5">
                <span className="text-[10px] text-[#6B6B66] dark:text-[#888884] uppercase font-semibold">
                  Payload Scope
                </span>
                <div className="p-3 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] text-[11px] space-y-1">
                  <div><strong className="text-[#6B6B66] dark:text-[#888884]">Network ID:</strong> {scope.network_id || "global"}</div>
                  <div><strong className="text-[#6B6B66] dark:text-[#888884]">Devices:</strong> {scope.devices?.join(", ") || "none specified"}</div>
                  <div><strong className="text-[#6B6B66] dark:text-[#888884]">Interfaces:</strong> {scope.interfaces?.join(", ") || "none specified"}</div>
                </div>
              </div>

              {/* Observations */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-[#6B6B66] dark:text-[#888884] uppercase font-semibold">
                    Observations ({observations.length})
                  </span>
                </div>
                {observations.length === 0 ? (
                  <div className="text-[11px] text-[#6B6B66] dark:text-[#888884] italic p-2 border border-dashed border-[#E5E5E3] dark:border-[#2A2A2D]">
                    No observations contained in this envelope.
                  </div>
                ) : (
                  <div className="space-y-2">
                    {observations.map((obs: any, idx: number) => (
                      <div
                        key={idx}
                        className="p-3 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] space-y-1"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-semibold text-[#111111] dark:text-[#EDEDEA]">
                            {obs.entity}
                          </span>
                          <span className="text-[10px] px-1.5 py-0.2 border border-[#475569] uppercase">
                            {obs.severity || "info"}
                          </span>
                        </div>
                        <div className="text-[#6B6B66] dark:text-[#888884]">
                          {obs.metric_name}: observed {obs.observed_value} {obs.unit} (baseline: {obs.baseline_value})
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Hypotheses */}
              <div className="space-y-1.5">
                <span className="text-[10px] text-[#6B6B66] dark:text-[#888884] uppercase font-semibold">
                  Hypotheses ({hypotheses.length})
                </span>
                {hypotheses.length === 0 ? (
                  <div className="text-[11px] text-[#6B6B66] dark:text-[#888884] italic p-2 border border-dashed border-[#E5E5E3] dark:border-[#2A2A2D]">
                    No hypotheses submitted in this envelope.
                  </div>
                ) : (
                  <div className="space-y-2">
                    {hypotheses.map((h: any, idx: number) => (
                      <div
                        key={idx}
                        className="p-3 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] space-y-1"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-[#111111] dark:text-[#EDEDEA]">
                            {h.probable_cause}
                          </span>
                          <span className="font-bold text-[#475569]">
                            {Math.round((h.confidence || 0) * 100)}%
                          </span>
                        </div>
                        <div className="text-[10px] text-[#6B6B66] dark:text-[#888884]">
                          Supporting: {h.supporting_observation_ids?.join(", ") || "none"}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Inquiries */}
              <div className="space-y-1.5">
                <span className="text-[10px] text-[#6B6B66] dark:text-[#888884] uppercase font-semibold">
                  Cross-Inquiries ({inquiries.length})
                </span>
                {inquiries.length === 0 ? (
                  <div className="text-[11px] text-[#6B6B66] dark:text-[#888884] italic p-2 border border-dashed border-[#E5E5E3] dark:border-[#2A2A2D]">
                    No cross-inquiries in this envelope.
                  </div>
                ) : (
                  <div className="space-y-2">
                    {inquiries.map((inq: any, idx: number) => (
                      <div
                        key={idx}
                        className="p-3 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] space-y-1"
                      >
                        <div className="text-[10px] text-[#475569]">
                          Target: {inq.target_agent} ({inq.target_entity})
                        </div>
                        <div className="text-[#111111] dark:text-[#EDEDEA] italic">
                          "{inq.question}"
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          ) : (
            <pre className="p-4 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] text-[11px] leading-relaxed text-[#111111] dark:text-[#EDEDEA] overflow-x-auto">
              {JSON.stringify(envelope, null, 2)}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
};

