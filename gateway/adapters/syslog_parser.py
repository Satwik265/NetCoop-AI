"""RFC 3164 and RFC 5424 syslog line parser for gateway telemetry ingestion.

Converts raw syslog string lines into structured log dicts before log_agent.
Supports:
  - RFC 3164: <PRI>Mmm DD HH:MM:SS HOST PROGRAM[PID]: MSG
  - RFC 5424: <PRI>VERSION TIMESTAMP HOSTNAME APP-NAME PROCID MSGID STRUCTURED-DATA MSG
  - Plain-text fallback with optional 'hostname: msg' pattern
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Dict, Any, Optional


# ---------------------------------------------------------------------------
# Severity / facility mappings (RFC 5424 §6.2.1)
# ---------------------------------------------------------------------------

_FACILITY_NAMES = {
    0: "kern", 1: "user", 2: "mail", 3: "daemon", 4: "auth", 5: "syslog",
    6: "lpr", 7: "news", 8: "uucp", 9: "cron", 10: "authpriv", 11: "ftp",
    16: "local0", 17: "local1", 18: "local2", 19: "local3",
    20: "local4", 21: "local5", 22: "local6", 23: "local7",
}

_SEVERITY_NAMES = {
    0: "emergency", 1: "alert", 2: "critical", 3: "error",
    4: "warning", 5: "notice", 6: "informational", 7: "debug",
}

# Abbreviated month names for RFC 3164 timestamp
_MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


# ---------------------------------------------------------------------------
# RFC 3164 parser
# ---------------------------------------------------------------------------

# <PRI>Mmm DD HH:MM:SS HOST [TAG[PID]:] MSG
# TAG and PID are optional in some implementations (RFC 3164 §4.1.3 allows no TAG)
_RFC3164_PATTERN = re.compile(
    r"^<(\d{1,3})>"                              # PRI
    r"([A-Z][a-z]{2})\s+"                        # Month (Mmm)
    r"(\d{1,2})\s+"                              # Day
    r"(\d{2}:\d{2}:\d{2})\s+"                   # HH:MM:SS
    r"(\S+)\s+"                                  # HOST
    r"(?:(\S+?)(?:\[(\d+)\])?:\s*)?"            # TAG[PID]: (optional)
    r"(.*)"                                       # MSG
)


def _parse_rfc3164(line: str) -> Optional[Dict[str, Any]]:
    m = _RFC3164_PATTERN.match(line)
    if not m:
        return None
    pri_raw, mon_str, day_str, time_str, host, program, pid, message = m.groups()
    # program may be None when TAG is absent (message contains the full content)
    if program is None:
        program = ""
    pri = int(pri_raw)
    facility_num = pri >> 3
    severity_num = pri & 0x07
    # Build an ISO-8601 timestamp (year is not in RFC 3164; use current year)
    year = datetime.now(tz=timezone.utc).year
    month_num = _MONTHS.get(mon_str, 1)
    try:
        ts_naive = datetime.strptime(
            f"{year}-{month_num:02d}-{int(day_str):02d}T{time_str}", "%Y-%m-%dT%H:%M:%S"
        )
        timestamp_utc = ts_naive.replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        timestamp_utc = None

    return {
        "device": host,
        "program": program,
        "pid": int(pid) if pid else None,
        "facility": _FACILITY_NAMES.get(facility_num, str(facility_num)),
        "facility_num": facility_num,
        "severity": _SEVERITY_NAMES.get(severity_num, str(severity_num)),
        "severity_num": severity_num,
        "timestamp_utc": timestamp_utc,
        "message": message,
        "_rfc": "3164",
    }


# ---------------------------------------------------------------------------
# RFC 5424 parser
# ---------------------------------------------------------------------------

# <PRI>VERSION TIMESTAMP HOSTNAME APP-NAME PROCID MSGID STRUCTURED-DATA MSG
_RFC5424_PATTERN = re.compile(
    r"^<(\d{1,3})>"                             # PRI
    r"(\d+)\s+"                                  # VERSION
    r"(\S+)\s+"                                  # TIMESTAMP (or -)
    r"(\S+)\s+"                                  # HOSTNAME (or -)
    r"(\S+)\s+"                                  # APP-NAME (or -)
    r"(\S+)\s+"                                  # PROCID (or -)
    r"(\S+)\s+"                                  # MSGID (or -)
    r"(\[.*?\]|-)\s*"                            # STRUCTURED-DATA (or -)
    r"(.*)"                                       # MSG (may be empty)
)


def _parse_rfc5424(line: str) -> Optional[Dict[str, Any]]:
    m = _RFC5424_PATTERN.match(line)
    if not m:
        return None
    pri_raw, version, timestamp, hostname, app_name, procid, msgid, sd, message = m.groups()
    pri = int(pri_raw)
    facility_num = pri >> 3
    severity_num = pri & 0x07
    # Normalize NILVALUE (-) fields
    timestamp_utc = None if timestamp == "-" else timestamp
    hostname = None if hostname == "-" else hostname
    app_name = None if app_name == "-" else app_name
    procid = None if procid == "-" else procid

    return {
        "device": hostname or "unknown",
        "program": app_name,
        "pid": procid,
        "facility": _FACILITY_NAMES.get(facility_num, str(facility_num)),
        "facility_num": facility_num,
        "severity": _SEVERITY_NAMES.get(severity_num, str(severity_num)),
        "severity_num": severity_num,
        "timestamp_utc": timestamp_utc,
        "message": message,
        "_rfc": "5424",
        "_sd": sd if sd != "-" else None,
        "_msgid": msgid if msgid != "-" else None,
    }


# ---------------------------------------------------------------------------
# Plain-text fallback
# ---------------------------------------------------------------------------

_PLAIN_HOST_PREFIX = re.compile(r"^(\S+):\s+(.*)")


def _parse_plain(line: str) -> Dict[str, Any]:
    """Fallback: extract host from 'hostname: message' pattern or return raw."""
    m = _PLAIN_HOST_PREFIX.match(line)
    if m:
        host, message = m.groups()
        # Only treat as host: message if 'host' doesn't look like a severity keyword
        if host.lower() not in ("error", "warn", "info", "debug", "notice", "critical"):
            return {
                "device": host,
                "program": None,
                "pid": None,
                "facility": None,
                "facility_num": None,
                "severity": "informational",
                "severity_num": 6,
                "timestamp_utc": None,
                "message": message,
                "_rfc": "plain",
            }
    return {
        "device": "unknown",
        "program": None,
        "pid": None,
        "facility": None,
        "facility_num": None,
        "severity": "informational",
        "severity_num": 6,
        "timestamp_utc": None,
        "message": line,
        "_rfc": "plain",
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_syslog_line(line: str) -> Dict[str, Any]:
    """Parse a syslog line (RFC 3164, RFC 5424, or plain-text fallback).

    Returns a dict with keys:
      device, program, pid, facility, facility_num,
      severity, severity_num, timestamp_utc, message, _rfc

    Never raises; unknown lines fall back to plain-text with device='unknown'.
    """
    if not isinstance(line, str):
        line = str(line)
    line = line.strip()
    if not line:
        return {
            "device": "unknown",
            "program": None,
            "pid": None,
            "facility": None,
            "facility_num": None,
            "severity": "informational",
            "severity_num": 6,
            "timestamp_utc": None,
            "message": "",
            "_rfc": "plain",
        }

    # Try RFC 5424 first (versioned; unambiguous)
    result = _parse_rfc5424(line)
    if result is not None:
        return result

    # Try RFC 3164
    result = _parse_rfc3164(line)
    if result is not None:
        return result

    # Plain-text fallback
    return _parse_plain(line)


def parse_syslog_lines(lines: list) -> list:
    """Parse a list of raw syslog strings into a list of structured dicts.

    Items that are already dicts are passed through unchanged.
    Items that are strings are run through parse_syslog_line().
    Other types are skipped (None returned for each), filtered from output.
    """
    result = []
    for item in lines:
        if isinstance(item, dict):
            result.append(item)
        elif isinstance(item, str):
            result.append(parse_syslog_line(item))
        else:
            # Non-dict, non-string: skip silently
            pass
    return result
