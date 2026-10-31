import React from "react";

interface Node {
  id: string;
  role: string;
  management_ip?: string;
  vendor?: string;
  display_name?: string;
  simulated?: boolean;
  layout_position?: { x: number; y: number };
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
  blastRadiusDevices?: string[];
}

export const TopologyView: React.FC<Props> = ({
  nodes = [],
  links = [],
  affectedDevices = [],
  blastRadiusDevices = [],
}) => {
  // When topology is unavailable (e.g. organizer data with no link graph or empty nodes)
  if (!nodes || nodes.length === 0 || !links || links.length === 0) {
    return (
      <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D] p-8 text-center font-mono space-y-2">
        <div className="text-xs font-semibold uppercase tracking-wider text-[#6B6B66] dark:text-[#888884]">
          Topology Unavailable
        </div>
        <div className="text-[11px] text-[#6B6B66] dark:text-[#888884] max-w-md mx-auto">
          The selected dataset (such as organizer Colab telemetry or isolated endpoints) contains unlinked device records without physical or logical link definitions.
        </div>
      </div>
    );
  }

  const width = 640;
  const height = 300;
  const nodeCount = nodes.length;

  const positions: Record<string, { x: number; y: number }> = {};
  nodes.forEach((node, idx) => {
    if (
      node.layout_position &&
      typeof node.layout_position.x === "number" &&
      typeof node.layout_position.y === "number"
    ) {
      positions[node.id] = {
        x: Math.round(node.layout_position.x * width),
        y: Math.round(node.layout_position.y * height),
      };
    } else if (nodeCount === 1) {
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
    <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D] p-5 space-y-4 font-mono">
      <div className="flex flex-wrap items-center justify-between border-b border-[#E5E5E3] dark:border-[#2A2A2D] pb-3 gap-3">
        <div>
          <h2 className="text-xs font-semibold uppercase tracking-wider text-[#111111] dark:text-[#EDEDEA]">
            Network Topology & Blast Radius Map
          </h2>
          <div className="text-[10px] text-[#6B6B66] dark:text-[#888884]">
            Affected nodes outlined in bold; remediation blast radius highlighted by link weight.
          </div>
        </div>

        <div className="flex items-center gap-4 text-[10px] text-[#6B6B66] dark:text-[#888884]">
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 border border-[#475569] inline-block"></span> Nominal Node
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 border-2 border-[#9A5B5B] inline-block"></span> Affected Node
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-4 h-1 bg-[#475569] inline-block"></span> Blast Radius Path
          </span>
          <span className="flex items-center gap-1 text-[9px] text-[#888884]">
            [SIM] = Simulated Node
          </span>
        </div>
      </div>

      <div className="bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] flex items-center justify-center p-3 overflow-x-auto">
        <svg width={width} height={height} className="max-w-full">
          {/* Render Links */}
          {links.map((link, idx) => {
            const srcPos = positions[link.source];
            const dstPos = positions[link.target];
            if (!srcPos || !dstPos) return null;

            const isBlastRadiusLink =
              (blastRadiusDevices.includes(link.source) && blastRadiusDevices.includes(link.target)) ||
              (affectedDevices.includes(link.source) && blastRadiusDevices.includes(link.target));

            const isAffectedLink =
              affectedDevices.includes(link.source) || affectedDevices.includes(link.target);

            const strokeColor = isAffectedLink ? "#9A5B5B" : isBlastRadiusLink ? "#475569" : "#2A2A2D";
            const strokeWidth = isBlastRadiusLink ? 3.5 : isAffectedLink ? 2.5 : 1.2;

            return (
              <g key={idx}>
                <line
                  x1={srcPos.x}
                  y1={srcPos.y}
                  x2={dstPos.x}
                  y2={dstPos.y}
                  stroke={strokeColor}
                  strokeWidth={strokeWidth}
                  strokeDasharray={isAffectedLink && !isBlastRadiusLink ? "4 2" : undefined}
                  className="transition-all duration-200"
                />
              </g>
            );
          })}

          {/* Render Nodes */}
          {nodes.map((node) => {
            const pos = positions[node.id];
            if (!pos) return null;
            const isAffected = affectedDevices.includes(node.id);
            const isBlastRadius = blastRadiusDevices.includes(node.id);

            return (
              <g key={node.id} transform={`translate(${pos.x}, ${pos.y})`}>
                <rect
                  x="-48"
                  y="-22"
                  width="96"
                  height="44"
                  className="transition-all duration-200"
                  fill="#161618"
                  stroke={isAffected ? "#9A5B5B" : isBlastRadius ? "#EDEDEA" : "#475569"}
                  strokeWidth={isAffected ? 2.5 : isBlastRadius ? 2.0 : 1.0}
                />
                <text
                  x="0"
                  y="-4"
                  textAnchor="middle"
                  fill="#EDEDEA"
                  fontSize="11"
                  fontFamily="JetBrains Mono"
                  fontWeight={isAffected ? "700" : "600"}
                >
                  {node.id}
                </text>
                <text
                  x="0"
                  y="12"
                  textAnchor="middle"
                  fill={isAffected ? "#9A5B5B" : "#888884"}
                  fontSize="9"
                  fontFamily="Inter"
                  style={{ textTransform: "uppercase" }}
                >
                  {isAffected ? "FAULT ROOT" : node.simulated ? `[SIM] ${node.role}` : node.role}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
};
