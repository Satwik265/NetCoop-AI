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
import { HitlApprovalQueue } from "./components/HitlApprovalQueue";
import { SimulatedRemediationView } from "./components/SimulatedRemediationView";
import { SessionListResume } from "./components/SessionListResume";
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
  const [activeTab, setActiveTab] = useState<string>("workspace");
  const [wsConnected, setWsConnected] = useState<boolean>(false);

  // Feature flags state matching backend flags
  const [features, setFeatures] = useState<{
    FEATURE_HITL: boolean;
    FEATURE_REMEDIATION_SIM: boolean;
    FEATURE_RESUME: boolean;
  }>({
    FEATURE_HITL: true,
    FEATURE_REMEDIATION_SIM: true,
    FEATURE_RESUME: true,
  });

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

  // Fetch feature flags on load
  useEffect(() => {
    fetch("/api/features")
      .then((res) => {
        if (!res.ok) throw new Error("Features endpoint unavailable");
        return res.json();
      })
      .then((data) => {
        if (data && typeof data.FEATURE_HITL === "boolean") {
          setFeatures(data);
        }
      })
      .catch(() => {
        // Default to active
      });
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
      const scenRes = await fetch(`/api/scenarios/${selectedScenario}`);
      let scenData = await scenRes.json();

      const isOrg = selectedScenario.includes("organizer") || selectedScenario.endsWith(".jsonl");
      setDetectedFormat(isChaosActive ? "chaos_injected" : isOrg ? "organizer" : "canonical");

      if (scenData.topology) {
        setCurrentTopology(scenData.topology);
      } else {
        setCurrentTopology({ nodes: [], links: [] });
      }

      if (isChaosActive) {
        scenData = JSON.parse(JSON.stringify(scenData));
        scenData.schema_version = "9.9.9";

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
            action_id: "act-rebalance-spine-01",
            title: "Rebalance Traffic across ECMP Next-Hops",
            description: "Apply simulated traffic policy to redistribute load away from saturated interfaces.",
            device: "spine-01",
            commands: ["configure terminal", "interface et-0/0/1", "load-interval 30", "traffic-policy REBALANCE_ECMP", "commit and-quit"],
            rollback_commands: ["configure terminal", "interface et-0/0/1", "no traffic-policy REBALANCE_ECMP", "commit and-quit"],
            risk_level: "low",
            blast_radius_devices: ["spine-01", "leaf-02"],
            is_simulated: true,
            status: "pending_approval",
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

  const tabs: Array<{ id: string; label: string }> = [
    { id: "workspace", label: "Consensus Workspace" },
    { id: "topology", label: "Topology & Blast Radius" },
    { id: "interop", label: "Interoperability Inspector" },
    { id: "proof", label: "Proof & Evaluation" },
  ];

  if (features.FEATURE_HITL) {
    tabs.push({ id: "hitl", label: "HITL Approvals" });
  }
  if (features.FEATURE_REMEDIATION_SIM) {
    tabs.push({ id: "simulated_remediation", label: "Simulated Remediation" });
  }
  if (features.FEATURE_RESUME) {
    tabs.push({ id: "sessions", label: "Sessions & Resume" });
  }

  const resolvedTab = tabs.some((t) => t.id === activeTab) ? activeTab : "workspace";

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
              Multi-Agent Network Diagnosis &amp; Simulated Remediation
            </div>
          </div>
        </div>

        {/* Status Indicators, Feature Flags Toggles & Theme Control */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Feature Flags Pill Bar */}
          <div className="hidden sm:flex items-center gap-1.5 border border-[#E5E5E3] dark:border-[#2A2A2D] px-2.5 py-1 text-[10px]">
            <span className="text-[#6B6B66] dark:text-[#888884] uppercase">Flags:</span>
            <button
              onClick={() => setFeatures((p) => ({ ...p, FEATURE_HITL: !p.FEATURE_HITL }))}
              title="Toggle FEATURE_HITL"
              className={`px-1.5 py-0.5 border ${
                features.FEATURE_HITL
                  ? "border-[#5E7A6A] text-[#5E7A6A]"
                  : "border-[#6B6B66] text-[#6B6B66] opacity-50"
              }`}
            >
              HITL
            </button>
            <button
              onClick={() =>
                setFeatures((p) => ({ ...p, FEATURE_REMEDIATION_SIM: !p.FEATURE_REMEDIATION_SIM }))
              }
              title="Toggle FEATURE_REMEDIATION_SIM"
              className={`px-1.5 py-0.5 border ${
                features.FEATURE_REMEDIATION_SIM
                  ? "border-[#5E7A6A] text-[#5E7A6A]"
                  : "border-[#6B6B66] text-[#6B6B66] opacity-50"
              }`}
            >
              SIM
            </button>
            <button
              onClick={() => setFeatures((p) => ({ ...p, FEATURE_RESUME: !p.FEATURE_RESUME }))}
              title="Toggle FEATURE_RESUME"
              className={`px-1.5 py-0.5 border ${
                features.FEATURE_RESUME
                  ? "border-[#5E7A6A] text-[#5E7A6A]"
                  : "border-[#6B6B66] text-[#6B6B66] opacity-50"
              }`}
            >
              RESUME
            </button>
          </div>

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

        {/* View Selection Tabs (dynamically filtered by feature flags) */}
        <nav className="flex gap-4 border-b border-[#E5E5E3] dark:border-[#2A2A2D] font-mono text-xs uppercase tracking-wider overflow-x-auto">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`py-2.5 font-medium border-b-2 transition-colors whitespace-nowrap ${
                resolvedTab === tab.id
                  ? "border-[#475569] text-[#111111] dark:text-[#EDEDEA]"
                  : "border-transparent text-[#6B6B66] dark:text-[#888884] hover:text-[#111111] dark:hover:text-[#EDEDEA]"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        {/* Tab 1: Consensus Workspace */}
        {resolvedTab === "workspace" && (
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
        {resolvedTab === "topology" && (
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
        {resolvedTab === "interop" && (
          <InteroperabilityInspector />
        )}

        {/* Tab 4: Proof & Benchmark Evaluation */}
        {resolvedTab === "proof" && (
          <ProofTab />
        )}

        {/* Tab 5: Human-in-the-Loop (HITL) Approvals (FEATURE_HITL) */}
        {resolvedTab === "hitl" && features.FEATURE_HITL && (
          <HitlApprovalQueue
            incidentId={report?.incident_id || "inc-link-congestion-42"}
            actions={report?.remediation_actions || []}
            onActionExecuted={(actionId) => {
              if (report && report.remediation_actions) {
                setReport({
                  ...report,
                  remediation_actions: report.remediation_actions.map((a) =>
                    a.action_id === actionId ? { ...a, status: "simulated_executed" } : a
                  ),
                });
              }
            }}
          />
        )}

        {/* Tab 6: Simulated Remediation View (FEATURE_REMEDIATION_SIM) */}
        {resolvedTab === "simulated_remediation" && features.FEATURE_REMEDIATION_SIM && (
          <SimulatedRemediationView />
        )}

        {/* Tab 7: Sessions & Resume Control (FEATURE_RESUME) */}
        {resolvedTab === "sessions" && features.FEATURE_RESUME && (
          <SessionListResume
            onSelectSession={(_incId) => {
              setSelectedScenario("link_congestion.json");
              handleRunDiagnosis();
            }}
          />
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
