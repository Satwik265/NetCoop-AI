import React, { useState } from "react";
import { UnifiedDiagnosticReport } from "../../types/protocol";

interface HelpdeskViewProps {
  report: UnifiedDiagnosticReport | null;
  onNavigateToIncidents?: () => void;
  onNavigate?: (navId: string) => void;
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
      incident_id: report?.incident_id || "inc-link-congestion-42",
      summary: "Lab workstations experiencing heavy buffering and slow external code repository access.",
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
      incident_id: report?.incident_id || "inc-link-congestion-42",
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
  const [escalatedFeedback, setEscalatedFeedback] = useState<string | null>(null);
  const [copiedBulletin, setCopiedBulletin] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<"overview" | "bulletin" | "tickets" | "guide">("overview");

  // Derive plain-language explanations from actual technical reports
  const getPlainLanguageCause = () => {
    if (!report || !report.probable_cause) {
      return "Network traffic congestion causing temporary slow access.";
    }
    const pc = report.probable_cause.toLowerCase();
    if (pc.includes("saturation") || pc.includes("congestion") || pc.includes("queue")) {
      return "Heavy network traffic on a main campus communication link, causing data to queue and slow down.";
    }
    if (pc.includes("bgp") || pc.includes("route")) {
      return "Internet routing redirection causing external web connections to take longer paths.";
    }
    if (pc.includes("radio") || pc.includes("wifi")) {
      return "Wireless radio frequency congestion in high-density hostel areas.";
    }
    return report.summary || "A localized network performance slowdown is under investigation.";
  };

  const getPlainLanguageLocation = () => {
    if (!report || !report.affected_devices || report.affected_devices.length === 0) {
      return "Academic Complex B & Hostel 4 (Campus Core Network)";
    }
    const devs = report.affected_devices.join(", ");
    return `${devs} (Academic Complex B & Hostel 4)`;
  };

  // Generate plain-language customer advisory bulletin from actual diagnosis results
  const getPlainLanguageBulletin = () => {
    const cause = getPlainLanguageCause();
    const location = getPlainLanguageLocation();
    const statusText = report?.status === "diagnosed" ? "Diagnosed by AI diagnostic assistant" : "Investigating";

    return `CAMPUS IT ADVISORY:
Issue: ${cause}
Affected Areas: ${location}
Status: ${statusText} - Network Infrastructure Engineers have been dispatched.
What Users Should Expect: Web pages and downloads may load more slowly than usual. Critical campus portals remain reachable.
Expected Next Update: Within 15 minutes.
Support Action: No action is required by end users. For emergency escalations, contact the IT Helpdesk at ext 4000.`;
  };

  const handleCopyBulletin = () => {
    navigator.clipboard.writeText(getPlainLanguageBulletin());
    setCopiedBulletin(true);
    setTimeout(() => setCopiedBulletin(false), 2500);
  };

  const handleEscalateTicket = (ticketId: string) => {
    setTickets((prev) =>
      prev.map((t) =>
        t.ticket_id === ticketId
          ? { ...t, status: "escalated", assigned_agent: "Tier-2 Network Engineering" }
          : t
      )
    );
    setEscalatedFeedback(`Ticket ${ticketId} escalated to Tier-2 Network Engineering.`);
    setTimeout(() => setEscalatedFeedback(null), 3000);
  };

  const filteredTickets = tickets.filter((t) => {
    const matchesPriority = filterPriority === "all" || t.priority === filterPriority;
    const matchesSearch =
      t.user_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      t.location.toLowerCase().includes(searchTerm.toLowerCase()) ||
      t.summary.toLowerCase().includes(searchTerm.toLowerCase()) ||
      t.ticket_id.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesPriority && matchesSearch;
  });

  const openTicketsCount = tickets.filter((t) => t.status === "open" || t.status === "in_progress").length;

  return (
    <div className="space-y-6 font-mono text-xs">
      {/* Top Banner: Campus Service Status (Level 1 Summary) */}
      <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 bg-[#A08A5B]"></span>
              <span className="text-[10px] text-[#6B6B66] dark:text-[#888884] uppercase tracking-wider font-bold">
                Helpdesk Support &amp; Customer Incident Center
              </span>
            </div>
            <div className="text-base font-bold text-[#111111] dark:text-[#EDEDEA] mt-1">
              Campus Network Status: Service Notice Active
            </div>
            <p className="mt-1 text-[11px] text-[#6B6B66] dark:text-[#888884] leading-relaxed">
              Simplified incident tracking for end-user support staff. Technical networking metrics are automatically translated into plain language.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleCopyBulletin}
              className="px-3 py-1.5 border border-[#111111] dark:border-[#EDEDEA] bg-[#111111] dark:bg-[#EDEDEA] text-[#FAFAF9] dark:text-[#0F0F10] uppercase text-[10px] font-semibold hover:opacity-90 transition-opacity"
            >
              {copiedBulletin ? "COPIED BULLETIN TO CLIPBOARD" : "COPY USER ADVISORY BULLETIN"}
            </button>
          </div>
        </div>

        {escalatedFeedback && (
          <div className="mt-4 p-2.5 bg-[#5E7A6A]/10 border border-[#5E7A6A]/30 text-[#5E7A6A] text-[11px]">
            {escalatedFeedback}
          </div>
        )}

        {/* Navigation Tabs */}
        <div className="mt-6 flex flex-wrap items-center gap-2 border-t border-[#E5E5E3] dark:border-[#2A2A2D] pt-4">
          <button
            onClick={() => setActiveTab("overview")}
            className={`px-3 py-1 border text-[11px] uppercase font-semibold transition-colors ${
              activeTab === "overview"
                ? "border-[#111111] dark:border-[#EDEDEA] bg-[#111111] dark:bg-[#EDEDEA] text-[#FAFAF9] dark:text-[#0F0F10]"
                : "border-[#E5E5E3] dark:border-[#2A2A2D] text-[#6B6B66] dark:text-[#888884] hover:text-[#111111] dark:hover:text-[#EDEDEA]"
            }`}
          >
            Service Status &amp; Impact
          </button>
          <button
            onClick={() => setActiveTab("bulletin")}
            className={`px-3 py-1 border text-[11px] uppercase font-semibold transition-colors ${
              activeTab === "bulletin"
                ? "border-[#111111] dark:border-[#EDEDEA] bg-[#111111] dark:bg-[#EDEDEA] text-[#FAFAF9] dark:text-[#0F0F10]"
                : "border-[#E5E5E3] dark:border-[#2A2A2D] text-[#6B6B66] dark:text-[#888884] hover:text-[#111111] dark:hover:text-[#EDEDEA]"
            }`}
          >
            What To Tell Users (Bulletin)
          </button>
          <button
            onClick={() => setActiveTab("tickets")}
            className={`px-3 py-1 border text-[11px] uppercase font-semibold transition-colors ${
              activeTab === "tickets"
                ? "border-[#111111] dark:border-[#EDEDEA] bg-[#111111] dark:bg-[#EDEDEA] text-[#FAFAF9] dark:text-[#0F0F10]"
                : "border-[#E5E5E3] dark:border-[#2A2A2D] text-[#6B6B66] dark:text-[#888884] hover:text-[#111111] dark:hover:text-[#EDEDEA]"
            }`}
          >
            Support Tickets Queue ({openTicketsCount} Open)
          </button>
          <button
            onClick={() => setActiveTab("guide")}
            className={`px-3 py-1 border text-[11px] uppercase font-semibold transition-colors ${
              activeTab === "guide"
                ? "border-[#111111] dark:border-[#EDEDEA] bg-[#111111] dark:bg-[#EDEDEA] text-[#FAFAF9] dark:text-[#0F0F10]"
                : "border-[#E5E5E3] dark:border-[#2A2A2D] text-[#6B6B66] dark:text-[#888884] hover:text-[#111111] dark:hover:text-[#EDEDEA]"
            }`}
          >
            Helpdesk Caller Script
          </button>
        </div>
      </div>

      {/* TAB 1: SERVICE STATUS & PLAIN-LANGUAGE IMPACT */}
      {activeTab === "overview" && (
        <div className="space-y-6">
          {/* Plain-Language Status Cards (10 Core Screen Elements) */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-4">
              <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] uppercase">1. Current Service Status</div>
              <div className="mt-1 text-base font-bold text-[#A08A5B] uppercase">
                SLOW SPEEDS REPORTED
              </div>
              <div className="mt-1 text-[10px] text-[#6B6B66]">Connectivity Still Reachable</div>
            </div>

            <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-4">
              <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] uppercase">2. Affected Locations</div>
              <div className="mt-1 text-base font-bold text-[#111111] dark:text-[#EDEDEA]">
                Academic Complex B
              </div>
              <div className="mt-1 text-[10px] text-[#6B6B66]">&amp; Hostel 4 Resident Rooms</div>
            </div>

            <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-4">
              <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] uppercase">3. Incident Severity</div>
              <div className="mt-1 text-base font-bold text-[#A08A5B] uppercase">
                MODERATE
              </div>
              <div className="mt-1 text-[10px] text-[#6B6B66]">Non-Critical Intermittent Delay</div>
            </div>

            <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-4">
              <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] uppercase">4. Expected Next Update</div>
              <div className="mt-1 text-base font-bold text-[#5E7A6A]">
                IN ~15 MINUTES
              </div>
              <div className="mt-1 text-[10px] text-[#6B6B66]">Automated Progress Check</div>
            </div>
          </div>

          {/* Plain-Language Incident Overview Card */}
          <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-5 space-y-3">
            <div className="flex items-center justify-between border-b border-[#E5E5E3] dark:border-[#2A2A2D] pb-3">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-[#111111] dark:text-[#EDEDEA]">
                What Is Happening Right Now?
              </h2>
              <span className="px-2 py-0.5 border border-[#5E7A6A] text-[#5E7A6A] text-[9px] uppercase font-bold">
                DIAGNOSED BY AI ASSISTANT
              </span>
            </div>

            <p className="text-[12px] text-[#111111] dark:text-[#EDEDEA] leading-relaxed">
              {getPlainLanguageCause()}
            </p>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-2 text-[10px]">
              <div className="p-2.5 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10]">
                <span className="text-[#6B6B66] uppercase block">Impacted Services:</span>
                <span className="font-semibold text-[#111111] dark:text-[#EDEDEA] mt-0.5 block">
                  Student &amp; Faculty Wi-Fi, Computer Science Lab Internet
                </span>
              </div>
              <div className="p-2.5 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10]">
                <span className="text-[#6B6B66] uppercase block">Estimated Impact:</span>
                <span className="font-semibold text-[#111111] dark:text-[#EDEDEA] mt-0.5 block">
                  ~150+ users experiencing slower browsing speeds
                </span>
              </div>
              <div className="p-2.5 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10]">
                <span className="text-[#6B6B66] uppercase block">Engineering Escalation:</span>
                <span className="font-semibold text-[#5E7A6A] mt-0.5 block">
                  Network Engineering On-Call Dispatched
                </span>
              </div>
            </div>
          </div>

          {/* Mandatory Capabilities Explained Simply (Read-Only) */}
          <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-5 space-y-4">
            <div className="border-b border-[#E5E5E3] dark:border-[#2A2A2D] pb-3">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-[#111111] dark:text-[#EDEDEA]">
                How NetCoop-AI Investigated This Incident
              </h2>
              <p className="text-[10px] text-[#6B6B66] dark:text-[#888884] mt-0.5">
                Understand the mandatory AI capabilities behind this incident status report.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-[11px]">
              <div className="p-3 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10] space-y-1">
                <span className="font-bold text-[#111111] dark:text-[#EDEDEA]">Multiple Collaborating AI Specialists</span>
                <p className="text-[10px] text-[#6B6B66] dark:text-[#888884]">
                  Several specialist AI programs (Traffic, Device Logs, Topology, Wireless) worked together in real time to isolate the issue.
                </p>
              </div>

              <div className="p-3 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10] space-y-1">
                <span className="font-bold text-[#111111] dark:text-[#EDEDEA]">Information Sharing &amp; Compatibility</span>
                <p className="text-[10px] text-[#6B6B66] dark:text-[#888884]">
                  Findings from each specialist were shared across standard message envelopes without loss of diagnostic precision.
                </p>
              </div>

              <div className="p-3 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10] space-y-1">
                <span className="font-bold text-[#111111] dark:text-[#EDEDEA]">Automated Investigation Workflow</span>
                <p className="text-[10px] text-[#6B6B66] dark:text-[#888884]">
                  The investigation followed a step-by-step workflow: Ingest &rarr; Analyze Signals &rarr; Correlate Causes &rarr; Generate Advisory.
                </p>
              </div>

              <div className="p-3 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10] space-y-1">
                <span className="font-bold text-[#111111] dark:text-[#EDEDEA]">Verified Network Data Quality</span>
                <p className="text-[10px] text-[#6B6B66] dark:text-[#888884]">
                  Sensor telemetry and switch counters were checked for completeness and confirmed valid before reaching conclusions.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: WHAT TO TELL USERS (BULLETIN ASSISTANT) */}
      {activeTab === "bulletin" && (
        <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-[#E5E5E3] dark:border-[#2A2A2D] pb-3">
            <div>
              <h2 className="text-xs font-semibold uppercase tracking-wider text-[#111111] dark:text-[#EDEDEA]">
                One-Click Customer Advisory Bulletin
              </h2>
              <p className="text-[10px] text-[#6B6B66] dark:text-[#888884] mt-0.5">
                Copy and paste this bulletin into campus emails, status portals, or customer support replies.
              </p>
            </div>
            <button
              onClick={handleCopyBulletin}
              className="px-3 py-1.5 border border-[#111111] dark:border-[#EDEDEA] bg-[#111111] dark:bg-[#EDEDEA] text-[#FAFAF9] dark:text-[#0F0F10] uppercase text-[10px] font-semibold hover:opacity-90 transition-opacity"
            >
              {copiedBulletin ? "COPIED TO CLIPBOARD" : "COPY BULLETIN TEXT"}
            </button>
          </div>

          <div className="p-4 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] font-mono text-[11px] leading-relaxed whitespace-pre-wrap text-[#111111] dark:text-[#EDEDEA]">
            {getPlainLanguageBulletin()}
          </div>
        </div>
      )}

      {/* TAB 3: SUPPORT TICKETS & INCIDENT TRIAGE */}
      {activeTab === "tickets" && (
        <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-[#E5E5E3] dark:border-[#2A2A2D] pb-3">
            <div>
              <h2 className="text-xs font-semibold uppercase tracking-wider text-[#111111] dark:text-[#EDEDEA]">
                Active User Support Tickets ({filteredTickets.length})
              </h2>
              <p className="text-[10px] text-[#6B6B66] dark:text-[#888884] mt-0.5">
                Review end-user reports, correlate with current network advisory, and escalate to Tier-2 Engineering.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="text"
                placeholder="Search tickets, names, locations..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] px-2 py-1 text-[10px] w-48"
              />
              <select
                value={filterPriority}
                onChange={(e) => setFilterPriority(e.target.value)}
                aria-label="Filter tickets by priority"
                className="bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] px-2 py-1 text-[10px]"
              >
                <option value="all">All Priorities</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="normal">Normal</option>
                <option value="low">Low</option>
              </select>
            </div>
          </div>

          <div className="space-y-3">
            {filteredTickets.map((t) => (
              <div
                key={t.ticket_id}
                className="p-3 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10] space-y-2"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-[#111111] dark:text-[#EDEDEA]">{t.ticket_id}</span>
                    <span className="text-[#6B6B66] font-semibold">{t.user_name} ({t.department})</span>
                    <span className="text-[10px] text-[#475569]">{t.location}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className={`px-1.5 py-0.2 border text-[9px] uppercase font-bold ${
                        t.priority === "critical"
                          ? "border-[#9A5B5B] text-[#9A5B5B]"
                          : t.priority === "high"
                          ? "border-[#A08A5B] text-[#A08A5B]"
                          : "border-[#475569] text-[#475569]"
                      }`}
                    >
                      {t.priority}
                    </span>
                    <span className="text-[10px] text-[#6B6B66]">{t.created_at}</span>
                  </div>
                </div>

                <p className="text-[11px] text-[#6B6B66] dark:text-[#888884]">{t.summary}</p>

                <div className="flex items-center justify-between pt-2 border-t border-[#E5E5E3] dark:border-[#2A2A2D] text-[10px]">
                  <span className="text-[#475569]">Assigned: {t.assigned_agent}</span>
                  {t.status !== "escalated" ? (
                    <button
                      onClick={() => handleEscalateTicket(t.ticket_id)}
                      className="px-2.5 py-1 border border-[#A08A5B] text-[#A08A5B] hover:bg-[#A08A5B]/10 uppercase font-semibold"
                    >
                      Escalate Ticket to Tier-2
                    </button>
                  ) : (
                    <span className="text-[#5E7A6A] font-bold uppercase">Escalated to Engineering</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 4: HELPDESK CALLER SCRIPT */}
      {activeTab === "guide" && (
        <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-5 space-y-4">
          <div className="border-b border-[#E5E5E3] dark:border-[#2A2A2D] pb-3">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-[#111111] dark:text-[#EDEDEA]">
              Helpdesk Operator Script for Inbound Inquiries
            </h2>
            <p className="text-[10px] text-[#6B6B66] dark:text-[#888884] mt-0.5">
              Standard script to answer student, researcher, and faculty calls during this incident window.
            </p>
          </div>

          <div className="space-y-3 text-[11px]">
            <div className="p-3 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10] space-y-1">
              <span className="font-bold text-[#111111] dark:text-[#EDEDEA]">Step 1: Acknowledge &amp; Validate Location</span>
              <p className="text-[#6B6B66] dark:text-[#888884]">
                "Thank you for reaching out to the IT Helpdesk. Are you calling from Academic Complex B or Hostel 4?"
              </p>
            </div>

            <div className="p-3 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10] space-y-1">
              <span className="font-bold text-[#111111] dark:text-[#EDEDEA]">Step 2: Provide Non-Technical Explanation</span>
              <p className="text-[#6B6B66] dark:text-[#888884]">
                "We are actively aware of a network slowdown impacting that area. Our AI diagnostics have isolated a congested core communication link, and network engineering is currently applying a traffic rebalance."
              </p>
            </div>

            <div className="p-3 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10] space-y-1">
              <span className="font-bold text-[#111111] dark:text-[#EDEDEA]">Step 3: Set Expectations &amp; Ticket Reference</span>
              <p className="text-[#6B6B66] dark:text-[#888884]">
                "No changes are needed on your device. We expect another status update within 15 minutes. May I have your name to link your report to incident {report?.incident_id || 'inc-link-congestion-42'}?"
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
