import React, { useMemo, useState } from "react";
import ReactFlow, {
  Background,
  Controls,
  Edge,
  Node,
  Position,
  Handle,
  MarkerType,
} from "reactflow";
import "reactflow/dist/style.css";
import { EnvelopeLogItem } from "../types/protocol";

interface AgentGraphProps {
  activeEnvelope: EnvelopeLogItem | null;
  envelopes: EnvelopeLogItem[];
  onSelectEnvelope: (env: EnvelopeLogItem) => void;
  onFilterAgent?: (agent: string) => void;
}

export interface AgentMetadataItem {
  id: string;
  label: string;
  port: number;
  role: string;
  domain: string;
  x: number;
  y: number;
}

interface CustomNodeData {
  id: string;
  label: string;
  port: number;
  role: string;
  domain: string;
  messageCount: number;
  isSender: boolean;
  isReceiver: boolean;
  onFilterAgent?: (agent: string) => void;
}

const CustomAgentNode: React.FC<{ data: CustomNodeData }> = ({ data }) => {
  const isTarget = data.isReceiver;
  const isSource = data.isSender;

  return (
    <div
      onClick={() => data.onFilterAgent && data.onFilterAgent(data.id)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if ((e.key === "Enter" || e.key === " ") && data.onFilterAgent) {
          e.preventDefault();
          data.onFilterAgent(data.id);
        }
      }}
      aria-label={`Agent ${data.label}, Port ${data.port}, ${data.messageCount} messages recorded`}
      className={`px-3.5 py-2.5 rounded-none border text-xs font-mono transition-all duration-200 cursor-pointer focus-visible:ring-2 focus-visible:ring-[#133E87] dark:focus-visible:ring-[#3A86FF] outline-none ${
        isTarget
          ? "border-[#133E87] bg-[#EEF4FB] dark:border-[#3A86FF] dark:bg-[#1E293B] shadow-sm ring-1 ring-[#133E87]"
          : isSource
          ? "border-[#0B2545] bg-[#F1F5F9] dark:border-[#94A3B8] dark:bg-[#1E2024]"
          : "border-[#E2E8F0] bg-[#FFFFFF] dark:border-[#2A2A2D] dark:bg-[#161618] hover:border-[#64748B]"
      }`}
      style={{ minWidth: "160px" }}
    >
      <Handle type="target" position={Position.Top} className="!bg-[#0B2545] dark:!bg-[#3A86FF] !w-2 !h-2 !border-0" />
      <Handle type="source" position={Position.Bottom} className="!bg-[#0B2545] dark:!bg-[#3A86FF] !w-2 !h-2 !border-0" />
      <Handle type="target" position={Position.Left} className="!bg-[#0B2545] dark:!bg-[#3A86FF] !w-2 !h-2 !border-0" id="left" />
      <Handle type="source" position={Position.Right} className="!bg-[#0B2545] dark:!bg-[#3A86FF] !w-2 !h-2 !border-0" id="right" />

      <div className="flex items-center justify-between gap-2 mb-1">
        <span className="font-bold uppercase tracking-wider text-[11px] text-[#0F172A] dark:text-[#F1F5F9]">
          {data.label}
        </span>
        <span className="text-[10px] font-mono text-[#475569] dark:text-[#94A3B8]">
          :{data.port}
        </span>
      </div>

      <div className="text-[10px] text-[#475569] dark:text-[#94A3B8] mb-1.5 leading-snug">
        {data.role}
      </div>

      <div className="flex items-center justify-between text-[10px] pt-1.5 border-t border-[#E2E8F0] dark:border-[#2A2A2D]">
        <span className="text-[#475569] dark:text-[#94A3B8]">Messages</span>
        <span className="font-bold text-[#0F172A] dark:text-[#F1F5F9]">
          {data.messageCount}
        </span>
      </div>
    </div>
  );
};

const nodeTypes = {
  agentNode: CustomAgentNode,
};

export const AGENT_METADATA: AgentMetadataItem[] = [
  { id: "gateway", label: "Gateway", port: 8006, role: "Ingestion & Adapter", domain: "Normalized Wire Telemetry Ingestion", x: 260, y: 20 },
  { id: "orchestrator", label: "Orchestrator", port: 8000, role: "LangGraph Mediator", domain: "Consensus Orchestration & Inquiry Dispatch", x: 260, y: 135 },
  { id: "telemetry_agent", label: "Telemetry Agent", port: 8001, role: "Metrics Specialist", domain: "Queue Drops, Traffic & Interface Metrics", x: 20, y: 260 },
  { id: "topology_agent", label: "Topology Agent", port: 8002, role: "Graph & Flaps", domain: "Topology Footprint & Link Flap Frequency", x: 180, y: 260 },
  { id: "config_agent", label: "Config Agent", port: 8003, role: "Diff & MTU", domain: "Configuration Drift & MTU Mismatch", x: 340, y: 260 },
  { id: "log_agent", label: "Log Agent", port: 8004, role: "Syslog & Events", domain: "Syslog Event Correlation & BGP Flaps", x: 500, y: 260 },
  { id: "classifier_agent", label: "Classifier Agent", port: 8007, role: "ML Classifier & Calibrator", domain: "Softmax Classification & Conformal Sets", x: 100, y: 395 },
  { id: "wifi_services_agent", label: "Wi-Fi & Services", port: 8008, role: "Wireless RF & Services", domain: "Wi-Fi RSSI, Channel Load & Core Services", x: 420, y: 395 },
  { id: "synthesizer_agent", label: "Synthesizer", port: 8005, role: "Root Cause Aggregator", domain: "Unified Report Synthesis & Remediation", x: 260, y: 520 },
];

export const AgentGraph: React.FC<AgentGraphProps> = ({
  activeEnvelope,
  envelopes,
  onSelectEnvelope,
  onFilterAgent,
}) => {
  const [viewMode, setViewMode] = useState<"graph" | "table">("graph");

  // Count envelopes per agent
  const messageCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const env of envelopes) {
      counts[env.sender] = (counts[env.sender] || 0) + 1;
      counts[env.recipient] = (counts[env.recipient] || 0) + 1;
    }
    return counts;
  }, [envelopes]);

  // Construct nodes
  const nodes: Node[] = useMemo(() => {
    const activeSender = activeEnvelope?.sender;
    const activeReceiver = activeEnvelope?.recipient;

    return AGENT_METADATA.map((agent) => ({
      id: agent.id,
      type: "agentNode",
      position: { x: agent.x, y: agent.y },
      data: {
        id: agent.id,
        label: agent.label,
        port: agent.port,
        role: agent.role,
        domain: agent.domain,
        messageCount: messageCounts[agent.id] || 0,
        isSender: activeSender === agent.id,
        isReceiver: activeReceiver === agent.id,
        onFilterAgent,
      },
    }));
  }, [activeEnvelope, messageCounts, onFilterAgent]);

  // Construct edges representing complete 9-agent communication topology
  const edges: Edge[] = useMemo(() => {
    const baseEdges: Array<{ id: string; source: string; target: string }> = [
      { id: "gw-orch", source: "gateway", target: "orchestrator" },
      { id: "orch-telem", source: "orchestrator", target: "telemetry_agent" },
      { id: "orch-topo", source: "orchestrator", target: "topology_agent" },
      { id: "orch-cfg", source: "orchestrator", target: "config_agent" },
      { id: "orch-log", source: "orchestrator", target: "log_agent" },
      { id: "orch-cls", source: "orchestrator", target: "classifier_agent" },
      { id: "orch-wifi", source: "orchestrator", target: "wifi_services_agent" },
      { id: "orch-synth", source: "orchestrator", target: "synthesizer_agent" },
    ];

    const currentSender = activeEnvelope?.sender;
    const currentReceiver = activeEnvelope?.recipient;

    return baseEdges.map((e) => {
      const isCurrentlyActive =
        (e.source === currentSender && e.target === currentReceiver) ||
        (e.source === currentReceiver && e.target === currentSender);

      return {
        id: e.id,
        source: e.source,
        target: e.target,
        animated: isCurrentlyActive,
        style: {
          stroke: isCurrentlyActive ? "#133E87" : "#64748B",
          strokeWidth: isCurrentlyActive ? 2.5 : 1,
          transition: "all 200ms ease-out",
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: isCurrentlyActive ? "#133E87" : "#64748B",
          width: 12,
          height: 12,
        },
      };
    });
  }, [activeEnvelope]);

  return (
    <div className="w-full bg-[#FFFFFF] dark:bg-[#161618] border border-[#E2E8F0] dark:border-[#2A2A2D] flex flex-col font-sans">
      {/* Header with Title and Accessible View Switcher */}
      <div className="p-3.5 border-b border-[#E2E8F0] dark:border-[#2A2A2D] flex flex-wrap items-center justify-between gap-3 bg-[#F8FAFC] dark:bg-[#0F0F10]">
        <div>
          <h2 className="text-xs font-bold uppercase tracking-wider text-[#0B2545] dark:text-[#F1F5F9]">
            Multi-Agent Architecture & Protocol Graph
          </h2>
          <div className="text-[11px] text-[#475569] dark:text-[#94A3B8]">
            {activeEnvelope
              ? `Active Wire Transmission: ${activeEnvelope.sender} → ${activeEnvelope.recipient} (${activeEnvelope.message_type})`
              : "9 Backend Services Registered &middot; Select agent to inspect or filter message ledger"}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Accessible Table vs Visual Graph Switcher */}
          <div
            role="tablist"
            aria-label="Agent view mode selector"
            className="flex items-center border border-[#CBD5E1] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-0.5"
          >
            <button
              role="tab"
              aria-selected={viewMode === "graph"}
              onClick={() => setViewMode("graph")}
              className={`px-3 py-1 text-xs font-semibold transition-colors focus-visible:ring-2 focus-visible:ring-[#133E87] ${
                viewMode === "graph"
                  ? "bg-[#0B2545] text-white dark:bg-[#133E87]"
                  : "text-[#475569] dark:text-[#94A3B8] hover:text-[#0F172A] dark:hover:text-[#F1F5F9]"
              }`}
            >
              Graph View
            </button>
            <button
              role="tab"
              aria-selected={viewMode === "table"}
              onClick={() => setViewMode("table")}
              className={`px-3 py-1 text-xs font-semibold transition-colors focus-visible:ring-2 focus-visible:ring-[#133E87] ${
                viewMode === "table"
                  ? "bg-[#0B2545] text-white dark:bg-[#133E87]"
                  : "text-[#475569] dark:text-[#94A3B8] hover:text-[#0F172A] dark:hover:text-[#F1F5F9]"
              }`}
            >
              Accessible Table View
            </button>
          </div>

          {activeEnvelope && (
            <button
              onClick={() => onSelectEnvelope(activeEnvelope)}
              className="px-3 py-1 bg-[#FFFFFF] dark:bg-[#161618] border border-[#CBD5E1] dark:border-[#2A2A2D] text-xs font-semibold hover:border-[#0B2545] text-[#0B2545] dark:text-[#F1F5F9] transition-all min-h-[28px] focus-visible:ring-2"
            >
              View Envelope JSON
            </button>
          )}
        </div>
      </div>

      {/* Main View Area */}
      {viewMode === "graph" ? (
        <div className="w-full h-[540px] relative">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            proOptions={{ hideAttribution: true }}
          >
            <Background color="#94A3B8" gap={16} size={1} />
            <Controls className="!bg-[#FFFFFF] dark:!bg-[#161618] !border-[#CBD5E1] dark:!border-[#2A2A2D] !fill-[#0F172A] dark:!fill-[#F1F5F9]" />
          </ReactFlow>
        </div>
      ) : (
        /* Accessible Table Alternative (WCAG 2.2 AA compliant tabular view) */
        <div className="p-4 overflow-x-auto">
          <table
            className="w-full text-left border-collapse text-xs font-sans"
            aria-label="Agent Registry Table"
          >
            <caption className="sr-only">
              List of 7 specialist agents plus gateway and orchestrator, their network ports, domains of diagnostic expertise, and message traffic statistics.
            </caption>
            <thead>
              <tr className="border-b border-[#CBD5E1] dark:border-[#2A2A2D] bg-[#F1F5F9] dark:bg-[#0F0F10] text-[11px] uppercase tracking-wider text-[#475569] dark:text-[#94A3B8]">
                <th scope="col" className="p-3 font-bold">Agent Name</th>
                <th scope="col" className="p-3 font-bold">Service Port</th>
                <th scope="col" className="p-3 font-bold">Operational Role</th>
                <th scope="col" className="p-3 font-bold">Diagnostic Domain</th>
                <th scope="col" className="p-3 font-bold text-center">Messages Handled</th>
                <th scope="col" className="p-3 font-bold text-right">Filter Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E2E8F0] dark:divide-[#2A2A2D]">
              {AGENT_METADATA.map((agent) => {
                const count = messageCounts[agent.id] || 0;
                const isSelected =
                  activeEnvelope?.sender === agent.id || activeEnvelope?.recipient === agent.id;

                return (
                  <tr
                    key={agent.id}
                    className={`hover:bg-[#F8FAFC] dark:hover:bg-[#1E293B]/50 transition-colors ${
                      isSelected ? "bg-[#EEF4FB] dark:bg-[#1E293B]" : ""
                    }`}
                  >
                    <td className="p-3 font-bold text-[#0F172A] dark:text-[#F1F5F9] flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-[#15803D]"></span>
                      {agent.label}
                    </td>
                    <td className="p-3 font-mono text-[#475569] dark:text-[#94A3B8]">
                      :{agent.port}
                    </td>
                    <td className="p-3 font-semibold text-[#0B2545] dark:text-[#3A86FF]">
                      {agent.role}
                    </td>
                    <td className="p-3 text-[#475569] dark:text-[#94A3B8]">
                      {agent.domain}
                    </td>
                    <td className="p-3 text-center font-mono font-bold text-[#0F172A] dark:text-[#F1F5F9]">
                      {count}
                    </td>
                    <td className="p-3 text-right">
                      {onFilterAgent && (
                        <button
                          onClick={() => onFilterAgent(agent.id)}
                          className="px-2.5 py-1 text-xs border border-[#CBD5E1] dark:border-[#2A2A2D] hover:border-[#0B2545] hover:bg-[#EEF4FB] dark:hover:bg-[#1E293B] text-[#0B2545] dark:text-[#F1F5F9] font-medium transition-colors focus-visible:ring-2 focus-visible:ring-[#133E87]"
                        >
                          Filter Telemetry
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
