"""Database connection and audit logging repository mirroring netcoop.storage.db."""

import sys
import netcoop.storage.db

sys.modules[__name__] = netcoop.storage.db
from netcoop.storage.db import (
    engine,
    init_db,
    log_envelope,
    get_envelope_logs,
    save_incident,
    get_incident,
    list_incidents,
    save_checkpoint,
    get_latest_checkpoint,
    list_checkpoints,
    mark_session_paused,
    mark_session_resumed,
    save_remediation_action_log,
    get_remediation_action_log,
    list_remediation_action_logs,
    record_hitl_decision,
    get_remediation_logs,
    save_remediation_log,
)
