import React, { useState } from "react";
import { EnvelopeLogItem } from "../types/protocol";

interface StreamingTimelineProps {
  envelopes: EnvelopeLogItem[];
  currentIndex: number;
  onSelectEnvelope: (env: EnvelopeLogItem) => void;
  onScrub: (index: number) => void;
  isPlaying: boolean;
  onTogglePlay: () => void;
}

export const StreamingTimeline: React.FC<StreamingTimelineProps> = ({
  envelopes,
  currentIndex,
  onSelectEnvelope,
  onScrub,
  isPlaying,
  onTogglePlay,
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
    <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D] p-5 flex flex-col h-[520px]">
      {/* Header and Filter Controls */}
      <div className="flex flex-wrap items-center justify-between border-b border-[#E5E5E3] dark:border-[#2A2A2D] pb-3 mb-3 gap-3">
        <div>
          <h2 className="text-xs font-semibold uppercase tracking-wider font-mono text-[#111111] dark:text-[#EDEDEA]">
            Streaming Message Timeline
          </h2>
          <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] font-mono">
            {visibleEnvelopes.length} of {envelopes.length} envelopes rendered
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Agent Filter */}
          <select
            value={filterAgent}
            onChange={(e) => setFilterAgent(e.target.value)}
            className="bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] text-[#111111] dark:text-[#EDEDEA] px-2 py-1 text-[11px] font-mono outline-none focus:border-[#475569]"
          >
            {agents.map((a) => (
              <option key={a} value={a}>
                Agent: {a.replace("_agent", "")}
              </option>
            ))}
          </select>

          {/* Type Filter */}
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] text-[#111111] dark:text-[#EDEDEA] px-2 py-1 text-[11px] font-mono outline-none focus:border-[#475569]"
          >
            {types.map((t) => (
              <option key={t} value={t}>
                Type: {t.replace("_", " ")}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Scrub & Playback Control Bar */}
      <div className="bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] px-3 py-2 mb-3 flex items-center gap-3">
        <button
          onClick={onTogglePlay}
          className="px-2.5 py-1 bg-[#111111] dark:bg-[#EDEDEA] text-[#FFFFFF] dark:text-[#111111] text-[10px] font-mono uppercase font-semibold hover:opacity-90 transition-opacity"
        >
          {isPlaying ? "Pause" : "Play"}
        </button>

        <button
          onClick={() => onScrub(Math.max(0, currentIndex - 1))}
          disabled={currentIndex <= 0}
          className="px-2 py-1 border border-[#E5E5E3] dark:border-[#2A2A2D] text-[10px] font-mono disabled:opacity-30 hover:border-[#475569]"
        >
          &lt; Step
        </button>

        <button
          onClick={() => onScrub(Math.min(envelopes.length - 1, currentIndex + 1))}
          disabled={currentIndex >= envelopes.length - 1}
          className="px-2 py-1 border border-[#E5E5E3] dark:border-[#2A2A2D] text-[10px] font-mono disabled:opacity-30 hover:border-[#475569]"
        >
          Step &gt;
        </button>

        <input
          type="range"
          min="0"
          max={Math.max(0, envelopes.length - 1)}
          value={currentIndex}
          onChange={(e) => onScrub(parseInt(e.target.value, 10))}
          className="flex-1 accent-[#475569] cursor-pointer"
        />

        <span className="text-[10px] font-mono text-[#6B6B66] dark:text-[#888884] min-w-[45px] text-right">
          {envelopes.length > 0 ? `${currentIndex + 1}/${envelopes.length}` : "0/0"}
        </span>
      </div>

      {/* Scrollable Timeline List */}
      <div className="flex-1 overflow-y-auto space-y-2 pr-1">
        {filtered.length === 0 ? (
          <div className="text-xs text-[#6B6B66] dark:text-[#888884] font-mono py-8 text-center">
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
                className={`p-2.5 border text-xs font-mono cursor-pointer transition-all duration-200 ${
                  isLatest
                    ? "border-[#475569] bg-[#F8FAFC] dark:bg-[#1A1E24]"
                    : "border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10] hover:border-[#6B6B66]"
                }`}
              >
                <div className="flex items-center justify-between gap-2 mb-1">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="text-[10px] text-[#6B6B66] dark:text-[#888884]">
                      #{env.id || idx + 1}
                    </span>
                    <span className="font-semibold text-[#111111] dark:text-[#EDEDEA]">
                      {env.sender}
                    </span>
                    <span className="text-[#6B6B66] dark:text-[#888884]">-&gt;</span>
                    <span className="text-[#475569] font-medium">
                      {env.recipient}
                    </span>
                  </div>

                  <span className="text-[10px] text-[#6B6B66] dark:text-[#888884]">
                    {env.timestamp_utc?.slice(11, 19) || "00:00:00"} UTC
                  </span>
                </div>

                <div className="flex items-center justify-between text-[11px] gap-2 pt-1 border-t border-[#E5E5E3]/60 dark:border-[#2A2A2D]/60">
                  <span className="px-1.5 py-0.5 border border-[#E5E5E3] dark:border-[#2A2A2D] text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">
                    {env.message_type}
                  </span>

                  <div className="flex items-center gap-2 text-[10px] text-[#6B6B66] dark:text-[#888884]">
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
