import React, { useEffect, useState } from "react";

export const ProtocolViewer: React.FC = () => {
  const [selectedSchema, setSelectedSchema] = useState<string>("envelope");
  const [schemaContent, setSchemaContent] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(false);

  useEffect(() => {
    setLoading(true);
    fetch(`/api/schemas/${selectedSchema}`)
      .then((res) => res.json())
      .then((data) => {
        setSchemaContent(data);
        setLoading(false);
      })
      .catch(() => {
        setSchemaContent({ error: "Failed to load schema" });
        setLoading(false);
      });
  }, [selectedSchema]);

  return (
    <div className="bg-[#161618] border border-[#2A2A2D] p-5">
      <div className="flex flex-wrap items-center justify-between border-b border-[#2A2A2D] pb-3 mb-4 gap-3">
        <div>
          <h2 className="text-sm font-semibold tracking-wide uppercase font-mono text-[#EDEDEA]">
            Protocol Specification & JSON Schemas
          </h2>
          <div className="text-xs text-[#888884] font-mono mt-0.5">
            Interoperability standard: NetCoop Envelope v1.0.0
          </div>
        </div>

        <div className="flex gap-2">
          {["envelope", "telemetry", "diagnostic_report", "remediation_plan"].map(
            (s) => (
              <button
                key={s}
                onClick={() => setSelectedSchema(s)}
                className={`px-3 py-1 text-xs font-mono uppercase tracking-wider transition-colors ${
                  selectedSchema === s
                    ? "bg-[#475569] text-white"
                    : "bg-[#0F0F10] border border-[#2A2A2D] text-[#888884] hover:text-[#EDEDEA]"
                }`}
              >
                {s.replace("_", " ")}
              </button>
            )
          )}
        </div>
      </div>

      <div className="bg-[#0F0F10] border border-[#2A2A2D] p-4 text-xs font-mono overflow-x-auto max-h-[500px]">
        {loading ? (
          <div className="text-[#888884] py-8 text-center">Loading formal JSON schema...</div>
        ) : (
          <pre className="text-[#EDEDEA] leading-relaxed">
            {JSON.stringify(schemaContent, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
};

