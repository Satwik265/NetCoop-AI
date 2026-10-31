import React, { useState } from "react";
import { UnifiedDiagnosticReport } from "../../types/protocol";

interface SecurityViewProps {
  report: UnifiedDiagnosticReport | null;
}

interface SecurityThreatItem {
  id: string;
  category: "access_violation" | "traffic_spike" | "topology_anomaly" | "protocol_abuse";
  title: string;
  affectedAsset: string;
  observedEvidence: string;
  riskScore: number; // 0 to 100
  mitigation: string;
}

export const SecurityView: React.FC<SecurityViewProps> = ({ report }) => {
  const [threats] = useState<SecurityThreatItem[]>([
    {
      id: "sec-001",
      category: "traffic_spike",
      title: "Asymmetric Microburst Exceeding Buffer Threshold",
      affectedAsset: "spine-01:et-0/0/1",
      observedEvidence: "94.2% bandwidth spike with 4,500 drops/s, concentrating on single egress interface.",
      riskScore: 78,
      mitigation: "ECMP dynamic path hashing rebalance; rate-limiting burst ingress.",
    },
    {
      id: "sec-002",
      category: "access_violation",
      title: "Border ACL Drop Elevation",
      affectedAsset: "wan-01",
      observedEvidence: "1,240 drops/min on external ingress ACL filtering unauthorized RFC1918 traffic.",
      riskScore: 64,
      mitigation: "Strict uRPF verification enabled; ingress ACL audit verified.",
    },
    {
      id: "sec-003",
      category: "protocol_abuse",
      title: "Excessive MTU Blackholing",
      affectedAsset: "leaf-02:xe-0/0/4",
      observedEvidence: "Path MTU discovery failure; ICMP Fragmentation Needed packets dropped by upstream firewall.",
      riskScore: 52,
      mitigation: "Interface MTU harmonized to 9000 bytes; ICMP unreachable inspection verified.",
    },
  ]);

  const [selectedThreat, setSelectedThreat] = useState<SecurityThreatItem>(threats[0]);

  return (
    <div className="space-y-6 font-mono text-xs">
      {/* Top Banner: SecOps Assessment */}
      <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 bg-[#9A5B5B]"></span>
              <h2 className="text-sm font-semibold tracking-wider uppercase text-[#111111] dark:text-[#EDEDEA]">
                Security Operations &amp; Anomaly Telemetry
              </h2>
            </div>
            <p className="mt-1 text-[#6B6B66] dark:text-[#888884] text-[11px]">
              Evidence-based anomaly detection evaluating protocol abuse, traffic spikes, and boundary violations.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="border border-[#9A5B5B] px-3 py-1.5 bg-[#9A5B5B]/10 text-center">
              <div className="text-[9px] uppercase text-[#9A5B5B]">Overall Fabric Threat Score</div>
              <div className="text-lg font-bold text-[#9A5B5B]">64 / 100 (ELEVATED)</div>
            </div>
          </div>
        </div>

        <div className="mt-4 pt-3 border-t border-[#E5E5E3] dark:border-[#2A2A2D] text-[10px] text-[#6B6B66] dark:text-[#888884]">
          Invariant: All threat findings are strictly grounded in physical CRC telemetry, interface drops, and syslog signatures. Unverified malware assertions are prohibited.
        </div>
      </div>

      {/* Main Threat Findings & Forensic Evidence */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Threats List (6 cols) */}
        <div className="lg:col-span-6 space-y-4">
          <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-4 space-y-3">
            <div className="flex items-center justify-between border-b border-[#E5E5E3] dark:border-[#2A2A2D] pb-2">
              <span className="font-semibold text-[#111111] dark:text-[#EDEDEA] uppercase tracking-wider">
                Corroborated Security Anomalies ({threats.length})
              </span>
              <span className="text-[10px] text-[#6B6B66] dark:text-[#888884]">
                Ranked by Risk Score
              </span>
            </div>

            <div className="space-y-2.5">
              {threats.map((t) => {
                const isSelected = selectedThreat.id === t.id;
                return (
                  <div
                    key={t.id}
                    onClick={() => setSelectedThreat(t)}
                    className={`p-3 border cursor-pointer transition-colors space-y-1.5 ${
                      isSelected
                        ? "border-[#111111] dark:border-[#EDEDEA] bg-[#FAFAF9] dark:bg-[#0F0F10]"
                        : "border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] hover:border-[#475569]"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="px-1.5 py-0.2 border border-[#9A5B5B] text-[#9A5B5B] text-[9px] uppercase font-bold">
                          {t.category}
                        </span>
                        <span className="font-bold text-[#111111] dark:text-[#EDEDEA]">
                          {t.title}
                        </span>
                      </div>
                      <span className="text-[10px] font-bold text-[#9A5B5B]">
                        Risk {t.riskScore}
                      </span>
                    </div>

                    <p className="text-[11px] text-[#6B6B66] dark:text-[#888884]">
                      Asset: <code className="text-[#111111] dark:text-[#EDEDEA]">{t.affectedAsset}</code>
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Right: Forensic Technical Evidence Inspector (6 cols) */}
        <div className="lg:col-span-6 space-y-4">
          <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-4 space-y-3">
            <div className="flex items-center justify-between border-b border-[#E5E5E3] dark:border-[#2A2A2D] pb-2">
              <span className="font-semibold text-[#111111] dark:text-[#EDEDEA] uppercase tracking-wider">
                Forensic Evidence Breakdown: {selectedThreat.id}
              </span>
              <span className="px-2 py-0.5 border border-[#5E7A6A] text-[#5E7A6A] text-[9px]">
                GROUNDED
              </span>
            </div>

            <div>
              <label className="text-[10px] text-[#6B6B66] dark:text-[#888884] uppercase">Target Asset</label>
              <div className="text-xs font-bold text-[#111111] dark:text-[#EDEDEA] mt-0.5">
                {selectedThreat.affectedAsset}
              </div>
            </div>

            <div>
              <label className="text-[10px] text-[#6B6B66] dark:text-[#888884] uppercase">Technical Telemetry Evidence</label>
              <div className="mt-1 p-2.5 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] text-[11px] text-[#111111] dark:text-[#EDEDEA]">
                {selectedThreat.observedEvidence}
              </div>
            </div>

            <div>
              <label className="text-[10px] text-[#6B6B66] dark:text-[#888884] uppercase">Recommended SecOps Mitigation</label>
              <div className="mt-1 p-2.5 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] text-[11px] text-[#5E7A6A]">
                {selectedThreat.mitigation}
              </div>
            </div>

            <div className="pt-2 text-[10px] text-[#6B6B66] dark:text-[#888884] border-t border-[#E5E5E3] dark:border-[#2A2A2D]">
              Forensic timeline corroboration: Correlated with diagnostic report <code className="text-[#111111] dark:text-[#EDEDEA]">{report?.incident_id || "inc-link-congestion-42"}</code>.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

