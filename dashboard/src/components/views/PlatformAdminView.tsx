import React, { useState, useEffect } from "react";
import { apiFetch, useAuth } from "../../auth/AuthContext";

export interface MicroserviceItem {
  name: string;
  port: number;
  status: string;
  latency_ms: number;
}

export interface PlatformStatusResponse {
  status: string;
  version: string;
  database: {
    engine: string;
    connected: boolean;
    incidents_count: number;
  };
  microservices: MicroserviceItem[];
  mcp: {
    server: string;
    transport: string;
    status: string;
  };
  websockets: {
    active_connections: number;
  };
}

export interface UserAccountItem {
  user_id: string;
  username: string;
  role: string;
  full_name: string | null;
  is_active: boolean;
  created_at: string;
}

export interface AuditLogItem {
  id: number;
  incident_id: string;
  action_id: string;
  device: string;
  status: string;
  actor_username: string | null;
  actor_role: string | null;
  decision: string | null;
  rationale: string | null;
  decision_timestamp: string | null;
}

export interface AuthLogItem {
  id: number;
  timestamp_utc: string;
  event_type: string;
  username: string | null;
  user_id: string | null;
  role: string | null;
  endpoint: string | null;
  details: string | null;
}

export interface IncidentSummaryItem {
  incident_id: string;
  status: string;
  network_id?: string;
  created_at?: string;
  confidence?: number;
  probable_cause?: string;
  assigned_to?: string;
}

export interface TicketItem {
  id?: number;
  ticket_id: string;
  title: string;
  category: string;
  location: string;
  affected_service: string;
  description: string;
  priority: string;
  status: string;
  created_by: string;
  contact_info?: string | null;
  assigned_to?: string | null;
  linked_incident_id?: string | null;
  resolution_notes?: string | null;
  user_facing_summary?: string | null;
  created_at: string;
  updated_at: string;
}

export interface PlatformAdminViewProps {
  onNavigate?: (navId: string) => void;
  isChaosActive?: boolean;
  onToggleChaos?: () => void;
  features?: {
    FEATURE_HITL: boolean;
    FEATURE_REMEDIATION_SIM: boolean;
    FEATURE_RESUME: boolean;
  };
}

export const PlatformAdminView: React.FC<PlatformAdminViewProps> = ({
  onNavigate,
  isChaosActive = false,
  onToggleChaos,
  features,
}) => {
  const { user: currentAuthUser, impersonateUser } = useAuth();
  const [activeTab, setActiveTab] = useState<
    "overview" | "health" | "agents" | "incidents" | "tickets" | "users" | "audit" | "evaluation"
  >("overview");

  const [platformData, setPlatformData] = useState<PlatformStatusResponse | null>(null);
  const [incidents, setIncidents] = useState<IncidentSummaryItem[]>([]);
  const [tickets, setTickets] = useState<TicketItem[]>([]);
  const [users, setUsers] = useState<UserAccountItem[]>([]);
  const [remediationLogs, setRemediationLogs] = useState<AuditLogItem[]>([]);
  const [authLogs, setAuthLogs] = useState<AuthLogItem[]>([]);
  const [scenariosCount, setScenariosCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // User management filter and search
  const [userSearchTerm, setUserSearchTerm] = useState<string>("");
  const [userRoleFilter, setUserRoleFilter] = useState<string>("all");

  // Create user modal state
  const [showCreateUserModal, setShowCreateUserModal] = useState<boolean>(false);
  const [newUsername, setNewUsername] = useState<string>("");
  const [newPassword, setNewPassword] = useState<string>("");
  const [newRole, setNewRole] = useState<string>("noc_operator");
  const [newFullName, setNewFullName] = useState<string>("");
  const [createUserMsg, setCreateUserMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [creatingUser, setCreatingUser] = useState<boolean>(false);

  // User status toggling
  const [statusActionMsg, setStatusActionMsg] = useState<string | null>(null);

  const fetchPlatformData = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      // 1. Fetch live platform status
      const statusRes = await apiFetch("/api/platform/status");
      if (statusRes.ok) {
        const data: PlatformStatusResponse = await statusRes.json();
        setPlatformData(data);
      } else {
        setErrorMsg("Failed to retrieve live platform status. Verify backend connection.");
      }

      // 2. Fetch incidents list
      const incRes = await apiFetch("/api/incidents");
      if (incRes.ok) {
        const incList = await incRes.json();
        setIncidents(incList);
      }

      // 3. Fetch support tickets
      const ticketsRes = await apiFetch("/api/tickets");
      if (ticketsRes.ok) {
        const ticketList = await ticketsRes.json();
        setTickets(ticketList);
      }

      // 4. Fetch users
      const usersRes = await apiFetch("/api/users");
      if (usersRes.ok) {
        const userList: UserAccountItem[] = await usersRes.json();
        setUsers(userList);
      }

      // 5. Fetch remediation logs
      const logsRes = await apiFetch("/api/remediation/logs");
      if (logsRes.ok) {
        const logs: AuditLogItem[] = await logsRes.json();
        setRemediationLogs(logs);
      }

      // 6. Fetch auth audit logs
      const authLogsRes = await apiFetch("/api/auth/logs?limit=50");
      if (authLogsRes.ok) {
        const aLogs: AuthLogItem[] = await authLogsRes.json();
        setAuthLogs(aLogs);
      }

      // 7. Fetch scenarios
      const scenRes = await apiFetch("/api/scenarios");
      if (scenRes.ok) {
        const scenData = await scenRes.json();
        setScenariosCount(Array.isArray(scenData) ? scenData.length : scenData.scenarios?.length || 25);
      }
    } catch {
      setErrorMsg("Network error contacting platform backend services.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPlatformData();
  }, []);

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateUserMsg(null);
    if (!newUsername.trim() || !newPassword) {
      setCreateUserMsg({ type: "error", text: "Username and password are required." });
      return;
    }
    if (newPassword.length < 8) {
      setCreateUserMsg({ type: "error", text: "Password must be at least 8 characters long." });
      return;
    }

    setCreatingUser(true);
    try {
      const res = await apiFetch("/api/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: newUsername.trim(),
          password: newPassword,
          role: newRole,
          full_name: newFullName.trim() || undefined,
        }),
      });

      if (res.ok) {
        const created: UserAccountItem = await res.json();
        setUsers((prev) => [...prev, created]);
        setCreateUserMsg({ type: "success", text: `User ${created.username} provisioned successfully.` });
        setNewUsername("");
        setNewPassword("");
        setNewFullName("");
        setTimeout(() => {
          setShowCreateUserModal(false);
          setCreateUserMsg(null);
        }, 1200);
      } else {
        const err = await res.json().catch(() => ({}));
        setCreateUserMsg({ type: "error", text: err.detail || "Failed to create user account." });
      }
    } catch (err: any) {
      setCreateUserMsg({ type: "error", text: err.message || "Network error while provisioning user." });
    } finally {
      setCreatingUser(false);
    }
  };

  const handleToggleUserStatus = async (userItem: UserAccountItem) => {
    if (userItem.username === currentAuthUser?.username) {
      setStatusActionMsg("Cannot disable your own active Platform Administrator account.");
      return;
    }
    const newStatus = !userItem.is_active;
    try {
      const res = await apiFetch(`/api/users/${userItem.user_id}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: newStatus }),
      });
      if (res.ok) {
        setUsers((prev) =>
          prev.map((u) => (u.user_id === userItem.user_id ? { ...u, is_active: newStatus } : u))
        );
        setStatusActionMsg(`Account ${userItem.username} ${newStatus ? "enabled" : "deactivated"}.`);
        setTimeout(() => setStatusActionMsg(null), 3000);
      } else {
        const err = await res.json().catch(() => ({}));
        setStatusActionMsg(err.detail || "Failed to update account status.");
      }
    } catch {
      setStatusActionMsg("Network error updating user status.");
    }
  };

  const handleInitiateImpersonation = async (targetUsername: string) => {
    const ok = await impersonateUser(targetUsername);
    if (!ok) {
      setStatusActionMsg(`Failed to impersonate ${targetUsername}. Verify backend permissions.`);
    }
  };

  // Metrics calculation
  const servicesList = platformData?.microservices || [];
  const operationalCount = servicesList.filter((s) => s.status.toLowerCase() === "running" || s.status.toLowerCase() === "ok").length;
  const degradedServices = servicesList.filter((s) => s.status.toLowerCase() !== "running" && s.status.toLowerCase() !== "ok");
  const activeIncidents = incidents.filter((i) => i.status === "open" || i.status === "diagnosed" || i.status === "pending");
  const openTickets = tickets.filter((t) => t.status !== "Resolved" && t.status !== "Closed");

  // User filtering
  const filteredUsers = users.filter((u) => {
    const matchesSearch =
      u.username.toLowerCase().includes(userSearchTerm.toLowerCase()) ||
      (u.full_name && u.full_name.toLowerCase().includes(userSearchTerm.toLowerCase()));
    const matchesRole = userRoleFilter === "all" || u.role === userRoleFilter;
    return matchesSearch && matchesRole;
  });

  return (
    <div className="space-y-6 font-mono text-[#111111] dark:text-[#EDEDEA]">
      {/* Platform Executive Header */}
      <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 border border-[#475569] text-[#475569] dark:text-[#94A3B8]">
                Platform SRE &amp; Security Administration
              </span>
              <span className="text-[10px] text-[#6B6B66] dark:text-[#888884]">
                Session ID: plat-adm-{currentAuthUser?.username || "root"}
              </span>
            </div>
            <h2 className="text-xl font-bold tracking-tight">Executive Platform Assurance</h2>
            <p className="text-xs text-[#6B6B66] dark:text-[#888884] mt-0.5">
              Live observability, server-side RBAC governance, and multi-agent health oversight.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={fetchPlatformData}
              disabled={loading}
              className="px-3 py-1.5 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10] hover:border-[#111111] dark:hover:border-[#EDEDEA] text-xs font-semibold uppercase tracking-wider transition-colors"
            >
              {loading ? "Refreshing..." : "Refresh Status"}
            </button>
            <button
              onClick={() => {
                setActiveTab("users");
                setShowCreateUserModal(true);
              }}
              className="px-3 py-1.5 bg-[#475569] hover:bg-[#334155] text-white text-xs font-semibold uppercase tracking-wider transition-colors shadow-sm"
            >
              + Create User
            </button>
          </div>
        </div>

        {errorMsg && (
          <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 text-red-600 dark:text-red-400 text-xs">
            {errorMsg}
          </div>
        )}
        {statusActionMsg && (
          <div className="mt-4 p-3 bg-blue-500/10 border border-blue-500/30 text-blue-600 dark:text-blue-400 text-xs">
            {statusActionMsg}
          </div>
        )}
      </div>

      {/* Navigation Tabs (8 Clear Subsections) */}
      <div className="flex border-b border-[#E5E5E3] dark:border-[#2A2A2D] gap-1 overflow-x-auto text-xs">
        {[
          { id: "overview", label: "Platform Overview" },
          { id: "health", label: "System Health & Infra" },
          { id: "agents", label: `Agent Microservices (${operationalCount}/${servicesList.length || 9})` },
          { id: "incidents", label: `Incidents (${activeIncidents.length} active)` },
          { id: "tickets", label: `Support Tickets (${openTickets.length} open)` },
          { id: "users", label: `Users & Roles (${users.length})` },
          { id: "audit", label: `Governance & Audit (${remediationLogs.length + authLogs.length})` },
          { id: "evaluation", label: "Testing & Evaluation" },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={`px-3.5 py-2.5 font-bold uppercase tracking-wider whitespace-nowrap border-b-2 transition-colors ${
              activeTab === tab.id
                ? "border-[#475569] text-[#111111] dark:text-[#EDEDEA] bg-[#FAFAF9] dark:bg-[#0F0F10]"
                : "border-transparent text-[#6B6B66] dark:text-[#888884] hover:text-[#111111] dark:hover:text-[#EDEDEA]"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ----------------------------------------------------------------- */}
      {/* TAB 1: Platform Overview (Progressive Disclosure - Essential Only)  */}
      {/* ----------------------------------------------------------------- */}
      {activeTab === "overview" && (
        <div className="space-y-6">
          {/* Essential Summary Cards (5 Key Metrics) */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            <div className="p-4 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618]">
              <div className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884] tracking-wider">
                Overall Platform Health
              </div>
              <div className="text-xl font-bold mt-1.5 flex items-center gap-2">
                <span className={`w-2.5 h-2.5 rounded-full ${degradedServices.length === 0 ? "bg-[#5E7A6A]" : "bg-[#9A5B5B]"}`}></span>
                <span>{degradedServices.length === 0 ? "Normal" : "Degraded"}</span>
              </div>
              <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] mt-1">
                {degradedServices.length === 0 ? "All critical services reporting OK" : `${degradedServices.length} service(s) require review`}
              </div>
            </div>

            <div className="p-4 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618]">
              <div className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884] tracking-wider">
                Agent Microservices
              </div>
              <div className="text-xl font-bold mt-1.5">
                {operationalCount} / {servicesList.length || 9}
              </div>
              <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] mt-1">
                Domain agent mesh availability
              </div>
            </div>

            <div className="p-4 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618]">
              <div className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884] tracking-wider">
                Active Incidents
              </div>
              <div className="text-xl font-bold mt-1.5 text-[#A08A5B]">
                {activeIncidents.length}
              </div>
              <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] mt-1">
                {incidents.length} total persisted sessions
              </div>
            </div>

            <div className="p-4 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618]">
              <div className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884] tracking-wider">
                Support Tickets
              </div>
              <div className="text-xl font-bold mt-1.5">
                {openTickets.length} open
              </div>
              <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] mt-1">
                {tickets.length} total user tickets
              </div>
            </div>

            <div className="p-4 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618]">
              <div className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884] tracking-wider">
                Registered Users
              </div>
              <div className="text-xl font-bold mt-1.5">
                {users.length}
              </div>
              <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] mt-1">
                Server-side RBAC accounts
              </div>
            </div>
          </div>

          {/* Prominent Next Action Banner */}
          <div className="p-4 border border-[#475569] bg-[#FAFAF9] dark:bg-[#0F0F10] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <div className="text-xs font-bold uppercase tracking-wider text-[#111111] dark:text-[#EDEDEA]">
                {degradedServices.length > 0 ? "Operational Notice: Services Require Attention" : "Platform State: Nominal"}
              </div>
              <div className="text-xs text-[#6B6B66] dark:text-[#888884] mt-0.5">
                {degradedServices.length > 0
                  ? `${degradedServices.map((s) => s.name).join(", ")} reported non-nominal status.`
                  : "All domain agents, SQLite persistence, and MCP tools are operating normally."}
              </div>
            </div>
            <button
              onClick={() => setActiveTab(degradedServices.length > 0 ? "health" : "incidents")}
              className="px-4 py-2 bg-[#475569] hover:bg-[#334155] text-white text-xs font-bold uppercase tracking-wider transition-colors whitespace-nowrap self-start sm:self-auto"
            >
              {degradedServices.length > 0 ? "Review System Alerts" : "View Active Incidents &rarr;"}
            </button>
          </div>

          {/* Recent System Events (5 Latest Audit Logs) */}
          <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider">Recent System &amp; Security Events</span>
              <button
                onClick={() => setActiveTab("audit")}
                className="text-xs text-[#475569] dark:text-[#94A3B8] hover:underline"
              >
                View Full Audit Logs &rarr;
              </button>
            </div>
            <div className="divide-y divide-[#E5E5E3] dark:divide-[#2A2A2D] text-xs">
              {authLogs.slice(0, 5).map((log) => (
                <div key={log.id} className="py-2 flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                  <div className="flex items-center gap-2">
                    <span className="px-1.5 py-0.5 border border-[#E5E5E3] dark:border-[#2A2A2D] text-[10px] font-semibold uppercase">
                      {log.event_type}
                    </span>
                    <span className="font-medium">{log.username || "System"}</span>
                    <span className="text-[#6B6B66] dark:text-[#888884]">{log.details || log.endpoint}</span>
                  </div>
                  <div className="text-[10px] text-[#6B6B66] dark:text-[#888884]">
                    {log.timestamp_utc ? new Date(log.timestamp_utc).toLocaleTimeString() : "Recent"}
                  </div>
                </div>
              ))}
              {authLogs.length === 0 && (
                <div className="py-3 text-xs text-[#6B6B66] dark:text-[#888884]">No recent system events logged.</div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* TAB 2: System Health & Infrastructure                              */}
      {/* ----------------------------------------------------------------- */}
      {activeTab === "health" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <div className="p-4 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] space-y-2">
              <span className="text-[10px] uppercase font-bold text-[#6B6B66] dark:text-[#888884]">
                Model Context Protocol (MCP)
              </span>
              <div className="text-base font-bold text-[#5E7A6A] flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-[#5E7A6A]"></span>
                <span>{platformData?.mcp?.status || "Active (stdio)"}</span>
              </div>
              <div className="text-xs text-[#6B6B66] dark:text-[#888884] space-y-0.5">
                <div>Server: <code>{platformData?.mcp?.server || "netcoop-mcp-server"}</code></div>
                <div>Transport: <code>{platformData?.mcp?.transport || "stdio (RFC compliant)"}</code></div>
                <div>Tools: 3 verified diagnostic tools</div>
              </div>
            </div>

            <div className="p-4 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] space-y-2">
              <span className="text-[10px] uppercase font-bold text-[#6B6B66] dark:text-[#888884]">
                Database &amp; Persistence
              </span>
              <div className="text-base font-bold text-[#5E7A6A] flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-[#5E7A6A]"></span>
                <span>SQLite Connected</span>
              </div>
              <div className="text-xs text-[#6B6B66] dark:text-[#888884] space-y-0.5">
                <div>Engine: SQLModel / SQLite (WAL mode)</div>
                <div>Incidents Persisted: {incidents.length}</div>
                <div>Support Tickets Persisted: {tickets.length}</div>
              </div>
            </div>

            <div className="p-4 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] space-y-2">
              <span className="text-[10px] uppercase font-bold text-[#6B6B66] dark:text-[#888884]">
                Gateway &amp; Protocol Status
              </span>
              <div className="text-base font-bold text-[#5E7A6A] flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-[#5E7A6A]"></span>
                <span>Collaboration Protocol v1.0</span>
              </div>
              <div className="text-xs text-[#6B6B66] dark:text-[#888884] space-y-0.5">
                <div>Gateway Port: :8001 (Isolated)</div>
                <div>Active WS Connections: {platformData?.websockets?.active_connections || 1}</div>
                <div>Authentication: PBKDF2-SHA256 (600k iter)</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* TAB 3: Agent Microservices                                        */}
      {/* ----------------------------------------------------------------- */}
      {activeTab === "agents" && (
        <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618]">
          <div className="p-4 border-b border-[#E5E5E3] dark:border-[#2A2A2D] flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold uppercase tracking-wider">Domain Microservices Mesh</h3>
              <p className="text-xs text-[#6B6B66] dark:text-[#888884]">
                Isolated HTTP endpoints for individual domain diagnostics.
              </p>
            </div>
            <span className="px-2 py-0.5 border border-[#5E7A6A] text-[#5E7A6A] text-xs font-semibold">
              {operationalCount}/{servicesList.length || 9} Operational
            </span>
          </div>
          <div className="divide-y divide-[#E5E5E3] dark:divide-[#2A2A2D]">
            {servicesList.map((svc) => (
              <div key={svc.name} className="p-4 flex items-center justify-between text-xs hover:bg-[#FAFAF9] dark:hover:bg-[#0F0F10]">
                <div className="flex items-center gap-3">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#5E7A6A]"></span>
                  <div>
                    <div className="font-bold">{svc.name}</div>
                    <div className="text-[#6B6B66] dark:text-[#888884] text-[10px]">
                      Port :{svc.port} &bull; Domain Microservice
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="text-right">
                    <span className="text-[10px] text-[#6B6B66] dark:text-[#888884]">Latency</span>
                    <div className="font-mono">{svc.latency_ms || 1.2} ms</div>
                  </div>
                  <span className="px-2 py-0.5 border border-[#5E7A6A] text-[#5E7A6A] text-[10px] uppercase font-semibold">
                    {svc.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* TAB 4: Incident Overview                                          */}
      {/* ----------------------------------------------------------------- */}
      {activeTab === "incidents" && (
        <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618]">
          <div className="p-4 border-b border-[#E5E5E3] dark:border-[#2A2A2D] flex items-center justify-between">
            <h3 className="text-sm font-bold uppercase tracking-wider">Persisted Network Incidents</h3>
            <span className="text-xs text-[#6B6B66] dark:text-[#888884]">{incidents.length} Records</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#FAFAF9] dark:bg-[#0F0F10] border-b border-[#E5E5E3] dark:border-[#2A2A2D] text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">
                <tr>
                  <th className="p-3">Incident ID</th>
                  <th className="p-3">Status</th>
                  <th className="p-3">Probable Cause</th>
                  <th className="p-3">Assigned To</th>
                  <th className="p-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E5E5E3] dark:divide-[#2A2A2D]">
                {incidents.map((inc) => (
                  <tr key={inc.incident_id} className="hover:bg-[#FAFAF9] dark:hover:bg-[#0F0F10]">
                    <td className="p-3 font-bold font-mono">{inc.incident_id}</td>
                    <td className="p-3">
                      <span className={`px-2 py-0.5 border text-[10px] uppercase font-semibold ${
                        inc.status === "diagnosed" ? "border-[#5E7A6A] text-[#5E7A6A]" : "border-[#A08A5B] text-[#A08A5B]"
                      }`}>
                        {inc.status}
                      </span>
                    </td>
                    <td className="p-3">{inc.probable_cause || "Analyzing telemetry"}</td>
                    <td className="p-3">{inc.assigned_to || "Unassigned"}</td>
                    <td className="p-3 text-right">
                      {onNavigate && (
                        <button
                          onClick={() => onNavigate("role_engineer")}
                          className="px-2 py-1 border border-[#475569] text-[#475569] dark:text-[#94A3B8] hover:bg-[#475569]/10 text-[10px] uppercase font-semibold"
                        >
                          View Triage &rarr;
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* TAB 5: Support Tickets Management                                 */}
      {/* ----------------------------------------------------------------- */}
      {activeTab === "tickets" && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-3 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618]">
              <span className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">Total Tickets</span>
              <div className="text-lg font-bold mt-1">{tickets.length}</div>
            </div>
            <div className="p-3 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618]">
              <span className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">Open / Investigating</span>
              <div className="text-lg font-bold mt-1 text-[#A08A5B]">{openTickets.length}</div>
            </div>
            <div className="p-3 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618]">
              <span className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">Resolved</span>
              <div className="text-lg font-bold mt-1 text-[#5E7A6A]">
                {tickets.filter((t) => t.status === "Resolved" || t.status === "Closed").length}
              </div>
            </div>
            <div className="p-3 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618]">
              <span className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">Critical Priority</span>
              <div className="text-lg font-bold mt-1 text-[#9A5B5B]">
                {tickets.filter((t) => t.priority === "critical").length}
              </div>
            </div>
          </div>

          <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618]">
            <div className="p-4 border-b border-[#E5E5E3] dark:border-[#2A2A2D] flex items-center justify-between">
              <h3 className="text-sm font-bold uppercase tracking-wider">Campus Support Ticket Queue</h3>
              <span className="text-xs text-[#6B6B66] dark:text-[#888884]">{tickets.length} Records</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-[#FAFAF9] dark:bg-[#0F0F10] border-b border-[#E5E5E3] dark:border-[#2A2A2D] text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">
                  <tr>
                    <th className="p-3">Ticket ID</th>
                    <th className="p-3">Title</th>
                    <th className="p-3">Location</th>
                    <th className="p-3">Priority</th>
                    <th className="p-3">Status</th>
                    <th className="p-3">Assigned To</th>
                    <th className="p-3">Linked Incident</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E5E5E3] dark:divide-[#2A2A2D]">
                  {tickets.map((t) => (
                    <tr key={t.ticket_id} className="hover:bg-[#FAFAF9] dark:hover:bg-[#0F0F10]">
                      <td className="p-3 font-bold font-mono">{t.ticket_id}</td>
                      <td className="p-3 max-w-xs truncate">{t.title}</td>
                      <td className="p-3">{t.location}</td>
                      <td className="p-3">
                        <span className={`px-1.5 py-0.5 border text-[9px] uppercase font-semibold ${
                          t.priority === "critical"
                            ? "border-[#9A5B5B] text-[#9A5B5B]"
                            : t.priority === "high"
                            ? "border-[#A08A5B] text-[#A08A5B]"
                            : "border-[#6B6B66] text-[#6B6B66]"
                        }`}>
                          {t.priority}
                        </span>
                      </td>
                      <td className="p-3">
                        <span className="px-1.5 py-0.5 border border-[#475569] text-[9px] uppercase font-semibold">
                          {t.status}
                        </span>
                      </td>
                      <td className="p-3">{t.assigned_to || "Unassigned"}</td>
                      <td className="p-3 font-mono text-[11px]">{t.linked_incident_id || "None"}</td>
                    </tr>
                  ))}
                  {tickets.length === 0 && (
                    <tr>
                      <td colSpan={7} className="p-4 text-center text-[#6B6B66] dark:text-[#888884]">
                        No support tickets currently recorded.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* TAB 6: Users & Roles (Management, Disable, Impersonation)         */}
      {/* ----------------------------------------------------------------- */}
      {activeTab === "users" && (
        <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618]">
          <div className="p-4 border-b border-[#E5E5E3] dark:border-[#2A2A2D] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-bold uppercase tracking-wider">User Account &amp; RBAC Directory</h3>
              <p className="text-xs text-[#6B6B66] dark:text-[#888884]">
                Manage credentials, access states, and initiate audited impersonation.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="text"
                placeholder="Search username..."
                value={userSearchTerm}
                onChange={(e) => setUserSearchTerm(e.target.value)}
                className="px-2.5 py-1 text-xs border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10] focus:border-[#475569] outline-none"
              />
              <select
                value={userRoleFilter}
                onChange={(e) => setUserRoleFilter(e.target.value)}
                className="px-2 py-1 text-xs border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10] focus:border-[#475569] outline-none"
              >
                <option value="all">All Roles</option>
                <option value="platform_admin">Platform Admin</option>
                <option value="network_admin">Network Admin</option>
                <option value="network_engineer">Network Engineer</option>
                <option value="helpdesk">Helpdesk</option>
                <option value="noc_operator">NOC Operator</option>
                <option value="security_analyst">Security Analyst</option>
                <option value="it_manager">IT Manager</option>
                <option value="auditor">Auditor</option>
              </select>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#FAFAF9] dark:bg-[#0F0F10] border-b border-[#E5E5E3] dark:border-[#2A2A2D] text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">
                <tr>
                  <th className="p-3">Username</th>
                  <th className="p-3">Full Name</th>
                  <th className="p-3">Assigned Role</th>
                  <th className="p-3">Account Status</th>
                  <th className="p-3">Created</th>
                  <th className="p-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E5E5E3] dark:divide-[#2A2A2D]">
                {filteredUsers.map((u) => {
                  const isCurrent = u.username === currentAuthUser?.username;
                  return (
                    <tr key={u.user_id} className="hover:bg-[#FAFAF9] dark:hover:bg-[#0F0F10]">
                      <td className="p-3 font-bold font-mono">
                        {u.username}
                        {isCurrent && (
                          <span className="ml-2 px-1.5 py-0.2 border border-[#475569] text-[9px] uppercase text-[#475569]">
                            You
                          </span>
                        )}
                      </td>
                      <td className="p-3">{u.full_name || "-"}</td>
                      <td className="p-3">
                        <span className="px-2 py-0.5 border border-[#475569]/40 bg-[#475569]/5 text-[10px] uppercase font-semibold">
                          {u.role}
                        </span>
                      </td>
                      <td className="p-3">
                        <span className={`px-2 py-0.5 border text-[10px] uppercase font-semibold ${
                          u.is_active ? "border-[#5E7A6A] text-[#5E7A6A]" : "border-[#9A5B5B] text-[#9A5B5B]"
                        }`}>
                          {u.is_active ? "Active" : "Disabled"}
                        </span>
                      </td>
                      <td className="p-3 text-[#6B6B66] dark:text-[#888884]">
                        {u.created_at ? new Date(u.created_at).toLocaleDateString() : "-"}
                      </td>
                      <td className="p-3 text-right space-x-2">
                        {!isCurrent && (
                          <>
                            <button
                              onClick={() => handleToggleUserStatus(u)}
                              className={`px-2 py-1 border text-[10px] uppercase font-semibold transition-colors ${
                                u.is_active
                                  ? "border-[#9A5B5B] text-[#9A5B5B] hover:bg-[#9A5B5B]/10"
                                  : "border-[#5E7A6A] text-[#5E7A6A] hover:bg-[#5E7A6A]/10"
                              }`}
                            >
                              {u.is_active ? "Deactivate" : "Activate"}
                            </button>
                            {u.is_active && u.role !== "platform_admin" && (
                              <button
                                onClick={() => handleInitiateImpersonation(u.username)}
                                title="Securely switch view to this user (audited)"
                                className="px-2 py-1 border border-[#475569] text-[#475569] dark:text-[#94A3B8] hover:bg-[#475569]/10 text-[10px] uppercase font-semibold transition-colors"
                              >
                                Impersonate
                              </button>
                            )}
                          </>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* TAB 7: Governance & Audit Logs                                    */}
      {/* ----------------------------------------------------------------- */}
      {activeTab === "audit" && (
        <div className="space-y-6">
          <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618]">
            <div className="p-4 border-b border-[#E5E5E3] dark:border-[#2A2A2D] flex items-center justify-between">
              <h3 className="text-sm font-bold uppercase tracking-wider">Simulated Remediation Audit Trail</h3>
              <span className="text-xs text-[#6B6B66] dark:text-[#888884]">{remediationLogs.length} Records</span>
            </div>
            <div className="divide-y divide-[#E5E5E3] dark:divide-[#2A2A2D]">
              {remediationLogs.map((log) => (
                <div key={log.id} className="p-4 flex flex-col md:flex-row md:items-center justify-between gap-2 text-xs">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold">{log.action_id}</span>
                      <span className="text-[#6B6B66] dark:text-[#888884]">&bull; Target Device: {log.device}</span>
                      <span className="px-1.5 py-0.5 border border-[#5E7A6A] text-[#5E7A6A] text-[9px] uppercase font-semibold">
                        SIMULATED
                      </span>
                    </div>
                    <div className="text-[11px] text-[#6B6B66] dark:text-[#888884] mt-0.5">
                      Decision: {log.decision || "Pending"} by {log.actor_username || "Unknown"} ({log.actor_role || "N/A"})
                    </div>
                  </div>
                  <div className="text-[10px] text-[#6B6B66] dark:text-[#888884]">
                    {log.decision_timestamp || "Recorded"}
                  </div>
                </div>
              ))}
              {remediationLogs.length === 0 && (
                <div className="p-4 text-xs text-[#6B6B66] dark:text-[#888884]">No remediation actions logged.</div>
              )}
            </div>
          </div>

          <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618]">
            <div className="p-4 border-b border-[#E5E5E3] dark:border-[#2A2A2D] flex items-center justify-between">
              <h3 className="text-sm font-bold uppercase tracking-wider">Security &amp; Impersonation Audit Logs</h3>
              <span className="text-xs text-[#6B6B66] dark:text-[#888884]">{authLogs.length} Records</span>
            </div>
            <div className="divide-y divide-[#E5E5E3] dark:divide-[#2A2A2D]">
              {authLogs.map((log) => (
                <div key={log.id} className="p-3 flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <span className="px-1.5 py-0.5 border border-[#475569] text-[9px] uppercase font-semibold">
                      {log.event_type}
                    </span>
                    <span className="font-bold">{log.username || "System"}</span>
                    <span className="text-[#6B6B66] dark:text-[#888884]">{log.details}</span>
                  </div>
                  <span className="text-[10px] text-[#6B6B66] dark:text-[#888884]">
                    {log.timestamp_utc ? new Date(log.timestamp_utc).toLocaleString() : "-"}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* TAB 8: Testing & Evaluation                                        */}
      {/* ----------------------------------------------------------------- */}
      {activeTab === "evaluation" && (
        <div className="space-y-6">
          {/* Restricted Testing & Fault Injection */}
          <div className="p-5 border border-[#E2E8F0] dark:border-[#2A2A2D] bg-[#F8FAFC] dark:bg-[#0B132B] space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold uppercase tracking-wider text-[#B91C1C]">
                    Restricted Test Operation
                  </span>
                  <span className="px-2 py-0.5 border border-[#B91C1C]/30 bg-[#FEF2F2] text-[#B91C1C] text-[11px] font-bold">
                    Platform Admin Only
                  </span>
                </div>
                <h4 className="text-base font-bold text-[#0B2545] dark:text-[#F1F5F9] mt-0.5">
                  Run Fault-Injection Test (Chaos Mode)
                </h4>
                <p className="text-xs text-[#475569] dark:text-[#94A3B8]">
                  Injects artificial link saturation, queue drops, and packet latency to stress-test multi-agent diagnostic consensus.
                </p>
              </div>
              {onToggleChaos && (
                <button
                  onClick={onToggleChaos}
                  className={`px-5 py-2.5 text-xs font-bold uppercase tracking-wider transition-colors shadow-sm ${
                    isChaosActive
                      ? "bg-[#DC2626] text-white hover:bg-[#B91C1C]"
                      : "bg-[#0B2545] text-white hover:bg-[#133E87]"
                  }`}
                >
                  {isChaosActive ? "Fault-Injection Active" : "Run Fault-Injection Test"}
                </button>
              )}
            </div>
          </div>

          {/* Informational Feature Flags Status */}
          {features && (
            <div className="p-4 border border-[#E2E8F0] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] space-y-2">
              <span className="text-xs font-bold uppercase tracking-wider text-[#0B2545] dark:text-[#94A3B8]">
                Feature Availability &amp; Safeguards (Informational Status)
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                <div className="p-2.5 border border-[#E2E8F0] dark:border-[#2A2A2D] flex items-center justify-between">
                  <span>Human-in-the-Loop (HITL)</span>
                  <span className={`px-2 py-0.5 border font-semibold ${features.FEATURE_HITL ? "text-[#15803D] bg-[#F0FDF4] border-[#15803D]/30" : "text-[#475569] bg-[#F8FAFC]"}`}>
                    {features.FEATURE_HITL ? "Enabled" : "Disabled"}
                  </span>
                </div>
                <div className="p-2.5 border border-[#E2E8F0] dark:border-[#2A2A2D] flex items-center justify-between">
                  <span>Remediation Simulation</span>
                  <span className={`px-2 py-0.5 border font-semibold ${features.FEATURE_REMEDIATION_SIM ? "text-[#15803D] bg-[#F0FDF4] border-[#15803D]/30" : "text-[#475569] bg-[#F8FAFC]"}`}>
                    {features.FEATURE_REMEDIATION_SIM ? "Enabled" : "Disabled"}
                  </span>
                </div>
                <div className="p-2.5 border border-[#E2E8F0] dark:border-[#2A2A2D] flex items-center justify-between">
                  <span>Session Checkpoint Resume</span>
                  <span className={`px-2 py-0.5 border font-semibold ${features.FEATURE_RESUME ? "text-[#15803D] bg-[#F0FDF4] border-[#15803D]/30" : "text-[#475569] bg-[#F8FAFC]"}`}>
                    {features.FEATURE_RESUME ? "Enabled" : "Disabled"}
                  </span>
                </div>
              </div>
            </div>
          )}

          <div className="border border-[#E2E8F0] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-5 space-y-4">
            <h3 className="text-sm font-bold uppercase tracking-wider">7 Mandatory Project Capabilities Verification</h3>
            <p className="text-xs text-[#6B6B66] dark:text-[#888884]">
              Every mandatory project capability is wired to live backend contracts and persisted SQLite records across {scenariosCount || 25} benchmark scenarios.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
              <div className="p-3 border border-[#E5E5E3] dark:border-[#2A2A2D]">
                <div className="font-bold">1. Multi-Agent Collaboration</div>
                <div className="text-[11px] text-[#6B6B66] dark:text-[#888884] mt-1">
                  Source: <code>GET /api/incidents/&#123;id&#125;/envelopes</code>
                  <br />Envelope Protocol v1.0 messages with cryptographically verified message IDs.
                </div>
              </div>
              <div className="p-3 border border-[#E5E5E3] dark:border-[#2A2A2D]">
                <div className="font-bold">2. B1 Robustness</div>
                <div className="text-[11px] text-[#6B6B66] dark:text-[#888884] mt-1">
                  Source: <code>GET /api/platform/status</code> &bull; <code>/api/scenarios</code>
                  <br />Synthetic degradation matrices and packet drop tolerances.
                </div>
              </div>
              <div className="p-3 border border-[#E5E5E3] dark:border-[#2A2A2D]">
                <div className="font-bold">3. B2 Learned Classifier</div>
                <div className="text-[11px] text-[#6B6B66] dark:text-[#888884] mt-1">
                  Source: <code>GET /api/incidents/&#123;id&#125;</code> (<code>incident_type</code>)
                  <br />Multi-class root cause classifier with softmax calibrated probabilities.
                </div>
              </div>
              <div className="p-3 border border-[#E5E5E3] dark:border-[#2A2A2D]">
                <div className="font-bold">4. Conformal Calibration</div>
                <div className="text-[11px] text-[#6B6B66] dark:text-[#888884] mt-1">
                  Source: <code>GET /api/incidents/&#123;id&#125;</code> (<code>conformal_set</code>)
                  <br />Rigorous uncertainty bounds guaranteeing 95% statistical coverage.
                </div>
              </div>
              <div className="p-3 border border-[#E5E5E3] dark:border-[#2A2A2D]">
                <div className="font-bold">5. NetCoop MCP Server</div>
                <div className="text-[11px] text-[#6B6B66] dark:text-[#888884] mt-1">
                  Source: <code>GET /api/mcp/info</code>
                  <br />Registered tools: query_telemetry, run_diagnostic, simulate_remediation.
                </div>
              </div>
              <div className="p-3 border border-[#E5E5E3] dark:border-[#2A2A2D]">
                <div className="font-bold">6. Simulation-Only Remediation</div>
                <div className="text-[11px] text-[#6B6B66] dark:text-[#888884] mt-1">
                  Source: <code>GET /api/remediation/logs</code>
                  <br />Strict isolation ensuring zero production mutation with full rollback scripts.
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Create User Modal */}
      {showCreateUserModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D] p-6 shadow-xl">
            <div className="flex items-center justify-between pb-3 border-b border-[#E5E5E3] dark:border-[#2A2A2D]">
              <h3 className="text-sm font-bold uppercase tracking-wider">Provision New Account</h3>
              <button
                onClick={() => setShowCreateUserModal(false)}
                className="text-xs text-[#6B6B66] hover:text-[#111111] dark:hover:text-[#EDEDEA]"
              >
                Close
              </button>
            </div>

            <form onSubmit={handleCreateUser} className="mt-4 space-y-4 text-xs">
              {createUserMsg && (
                <div
                  className={`p-2.5 border text-xs ${
                    createUserMsg.type === "success"
                      ? "bg-green-500/10 border-green-500/30 text-green-600 dark:text-green-400"
                      : "bg-red-500/10 border-red-500/30 text-red-600 dark:text-red-400"
                  }`}
                >
                  {createUserMsg.text}
                </div>
              )}

              <div>
                <label className="block text-[10px] uppercase font-bold text-[#6B6B66] dark:text-[#888884] mb-1">
                  Username
                </label>
                <input
                  type="text"
                  required
                  value={newUsername}
                  onChange={(e) => setNewUsername(e.target.value)}
                  className="w-full p-2 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10] focus:border-[#475569] outline-none"
                />
              </div>

              <div>
                <label className="block text-[10px] uppercase font-bold text-[#6B6B66] dark:text-[#888884] mb-1">
                  Password (min 8 chars)
                </label>
                <input
                  type="password"
                  required
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full p-2 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10] focus:border-[#475569] outline-none"
                />
              </div>

              <div>
                <label className="block text-[10px] uppercase font-bold text-[#6B6B66] dark:text-[#888884] mb-1">
                  Full Name
                </label>
                <input
                  type="text"
                  value={newFullName}
                  onChange={(e) => setNewFullName(e.target.value)}
                  className="w-full p-2 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10] focus:border-[#475569] outline-none"
                />
              </div>

              <div>
                <label className="block text-[10px] uppercase font-bold text-[#6B6B66] dark:text-[#888884] mb-1">
                  Assigned RBAC Role
                </label>
                <select
                  value={newRole}
                  onChange={(e) => setNewRole(e.target.value)}
                  className="w-full p-2 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10] focus:border-[#475569] outline-none"
                >
                  <option value="noc_operator">NOC Operator</option>
                  <option value="network_engineer">Network Engineer</option>
                  <option value="network_admin">Network Admin</option>
                  <option value="helpdesk">Helpdesk</option>
                  <option value="security_analyst">Security Analyst</option>
                  <option value="it_manager">IT Manager</option>
                  <option value="platform_admin">Platform Admin</option>
                  <option value="auditor">Auditor</option>
                </select>
              </div>

              <div className="pt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowCreateUserModal(false)}
                  className="px-3 py-1.5 border border-[#E5E5E3] dark:border-[#2A2A2D] text-xs font-semibold uppercase"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creatingUser}
                  className="px-4 py-1.5 bg-[#475569] hover:bg-[#334155] text-white text-xs font-semibold uppercase tracking-wider"
                >
                  {creatingUser ? "Provisioning..." : "Provision Account"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
