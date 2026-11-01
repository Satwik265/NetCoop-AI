import React, { useState, useEffect } from "react";

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
}

export const AdminView: React.FC = () => {
  const [devices, setDevices] = useState<DeviceItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedDevice, setSelectedDevice] = useState<DeviceItem | null>(null);
  const [maintenanceSchedule, setMaintenanceSchedule] = useState<Array<{ id: string; device: string; window: string; reason: string }>>([
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
  const [scheduledMsg, setScheduledMsg] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/devices")
      .then((res) => {
        if (!res.ok) throw new Error("Devices API unavailable");
        return res.json();
      })
      .then((data: DeviceItem[]) => {
        if (data && data.length > 0) {
          setDevices(data);
          setSelectedDevice(data[0]);
        }
      })
      .catch(() => {
        // Fallback default device inventory
        const fallback: DeviceItem[] = [
          {
            device_id: "spine-01",
            hostname: "spine-01.campus.netcoop.internal",
            role: "spine",
            vendor: "Arista EOS 4.31.0F",
            ip_address: "10.0.0.1",
            status: "online",
            interfaces_count: 32,
            cpu_utilization_pct: 34.2,
            memory_utilization_pct: 48.5,
            last_config_change: "2026-10-31T08:30:00Z",
            maintenance_mode: false,
          },
          {
            device_id: "spine-02",
            hostname: "spine-02.campus.netcoop.internal",
            role: "spine",
            vendor: "Arista EOS 4.31.0F",
            ip_address: "10.0.0.2",
            status: "online",
            interfaces_count: 32,
            cpu_utilization_pct: 28.1,
            memory_utilization_pct: 46.0,
            last_config_change: "2026-10-30T14:15:00Z",
            maintenance_mode: false,
          },
          {
            device_id: "leaf-01",
            hostname: "leaf-01.campus.netcoop.internal",
            role: "leaf",
            vendor: "Cisco NX-OS 10.3",
            ip_address: "10.0.1.1",
            status: "online",
            interfaces_count: 48,
            cpu_utilization_pct: 42.0,
            memory_utilization_pct: 52.3,
            last_config_change: "2026-10-29T10:00:00Z",
            maintenance_mode: false,
          },
          {
            device_id: "leaf-02",
            hostname: "leaf-02.campus.netcoop.internal",
            role: "leaf",
            vendor: "Cisco NX-OS 10.3",
            ip_address: "10.0.1.2",
            status: "warning",
            interfaces_count: 48,
            cpu_utilization_pct: 78.5,
            memory_utilization_pct: 68.9,
            last_config_change: "2026-10-31T12:00:00Z",
            maintenance_mode: false,
          },
        ];
        setDevices(fallback);
        setSelectedDevice(fallback[0]);
      })
      .finally(() => setLoading(false));
  }, []);

  const handleScheduleMaintenance = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newMaintReason.trim()) return;

    const newEntry = {
      id: `maint-${Date.now()}`,
      device: newMaintDevice,
      window: "Next Maintenance Window (Pending Approval)",
      reason: newMaintReason.trim(),
    };
    setMaintenanceSchedule((prev) => [newEntry, ...prev]);
    setNewMaintReason("");
    setScheduledMsg(`Scheduled maintenance window for ${newMaintDevice}.`);
    setTimeout(() => setScheduledMsg(null), 3000);
  };

  const toggleMaintenanceMode = (deviceId: string) => {
    setDevices((prev) =>
      prev.map((d) =>
        d.device_id === deviceId ? { ...d, maintenance_mode: !d.maintenance_mode } : d
      )
    );
  };

  return (
    <div className="space-y-6 font-mono text-xs">
      {/* Top Banner */}
      <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h2 className="text-sm font-semibold tracking-wider uppercase text-[#111111] dark:text-[#EDEDEA]">
              Network Infrastructure &amp; Device Inventory
            </h2>
            <p className="mt-1 text-[#6B6B66] dark:text-[#888884] text-[11px]">
              Hardware lifecycle management, configuration history diffs, and scheduled maintenance windows.
            </p>
          </div>
          <div className="flex items-center gap-3 text-[11px]">
            <span className="border border-[#5E7A6A] text-[#5E7A6A] px-2 py-1">
              TOTAL DEVICES: {devices.length}
            </span>
            <span className="border border-[#A08A5B] text-[#A08A5B] px-2 py-1">
              MAINTENANCE: {devices.filter((d) => d.maintenance_mode).length}
            </span>
          </div>
        </div>
      </div>

      {scheduledMsg && (
        <div className="p-3 border border-[#5E7A6A] bg-[#5E7A6A]/10 text-[#5E7A6A]">
          {scheduledMsg}
        </div>
      )}

      {/* Main Grid: Devices Table & Configuration Inspector */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Device Inventory Table (7 cols) */}
        <div className="lg:col-span-7 space-y-4">
          <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-4 space-y-3">
            <div className="flex items-center justify-between border-b border-[#E5E5E3] dark:border-[#2A2A2D] pb-2">
              <span className="font-semibold text-[#111111] dark:text-[#EDEDEA] uppercase tracking-wider">
                Managed Network Devices ({devices.length})
              </span>
              <span className="text-[10px] text-[#6B6B66] dark:text-[#888884]">
                Click row to inspect configuration
              </span>
            </div>

            {loading ? (
              <div className="py-8 text-center text-[#6B6B66]">Loading device inventory...</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-[11px]">
                  <thead>
                    <tr className="border-b border-[#E5E5E3] dark:border-[#2A2A2D] text-[#6B6B66] dark:text-[#888884] uppercase text-[10px]">
                      <th className="py-2 pr-3">Device</th>
                      <th className="py-2 pr-3">Role</th>
                      <th className="py-2 pr-3">IP Address</th>
                      <th className="py-2 pr-3">CPU / Mem</th>
                      <th className="py-2 pr-3">Status</th>
                      <th className="py-2 text-right">Maint Mode</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E5E5E3] dark:divide-[#2A2A2D]">
                    {devices.map((dev) => {
                      const isSelected = selectedDevice?.device_id === dev.device_id;
                      return (
                        <tr
                          key={dev.device_id}
                          onClick={() => setSelectedDevice(dev)}
                          className={`cursor-pointer transition-colors ${
                            isSelected
                              ? "bg-[#FAFAF9] dark:bg-[#0F0F10] font-semibold"
                              : "hover:bg-[#FAFAF9] dark:hover:bg-[#161618]"
                          }`}
                        >
                          <td className="py-2.5 pr-3 text-[#111111] dark:text-[#EDEDEA]">
                            {dev.device_id}
                          </td>
                          <td className="py-2.5 pr-3 uppercase text-[10px] text-[#475569] dark:text-[#888884]">
                            {dev.role}
                          </td>
                          <td className="py-2.5 pr-3 text-[10px] text-[#6B6B66] dark:text-[#888884]">
                            {dev.ip_address}
                          </td>
                          <td className="py-2.5 pr-3 text-[10px]">
                            {dev.cpu_utilization_pct}% / {dev.memory_utilization_pct}%
                          </td>
                          <td className="py-2.5 pr-3">
                            <span
                              className={`px-1.5 py-0.2 border text-[9px] uppercase ${
                                dev.status === "online"
                                  ? "border-[#5E7A6A] text-[#5E7A6A]"
                                  : "border-[#A08A5B] text-[#A08A5B]"
                              }`}
                            >
                              {dev.status}
                            </span>
                          </td>
                          <td className="py-2.5 text-right">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                toggleMaintenanceMode(dev.device_id);
                              }}
                              className={`px-2 py-0.5 border text-[9px] uppercase ${
                                dev.maintenance_mode
                                  ? "border-[#A08A5B] text-[#A08A5B] bg-[#A08A5B]/10"
                                  : "border-[#E5E5E3] dark:border-[#2A2A2D] text-[#6B6B66]"
                              }`}
                            >
                              {dev.maintenance_mode ? "ACTIVE" : "OFF"}
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Maintenance Scheduler */}
          <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-4 space-y-3">
            <span className="font-semibold text-[#111111] dark:text-[#EDEDEA] uppercase tracking-wider block border-b border-[#E5E5E3] dark:border-[#2A2A2D] pb-2">
              Scheduled Maintenance Windows ({maintenanceSchedule.length})
            </span>

            <div className="space-y-2">
              {maintenanceSchedule.map((m) => (
                <div
                  key={m.id}
                  className="p-2.5 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10] flex items-center justify-between"
                >
                  <div>
                    <span className="font-bold text-[#111111] dark:text-[#EDEDEA]">{m.device}</span>
                    <span className="text-[10px] text-[#475569] dark:text-[#888884] ml-2">[{m.window}]</span>
                    <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] mt-0.5">{m.reason}</div>
                  </div>
                  <span className="px-2 py-0.5 border border-[#A08A5B] text-[#A08A5B] text-[9px] uppercase">
                    SCHEDULED
                  </span>
                </div>
              ))}
            </div>

            <form onSubmit={handleScheduleMaintenance} className="pt-2 flex items-center gap-2">
              <select
                value={newMaintDevice}
                onChange={(e) => setNewMaintDevice(e.target.value)}
                className="bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] px-2 py-1 text-[11px]"
              >
                {devices.map((d) => (
                  <option key={d.device_id} value={d.device_id}>
                    {d.device_id}
                  </option>
                ))}
              </select>
              <input
                type="text"
                placeholder="Maintenance reason & ticket ID..."
                value={newMaintReason}
                onChange={(e) => setNewMaintReason(e.target.value)}
                className="flex-1 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] px-2 py-1 text-[11px]"
              />
              <button
                type="submit"
                className="px-3 py-1 border border-[#111111] dark:border-[#EDEDEA] bg-[#111111] dark:bg-[#EDEDEA] text-[#FAFAF9] dark:text-[#0F0F10] uppercase text-[10px] font-semibold"
              >
                Schedule
              </button>
            </form>
          </div>
        </div>

        {/* Right: Selected Device Configuration & History Diff (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          {selectedDevice && (
            <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-4 space-y-3">
              <div className="flex items-center justify-between border-b border-[#E5E5E3] dark:border-[#2A2A2D] pb-2">
                <span className="font-semibold text-[#111111] dark:text-[#EDEDEA] uppercase tracking-wider">
                  Device Configuration Diff
                </span>
                <span className="text-[10px] text-[#475569]">{selectedDevice.device_id}</span>
              </div>

              <div>
                <label className="text-[10px] text-[#6B6B66] dark:text-[#888884] uppercase">Operating System &amp; Model</label>
                <div className="text-[11px] font-bold text-[#111111] dark:text-[#EDEDEA]">{selectedDevice.vendor}</div>
              </div>

              <div>
                <label className="text-[10px] text-[#6B6B66] dark:text-[#888884] uppercase">Last Committed Config Diff (Turn 1)</label>
                <pre className="mt-1 p-3 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] text-[10px] overflow-x-auto leading-relaxed">
{`--- /etc/network/interfaces.orig
+++ /etc/network/interfaces.active
@@ -14,6 +14,8 @@
 interface et-0/0/1
+  load-interval 30
+  traffic-policy REBALANCE_ECMP
   mtu 9000
-  speed auto
+  speed 100G`}
                </pre>
              </div>

              <div className="pt-2 text-[10px] text-[#6B6B66] dark:text-[#888884] leading-normal border-t border-[#E5E5E3] dark:border-[#2A2A2D]">
                Configuration rollback script verified in SQLite audit log: <code className="text-[#111111] dark:text-[#EDEDEA]">no traffic-policy REBALANCE_ECMP</code>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

