"""SQLModel database models facade mirroring netcoop.storage.models."""

import sys
import netcoop.storage.models

sys.modules[__name__] = netcoop.storage.models
from netcoop.storage.models import (
    IncidentRecord,
    EnvelopeLog,
    RemediationLog,
    OrchestratorCheckpoint,
    UserRecord,
    AuthAuditLog,
    RevokedToken,
    WsTicketRecord,
)
