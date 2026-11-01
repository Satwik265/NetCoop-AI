import React, { useState, useEffect } from "react";
import { apiFetch } from "../../auth/AuthContext";

export interface DeviceItem {
  device_id: string;
  hostname: string;
  role: string;
  vendor: string;
  ip_address: string;
  status: string;
  interfaces_count: number;
  cpu_utilization_pct: number;
  memory_utilization_pct: number;
  last_config_change: string;
  maintenance_mode: boolean;
  location?: string;
  warning?: string | null;
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
  ticket_id: string;
  title: string;
  category: string;
  location: string;
  affected_service: string;
  priority: string;
  status: string;
  created_by: string;
  assigned_to?: string | null;
  linked_incident_id?: string | null;
  created_at: string;
}

export interface AdminViewProps {
  onNavigate?: (navId: string) => void;
}

export const AdminView: React.FC<AdminViewProps> = ({ onNavigate }) => {
  const [activeTab, setActiveTab] = useState<
    "overview" | "incidents" | "devices" | "telemetry" | "maintenance" | "tickets" | "reports"
  >("overview");

  const [devices, setDevices] = useState<DeviceItem[]>([]);
  const [incidents, setIncidents] = useState<IncidentSummaryItem[]>([]);
  const [tickets, setTickets] = useState<TicketItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedDevice, setSelectedDevice] = useState<DeviceItem | null>(null);

  // Search and filter for devices
  const [deviceSearch, setDeviceSearch] = useState<string>("");
  const [deviceRoleFilter, setDeviceRoleFilter] = useState<string>("all");

  // Maintenance Schedule & Confirmation Modal
  const [maintenanceSchedule, setMaintenanceSchedule] = useState<
    Array<{ id: string; device: string; window: string; reason: string }>
  >([
    {
      id: "maint-01",
      device: "spine-01",
      window: "Sunday 02:00 - 04:00 UTC",
      reason: "OS Upgrade & ECMP load-interval tuning",
    },
    {
      id: "maint-02",
      device: "leaf-02",
      window: "Tuesday 01:00 - 02:30 UTC",
      reason: "SFP28 optical transceiver replacement",
    },
  ]);
  const [newMaintDevice, setNewMaintDevice] = useState<string>("spine-02");
  const [newMaintReason, setNewMaintReason] = useState<string>("");
  const [showMaintConfirm, setShowMaintConfirm] = useState<boolean>(false);
  const [scheduledMsg, setScheduledMsg] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      apiFetch("/api/devices")
        .then((res) => (res.ok ? res.json() : []))
        .catch(() => []),
      apiFetch("/api/incidents")
        .then((res) => (res.ok ? res.json() : []))
        .catch(() => []),
      apiFetch("/api/tickets")
        .then((res) => (res.ok ? res.json() : []))
        .catch(() => []),
    ])
      .then(([devData, incData, tickData]) => {
        if (devData && devData.length > 0) {
          const mapped: DeviceItem[] = devData.map((d: any) => ({
            ...d,
            location: d.hostname?.includes("campus") ? "IIT-Bhubaneswar Main Campus" : "Data Center Core",
            warning: d.cpu_utilization_pct > 80 ? "High CPU" : d.status !== "online" ? "Degraded Link" : null,
          }));
          setDevices(mapped);
          setSelectedDevice(mapped[0]);
        }
        if (incData) setIncidents(incData);
        if (tickData) setTickets(tickData);
      })
      .finally(() => setLoading(false));
  }, []);

  const handleConfirmScheduleMaintenance = () => {
    if (!newMaintReason.trim()) return;
    const newEntry = {
      id: `maint-0${maintenanceSchedule.length + 1}`,
      device: newMaintDevice,
      window: "Scheduled Maintenance Window (Upcoming)",
      reason: newMaintReason,
    };
    setMaintenanceSchedule((prev) => [...prev, newEntry]);
    setShowMaintConfirm(false);
    setNewMaintReason("");
    setScheduledMsg(`Maintenance window confirmed for ${newMaintDevice}. Audit record created.`);
    setTimeout(() => setScheduledMsg(null), 4000);
  };

  const criticalOrWarningDevices = devices.filter(
    (d) => d.status !== "online" || d.cpu_utilization_pct > 75 || d.warning
  );
  const activeIncidents = incidents.filter(
    (i) => i.status === "open" || i.status === "diagnosed" || i.status === "pending"
  );
  const networkTickets = tickets.filter(
    (t) => t.category === "hardware" || t.category === "connectivity" || t.category === "wifi"
  );

  const filteredDevices = devices.filter((d) => {
    const matchesSearch =
      d.hostname.toLowerCase().includes(deviceSearch.toLowerCase()) ||
      d.device_id.toLowerCase().includes(deviceSearch.toLowerCase());
    const matchesRole = deviceRoleFilter === "all" || d.role === deviceRoleFilter;
    return matchesSearch && matchesRole;
  });

  return (
    <div className="space-y-6 font-sans text-slate-800 dark:text-slate-100">
      {/* Network Administrator Header */}
      <div className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[11px] uppercase font-bold tracking-wider px-2 py-0.5 bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border border-slate-300 dark:border-slate-700">
                Network Infrastructure Administration
              </span>
              <span className="text-xs text-slate-500 dark:text-slate-400">
                Campus Fabric Domain: iitbbsr-campus-prod
              </span>
            </div>
            <h2 className="text-2xl font-bold tracking-tight text-[#0B2545] dark:text-slate-100">Network Administrator Operations</h2>
            <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
              Fabric device health, maintenance scheduling, and operational incident assignment.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => onNavigate && onNavigate("role_engineer")}
              className="px-4 py-2 bg-[#0B2545] hover:bg-[#133E87] text-white text-xs font-bold uppercase tracking-wider transition-colors shadow-sm"
            >
              Investigate Active Incidents &rarr;
            </button>
          </div>
        </div>

        {scheduledMsg && (
          <div className="mt-4 p-3 bg-green-500/10 border border-green-500/30 text-green-700 dark:text-green-400 text-xs">
            {scheduledMsg}
          </div>
        )}
      </div>

      {/* Navigation Sub-Tabs */}
      <div className="flex border-b border-slate-200 dark:border-slate-800 gap-1 overflow-x-auto text-xs">
        {[
          { id: "overview", label: "Network Overview" },
          { id: "incidents", label: `Active Incidents (${activeIncidents.length})` },
          { id: "devices", label: `Devices & Topology (${devices.length})` },
          { id: "telemetry", label: "Telemetry & Performance" },
          { id: "maintenance", label: `Maintenance (${maintenanceSchedule.length})` },
          { id: "tickets", label: `Assigned Tickets (${networkTickets.length})` },
          { id: "reports", label: "Diagnostic Reports" },
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
      {/* TAB 1: Network Overview                                           */}
      {/* ----------------------------------------------------------------- */}
      {activeTab === "overview" && (
        <div className="space-y-6">
          {/* Key Health Metrics */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            <div className="p-4 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618]">
              <span className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">Fabric Health</span>
              <div className="text-xl font-bold mt-1.5 flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-[#5E7A6A]"></span>
                <span>98.6% Nominal</span>
              </div>
              <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] mt-1">
                Zero unhandled link drops
              </div>
            </div>

            <div className="p-4 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618]">
              <span className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">Active Incidents</span>
              <div className="text-xl font-bold mt-1.5 text-[#A08A5B]">
                {activeIncidents.length}
              </div>
              <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] mt-1">
                Requiring engineering triage
              </div>
            </div>

            <div className="p-4 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618]">
              <span className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">Warning Devices</span>
              <div className="text-xl font-bold mt-1.5">
                {criticalOrWarningDevices.length}
              </div>
              <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] mt-1">
                {criticalOrWarningDevices.length > 0 ? "Elevated telemetry detected" : "All switches nominal"}
              </div>
            </div>

            <div className="p-4 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618]">
              <span className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">Affected Locations</span>
              <div className="text-base font-bold mt-1.5">Hostel Block B</div>
              <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] mt-1">Academic Complex normal</div>
            </div>

            <div className="p-4 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618]">
              <span className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">Current Maintenance</span>
              <div className="text-xl font-bold mt-1.5">
                {maintenanceSchedule.length} Windows
              </div>
              <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] mt-1">Next: Sunday 02:00 UTC</div>
            </div>
          </div>

          {/* Primary Action Card */}
          <div className="p-4 border border-[#475569] bg-[#FAFAF9] dark:bg-[#0F0F10] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <div className="text-xs font-bold uppercase tracking-wider text-[#111111] dark:text-[#EDEDEA]">
                Operational Priority: Active Congestion Incident Detected
              </div>
              <div className="text-xs text-[#6B6B66] dark:text-[#888884] mt-0.5">
                Incident <code>inc-link-congestion-42</code> on SW_CAMPUS_1 requires operator review and approval.
              </div>
            </div>
            <button
              onClick={() => onNavigate && onNavigate("role_engineer")}
              className="px-4 py-2 bg-[#0B2545] hover:bg-[#133E87] text-white text-xs font-bold uppercase tracking-wider transition-colors whitespace-nowrap"
            >
              Investigate Active Incidents &rarr;
            </button>
          </div>

          {/* Critical Devices Quick Summary */}
          <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-4">
            <h3 className="text-xs font-bold uppercase tracking-wider mb-3">Campus Infrastructure Health Summary</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
              <div className="p-3 border border-[#E5E5E3] dark:border-[#2A2A2D] flex items-center justify-between">
                <div>
                  <div className="font-bold">Core Switches (Spine)</div>
                  <div className="text-[10px] text-[#6B6B66] dark:text-[#888884]">spine-01, spine-02</div>
                </div>
                <span className="px-2 py-0.5 border border-[#5E7A6A] text-[#5E7A6A] text-[10px] uppercase font-semibold">
                  Online
                </span>
              </div>
              <div className="p-3 border border-[#E5E5E3] dark:border-[#2A2A2D] flex items-center justify-between">
                <div>
                  <div className="font-bold">Distribution Switches (Leaf)</div>
                  <div className="text-[10px] text-[#6B6B66] dark:text-[#888884]">leaf-01, leaf-02, leaf-03</div>
                </div>
                <span className="px-2 py-0.5 border border-[#5E7A6A] text-[#5E7A6A] text-[10px] uppercase font-semibold">
                  Online
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* TAB 2: Active Incidents                                           */}
      {/* ----------------------------------------------------------------- */}
      {activeTab === "incidents" && (
        <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618]">
          <div className="p-4 border-b border-[#E5E5E3] dark:border-[#2A2A2D] flex items-center justify-between">
            <h3 className="text-sm font-bold uppercase tracking-wider">Active Operational Incidents</h3>
            <span className="text-xs text-[#6B6B66] dark:text-[#888884]">{incidents.length} Persisted</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#FAFAF9] dark:bg-[#0F0F10] border-b border-[#E5E5E3] dark:border-[#2A2A2D] text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">
                <tr>
                  <th className="p-3">Incident ID</th>
                  <th className="p-3">Status</th>
                  <th className="p-3">Probable Cause</th>
                  <th className="p-3">Assigned Operator</th>
                  <th className="p-3 text-right">Engineering Triage</th>
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
                    <td className="p-3">{inc.probable_cause || "Telemetry investigation active"}</td>
                    <td className="p-3">{inc.assigned_to || "Unassigned"}</td>
                    <td className="p-3 text-right">
                      <button
                        onClick={() => onNavigate && onNavigate("role_engineer")}
                        className="px-2 py-1 border border-[#475569] text-[#475569] dark:text-[#94A3B8] hover:bg-[#475569]/10 text-[10px] uppercase font-semibold"
                      >
                        Inspect Triage &rarr;
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* TAB 3: Devices & Topology (Searchable & Filterable)               */}
      {/* ----------------------------------------------------------------- */}
      {activeTab === "devices" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618]">
            <div className="p-4 border-b border-[#E5E5E3] dark:border-[#2A2A2D] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <h3 className="text-sm font-bold uppercase tracking-wider">Device Inventory</h3>
                <p className="text-xs text-[#6B6B66] dark:text-[#888884]">Physical &amp; virtual fabric elements</p>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  placeholder="Filter hostname or ID..."
                  value={deviceSearch}
                  onChange={(e) => setDeviceSearch(e.target.value)}
                  className="px-2.5 py-1 text-xs border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10] focus:border-[#475569] outline-none"
                />
                <select
                  value={deviceRoleFilter}
                  onChange={(e) => setDeviceRoleFilter(e.target.value)}
                  className="px-2 py-1 text-xs border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10] focus:border-[#475569] outline-none"
                >
                  <option value="all">All Roles</option>
                  <option value="spine">Spine</option>
                  <option value="leaf">Leaf</option>
                  <option value="edge_router">Edge Router</option>
                </select>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-[#FAFAF9] dark:bg-[#0F0F10] border-b border-[#E5E5E3] dark:border-[#2A2A2D] text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">
                  <tr>
                    <th className="p-3">Device Name</th>
                    <th className="p-3">Role</th>
                    <th className="p-3">Status</th>
                    <th className="p-3">IP Address</th>
                    <th className="p-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E5E5E3] dark:divide-[#2A2A2D]">
                  {loading && (
                    <tr>
                      <td colSpan={5} className="p-4 text-center text-[#6B6B66] dark:text-[#888884]">
                        Loading campus network telemetry and inventory...
                      </td>
                    </tr>
                  )}
                  {!loading && filteredDevices.length === 0 && (
                    <tr>
                      <td colSpan={5} className="p-4 text-center text-[#6B6B66] dark:text-[#888884]">
                        No network devices matching search criteria.
                      </td>
                    </tr>
                  )}
                  {filteredDevices.map((d) => (
                    <tr
                      key={d.device_id}
                      onClick={() => setSelectedDevice(d)}
                      className={`cursor-pointer hover:bg-[#FAFAF9] dark:hover:bg-[#0F0F10] ${
                        selectedDevice?.device_id === d.device_id ? "bg-[#FAFAF9] dark:bg-[#0F0F10]" : ""
                      }`}
                    >
                      <td className="p-3 font-bold font-mono">
                        {d.device_id}
                        <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] font-normal">{d.hostname}</div>
                      </td>
                      <td className="p-3 uppercase text-[10px] font-semibold">{d.role}</td>
                      <td className="p-3">
                        <span className="px-1.5 py-0.5 border border-[#5E7A6A] text-[#5E7A6A] text-[9px] uppercase font-semibold">
                          {d.status}
                        </span>
                      </td>
                      <td className="p-3 font-mono">{d.ip_address}</td>
                      <td className="p-3 text-right">
                        <button className="text-[10px] text-[#475569] dark:text-[#94A3B8] font-semibold hover:underline">
                          Select &rarr;
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Selected Device Details Inspector */}
          {selectedDevice && (
            <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-4 space-y-4">
              <div className="pb-3 border-b border-[#E5E5E3] dark:border-[#2A2A2D]">
                <span className="text-[10px] uppercase font-bold text-[#6B6B66] dark:text-[#888884]">
                  Device Telemetry &amp; Specs
                </span>
                <h4 className="text-base font-bold font-mono mt-0.5">{selectedDevice.device_id}</h4>
                <div className="text-[11px] text-[#6B6B66] dark:text-[#888884]">{selectedDevice.vendor}</div>
              </div>

              <div className="space-y-3 text-xs">
                <div>
                  <div className="flex justify-between text-[11px] mb-1">
                    <span>CPU Utilization</span>
                    <span className="font-bold">{selectedDevice.cpu_utilization_pct}%</span>
                  </div>
                  <div className="w-full bg-[#E5E5E3] dark:bg-[#2A2A2D] h-1.5">
                    <div
                      className={`h-1.5 ${selectedDevice.cpu_utilization_pct > 75 ? "bg-[#9A5B5B]" : "bg-[#475569]"}`}
                      style={{ width: `${selectedDevice.cpu_utilization_pct}%` }}
                    ></div>
                  </div>
                </div>

                <div>
                  <div className="flex justify-between text-[11px] mb-1">
                    <span>Memory Utilization</span>
                    <span className="font-bold">{selectedDevice.memory_utilization_pct}%</span>
                  </div>
                  <div className="w-full bg-[#E5E5E3] dark:bg-[#2A2A2D] h-1.5">
                    <div
                      className="h-1.5 bg-[#475569]"
                      style={{ width: `${selectedDevice.memory_utilization_pct}%` }}
                    ></div>
                  </div>
                </div>

                <div className="pt-2 border-t border-[#E5E5E3] dark:border-[#2A2A2D] space-y-1.5 text-[11px]">
                  <div className="flex justify-between">
                    <span className="text-[#6B6B66] dark:text-[#888884]">Port Interfaces:</span>
                    <span className="font-bold">{selectedDevice.interfaces_count} GbE</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#6B6B66] dark:text-[#888884]">Maintenance Mode:</span>
                    <span className="font-bold">{selectedDevice.maintenance_mode ? "ACTIVE" : "INACTIVE"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#6B6B66] dark:text-[#888884]">Last Config Commit:</span>
                    <span className="font-mono text-[10px]">{selectedDevice.last_config_change}</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* TAB 4: Telemetry & Performance                                    */}
      {/* ----------------------------------------------------------------- */}
      {activeTab === "telemetry" && (
        <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-5 space-y-4">
          <h3 className="text-sm font-bold uppercase tracking-wider">Fabric Port Interface Telemetry</h3>
          <p className="text-xs text-[#6B6B66] dark:text-[#888884]">
            High-precision queue depth, interface counters, and drop statistics.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
            <div className="p-3 border border-[#E5E5E3] dark:border-[#2A2A2D] space-y-1">
              <span className="text-[10px] text-[#6B6B66] dark:text-[#888884] uppercase">SW_CAMPUS_1 (Port xe-0/0/1)</span>
              <div className="text-base font-bold text-[#A08A5B]">89.4% Bandwidth Saturation</div>
              <div className="text-[10px] text-[#6B6B66] dark:text-[#888884]">Queue drops: 4,120 pkts/sec &bull; Baseline: 0</div>
            </div>
            <div className="p-3 border border-[#E5E5E3] dark:border-[#2A2A2D] space-y-1">
              <span className="text-[10px] text-[#6B6B66] dark:text-[#888884]">spine-01 (Port xe-0/0/2)</span>
              <div className="text-base font-bold text-[#5E7A6A]">34.2% Utilization</div>
              <div className="text-[10px] text-[#6B6B66] dark:text-[#888884]">Queue drops: 0 pkts/sec &bull; Nominal</div>
            </div>
            <div className="p-3 border border-[#E5E5E3] dark:border-[#2A2A2D] space-y-1">
              <span className="text-[10px] text-[#6B6B66] dark:text-[#888884]">leaf-01 (Port et-0/0/1)</span>
              <div className="text-base font-bold text-[#5E7A6A]">42.0% Utilization</div>
              <div className="text-[10px] text-[#6B6B66] dark:text-[#888884]">Queue drops: 0 pkts/sec &bull; Nominal</div>
            </div>
          </div>
        </div>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* TAB 5: Maintenance Scheduling (with Confirmation Workflow)        */}
      {/* ----------------------------------------------------------------- */}
      {activeTab === "maintenance" && (
        <div className="space-y-6">
          <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-5">
            <h3 className="text-sm font-bold uppercase tracking-wider mb-2">Schedule Maintenance Window</h3>
            <p className="text-xs text-[#6B6B66] dark:text-[#888884] mb-4">
              Schedule planned device offline maintenance with explicit operator confirmation.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
              <div>
                <label className="block text-[10px] uppercase font-bold text-[#6B6B66] dark:text-[#888884] mb-1">
                  Target Device
                </label>
                <select
                  value={newMaintDevice}
                  onChange={(e) => setNewMaintDevice(e.target.value)}
                  className="w-full p-2 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10] focus:border-[#475569] outline-none"
                >
                  {devices.map((d) => (
                    <option key={d.device_id} value={d.device_id}>
                      {d.device_id} ({d.hostname})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-[10px] uppercase font-bold text-[#6B6B66] dark:text-[#888884] mb-1">
                  Reason for Maintenance
                </label>
                <input
                  type="text"
                  placeholder="e.g. SFP optics cleaning and optics reseat"
                  value={newMaintReason}
                  onChange={(e) => setNewMaintReason(e.target.value)}
                  className="w-full p-2 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10] focus:border-[#475569] outline-none"
                />
              </div>

              <div className="flex items-end">
                <button
                  type="button"
                  disabled={!newMaintReason.trim()}
                  onClick={() => setShowMaintConfirm(true)}
                  className="w-full p-2 bg-[#0B2545] hover:bg-[#133E87] disabled:opacity-40 text-white font-bold uppercase tracking-wider text-xs transition-colors"
                >
                  Schedule Window...
                </button>
              </div>
            </div>
          </div>

          <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618]">
            <div className="p-4 border-b border-[#E5E5E3] dark:border-[#2A2A2D]">
              <h3 className="text-sm font-bold uppercase tracking-wider">Confirmed Maintenance Windows</h3>
            </div>
            <div className="divide-y divide-[#E5E5E3] dark:divide-[#2A2A2D] text-xs">
              {maintenanceSchedule.map((m) => (
                <div key={m.id} className="p-4 flex items-center justify-between">
                  <div>
                    <div className="font-bold font-mono">{m.device}</div>
                    <div className="text-[#6B6B66] dark:text-[#888884] text-[11px] mt-0.5">{m.reason}</div>
                  </div>
                  <span className="px-2 py-1 border border-[#475569] text-[10px] uppercase font-semibold">
                    {m.window}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Confirmation Modal */}
          {showMaintConfirm && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
              <div className="w-full max-w-md bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D] p-6 shadow-xl space-y-4">
                <h4 className="text-sm font-bold uppercase tracking-wider text-[#9A5B5B]">
                  Confirm Maintenance Window
                </h4>
                <p className="text-xs text-[#6B6B66] dark:text-[#888884]">
                  Are you sure you want to schedule maintenance for <strong>{newMaintDevice}</strong>? Traffic routing will be diverted via ECMP alternate paths during this window.
                </p>
                <div className="p-3 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] text-xs space-y-1">
                  <div>Target Device: <code className="font-bold">{newMaintDevice}</code></div>
                  <div>Rationale: <em>{newMaintReason}</em></div>
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <button
                    onClick={() => setShowMaintConfirm(false)}
                    className="px-3 py-1.5 border border-[#E5E5E3] dark:border-[#2A2A2D] text-xs font-semibold uppercase"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleConfirmScheduleMaintenance}
                    className="px-4 py-1.5 bg-[#0B2545] hover:bg-[#133E87] text-white text-xs font-bold uppercase tracking-wider"
                  >
                    Confirm &amp; Schedule
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* TAB 6: Assigned Support Tickets                                   */}
      {/* ----------------------------------------------------------------- */}
      {activeTab === "tickets" && (
        <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618]">
          <div className="p-4 border-b border-[#E5E5E3] dark:border-[#2A2A2D] flex items-center justify-between">
            <h3 className="text-sm font-bold uppercase tracking-wider">Network Infrastructure Support Tickets</h3>
            <span className="text-xs text-[#6B6B66] dark:text-[#888884]">{networkTickets.length} Tickets</span>
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
                  <th className="p-3">Linked Incident</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E5E5E3] dark:divide-[#2A2A2D]">
                {networkTickets.map((t) => (
                  <tr key={t.ticket_id} className="hover:bg-[#FAFAF9] dark:hover:bg-[#0F0F10]">
                    <td className="p-3 font-bold font-mono">{t.ticket_id}</td>
                    <td className="p-3">{t.title}</td>
                    <td className="p-3">{t.location}</td>
                    <td className="p-3">
                      <span className={`px-1.5 py-0.5 border text-[9px] uppercase font-semibold ${
                        t.priority === "critical" ? "border-[#9A5B5B] text-[#9A5B5B]" : "border-[#A08A5B] text-[#A08A5B]"
                      }`}>
                        {t.priority}
                      </span>
                    </td>
                    <td className="p-3">
                      <span className="px-1.5 py-0.5 border border-[#475569] text-[9px] uppercase font-semibold">
                        {t.status}
                      </span>
                    </td>
                    <td className="p-3 font-mono">{t.linked_incident_id || "None"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* TAB 7: Diagnostic Reports                                         */}
      {/* ----------------------------------------------------------------- */}
      {activeTab === "reports" && (
        <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-5 space-y-4">
          <h3 className="text-sm font-bold uppercase tracking-wider">Unified Diagnostic Reports</h3>
          <p className="text-xs text-[#6B6B66] dark:text-[#888884]">
            Synthesized reports produced by multi-agent diagnostic consensus.
          </p>
          <div className="p-4 border border-[#E5E5E3] dark:border-[#2A2A2D] flex items-center justify-between">
            <div>
              <div className="font-bold text-xs">Diagnostic Quality Report (Version 2)</div>
              <div className="text-[11px] text-[#6B6B66] dark:text-[#888884] mt-0.5">
                Evaluates schema conformance, agent corroboration count, and conformal uncertainty intervals.
              </div>
            </div>
            {onNavigate && (
              <button
                onClick={() => onNavigate("report")}
                className="px-3 py-1.5 border border-[#475569] text-[#475569] dark:text-[#94A3B8] hover:bg-[#475569]/10 text-xs uppercase font-semibold"
              >
                Open Unified Report &rarr;
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
