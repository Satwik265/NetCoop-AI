import React, { useState } from "react";
import { UserRole, ROLE_DEFINITIONS, hasPermission, Permission } from "../rbac/roles";
import { WebSocketStatus } from "../hooks/useWebSocket";

export interface NavItem {
  id: string;
  label: string;
  category: "role_view" | "platform" | "remediation" | "governance";
  requiredPermission?: Permission;
  badge?: string;
}

interface SidebarProps {
  currentRole: UserRole;
  onSelectRole: (role: UserRole) => void;
  activeNav: string;
  onSelectNav: (navId: string) => void;
  wsStatus: WebSocketStatus;
  features: {
    FEATURE_HITL: boolean;
    FEATURE_REMEDIATION_SIM: boolean;
    FEATURE_RESUME: boolean;
  };
  isMobileOpen: boolean;
  onCloseMobile: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentRole,
  onSelectRole,
  activeNav,
  onSelectNav,
  wsStatus,
  features,
  isMobileOpen,
  onCloseMobile,
}) => {
  const [showPermissions, setShowPermissions] = useState<boolean>(false);
  const currentRoleDef = ROLE_DEFINITIONS[currentRole];

  const roleNavItems: Array<{ roleId: UserRole; label: string; navId: string }> = [
    { roleId: "noc_operator", label: "NOC Operations", navId: "role_noc" },
    { roleId: "network_engineer", label: "Network Engineer", navId: "role_engineer" },
    { roleId: "network_admin", label: "Network Admin", navId: "role_admin" },
    { roleId: "security_analyst", label: "Security Analyst", navId: "role_security" },
    { roleId: "it_manager", label: "IT Management", navId: "role_it_manager" },
    { roleId: "platform_admin", label: "Platform SRE", navId: "role_platform_admin" },
    { roleId: "auditor", label: "Auditor & Compliance", navId: "role_auditor" },
    { roleId: "helpdesk", label: "Helpdesk Support", navId: "role_helpdesk" },
  ];

  const platformNavItems: NavItem[] = [
    { id: "workspace", label: "Consensus Workspace", category: "platform" },
    { id: "topology", label: "Topology & Blast Radius", category: "platform" },
    { id: "report", label: "Unified Diagnostic Report", category: "platform" },
    { id: "interop", label: "Interoperability Inspector", category: "governance" },
    { id: "proof", label: "Proof & Evaluation", category: "governance" },
  ];

  if (features.FEATURE_HITL) {
    platformNavItems.push({
      id: "hitl",
      label: "HITL Approvals",
      category: "remediation",
      requiredPermission: "approve_remediation",
      badge: "Guarded",
    });
  }

  if (features.FEATURE_REMEDIATION_SIM) {
    platformNavItems.push({
      id: "simulated_remediation",
      label: "Simulated Remediation",
      category: "remediation",
      requiredPermission: "create_remediation_proposals",
      badge: "Sandbox",
    });
  }

  if (features.FEATURE_RESUME) {
    platformNavItems.push({
      id: "sessions",
      label: "Sessions & Resume",
      category: "platform",
    });
  }

  platformNavItems.push({
    id: "mcp",
    label: "MCP Tool Catalog",
    category: "governance",
    badge: "v1.0",
  });

  const wsStatusColor =
    wsStatus === "connected"
      ? "bg-[#5E7A6A] border-[#5E7A6A]/40"
      : wsStatus === "connecting"
      ? "bg-[#A08A5B] border-[#A08A5B]/40"
      : "bg-[#9A5B5B] border-[#9A5B5B]/40";

  return (
    <>
      {/* Mobile Backdrop */}
      {isMobileOpen && (
        <div
          onClick={onCloseMobile}
          className="fixed inset-0 bg-[#000000]/40 z-40 lg:hidden"
        />
      )}

      <aside
        className={`fixed lg:static top-0 bottom-0 left-0 z-50 w-72 bg-[#FFFFFF] dark:bg-[#161618] border-r border-[#E5E5E3] dark:border-[#2A2A2D] flex flex-col font-mono transition-transform duration-200 ease-in-out ${
          isMobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        }`}
      >
        {/* Brand Header */}
        <div className="p-4 border-b border-[#E5E5E3] dark:border-[#2A2A2D] flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-4 h-4 bg-[#475569]"></div>
            <div>
              <div className="text-xs font-bold uppercase tracking-wider text-[#111111] dark:text-[#EDEDEA]">
                NetCoop AI
              </div>
              <div className="text-[10px] text-[#6B6B66] dark:text-[#888884]">
                Enterprise RBAC Platform
              </div>
            </div>
          </div>
          <button
            onClick={onCloseMobile}
            className="lg:hidden text-xs text-[#6B6B66] hover:text-[#111111] dark:hover:text-[#EDEDEA]"
          >
            Close
          </button>
        </div>

        {/* Role Selector Card */}
        <div className="p-4 border-b border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10] space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#6B6B66] dark:text-[#888884]">
              Active User Role
            </span>
            <button
              onClick={() => setShowPermissions(!showPermissions)}
              className="text-[10px] text-[#475569] hover:underline"
            >
              {showPermissions ? "Hide Perms" : "Inspect Perms"}
            </button>
          </div>

          <div className="relative">
            <select
              value={currentRole}
              onChange={(e) => {
                const newRole = e.target.value as UserRole;
                onSelectRole(newRole);
                // Also jump to primary role view
                onSelectNav(`role_${newRole.replace("noc_operator", "noc").replace("network_", "")}`);
              }}
              aria-label="Select active user role"
              className="w-full p-2 bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D] text-xs font-mono font-semibold text-[#111111] dark:text-[#EDEDEA] focus:border-[#475569] outline-none"
            >
              <option value="noc_operator">NOC Operator</option>
              <option value="network_engineer">Network Engineer</option>
              <option value="network_admin">Network Administrator</option>
              <option value="security_analyst">Security Analyst</option>
              <option value="it_manager">IT Manager</option>
              <option value="platform_admin">Platform Administrator</option>
              <option value="auditor">Auditor / Compliance</option>
              <option value="helpdesk">Helpdesk Operator</option>
            </select>
          </div>

          <div className="text-[11px] text-[#6B6B66] dark:text-[#888884] leading-tight">
            {currentRoleDef.department}
          </div>

          {/* Expandable Permissions Breakdown */}
          {showPermissions && (
            <div className="pt-2 border-t border-[#E5E5E3] dark:border-[#2A2A2D] space-y-1 text-[10px]">
              <div className="font-semibold text-[#111111] dark:text-[#EDEDEA] uppercase">
                Active Permissions ({currentRoleDef.permissions.length}):
              </div>
              <div className="space-y-0.5">
                {[
                  "view_incidents",
                  "view_diagnostic_evidence",
                  "create_remediation_proposals",
                  "approve_remediation",
                  "execute_remediation",
                  "manage_network_devices",
                  "manage_platform_settings",
                  "view_audit_records",
                ].map((perm) => {
                  const has = hasPermission(currentRole, perm as Permission);
                  return (
                    <div key={perm} className="flex items-center justify-between">
                      <span className={has ? "text-[#111111] dark:text-[#EDEDEA]" : "text-[#6B6B66]/40 dark:text-[#888884]/40"}>
                        {perm}
                      </span>
                      <span className={`text-[9px] uppercase ${has ? "text-[#5E7A6A] font-bold" : "text-[#6B6B66]/40"}`}>
                        {has ? "Allowed" : "Denied"}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Scrollable Navigation Items */}
        <div className="flex-1 overflow-y-auto p-3 space-y-5">
          {/* Section: Role Specific Views */}
          <div className="space-y-1">
            <div className="px-2 text-[10px] font-bold uppercase tracking-wider text-[#6B6B66] dark:text-[#888884]">
              Role Dashboards
            </div>
            {roleNavItems.map((item) => {
              const isCurrentRoleMatch =
                (currentRole === "noc_operator" && item.navId === "role_noc") ||
                (currentRole === "network_engineer" && item.navId === "role_engineer") ||
                (currentRole === "network_admin" && item.navId === "role_admin") ||
                (currentRole === "security_analyst" && item.navId === "role_security") ||
                (currentRole === "it_manager" && item.navId === "role_it_manager") ||
                (currentRole === "platform_admin" && item.navId === "role_platform_admin") ||
                (currentRole === "auditor" && item.navId === "role_auditor") ||
                (currentRole === "helpdesk" && item.navId === "role_helpdesk");

              const isActive = activeNav === item.navId;

              return (
                <button
                  key={item.navId}
                  onClick={() => {
                    onSelectNav(item.navId);
                    onCloseMobile();
                  }}
                  className={`w-full text-left px-2.5 py-1.5 text-xs flex items-center justify-between border transition-all ${
                    isActive
                      ? "bg-[#FAFAF9] dark:bg-[#0F0F10] border-[#475569] font-bold text-[#111111] dark:text-[#EDEDEA]"
                      : "border-transparent text-[#6B6B66] dark:text-[#888884] hover:text-[#111111] dark:hover:text-[#EDEDEA] hover:border-[#E5E5E3] dark:hover:border-[#2A2A2D]"
                  }`}
                >
                  <span className="truncate">{item.label}</span>
                  {isCurrentRoleMatch && (
                    <span className="px-1.5 py-0.2 border border-[#475569] text-[9px] uppercase text-[#475569]">
                      Assigned
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          {/* Section: Platform Subsystems */}
          <div className="space-y-1">
            <div className="px-2 text-[10px] font-bold uppercase tracking-wider text-[#6B6B66] dark:text-[#888884]">
              Diagnostic Platform
            </div>
            {platformNavItems.map((item) => {
              const isActive = activeNav === item.id;
              const hasAccess = item.requiredPermission
                ? hasPermission(currentRole, item.requiredPermission)
                : true;

              return (
                <button
                  key={item.id}
                  onClick={() => {
                    onSelectNav(item.id);
                    onCloseMobile();
                  }}
                  className={`w-full text-left px-2.5 py-1.5 text-xs flex items-center justify-between border transition-all ${
                    isActive
                      ? "bg-[#FAFAF9] dark:bg-[#0F0F10] border-[#475569] font-bold text-[#111111] dark:text-[#EDEDEA]"
                      : "border-transparent text-[#6B6B66] dark:text-[#888884] hover:text-[#111111] dark:hover:text-[#EDEDEA] hover:border-[#E5E5E3] dark:hover:border-[#2A2A2D]"
                  }`}
                >
                  <span className="truncate">{item.label}</span>
                  {item.badge && (
                    <span
                      className={`px-1.5 py-0.2 border text-[9px] uppercase ${
                        hasAccess
                          ? "border-[#5E7A6A] text-[#5E7A6A]"
                          : "border-[#A08A5B] text-[#A08A5B]"
                      }`}
                    >
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* System & Connection Status Footer */}
        <div className="p-3 border-t border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10] space-y-2 text-[10px]">
          <div className="flex items-center justify-between">
            <span className="text-[#6B6B66] dark:text-[#888884] uppercase">Live Stream:</span>
            <div className="flex items-center gap-1.5 font-bold">
              <span className={`w-2 h-2 rounded-full border ${wsStatusColor}`}></span>
              <span className="uppercase text-[#111111] dark:text-[#EDEDEA]">{wsStatus}</span>
            </div>
          </div>

          <div className="flex items-center justify-between text-[#6B6B66] dark:text-[#888884]">
            <span>Active Fabric:</span>
            <span className="font-semibold text-[#111111] dark:text-[#EDEDEA]">iit-bbs-campus</span>
          </div>

          <div className="flex items-center justify-between text-[#6B6B66] dark:text-[#888884]">
            <span>RBAC Policy:</span>
            <span className="text-[#5E7A6A] font-semibold uppercase">Strict Enforced</span>
          </div>
        </div>
      </aside>
    </>
  );
};

