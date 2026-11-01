"""Unit tests and schema validation fixtures for IIT Bhubaneswar demonstration campus topology.

Validates schema compliance, graph integrity, naming conventions, simulated
provenance flags, and normalized canvas layout constraints.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import jsonschema
import pytest

SCHEMA_PATH = Path("schemas/campus_topology.schema.json")
DATA_PATH = Path("data/campus/iitbbsr_demo_topology.json")

SUPPORTED_CAMPUS_LOCATIONS = {
    "Administrative Building",
    "IIT Bhubaneswar Auditorium",
    "School of Basic Sciences",
    "School of Infrastructure",
    "School of Mechanical Sciences",
    "Central Workshop",
    "Rushikulya Hall of Residence",
    "Academic zone",
    "Residential zone",
}

ROUTER_ID_PATTERN = re.compile(r"^IITBBSR-(CORE|AGG|DIST)-[A-Z0-9]+-[0-9]{2}$")


@pytest.fixture(scope="module")
def schema() -> dict:
    assert SCHEMA_PATH.is_file(), f"Schema file not found at {SCHEMA_PATH}"
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def topology_data() -> dict:
    assert DATA_PATH.is_file(), f"Topology dataset not found at {DATA_PATH}"
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_schema_file_exists():
    assert SCHEMA_PATH.exists()
    assert DATA_PATH.exists()


def test_schema_validation(schema: dict, topology_data: dict):
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)
    validator = validator_cls(schema)
    errors = sorted(validator.iter_errors(topology_data), key=lambda e: e.path)
    assert not errors, f"JSON Schema validation failed with errors: {errors}"


def test_unique_node_ids(topology_data: dict):
    nodes = topology_data.get("nodes", [])
    assert len(nodes) == 10, f"Expected exactly 10 nodes, found {len(nodes)}"
    node_ids = [n["id"] for n in nodes]
    assert len(node_ids) == len(set(node_ids)), f"Duplicate node IDs found: {node_ids}"


def test_router_naming_convention(topology_data: dict):
    for node in topology_data.get("nodes", []):
        node_id = node["id"]
        assert ROUTER_ID_PATTERN.match(node_id), (
            f"Node ID '{node_id}' does not match expected convention ^IITBBSR-(CORE|AGG|DIST)-[A-Z0-9]+-[0-9]{{2}}$"
        )


def test_supported_campus_locations(topology_data: dict):
    for node in topology_data.get("nodes", []):
        site_name = node["site_name"]
        assert site_name in SUPPORTED_CAMPUS_LOCATIONS, (
            f"Node {node['id']} has unsupported site_name '{site_name}'."
        )


def test_link_integrity(topology_data: dict):
    nodes = {n["id"] for n in topology_data.get("nodes", [])}
    links = topology_data.get("links", [])
    assert len(links) >= 10, f"Expected at least 10 links, found {len(links)}"

    for link in links:
        src = link["source"]
        tgt = link["target"]
        assert src in nodes, f"Link source '{src}' does not exist in nodes"
        assert tgt in nodes, f"Link target '{tgt}' does not exist in nodes"
        assert src != tgt, f"Self-loop detected on node '{src}'"


def test_no_orphaned_nodes(topology_data: dict):
    nodes = {n["id"] for n in topology_data.get("nodes", [])}
    connected_nodes = set()
    for link in topology_data.get("links", []):
        connected_nodes.add(link["source"])
        connected_nodes.add(link["target"])

    orphans = nodes - connected_nodes
    assert not orphans, f"Found orphaned nodes with no links: {orphans}"


def test_simulated_provenance(topology_data: dict):
    assert topology_data.get("simulated_inventory") is True
    assert topology_data.get("layout_coordinate_system") == "normalized_canvas_space"

    provenance = topology_data.get("topology_provenance", {})
    assert provenance.get("model_type") == "simulated_demonstration_topology"
    assert "synthetic demonstration inventory" in provenance.get("disclaimer", "").lower()

    for node in topology_data.get("nodes", []):
        assert node.get("simulated") is True, f"Node {node['id']} simulated flag must be True"
        assert node.get("inventory_status") == "simulated_demonstration", (
            f"Node {node['id']} inventory_status must be 'simulated_demonstration'"
        )

    for link in topology_data.get("links", []):
        assert link.get("simulated") is True, f"Link {link['source']}->{link['target']} simulated flag must be True"


def test_no_fabricated_geographic_coordinates(topology_data: dict):
    forbidden_keys = {"latitude", "longitude", "lat", "lng", "gps", "altitude"}

    for node in topology_data.get("nodes", []):
        assert not (forbidden_keys & set(node.keys())), (
            f"Node {node['id']} contains forbidden GPS/geo keys: {forbidden_keys & set(node.keys())}"
        )
        pos = node.get("layout_position", {})
        assert "x" in pos and "y" in pos, f"Node {node['id']} missing normalized canvas coordinates"
        assert 0.0 <= pos["x"] <= 1.0, f"Node {node['id']} x-coordinate {pos['x']} out of [0.0, 1.0]"
        assert 0.0 <= pos["y"] <= 1.0, f"Node {node['id']} y-coordinate {pos['y']} out of [0.0, 1.0]"


def test_base_status_unknown(topology_data: dict):
    for node in topology_data.get("nodes", []):
        assert node.get("status") == "unknown", (
            f"Node {node['id']} initial status must be 'unknown', found '{node.get('status')}'"
        )
    for link in topology_data.get("links", []):
        assert link.get("status") == "unknown", (
            f"Link {link['source']}->{link['target']} initial status must be 'unknown', found '{link.get('status')}'"
        )


def test_demonstration_route_integrity(topology_data: dict):
    paths = topology_data.get("logical_routing_paths", [])
    assert len(paths) >= 1, "At least one logical demonstration path must be defined"

    target_path = next((p for p in paths if p.get("path_id") == "PATH-DEMO-CORE-SBS-01"), None)
    assert target_path is not None, "Demonstration path 'PATH-DEMO-CORE-SBS-01' not found"

    assert target_path.get("simulated") is True
    assert target_path.get("path_type") == "simulated_logical_route"
    assert len(target_path.get("disclaimer", "")) > 10

    hops = target_path.get("hops", [])
    expected_hops = [
        "IITBBSR-CORE-RTR-01",
        "IITBBSR-AGG-ACAD-01",
        "IITBBSR-DIST-SBS-01",
    ]
    assert hops == expected_hops, f"Expected hops {expected_hops}, got {hops}"

    # Verify that each hop transition corresponds to an existing link in topology
    link_pairs = set()
    for link in topology_data.get("links", []):
        src, tgt = link["source"], link["target"]
        link_pairs.add((src, tgt))
        link_pairs.add((tgt, src))

    for i in range(len(hops) - 1):
        pair = (hops[i], hops[i + 1])
        assert pair in link_pairs, f"Hop step {pair} is not connected by any physical link in topology"

