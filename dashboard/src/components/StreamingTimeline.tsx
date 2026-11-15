import React, { useState } from "react";
import { EnvelopeLogItem } from "../types/protocol";
import { formatDateTime, SupportedTimezone } from "../utils/i18n";

interface StreamingTimelineProps {
  envelopes: EnvelopeLogItem[];
  currentIndex: number;
  onSelectEnvelope: (env: EnvelopeLogItem) => void;
  onScrub: (index: number) => void;
  isPlaying: boolean;
  onTogglePlay: () => void;
  timezone?: SupportedTimezone;
}

export const StreamingTimeline: React.FC<StreamingTimelineProps> = ({
  envelopes,
  currentIndex,
  onSelectEnvelope,
  onScrub,
  isPlaying,
  onTogglePlay,
  timezone = "UTC",
}) => {
  const [filterAgent, setFilterAgent] = useState<string>("all");
  const [filterType, setFilterType] = useState<string>("all");

  const agents = [
    "all",
    "orchestrator",
    "telemetry_agent",
    "topology_agent",
    "config_agent",
    "log_agent",
    "classifier_agent",
    "wifi_services_agent",
    "synthesizer_agent",
    "gateway",
  ];

  const types = [
    "all",
    "telemetry_dispatch",
    "finding_submission",
    "inquiry_request",
    "inquiry_response",
    "conflict_notification",
    "synthesis_submission",
  ];

  // Up to current scrub index
  const visibleEnvelopes = envelopes.slice(0, currentIndex + 1);

  const filtered = visibleEnvelopes.filter((env) => {
    const matchesAgent =
      filterAgent === "all" ||
      env.sender === filterAgent ||
      env.recipient === filterAgent;
    const matchesType =
      filterType === "all" || env.message_type === filterType;
    return matchesAgent && matchesType;
  });

  return (
    <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E2E8F0] dark:border-[#2A2A2D] p-5 flex flex-col h-[540px] font-sans">
      {/* Header and Filter Controls */}
      <div className="flex flex-wrap items-center justify-between border-b border-[#E2E8F0] dark:border-[#2A2A2D] pb-3 mb-3 gap-3">
        <div>
          <h2 className="text-xs font-bold uppercase tracking-wider text-[#0B2545] dark:text-[#F1F5F9]">
            Wire Envelope Timeline
          </h2>
          <div className="text-[11px] text-[#475569] dark:text-[#94A3B8]">
            Streaming protocol telemetry events ({visibleEnvelopes.length}/{envelopes.length})
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Agent Filter */}
          <label htmlFor="agent-filter" className="sr-only">Filter by agent</label>
          <select
            id="agent-filter"
            value={filterAgent}
            onChange={(e) => setFilterAgent(e.target.value)}
            className="bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#CBD5E1] dark:border-[#2A2A2D] px-2.5 py-1 text-xs text-[#0F172A] dark:text-[#F1F5F9] outline-none min-h-[28px]"
          >
            {agents.map((ag) => (
              <option key={ag} value={ag}>
                {ag === "all" ? "All Agents" : ag}
              </option>
            ))}
          </select>

          {/* Type Filter */}
          <label htmlFor="type-filter" className="sr-only">Filter by message type</label>
          <select
            id="type-filter"
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#CBD5E1] dark:border-[#2A2A2D] px-2.5 py-1 text-xs text-[#0F172A] dark:text-[#F1F5F9] outline-none min-h-[28px]"
          >
            {types.map((tp) => (
              <option key={tp} value={tp}>
                {tp === "all" ? "All Message Types" : tp}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Scrub Controls */}
      <div className="flex items-center gap-3 bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#E2E8F0] dark:border-[#2A2A2D] p-2.5 mb-3">
        <button
          onClick={onTogglePlay}
          aria-label={isPlaying ? "Pause envelope playback" : "Play envelope playback"}
          className="px-3 py-1 bg-[#0B2545] text-white hover:bg-[#133E87] dark:bg-[#133E87] dark:hover:bg-[#3A86FF] text-xs font-bold uppercase tracking-wider transition-colors min-h-[28px] focus-visible:ring-2"
        >
          {isPlaying ? "Pause" : "Play"}
        </button>

        <label htmlFor="timeline-scrubber" className="sr-only">Timeline progress scrubber</label>
        <input
          id="timeline-scrubber"
          type="range"
          min={0}
          max={Math.max(0, envelopes.length - 1)}
          value={currentIndex}
          onChange={(e) => onScrub(parseInt(e.target.value, 10))}
          className="flex-1 accent-[#0B2545] dark:accent-[#3A86FF] cursor-pointer"
        />

        <span className="text-[11px] font-mono font-bold text-[#0F172A] dark:text-[#F1F5F9] min-w-[50px] text-right">
          {envelopes.length > 0 ? `${currentIndex + 1}/${envelopes.length}` : "0/0"}
        </span>
      </div>

      {/* Scrollable Timeline List */}
      <div className="flex-1 overflow-y-auto space-y-2 pr-1" role="region" aria-label="Envelope events list">
        {filtered.length === 0 ? (
          <div className="text-xs text-[#475569] dark:text-[#94A3B8] font-mono py-8 text-center">
            No envelopes match the selected filters or scrub state.
          </div>
        ) : (
          filtered.map((env, idx) => {
            const isLatest = idx === filtered.length - 1;
            const obsCount = env.payload?.observations?.length || 0;
            const hypCount = env.payload?.hypotheses?.length || 0;
            const inqCount = env.payload?.inquiries?.length || 0;

            return (
              <div
                key={env.id || env.message_id || idx}
                onClick={() => onSelectEnvelope(env)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelectEnvelope(env);
                  }
                }}
                className={`p-2.5 border text-xs font-sans cursor-pointer transition-all duration-200 outline-none focus-visible:ring-2 focus-visible:ring-[#133E87] ${
                  isLatest
                    ? "border-[#0B2545] bg-[#EEF4FB] dark:border-[#3A86FF] dark:bg-[#1E293B]"
                    : "border-[#E2E8F0] dark:border-[#2A2A2D] bg-[#F8FAFC] dark:bg-[#0F0F10] hover:border-[#64748B]"
                }`}
              >
                <div className="flex items-center justify-between gap-2 mb-1">
                  <div className="flex items-center gap-1.5 flex-wrap font-mono">
                    <span className="text-[10px] text-[#475569] dark:text-[#94A3B8]">
                      #{env.id || idx + 1}
                    </span>
                    <span className="font-bold text-[#0F172A] dark:text-[#F1F5F9]">
                      {env.sender}
                    </span>
                    <span className="text-[#475569] dark:text-[#94A3B8]">&rarr;</span>
                    <span className="text-[#0B2545] dark:text-[#3A86FF] font-bold">
                      {env.recipient}
                    </span>
                  </div>

                  <span className="text-[10px] font-mono text-[#475569] dark:text-[#94A3B8]">
                    {formatDateTime(env.timestamp_utc, timezone, { includeSeconds: true })}
                  </span>
                </div>

                <div className="flex items-center justify-between text-[11px] gap-2 pt-1 border-t border-[#E2E8F0] dark:border-[#2A2A2D] font-mono">
                  <span className="px-1.5 py-0.5 border border-[#CBD5E1] dark:border-[#2A2A2D] text-[10px] uppercase font-bold text-[#475569] dark:text-[#94A3B8]">
                    {env.message_type}
                  </span>

                  <div className="flex items-center gap-2 text-[10px] text-[#475569] dark:text-[#94A3B8]">
                    <span>obs:{obsCount}</span>
                    <span>hyp:{hypCount}</span>
                    <span>inq:{inqCount}</span>
                    <span>iter:{env.context?.iteration ?? 0}</span>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
