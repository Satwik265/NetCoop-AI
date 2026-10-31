"""Optional Gemini LLM bridge for executive summaries and tie-breaking with offline fallback."""

import logging
from typing import Dict, List, Optional
from netcoop.config import settings

logger = logging.getLogger(__name__)


class GeminiBridge:
    """Optional LLM bridge providing plain-language summaries and subtle tie-breaking.

    Guaranteed to degrade gracefully to offline templates when GEMINI_API_KEY is absent.
    """

    @classmethod
    def is_available(cls) -> bool:
        """Check if Gemini credentials are configured."""
        return bool(settings.gemini_api_key)

    @classmethod
    def generate_executive_summary(
        cls,
        incident_id: str,
        network_id: str,
        status: str,
        probable_cause: Optional[str],
        confidence: float,
        affected_devices: List[str],
        evidence_summary: List[str],
    ) -> str:
        """Generate a natural language incident summary. Uses offline templates by default."""
        if not cls.is_available():
            return cls._offline_summary(
                incident_id, network_id, status, probable_cause, confidence, affected_devices
            )

        try:
            from google import genai

            client = genai.Client(api_key=settings.gemini_api_key)
            prompt = (
                f"You are a network reliability engineer. Summarize this network incident briefly and technically.\n"
                f"Incident: {incident_id} on {network_id}\n"
                f"Status: {status}\n"
                f"Probable Cause: {probable_cause}\n"
                f"Confidence: {confidence:.2f}\n"
                f"Affected Devices: {', '.join(affected_devices)}\n"
                f"Evidence: {'; '.join(evidence_summary)}\n"
                f"Write a 2-sentence executive summary without emojis."
            )
            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
            )
            return response.text.strip()
        except Exception as e:
            logger.warning("Gemini API call failed, falling back to offline summary: %s", e)
            return cls._offline_summary(
                incident_id, network_id, status, probable_cause, confidence, affected_devices
            )

    @classmethod
    def _offline_summary(
        cls,
        incident_id: str,
        network_id: str,
        status: str,
        probable_cause: Optional[str],
        confidence: float,
        affected_devices: List[str],
    ) -> str:
        """Deterministic offline incident summary."""
        if status == "diagnosed" and probable_cause:
            dev_str = ", ".join(affected_devices) if affected_devices else "affected nodes"
            return (
                f"Incident {incident_id} on network {network_id} was successfully diagnosed as "
                f"'{probable_cause}' with {int(confidence * 100)}% confidence impacting {dev_str}."
            )
        elif status == "insufficient_evidence":
            return (
                f"Incident {incident_id} on network {network_id} could not be conclusively diagnosed. "
                f"Observed anomalies lack necessary multi-point corroboration across agent domains."
            )
        return f"Incident {incident_id} evaluated with status {status}."
