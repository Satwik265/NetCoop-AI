import React, { useEffect, useState } from "react";
import {
  EnvelopeLogItem,
  ScenarioMeta,
  UnifiedDiagnosticReport,
} from "./types/protocol";
import { IncidentHeader } from "./components/IncidentHeader";
import { EvidenceCard } from "./components/EvidenceCard";
import { TopologyView } from "./components/TopologyView";
import { EnvelopeTrace } from "./components/EnvelopeTrace";
import { RemediationModal } from "./components/RemediationModal";
import { ProtocolViewer } from "./components/ProtocolViewer";

export const App: React.FC = () => {
  const [scenarios, setScenarios] = useState<ScenarioMeta[]>([]);
  const [selectedScenario, setSelectedScenario] = useState<string>("");
  const [report, setReport] = useState<UnifiedDiagnosticReport | null>(null);
  const [envelopes, setEnvelopes] = useState<EnvelopeLogItem[]>([]);
  const [currentTopology, setCurrentTopology] = useState<{ nodes: any[]; links: any[] }>({
    nodes: [],
    links: [],
  });
  const [activeTab, setActiveTab] = useState<"overview" | "trace" | "topology" | "protocol">("overview");
  const [loading, setLoading] = useState<boolean>(false);

  // Load scenarios on mount
  useEffect(() => {
    fetch("/api/scenarios")
      .then((res) => res.json())
      .then((data: ScenarioMeta[]) => {
        setScenarios(data);
        if (data.length > 0) {
          setSelectedScenario(data[0].filename);
        }
      })
      .catch(() => {});
  }, []);

  const handleRunDiagnosis = async () => {
    if (!selectedScenario) return;
    setLoading(true);

    try {
      // 1. Fetch scenario JSON
      const scenRes = await fetch(`/api/scenarios/${selectedScenario}`);
      const scenData = await scenRes.json();
      setCurrentTopology(scenData.topology || { nodes: [], links: [] });

      // 2. Trigger multi-agent diagnosis
      const diagRes = await fetch("/api/diagnose", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(scenData),
      });
      const reportData: UnifiedDiagnosticReport = await diagRes.json();
      setReport(reportData);

      // 3. Fetch envelope trace
      const envRes = await fetch(`/api/incidents/${reportData.incident_id}/envelopes`);
      const envData = await envRes.json();
      setEnvelopes(envData);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const reloadEnvelopes = () => {
    if (!report) return;
    fetch(`/api/incidents/${report.incident_id}/envelopes`)
      .then((res) => res.json())
      .then((data) => setEnvelopes(data))
      .catch(() => {});
  };

  return (
    <div className="min-h-screen bg-[#0F0F10] text-[#EDEDEA] flex flex-col font-sans">
      {/* Top Navigation Bar */}
      <header className="bg-[#161618] border-b border-[#2A2A2D] px-6 py-4 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-4 h-4 bg-[#475569]"></div>
          <div>
            <h1 className="text-base font-semibold tracking-wider font-mono uppercase text-[#EDEDEA]">
              NetCoop AI
            </h1>
            <div className="text-[10px] text-[#888884] font-mono">
              IIT Bhubaneswar Grand Finale | Multi-Agent Network Diagnosis
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-[#888884]">Scenario:</span>
            <select
              value={selectedScenario}
              onChange={(e) => setSelectedScenario(e.target.value)}
              className="bg-[#0F0F10] border border-[#2A2A2D] text-[#EDEDEA] px-3 py-1.5 text-xs font-mono outline-none focus:border-[#475569]"
            >
              {scenarios.map((s) => (
                <option key={s.filename} value={s.filename}>
                  {s.filename.replace(".json", "")}
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={handleRunDiagnosis}
            disabled={loading || !selectedScenario}
            className="px-4 py-1.5 bg-[#EDEDEA] text-[#111111] hover:bg-white text-xs font-mono uppercase tracking-wider font-semibold transition-colors disabled:opacity-50"
          >
            {loading ? "Diagnosing..." : "Run Diagnosis"}
          </button>
        </div>
      </header>

      {/* Tab Navigation */}
      <nav className="bg-[#161618] border-b border-[#2A2A2D] px-6 flex gap-6 text-xs font-mono uppercase tracking-wider">
        {[
          { key: "overview", label: "Overview & Evidence" },
          { key: "trace", label: `Envelope Trace (${envelopes.length})` },
          { key: "topology", label: "Topology Graph" },
          { key: "protocol", label: "Protocol Specification" },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key as any)}
            className={`py-3 font-medium transition-colors border-b-2 ${
              activeTab === tab.key
                ? "border-[#EDEDEA] text-[#EDEDEA]"
                : "border-transparent text-[#888884] hover:text-[#EDEDEA]"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      {/* Main Content Area */}
      <main className="flex-1 p-6 max-w-7xl w-full mx-auto space-y-6">
        {activeTab === "overview" && (
          <>
            <IncidentHeader report={report} loading={loading} />

            {report && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <EvidenceCard
                  evidence={report.evidence}
                  missingEvidence={report.uncertainty.missing_evidence}
                />
                <div className="space-y-6">
                  <TopologyView
                    nodes={currentTopology.nodes}
                    links={currentTopology.links}
                    affectedDevices={report.affected_devices}
                  />
                  {report.remediation_actions.length > 0 && (
                    <RemediationModal
                      incidentId={report.incident_id}
                      actions={report.remediation_actions}
                      onActionSimulated={reloadEnvelopes}
                    />
                  )}
                </div>
              </div>
            )}
          </>
        )}

        {activeTab === "trace" && (
          <EnvelopeTrace envelopes={envelopes} loading={loading} />
        )}

        {activeTab === "topology" && (
          <TopologyView
            nodes={currentTopology.nodes}
            links={currentTopology.links}
            affectedDevices={report?.affected_devices || []}
          />
        )}

        {activeTab === "protocol" && <ProtocolViewer />}
      </main>

      {/* Minimal Monochrome Footer */}
      <footer className="bg-[#161618] border-t border-[#2A2A2D] px-6 py-3 text-xs font-mono text-[#888884] flex flex-wrap items-center justify-between gap-4">
        <div>Offline-First Deterministic Core | Envelope Protocol v1.0.0</div>
        <div>Team inSANE MITRA | IIT Bhubaneswar Agentic AI Grand Finale</div>
      </footer>
    </div>
  );
};

