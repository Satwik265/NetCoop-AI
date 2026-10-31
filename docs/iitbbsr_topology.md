# IIT Bhubaneswar Demonstration Campus Topology Specification

## 1. Overview and Operational Context

This document defines the demonstration network topology model for the Indian Institute of Technology Bhubaneswar (IIT Bhubaneswar, Argul campus) within the NetCoop AI framework.

The dataset provides a source-aware, structured network architecture designed for:
- Multi-agent root-cause diagnosis and anomaly classification demonstrations.
- Interactive dashboard canvas rendering for topology visualization.
- Fault propagation modeling across hierarchical campus tiers.

All files are structured under:
- Dataset: `data/campus/iitbbsr_demo_topology.json`
- Schema: `schemas/campus_topology.schema.json`
- Test Fixture: `tests/test_iitbbsr_topology_fixture.py`

## 2. Provenance and Source Disclaimers

### 2.1 Official Source References

The physical landmarks, building names, and campus zone designations are derived directly from official public references published by IIT Bhubaneswar:
- About Campus: [https://www.iitbbs.ac.in/index.php/home/about-campus/](https://www.iitbbs.ac.in/index.php/home/about-campus/)
- Campus Master Plan: [https://www.iitbbs.ac.in/wp-content/uploads/2025/07/Master-Plan-IITBBS-scaled.jpg](https://www.iitbbs.ac.in/wp-content/uploads/2025/07/Master-Plan-IITBBS-scaled.jpg)
- Campus Route Map: [https://www.iitbbs.ac.in/wp-content/uploads/2025/10/Route-2.jpg](https://www.iitbbs.ac.in/wp-content/uploads/2025/10/Route-2.jpg)

### 2.2 Synthetic Inventory Disclaimer

Important Notice:
1. Official campus maps establish civil architectural footprints, road access, and building nomenclature only.
2. Official maps contain zero IT network equipment records, router locations, or optical fiber routing paths.
3. All routers, link interconnections, and routing paths described in this specification are synthetic demonstration inventory created exclusively for the NetCoop AI multi-agent incident diagnosis research prototype.
4. No actual security-sensitive infrastructure data is exposed or fabricated as empirical truth.

## 3. Supported Campus Locations

The topology references 9 supported campus locations verified against official IIT Bhubaneswar campus maps:
1. Administrative Building
2. IIT Bhubaneswar Auditorium
3. School of Basic Sciences
4. School of Infrastructure
5. School of Mechanical Sciences
6. Central Workshop
7. Rushikulya Hall of Residence
8. Academic zone
9. Residential zone

## 4. Router Naming Convention and Inventory Aliases

All routers adhere to the deterministic regex pattern:
`^IITBBSR-(CORE|AGG|DIST)-[A-Z0-9]+-[0-9]{2}$`

- `IITBBSR`: Campus identifier prefix (IIT Bhubaneswar).
- `CORE | AGG | DIST`: Tier designation (Core, Aggregation, Distribution).
- `[A-Z0-9]+`: Zone or building mnemonic.
- `[0-9]{2}`: Two-digit zero-padded instance index.

### 4.1 Demonstration Inventory Table

| Node ID | Display Name | Role | Site / Zone Name | Normalized (X, Y) | Description / Function |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `IITBBSR-CORE-RTR-01` | Campus Core Router 01 | Core | Administrative Building | (0.50, 0.35) | Central campus backbone router and gateway to NKN/ISP |
| `IITBBSR-AGG-ACAD-01` | Academic Zone Aggregation Router 01 | Aggregation | Academic zone | (0.32, 0.50) | Aggregates traffic from academic schools and workshop facilities |
| `IITBBSR-AGG-RES-01` | Residential Zone Aggregation Router 01 | Aggregation | Residential zone | (0.68, 0.55) | Aggregates traffic from student halls of residence and faculty quarters |
| `IITBBSR-DIST-ADMIN-01` | Administrative Building Distribution Router 01 | Distribution | Administrative Building | (0.50, 0.18) | Local LAN distribution for administrative offices and registrar |
| `IITBBSR-DIST-SBS-01` | School of Basic Sciences Distribution Router 01 | Distribution | School of Basic Sciences | (0.18, 0.42) | Departmental distribution for physics, chemistry, mathematics labs |
| `IITBBSR-DIST-SIF-01` | School of Infrastructure Distribution Router 01 | Distribution | School of Infrastructure | (0.18, 0.58) | Departmental distribution for civil and environmental engineering |
| `IITBBSR-DIST-SMS-01` | School of Mechanical Sciences Distribution Router 01 | Distribution | School of Mechanical Sciences | (0.32, 0.72) | Departmental distribution for mechanical engineering computing |
| `IITBBSR-DIST-AUD-01` | Auditorium Distribution Router 01 | Distribution | IIT Bhubaneswar Auditorium | (0.65, 0.22) | Local distribution for campus auditorium and event venues |
| `IITBBSR-DIST-CW-01` | Central Workshop Distribution Router 01 | Distribution | Central Workshop | (0.18, 0.78) | Industrial lab and fabrication facility distribution |
| `IITBBSR-DIST-RHR-01` | Rushikulya Hall of Residence Distribution Router 01 | Distribution | Rushikulya Hall of Residence | (0.82, 0.75) | Student residential network and hostel Wi-Fi distribution |

## 5. Physical and Logical Topology Hierarchy

The demonstration network is organized into a three-tier hierarchical architecture:

```
                  [ IITBBSR-CORE-RTR-01 ] (Administrative Building)
                     /         |          \
                    /          |           \
 [IITBBSR-DIST-ADMIN-01]       |       [IITBBSR-DIST-AUD-01]
                               |
              +----------------+----------------+
              |                                 |
   [ IITBBSR-AGG-ACAD-01 ] <=======> [ IITBBSR-AGG-RES-01 ]
      (Academic Zone)       (Interlink)   (Residential Zone)
      /    |     \    \                             |
     /     |      \    \                            |
 [SBS]   [SIF]   [SMS] [CW]                       [RHR]
```

### 5.1 Links Inventory

| Source Node | Target Node | Link Type | Simulated | Initial Status |
| :--- | :--- | :--- | :--- | :--- |
| `IITBBSR-CORE-RTR-01` | `IITBBSR-AGG-ACAD-01` | `core_aggregation_trunk` | true | unknown |
| `IITBBSR-CORE-RTR-01` | `IITBBSR-AGG-RES-01` | `core_aggregation_trunk` | true | unknown |
| `IITBBSR-CORE-RTR-01` | `IITBBSR-DIST-ADMIN-01` | `core_distribution_link` | true | unknown |
| `IITBBSR-CORE-RTR-01` | `IITBBSR-DIST-AUD-01` | `core_distribution_link` | true | unknown |
| `IITBBSR-AGG-ACAD-01` | `IITBBSR-DIST-SBS-01` | `aggregation_distribution_link` | true | unknown |
| `IITBBSR-AGG-ACAD-01` | `IITBBSR-DIST-SIF-01` | `aggregation_distribution_link` | true | unknown |
| `IITBBSR-AGG-ACAD-01` | `IITBBSR-DIST-SMS-01` | `aggregation_distribution_link` | true | unknown |
| `IITBBSR-AGG-ACAD-01` | `IITBBSR-DIST-CW-01` | `aggregation_distribution_link` | true | unknown |
| `IITBBSR-AGG-RES-01` | `IITBBSR-DIST-RHR-01` | `aggregation_distribution_link` | true | unknown |
| `IITBBSR-AGG-ACAD-01` | `IITBBSR-AGG-RES-01` | `aggregation_interconnect` | true | unknown |

Graph Properties:
- Total Nodes: 10
- Total Links: 10
- Connected Components: 1 (fully connected, zero orphaned nodes)
- Redundancy: Inter-aggregation trunk `IITBBSR-AGG-ACAD-01` <-> `IITBBSR-AGG-RES-01` enables alternate traffic diversion in simulated disaster or failure scenarios.

## 6. Logical Demonstration Routing Path

The dataset defines verified logical routing paths for multi-hop agent diagnostic demonstrations.

### 6.1 Path: `PATH-DEMO-CORE-SBS-01`
- Name: Campus Core to School of Basic Sciences
- Path Type: `simulated_logical_route`
- Hop 1: `IITBBSR-CORE-RTR-01` (Campus Core Router)
- Hop 2: `IITBBSR-AGG-ACAD-01` (Academic Aggregation Router)
- Hop 3: `IITBBSR-DIST-SBS-01` (School of Basic Sciences Router)
- Integrity: Every hop pair corresponds to a verified link in the links table (`IITBBSR-CORE-RTR-01` -> `IITBBSR-AGG-ACAD-01`, and `IITBBSR-AGG-ACAD-01` -> `IITBBSR-DIST-SBS-01`).
- Disclaimer: Simulated logical demonstration route; does not represent physical cable infrastructure.

## 7. Coordinate Space and Visualization Guidelines

To prevent misleading claims of exact physical hardware placement, the layout uses a normalized canvas coordinate system:
- Dimension Range: `x: [0.0, 1.0]`, `y: [0.0, 1.0]`.
- Origin `(0.0, 0.0)`: Top-left of the visual rendering container.
- Absolute geographic coordinates (such as GPS latitude and longitude) are strictly omitted.
- Responsive scaling: The frontend UI computes `pixel_x = node.layout_position.x * container_width` and `pixel_y = node.layout_position.y * container_height`.

## 8. Schema Specification and Validation

The JSON Schema is defined at `schemas/campus_topology.schema.json` using Draft 2020-12:
- Strict validation: `additionalProperties: false` is enforced on root, nodes, links, and logical paths.
- Naming validation: Regex checks on all node identifiers and link endpoints.
- Simulated provenance: All equipment must assert `simulated: true` and `inventory_status: "simulated_demonstration"`.
- Base status integrity: Default initial status for all nodes and links is `"unknown"`. Live telemetry feeds are decoupled from base topology inventory.

Validation suite:
```powershell
.venv\Scripts\python.exe -m pytest tests/test_iitbbsr_topology_fixture.py -v
```

## 9. Proposed Frontend and Dashboard Contract

The dataset is designed for direct ingestion by dashboard components (e.g., Cytoscape.js, D3 force-directed graph, or React Flow).

### 9.1 API Response Envelope Specification

When served via an API endpoint, the response wraps the topology in standard NetCoop API metadata:

```json
{
  "status": "success",
  "data": {
    "schema_version": "1.0.0",
    "campus_id": "iitbbsr_argul_campus",
    "campus_name": "Indian Institute of Technology Bhubaneswar",
    "simulated_inventory": true,
    "layout_coordinate_system": "normalized_canvas_space",
    "nodes": [
      {
        "id": "IITBBSR-CORE-RTR-01",
        "display_name": "Campus Core Router 01",
        "type": "router",
        "role": "core",
        "site_id": "site_admin",
        "site_name": "Administrative Building",
        "layout_position": { "x": 0.5, "y": 0.35 },
        "simulated": true,
        "inventory_status": "simulated_demonstration",
        "status": "unknown"
      }
    ],
    "links": [
      {
        "source": "IITBBSR-CORE-RTR-01",
        "target": "IITBBSR-AGG-ACAD-01",
        "link_type": "core_aggregation_trunk",
        "simulated": true,
        "status": "unknown"
      }
    ],
    "logical_routing_paths": [
      {
        "path_id": "PATH-DEMO-CORE-SBS-01",
        "name": "Campus Core to School of Basic Sciences",
        "description": "Simulated demonstration path routing traffic from Campus Core via Academic Zone Aggregation to School of Basic Sciences Distribution Router.",
        "path_type": "simulated_logical_route",
        "simulated": true,
        "hops": [
          "IITBBSR-CORE-RTR-01",
          "IITBBSR-AGG-ACAD-01",
          "IITBBSR-DIST-SBS-01"
        ],
        "disclaimer": "Simulated logical demonstration route; does not represent physical cable infrastructure."
      }
    ]
  },
  "metadata": {
    "generated_by": "netcoop_campus_modeling",
    "provenance": "simulated_demonstration",
    "disclaimer": "All network equipment is simulated demonstration inventory."
  }
}
```

### 9.2 UI Ingestion Contract
1. Node Rendering: Render circles or device glyphs placed at normalized `(x, y)` multiplied by canvas dimensions.
2. Link Rendering: Draw orthogonal or curved bezier lines between source and target node coordinates.
3. Color Mapping by Status:
   - `unknown`: Slate gray / neutral (`#64748B`)
   - `nominal`: Emerald green (`#10B981`)
   - `warning`: Amber orange (`#F59E0B`)
   - `critical`: Crimson red (`#EF4444`)
4. Hover Tooltip: Display `display_name`, `role`, `site_name`, and simulated inventory badge.

