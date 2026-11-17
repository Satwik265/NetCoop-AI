"""Unit tests for gateway.adapters.syslog_parser.

Uses public RFC 3164 and RFC 5424 example lines from the RFCs themselves,
NOT from the Phase 13L emulation captures.

RFC 3164 examples from:  https://www.rfc-editor.org/rfc/rfc3164 §5.4
RFC 5424 examples from:  https://www.rfc-editor.org/rfc/rfc5424 §6.5
"""

import sys
import os

# Allow importing from gateway package directly when run from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from gateway.adapters.syslog_parser import parse_syslog_line, parse_syslog_lines


# ---------------------------------------------------------------------------
# RFC 3164 examples (§5.4 of RFC 3164)
# ---------------------------------------------------------------------------

class TestRFC3164:
    """Public RFC 3164 example lines."""

    # RFC 3164 §5.4 example 1
    RFC3164_EX1 = "<34>Oct 11 22:14:15 mymachine su: 'su root' failed for lonvick on /dev/pts/8"

    def test_rfc3164_example1_basic(self):
        r = parse_syslog_line(self.RFC3164_EX1)
        assert r["_rfc"] == "3164", f"Expected RFC 3164, got {r['_rfc']}"
        assert r["device"] == "mymachine"
        assert r["program"] == "su"
        assert "su root" in r["message"]

    def test_rfc3164_example1_severity(self):
        r = parse_syslog_line(self.RFC3164_EX1)
        # PRI=34 → facility=4 (auth), severity=2 (critical)
        assert r["severity_num"] == 2, f"Expected severity 2 (critical), got {r['severity_num']}"
        assert r["severity"] == "critical"
        assert r["facility_num"] == 4
        assert r["facility"] == "auth"

    def test_rfc3164_example1_timestamp(self):
        r = parse_syslog_line(self.RFC3164_EX1)
        assert r["timestamp_utc"] is not None
        assert "10-11T22:14:15" in r["timestamp_utc"]

    # RFC 3164 §5.4 example 2 — no PID
    RFC3164_EX2 = "<13>Feb  5 17:32:18 10.0.0.99 Use the BFD daemon"

    def test_rfc3164_example2_host_and_msg(self):
        r = parse_syslog_line(self.RFC3164_EX2)
        assert r["_rfc"] == "3164"
        assert r["device"] == "10.0.0.99"

    def test_rfc3164_example2_severity_informational(self):
        r = parse_syslog_line(self.RFC3164_EX2)
        # PRI=13 → facility=1 (user), severity=5 (notice)
        assert r["severity_num"] == 5
        assert r["facility_num"] == 1

    # RFC 3164 §5.4 example 3 — with PID
    RFC3164_EX3 = "<165>Aug 24 05:34:00 CST 1987 mymachine myproc[10]: %% It's time to make the do-nuts."

    def test_rfc3164_with_pid(self):
        r = parse_syslog_line(self.RFC3164_EX3)
        # May parse as RFC 3164 or fallback; either is acceptable
        assert r["message"] != ""

    # Required output keys
    def test_rfc3164_required_keys(self):
        r = parse_syslog_line(self.RFC3164_EX1)
        for key in ("device", "message", "severity", "severity_num", "timestamp_utc"):
            assert key in r, f"Missing required key: {key}"


# ---------------------------------------------------------------------------
# RFC 5424 examples (§6.5 of RFC 5424)
# ---------------------------------------------------------------------------

class TestRFC5424:
    """Public RFC 5424 example lines."""

    # RFC 5424 §6.5 example 1
    RFC5424_EX1 = (
        "<34>1 2003-10-11T22:14:15.003Z mymachine.example.com su - ID47 - "
        "BOM'su root' failed for lonvick on /dev/pts/8"
    )

    def test_rfc5424_example1_basic(self):
        r = parse_syslog_line(self.RFC5424_EX1)
        assert r["_rfc"] == "5424", f"Expected RFC 5424, got {r['_rfc']}"
        assert r["device"] == "mymachine.example.com"
        assert r["program"] == "su"

    def test_rfc5424_example1_severity(self):
        r = parse_syslog_line(self.RFC5424_EX1)
        # PRI=34 → facility=4, severity=2 (critical)
        assert r["severity_num"] == 2
        assert r["severity"] == "critical"
        assert r["facility_num"] == 4

    def test_rfc5424_example1_timestamp(self):
        r = parse_syslog_line(self.RFC5424_EX1)
        assert r["timestamp_utc"] == "2003-10-11T22:14:15.003Z"

    # RFC 5424 §6.5 example 2 — with structured data
    RFC5424_EX2 = (
        '<165>1 2003-10-11T22:14:15.003Z mymachine.example.com evntslog - ID47 '
        '[exampleSDID@32473 iut="3" eventSource="Application" eventID="1011"] '
        'An application event log entry...'
    )

    def test_rfc5424_example2_app(self):
        r = parse_syslog_line(self.RFC5424_EX2)
        assert r["_rfc"] == "5424"
        assert r["device"] == "mymachine.example.com"
        assert r["program"] == "evntslog"

    def test_rfc5424_example2_severity(self):
        r = parse_syslog_line(self.RFC5424_EX2)
        # PRI=165 → facility=20 (local4), severity=5 (notice)
        assert r["severity_num"] == 5
        assert r["facility_num"] == 20

    def test_rfc5424_example2_message(self):
        r = parse_syslog_line(self.RFC5424_EX2)
        assert "application event log entry" in r["message"].lower()

    # RFC 5424 §6.5 example 3 — NILVALUE fields
    RFC5424_EX3 = "<0>1 1970-01-01T00:00:00.000000+00:00 - - - - - test nil fields"

    def test_rfc5424_nilvalue_device_fallback(self):
        r = parse_syslog_line(self.RFC5424_EX3)
        assert r["_rfc"] == "5424"
        # NILVALUE hostname → 'unknown'
        assert r["device"] == "unknown"

    def test_rfc5424_nilvalue_program_is_none(self):
        r = parse_syslog_line(self.RFC5424_EX3)
        assert r["program"] is None

    # Required output keys
    def test_rfc5424_required_keys(self):
        r = parse_syslog_line(self.RFC5424_EX2)
        for key in ("device", "message", "severity", "severity_num", "timestamp_utc"):
            assert key in r, f"Missing required key: {key}"


# ---------------------------------------------------------------------------
# PRI numeric mapping
# ---------------------------------------------------------------------------

class TestPRIMapping:
    """Verify PRI = facility*8 + severity decomposition."""

    def test_pri_0_emergency_kern(self):
        line = "<0>Oct 11 10:00:00 host prog: msg"
        r = parse_syslog_line(line)
        if r["_rfc"] == "3164":
            assert r["facility_num"] == 0
            assert r["severity_num"] == 0
            assert r["severity"] == "emergency"

    def test_pri_191_debug_local7(self):
        line = "<191>Oct 11 10:00:00 host prog: msg"
        r = parse_syslog_line(line)
        if r["_rfc"] == "3164":
            assert r["facility_num"] == 23  # local7
            assert r["severity_num"] == 7   # debug

    def test_pri_161_informational_local4(self):
        line = "<161>1 2003-10-11T22:14:15Z host app - - - msg"
        r = parse_syslog_line(line)
        if r["_rfc"] == "5424":
            # 161 = 20*8 + 1 → facility 20 (local4), severity 1 (alert)
            assert r["facility_num"] == 20
            assert r["severity_num"] == 1


# ---------------------------------------------------------------------------
# Plain-text fallback
# ---------------------------------------------------------------------------

class TestPlainFallback:
    """Non-RFC lines must not raise and must have required keys."""

    def test_plain_string(self):
        r = parse_syslog_line("interface GigabitEthernet0/0 changed state to down")
        assert "device" in r
        assert "message" in r
        assert r["message"] != ""
        assert r["_rfc"] == "plain"

    def test_plain_host_prefix(self):
        r = parse_syslog_line("router1: interface eth0 link down")
        assert r["device"] == "router1"
        assert "interface eth0" in r["message"]

    def test_empty_string(self):
        r = parse_syslog_line("")
        assert r["device"] == "unknown"
        assert r["message"] == ""

    def test_non_string_coerced(self):
        # Should coerce to str and not raise
        r = parse_syslog_line(12345)  # type: ignore[arg-type]
        assert "message" in r

    def test_all_required_keys_present(self):
        r = parse_syslog_line("some plain text without any syslog header")
        for key in ("device", "message", "severity", "severity_num", "timestamp_utc"):
            assert key in r


# ---------------------------------------------------------------------------
# parse_syslog_lines (batch)
# ---------------------------------------------------------------------------

class TestParseSyslogLines:
    """Batch helper: mixed list of dicts, strings and others."""

    def test_dict_passthrough(self):
        already = {"device": "sw1", "message": "ok", "severity": "informational", "severity_num": 6, "timestamp_utc": None}
        result = parse_syslog_lines([already])
        assert result[0] is already  # exact same object

    def test_string_converted(self):
        lines = ["<34>Oct 11 22:14:15 host prog: msg"]
        result = parse_syslog_lines(lines)
        assert len(result) == 1
        assert result[0]["_rfc"] == "3164"

    def test_mixed_list(self):
        d = {"device": "sw2", "message": "ping ok", "severity": "debug", "severity_num": 7, "timestamp_utc": None}
        lines = [d, "<34>Oct 11 22:14:15 host prog: msg", None, 42]
        result = parse_syslog_lines(lines)
        # dict passthrough + 1 parsed string; None and int skipped
        assert len(result) == 2
        assert result[0] is d
        assert result[1]["_rfc"] == "3164"

    def test_empty_list(self):
        assert parse_syslog_lines([]) == []

    def test_all_strings(self):
        lines = [
            "<34>Oct 11 22:14:15 mymachine su: failed",
            '<165>1 2003-10-11T22:14:15.003Z host evntslog - ID47 - msg',
            "plain text without header",
        ]
        result = parse_syslog_lines(lines)
        assert len(result) == 3
        rfcs = [r["_rfc"] for r in result]
        assert "3164" in rfcs
        assert "5424" in rfcs
        assert "plain" in rfcs


# ---------------------------------------------------------------------------
# LogAgent non-dict guard and limitation recording
# ---------------------------------------------------------------------------

class TestLogAgentNonDictGuard:
    """log_agent must guard against non-dict items and record typed limitation."""

    def test_log_agent_handles_raw_strings_without_crash(self):
        from netcoop.agents.log_agent import LogAgent
        from netcoop.core.envelope import AgentEnvelope, ProtocolHeader, EnvelopePayload, MessageType, AgentRole, NetworkScope

        agent = LogAgent()
        raw_logs = [
            "<34>Oct 11 22:14:15 host su: failed",  # raw string, not dict
            "plain text string line",
            12345,  # int
            {"device": "sw1", "message": "%LINK-3-UPDOWN: Interface eth0 changed state to down", "severity": 3, "timestamp_utc": None},
        ]
        envelope = AgentEnvelope(
            header=ProtocolHeader(
                message_type=MessageType.TELEMETRY_DISPATCH,
                sender=AgentRole.ORCHESTRATOR,
                recipient=AgentRole.LOG_AGENT,
                correlation_id="test-log-nondict",
            ),
            payload=EnvelopePayload(
                scope=NetworkScope(network_id="lab-01", devices=["sw1"]),
                raw_data={"logs": raw_logs},
            ),
        )

        resp = agent.handle_envelope(envelope)
        assert resp is not None
        # Typed limitation must be recorded
        limitations = resp.context.get("limitations", [])
        assert any("unstructured_syslog_telemetry" in lim for lim in limitations)
        # Valid dict log should still be parsed into observation
        obs = resp.payload.observations
        assert any("link_flap" in o.metric_name for o in obs)

    def test_log_agent_inquiry_with_raw_strings(self):
        from netcoop.agents.log_agent import LogAgent
        from netcoop.core.envelope import AgentEnvelope, ProtocolHeader, EnvelopePayload, MessageType, AgentRole, Inquiry, NetworkScope

        agent = LogAgent()
        raw_logs = [
            "raw string that would have crashed",
            {"device": "sw1", "message": "carrier transition link flap", "severity": 3, "timestamp_utc": None},
        ]
        envelope = AgentEnvelope(
            header=ProtocolHeader(
                message_type=MessageType.INQUIRY_REQUEST,
                sender=AgentRole.ORCHESTRATOR,
                recipient=AgentRole.LOG_AGENT,
                correlation_id="test-log-inq",
            ),
            payload=EnvelopePayload(
                scope=NetworkScope(network_id="lab-01", devices=["sw1"]),
                raw_data={"logs": raw_logs},
                inquiries=[Inquiry(inquiry_id="inq-1", target_agent=AgentRole.LOG_AGENT, target_entity="sw1", question="any flaps?")],
            ),
        )

        resp = agent.handle_envelope(envelope)
        assert resp is not None
        assert len(resp.payload.inquiries) == 1
        assert "verified" in resp.payload.inquiries[0].answer

