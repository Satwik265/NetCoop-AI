import React, { useState } from "react";
import { formatRate } from "../utils/i18n";

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
  const [viewMode, setViewMode] = useState<"visual" | "table">("visual");

  // When topology is unavailable (e.g. organizer data with no link graph or empty nodes)
  if (!nodes || nodes.length === 0 || !links || links.length === 0) {
    return (
      <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E2E8F0] dark:border-[#2A2A2D] p-8 text-center font-sans space-y-2">
        <div className="text-xs font-bold uppercase tracking-wider text-[#475569] dark:text-[#94A3B8]">
          Topology Unavailable
        </div>
        <div className="text-[11px] text-[#475569] dark:text-[#94A3B8] max-w-md mx-auto">
          The selected dataset contains standalone device records without physical or logical link definitions.
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
    <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E2E8F0] dark:border-[#2A2A2D] p-5 space-y-4 font-sans">
      <div className="flex flex-wrap items-center justify-between border-b border-[#E2E8F0] dark:border-[#2A2A2D] pb-3 gap-3">
        <div>
          <h2 className="text-xs font-bold uppercase tracking-wider text-[#0B2545] dark:text-[#F1F5F9]">
            Campus Network Topology & Remediation Blast Radius Map
          </h2>
          <div className="text-[11px] text-[#475569] dark:text-[#94A3B8]">
            {affectedDevices.length > 0
              ? `Direct Fault Entity: ${affectedDevices.join(", ")} | Blast Radius Boundary: ${blastRadiusDevices.length} devices`
              : "All monitored campus switches, routers, and access points reporting nominal telemetry."}
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Accessible Table Switcher */}
          <div
            role="tablist"
            aria-label="Topology display mode"
            className="flex items-center border border-[#CBD5E1] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-0.5"
          >
            <button
              role="tab"
              aria-selected={viewMode === "visual"}
              onClick={() => setViewMode("visual")}
              className={`px-3 py-1 text-xs font-semibold transition-colors focus-visible:ring-2 focus-visible:ring-[#133E87] ${
                viewMode === "visual"
                  ? "bg-[#0B2545] text-white dark:bg-[#133E87]"
                  : "text-[#475569] dark:text-[#94A3B8] hover:text-[#0F172A] dark:hover:text-[#F1F5F9]"
              }`}
            >
              Visual Map
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
        </div>
      </div>

      {viewMode === "visual" ? (
        <div className="space-y-3">
          {/* Legend */}
          <div className="flex flex-wrap items-center gap-4 text-xs font-medium text-[#475569] dark:text-[#94A3B8]">
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-3 border border-[#0B2545] dark:border-[#94A3B8] bg-[#F1F5F9] dark:bg-[#161618] inline-block"></span> Nominal Node
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-3 border-2 border-[#DC2626] bg-[#FEF2F2] dark:bg-[#7F1D1D]/30 inline-block"></span> Fault Root Device
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-5 h-1.5 bg-[#133E87] dark:bg-[#3A86FF] inline-block"></span> Blast Radius Link
            </span>
            <span className="text-[11px] text-[#475569] dark:text-[#94A3B8]">
              [SIM] = Simulated Sandbox Node
            </span>
          </div>

          <div className="bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#E2E8F0] dark:border-[#2A2A2D] flex items-center justify-center p-3 overflow-x-auto">
            <svg width={width} height={height} className="max-w-full" aria-hidden="true">
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

                const strokeColor = isAffectedLink ? "#DC2626" : isBlastRadiusLink ? "#133E87" : "#CBD5E1";
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
                      fill={isAffected ? "#FEF2F2" : "#FFFFFF"}
                      stroke={isAffected ? "#DC2626" : isBlastRadius ? "#133E87" : "#CBD5E1"}
                      strokeWidth={isAffected ? 2.5 : isBlastRadius ? 2.0 : 1.0}
                    />
                    <text
                      x="0"
                      y="-4"
                      textAnchor="middle"
                      fill={isAffected ? "#991B1B" : "#0F172A"}
                      fontSize="11"
                      fontFamily="JetBrains Mono, monospace"
                      fontWeight={isAffected ? "700" : "600"}
                    >
                      {node.id}
                    </text>
                    <text
                      x="0"
                      y="12"
                      textAnchor="middle"
                      fill={isAffected ? "#DC2626" : "#475569"}
                      fontSize="9"
                      fontFamily="Inter, sans-serif"
                      fontWeight="600"
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
      ) : (
        /* Accessible Table Alternative (WCAG 2.2 AA compliant tabular view) */
        <div className="space-y-6">
          {/* Nodes Table */}
          <div className="space-y-2">
            <h3 className="text-xs font-bold uppercase tracking-wider text-[#0B2545] dark:text-[#F1F5F9]">
              Network Nodes & Impact Scope ({nodes.length} devices)
            </h3>
            <div className="overflow-x-auto border border-[#E2E8F0] dark:border-[#2A2A2D]">
              <table className="w-full text-left border-collapse text-xs font-sans" aria-label="Topology Nodes Table">
                <caption className="sr-only">List of network topology devices, roles, management IPs, and failure impact status</caption>
                <thead>
                  <tr className="border-b border-[#CBD5E1] dark:border-[#2A2A2D] bg-[#F1F5F9] dark:bg-[#0F0F10] text-[11px] uppercase tracking-wider text-[#475569] dark:text-[#94A3B8]">
                    <th scope="col" className="p-2.5 font-bold">Device ID</th>
                    <th scope="col" className="p-2.5 font-bold">Architecture Role</th>
                    <th scope="col" className="p-2.5 font-bold">Vendor</th>
                    <th scope="col" className="p-2.5 font-bold">Management IP</th>
                    <th scope="col" className="p-2.5 font-bold">Incident Impact</th>
                    <th scope="col" className="p-2.5 font-bold">Blast Radius Boundary</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E2E8F0] dark:divide-[#2A2A2D]">
                  {nodes.map((node) => {
                    const isAffected = affectedDevices.includes(node.id);
                    const isBlast = blastRadiusDevices.includes(node.id);

                    return (
                      <tr
                        key={node.id}
                        className={`hover:bg-[#F8FAFC] dark:hover:bg-[#1E293B]/50 transition-colors ${
                          isAffected ? "bg-[#FEF2F2] dark:bg-[#7F1D1D]/20" : ""
                        }`}
                      >
                        <td className="p-2.5 font-mono font-bold text-[#0F172A] dark:text-[#F1F5F9]">
                          {node.id} {node.simulated && <span className="text-[10px] text-[#475569]">[SIM]</span>}
                        </td>
                        <td className="p-2.5 font-semibold text-[#0B2545] dark:text-[#3A86FF]">
                          {node.role}
                        </td>
                        <td className="p-2.5 text-[#475569] dark:text-[#94A3B8]">
                          {node.vendor || "Cisco / Arista (Campus Core)"}
                        </td>
                        <td className="p-2.5 font-mono text-[#475569] dark:text-[#94A3B8]">
                          {node.management_ip || "10.100.0.1"}
                        </td>
                        <td className="p-2.5">
                          {isAffected ? (
                            <span className="px-2 py-0.5 border border-[#DC2626]/40 bg-[#FEF2F2] text-[#DC2626] dark:bg-[#7F1D1D]/30 dark:text-[#FCA5A5] text-[10px] font-bold uppercase">
                              Primary Fault Root
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 border border-[#15803D]/40 bg-[#F0FDF4] text-[#15803D] dark:bg-[#14532D]/30 dark:text-[#86EFAC] text-[10px] font-semibold uppercase">
                              Nominal Operational
                            </span>
                          )}
                        </td>
                        <td className="p-2.5">
                          {isBlast ? (
                            <span className="px-2 py-0.5 border border-[#133E87]/40 bg-[#EEF4FB] text-[#133E87] dark:bg-[#1E3A8A]/30 dark:text-[#93C5FD] text-[10px] font-bold uppercase">
                              In Remediation Scope
                            </span>
                          ) : (
                            <span className="text-[#64748B] text-[11px]">Isolated</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Links Table */}
          <div className="space-y-2">
            <h3 className="text-xs font-bold uppercase tracking-wider text-[#0B2545] dark:text-[#F1F5F9]">
              Physical & Logical Links ({links.length} interconnections)
            </h3>
            <div className="overflow-x-auto border border-[#E2E8F0] dark:border-[#2A2A2D]">
              <table className="w-full text-left border-collapse text-xs font-sans" aria-label="Topology Links Table">
                <caption className="sr-only">List of network links, interface pairs, link bandwidth, and blast radius state</caption>
                <thead>
                  <tr className="border-b border-[#CBD5E1] dark:border-[#2A2A2D] bg-[#F1F5F9] dark:bg-[#0F0F10] text-[11px] uppercase tracking-wider text-[#475569] dark:text-[#94A3B8]">
                    <th scope="col" className="p-2.5 font-bold">Source Device</th>
                    <th scope="col" className="p-2.5 font-bold">Source Interface</th>
                    <th scope="col" className="p-2.5 font-bold">Target Device</th>
                    <th scope="col" className="p-2.5 font-bold">Target Interface</th>
                    <th scope="col" className="p-2.5 font-bold">Capacity / Speed</th>
                    <th scope="col" className="p-2.5 font-bold">Path Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E2E8F0] dark:divide-[#2A2A2D]">
                  {links.map((link, idx) => {
                    const isBlastLink =
                      (blastRadiusDevices.includes(link.source) && blastRadiusDevices.includes(link.target)) ||
                      (affectedDevices.includes(link.source) && blastRadiusDevices.includes(link.target));
                    const isAffectedLink =
                      affectedDevices.includes(link.source) || affectedDevices.includes(link.target);

                    return (
                      <tr key={idx} className="hover:bg-[#F8FAFC] dark:hover:bg-[#1E293B]/50 transition-colors">
                        <td className="p-2.5 font-mono font-bold text-[#0F172A] dark:text-[#F1F5F9]">
                          {link.source}
                        </td>
                        <td className="p-2.5 font-mono text-[#475569] dark:text-[#94A3B8]">
                          {link.source_interface}
                        </td>
                        <td className="p-2.5 font-mono font-bold text-[#0F172A] dark:text-[#F1F5F9]">
                          {link.target}
                        </td>
                        <td className="p-2.5 font-mono text-[#475569] dark:text-[#94A3B8]">
                          {link.target_interface}
                        </td>
                        <td className="p-2.5 font-mono font-semibold text-[#0B2545] dark:text-[#3A86FF]">
                          {link.speed_bps ? formatRate(link.speed_bps) : "10 Gbps"}
                        </td>
                        <td className="p-2.5">
                          {isAffectedLink ? (
                            <span className="text-[#DC2626] font-bold text-[10px] uppercase">
                              Degraded / Saturated Path
                            </span>
                          ) : isBlastLink ? (
                            <span className="text-[#133E87] dark:text-[#3A86FF] font-semibold text-[10px] uppercase">
                              Remediation Rebalance Path
                            </span>
                          ) : (
                            <span className="text-[#15803D] font-medium text-[10px] uppercase">
                              Nominal Transit
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
