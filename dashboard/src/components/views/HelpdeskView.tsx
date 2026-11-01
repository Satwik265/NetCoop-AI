import React, { useState, useEffect } from "react";
import { apiFetch } from "../../auth/AuthContext";
import { UnifiedDiagnosticReport } from "../../types/protocol";

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

export interface IncidentSummaryItem {
  incident_id: string;
  status: string;
  network_id?: string;
  created_at?: string;
  confidence?: number;
  probable_cause?: string;
}

interface HelpdeskViewProps {
  report: UnifiedDiagnosticReport | null;
  onNavigateToIncidents?: () => void;
  onNavigate?: (navId: string) => void;
}

export const HelpdeskView: React.FC<HelpdeskViewProps> = ({ report }) => {
  const [activeTab, setActiveTab] = useState<
    "overview" | "create_ticket" | "tickets" | "status" | "caller_guide"
  >("overview");

  const [tickets, setTickets] = useState<TicketItem[]>([]);
  const [incidents, setIncidents] = useState<IncidentSummaryItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Ticket creation form state
  const [title, setTitle] = useState<string>("");
  const [category, setCategory] = useState<string>("wifi");
  const [location, setLocation] = useState<string>("Hostel Block B");
  const [affectedService, setAffectedService] = useState<string>("Campus WiFi");
  const [description, setDescription] = useState<string>("");
  const [priority, setPriority] = useState<string>("high");
  const [contactInfo, setContactInfo] = useState<string>("");
  const [createMsg, setCreateMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [creating, setCreating] = useState<boolean>(false);

  // Filter and search state
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [filterPriority, setFilterPriority] = useState<string>("all");
  const [searchTerm, setSearchTerm] = useState<string>("");

  // Ticket detail / update drawer
  const [selectedTicket, setSelectedTicket] = useState<TicketItem | null>(null);
  const [updateStatus, setUpdateStatus] = useState<string>("");
  const [updateNotes, setUpdateNotes] = useState<string>("");
  const [updateMsg, setUpdateMsg] = useState<string | null>(null);
  const [updating, setUpdating] = useState<boolean>(false);

  // Advisory bulletin copy state
  const [copiedBulletin, setCopiedBulletin] = useState<boolean>(false);

  const fetchTicketsAndIncidents = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const [tickRes, incRes] = await Promise.all([
        apiFetch("/api/tickets"),
        apiFetch("/api/incidents"),
      ]);

      if (tickRes.ok) {
        const data: TicketItem[] = await tickRes.json();
        setTickets(data);
      } else {
        setErrorMsg("Failed to load tickets from backend.");
      }

      if (incRes.ok) {
        const incData: IncidentSummaryItem[] = await incRes.json();
        setIncidents(incData);
      }
    } catch {
      setErrorMsg("Network error connecting to support services.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTicketsAndIncidents();
  }, []);

  const handleCreateTicket = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateMsg(null);

    if (!title.trim() || !description.trim()) {
      setCreateMsg({ type: "error", text: "Please provide a ticket title and detailed description." });
      return;
    }

    setCreating(true);
    try {
      const activeInc = incidents.find((i) => i.status === "open" || i.status === "diagnosed");
      const res = await apiFetch("/api/tickets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: title.trim(),
          category,
          location,
          affected_service: affectedService,
          description: description.trim(),
          priority,
          contact_info: contactInfo.trim() || undefined,
          linked_incident_id: activeInc ? activeInc.incident_id : undefined,
        }),
      });

      if (res.ok) {
        const created: TicketItem = await res.json();
        setTickets((prev) => [created, ...prev]);
        setCreateMsg({
          type: "success",
          text: `Support ticket ${created.ticket_id} submitted and logged in backend.`,
        });
        setTitle("");
        setDescription("");
        setContactInfo("");
        setTimeout(() => {
          setActiveTab("tickets");
          setSelectedTicket(created);
        }, 1200);
      } else {
        const err = await res.json().catch(() => ({}));
        setCreateMsg({ type: "error", text: err.detail || "Failed to create support ticket." });
      }
    } catch {
      setCreateMsg({ type: "error", text: "Network error submitting ticket." });
    } finally {
      setCreating(false);
    }
  };

  const handleUpdateTicket = async () => {
    if (!selectedTicket || !updateStatus) return;
    setUpdating(true);
    setUpdateMsg(null);
    try {
      const res = await apiFetch(`/api/tickets/${selectedTicket.ticket_id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          status: updateStatus,
          notes: updateNotes.trim() || undefined,
        }),
      });

      if (res.ok) {
        const updated: TicketItem = await res.json();
        setTickets((prev) => prev.map((t) => (t.ticket_id === updated.ticket_id ? updated : t)));
        setSelectedTicket(updated);
        setUpdateMsg("Ticket status updated successfully.");
        setUpdateNotes("");
        setTimeout(() => setUpdateMsg(null), 3000);
      } else {
        const err = await res.json().catch(() => ({}));
        setUpdateMsg(err.detail || "Unable to update ticket status.");
      }
    } catch {
      setUpdateMsg("Network error updating ticket.");
    } finally {
      setUpdating(false);
    }
  };

  // Plain language translation of technical root causes
  const getPlainLanguageExplanation = () => {
    const raw = report?.probable_cause || (incidents[0] ? incidents[0].probable_cause : null);
    if (!raw) {
      return "Network traffic is running smoothly with no active service disruptions.";
    }
    const lower = raw.toLowerCase();
    if (lower.includes("congestion") || lower.includes("overflow") || lower.includes("saturation")) {
      return "Network traffic is unusually high between the core router and campus buildings, causing slower internet and intermittent video buffering.";
    }
    if (lower.includes("drop") || lower.includes("loss")) {
      return "Data packets are experiencing minor delays on the campus uplink. Engineers are rerouting traffic to restore full bandwidth.";
    }
    if (lower.includes("link_failure") || lower.includes("down")) {
      return "A primary campus network link is currently undergoing emergency maintenance. Redundant backup connections are active.";
    }
    return "Technical diagnosis is in progress by Network Operations. Expected resolution within 15 minutes.";
  };

  const bulletinText = `CAMPUS SERVICE ADVISORY BULLETIN
Reference: ${incidents[0]?.incident_id || "NET-2026-NOTICE"}
Status: Degraded Internet Connectivity (Resolution in Progress)
Affected Areas: Hostel Block B, Academic Complex B
Affected Services: Campus Wi-Fi, High-definition Video Calling

Notice:
${getPlainLanguageExplanation()}

Support Instructions:
Students and faculty do not need to reboot personal routers. Network Engineers are actively stabilizing traffic flow. Next update expected in 15 minutes.`;

  const handleCopyBulletin = () => {
    navigator.clipboard.writeText(bulletinText);
    setCopiedBulletin(true);
    setTimeout(() => setCopiedBulletin(false), 3000);
  };

  const openTicketsCount = tickets.filter((t) => t.status !== "Resolved" && t.status !== "Closed").length;
  const activeIncidents = incidents.filter((i) => i.status === "open" || i.status === "diagnosed");

  const filteredTickets = tickets.filter((t) => {
    const matchesSearch =
      t.ticket_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      t.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      t.location.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = filterStatus === "all" || t.status.toLowerCase() === filterStatus.toLowerCase();
    const matchesPriority = filterPriority === "all" || t.priority.toLowerCase() === filterPriority.toLowerCase();
    return matchesSearch && matchesStatus && matchesPriority;
  });

  return (
    <div className="space-y-6 font-sans text-sm text-slate-800 dark:text-slate-100">
      {/* Helpdesk Center Header */}
      <div className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[11px] uppercase font-bold tracking-wider px-2 py-0.5 border border-emerald-600/30 bg-emerald-50 text-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-300">
                Customer Support &amp; Helpdesk Center
              </span>
              <span className="text-xs text-slate-500 dark:text-slate-400">
                Campus Support Portal &bull; IIT-Bhubaneswar
              </span>
            </div>
            <h2 className="text-2xl font-bold tracking-tight text-[#0B2545] dark:text-slate-100">End-User Support &amp; Service Status</h2>
            <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
              Plain-language campus notices, ticket submission, and user advisory coordination.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setActiveTab("create_ticket")}
              className="px-4 py-2 bg-[#0B2545] hover:bg-[#133E87] text-white text-xs font-bold uppercase tracking-wider transition-colors shadow-sm"
            >
              + Create Support Ticket
            </button>
          </div>
        </div>

        {errorMsg && (
          <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 text-red-700 dark:text-red-400 text-xs">
            {errorMsg}
          </div>
        )}
      </div>

      {/* Navigation Sub-Tabs */}
      <div className="flex border-b border-slate-200 dark:border-slate-800 gap-1 overflow-x-auto text-xs">
        {[
          { id: "overview", label: "Overview" },
          { id: "create_ticket", label: "Create Ticket" },
          { id: "tickets", label: `Support Tickets Queue (${openTicketsCount} open)` },
          { id: "status", label: "Campus Status & Bulletin" },
          { id: "caller_guide", label: "Inbound Caller Script" },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={`px-3.5 py-2.5 font-bold uppercase tracking-wider whitespace-nowrap border-b-2 transition-colors ${
              activeTab === tab.id
                ? "border-[#0B2545] text-[#0B2545] dark:text-blue-400 bg-slate-50 dark:bg-slate-800/50"
                : "border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ----------------------------------------------------------------- */}
      {/* TAB 1: Helpdesk Overview                                          */}
      {/* ----------------------------------------------------------------- */}
      {activeTab === "overview" && (
        <div className="space-y-6">
          {/* Service Status Notice Banner */}
          <div
            className={`p-4 border ${
              activeIncidents.length > 0
                ? "border-[#A08A5B] bg-[#A08A5B]/10"
                : "border-[#5E7A6A] bg-[#5E7A6A]/10"
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span
                  className={`w-3 h-3 rounded-full ${
                    activeIncidents.length > 0 ? "bg-[#A08A5B]" : "bg-[#5E7A6A]"
                  }`}
                ></span>
                <span className="font-bold uppercase text-xs">
                  {activeIncidents.length > 0
                    ? "Service Notice Active: Degraded Campus Performance"
                    : "All Campus Services Operating Normally"}
                </span>
              </div>
              <span className="text-[10px] text-[#6B6B66] dark:text-[#888884]">
                Next status update in ~15 mins
              </span>
            </div>
            <p className="mt-2 text-xs leading-relaxed text-[#111111] dark:text-[#EDEDEA]">
              {getPlainLanguageExplanation()}
            </p>
          </div>

          {/* Quick Metrics */}
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
            <div className="p-4 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618]">
              <span className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">Open Tickets</span>
              <div className="text-xl font-bold mt-1 text-[#A08A5B]">{openTicketsCount}</div>
              <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] mt-0.5">Awaiting resolution</div>
            </div>

            <div className="p-4 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618]">
              <span className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">Affected Location</span>
              <div className="text-base font-bold mt-1">Hostel Block B</div>
              <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] mt-0.5">South Campus area</div>
            </div>

            <div className="p-4 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618]">
              <span className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">Impacted Services</span>
              <div className="text-base font-bold mt-1">Wi-Fi &amp; Video Calls</div>
              <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] mt-0.5">LMS operational</div>
            </div>

            <div className="p-4 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618]">
              <span className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">Engineering Triage</span>
              <div className="text-base font-bold mt-1 text-[#5E7A6A]">In Progress</div>
              <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] mt-0.5">Automated rebalancing</div>
            </div>
          </div>

          {/* Primary Action Callout */}
          <div className="p-4 border border-[#475569] bg-[#FAFAF9] dark:bg-[#0F0F10] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <div className="font-bold text-xs uppercase">Need to Report a New User Issue?</div>
              <div className="text-xs text-[#6B6B66] dark:text-[#888884] mt-0.5">
                Log student or faculty connectivity complaints directly into the central ticket queue.
              </div>
            </div>
            <button
              onClick={() => setActiveTab("create_ticket")}
              className="px-4 py-2 bg-[#0B2545] hover:bg-[#133E87] text-white text-xs font-bold uppercase tracking-wider transition-colors"
            >
              Create Support Ticket &rarr;
            </button>
          </div>
        </div>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* TAB 2: Create Support Ticket Form                                 */}
      {/* ----------------------------------------------------------------- */}
      {activeTab === "create_ticket" && (
        <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-5 max-w-2xl mx-auto">
          <h3 className="text-sm font-bold uppercase tracking-wider mb-1">Create Support Ticket</h3>
          <p className="text-xs text-[#6B6B66] dark:text-[#888884] mb-4">
            Submits a verified support request persisted in the central database.
          </p>

          {createMsg && (
            <div
              className={`p-3 border text-xs mb-4 ${
                createMsg.type === "success"
                  ? "bg-green-500/10 border-green-500/30 text-green-600 dark:text-green-400"
                  : "bg-red-500/10 border-red-500/30 text-red-600 dark:text-red-400"
              }`}
            >
              {createMsg.text}
            </div>
          )}

          <form onSubmit={handleCreateTicket} className="space-y-4">
            <div>
              <label className="block text-[10px] uppercase font-bold text-[#6B6B66] dark:text-[#888884] mb-1">
                Ticket Title
              </label>
              <input
                type="text"
                required
                placeholder="e.g. WiFi dropping out in Library 2nd floor reading hall"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full p-2 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10] focus:border-[#475569] outline-none"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-[10px] uppercase font-bold text-[#6B6B66] dark:text-[#888884] mb-1">
                  Problem Category
                </label>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="w-full p-2 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10] focus:border-[#475569] outline-none"
                >
                  <option value="wifi">Campus Wi-Fi</option>
                  <option value="connectivity">Internet / Intranet Connectivity</option>
                  <option value="application">LMS / Moodle Portal</option>
                  <option value="hardware">Hardware / Cable / Switch</option>
                  <option value="dns">Domain / DNS Resolution</option>
                  <option value="other">General Network Inquiry</option>
                </select>
              </div>

              <div>
                <label className="block text-[10px] uppercase font-bold text-[#6B6B66] dark:text-[#888884] mb-1">
                  Priority / Impact Level
                </label>
                <select
                  value={priority}
                  onChange={(e) => setPriority(e.target.value)}
                  className="w-full p-2 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10] focus:border-[#475569] outline-none"
                >
                  <option value="low">Low (Single user inquiry)</option>
                  <option value="medium">Medium (Moderate slowdown)</option>
                  <option value="high">High (Multiple users affected)</option>
                  <option value="critical">Critical (Full block or hall outage)</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-[10px] uppercase font-bold text-[#6B6B66] dark:text-[#888884] mb-1">
                  Affected Campus Location
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Hostel Block B, Room 204"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  className="w-full p-2 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10] focus:border-[#475569] outline-none"
                />
              </div>

              <div>
                <label className="block text-[10px] uppercase font-bold text-[#6B6B66] dark:text-[#888884] mb-1">
                  Affected Campus Service
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Campus WiFi, Moodle, VoIP"
                  value={affectedService}
                  onChange={(e) => setAffectedService(e.target.value)}
                  className="w-full p-2 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10] focus:border-[#475569] outline-none"
                />
              </div>
            </div>

            <div>
              <label className="block text-[10px] uppercase font-bold text-[#6B6B66] dark:text-[#888884] mb-1">
                Description of Issue
              </label>
              <textarea
                required
                rows={4}
                placeholder="Describe what the user is experiencing in detail..."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="w-full p-2 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10] focus:border-[#475569] outline-none"
              ></textarea>
            </div>

            <div>
              <label className="block text-[10px] uppercase font-bold text-[#6B6B66] dark:text-[#888884] mb-1">
                User Contact Information (Optional)
              </label>
              <input
                type="text"
                placeholder="e.g. student@iitbbsr.ac.in or +91 98765 43210"
                value={contactInfo}
                onChange={(e) => setContactInfo(e.target.value)}
                className="w-full p-2 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10] focus:border-[#475569] outline-none"
              />
            </div>

            <div className="pt-2 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setActiveTab("overview")}
                className="px-4 py-2 border border-[#E5E5E3] dark:border-[#2A2A2D] text-xs font-semibold uppercase"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={creating}
                className="px-5 py-2 bg-[#0B2545] hover:bg-[#133E87] text-white font-bold uppercase text-xs tracking-wider transition-colors"
              >
                {creating ? "Submitting..." : "Submit Ticket"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* TAB 3: Support Tickets Queue                                      */}
      {/* ----------------------------------------------------------------- */}
      {activeTab === "tickets" && (
        <div className="space-y-4">
          <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618]">
            <div className="p-4 border-b border-[#E5E5E3] dark:border-[#2A2A2D] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <h3 className="text-sm font-bold uppercase tracking-wider">Authorized Support Ticket Queue</h3>
                <p className="text-xs text-[#6B6B66] dark:text-[#888884]">Live records persisted in backend database.</p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <input
                  type="text"
                  placeholder="Search tickets..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="px-2.5 py-1 text-xs border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10] focus:border-[#475569] outline-none"
                />
                <select
                  value={filterStatus}
                  onChange={(e) => setFilterStatus(e.target.value)}
                  className="px-2 py-1 text-xs border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10] focus:border-[#475569] outline-none"
                >
                  <option value="all">All Statuses</option>
                  <option value="New">New</option>
                  <option value="Open">Open</option>
                  <option value="Assigned">Assigned</option>
                  <option value="Investigating">Investigating</option>
                  <option value="Awaiting User">Awaiting User</option>
                  <option value="Resolved">Resolved</option>
                  <option value="Closed">Closed</option>
                </select>
                <select
                  value={filterPriority}
                  onChange={(e) => setFilterPriority(e.target.value)}
                  className="px-2 py-1 text-xs border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10] focus:border-[#475569] outline-none"
                >
                  <option value="all">All Priorities</option>
                  <option value="critical">Critical</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-[#FAFAF9] dark:bg-[#0F0F10] border-b border-[#E5E5E3] dark:border-[#2A2A2D] text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">
                  <tr>
                    <th className="p-3">Ticket ID</th>
                    <th className="p-3">Issue Title</th>
                    <th className="p-3">Location</th>
                    <th className="p-3">Priority</th>
                    <th className="p-3">Status</th>
                    <th className="p-3">Linked Incident</th>
                    <th className="p-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E5E5E3] dark:divide-[#2A2A2D]">
                  {filteredTickets.map((t) => (
                    <tr
                      key={t.ticket_id}
                      onClick={() => {
                        setSelectedTicket(t);
                        setUpdateStatus(t.status);
                      }}
                      className={`cursor-pointer hover:bg-[#FAFAF9] dark:hover:bg-[#0F0F10] ${
                        selectedTicket?.ticket_id === t.ticket_id ? "bg-[#FAFAF9] dark:bg-[#0F0F10]" : ""
                      }`}
                    >
                      <td className="p-3 font-bold font-mono">{t.ticket_id}</td>
                      <td className="p-3 max-w-xs truncate">{t.title}</td>
                      <td className="p-3">{t.location}</td>
                      <td className="p-3">
                        <span
                          className={`px-1.5 py-0.5 border text-[9px] uppercase font-semibold ${
                            t.priority === "critical"
                              ? "border-[#9A5B5B] text-[#9A5B5B]"
                              : t.priority === "high"
                              ? "border-[#A08A5B] text-[#A08A5B]"
                              : "border-[#6B6B66] text-[#6B6B66]"
                          }`}
                        >
                          {t.priority}
                        </span>
                      </td>
                      <td className="p-3">
                        <span className="px-1.5 py-0.5 border border-[#475569] text-[9px] uppercase font-semibold">
                          {t.status}
                        </span>
                      </td>
                      <td className="p-3 font-mono">{t.linked_incident_id || "None"}</td>
                      <td className="p-3 text-right">
                        <button className="text-[10px] text-[#475569] dark:text-[#94A3B8] font-semibold hover:underline">
                          Inspect &rarr;
                        </button>
                      </td>
                    </tr>
                  ))}
                  {loading && (
                    <tr>
                      <td colSpan={7} className="p-4 text-center text-[#6B6B66] dark:text-[#888884]">
                        Loading support tickets...
                      </td>
                    </tr>
                  )}
                  {!loading && filteredTickets.length === 0 && (
                    <tr>
                      <td colSpan={7} className="p-4 text-center text-[#6B6B66] dark:text-[#888884]">
                        No support tickets matching current filter criteria.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Ticket Detail & Status Update Drawer */}
          {selectedTicket && (
            <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-5 space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-[#E5E5E3] dark:border-[#2A2A2D]">
                <div>
                  <span className="text-[10px] uppercase font-bold text-[#6B6B66] dark:text-[#888884]">
                    Ticket Inspector
                  </span>
                  <h4 className="text-base font-bold font-mono mt-0.5">{selectedTicket.ticket_id}: {selectedTicket.title}</h4>
                </div>
                <button
                  onClick={() => setSelectedTicket(null)}
                  className="text-xs text-[#6B6B66] hover:text-[#111111] dark:hover:text-[#EDEDEA]"
                >
                  Close
                </button>
              </div>

              {updateMsg && (
                <div className="p-2.5 bg-blue-500/10 border border-blue-500/30 text-blue-600 dark:text-blue-400 text-xs">
                  {updateMsg}
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
                <div className="p-3 border border-[#E5E5E3] dark:border-[#2A2A2D] space-y-1">
                  <span className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">Campus Location</span>
                  <div className="font-bold">{selectedTicket.location}</div>
                  <div className="text-[11px] text-[#6B6B66] dark:text-[#888884]">Service: {selectedTicket.affected_service}</div>
                </div>

                <div className="p-3 border border-[#E5E5E3] dark:border-[#2A2A2D] space-y-1">
                  <span className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">Lifecycle State</span>
                  <div className="font-bold">{selectedTicket.status}</div>
                  <div className="text-[11px] text-[#6B6B66] dark:text-[#888884]">Priority: {selectedTicket.priority}</div>
                </div>

                <div className="p-3 border border-[#E5E5E3] dark:border-[#2A2A2D] space-y-1">
                  <span className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">Linked Network Incident</span>
                  <div className="font-bold font-mono">{selectedTicket.linked_incident_id || "Unlinked"}</div>
                  <div className="text-[11px] text-[#6B6B66] dark:text-[#888884]">Created by: {selectedTicket.created_by}</div>
                </div>
              </div>

              <div className="p-3 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] text-xs">
                <span className="text-[10px] uppercase font-bold text-[#6B6B66] dark:text-[#888884] block mb-1">
                  Description:
                </span>
                <p className="leading-relaxed">{selectedTicket.description}</p>
                {selectedTicket.user_facing_summary && (
                  <div className="mt-2 pt-2 border-t border-[#E5E5E3] dark:border-[#2A2A2D]">
                    <span className="text-[10px] uppercase font-bold text-[#5E7A6A] block mb-0.5">
                      Engineering Resolution Summary:
                    </span>
                    <p className="text-[#5E7A6A] dark:text-[#86EFAC]">{selectedTicket.user_facing_summary}</p>
                  </div>
                )}
              </div>

              {/* Status Update Form for Helpdesk */}
              <div className="pt-2 border-t border-[#E5E5E3] dark:border-[#2A2A2D] flex flex-col sm:flex-row items-end gap-3 text-xs">
                <div className="w-full sm:w-48">
                  <label className="block text-[10px] uppercase font-bold text-[#6B6B66] dark:text-[#888884] mb-1">
                    Update Status
                  </label>
                  <select
                    value={updateStatus}
                    onChange={(e) => setUpdateStatus(e.target.value)}
                    className="w-full p-2 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10] outline-none"
                  >
                    <option value="New">New</option>
                    <option value="Open">Open</option>
                    <option value="Awaiting User">Awaiting User</option>
                    <option value="Closed">Closed</option>
                  </select>
                </div>
                <div className="w-full sm:flex-1">
                  <label className="block text-[10px] uppercase font-bold text-[#6B6B66] dark:text-[#888884] mb-1">
                    Add Note / Progress Update
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Contacted user, waiting for test confirmation"
                    value={updateNotes}
                    onChange={(e) => setUpdateNotes(e.target.value)}
                    className="w-full p-2 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10] outline-none"
                  />
                </div>
                <button
                  onClick={handleUpdateTicket}
                  disabled={updating}
                  className="w-full sm:w-auto px-4 py-2 bg-[#0B2545] hover:bg-[#133E87] text-white font-bold uppercase tracking-wider text-xs whitespace-nowrap transition-colors"
                >
                  {updating ? "Saving..." : "Save Update"}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* TAB 4: Campus Status & Advisory Bulletin                          */}
      {/* ----------------------------------------------------------------- */}
      {activeTab === "status" && (
        <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-5 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-[#E5E5E3] dark:border-[#2A2A2D]">
            <div>
              <h3 className="text-sm font-bold uppercase tracking-wider">Campus Service Advisory Bulletin</h3>
              <p className="text-xs text-[#6B6B66] dark:text-[#888884]">
                Standardized non-technical communication for students and faculty.
              </p>
            </div>
            <button
              onClick={handleCopyBulletin}
              className={`px-3.5 py-1.5 border text-xs font-bold uppercase tracking-wider transition-colors ${
                copiedBulletin
                  ? "border-[#5E7A6A] bg-[#5E7A6A] text-white"
                  : "border-[#475569] text-[#475569] dark:text-[#94A3B8] hover:bg-[#475569]/10"
              }`}
            >
              {copiedBulletin ? "Copied Bulletin!" : "Copy Bulletin to Clipboard"}
            </button>
          </div>

          <div className="p-4 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] font-mono text-xs whitespace-pre-line leading-relaxed">
            {bulletinText}
          </div>
        </div>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* TAB 5: Inbound Caller Script                                      */}
      {/* ----------------------------------------------------------------- */}
      {activeTab === "caller_guide" && (
        <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-5 space-y-4">
          <h3 className="text-sm font-bold uppercase tracking-wider">Helpdesk Inbound Phone Caller Script</h3>
          <p className="text-xs text-[#6B6B66] dark:text-[#888884]">
            Guidance for telephone interactions with students and professors reporting slowdowns.
          </p>

          <div className="space-y-3 text-xs">
            <div className="p-3 border border-[#E5E5E3] dark:border-[#2A2A2D] space-y-1">
              <div className="font-bold text-[#475569] dark:text-[#94A3B8]">1. Greet and Collect Location</div>
              <p className="text-[#6B6B66] dark:text-[#888884]">
                &quot;Thank you for calling IIT-Bhubaneswar IT Helpdesk. May I please have your name, department or hostel room number, and which service you are experiencing difficulties with?&quot;
              </p>
            </div>

            <div className="p-3 border border-[#E5E5E3] dark:border-[#2A2A2D] space-y-1">
              <div className="font-bold text-[#475569] dark:text-[#94A3B8]">2. Explain Situation Clearly</div>
              <p className="text-[#6B6B66] dark:text-[#888884]">
                &quot;We are currently experiencing high network volume in Hostel Block B. Our network engineering team is actively optimizing connections and traffic routing.&quot;
              </p>
            </div>

            <div className="p-3 border border-[#E5E5E3] dark:border-[#2A2A2D] space-y-1">
              <div className="font-bold text-[#475569] dark:text-[#94A3B8]">3. Provide Actionable Guidance</div>
              <p className="text-[#6B6B66] dark:text-[#888884]">
                &quot;You do not need to restart your device or alter network settings. LMS submission services remain accessible. We anticipate full stability within approximately 15 minutes.&quot;
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
