import React from "react";

interface Node {
  id: string;
  role: string;
  management_ip?: string;
  vendor?: string;
}

interface Link {
  source: string;
  source_interface: string;
  target: string;
  target_interface: string;
  speed_bps?: number;
}

interface Props {
  nodes?: Node[];
  links?: Link[];
  affectedDevices?: string[];
}

export const TopologyView: React.FC<Props> = ({
  nodes = [],
  links = [],
  affectedDevices = [],
}) => {
  if (nodes.length === 0) {
    return (
      <div className="bg-[#161618] border border-[#2A2A2D] p-8 text-center text-xs font-mono text-[#888884]">
        No topology graph data available for this incident.
      </div>
    );
  }

  // Calculate coordinates in a deterministic layout
  const width = 640;
  const height = 300;
  const nodeCount = nodes.length;

  const positions: Record<string, { x: number; y: number }> = {};
  nodes.forEach((node, idx) => {
    if (nodeCount === 1) {
      positions[node.id] = { x: width / 2, y: height / 2 };
    } else if (nodeCount === 2) {
      positions[node.id] = {
        x: idx === 0 ? width * 0.3 : width * 0.7,
        y: height / 2,
      };
    } else if (nodeCount === 3) {
      if (node.role.toLowerCase().includes("spine")) {
        positions[node.id] = { x: width / 2, y: height * 0.3 };
      } else if (idx === 0) {
        positions[node.id] = { x: width * 0.25, y: height * 0.7 };
      } else {
        positions[node.id] = { x: width * 0.75, y: height * 0.7 };
      }
    } else {
      const angle = (idx / nodeCount) * 2 * Math.PI - Math.PI / 2;
      positions[node.id] = {
        x: width / 2 + Math.cos(angle) * (width * 0.35),
        y: height / 2 + Math.sin(angle) * (height * 0.35),
      };
    }
  });

  return (
    <div className="bg-[#161618] border border-[#2A2A2D] p-5">
      <div className="flex items-center justify-between border-b border-[#2A2A2D] pb-3 mb-4">
        <h2 className="text-sm font-semibold tracking-wide uppercase font-mono text-[#EDEDEA]">
          Network Topology Graph
        </h2>
        <div className="flex items-center gap-4 text-[10px] font-mono text-[#888884]">
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 bg-[#475569] inline-block"></span> Nominal
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 bg-[#9A5B5B] inline-block"></span> Affected Node
          </span>
        </div>
      </div>

      <div className="bg-[#0F0F10] border border-[#2A2A2D] flex items-center justify-center p-2 overflow-x-auto">
        <svg width={width} height={height} className="max-w-full">
          {/* Render Links */}
          {links.map((link, idx) => {
            const srcPos = positions[link.source];
            const dstPos = positions[link.target];
            if (!srcPos || !dstPos) return null;

            const isAffectedLink =
              affectedDevices.includes(link.source) || affectedDevices.includes(link.target);

            return (
              <g key={idx}>
                <line
                  x1={srcPos.x}
                  y1={srcPos.y}
                  x2={dstPos.x}
                  y2={dstPos.y}
                  stroke={isAffectedLink ? "#9A5B5B" : "#2A2A2D"}
                  strokeWidth={isAffectedLink ? 2 : 1.5}
                  strokeDasharray={isAffectedLink ? "4 2" : undefined}
                />
              </g>
            );
          })}

          {/* Render Nodes */}
          {nodes.map((node) => {
            const pos = positions[node.id];
            if (!pos) return null;
            const isAffected = affectedDevices.includes(node.id);

            return (
              <g key={node.id} transform={`translate(${pos.x}, ${pos.y})`}>
                <rect
                  x="-45"
                  y="-22"
                  width="90"
                  height="44"
                  fill="#161618"
                  stroke={isAffected ? "#9A5B5B" : "#475569"}
                  strokeWidth={isAffected ? "2" : "1"}
                />
                <text
                  x="0"
                  y="-4"
                  textAnchor="middle"
                  fill="#EDEDEA"
                  fontSize="11"
                  fontFamily="JetBrains Mono"
                  fontWeight="600"
                >
                  {node.id}
                </text>
                <text
                  x="0"
                  y="12"
                  textAnchor="middle"
                  fill="#888884"
                  fontSize="9"
                  fontFamily="Inter"
                >
                  {node.role}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
};

