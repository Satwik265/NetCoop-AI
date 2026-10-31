import React, { useState } from "react";
import { EnvelopeLogItem } from "../types/protocol";

interface Props {
  envelopes: EnvelopeLogItem[];
  loading: boolean;
}

export const EnvelopeTrace: React.FC<Props> = ({ envelopes, loading }) => {
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [filterSender, setFilterSender] = useState<string>("all");

  if (loading) {
    return (
      <div className="bg-[#161618] border border-[#2A2A2D] p-6 text-center text-xs font-mono text-[#888884] animate-pulse">
        Loading auditable envelope logs...
      </div>
    );
  }

  const senders = ["all", ...Array.from(new Set(envelopes.map((e) => e.sender)))];
  const filtered =
    filterSender === "all"
      ? envelopes
      : envelopes.filter((e) => e.sender === filterSender);

  return (
    <div className="bg-[#161618] border border-[#2A2A2D] p-5">
      <div className="flex flex-wrap items-center justify-between border-b border-[#2A2A2D] pb-3 mb-4 gap-3">
        <h2 className="text-sm font-semibold tracking-wide uppercase font-mono text-[#EDEDEA]">
          Auditable Envelope Trace ({envelopes.length} Envelopes)
        </h2>

        <div className="flex items-center gap-2 text-xs font-mono">
          <span className="text-[#888884]">Filter Sender:</span>
          <select
            value={filterSender}
            onChange={(e) => setFilterSender(e.target.value)}
            className="bg-[#0F0F10] border border-[#2A2A2D] text-[#EDEDEA] px-2 py-1 text-xs font-mono outline-none focus:border-[#475569]"
          >
            {senders.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="text-xs text-[#888884] font-mono py-6 text-center">
          No envelope logs match filter criteria.
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((env) => {
            const isExpanded = expandedId === env.id;
            return (
              <div
                key={env.id}
                className="bg-[#0F0F10] border border-[#2A2A2D] text-xs font-mono"
              >
                <div
                  onClick={() => setExpandedId(isExpanded ? null : env.id)}
                  className="p-3 flex flex-wrap items-center justify-between gap-3 cursor-pointer hover:bg-[#161618] transition-colors"
                >
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[#888884]">
                      {env.timestamp_utc.slice(11, 19)} UTC
                    </span>
                    <span className="text-[#EDEDEA] font-semibold">
                      {env.sender}
                    </span>
                    <span className="text-[#888884]">-&gt;</span>
                    <span className="text-[#475569] font-semibold">
                      {env.recipient}
                    </span>
                    <span className="px-2 py-0.5 border border-[#2A2A2D] text-[10px] uppercase text-[#EDEDEA]">
                      {env.message_type}
                    </span>
                  </div>

                  <div className="flex items-center gap-3">
                    <span className="text-[10px] text-[#888884]">
                      v1.0.0 | prio: {env.priority}
                    </span>
                    <span className="text-[#888884]">
                      {isExpanded ? "[-]" : "[+]"}
                    </span>
                  </div>
                </div>

                {isExpanded && (
                  <div className="p-3 border-t border-[#2A2A2D] bg-[#0A0A0B] text-[11px] overflow-x-auto text-[#EDEDEA]">
                    <div className="text-[#888884] text-[10px] uppercase mb-1">
                      Payload:
                    </div>
                    <pre className="text-[#EDEDEA] leading-relaxed">
                      {JSON.stringify(env.payload, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
