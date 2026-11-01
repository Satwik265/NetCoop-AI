import React, { useState, useEffect } from "react";
import { apiFetch, useAuth } from "../../auth/AuthContext";
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
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<
    "overview" | "create_ticket" | "my_tickets" | "service_status"
  >("overview");

  const [tickets, setTickets] = useState<TicketItem[]>([]);
  const [incidents, setIncidents] = useState<IncidentSummaryItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Ticket creation form state
  const [title, setTitle] = useState<string>("");
  const [category, setCategory] = useState<string>("wifi");
  const [location, setLocation] = useState<string>("Hostel Block B");
  const [affectedService, setAffectedService] = useState<string>("Campus Wi-Fi");
  const [description, setDescription] = useState<string>("");
  const [priority, setPriority] = useState<string>("high");
  const [contactInfo, setContactInfo] = useState<string>("");
  const [createMsg, setCreateMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [creating, setCreating] = useState<boolean>(false);

  // Filter and search state for My Tickets
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [filterPriority, setFilterPriority] = useState<string>("all");
  const [searchTerm, setSearchTerm] = useState<string>("");

  // Ticket detail view state
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
    if (!location.trim() || !affectedService.trim()) {
      setCreateMsg({ type: "error", text: "Please specify affected campus location and service." });
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
          location: location.trim(),
          affected_service: affectedService.trim(),
          description: description.trim(),
          priority,
          contact_info: contactInfo.trim() || (user?.username ? `Reported by ${user.username}` : undefined),
          linked_incident_id: activeInc ? activeInc.incident_id : undefined,
        }),
      });

      if (res.ok) {
        const created: TicketItem = await res.json();
        setTickets((prev) => [created, ...prev]);
        setCreateMsg({
          type: "success",
          text: `Support ticket ${created.ticket_id} created and forwarded to Network Operations.`,
        });
        setTitle("");
        setDescription("");
        setContactInfo("");
        setTimeout(() => {
          setActiveTab("my_tickets");
          setSelectedTicket(created);
          setCreateMsg(null);
        }, 1200);
      } else {
        const err = await res.json().catch(() => ({}));
        setCreateMsg({ type: "error", text: err.detail || "Failed to create support ticket in backend." });
      }
    } catch {
      setCreateMsg({ type: "error", text: "Network error submitting support ticket." });
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
    <div className="space-y-6 font-sans text-slate-800 dark:text-slate-100">
      {/* Helpdesk Center Header */}
      <div className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <span className="text-xs uppercase font-bold tracking-wider px-2.5 py-0.5 border border-emerald-600/30 bg-emerald-50 text-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-300">
                Customer Support &amp; Helpdesk Center
              </span>
              <span className="text-sm text-slate-500 dark:text-slate-400">
                IIT Bhubaneswar Campus Portal
              </span>
            </div>
            <h2 className="text-2xl font-bold tracking-tight text-[#0B2545] dark:text-slate-100">
              End-User Support &amp; Ticket Operations
            </h2>
            <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
              Create student and faculty support requests, track incident escalation, and coordinate campus notices.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => {
                setSelectedTicket(null);
                setActiveTab("create_ticket");
              }}
              className="px-5 py-2.5 bg-[#0B2545] hover:bg-[#133E87] text-white text-sm font-semibold tracking-wide transition-colors shadow-sm"
            >
              + Create Support Ticket
            </button>
          </div>
        </div>

        {errorMsg && (
          <div className="mt-4 p-3.5 bg-red-500/10 border border-red-500/30 text-red-700 dark:text-red-400 text-sm">
            {errorMsg}
          </div>
        )}
      </div>

      {/* Navigation Tabs - 4 strictly clean tabs */}
      <div className="flex border-b border-slate-200 dark:border-slate-800 gap-2 overflow-x-auto text-sm">
        {[
          { id: "overview", label: "Overview" },
          { id: "create_ticket", label: "Create Ticket" },
          { id: "my_tickets", label: `My Tickets (${openTicketsCount} open)` },
          { id: "service_status", label: "Service Status" },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => {
              setActiveTab(tab.id as any);
              if (tab.id !== "my_tickets") {
                setSelectedTicket(null);
              }
            }}
            className={`px-4 py-3 font-semibold tracking-wide whitespace-nowrap border-b-2 transition-colors ${
              activeTab === tab.id
                ? "border-[#0B2545] text-[#0B2545] dark:text-blue-400 bg-slate-50 dark:bg-slate-800/50"
                : "border-transparent text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* TAB 1: Overview */}
      {activeTab === "overview" && (
        <div className="space-y-6">
          {/* Service Status Notice Banner */}
          <div
            className={`p-5 border ${
              activeIncidents.length > 0
                ? "border-amber-300 bg-amber-50 dark:bg-amber-950/20 dark:border-amber-800"
                : "border-emerald-300 bg-emerald-50 dark:bg-emerald-950/20 dark:border-emerald-800"
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <span
                  className={`w-3 h-3 rounded-full ${
                    activeIncidents.length > 0 ? "bg-amber-600 animate-pulse" : "bg-emerald-600"
                  }`}
                ></span>
                <span className="font-bold text-sm tracking-wide text-slate-900 dark:text-slate-100">
                  {activeIncidents.length > 0
                    ? "Service Notice: Network Performance Under Investigation"
                    : "All Campus Digital Services Operating Normally"}
                </span>
              </div>
              <span className="text-xs text-slate-500 dark:text-slate-400">
                Auto-updated from Network Operations
              </span>
            </div>
            <p className="mt-2.5 text-sm leading-relaxed text-slate-700 dark:text-slate-300">
              {getPlainLanguageExplanation()}
            </p>
          </div>

          {/* Quick Metrics */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="p-5 border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
              <span className="text-xs uppercase font-semibold text-slate-500">Active Campus Incidents</span>
              <div className="text-2xl font-bold mt-1 text-slate-900 dark:text-slate-100">
                {activeIncidents.length}
              </div>
              <div className="text-xs text-slate-500 mt-1">
                {activeIncidents.length > 0 ? "Engineering triage in progress" : "No active disruptions"}
              </div>
            </div>

            <div className="p-5 border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
              <span className="text-xs uppercase font-semibold text-slate-500">Open Support Tickets</span>
              <div className="text-2xl font-bold mt-1 text-amber-700 dark:text-amber-400">
                {openTicketsCount}
              </div>
              <div className="text-xs text-slate-500 mt-1">In user support queue</div>
            </div>

            <div className="p-5 border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
              <span className="text-xs uppercase font-semibold text-slate-500">Total Logged Tickets</span>
              <div className="text-2xl font-bold mt-1 text-slate-900 dark:text-slate-100">
                {tickets.length}
              </div>
              <div className="text-xs text-slate-500 mt-1">Persisted in local database</div>
            </div>
          </div>

          {/* Action prompt */}
          <div className="p-5 border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <div className="font-bold text-base text-[#0B2545] dark:text-slate-100">
                Log a Student or Faculty Request
              </div>
              <div className="text-sm text-slate-600 dark:text-slate-400 mt-0.5">
                Capture connectivity complaints directly into the persistent support ticket queue for Network Operations.
              </div>
            </div>
            <button
              onClick={() => {
                setSelectedTicket(null);
                setActiveTab("create_ticket");
              }}
              className="px-5 py-2.5 bg-[#0B2545] hover:bg-[#133E87] text-white text-sm font-semibold tracking-wide transition-colors whitespace-nowrap"
            >
              Create Support Ticket &rarr;
            </button>
          </div>
        </div>
      )}

      {/* TAB 2: Create Support Ticket */}
      {activeTab === "create_ticket" && (
        <div className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 space-y-6">
          <div>
            <h3 className="text-xl font-bold text-[#0B2545] dark:text-slate-100">
              Create Support Ticket
            </h3>
            <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
              Submit end-user connectivity issues into the central database. The ticket will automatically enter the Network Operations queue.
            </p>
          </div>

          {createMsg && (
            <div
              className={`p-4 border text-sm ${
                createMsg.type === "success"
                  ? "bg-emerald-50 border-emerald-300 text-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-300"
                  : "bg-red-50 border-red-300 text-red-800 dark:bg-red-950/30 dark:text-red-300"
              }`}
            >
              {createMsg.text}
            </div>
          )}

          <form onSubmit={handleCreateTicket} className="space-y-5 text-sm">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
              <div>
                <label className="block text-xs uppercase font-bold text-slate-600 dark:text-slate-400 mb-1.5">
                  Issue Title <span className="text-red-600">*</span>
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. WiFi dropping intermittently in Hostel B"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full p-2.5 border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 focus:border-[#0B2545] outline-none"
                />
              </div>

              <div>
                <label className="block text-xs uppercase font-bold text-slate-600 dark:text-slate-400 mb-1.5">
                  Category
                </label>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="w-full p-2.5 border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 focus:border-[#0B2545] outline-none"
                >
                  <option value="wifi">Campus Wi-Fi / AP</option>
                  <option value="connectivity">Ethernet LAN Connectivity</option>
                  <option value="hardware">Router / Switch Hardware</option>
                  <option value="email_auth">Academic Portal &amp; Authentication</option>
                  <option value="dns_access">DNS &amp; Web Access</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
              <div>
                <label className="block text-xs uppercase font-bold text-slate-600 dark:text-slate-400 mb-1.5">
                  Campus Location <span className="text-red-600">*</span>
                </label>
                <select
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  className="w-full p-2.5 border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 focus:border-[#0B2545] outline-none"
                >
                  <option value="Hostel Block B">Hostel Block B</option>
                  <option value="Hostel Block A">Hostel Block A</option>
                  <option value="Academic Complex A">Academic Complex A</option>
                  <option value="Academic Complex B">Academic Complex B</option>
                  <option value="Central Library">Central Library</option>
                  <option value="Administrative Building">Administrative Building</option>
                  <option value="Faculty Housing">Faculty Housing</option>
                </select>
              </div>

              <div>
                <label className="block text-xs uppercase font-bold text-slate-600 dark:text-slate-400 mb-1.5">
                  Affected Service <span className="text-red-600">*</span>
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Campus Wi-Fi, LMS Moodle"
                  value={affectedService}
                  onChange={(e) => setAffectedService(e.target.value)}
                  className="w-full p-2.5 border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 focus:border-[#0B2545] outline-none"
                />
              </div>

              <div>
                <label className="block text-xs uppercase font-bold text-slate-600 dark:text-slate-400 mb-1.5">
                  Priority
                </label>
                <select
                  value={priority}
                  onChange={(e) => setPriority(e.target.value)}
                  className="w-full p-2.5 border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 focus:border-[#0B2545] outline-none"
                >
                  <option value="critical">Critical (Campus Outage)</option>
                  <option value="high">High (Severe Slowdown)</option>
                  <option value="medium">Medium (Moderate Degradation)</option>
                  <option value="low">Low (Minor Inquiry)</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-xs uppercase font-bold text-slate-600 dark:text-slate-400 mb-1.5">
                Issue Description <span className="text-red-600">*</span>
              </label>
              <textarea
                required
                rows={4}
                placeholder="Describe the problem experienced by the user in detail..."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="w-full p-2.5 border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 focus:border-[#0B2545] outline-none"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 pt-2 border-t border-slate-200 dark:border-slate-800">
              <div>
                <label className="block text-xs uppercase font-bold text-slate-600 dark:text-slate-400 mb-1.5">
                  User Contact / Notes
                </label>
                <input
                  type="text"
                  placeholder="e.g. Room 204, user@iitbbs.ac.in"
                  value={contactInfo}
                  onChange={(e) => setContactInfo(e.target.value)}
                  className="w-full p-2.5 border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 focus:border-[#0B2545] outline-none"
                />
              </div>

              <div className="flex flex-col justify-end">
                <div className="text-xs text-slate-500 dark:text-slate-400 mb-2">
                  Reporter: <span className="font-semibold text-slate-800 dark:text-slate-200">{user?.full_name || user?.username || "Helpdesk User"}</span> ({user?.role || "helpdesk"})
                </div>
              </div>
            </div>

            <div className="pt-4 flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={() => setActiveTab("my_tickets")}
                className="px-4 py-2 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 text-sm font-semibold hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={creating}
                className="px-6 py-2.5 bg-[#0B2545] hover:bg-[#133E87] text-white font-semibold text-sm tracking-wide transition-colors shadow-sm disabled:opacity-50"
              >
                {creating ? "Submitting..." : "Create Support Ticket"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* TAB 3: My Tickets */}
      {activeTab === "my_tickets" && (
        <div className="space-y-4">
          {/* If a ticket is clicked, show dedicated simplified ticket details view */}
          {selectedTicket ? (
            <div className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
                <div>
                  <button
                    onClick={() => setSelectedTicket(null)}
                    className="inline-flex items-center gap-1.5 text-sm font-semibold text-[#0B2545] hover:text-[#133E87] dark:text-blue-400 mb-2 transition-colors"
                  >
                    &larr; Back to My Tickets
                  </button>
                  <h3 className="text-xl font-bold text-slate-900 dark:text-slate-100">
                    <span className="font-mono text-[#0B2545] dark:text-blue-400">{selectedTicket.ticket_id}</span>: {selectedTicket.title}
                  </h3>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={`px-3 py-1 border text-xs uppercase font-bold tracking-wider ${
                      selectedTicket.priority === "critical"
                        ? "border-red-600/30 bg-red-50 text-red-700 dark:bg-red-950/30 dark:text-red-300"
                        : selectedTicket.priority === "high"
                        ? "border-amber-600/30 bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-300"
                        : "border-slate-300 bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300"
                    }`}
                  >
                    Priority: {selectedTicket.priority}
                  </span>
                  <span className="px-3 py-1 border border-slate-300 bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 text-xs uppercase font-bold tracking-wider">
                    Status: {selectedTicket.status}
                  </span>
                </div>
              </div>

              {updateMsg && (
                <div className="p-3 bg-blue-50 border border-blue-200 text-blue-700 dark:bg-blue-950/30 dark:text-blue-300 text-sm">
                  {updateMsg}
                </div>
              )}

              {/* Clean Information Grid - strictly ticket fields, NO raw telemetry or internal diagnostics */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
                <div className="p-4 border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 space-y-1">
                  <span className="text-xs uppercase font-bold text-slate-500">Campus Location</span>
                  <div className="font-semibold text-slate-900 dark:text-slate-100">{selectedTicket.location}</div>
                  <div className="text-xs text-slate-500">Service: {selectedTicket.affected_service}</div>
                </div>

                <div className="p-4 border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 space-y-1">
                  <span className="text-xs uppercase font-bold text-slate-500">Category</span>
                  <div className="font-semibold text-slate-900 dark:text-slate-100 uppercase text-xs">{selectedTicket.category}</div>
                  <div className="text-xs text-slate-500">Created by: {selectedTicket.created_by}</div>
                </div>

                <div className="p-4 border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 space-y-1">
                  <span className="text-xs uppercase font-bold text-slate-500">Assigned Team / Person</span>
                  <div className="font-semibold text-slate-900 dark:text-slate-100">
                    {selectedTicket.assigned_to || "Unassigned (Network Operations)"}
                  </div>
                  <div className="text-xs text-slate-500">
                    {selectedTicket.assigned_to ? "Assigned to engineer" : "Awaiting assignment"}
                  </div>
                </div>

                <div className="p-4 border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 space-y-1">
                  <span className="text-xs uppercase font-bold text-slate-500">Timestamps</span>
                  <div className="text-xs font-mono text-slate-700 dark:text-slate-300">
                    Created: {new Date(selectedTicket.created_at).toLocaleString()}
                  </div>
                  <div className="text-xs font-mono text-slate-500">
                    Updated: {new Date(selectedTicket.updated_at).toLocaleString()}
                  </div>
                </div>
              </div>

              {/* Description */}
              <div className="p-5 border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 space-y-2">
                <span className="text-xs uppercase font-bold text-slate-500 block">
                  Detailed Description
                </span>
                <p className="text-sm text-slate-800 dark:text-slate-200 leading-relaxed whitespace-pre-line">
                  {selectedTicket.description}
                </p>
                {selectedTicket.contact_info && (
                  <p className="text-xs text-slate-500 pt-2 border-t border-slate-100 dark:border-slate-800">
                    User Contact Notes: {selectedTicket.contact_info}
                  </p>
                )}
              </div>

              {/* User-facing engineering summary if available */}
              {selectedTicket.user_facing_summary && (
                <div className="p-5 border border-emerald-300 bg-emerald-50 dark:bg-emerald-950/20 dark:border-emerald-800">
                  <span className="text-xs uppercase font-bold text-emerald-800 dark:text-emerald-300 block mb-1">
                    Network Engineering Resolution Summary
                  </span>
                  <p className="text-sm text-emerald-900 dark:text-emerald-100 leading-relaxed">
                    {selectedTicket.user_facing_summary}
                  </p>
                </div>
              )}

              {/* Status Update / Notes Form */}
              <div className="pt-4 border-t border-slate-200 dark:border-slate-800 space-y-3">
                <h4 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                  Update Ticket Note / Lifecycle State
                </h4>
                <div className="flex flex-col sm:flex-row items-end gap-3 text-sm">
                  <div className="w-full sm:w-56">
                    <label className="block text-xs uppercase font-bold text-slate-500 mb-1">
                      Status
                    </label>
                    <select
                      value={updateStatus}
                      onChange={(e) => setUpdateStatus(e.target.value)}
                      className="w-full p-2.5 border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 outline-none"
                    >
                      <option value="New">New</option>
                      <option value="Open">Open</option>
                      <option value="Awaiting User">Awaiting User</option>
                      <option value="Closed">Closed</option>
                    </select>
                  </div>
                  <div className="w-full sm:flex-1">
                    <label className="block text-xs uppercase font-bold text-slate-500 mb-1">
                      Add Progress Note
                    </label>
                    <input
                      type="text"
                      placeholder="e.g. Contacted user, verified local switch port"
                      value={updateNotes}
                      onChange={(e) => setUpdateNotes(e.target.value)}
                      className="w-full p-2.5 border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 outline-none"
                    />
                  </div>
                  <button
                    onClick={handleUpdateTicket}
                    disabled={updating}
                    className="w-full sm:w-auto px-5 py-2.5 bg-[#0B2545] hover:bg-[#133E87] text-white font-semibold text-sm whitespace-nowrap transition-colors"
                  >
                    {updating ? "Saving..." : "Save Update"}
                  </button>
                </div>
              </div>
            </div>
          ) : (
            /* Ticket Table View - Clean without repeated Inspect column */
            <div className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
              <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <h3 className="text-base font-bold text-[#0B2545] dark:text-slate-100">
                    My Support Tickets
                  </h3>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Click any ticket row to view dedicated details.
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2.5">
                  <input
                    type="text"
                    placeholder="Search tickets..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="px-3 py-1.5 text-xs border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 focus:border-[#0B2545] outline-none"
                  />
                  <select
                    value={filterStatus}
                    onChange={(e) => setFilterStatus(e.target.value)}
                    className="px-3 py-1.5 text-xs border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 focus:border-[#0B2545] outline-none"
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
                    className="px-3 py-1.5 text-xs border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 focus:border-[#0B2545] outline-none"
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
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 dark:bg-slate-950 border-b border-slate-200 dark:border-slate-800 text-xs uppercase font-bold text-slate-500">
                    <tr>
                      <th className="p-3.5">Ticket ID</th>
                      <th className="p-3.5">Issue Title</th>
                      <th className="p-3.5">Location</th>
                      <th className="p-3.5">Priority</th>
                      <th className="p-3.5">Status</th>
                      <th className="p-3.5">Assigned To</th>
                      <th className="p-3.5">Linked Incident</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                    {filteredTickets.map((t) => (
                      <tr
                        key={t.ticket_id}
                        onClick={() => {
                          setSelectedTicket(t);
                          setUpdateStatus(t.status);
                        }}
                        className="cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
                      >
                        <td className="p-3.5 font-bold font-mono text-[#0B2545] dark:text-blue-400">
                          {t.ticket_id}
                        </td>
                        <td className="p-3.5 font-semibold text-slate-900 dark:text-slate-100 max-w-xs truncate">
                          {t.title}
                        </td>
                        <td className="p-3.5 text-slate-600 dark:text-slate-400">{t.location}</td>
                        <td className="p-3.5">
                          <span
                            className={`px-2 py-0.5 border text-xs uppercase font-semibold ${
                              t.priority === "critical"
                                ? "border-red-600/30 bg-red-50 text-red-700 dark:bg-red-950/30 dark:text-red-300"
                                : t.priority === "high"
                                ? "border-amber-600/30 bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-300"
                                : "border-slate-300 bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300"
                            }`}
                          >
                            {t.priority}
                          </span>
                        </td>
                        <td className="p-3.5">
                          <span className="px-2 py-0.5 border border-slate-300 text-xs uppercase font-semibold text-slate-700 dark:text-slate-300">
                            {t.status}
                          </span>
                        </td>
                        <td className="p-3.5 text-slate-600 dark:text-slate-400 text-xs">
                          {t.assigned_to || "Unassigned"}
                        </td>
                        <td className="p-3.5 font-mono text-xs text-slate-500">
                          {t.linked_incident_id || "None"}
                        </td>
                      </tr>
                    ))}
                    {loading && (
                      <tr>
                        <td colSpan={7} className="p-6 text-center text-slate-500">
                          Loading support tickets...
                        </td>
                      </tr>
                    )}
                    {!loading && filteredTickets.length === 0 && (
                      <tr>
                        <td colSpan={7} className="p-6 text-center text-slate-500">
                          No support tickets matching current filter criteria.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 4: Service Status & Bulletin */}
      {activeTab === "service_status" && (
        <div className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 space-y-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
            <div>
              <h3 className="text-xl font-bold text-[#0B2545] dark:text-slate-100">
                Campus Service Status &amp; Advisory Notice
              </h3>
              <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                Standardized non-technical communication for sharing with students, faculty, and departments.
              </p>
            </div>
            <button
              onClick={handleCopyBulletin}
              className={`px-4 py-2 border text-sm font-semibold tracking-wide transition-colors ${
                copiedBulletin
                  ? "border-emerald-600 bg-emerald-600 text-white"
                  : "border-[#0B2545] text-[#0B2545] dark:text-blue-400 hover:bg-[#0B2545]/10"
              }`}
            >
              {copiedBulletin ? "Copied Bulletin!" : "Copy Bulletin to Clipboard"}
            </button>
          </div>

          <div className="p-5 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-sm whitespace-pre-line leading-relaxed text-slate-800 dark:text-slate-200">
            {bulletinText}
          </div>
        </div>
      )}
    </div>
  );
};
