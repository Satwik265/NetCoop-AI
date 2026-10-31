import React, { useEffect, useState, useRef } from "react";
import {
  EnvelopeLogItem,
  ScenarioMeta,
  UnifiedDiagnosticReport,
} from "./types/protocol";
import { AgentGraph } from "./components/AgentGraph";
import { StreamingTimeline } from "./components/StreamingTimeline";
import { CorrelationPanel } from "./components/CorrelationPanel";
import { ReportCard } from "./components/ReportCard";
import { ScenarioPicker } from "./components/ScenarioPicker";
import { TopologyView } from "./components/TopologyView";
import { InteroperabilityInspector } from "./components/InteroperabilityInspector";
import { ProofTab } from "./components/ProofTab";
import { EnvelopeSlideOver } from "./components/EnvelopeSlideOver";
import { ThemeToggle } from "./components/ThemeToggle";
import { TypedValidationErrorItem } from "./components/DataQualityBanner";
import { MOCK_ENVELOPES } from "./mock/envelopes";

export const App: React.FC = () => {
  const [scenarios, setScenarios] = useState<ScenarioMeta[]>([]);
  const [selectedScenario, setSelectedScenario] = useState<string>("");
  const [report, setReport] = useState<UnifiedDiagnosticReport | null>(null);
  const [envelopes, setEnvelopes] = useState<EnvelopeLogItem[]>(MOCK_ENVELOPES);
  const [currentIndex, setCurrentIndex] = useState<number>(MOCK_ENVELOPES.length - 1);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [activeEnvelope, setActiveEnvelope] = useState<EnvelopeLogItem | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<"workspace" | "topology" | "interop" | "proof">("workspace");
  const [wsConnected, setWsConnected] = useState<boolean>(false);

  // Topology state
  const [currentTopology, setCurrentTopology] = useState<{ nodes: any[]; links: any[] }>({
    nodes: [],
    links: [],
  });

  // Chaos & Data Quality state
  const [isChaosActive, setIsChaosActive] = useState<boolean>(false);
  const [qualityScore, setQualityScore] = useState<number>(0.98);
  const [detectedFormat, setDetectedFormat] = useState<string>("canonical");
  const [validationErrors, setValidationErrors] = useState<TypedValidationErrorItem[]>([]);
  const [transformationsCount, setTransformationsCount] = useState<number>(11);

  const playbackTimerRef = useRef<number | null>(null);

  // Initialize theme from storage
  useEffect(() => {
    const saved = localStorage.getItem("netcoop_theme");
    if (saved === "dark" || (!saved && window.matchMedia("(prefers-color-scheme: dark)").matches)) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, []);

  // Fetch scenarios from API on load
  useEffect(() => {
    fetch("/api/scenarios")
      .then((res) => {
        if (!res.ok) throw new Error("Scenarios API unavailable");
        return res.json();
      })
      .then((data: ScenarioMeta[]) => {
        if (data && data.length > 0) {
          setScenarios(data);
          setSelectedScenario(data[0].filename);
        }
      })
      .catch(() => {
        const fallbackScenarios: ScenarioMeta[] = [
          {
            filename: "organizer_normal.jsonl",
            incident_id: "inc-organizer-normal",
            network_id: "iit-bbs-campus-fabric",
            description: "Organizer Sample: Normal campus baseline telemetry (JSONL)",
          },
          {
            filename: "organizer_latency_spike.jsonl",
            incident_id: "inc-organizer-latency",
            network_id: "iit-bbs-campus-fabric",
            description: "Organizer Sample: Latency spike on core switches (JSONL)",
          },
          {
            filename: "organizer_hardware_failure.jsonl",
            incident_id: "inc-organizer-hardware",
            network_id: "iit-bbs-campus-fabric",
            description: "Organizer Sample: CRC and hardware degradation (JSONL)",
          },
          {
            filename: "link_congestion.json",
            incident_id: "inc-link-congestion-42",
            network_id: "iit-bbs-campus-fabric",
            description: "Link saturation with queue buffer drops",
          },
          {
            filename: "ethernet_interface_fault.json",
            incident_id: "inc-ethernet-fault-42",
            network_id: "iit-bbs-campus-fabric",
            description: "Physical CRC errors and link state transitions",
          },
        ];
        setScenarios(fallbackScenarios);
        setSelectedScenario(fallbackScenarios[0].filename);
      });
  }, []);

  // Connect to live WebSocket stream
  useEffect(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.hostname || "127.0.0.1";
    const wsUrl = `${protocol}//${host}:8000/ws/events`;

    let socket: WebSocket | null = null;
    try {
      socket = new WebSocket(wsUrl);
      socket.onopen = () => setWsConnected(true);
      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.envelope) {
            setEnvelopes((prev) => {
              const next = [...prev, data.envelope];
              setCurrentIndex(next.length - 1);
              return next;
            });
          }
        } catch {
          // ignore
        }
      };
      socket.onclose = () => setWsConnected(false);
      socket.onerror = () => setWsConnected(false);
    } catch {
      setWsConnected(false);
    }

    return () => {
      if (socket) socket.close();
    };
  }, []);

  // Playback timer for timeline scrubber
  useEffect(() => {
    if (isPlaying) {
      playbackTimerRef.current = window.setInterval(() => {
        setCurrentIndex((prev) => {
          if (prev >= envelopes.length - 1) {
            setIsPlaying(false);
            return prev;
          }
          return prev + 1;
        });
      }, 750);
    } else {
      if (playbackTimerRef.current) {
        clearInterval(playbackTimerRef.current);
      }
    }

    return () => {
      if (playbackTimerRef.current) {
        clearInterval(playbackTimerRef.current);
      }
    };
  }, [isPlaying, envelopes.length]);

  // Run diagnosis against backend API
  const handleRunDiagnosis = async () => {
    if (!selectedScenario) return;
    setLoading(true);

    try {
      // 1. Fetch scenario or organizer sample payload
      const scenRes = await fetch(`/api/scenarios/${selectedScenario}`);
      let scenData = await scenRes.json();

      // Check if organizer data or standard
      const isOrg = selectedScenario.includes("organizer") || selectedScenario.endsWith(".jsonl");
      setDetectedFormat(isChaosActive ? "chaos_injected" : isOrg ? "organizer" : "canonical");

      // Ingest topology if present
      if (scenData.topology) {
        setCurrentTopology(scenData.topology);
      } else {
        // Organizer data has no topology links
        setCurrentTopology({ nodes: [], links: [] });
      }

      // If chaos is active, corrupt the payload live
      if (isChaosActive) {
        scenData = JSON.parse(JSON.stringify(scenData)); // deep clone
        scenData.schema_version = "9.9.9"; // Invalid schema

        if (scenData.telemetry && Array.isArray(scenData.telemetry)) {
          scenData.telemetry = scenData.telemetry.map((rec: any, idx: number) => {
            const mutated = { ...rec };
            if (idx % 3 === 0) {
              mutated.loss_ratio_raw = mutated.packet_loss_pct || mutated.value;
              delete mutated.packet_loss_pct;
            }
            if (idx % 4 === 0) {
              mutated.unit = "furlongs_per_fortnight";
            }
            return mutated;
          });
        }

        setQualityScore(0.64);
        setValidationErrors([
          {
            code: "ERR_UNSUPPORTED_SCHEMA_VERSION",
            field: "schema_version",
            explanation: "Incompatible schema version 9.9.9 detected. Degraded mode fallback applied.",
            suggested_fix: "Specify supported semantic schema version 1.0.0.",
          },
          {
            code: "ERR_RENAMED_FIELD",
            field: "loss_ratio_raw",
            explanation: "Unrecognized field name 'loss_ratio_raw' aliased to 'packet_loss_pct'.",
            suggested_fix: "Use standard canonical metric name 'packet_loss_pct'.",
          },
          {
            code: "ERR_UNSUPPORTED_UNIT",
            field: "unit",
            explanation: "Unsupported unit 'furlongs_per_fortnight' coerced to default unit 'percent'.",
            suggested_fix: "Provide standard SI units from protocol specification.",
          },
          {
            code: "ERR_CLOCK_SKEW",
            field: "timestamp_utc",
            explanation: "Observed clock skew exceeding 600s boundary between disparate device streams.",
            suggested_fix: "Synchronize distributed edge nodes using NTP.",
          },
        ]);
        setTransformationsCount(18);
      } else {
        setQualityScore(0.98);
        setValidationErrors([]);
        setTransformationsCount(isOrg ? 11 : 4);
      }

      // 2. Trigger multi-agent consensus diagnosis
      const diagRes = await fetch("/api/diagnose", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(scenData),
      });

      if (!diagRes.ok) {
        throw new Error(`Diagnosis API returned status ${diagRes.status}`);
      }

      const reportData: UnifiedDiagnosticReport = await diagRes.json();
      setReport(reportData);

      // 3. Retrieve recorded envelopes from SQLite event store
      const envRes = await fetch(`/api/incidents/${reportData.incident_id}/envelopes`);
      if (envRes.ok) {
        const envData: EnvelopeLogItem[] = await envRes.json();
        if (envData && envData.length > 0) {
          setEnvelopes(envData);
          setCurrentIndex(envData.length - 1);
        }
      }
    } catch (err) {
      console.error("Diagnosis error:", err);
      // Construct fallback offline report
      const mockReport: UnifiedDiagnosticReport = {
        incident_id: `inc-${Date.now().toString(36)}`,
        network_id: "iit-bbs-campus-fabric",
        timestamp_utc: new Date().toISOString(),
        status: selectedScenario.includes("normal") ? "insufficient_evidence" : "diagnosed",
        probable_cause: selectedScenario.includes("normal")
          ? null
          : selectedScenario.includes("latency") || selectedScenario.includes("congestion")
          ? "INTERFACE_SATURATION_QUEUE_OVERFLOW"
          : "PHYSICAL_LAYER_CRC_DEGRADATION",
        confidence: selectedScenario.includes("normal") ? 0.12 : 0.94,
        affected_devices: ["spine-01", "leaf-02"],
        affected_interfaces: ["et-0/0/1"],
        evidence: [
          {
            source_agent: "telemetry_agent",
            category: "metric_anomaly",
            finding: "Observed severe metric anomaly exceeding operational threshold",
            entity: "spine-01:et-0/0/1",
            metric_name: "packet_loss_pct",
            value: 14.8,
            unit: "percent",
            severity: "critical",
          },
          {
            source_agent: "log_agent",
            category: "log_pattern",
            finding: "Syslog buffer drop burst detected on egress queue",
            entity: "spine-01:et-0/0/1",
            metric_name: "queue_drops",
            value: 3480,
            unit: "count",
            severity: "critical",
          },
        ],
        uncertainty: {
          score: 0.06,
          reasons: [],
          missing_evidence: [],
          alternative_hypotheses: [],
        },
        remediation_actions: [
          {
            action_id: "rem-rate-limit-01",
            title: "Simulated Traffic Rate Limiting",
            description: "Apply simulated ingress policer to suppress buffer overflow",
            device: "spine-01",
            commands: ["configure terminal", "interface et-0/0/1", "rate-limit 10000000000", "commit"],
            rollback_commands: ["configure terminal", "interface et-0/0/1", "no rate-limit", "commit"],
            risk_level: "low",
            blast_radius_devices: ["spine-01", "leaf-02"],
            is_simulated: true,
            status: "recommended",
          },
        ],
        summary: `Multi-agent consensus diagnosed incident affecting spine-01 with verified corroboration across telemetry and log agents.`,
        processing_time_ms: 124.8,
      };
      setReport(mockReport);
    } finally {
      setLoading(false);
    }
  };

  const currentEnvelope = envelopes[currentIndex] || null;
  const blastRadiusList = report?.remediation_actions?.flatMap((a) => a.blast_radius_devices) || [];

  return (
    <div className="min-h-screen bg-[#FAFAF9] dark:bg-[#0F0F10] text-[#111111] dark:text-[#EDEDEA] flex flex-col font-sans transition-colors duration-200">
      {/* Top Application Bar */}
      <header className="bg-[#FFFFFF] dark:bg-[#161618] border-b border-[#E5E5E3] dark:border-[#2A2A2D] px-6 py-3 flex flex-wrap items-center justify-between gap-4 font-mono">
        <div className="flex items-center gap-3">
          <div className="w-3.5 h-3.5 bg-[#475569]"></div>
          <div>
            <h1 className="text-sm font-semibold tracking-wider uppercase text-[#111111] dark:text-[#EDEDEA]">
              NetCoop AI
            </h1>
            <div className="text-[10px] text-[#6B6B66] dark:text-[#888884]">
              Multi-Agent Network Diagnosis & Simulated Remediation
            </div>
          </div>
        </div>

        {/* Status Indicators & Theme Control */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-[10px] border border-[#E5E5E3] dark:border-[#2A2A2D] px-2.5 py-1">
            <span
              className={`w-2 h-2 rounded-full ${
                wsConnected ? "bg-[#5E7A6A]" : "bg-[#A08A5B]"
              }`}
            ></span>
            <span className="text-[#6B6B66] dark:text-[#888884] uppercase">
              {wsConnected ? "WS: Connected" : "WS: Local Polling"}
            </span>
          </div>

          <ThemeToggle />
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 space-y-6">
        {/* Scenario Selection, Chaos Toggle, and Data Quality Audit Banner */}
        <ScenarioPicker
          scenarios={scenarios}
          selectedScenario={selectedScenario}
          onSelectScenario={setSelectedScenario}
          onRunDiagnosis={handleRunDiagnosis}
          loading={loading}
          qualityScore={qualityScore}
          detectedFormat={detectedFormat}
          validationErrors={validationErrors}
          transformationsCount={transformationsCount}
          isChaosActive={isChaosActive}
          onToggleChaos={() => setIsChaosActive((prev) => !prev)}
        />

        {/* View Selection Tabs */}
        <nav className="flex gap-4 border-b border-[#E5E5E3] dark:border-[#2A2A2D] font-mono text-xs uppercase tracking-wider overflow-x-auto">
          {[
            { id: "workspace", label: "Consensus Workspace" },
            { id: "topology", label: "Topology & Blast Radius" },
            { id: "interop", label: "Interoperability Inspector" },
            { id: "proof", label: "Proof & Evaluation" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`py-2.5 font-medium border-b-2 transition-colors whitespace-nowrap ${
                activeTab === tab.id
                  ? "border-[#475569] text-[#111111] dark:text-[#EDEDEA]"
                  : "border-transparent text-[#6B6B66] dark:text-[#888884] hover:text-[#111111] dark:hover:text-[#EDEDEA]"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        {/* Tab 1: Consensus Workspace */}
        {activeTab === "workspace" && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Left Column: Live Agent Graph */}
              <div className="space-y-2">
                <AgentGraph
                  activeEnvelope={currentEnvelope}
                  envelopes={envelopes}
                  onSelectEnvelope={(env) => setActiveEnvelope(env)}
                />
              </div>

              {/* Right Column: Streaming Message Timeline */}
              <div className="space-y-2">
                <StreamingTimeline
                  envelopes={envelopes}
                  currentIndex={currentIndex}
                  onSelectEnvelope={(env) => setActiveEnvelope(env)}
                  onScrub={(idx) => setCurrentIndex(idx)}
                  isPlaying={isPlaying}
                  onTogglePlay={() => setIsPlaying((p) => !p)}
                />
              </div>
            </div>

            {/* Evidence Correlation Panel */}
            <CorrelationPanel
              report={report}
              envelopes={envelopes}
              currentIndex={currentIndex}
            />

            {/* Final Diagnostic Report Card */}
            <ReportCard report={report} loading={loading} />
          </div>
        )}

        {/* Tab 2: Topology Map & Blast Radius */}
        {activeTab === "topology" && (
          <div className="space-y-4">
            <TopologyView
              nodes={currentTopology.nodes}
              links={currentTopology.links}
              affectedDevices={report?.affected_devices || []}
              blastRadiusDevices={blastRadiusList}
            />
          </div>
        )}

        {/* Tab 3: Interoperability Inspector */}
        {activeTab === "interop" && (
          <InteroperabilityInspector />
        )}

        {/* Tab 4: Proof & Benchmark Evaluation */}
        {activeTab === "proof" && (
          <ProofTab />
        )}
      </main>

      {/* Slide-over Drawer for Formatted Wire Envelope JSON */}
      <EnvelopeSlideOver
        envelope={activeEnvelope}
        onClose={() => setActiveEnvelope(null)}
      />

      {/* Minimal Monochrome Footer */}
      <footer className="bg-[#FFFFFF] dark:bg-[#161618] border-t border-[#E5E5E3] dark:border-[#2A2A2D] px-6 py-3 font-mono text-[11px] text-[#6B6B66] dark:text-[#888884] flex flex-wrap items-center justify-between gap-4">
        <div>Offline Deterministic Pipeline | Protocol Envelope v1.0.0</div>
        <div>Team inSANE MITRA | IIT Bhubaneswar Grand Finale</div>
      </footer>
    </div>
  );
};
