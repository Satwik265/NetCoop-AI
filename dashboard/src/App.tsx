import React, { useEffect, useState } from "react";
import {
  EnvelopeLogItem,
  ScenarioMeta,
  UnifiedDiagnosticReport,
} from "./types/protocol";
import { UserRole, ROLE_DEFINITIONS, hasPermission } from "./rbac/roles";
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
import { useAuth, apiFetch } from "./auth/AuthContext";
import { LoginModal } from "./components/LoginModal";
import { CompareRunsModal, RunComparisonData } from "./components/CompareRunsModal";

export interface HistoryItem {
  nav: string;
  label: string;
  incidentId?: string;
  ticketId?: string;
  tab?: string;
}

const getPrimaryRoleNav = (role?: UserRole): string => {
  switch (role) {
    case "platform_admin":
      return "role_platform_admin";
    case "network_admin":
      return "role_admin";
    case "network_engineer":
      return "role_engineer";
    case "helpdesk":
      return "role_helpdesk";
    case "noc_operator":
      return "role_noc";
    case "security_analyst":
      return "role_security";
    case "it_manager":
      return "role_it_manager";
    case "auditor":
      return "role_auditor";
    default:
      return "role_helpdesk";
  }
};

const getNavLabel = (navId: string): string => {
  switch (navId) {
    case "role_platform_admin":
      return "Platform Admin";
    case "role_admin":
      return "Network Admin";
    case "role_engineer":
      return "Network Engineer";
    case "role_helpdesk":
      return "Helpdesk Support";
    case "role_noc":
      return "NOC Operations";
    case "role_security":
      return "Security Defense";
    case "role_it_manager":
      return "IT Leadership";
    case "role_auditor":
      return "Compliance & Auditor";
    case "workspace":
      return "Consensus Workspace";
    case "topology":
      return "Topology & Blast Radius";
    case "report":
      return "Diagnostic Report";
    case "interop":
      return "Interoperability Inspector";
    case "proof":
      return "Proof & Evaluation";
    case "hitl":
      return "HITL Approvals";
    case "simulated_remediation":
      return "Simulated Remediation";
    case "sessions":
      return "Sessions & Resume";
    case "mcp":
      return "MCP Tool Catalog";
    default:
      return navId;
  }
};

const isAuthorizedForNav = (navId: string, role?: UserRole): boolean => {
  if (!role) return false;
  // Platform administrator has supervisory oversight
  if (role === "platform_admin") return true;

  // Strict role boundaries
  if (navId === "role_engineer") return role === "network_engineer";
  if (navId === "role_admin") return role === "network_admin";
  if (navId === "role_helpdesk") return role === "helpdesk";
  if (navId === "role_noc") return role === "noc_operator";
  if (navId === "role_security") return role === "security_analyst";
  if (navId === "role_it_manager") return role === "it_manager";
  if (navId === "role_auditor") return role === "auditor";
  if (navId === "role_platform_admin") return false;

  // Helpdesk cannot access technical diagnostic platform subsystems
  if (role === "helpdesk") {
    return false;
  }

  // Guarded actions
  if (navId === "hitl") return hasPermission(role, "approve_remediation");
  if (navId === "simulated_remediation") return hasPermission(role, "create_remediation_proposals");

  return true;
};

export const App: React.FC = () => {
  const {
    user,
    token,
    isDemoMode,
    isImpersonating,
    impersonatedBy,
    exitImpersonation,
    logout,
    openLoginModal,
    lastForbiddenError,
    clearForbiddenError,
    loginAsDemoAccount,
  } = useAuth();

  // Role & Navigation state - authority is derived from authenticated backend JWT
  const [currentRole, setCurrentRole] = useState<UserRole>(() => {
    return user?.role || "helpdesk";
  });
  const [activeNav, setActiveNav] = useState<string>(() => {
    return user?.role ? getPrimaryRoleNav(user.role) : "role_helpdesk";
  });
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState<boolean>(false);

  // Consistent Navigation History Stack & Breadcrumbs
  const [historyStack, setHistoryStack] = useState<HistoryItem[]>(() => {
    const initNav = user?.role ? getPrimaryRoleNav(user.role) : "role_helpdesk";
    return [{ nav: initNav, label: "Dashboard" }];
  });

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
  const [qualityScore, setQualityScore] = useState<number>(1.0);
  const [detectedFormat, setDetectedFormat] = useState<string>("canonical");
  const [validationErrors, setValidationErrors] = useState<TypedValidationErrorItem[]>([]);
  const [transformationsCount, setTransformationsCount] = useState<number>(0);
  const [recordsCount, setRecordsCount] = useState<number>(0);
  const [isValidated, setIsValidated] = useState<boolean>(false);
  const [validatingInput, setValidatingInput] = useState<boolean>(false);

  // Diagnosis Run Provenance & Comparison state
  const [lastRunId, setLastRunId] = useState<string | null>(null);
  const [lastRunTimestamp, setLastRunTimestamp] = useState<string | null>(null);
  const [previousRunId, setPreviousRunId] = useState<string | null>(null);
  const [executionStatus, setExecutionStatus] = useState<"idle" | "running" | "completed" | "failed">("idle");
  const [runErrorMessage, setRunErrorMessage] = useState<string | null>(null);
  const [isCompareModalOpen, setIsCompareModalOpen] = useState<boolean>(false);
  const [comparisonData, setComparisonData] = useState<RunComparisonData | null>(null);
  const [loadingComparison, setLoadingComparison] = useState<boolean>(false);

  // Sync currentRole and primary view when authenticated user changes
  useEffect(() => {
    if (user?.role) {
      setCurrentRole(user.role);
      const homeNav = getPrimaryRoleNav(user.role);
      setActiveNav(homeNav);
      setHistoryStack([{ nav: homeNav, label: "Dashboard" }]);
    }
  }, [user?.role, user?.username]);

  // Browser popstate navigation handler (supports Back / Forward buttons)
  useEffect(() => {
    const handlePopState = (e: PopStateEvent) => {
      if (e.state && e.state.nav) {
        if (isAuthorizedForNav(e.state.nav, user?.role)) {
          setActiveNav(e.state.nav);
          setHistoryStack((prev) => {
            const idx = prev.findIndex((item) => item.nav === e.state.nav);
            if (idx >= 0) {
              return prev.slice(0, idx + 1);
            }
            return [...prev, { nav: e.state.nav, label: e.state.label || getNavLabel(e.state.nav) }];
          });
        }
      }
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, [user?.role]);

  // Navigate to target view with history tracking
  const navigateTo = (navId: string, customLabel?: string, meta?: { incidentId?: string; ticketId?: string; tab?: string }) => {
    if (!isAuthorizedForNav(navId, user?.role)) {
      clearForbiddenError();
      return;
    }
    const label = customLabel || getNavLabel(navId);
    const newItem: HistoryItem = { nav: navId, label, ...meta };
    setHistoryStack((prev) => [...prev, newItem]);
    setActiveNav(navId);
    window.history.pushState({ nav: navId, label, ...meta }, "", `?nav=${navId}`);
  };

  const handleNavigateBack = () => {
    if (historyStack.length <= 1) return;
    const newStack = [...historyStack];
    newStack.pop();
    const prevItem = newStack[newStack.length - 1];
    setHistoryStack(newStack);
    setActiveNav(prevItem.nav);
    window.history.pushState({ nav: prevItem.nav, label: prevItem.label }, "", `?nav=${prevItem.nav}`);
  };

  const handleNavigateHome = () => {
    const homeNav = getPrimaryRoleNav(user?.role);
    const homeItem: HistoryItem = { nav: homeNav, label: "Dashboard" };
    setHistoryStack([homeItem]);
    setActiveNav(homeNav);
    window.history.pushState({ nav: homeNav, label: "Dashboard" }, "", `?nav=${homeNav}`);
  };

  const handleBreadcrumbClick = (crumb: HistoryItem) => {
    const idx = historyStack.findIndex((item) => item.nav === crumb.nav);
    if (idx >= 0) {
      setHistoryStack(historyStack.slice(0, idx + 1));
      setActiveNav(crumb.nav);
      window.history.pushState({ nav: crumb.nav, label: crumb.label }, "", `?nav=${crumb.nav}`);
    } else {
      navigateTo(crumb.nav, crumb.label);
    }
  };

  // Only Platform Administrator can initiate role switching/impersonation
  const handleSelectRole = (role: UserRole) => {
    if (user?.role !== "platform_admin") {
      return;
    }
    const roleToUserMap: Record<UserRole, string> = {
      noc_operator: "noc",
      network_engineer: "engineer",
      network_admin: "admin",
      security_analyst: "security",
      it_manager: "it_manager",
      platform_admin: "platform_admin",
      auditor: "auditor",
      helpdesk: "helpdesk",
    };
    const targetUser = roleToUserMap[role];
    if (targetUser && user?.role !== role) {
      if (isDemoMode) {
        loginAsDemoAccount(targetUser).then((ok) => {
          if (!ok) {
            setCurrentRole(role);
          }
        });
      } else {
        openLoginModal();
      }
    }
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
      .catch(() => {});
  }, []);

  // Fetch scenarios from API on load
  useEffect(() => {
    fetch("/api/scenarios")
      .then((res) => {
        if (!res.ok) throw new Error("Failed to load scenarios");
        return res.json();
      })
      .then((data: ScenarioMeta[]) => {
        if (data && data.length > 0) {
          setScenarios(data);
          setSelectedScenario(data[0].filename);
        }
      })
      .catch(() => {});
  }, []);

  // Fetch default diagnostic report on startup
  useEffect(() => {
    fetch("/api/reports/latest")
      .then((res) => {
        if (!res.ok) throw new Error("Latest report endpoint returned error");
        return res.json();
      })
      .then((data: UnifiedDiagnosticReport) => {
        if (data && data.incident_id) {
          setReport(data);
        }
      })
      .catch(() => {});
  }, []);

  // Fetch campus topology on startup
  useEffect(() => {
    apiFetch("/api/topology")
      .then((res) => {
        if (!res.ok) throw new Error("Failed to load topology");
        return res.json();
      })
      .then((data) => {
        if (data && data.nodes && data.links) {
          setCurrentTopology(data);
        }
      })
      .catch(() => {});
  }, []);

  // WebSocket connection for real-time events
  useEffect(() => {
    if (!token) {
      setWsStatus("offline");
      return;
    }

    let ws: WebSocket | null = null;
    let reconnectTimer: any = null;

    const connectWs = async () => {
      try {
        setWsStatus("connecting");
        const ticketRes = await apiFetch("/api/auth/ws-ticket", { method: "POST" });
        if (!ticketRes.ok) {
          setWsStatus("offline");
          return;
        }
        const ticketData = await ticketRes.json();
        const ticket = ticketData.ticket;

        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${protocol}//${window.location.host}/ws/events?ticket=${ticket}`;
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          setWsStatus("connected");
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.event_type === "envelope_sent" && data.message_id) {
              setEnvelopes((prev) => [
                ...prev,
                {
                  id: prev.length + 1,
                  correlation_id: data.payload?.correlation_id || "corr-ws",
                  message_id: data.message_id,
                  timestamp_utc: data.timestamp_utc || new Date().toISOString(),
                  sender: data.sender || "unknown",
                  recipient: data.recipient || "unknown",
                  message_type: data.message_type || "OBSERVATION",
                  priority: "normal",
                  payload: data.payload || {},
                  context: data.context || {},
                },
              ]);
            }
          } catch {}
        };

        ws.onclose = () => {
          setWsStatus("offline");
          reconnectTimer = setTimeout(connectWs, 5000);
        };

        ws.onerror = () => {
          setWsStatus("offline");
        };
      } catch {
        setWsStatus("offline");
        reconnectTimer = setTimeout(connectWs, 5000);
      }
    };

    connectWs();

    return () => {
      if (ws) ws.close();
      if (reconnectTimer) clearTimeout(reconnectTimer);
    };
  }, [token]);

  const handleValidateScenario = async (filename?: string) => {
    const target = filename || selectedScenario;
    if (!target) return;
    setValidatingInput(true);
    try {
      const res = await apiFetch(`/api/scenarios/${target}/validate`);
      if (res.ok) {
        const data = await res.json();
        setQualityScore(data.quality_score ?? 1.0);
        setDetectedFormat(data.detected_format ?? "canonical");
        setValidationErrors(data.validation_errors ?? []);
        setTransformationsCount(data.transformations_count ?? 0);
        setRecordsCount(data.records_count ?? 0);
        setIsValidated(true);
      }
    } catch {}
    finally {
      setValidatingInput(false);
    }
  };

  const handleSelectScenario = (filename: string) => {
    setSelectedScenario(filename);
    handleValidateScenario(filename);
  };

  // Handler for running full diagnosis on demand with run ID provenance and state
  const handleRunDiagnosis = async () => {
    if (!selectedScenario) return;
    setLoading(true);
    setExecutionStatus("running");
    setRunErrorMessage(null);
    try {
      const res = await apiFetch(`/api/scenarios/${selectedScenario}/run`, {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        if (data.report) {
          setReport(data.report);
        }
        if (data.envelopes && data.envelopes.length > 0) {
          setEnvelopes(data.envelopes);
          setCurrentIndex(data.envelopes.length - 1);
        }
        setLastRunId(data.run_id);
        setLastRunTimestamp(data.timestamp_utc || new Date().toISOString());
        setPreviousRunId(data.previous_run_id || null);
        setExecutionStatus("completed");
      } else {
        const err = await res.json().catch(() => ({ detail: "Diagnostic execution failed" }));
        setExecutionStatus("failed");
        setRunErrorMessage(err.detail || "Diagnostic execution failed.");
      }
    } catch (e: any) {
      setExecutionStatus("failed");
      setRunErrorMessage(e?.message || "Network error connecting to diagnostic service.");
    } finally {
      setLoading(false);
    }
  };

  const handleCompareRuns = async () => {
    if (!lastRunId || !previousRunId) return;
    setIsCompareModalOpen(true);
    setLoadingComparison(true);
    try {
      const res = await apiFetch(`/api/runs/${lastRunId}/compare/${previousRunId}`);
      if (res.ok) {
        const data = await res.json();
        setComparisonData(data);
      }
    } catch {}
    finally {
      setLoadingComparison(false);
    }
  };

  const currentEnvelope = envelopes[currentIndex] || envelopes[envelopes.length - 1] || null;
  const blastRadiusList = report?.affected_devices || [];

  const roleDef = ROLE_DEFINITIONS[currentRole] || ROLE_DEFINITIONS["helpdesk"];
  const isNavAuthorized = isAuthorizedForNav(activeNav, user?.role);

  return (
    <div className="flex h-screen bg-[#F8FAFC] dark:bg-[#0B132B] text-[#0F172A] dark:text-[#F1F5F9] overflow-hidden font-sans antialiased">
      {/* Role-isolated Sidebar */}
      <Sidebar
        currentRole={currentRole}
        onSelectRole={handleSelectRole}
        activeNav={activeNav}
        onSelectNav={(nav) => navigateTo(nav)}
        wsStatus={wsStatus}
        features={features}
        isMobileOpen={isMobileMenuOpen}
        onCloseMobile={() => setIsMobileMenuOpen(false)}
      />

      {/* Main Layout Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        {/* Impersonation Security Alert Banner */}
        {isImpersonating && (
          <div className="bg-[#9A5B5B]/15 border-b border-[#9A5B5B]/40 px-6 py-2 text-xs flex items-center justify-between font-mono text-[#9A5B5B] dark:text-[#E89E9E] z-40 sticky top-0">
            <div className="flex items-center gap-2">
              <span className="font-bold uppercase tracking-wider px-1.5 py-0.5 border border-[#9A5B5B]/40 bg-[#9A5B5B]/10">
                AUDITED IMPERSONATION
              </span>
              <span>
                Viewing as <strong>{user?.username}</strong> ({user?.role}) &mdash; Initiated by Administrator <strong>{impersonatedBy}</strong>
              </span>
            </div>
            <button
              onClick={async () => {
                await exitImpersonation();
                handleNavigateHome();
              }}
              className="px-2.5 py-1 bg-[#9A5B5B] text-white hover:bg-[#8A4B4B] text-[11px] font-semibold uppercase tracking-wider transition-colors shadow-sm"
            >
              Exit Impersonation
            </button>
          </div>
        )}

        {/* Top Institutional Header (IIT Bhubaneswar Academic Theme) */}
        <header className="bg-[#FFFFFF] dark:bg-[#161618] border-b border-[#E2E8F0] dark:border-[#2A2A2D] px-6 py-3.5 flex flex-wrap items-center justify-between gap-4 font-sans sticky top-0 z-30 shadow-sm">
          <div className="flex items-center gap-3.5">
            <button
              onClick={() => setIsMobileMenuOpen(true)}
              className="lg:hidden p-1.5 border border-[#E2E8F0] dark:border-[#2A2A2D] text-xs font-semibold"
            >
              Menu
            </button>
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-sm bg-[#0B2545] dark:bg-[#133E87] flex items-center justify-center text-white font-bold text-xs tracking-wider">
                IIT
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-base font-bold tracking-tight text-[#0B2545] dark:text-[#F1F5F9]">
                    NetCoop AI
                  </h1>
                  <span className={`px-2 py-0.5 border text-xs font-semibold ${roleDef.badgeClass}`}>
                    {roleDef.title}
                  </span>
                </div>
                <div className="text-xs text-[#475569] dark:text-[#94A3B8]">
                  Autonomous Campus Network Diagnostic Platform &bull; IIT Bhubaneswar
                </div>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3 text-sm">
            {/* Authenticated User Badge */}
            <div className="flex items-center gap-2 border border-[#E2E8F0] dark:border-[#2A2A2D] px-3 py-1.5 text-xs bg-[#F8FAFC] dark:bg-[#0F0F10]">
              <span className="text-[#475569] dark:text-[#94A3B8] font-medium">Logged in as:</span>
              <span className="font-bold text-[#0F172A] dark:text-[#EDEDEA]">
                {user ? `${user.username} (${user.role})` : "Unauthenticated"}
              </span>

              {user?.role === "platform_admin" && (
                <button
                  onClick={openLoginModal}
                  className="ml-1 px-2 py-0.5 border border-[#0B2545] dark:border-[#3A86FF] hover:bg-[#0B2545]/10 text-[11px] font-bold uppercase transition-colors"
                  title="Administrative Account Management"
                >
                  Switch User
                </button>
              )}

              {user && (
                <button
                  onClick={logout}
                  className="px-2 py-0.5 border border-[#DC2626] text-[#DC2626] hover:bg-[#FEF2F2] text-[11px] font-bold uppercase transition-colors"
                  title="Log out"
                >
                  Logout
                </button>
              )}
            </div>

            <ThemeToggle />
          </div>
        </header>

        {/* Consistent Navigation Bar (Back Button + Clickable Breadcrumbs + Home Shortcut) */}
        <div className="bg-[#FAFAF9] dark:bg-[#121214] border-b border-[#E5E5E3] dark:border-[#2A2A2D] px-6 py-2 flex items-center justify-between text-xs font-mono">
          <div className="flex items-center gap-2.5 overflow-x-auto">
            {historyStack.length > 1 && (
              <button
                onClick={handleNavigateBack}
                className="flex items-center gap-1 px-2.5 py-1 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#1A1A1D] hover:border-[#111111] dark:hover:border-[#EDEDEA] text-[11px] font-semibold uppercase tracking-wider text-[#111111] dark:text-[#EDEDEA] transition-colors"
                title="Return to previous screen"
              >
                <span>&larr; Back</span>
              </button>
            )}

            {/* Breadcrumb Trail */}
            <nav className="flex items-center gap-1.5 text-[11px]">
              {historyStack.map((crumb, idx) => {
                const isLast = idx === historyStack.length - 1;
                return (
                  <React.Fragment key={`${crumb.nav}-${idx}`}>
                    {idx > 0 && <span className="text-[#888884]">&rsaquo;</span>}
                    {isLast ? (
                      <span className="font-semibold text-[#111111] dark:text-[#EDEDEA]">
                        {crumb.label}
                      </span>
                    ) : (
                      <button
                        onClick={() => handleBreadcrumbClick(crumb)}
                        className="text-[#6B6B66] dark:text-[#888884] hover:text-[#111111] dark:hover:text-[#EDEDEA] hover:underline"
                      >
                        {crumb.label}
                      </button>
                    )}
                  </React.Fragment>
                );
              })}
            </nav>
          </div>

          <button
            onClick={handleNavigateHome}
            className="text-[10px] uppercase font-semibold text-[#6B6B66] dark:text-[#888884] hover:text-[#111111] dark:hover:text-[#EDEDEA] hover:underline whitespace-nowrap"
          >
            Home Dashboard
          </button>
        </div>

        {/* Main Content Area */}
        <main className="flex-1 p-4 sm:p-6 space-y-6 max-w-7xl w-full mx-auto">
          {/* Server-Side 403 Forbidden Alert Banner */}
          {lastForbiddenError && (
            <div className="bg-red-500/10 border border-red-500/30 text-red-600 dark:text-red-400 p-3 text-xs flex items-center justify-between font-mono">
              <div>
                <span className="font-semibold uppercase tracking-wider block mb-0.5">
                  Permission Denied (HTTP 403 Forbidden)
                </span>
                {lastForbiddenError}
              </div>
              <button
                onClick={clearForbiddenError}
                className="text-xs uppercase tracking-wider font-semibold ml-4 hover:underline"
              >
                Dismiss
              </button>
            </div>
          )}

          {/* Universal Scenario Picker (Visible only to technical operational roles, hidden for Helpdesk) */}
          {(currentRole === "platform_admin" || currentRole === "network_engineer" || currentRole === "network_admin") && (
            <ScenarioPicker
              scenarios={scenarios}
              selectedScenario={selectedScenario}
              onSelectScenario={handleSelectScenario}
              onRunDiagnosis={handleRunDiagnosis}
              loading={loading}
              qualityScore={qualityScore}
              detectedFormat={detectedFormat}
              validationErrors={validationErrors}
              transformationsCount={transformationsCount}
              isValidated={isValidated}
              recordsCount={recordsCount}
              onRunValidation={() => handleValidateScenario(selectedScenario)}
              validating={validatingInput}
              lastRunId={lastRunId}
              lastRunTimestamp={lastRunTimestamp}
              previousRunId={previousRunId}
              onCompareRuns={handleCompareRuns}
              executionStatus={executionStatus}
              errorMessage={runErrorMessage}
            />
          )}

          {/* ROUTE GUARD: Check authorization for active view */}
          {!isNavAuthorized ? (
            <div className="p-8 border border-red-500/30 bg-red-500/10 text-red-600 dark:text-red-400 font-mono space-y-3">
              <div className="font-bold uppercase text-sm">Access Denied (RBAC Protected Route)</div>
              <p className="text-xs">
                Your authenticated role (<strong>{user?.role}</strong>) does not have authorization to view the requested dashboard (<strong>{getNavLabel(activeNav)}</strong>).
              </p>
              <button
                onClick={handleNavigateHome}
                className="px-3 py-1.5 bg-[#475569] text-white text-xs font-bold uppercase tracking-wider"
              >
                Return to My Authorized Dashboard &rarr;
              </button>
            </div>
          ) : (
            <>
              {/* 1. ROLE VIEW: NOC Operator */}
              {activeNav === "role_noc" && (
                <NocView
                  report={report}
                  onInvestigateIncident={() => navigateTo("role_engineer")}
                />
              )}

              {/* 2. ROLE VIEW: Network Engineer */}
              {activeNav === "role_engineer" && (
                <EngineerView
                  report={report}
                  onLaunchSimulation={() => navigateTo("simulated_remediation")}
                  onOpenHitlQueue={() => navigateTo("hitl")}
                  onNavigate={(nav) => navigateTo(nav)}
                  lastRunId={lastRunId}
                  lastRunTimestamp={lastRunTimestamp}
                  selectedScenario={selectedScenario}
                  executionStatus={executionStatus}
                  runErrorMessage={runErrorMessage}
                  previousRunId={previousRunId}
                  onRunDiagnosis={handleRunDiagnosis}
                  onCompareRuns={handleCompareRuns}
                />
              )}

              {/* 3. ROLE VIEW: Network Administrator */}
              {activeNav === "role_admin" && (
                <AdminView onNavigate={(nav) => navigateTo(nav)} />
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
                <PlatformAdminView onNavigate={(nav) => navigateTo(nav)} isChaosActive={isChaosActive} onToggleChaos={() => setIsChaosActive((p) => !p)} features={features} />
              )}

              {/* 7. ROLE VIEW: Auditor / Compliance */}
              {activeNav === "role_auditor" && (
                <AuditorView report={report} />
              )}

              {/* 8. ROLE VIEW: Helpdesk Support */}
              {activeNav === "role_helpdesk" && (
                <HelpdeskView
                  report={report}
                  onNavigateToIncidents={() => navigateTo("role_engineer")}
                  onNavigate={(nav) => navigateTo(nav)}
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

              {/* PLATFORM SUBSYSTEM: Unified Diagnostic Report */}
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

              {/* PLATFORM SUBSYSTEM: HITL Approval Queue */}
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
                    <div className="p-6 bg-red-500/10 border border-red-500/30 text-xs font-mono text-center text-red-600 dark:text-red-400">
                      Access Restricted: Missing required permission &apos;approve_remediation&apos;.
                    </div>
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
                    <div className="p-6 bg-red-500/10 border border-red-500/30 text-xs font-mono text-center text-red-600 dark:text-red-400">
                      Access Restricted: Missing permission &apos;create_remediation_proposals&apos;.
                    </div>
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
            </>
          )}
        </main>

        {/* Slide-over Drawer for Formatted Wire Envelope JSON */}
        <EnvelopeSlideOver
          envelope={activeEnvelope}
          onClose={() => setActiveEnvelope(null)}
        />

        {/* Enterprise Monochrome Footer */}
        <footer className="bg-[#FFFFFF] dark:bg-[#161618] border-t border-[#E5E5E3] dark:border-[#2A2A2D] px-6 py-3 font-mono text-[11px] text-[#6B6B66] dark:text-[#888884] flex flex-wrap items-center justify-between gap-4">
          <div>Role: {roleDef.title} ({roleDef.department})</div>
          <div>NetCoop AI &bull; Autonomous Multi-Agent Network Diagnosis</div>
        </footer>
      </div>
            <CompareRunsModal
        isOpen={isCompareModalOpen}
        onClose={() => setIsCompareModalOpen(false)}
        data={comparisonData}
        loading={loadingComparison}
      />
      <LoginModal />
    </div>
  );
};
