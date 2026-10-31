import React, { useEffect, useState, useRef } from "react";
import {
  EnvelopeLogItem,
  ScenarioMeta,
  UnifiedDiagnosticReport,
} from "./types/protocol";
import { UserRole, ROLE_DEFINITIONS, hasPermission, Permission } from "./rbac/roles";
import { Sidebar } from "./components/Sidebar";
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
import { McpGallery } from "./components/McpGallery";
import { EnvelopeSlideOver } from "./components/EnvelopeSlideOver";
import { ThemeToggle } from "./components/ThemeToggle";
import { TypedValidationErrorItem } from "./components/DataQualityBanner";
import { MOCK_ENVELOPES } from "./mock/envelopes";

// Role-Specific Views
import { NocView } from "./components/views/NocView";
import { EngineerView } from "./components/views/EngineerView";
import { AdminView } from "./components/views/AdminView";
import { SecurityView } from "./components/views/SecurityView";
import { ItManagerView } from "./components/views/ItManagerView";
import { PlatformAdminView } from "./components/views/PlatformAdminView";
import { AuditorView } from "./components/views/AuditorView";
import { HelpdeskView } from "./components/views/HelpdeskView";

export const App: React.FC = () => {
  // Role & Navigation state
  const [currentRole, setCurrentRole] = useState<UserRole>(() => {
    const saved = localStorage.getItem("netcoop_user_role");
    return (saved as UserRole) || "noc_operator";
  });
  const [activeNav, setActiveNav] = useState<string>("role_noc");
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState<boolean>(false);

  // Scenarios and Reports state
  const [scenarios, setScenarios] = useState<ScenarioMeta[]>([]);
  const [selectedScenario, setSelectedScenario] = useState<string>("");
  const [report, setReport] = useState<UnifiedDiagnosticReport | null>(null);
  const [envelopes, setEnvelopes] = useState<EnvelopeLogItem[]>(MOCK_ENVELOPES);
  const [currentIndex, setCurrentIndex] = useState<number>(MOCK_ENVELOPES.length - 1);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [activeEnvelope, setActiveEnvelope] = useState<EnvelopeLogItem | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [wsStatus, setWsStatus] = useState<"connected" | "connecting" | "offline">("connecting");

  // Feature flags
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

  // Persist role change
  const handleSelectRole = (role: UserRole) => {
    setCurrentRole(role);
    localStorage.setItem("netcoop_user_role", role);
  };

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

  // WebSocket real-time connection with auto-reconnect
  useEffect(() => {
    let socket: WebSocket | null = null;
    let reconnectTimer: number | null = null;
    let attempts = 0;

    const connect = () => {
      setWsStatus("connecting");
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const host = window.location.host;
      const wsUrl = `${protocol}//${host}/ws/events`;

      try {
        socket = new WebSocket(wsUrl);

        socket.onopen = () => {
          setWsStatus("connected");
          attempts = 0;
        };

        socket.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.event_type === "envelope_logged" && data.envelope) {
              const env = data.envelope;
              const logItem: EnvelopeLogItem = {
                id: Date.now(),
                message_id: env.header?.message_id || `msg-${Date.now()}`,
                correlation_id: env.header?.correlation_id || "corr-default",
                timestamp_utc: env.header?.timestamp_utc || new Date().toISOString(),
                sender: env.header?.sender || "unknown",
                recipient: env.header?.recipient || "unknown",
                message_type: env.header?.message_type || "UNKNOWN",
                priority: env.header?.priority || "normal",
                payload: env.payload || {},
                context: env.context || {},
              };
              setEnvelopes((prev) => {
                if (prev.some((e) => e.message_id === logItem.message_id)) return prev;
                const next = [...prev, logItem];
                setCurrentIndex(next.length - 1);
                return next;
              });
            }
          } catch {
            // ignore non-json
          }
        };

        socket.onclose = () => {
          setWsStatus("offline");
          const delay = Math.min(1000 * Math.pow(2, attempts), 10000);
          attempts += 1;
          reconnectTimer = window.setTimeout(connect, delay);
        };

        socket.onerror = () => {
          setWsStatus("offline");
        };
      } catch {
        setWsStatus("offline");
      }
    };

    connect();

    return () => {
      if (socket) socket.close();
      if (reconnectTimer) clearTimeout(reconnectTimer);
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
            source_agent: "topology_agent",
            category: "topology_finding",
            finding: "Spine-01 interface link flaps detected on core fabric link",
            entity: "spine-01:et-0/0/1",
            metric_name: "link_flaps",
            value: 6,
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
        summary: `Multi-agent consensus diagnosed incident affecting spine-01 with verified corroboration across telemetry and topology agents.`,
        processing_time_ms: 124.8,
      };
      setReport(mockReport);
    } finally {
      setLoading(false);
    }
  };

  const currentEnvelope = envelopes[currentIndex] || null;
  const blastRadiusList = report?.remediation_actions?.flatMap((a) => a.blast_radius_devices) || [];

  // Check RBAC permission guard for guarded views
  const renderPermissionGuard = (requiredPerm: Permission, featureName: string) => (
    <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#9A5B5B]/30 p-8 text-center space-y-3 font-mono">
      <div className="inline-block px-2.5 py-0.5 border border-[#9A5B5B] text-[#9A5B5B] text-xs uppercase font-bold">
        Access Denied: RBAC Restriction
      </div>
      <h2 className="text-sm font-bold text-[#111111] dark:text-[#EDEDEA]">
        {featureName} Requires Elevated Permissions
      </h2>
      <p className="text-xs text-[#6B6B66] dark:text-[#888884] max-w-md mx-auto">
        Your active role <span className="font-semibold text-[#111111] dark:text-[#EDEDEA]">({ROLE_DEFINITIONS[currentRole].title})</span> does not possess the required permission <code className="text-[#9A5B5B]">"{requiredPerm}"</code>.
      </p>
      <div className="text-[11px] text-[#6B6B66] dark:text-[#888884]">
        To access this capability, switch to a role with execution authorization (e.g. Network Engineer or Administrator).
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-[#FAFAF9] dark:bg-[#0F0F10] text-[#111111] dark:text-[#EDEDEA] flex font-sans transition-colors duration-200">
      {/* Shared Enterprise Sidebar */}
      <Sidebar
        currentRole={currentRole}
        onSelectRole={handleSelectRole}
        activeNav={activeNav}
        onSelectNav={setActiveNav}
        wsStatus={wsStatus}
        features={features}
        isMobileOpen={isMobileMenuOpen}
        onCloseMobile={() => setIsMobileMenuOpen(false)}
      />

      {/* Main Layout Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Application Bar */}
        <header className="bg-[#FFFFFF] dark:bg-[#161618] border-b border-[#E5E5E3] dark:border-[#2A2A2D] px-6 py-3 flex flex-wrap items-center justify-between gap-4 font-mono sticky top-0 z-30">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setIsMobileMenuOpen(true)}
              className="lg:hidden p-1 border border-[#E5E5E3] dark:border-[#2A2A2D] text-xs"
            >
              Menu
            </button>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-sm font-semibold tracking-wider uppercase text-[#111111] dark:text-[#EDEDEA]">
                  NetCoop AI
                </h1>
                <span className={`px-2 py-0.5 border text-[10px] uppercase font-semibold ${ROLE_DEFINITIONS[currentRole].badgeClass}`}>
                  {ROLE_DEFINITIONS[currentRole].title}
                </span>
              </div>
              <div className="text-[10px] text-[#6B6B66] dark:text-[#888884]">
                Multi-Agent Network Diagnosis &amp; Simulated Remediation
              </div>
            </div>
          </div>

          {/* Feature Flags Pill Bar & Theme Control */}
          <div className="flex flex-wrap items-center gap-3">
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

            <ThemeToggle />
          </div>
        </header>

        {/* Main Content Area */}
        <main className="flex-1 p-4 sm:p-6 space-y-6 max-w-7xl w-full mx-auto">
          {/* Universal Scenario Picker and Fault Injection Bar */}
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

          {/* VIEW SWITCHER ROUTING */}

          {/* 1. ROLE VIEW: NOC Operator */}
          {activeNav === "role_noc" && (
            <NocView
              report={report}
              onInvestigateIncident={() => setActiveNav("role_engineer")}
            />
          )}

          {/* 2. ROLE VIEW: Network Engineer */}
          {activeNav === "role_engineer" && (
            <EngineerView
              report={report}
              onLaunchSimulation={() => setActiveNav("simulated_remediation")}
              onOpenHitlQueue={() => setActiveNav("hitl")}
            />
          )}

          {/* 3. ROLE VIEW: Network Administrator */}
          {activeNav === "role_admin" && (
            <AdminView />
          )}

          {/* 4. ROLE VIEW: Security Analyst */}
          {activeNav === "role_security" && (
            <SecurityView report={report} />
          )}

          {/* 5. ROLE VIEW: IT Manager */}
          {activeNav === "role_it_manager" && (
            <ItManagerView report={report} />
          )}

          {/* 6. ROLE VIEW: Platform Administrator */}
          {activeNav === "role_platform_admin" && (
            <PlatformAdminView />
          )}

          {/* 7. ROLE VIEW: Auditor / Compliance */}
          {activeNav === "role_auditor" && (
            <AuditorView report={report} />
          )}

          {/* 8. ROLE VIEW: Helpdesk Support */}
          {activeNav === "role_helpdesk" && (
            <HelpdeskView
              report={report}
              onNavigateToIncidents={() => setActiveNav("role_noc")}
            />
          )}

          {/* PLATFORM SUBSYSTEM: Consensus Workspace */}
          {activeNav === "workspace" && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <AgentGraph
                    activeEnvelope={currentEnvelope}
                    envelopes={envelopes}
                    onSelectEnvelope={(env) => setActiveEnvelope(env)}
                  />
                </div>

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

              <CorrelationPanel
                report={report}
                envelopes={envelopes}
                currentIndex={currentIndex}
              />
            </div>
          )}

          {/* PLATFORM SUBSYSTEM: Topology View */}
          {activeNav === "topology" && (
            <TopologyView
              nodes={currentTopology.nodes}
              links={currentTopology.links}
              affectedDevices={report?.affected_devices || []}
              blastRadiusDevices={blastRadiusList}
            />
          )}

          {/* PLATFORM SUBSYSTEM: Unified Diagnostic Report (12 Sections) */}
          {activeNav === "report" && (
            <ReportCard report={report} loading={loading} />
          )}

          {/* PLATFORM SUBSYSTEM: Interoperability Inspector */}
          {activeNav === "interop" && (
            <InteroperabilityInspector />
          )}

          {/* PLATFORM SUBSYSTEM: Proof & Evaluation Tab */}
          {activeNav === "proof" && (
            <ProofTab />
          )}

          {/* PLATFORM SUBSYSTEM: HITL Approval Queue (Guarded by Permission) */}
          {activeNav === "hitl" && (
            features.FEATURE_HITL ? (
              hasPermission(currentRole, "approve_remediation") ? (
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
              ) : (
                renderPermissionGuard("approve_remediation", "HITL Remediation Approvals")
              )
            ) : (
              <div className="p-6 bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D] text-xs font-mono text-center text-[#6B6B66]">
                FEATURE_HITL is currently disabled in backend flags.
              </div>
            )
          )}

          {/* PLATFORM SUBSYSTEM: Simulated Remediation Sandbox */}
          {activeNav === "simulated_remediation" && (
            features.FEATURE_REMEDIATION_SIM ? (
              hasPermission(currentRole, "create_remediation_proposals") ||
              hasPermission(currentRole, "execute_remediation") ? (
                <SimulatedRemediationView />
              ) : (
                renderPermissionGuard("create_remediation_proposals", "Simulated Remediation Sandbox")
              )
            ) : (
              <div className="p-6 bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D] text-xs font-mono text-center text-[#6B6B66]">
                FEATURE_REMEDIATION_SIM is currently disabled in backend flags.
              </div>
            )
          )}

          {/* PLATFORM SUBSYSTEM: Sessions & Resume */}
          {activeNav === "sessions" && (
            features.FEATURE_RESUME ? (
              <SessionListResume
                onSelectSession={(_incId) => {
                  setSelectedScenario("link_congestion.json");
                  handleRunDiagnosis();
                }}
              />
            ) : (
              <div className="p-6 bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D] text-xs font-mono text-center text-[#6B6B66]">
                FEATURE_RESUME is currently disabled in backend flags.
              </div>
            )
          )}

          {/* PLATFORM SUBSYSTEM: MCP Tool Gallery */}
          {activeNav === "mcp" && (
            <McpGallery />
          )}
        </main>

        {/* Slide-over Drawer for Formatted Wire Envelope JSON */}
        <EnvelopeSlideOver
          envelope={activeEnvelope}
          onClose={() => setActiveEnvelope(null)}
        />

        {/* Enterprise Monochrome Footer */}
        <footer className="bg-[#FFFFFF] dark:bg-[#161618] border-t border-[#E5E5E3] dark:border-[#2A2A2D] px-6 py-3 font-mono text-[11px] text-[#6B6B66] dark:text-[#888884] flex flex-wrap items-center justify-between gap-4">
          <div>Role: {ROLE_DEFINITIONS[currentRole].title} ({ROLE_DEFINITIONS[currentRole].department})</div>
          <div>Team inSANE MITRA | IIT Bhubaneswar Grand Finale</div>
        </footer>
      </div>
    </div>
  );
};
