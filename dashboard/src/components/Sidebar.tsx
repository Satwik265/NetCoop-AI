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
  onSelectRole?: (role: UserRole) => void;
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
  activeNav,
  onSelectNav,
  wsStatus,
  features,
  isMobileOpen,
  onCloseMobile,
}) => {
  const [showPermissions, setShowPermissions] = useState<boolean>(false);
  const currentRoleDef = ROLE_DEFINITIONS[currentRole] || ROLE_DEFINITIONS["noc_operator"];

  const allRoleNavItems: Array<{ roleId: UserRole; label: string; navId: string }> = [
    { roleId: "platform_admin", label: "Platform SRE / Admin", navId: "role_platform_admin" },
    { roleId: "network_admin", label: "Network Administrator", navId: "role_admin" },
    { roleId: "network_engineer", label: "Network Engineer", navId: "role_engineer" },
    { roleId: "helpdesk", label: "Helpdesk Support", navId: "role_helpdesk" },
    { roleId: "noc_operator", label: "NOC Operations", navId: "role_noc" },
    { roleId: "security_analyst", label: "Security Analyst", navId: "role_security" },
    { roleId: "it_manager", label: "IT Management", navId: "role_it_manager" },
    { roleId: "auditor", label: "Auditor & Compliance", navId: "role_auditor" },
  ];

  // RBAC isolation: Only platform_admin can see multiple role dashboards in sidebar navigation
  const visibleRoleNavItems =
    currentRole === "platform_admin"
      ? allRoleNavItems
      : allRoleNavItems.filter((item) => item.roleId === currentRole);

  const platformNavItems: NavItem[] = [];

  // Non-technical Helpdesk role does not access diagnostic/remediation subsystems
  if (currentRole !== "helpdesk") {
    platformNavItems.push(
      { id: "workspace", label: "Consensus Workspace", category: "platform" },
      { id: "topology", label: "Topology & Blast Radius", category: "platform" },
      { id: "report", label: "Unified Diagnostic Report", category: "platform" },
      { id: "interop", label: "Interoperability Inspector", category: "governance" },
      { id: "proof", label: "Proof & Evaluation", category: "governance" }
    );

    if (features.FEATURE_HITL && hasPermission(currentRole, "approve_remediation")) {
      platformNavItems.push({
        id: "hitl",
        label: "HITL Approvals",
        category: "remediation",
        requiredPermission: "approve_remediation",
        badge: "Guarded",
      });
    }

    if (features.FEATURE_REMEDIATION_SIM && hasPermission(currentRole, "create_remediation_proposals")) {
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
  }

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

        {/* Verified Assigned Role Card (No client-side unauthorized switching) */}
        <div className="p-4 border-b border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10] space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#6B6B66] dark:text-[#888884]">
              Authorized User Role
            </span>
            <button
              onClick={() => setShowPermissions(!showPermissions)}
              className="text-[10px] text-[#475569] hover:underline"
            >
              {showPermissions ? "Hide Perms" : "Inspect Perms"}
            </button>
          </div>

          <div className="p-2.5 bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D]">
            <div className="text-xs font-bold text-[#111111] dark:text-[#EDEDEA] flex items-center justify-between">
              <span>{currentRoleDef.title}</span>
              <span className="text-[9px] uppercase px-1.5 py-0.5 border border-[#5E7A6A] text-[#5E7A6A]">
                Active
              </span>
            </div>
            <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] mt-1">
              {currentRoleDef.department}
            </div>
          </div>

          {/* Expandable Permissions Breakdown */}
          {showPermissions && (
            <div className="pt-2 border-t border-[#E5E5E3] dark:border-[#2A2A2D] space-y-1 text-[10px]">
              <div className="font-semibold text-[#111111] dark:text-[#EDEDEA] uppercase">
                Active Permissions ({currentRoleDef.permissions.length}):
              </div>
              <div className="space-y-0.5 max-h-36 overflow-y-auto pr-1">
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
              {currentRole === "platform_admin" ? "All Role Dashboards" : "Primary Workspace"}
            </div>
            {visibleRoleNavItems.map((item) => {
              const isCurrentRoleMatch = item.roleId === currentRole;
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

          {/* Section: Platform Subsystems (Hidden for Helpdesk) */}
          {platformNavItems.length > 0 && (
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
                    disabled={!hasAccess}
                    onClick={() => {
                      if (hasAccess) {
                        onSelectNav(item.id);
                        onCloseMobile();
                      }
                    }}
                    className={`w-full text-left px-2.5 py-1.5 text-xs flex items-center justify-between border transition-all ${
                      isActive
                        ? "bg-[#FAFAF9] dark:bg-[#0F0F10] border-[#475569] font-bold text-[#111111] dark:text-[#EDEDEA]"
                        : hasAccess
                        ? "border-transparent text-[#6B6B66] dark:text-[#888884] hover:text-[#111111] dark:hover:text-[#EDEDEA] hover:border-[#E5E5E3] dark:hover:border-[#2A2A2D]"
                        : "border-transparent text-[#6B6B66]/30 dark:text-[#888884]/30 cursor-not-allowed"
                    }`}
                  >
                    <span className="truncate">{item.label}</span>
                    <div className="flex items-center gap-1.5">
                      {item.badge && (
                        <span className="px-1.5 py-0.2 border border-[#E5E5E3] dark:border-[#2A2A2D] text-[9px] text-[#6B6B66] dark:text-[#888884]">
                          {item.badge}
                        </span>
                      )}
                      {!hasAccess && (
                        <span className="text-[9px] uppercase text-[#9A5B5B] border border-[#9A5B5B]/30 px-1">
                          Locked
                        </span>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer: Connection Status & Version */}
        <div className="p-3 border-t border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10] text-[10px] space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="text-[#6B6B66] dark:text-[#888884]">WebSocket Bus:</span>
            <div className="flex items-center gap-1.5">
              <span className={`w-2 h-2 rounded-full border ${wsStatusColor}`}></span>
              <span className="capitalize font-semibold text-[#111111] dark:text-[#EDEDEA]">
                {wsStatus}
              </span>
            </div>
          </div>
          <div className="flex items-center justify-between text-[#6B6B66] dark:text-[#888884]">
            <span>Protocol:</span>
            <span className="font-semibold text-[#111111] dark:text-[#EDEDEA]">v1.0 (Signed)</span>
          </div>
        </div>
      </aside>
    </>
  );
};
