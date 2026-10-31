import React, { useState } from "react";
import { UnifiedDiagnosticReport } from "../../types/protocol";

interface HelpdeskViewProps {
  report: UnifiedDiagnosticReport | null;
  onNavigateToIncidents?: () => void;
}

interface SupportTicket {
  ticket_id: string;
  user_name: string;
  department: string;
  location: string;
  priority: "critical" | "high" | "normal" | "low";
  status: "open" | "in_progress" | "escalated" | "resolved";
  incident_id: string;
  summary: string;
  created_at: string;
  assigned_agent: string;
}

export const HelpdeskView: React.FC<HelpdeskViewProps> = ({ report }) => {
  const [tickets, setTickets] = useState<SupportTicket[]>([
    {
      ticket_id: "TICK-4091",
      user_name: "Dr. Arvind Ramesh",
      department: "Dept of Computer Science",
      location: "Academic Complex B - 3rd Floor",
      priority: "critical",
      status: "in_progress",
      incident_id: report?.incident_id || "INC-2026-0310-01",
      summary: "Lab workstations unable to reach external code repositories via gateway leaf switch.",
      created_at: "14 mins ago",
      assigned_agent: "Tier-1 Helpdesk",
    },
    {
      ticket_id: "TICK-4089",
      user_name: "Hostel Warden Office",
      department: "Student Affairs",
      location: "Hostel 4 - South Wing",
      priority: "high",
      status: "open",
      incident_id: report?.incident_id || "INC-2026-0310-01",
      summary: "Intermittent Wi-Fi disconnections across 2nd and 3rd floor resident rooms.",
      created_at: "28 mins ago",
      assigned_agent: "Tier-1 Helpdesk",
    },
    {
      ticket_id: "TICK-4084",
      user_name: "Finance Accounts Desk",
      department: "Administration",
      location: "Central Admin Block - Room 104",
      priority: "normal",
      status: "resolved",
      incident_id: "INC-2026-0309-04",
      summary: "Payment portal timed out during batch transaction run.",
      created_at: "1 hour ago",
      assigned_agent: "M. Fernandes",
    },
    {
      ticket_id: "TICK-4078",
      user_name: "Library Digital Catalog",
      department: "Library Services",
      location: "Main Library - Level 1",
      priority: "low",
      status: "resolved",
      incident_id: "INC-2026-0309-02",
      summary: "OPAC kiosk barcode scanner IP conflict resolved after DHCP lease renewal.",
      created_at: "3 hours ago",
      assigned_agent: "P. Sharma",
    },
  ]);

  const [filterPriority, setFilterPriority] = useState<string>("all");
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [selectedTicket, setSelectedTicket] = useState<SupportTicket | null>(tickets[0]);
  const [escalationNote, setEscalationNote] = useState<string>("");
  const [escalatedFeedback, setEscalatedFeedback] = useState<string | null>(null);
  const [copiedBulletin, setCopiedBulletin] = useState<boolean>(false);

  // Derive plain-language bulletin from current diagnostic report or fallback
  const getPlainLanguageBulletin = () => {
    if (!report || report.status === "insufficient_evidence") {
      return "Network engineers are currently monitoring campus connectivity. No major systemic service outages are verified at this time. Standard diagnostic workflows are in progress.";
    }

    const cause = report.probable_cause || "a localized network connectivity anomaly";
    const affected = report.affected_devices.length > 0 ? report.affected_devices.join(", ") : "core campus switches";
    const confidencePct = Math.round(report.confidence * 100);

    return `SERVICE ADVISORY: Network operations has detected an operational issue (${cause}) impacting infrastructure components (${affected}). Automated diagnostic confidence is at ${confidencePct}%. Engineering personnel have been dispatched to apply corrective routing and hardware validations. End users in affected zones may experience intermittent connectivity or elevated latency during this window. Estimated update within 15 minutes.`;
  };

  const handleCopyBulletin = () => {
    navigator.clipboard.writeText(getPlainLanguageBulletin());
    setCopiedBulletin(true);
    setTimeout(() => setCopiedBulletin(false), 2500);
  };

  const handleEscalateTicket = (ticketId: string) => {
    if (!escalationNote.trim()) return;
    setTickets((prev) =>
      prev.map((t) =>
        t.ticket_id === ticketId
          ? { ...t, status: "escalated", assigned_agent: "Tier-2 Infrastructure Engineering" }
          : t
      )
    );
    setEscalatedFeedback(`Ticket ${ticketId} escalated to Tier-2 Engineering with note: "${escalationNote}"`);
    setEscalationNote("");
    setTimeout(() => setEscalatedFeedback(null), 4000);
  };

  const filteredTickets = tickets.filter((t) => {
    if (filterPriority !== "all" && t.priority !== filterPriority) return false;
    if (searchTerm) {
      const q = searchTerm.toLowerCase();
      return (
        t.ticket_id.toLowerCase().includes(q) ||
        t.user_name.toLowerCase().includes(q) ||
        t.location.toLowerCase().includes(q) ||
        t.summary.toLowerCase().includes(q)
      );
    }
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Role Scope & Permission Boundary Banner */}
      <div className="p-4 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-[#111111] dark:text-[#EDEDEA]">
              Helpdesk Operator Workspace
            </span>
            <span className="px-2 py-0.5 border border-[#5E7A6A] text-[#5E7A6A] bg-[#5E7A6A]/10 text-[10px] font-mono uppercase">
              Triage & Client Support
            </span>
          </div>
          <p className="text-xs text-[#6B6B66] dark:text-[#888884] font-mono mt-1">
            Read-only diagnostic visibility and end-user ticket orchestration. Privileged remediation execution and device mutation are restricted to Tier-2/3 Network Engineering.
          </p>
        </div>

        <div className="flex items-center gap-4 text-xs font-mono text-right shrink-0">
          <div>
            <div className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">Open Tickets</div>
            <div className="text-lg font-bold text-[#111111] dark:text-[#EDEDEA]">
              {tickets.filter((t) => t.status === "open" || t.status === "in_progress").length}
            </div>
          </div>
          <div className="border-l border-[#E5E5E3] dark:border-[#2A2A2D] pl-4">
            <div className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">Escalated</div>
            <div className="text-lg font-bold text-[#A08A5B]">
              {tickets.filter((t) => t.status === "escalated").length}
            </div>
          </div>
        </div>
      </div>

      {/* Plain Language Client Bulletin Section */}
      <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D] p-5 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-[#111111] dark:text-[#EDEDEA]">
              Plain-Language Incident Advisory Bulletin
            </span>
            <span className="text-[10px] font-mono text-[#6B6B66] dark:text-[#888884]">
              For End-User / Faculty Communications
            </span>
          </div>
          <button
            onClick={handleCopyBulletin}
            className="px-3 py-1 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] hover:border-[#475569] text-xs font-mono text-[#111111] dark:text-[#EDEDEA] transition-all"
          >
            {copiedBulletin ? "Copied to Clipboard" : "Copy Bulletin"}
          </button>
        </div>

        <div className="p-3 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] text-xs font-mono text-[#111111] dark:text-[#EDEDEA] leading-relaxed">
          {getPlainLanguageBulletin()}
        </div>

        <div className="flex items-center justify-between text-[10px] font-mono text-[#6B6B66] dark:text-[#888884] pt-1">
          <span>Target Incident: {report?.incident_id || "Active Telemetry Stream"}</span>
          <span>Security & Compliance Notice: Technical hostnames, raw IP blocks, and vendor vulnerability vectors omitted for client distribution.</span>
        </div>
      </div>

      {/* Escalation Notification Toast */}
      {escalatedFeedback && (
        <div className="p-3 bg-[#5E7A6A]/10 border border-[#5E7A6A]/30 text-xs font-mono text-[#5E7A6A]">
          {escalatedFeedback}
        </div>
      )}

      {/* Main Grid: Ticket Queue & Ticket Details */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Ticket List (2 Cols) */}
        <div className="lg:col-span-2 bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D] p-5 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono font-bold uppercase tracking-wider text-[#111111] dark:text-[#EDEDEA]">
                Support Tickets Queue
              </span>
              <span className="text-[10px] font-mono text-[#6B6B66] dark:text-[#888884]">
                ({filteredTickets.length} items)
              </span>
            </div>

            <div className="flex items-center gap-2">
              <input
                type="text"
                placeholder="Search ticket, user, location..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="px-2.5 py-1 text-xs font-mono bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] text-[#111111] dark:text-[#EDEDEA] placeholder-[#6B6B66] focus:border-[#475569] outline-none"
              />
              <select
                value={filterPriority}
                onChange={(e) => setFilterPriority(e.target.value)}
                aria-label="Filter tickets by priority"
                className="px-2 py-1 text-xs font-mono bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] text-[#111111] dark:text-[#EDEDEA] outline-none"
              >
                <option value="all">All Priorities</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="normal">Normal</option>
                <option value="low">Low</option>
              </select>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left font-mono text-xs">
              <thead>
                <tr className="border-b border-[#E5E5E3] dark:border-[#2A2A2D] text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">
                  <th className="pb-2">Ticket ID</th>
                  <th className="pb-2">User / Dept</th>
                  <th className="pb-2">Location</th>
                  <th className="pb-2">Priority</th>
                  <th className="pb-2">Status</th>
                  <th className="pb-2">Time</th>
                  <th className="pb-2 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E5E5E3]/60 dark:divide-[#2A2A2D]/60">
                {filteredTickets.map((t) => {
                  const isSelected = selectedTicket?.ticket_id === t.ticket_id;
                  const priorityClass =
                    t.priority === "critical"
                      ? "text-[#9A5B5B] border-[#9A5B5B]/30 bg-[#9A5B5B]/10"
                      : t.priority === "high"
                      ? "text-[#A08A5B] border-[#A08A5B]/30 bg-[#A08A5B]/10"
                      : "text-[#6B6B66] border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10]";

                  const statusClass =
                    t.status === "resolved"
                      ? "text-[#5E7A6A] border-[#5E7A6A]/30"
                      : t.status === "escalated"
                      ? "text-[#A08A5B] border-[#A08A5B]/30"
                      : "text-[#111111] dark:text-[#EDEDEA] border-[#E5E5E3] dark:border-[#2A2A2D]";

                  return (
                    <tr
                      key={t.ticket_id}
                      onClick={() => setSelectedTicket(t)}
                      className={`hover:bg-[#FAFAF9] dark:hover:bg-[#0F0F10] cursor-pointer transition-colors ${
                        isSelected ? "bg-[#FAFAF9] dark:bg-[#0F0F10]" : ""
                      }`}
                    >
                      <td className="py-2.5 font-bold text-[#111111] dark:text-[#EDEDEA]">
                        {t.ticket_id}
                      </td>
                      <td className="py-2.5">
                        <div className="text-[#111111] dark:text-[#EDEDEA]">{t.user_name}</div>
                        <div className="text-[10px] text-[#6B6B66] dark:text-[#888884]">{t.department}</div>
                      </td>
                      <td className="py-2.5 text-[#6B6B66] dark:text-[#888884]">{t.location}</td>
                      <td className="py-2.5">
                        <span className={`px-1.5 py-0.5 border text-[10px] uppercase font-semibold ${priorityClass}`}>
                          {t.priority}
                        </span>
                      </td>
                      <td className="py-2.5">
                        <span className={`px-1.5 py-0.5 border text-[10px] uppercase font-mono ${statusClass}`}>
                          {t.status.replace("_", " ")}
                        </span>
                      </td>
                      <td className="py-2.5 text-[10px] text-[#6B6B66] dark:text-[#888884]">{t.created_at}</td>
                      <td className="py-2.5 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedTicket(t);
                          }}
                          className="px-2 py-0.5 border border-[#E5E5E3] dark:border-[#2A2A2D] hover:border-[#475569] text-[10px]"
                        >
                          Details
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Selected Ticket Detail & Escalation Drawer (1 Col) */}
        <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D] p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-[#E5E5E3] dark:border-[#2A2A2D] pb-3">
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-[#111111] dark:text-[#EDEDEA]">
              Ticket Details
            </span>
            {selectedTicket && (
              <span className="text-[10px] font-mono text-[#6B6B66] dark:text-[#888884]">
                {selectedTicket.ticket_id}
              </span>
            )}
          </div>

          {selectedTicket ? (
            <div className="space-y-4 text-xs font-mono">
              <div>
                <div className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">User & Department</div>
                <div className="font-bold text-[#111111] dark:text-[#EDEDEA] mt-0.5">
                  {selectedTicket.user_name}
                </div>
                <div className="text-[11px] text-[#6B6B66] dark:text-[#888884]">
                  {selectedTicket.department} ({selectedTicket.location})
                </div>
              </div>

              <div>
                <div className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">Reported Issue</div>
                <div className="mt-1 p-2.5 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] text-[#111111] dark:text-[#EDEDEA] leading-relaxed">
                  {selectedTicket.summary}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 pt-1">
                <div>
                  <div className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">Assigned Handler</div>
                  <div className="font-semibold text-[#111111] dark:text-[#EDEDEA] mt-0.5">
                    {selectedTicket.assigned_agent}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">Linked Incident</div>
                  <div className="font-semibold text-[#111111] dark:text-[#EDEDEA] mt-0.5">
                    {selectedTicket.incident_id}
                  </div>
                </div>
              </div>

              {/* Escalation to Tier-2 Engineering */}
              <div className="pt-3 border-t border-[#E5E5E3] dark:border-[#2A2A2D] space-y-2">
                <div className="text-[10px] uppercase font-bold text-[#111111] dark:text-[#EDEDEA]">
                  Escalate to Tier-2 Infrastructure
                </div>
                <p className="text-[11px] text-[#6B6B66] dark:text-[#888884]">
                  Forward ticket with field diagnostic context to Senior Network Engineering.
                </p>
                <textarea
                  rows={3}
                  value={escalationNote}
                  onChange={(e) => setEscalationNote(e.target.value)}
                  placeholder="Provide technical handoff notes, impacted switches, or room count..."
                  className="w-full p-2 text-xs font-mono bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] text-[#111111] dark:text-[#EDEDEA] focus:border-[#475569] outline-none"
                />
                <button
                  onClick={() => handleEscalateTicket(selectedTicket.ticket_id)}
                  disabled={!escalationNote.trim() || selectedTicket.status === "escalated"}
                  className="w-full py-1.5 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] hover:border-[#475569] disabled:opacity-40 text-xs font-mono font-semibold text-[#111111] dark:text-[#EDEDEA] transition-all"
                >
                  {selectedTicket.status === "escalated" ? "Already Escalated to Tier-2" : "Submit Escalation"}
                </button>
              </div>

              {/* Guardrail Reminder */}
              <div className="p-2.5 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] text-[10px] text-[#6B6B66] dark:text-[#888884] space-y-1">
                <div className="font-semibold text-[#111111] dark:text-[#EDEDEA] uppercase">
                  Remediation Guardrail Active
                </div>
                <p>
                  Direct interface flaps, ACL modification, and config rollbacks cannot be triggered from this view. Use the escalation workflow above to hand off to certified network engineers.
                </p>
              </div>
            </div>
          ) : (
            <div className="text-center py-8 text-xs font-mono text-[#6B6B66] dark:text-[#888884]">
              Select a ticket to review triage notes and escalation status.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

