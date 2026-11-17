"""Agent 4: Anomaly Correlation and Log Analyzer Agent."""



from typing import Any, Dict, List

from netcoop.agents.base import BaseAgent

from netcoop.core.envelope import (

    AgentEnvelope,

    AgentRole,

    Hypothesis,

    Inquiry,

    MessageType,

    Observation,

    ObservationCategory,

    Severity,

)





class LogAgent(BaseAgent):

    """Clusters and parses syslog streams, BFD state transitions, and transceiver alarms."""



    def __init__(self) -> None:

        super().__init__(

            role=AgentRole.LOG_AGENT,

            name="Anomaly Correlation & Log Analyzer",

        )



    def _handle_inquiry(self, envelope: AgentEnvelope) -> AgentEnvelope:

        """Answer targeted log inquiries from peer agents or orchestrator."""

        response = self.create_response_envelope(envelope, MessageType.INQUIRY_RESPONSE)

        raw_logs = (envelope.payload.raw_data or {}).get("logs", [])

        inquiries = envelope.payload.inquiries

        non_dict_count = 0

        for inq in inquiries:

            target_entity = inq.target_entity or ""

            target_dev = target_entity.split(":")[0] if target_entity else ""

            matched_logs = []

            for log in raw_logs:

                if not isinstance(log, dict):

                    non_dict_count += 1

                    continue

                dev = log.get("device", "")

                msg = log.get("message", "").lower()

                if target_dev and dev and target_dev not in dev and dev not in target_dev:

                    continue

                if any(w in msg for w in ("drop", "flap", "down", "error", "crc", "alarm", "optics", "bfd", "suppress", "qos")):

                    matched_logs.append(log)



            if matched_logs:

                first_msg = matched_logs[0].get("message", "")

                inq.answer = f"Syslog inquiry verified {len(matched_logs)} events on {target_entity or 'scope'}: {first_msg}"

            else:

                inq.answer = f"Syslog inquiry verified 0 anomalous events on {target_entity or 'scope'}; logs nominal."



        response.payload.inquiries = inquiries

        if non_dict_count > 0:
            limitations = response.context.setdefault("limitations", [])
            limitations.append(
                f"unstructured_syslog_telemetry: {non_dict_count} non-dict log entries skipped; gateway syslog normalization required"
            )

        return response



    def handle_envelope(self, envelope: AgentEnvelope) -> AgentEnvelope:

        """Parse syslog messages for known fault signatures and state transitions."""

        if envelope.header.message_type == MessageType.INQUIRY_REQUEST:

            return self._handle_inquiry(envelope)



        response = self.create_response_envelope(envelope, MessageType.FINDING_SUBMISSION)

        raw_logs = (envelope.payload.raw_data or {}).get("logs", [])



        if not raw_logs:

            response.context["limitations"] = ["syslog telemetry unavailable: no log events recorded for device scope"]



        observations: List[Observation] = []

        non_dict_count = 0

        for log in raw_logs:

            if not isinstance(log, dict):

                non_dict_count += 1

                continue

            dev = log.get("device", "unknown")

            msg = log.get("message", "")

            severity_num = log.get("severity", 6)

            ts = log.get("timestamp_utc")



            msg_lower = msg.lower()



            if "bfd session down" in msg_lower or "bfd down" in msg_lower:

                observations.append(

                    Observation(

                        category=ObservationCategory.LOG_PATTERN,

                        entity=dev,

                        metric_name="bfd_session_down",

                        observed_value=msg,

                        unit="text",

                        severity=Severity.CRITICAL,

                        timestamp_start=ts,

                        context={"agent_domain": "log_agent"},

                    )

                )

            elif "dampening active" in msg_lower or "suppressed penalty" in msg_lower:

                observations.append(

                    Observation(

                        category=ObservationCategory.LOG_PATTERN,

                        entity=dev,

                        metric_name="flap_damping_active",

                        observed_value=msg,

                        unit="text",

                        severity=Severity.CRITICAL,

                        timestamp_start=ts,

                        context={"agent_domain": "log_agent"},

                    )

                )

            elif "optics dom alarm" in msg_lower or "rx power" in msg_lower:

                observations.append(

                    Observation(

                        category=ObservationCategory.LOG_PATTERN,

                        entity=dev,

                        metric_name="optical_power_alarm",

                        observed_value=msg,

                        unit="text",

                        severity=Severity.WARNING if severity_num >= 4 else Severity.CRITICAL,

                        timestamp_start=ts,

                        context={"agent_domain": "log_agent"},

                    )

                )

            elif "flapping between port" in msg_lower or "mac flapping" in msg_lower:

                observations.append(

                    Observation(

                        category=ObservationCategory.LOG_PATTERN,

                        entity=dev,

                        metric_name="mac_flapping_log",

                        observed_value=msg,

                        unit="text",

                        severity=Severity.CRITICAL,

                        timestamp_start=ts,

                        context={"agent_domain": "log_agent"},

                    )

                )

            elif any(k in msg_lower for k in ("queue drop", "queue-drop", "tail drop", "%qos-", "class-of-service", "drops exceeded threshold")):

                observations.append(

                    Observation(

                        category=ObservationCategory.LOG_PATTERN,

                        entity=dev,

                        metric_name="queue_drop_syslog",

                        observed_value=msg,

                        unit="text",

                        severity=Severity.WARNING if severity_num >= 4 else Severity.CRITICAL,

                        timestamp_start=ts,

                        context={"agent_domain": "log_agent"},

                    )

                )

            elif any(k in msg_lower for k in ("%link-3-updown", "%lineproto-5-updown", "changed state to down", "carrier transition", "link flap", "line protocol")):

                observations.append(

                    Observation(

                        category=ObservationCategory.LOG_PATTERN,

                        entity=dev,

                        metric_name="link_flap_syslog",

                        observed_value=msg,

                        unit="text",

                        severity=Severity.CRITICAL,

                        timestamp_start=ts,

                        context={"agent_domain": "log_agent"},

                    )

                )

            elif any(k in msg_lower for k in ("%eth-4-crc_err", "crc error", "input error", "fcs error", "checksum error", "alignment error")):

                observations.append(

                    Observation(

                        category=ObservationCategory.LOG_PATTERN,

                        entity=dev,

                        metric_name="crc_error_syslog",

                        observed_value=msg,

                        unit="text",

                        severity=Severity.CRITICAL,

                        timestamp_start=ts,

                        context={"agent_domain": "log_agent"},

                    )

                )

            elif any(k in msg_lower for k in ("packet_too_big", "exceeds mtu", "packet size", "mtu exceeded")):

                observations.append(

                    Observation(

                        category=ObservationCategory.LOG_PATTERN,

                        entity=dev,

                        metric_name="mtu_exceeded_syslog",

                        observed_value=msg,

                        unit="text",

                        severity=Severity.WARNING,

                        timestamp_start=ts,

                        context={"agent_domain": "log_agent"},

                    )

                )



        response.payload.observations = observations



        obs_ids = [o.observation_id for o in observations]

        has_dampening = any(o.metric_name == "flap_damping_active" for o in observations)

        has_optics_alarm = any(o.metric_name == "optical_power_alarm" for o in observations)

        has_queue_drop = any(o.metric_name == "queue_drop_syslog" for o in observations)

        has_crc_or_flap = any(o.metric_name in ("link_flap_syslog", "crc_error_syslog") for o in observations)



        if has_dampening:

            response.payload.hypotheses.append(

                Hypothesis(

                    probable_cause="BGP route flap damping triggered by physical carrier flapping",

                    confidence=0.82,

                    supporting_observation_ids=obs_ids,

                    required_corroboration=["topology_agent:verify_bgp_session_state"],

                )

            )

        elif has_optics_alarm:

            response.payload.hypotheses.append(

                Hypothesis(

                    probable_cause="Physical transceiver optical signal degradation",

                    confidence=0.80,

                    supporting_observation_ids=obs_ids,

                    required_corroboration=["telemetry_agent:verify_crc_and_fcs_errors"],

                )

            )

        elif has_queue_drop:

            response.payload.hypotheses.append(

                Hypothesis(

                    probable_cause="Link Congestion and buffer exhaustion under heavy load",

                    confidence=0.78,

                    supporting_observation_ids=obs_ids,

                    required_corroboration=["telemetry_agent:verify_queue_drops"],

                )

            )

        elif has_crc_or_flap:

            response.payload.hypotheses.append(

                Hypothesis(

                    probable_cause="Physical layer Ethernet interface CRC errors and flapping transitions",

                    confidence=0.82,

                    supporting_observation_ids=obs_ids,

                    required_corroboration=["telemetry_agent:verify_crc_and_fcs_errors"],

                )

            )



        if non_dict_count > 0:
            limitations = response.context.setdefault("limitations", [])
            limitations.append(
                f"unstructured_syslog_telemetry: {non_dict_count} non-dict log entries skipped; gateway syslog normalization required"
            )

        return response

