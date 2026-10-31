"""NetCoop AI Ingestion Gateway package."""

from gateway.adapters.organizer_adapter import OrganizerAdapter
from gateway.api import app as gateway_app

__all__ = ["OrganizerAdapter", "gateway_app"]
