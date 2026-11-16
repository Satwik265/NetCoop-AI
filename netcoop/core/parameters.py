"""Parameters Catalog loader and documentation renderer for NetCoop AI."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional
import yaml


_PARAM_FILE = Path(__file__).resolve().parent.parent.parent / "config" / "parameters.yaml"
_CACHED_PARAMS: Optional[Dict[str, Any]] = None


def load_parameters(force_reload: bool = False) -> Dict[str, Any]:
    """Load parameter catalog from config/parameters.yaml."""
    global _CACHED_PARAMS
    if _CACHED_PARAMS is not None and not force_reload:
        return _CACHED_PARAMS

    if _PARAM_FILE.exists():
        with open(_PARAM_FILE, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            _CACHED_PARAMS = data.get("parameters", {})
    else:
        _CACHED_PARAMS = {}

    return _CACHED_PARAMS


def get_parameter(name: str, default: Any = None) -> Any:
    """Retrieve the value of an operational parameter."""
    params = load_parameters()
    entry = params.get(name)
    if isinstance(entry, dict) and "value" in entry:
        return entry["value"]
    return default if entry is None else entry


def get_parameter_entry(name: str) -> Optional[Dict[str, Any]]:
    """Retrieve complete metadata (value, type, evidence, unit) for a parameter."""
    params = load_parameters()
    return params.get(name)


def render_parameters_markdown_table() -> str:
    """Render parameter catalog as a GitHub Flavored Markdown table."""
    params = load_parameters()
    lines = [
        "| Parameter Name | Value | Unit | Type | Category | Evidence / Rationale |",
        "|:---|:---:|:---:|:---:|:---:|:---|",
    ]
    for name, p in sorted(params.items()):
        val = p.get("value", "")
        unit = p.get("unit", "-")
        ptype = p.get("type", "heuristic")
        category = p.get("category", "general")
        evidence = p.get("evidence", "").replace("|", "\\|")
        lines.append(f"| `{name}` | `{val}` | `{unit}` | **{ptype}** | `{category}` | {evidence} |")
    return "\n".join(lines)
