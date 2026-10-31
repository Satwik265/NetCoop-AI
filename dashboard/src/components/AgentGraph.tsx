import React, { useMemo } from "react";
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

interface CustomNodeData {
  id: string;
  label: string;
  port: number;
  role: string;
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
      className={`px-4 py-3 rounded-none border text-xs font-mono transition-all duration-200 cursor-pointer ${
        isTarget
          ? "border-[#475569] bg-[#1F232B] dark:border-[#EDEDEA] dark:bg-[#1E2024] shadow-sm ring-1 ring-[#475569]"
          : isSource
          ? "border-[#475569] bg-[#F1F3F5] dark:border-[#475569] dark:bg-[#1B1D21]"
          : "border-[#E5E5E3] bg-[#FFFFFF] dark:border-[#2A2A2D] dark:bg-[#161618] hover:border-[#6B6B66]"
      }`}
      style={{ minWidth: "155px" }}
    >
      <Handle type="target" position={Position.Top} className="!bg-[#475569] !w-2 !h-2 !border-0" />
      <Handle type="source" position={Position.Bottom} className="!bg-[#475569] !w-2 !h-2 !border-0" />
      <Handle type="target" position={Position.Left} className="!bg-[#475569] !w-2 !h-2 !border-0" id="left" />
      <Handle type="source" position={Position.Right} className="!bg-[#475569] !w-2 !h-2 !border-0" id="right" />

      <div className="flex items-center justify-between gap-2 mb-1">
        <span className="font-semibold uppercase tracking-wider text-[11px] text-[#111111] dark:text-[#EDEDEA]">
          {data.label}
        </span>
        <span className="text-[10px] text-[#6B6B66] dark:text-[#888884]">
          :{data.port}
        </span>
      </div>

      <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] mb-2">
        {data.role}
      </div>

      <div className="flex items-center justify-between text-[10px] pt-1.5 border-t border-[#E5E5E3] dark:border-[#2A2A2D]">
        <span className="text-[#6B6B66] dark:text-[#888884]">Messages</span>
        <span className="font-semibold text-[#111111] dark:text-[#EDEDEA]">
          {data.messageCount}
        </span>
      </div>
    </div>
  );
};

const nodeTypes = {
  agentNode: CustomAgentNode,
};

const AGENT_METADATA = [
  { id: "gateway", label: "Gateway", port: 8006, role: "Ingestion & Adapter", x: 260, y: 30 },
  { id: "orchestrator", label: "Orchestrator", port: 8000, role: "LangGraph Mediator", x: 260, y: 150 },
  { id: "telemetry_agent", label: "Telemetry", port: 8001, role: "Metrics Specialist", x: 40, y: 300 },
  { id: "topology_agent", label: "Topology", port: 8002, role: "Graph & Flaps", x: 190, y: 300 },
  { id: "config_agent", label: "Config", port: 8003, role: "Diff & MTU", x: 340, y: 300 },
  { id: "log_agent", label: "Log", port: 8004, role: "Syslog & Events", x: 490, y: 300 },
  { id: "synthesizer_agent", label: "Synthesizer", port: 8005, role: "Root Cause Aggregator", x: 260, y: 440 },
];

export const AgentGraph: React.FC<AgentGraphProps> = ({
  activeEnvelope,
  envelopes,
  onSelectEnvelope,
  onFilterAgent,
}) => {
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
        messageCount: messageCounts[agent.id] || 0,
        isSender: activeSender === agent.id,
        isReceiver: activeReceiver === agent.id,
        onFilterAgent,
      },
    }));
  }, [activeEnvelope, messageCounts, onFilterAgent]);

  // Construct edges representing communication topology
  const edges: Edge[] = useMemo(() => {
    const baseEdges: Array<{ id: string; source: string; target: string }> = [
      { id: "gw-orch", source: "gateway", target: "orchestrator" },
      { id: "orch-telem", source: "orchestrator", target: "telemetry_agent" },
      { id: "orch-topo", source: "orchestrator", target: "topology_agent" },
      { id: "orch-cfg", source: "orchestrator", target: "config_agent" },
      { id: "orch-log", source: "orchestrator", target: "log_agent" },
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
          stroke: isCurrentlyActive ? "#EDEDEA" : "#475569",
          strokeWidth: isCurrentlyActive ? 2 : 1,
          transition: "all 200ms ease-out",
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: isCurrentlyActive ? "#EDEDEA" : "#475569",
          width: 12,
          height: 12,
        },
      };
    });
  }, [activeEnvelope]);

  return (
    <div className="w-full h-[520px] bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D] relative">
      <div className="absolute top-3 left-4 z-10 font-mono">
        <div className="text-xs font-semibold uppercase tracking-wider text-[#111111] dark:text-[#EDEDEA]">
          Live Inter-Agent Communication Topology
        </div>
        <div className="text-[10px] text-[#6B6B66] dark:text-[#888884]">
          {activeEnvelope
            ? `Active: ${activeEnvelope.sender} -> ${activeEnvelope.recipient} (${activeEnvelope.message_type})`
            : "Click a node to filter, or a timeline envelope to animate route"}
        </div>
      </div>

      {activeEnvelope && (
        <button
          onClick={() => onSelectEnvelope(activeEnvelope)}
          className="absolute top-3 right-4 z-10 px-3 py-1 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] text-[11px] font-mono hover:border-[#475569] text-[#111111] dark:text-[#EDEDEA] transition-all"
        >
          View Envelope JSON
        </button>
      )}

      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#2A2A2D" gap={16} size={1} />
        <Controls className="!bg-[#161618] !border-[#2A2A2D] !fill-[#EDEDEA]" />
      </ReactFlow>
    </div>
  );
};
