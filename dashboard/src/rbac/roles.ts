/**
 * Role-Based Access Control (RBAC) definitions and permission matrix for NetCoop-AI.
 */

export type UserRole =
  | "noc_operator"
  | "network_engineer"
  | "network_admin"
  | "security_analyst"
  | "it_manager"
  | "platform_admin"
  | "auditor"
  | "helpdesk";

export type Permission =
  | "view_incidents"
  | "edit_incident_assignments"
  | "view_diagnostic_evidence"
  | "create_remediation_proposals"
  | "approve_remediation"
  | "execute_remediation"
  | "view_audit_records"
  | "manage_platform_settings"
  | "manage_network_devices";

export interface RoleDefinition {
  id: UserRole;
  title: string;
  department: string;
  description: string;
  permissions: Permission[];
  primaryView: string;
  badgeClass: string;
}

export const ROLE_DEFINITIONS: Record<UserRole, RoleDefinition> = {
  noc_operator: {
    id: "noc_operator",
    title: "NOC Operator",
    department: "Network Operations Center",
    description: "Monitors live fabric health, active incident queues, device alerts, and triage escalations.",
    permissions: ["view_incidents", "edit_incident_assignments", "view_diagnostic_evidence"],
    primaryView: "noc",
    badgeClass: "border-[#475569] text-[#475569] bg-[#475569]/10",
  },
  network_engineer: {
    id: "network_engineer",
    title: "Network Engineer",
    department: "Network Infrastructure Engineering",
    description: "Performs technical root-cause investigation, inspects AI evidence chains, and runs simulated remediations.",
    permissions: [
      "view_incidents",
      "view_diagnostic_evidence",
      "create_remediation_proposals",
      "execute_remediation", // Simulation sandbox execution
    ],
    primaryView: "engineer",
    badgeClass: "border-[#5E7A6A] text-[#5E7A6A] bg-[#5E7A6A]/10",
  },
  network_admin: {
    id: "network_admin",
    title: "Network Administrator",
    department: "Systems & Infrastructure",
    description: "Manages physical and virtual device inventories, interface configurations, and maintenance schedules.",
    permissions: ["view_incidents", "manage_network_devices", "view_audit_records"],
    primaryView: "admin",
    badgeClass: "border-[#A08A5B] text-[#A08A5B] bg-[#A08A5B]/10",
  },
  security_analyst: {
    id: "security_analyst",
    title: "Security Analyst",
    department: "SecOps & Cyber Defense",
    description: "Investigates security-relevant anomalies, suspicious traffic spikes, and threat telemetry grounded in evidence.",
    permissions: ["view_incidents", "view_diagnostic_evidence", "view_audit_records"],
    primaryView: "security",
    badgeClass: "border-[#9A5B5B] text-[#9A5B5B] bg-[#9A5B5B]/10",
  },
  it_manager: {
    id: "it_manager",
    title: "IT Manager",
    department: "IT Leadership & Service Delivery",
    description: "Tracks SLA compliance, incident MTTR/MTTD trends, service availability, and team workload.",
    permissions: ["view_incidents", "view_audit_records"],
    primaryView: "it_manager",
    badgeClass: "border-[#475569] text-[#475569] bg-[#475569]/10",
  },
  platform_admin: {
    id: "platform_admin",
    title: "Platform Administrator",
    department: "Site Reliability & Platform Ops",
    description: "Monitors AI agent microservices, orchestrator checkpoints, API latency, and MCP tool health.",
    permissions: ["view_incidents", "manage_platform_settings", "view_audit_records"],
    primaryView: "platform_admin",
    badgeClass: "border-[#111111] dark:border-[#EDEDEA] text-[#111111] dark:text-[#EDEDEA] bg-[#FAFAF9] dark:bg-[#0F0F10]",
  },
  auditor: {
    id: "auditor",
    title: "Auditor / Compliance Officer",
    department: "Governance, Risk & Compliance",
    description: "Inspects immutable audit logs, operator rationales, executed commands, and rollback verification (strictly read-only).",
    permissions: ["view_incidents", "view_diagnostic_evidence", "view_audit_records"],
    primaryView: "auditor",
    badgeClass: "border-[#6B6B66] text-[#6B6B66] bg-[#6B6B66]/10",
  },
  helpdesk: {
    id: "helpdesk",
    title: "Helpdesk Operator",
    department: "User Support & Service Desk",
    description: "Triages user support tickets, views impacted campus buildings, and tracks incident resolution progress.",
    permissions: ["view_incidents", "edit_incident_assignments"],
    primaryView: "helpdesk",
    badgeClass: "border-[#5E7A6A] text-[#5E7A6A] bg-[#5E7A6A]/10",
  },
};

/**
 * Check if a role possesses a specific permission.
 */
export function hasPermission(role: UserRole, permission: Permission): boolean {
  const def = ROLE_DEFINITIONS[role];
  if (!def) return false;
  return def.permissions.includes(permission);
}

