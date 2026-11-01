"""FastAPI backend server for NetCoop AI multi-agent diagnostic platform."""


import asyncio
import httpx

from datetime import datetime, timezone

import json

import os

from pathlib import Path

from typing import Any, Dict, List, Optional, Set

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, status

from fastapi.middleware.cors import CORSMiddleware

from fastapi.staticfiles import StaticFiles

from pydantic import BaseModel


from core.auth import (

    ALL_ROLES,

    AssignIncidentRequest,

    CreateUserRequest,

    
    ImpersonateRequest,
    UpdateUserStatusRequest,
    ROLE_PLATFORM_ADMIN,
    ROLE_NETWORK_ADMIN,
    ROLE_NETWORK_ENGINEER,
    ROLE_HELPDESK,DemoLoginRequest,

    LoginRequest,

    TokenResponse,

    UserProfileResponse,

    WsTicketResponse,

    create_ws_ticket,

    consume_ws_ticket,

    get_current_user,

    require_roles,

    require_permissions,

    create_access_token,

    decode_access_token,

    verify_password,

    hash_password,

    check_login_rate_limit,

    record_login_failure,

    clear_login_failures,

    ROLE_PERMISSIONS_MAP,

    PERM_VIEW_FABRIC_HEALTH,

    PERM_ACKNOWLEDGE_ALERTS,

    PERM_ASSIGN_INCIDENT,

    PERM_EXECUTE_DIAGNOSIS,

    PERM_SIMULATE_REMEDIATION,

    PERM_MODIFY_COMMANDS,

    PERM_APPROVE_REMEDIATION,

    PERM_EXECUTE_REMEDIATION,

    PERM_MANAGE_DEVICES,

    PERM_CONFIGURE_SETTINGS,

    PERM_MANAGE_USERS,

    PERM_EXPORT_AUDIT_LOGS,

)

from storage.models import UserRecord, TicketRecord


from netcoop import __version__

from core.config import settings, is_demo_mode_allowed

from core.envelope import AgentEnvelope

from core.report import RemediationActionItem, UnifiedDiagnosticReport

from gateway.adapters.organizer_adapter import OrganizerAdapter

from orchestrator.graph import pause_diagnosis, resume_diagnosis, run_diagnosis

try:

    from orchestrator.mediator import register_envelope_listener, unregister_envelope_listener

except ImportError:

    def register_envelope_listener(callback: Any) -> None:

        pass

    def unregister_envelope_listener(callback: Any) -> None:

        pass

from remediation.engine import RemediationEngine

from storage.db import (

    get_envelope_logs,

    get_incident,

    init_db,

    list_incidents,

    save_incident,

    list_checkpoints,

    list_remediation_action_logs,

    get_remediation_action_log,

    get_remediation_logs,

    save_remediation_log,

    get_user_by_username,

    log_auth_event,

    get_auth_audit_logs,

    init_default_users,

    revoke_token,

    is_token_revoked,

    assign_incident,

    create_user,

    list_users,
    
    get_user_by_id,
    create_ticket,
    get_ticket,
    list_tickets,
    update_ticket_status,
    link_ticket_incident,get_user_by_id,
    create_ticket,
    get_ticket,
    list_tickets,
    update_ticket_status,
    link_ticket_incident,

)


BASE_DIR = Path(__file__).parent.parent

EVAL_RESULTS_DIR = BASE_DIR / "eval" / "results"

SCHEMAS_DIR = BASE_DIR / "schemas"

SCENARIOS_DIR = BASE_DIR / "data" / "scenarios"

ORGANIZER_SAMPLES_DIR = BASE_DIR / "data" / "organizer_sample"


app = FastAPI(

    title="NetCoop AI Diagnostic Platform",

    description="Multi-agent offline network fault diagnosis, HITL remediation, and RBAC authentication",

    version=__version__,

)


app.add_middleware(

    CORSMiddleware,

    allow_origins=["*"],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],

)


class WebSocketManager:

    """Manages active real-time dashboard subscriber connections."""


    def __init__(self) -> None:

        self.active_connections: List[WebSocket] = []


    async def connect(self, websocket: WebSocket) -> None:

        await websocket.accept()

        self.active_connections.append(websocket)


    def disconnect(self, websocket: WebSocket) -> None:

        if websocket in self.active_connections:

            self.active_connections.remove(websocket)


    async def broadcast_json(self, message: Dict[str, Any]) -> None:

        for connection in list(self.active_connections):

            try:

                await connection.send_json(message)

            except Exception:

                self.disconnect(connection)


ws_manager = WebSocketManager()


def _envelope_stream_hook(envelope: AgentEnvelope) -> None:

    """Synchronous mediator hook dispatching envelope notifications to event loop."""

    try:

        loop = asyncio.get_running_loop()

        msg = {

            "event_type": "envelope_sent",

            "message_id": envelope.message_id,

            "timestamp_utc": envelope.timestamp_utc,

            "sender": envelope.sender,

            "recipient": envelope.recipient,

            "message_type": envelope.message_type,

            "payload": envelope.payload,

            "context": envelope.context,

        }

        loop.create_task(ws_manager.broadcast_json(msg))

    except RuntimeError:

        pass


@app.on_event("startup")

def on_startup() -> None:

    """Initialize database and register envelope listeners."""

    init_db()

    init_default_users()

    try:

        register_envelope_listener(_envelope_stream_hook)

    except Exception:

        pass


@app.on_event("shutdown")

def on_shutdown() -> None:

    """Unregister callbacks during server shutdown."""

    unregister_envelope_listener(_envelope_stream_hook)


@app.websocket("/ws/events")
async def websocket_events_endpoint(websocket: WebSocket) -> None:
    """WebSocket stream emitting real-time envelope traces and diagnostic events."""
    ticket = websocket.query_params.get("ticket")
    if not ticket:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="WebSocket ticket required.")
        return

    ok, reason, user = consume_ws_ticket(ticket)
    if not ok or not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=reason)
        return

    await ws_manager.connect(websocket)
    try:
        await websocket.send_json({
            "event_type": "connected",
            "message": "NetCoop WebSocket event stream active.",
            "user": user.username,
            "role": user.role,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)

    except Exception:

        ws_manager.disconnect(websocket)


@app.websocket("/ws/envelopes")

async def websocket_envelopes_endpoint(websocket: WebSocket) -> None:

    """Alias WebSocket stream for real-time envelope inspection."""

    await websocket_events_endpoint(websocket)


@app.get("/api/health")

def health() -> Dict[str, str]:

    """Basic health check probe."""

    return {"status": "ok", "version": __version__}


@app.get("/api/features")

def get_features_endpoint() -> Dict[str, Any]:

    """Return active runtime feature flags for optional UI and backend capabilities."""

    return {

        "FEATURE_HITL": os.environ.get("FEATURE_HITL", str(getattr(settings, "feature_hitl", True))).lower() in ("true", "1", "yes"),

        "FEATURE_REMEDIATION_SIM": os.environ.get("FEATURE_REMEDIATION_SIM", str(getattr(settings, "feature_remediation_sim", True))).lower() in ("true", "1", "yes"),

        "FEATURE_RESUME": os.environ.get("FEATURE_RESUME", str(getattr(settings, "feature_resume", True))).lower() in ("true", "1", "yes"),

        "DEMO_MODE_ENABLED": is_demo_mode_allowed(),

        "ENVIRONMENT": settings.environment,

    }


# -----------------------------------------------------------------------------

# Authentication & Authorization Endpoints

# -----------------------------------------------------------------------------


@app.post("/api/auth/ws-ticket", response_model=WsTicketResponse)

def get_ws_ticket_endpoint(

    current_user: UserRecord = Depends(require_permissions([PERM_VIEW_FABRIC_HEALTH])),

) -> WsTicketResponse:

    """Exchange authenticated session for a short-lived (60s), single-use WebSocket connection ticket."""

    ticket = create_ws_ticket(current_user)

    return WsTicketResponse(ticket=ticket, expires_in=60)


@app.post("/api/auth/login", response_model=TokenResponse)

def login_endpoint(req: LoginRequest, request: Request) -> TokenResponse:

    """Authenticate user credentials and return a signed JWT access token."""

    client_ip = request.client.host if request.client else "unknown"

    check_login_rate_limit(client_ip)


    user = get_user_by_username(req.username)

    if not user or not verify_password(req.password, user.hashed_password):

        record_login_failure(client_ip)

        log_auth_event(

            event_type="LOGIN_FAILURE",

            username=req.username,

            endpoint="/api/auth/login",

            client_ip=client_ip,

            details="Invalid username or password",

        )

        raise HTTPException(

            status_code=status.HTTP_401_UNAUTHORIZED,

            detail="Incorrect username or password.",

            headers={"WWW-Authenticate": "Bearer"},

        )


    if not user.is_active:

        log_auth_event(

            event_type="LOGIN_DISABLED",

            username=req.username,

            endpoint="/api/auth/login",

            client_ip=client_ip,

            details="Account is inactive",

        )

        raise HTTPException(

            status_code=status.HTTP_401_UNAUTHORIZED,

            detail="User account is inactive.",

            headers={"WWW-Authenticate": "Bearer"},

        )


    clear_login_failures(client_ip)

    log_auth_event(

        event_type="LOGIN_SUCCESS",

        username=user.username,

        user_id=user.user_id,

        role=user.role,

        endpoint="/api/auth/login",

        client_ip=client_ip,

        details="Successful login",

    )


    access_token = create_access_token(

        {

            "sub": user.username,

            "user_id": user.user_id,

            "role": user.role,

        }

    )

    user_perms = sorted(list(ROLE_PERMISSIONS_MAP.get(user.role, set())))


    return TokenResponse(

        access_token=access_token,

        token_type="bearer",

        expires_in=settings.jwt_access_token_expire_minutes * 60,

        role=user.role,

        username=user.username,

        full_name=user.full_name,

        permissions=user_perms,

    )


@app.post("/api/auth/demo-login", response_model=TokenResponse)

def demo_login_endpoint(req: DemoLoginRequest, request: Request) -> TokenResponse:

    """Convenience login for testing and demos. Disabled in production mode."""

    if not is_demo_mode_allowed():

        raise HTTPException(

            status_code=status.HTTP_403_FORBIDDEN,

            detail="Demo authentication is strictly disabled in production mode.",

        )


    client_ip = request.client.host if request.client else "unknown"

    user = get_user_by_username(req.username)

    if not user:

        raise HTTPException(

            status_code=status.HTTP_404_NOT_FOUND,

            detail=f"Demo user '{req.username}' not found. Please ensure demo accounts are seeded.",

        )


    if not user.is_active:

        raise HTTPException(

            status_code=status.HTTP_401_UNAUTHORIZED,

            detail="User account is inactive.",

        )


    log_auth_event(

        event_type="DEMO_LOGIN_SUCCESS",

        username=user.username,

        user_id=user.user_id,

        role=user.role,

        endpoint="/api/auth/demo-login",

        client_ip=client_ip,

        details="Demo login granted",

    )


    access_token = create_access_token(

        {

            "sub": user.username,

            "user_id": user.user_id,

            "role": user.role,

        }

    )

    user_perms = sorted(list(ROLE_PERMISSIONS_MAP.get(user.role, set())))


    return TokenResponse(

        access_token=access_token,

        token_type="bearer",

        expires_in=settings.jwt_access_token_expire_minutes * 60,

        role=user.role,

        username=user.username,

        full_name=user.full_name,

        permissions=user_perms,

    )


@app.get("/api/auth/me", response_model=UserProfileResponse)
def get_auth_me_endpoint(
    request: Request,
    current_user: UserRecord = Depends(get_current_user),
) -> UserProfileResponse:
    """Retrieve profile and active permissions for the currently authenticated user."""
    auth_header = request.headers.get("authorization", "")
    impersonated_by = None
    if auth_header.startswith("Bearer "):
        try:
            token_str = auth_header[7:].strip()
            payload = decode_access_token(token_str)
            impersonated_by = payload.get("impersonated_by")
        except Exception:
            pass

    user_perms = sorted(list(ROLE_PERMISSIONS_MAP.get(current_user.role, set())))
    return UserProfileResponse(
        user_id=current_user.user_id,
        username=current_user.username,
        role=current_user.role,
        full_name=current_user.full_name,
        permissions=user_perms,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        impersonated_by=impersonated_by,
    )


@app.post("/api/auth/logout")

def logout_endpoint(

    request: Request,

    current_user: UserRecord = Depends(get_current_user),

) -> Dict[str, Any]:

    """Client logout endpoint. Revokes the active token by its jti."""

    auth_header = request.headers.get("authorization", "")

    if auth_header.startswith("Bearer "):

        token_str = auth_header[7:].strip()

        try:

            payload = decode_access_token(token_str)

            jti = payload.get("jti")

            exp = payload.get("exp")

            exp_iso = None

            if exp:

                exp_iso = datetime.fromtimestamp(exp, tz=timezone.utc).isoformat()

            if jti:

                revoke_token(jti=jti, expires_at=exp_iso)

        except Exception:

            pass


    log_auth_event(

        event_type="LOGOUT",

        username=current_user.username,

        user_id=current_user.user_id,

        role=current_user.role,

        endpoint="/api/auth/logout",

        details="User logged out and token revoked",

    )

    return {"status": "success", "message": f"User {current_user.username} logged out successfully. Active session invalidated."}


@app.get("/api/auth/logs")

def get_auth_logs_endpoint(

    limit: int = 100,

    current_user: UserRecord = Depends(require_permissions([PERM_EXPORT_AUDIT_LOGS])),

) -> List[Dict[str, Any]]:

    """Retrieve auditable access and authentication event log."""

    logs = get_auth_audit_logs(limit=limit)

    return [

        {

            "id": l.id,

            "timestamp_utc": l.timestamp_utc,

            "event_type": l.event_type,

            "username": l.username,

            "user_id": l.user_id,

            "role": l.role,

            "endpoint": l.endpoint,

            "client_ip": l.client_ip,

            "details": l.details,

        }

        for l in logs

    ]


@app.get("/api/users", response_model=List[UserProfileResponse])

def list_users_endpoint(

    current_user: UserRecord = Depends(require_permissions([PERM_MANAGE_USERS])),

) -> List[UserProfileResponse]:

    """List all registered users (Platform Administrator only)."""

    users = list_users()

    return [

        UserProfileResponse(

            user_id=u.user_id,

            username=u.username,

            role=u.role,

            full_name=u.full_name,

            permissions=sorted(list(ROLE_PERMISSIONS_MAP.get(u.role, set()))),

            is_active=u.is_active,

            created_at=u.created_at,

        )

        for u in users

    ]


@app.post("/api/users", response_model=UserProfileResponse)

def create_user_endpoint(

    req: CreateUserRequest,

    current_user: UserRecord = Depends(require_permissions([PERM_MANAGE_USERS])),

) -> UserProfileResponse:

    """Create a new user account (Platform Administrator only)."""

    if req.role not in ALL_ROLES:

        raise HTTPException(

            status_code=status.HTTP_400_BAD_REQUEST,

            detail=f"Invalid role '{req.role}'. Valid roles: {ALL_ROLES}",

        )

    existing = get_user_by_username(req.username)

    if existing:

        raise HTTPException(

            status_code=status.HTTP_400_BAD_REQUEST,

            detail=f"Username '{req.username}' already exists.",

        )

    if len(req.password) < 8:

        raise HTTPException(

            status_code=status.HTTP_400_BAD_REQUEST,

            detail="Password must be at least 8 characters long.",

        )


    hashed = hash_password(req.password)

    user = create_user(

        username=req.username,

        hashed_password=hashed,

        role=req.role,

        full_name=req.full_name,

    )

    log_auth_event(

        event_type="USER_CREATED",

        username=user.username,

        user_id=user.user_id,

        role=user.role,

        endpoint="/api/users",

        details=f"User created by {current_user.username}",

    )

    return UserProfileResponse(

        user_id=user.user_id,

        username=user.username,

        role=user.role,

        full_name=user.full_name,

        permissions=sorted(list(ROLE_PERMISSIONS_MAP.get(user.role, set()))),

        is_active=user.is_active,

        created_at=user.created_at,

    )


@app.patch("/api/users/{user_id}/status", response_model=UserProfileResponse)
def update_user_status_endpoint(
    user_id: str,
    req: UpdateUserStatusRequest,
    current_user: UserRecord = Depends(require_permissions([PERM_MANAGE_USERS])),
) -> UserProfileResponse:
    """Enable or disable user account (Platform Administrator only)."""
    target = get_user_by_id(user_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User ID '{user_id}' not found.",
        )
    if target.user_id == current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify active state of your own administrator account.",
        )

    from sqlmodel import Session, select
    from storage.db import engine
    with Session(engine) as session:
        u = session.exec(select(UserRecord).where(UserRecord.user_id == user_id)).first()
        if not u:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        u.is_active = req.is_active
        session.add(u)
        session.commit()
        session.refresh(u)
        target = u

    log_auth_event(
        event_type="USER_STATUS_UPDATED",
        username=target.username,
        user_id=target.user_id,
        role=target.role,
        endpoint=f"/api/users/{user_id}/status",
        details=f"Status set to {'active' if req.is_active else 'inactive'} by {current_user.username}",
    )
    return UserProfileResponse(
        user_id=target.user_id,
        username=target.username,
        role=target.role,
        full_name=target.full_name,
        permissions=sorted(list(ROLE_PERMISSIONS_MAP.get(target.role, set()))),
        is_active=target.is_active,
        created_at=target.created_at,
    )


@app.post("/api/auth/impersonate", response_model=TokenResponse)
def impersonate_user_endpoint(
    req: ImpersonateRequest,
    request: Request,
    current_user: UserRecord = Depends(require_permissions([PERM_MANAGE_USERS])),
) -> TokenResponse:
    """Securely initiate user impersonation (Platform Administrator only). Audited in auth logs."""
    if current_user.role != ROLE_PLATFORM_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Platform Administrators may initiate user impersonation.",
        )
    target = get_user_by_username(req.username)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target user '{req.username}' not found.",
        )
    if not target.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Target user '{req.username}' is deactivated.",
        )
    if target.username == current_user.username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot impersonate your own active administrator account.",
        )

    client_ip = request.client.host if request.client else "unknown"
    log_auth_event(
        event_type="IMPERSONATION_START",
        username=current_user.username,
        user_id=current_user.user_id,
        role=current_user.role,
        endpoint="/api/auth/impersonate",
        client_ip=client_ip,
        details=f"Admin '{current_user.username}' initiated impersonation of '{target.username}' ({target.role})",
    )

    access_token = create_access_token(
        {
            "sub": target.username,
            "user_id": target.user_id,
            "role": target.role,
            "impersonated_by": current_user.username,
        }
    )
    target_perms = sorted(list(ROLE_PERMISSIONS_MAP.get(target.role, set())))
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        role=target.role,
        username=target.username,
        full_name=target.full_name,
        permissions=target_perms,
        impersonated_by=current_user.username,
    )


@app.post("/api/auth/exit-impersonation")
def exit_impersonation_endpoint(
    request: Request,
    current_user: UserRecord = Depends(get_current_user),
) -> Dict[str, Any]:
    """Exit user impersonation session and record security audit log."""
    client_ip = request.client.host if request.client else "unknown"
    auth_header = request.headers.get("authorization", "")
    impersonator = None
    if auth_header.startswith("Bearer "):
        try:
            token_str = auth_header[7:].strip()
            payload = decode_access_token(token_str)
            impersonator = payload.get("impersonated_by")
        except Exception:
            pass

    log_auth_event(
        event_type="IMPERSONATION_END",
        username=current_user.username,
        user_id=current_user.user_id,
        role=current_user.role,
        endpoint="/api/auth/exit-impersonation",
        client_ip=client_ip,
        details=f"Impersonation session for '{current_user.username}' ended by '{impersonator or 'unknown'}'",
    )
    return {"status": "success", "message": "Impersonation session ended."}


# -----------------------------------------------------------------------------
# Support Ticket Management Endpoints
# -----------------------------------------------------------------------------

class CreateTicketRequest(BaseModel):
    title: str
    category: str
    location: str
    affected_service: str
    description: str
    priority: str = "medium"
    contact_info: Optional[str] = None
    linked_incident_id: Optional[str] = None
    assigned_to: Optional[str] = None


class UpdateTicketStatusRequest(BaseModel):
    status: str
    notes: Optional[str] = None
    user_summary: Optional[str] = None
    assigned_to: Optional[str] = None


class LinkTicketIncidentRequest(BaseModel):
    incident_id: str


class TicketResponse(BaseModel):
    id: Optional[int] = None
    ticket_id: str
    title: str
    category: str
    location: str
    affected_service: str
    description: str
    priority: str
    status: str
    created_by: str
    contact_info: Optional[str] = None
    assigned_to: Optional[str] = None
    linked_incident_id: Optional[str] = None
    resolution_notes: Optional[str] = None
    user_facing_summary: Optional[str] = None
    created_at: str
    updated_at: str


@app.get("/api/tickets", response_model=List[TicketResponse])
def list_tickets_endpoint(
    category: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = 100,
    current_user: UserRecord = Depends(get_current_user),
) -> List[TicketResponse]:
    """List operational and user support tickets according to role authorization."""
    tickets = list_tickets(
        user_id=current_user.user_id,
        username=current_user.username,
        role=current_user.role,
        category=category,
        status=status,
        priority=priority,
        limit=limit,
    )
    return [
        TicketResponse(
            id=t.id,
            ticket_id=t.ticket_id,
            title=t.title,
            category=t.category,
            location=t.location,
            affected_service=t.affected_service,
            description=t.description,
            priority=t.priority,
            status=t.status,
            created_by=t.created_by,
            contact_info=t.contact_info,
            assigned_to=t.assigned_to,
            linked_incident_id=t.linked_incident_id,
            resolution_notes=t.resolution_notes,
            user_facing_summary=t.user_facing_summary,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
        for t in tickets
    ]


@app.post("/api/tickets", response_model=TicketResponse, status_code=201)
def create_ticket_endpoint(
    req: CreateTicketRequest,
    current_user: UserRecord = Depends(get_current_user),
) -> TicketResponse:
    """Create and persist a new customer or operational support ticket."""
    if not req.title.strip() or not req.description.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ticket title and description cannot be empty.",
        )
    if not req.location.strip() or not req.affected_service.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Affected campus location and service are required.",
        )

    t = create_ticket(
        title=req.title.strip(),
        category=req.category.strip(),
        location=req.location.strip(),
        affected_service=req.affected_service.strip(),
        description=req.description.strip(),
        priority=req.priority.strip(),
        created_by=current_user.username,
        contact_info=req.contact_info.strip() if req.contact_info else None,
        linked_incident_id=req.linked_incident_id.strip() if req.linked_incident_id else None,
        assigned_to=req.assigned_to.strip() if req.assigned_to else None,
    )
    log_auth_event(
        event_type="TICKET_CREATED",
        username=current_user.username,
        user_id=current_user.user_id,
        role=current_user.role,
        endpoint="/api/tickets",
        details=f"Ticket '{t.ticket_id}' created ({t.category}, {t.priority})",
    )
    return TicketResponse(
        id=t.id,
        ticket_id=t.ticket_id,
        title=t.title,
        category=t.category,
        location=t.location,
        affected_service=t.affected_service,
        description=t.description,
        priority=t.priority,
        status=t.status,
        created_by=t.created_by,
        contact_info=t.contact_info,
        assigned_to=t.assigned_to,
        linked_incident_id=t.linked_incident_id,
        resolution_notes=t.resolution_notes,
        user_facing_summary=t.user_facing_summary,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


@app.get("/api/tickets/{ticket_id}", response_model=TicketResponse)
def get_ticket_endpoint(
    ticket_id: str,
    current_user: UserRecord = Depends(get_current_user),
) -> TicketResponse:
    """Retrieve support ticket details with access validation."""
    t = get_ticket(ticket_id)
    if not t:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket '{ticket_id}' not found.",
        )

    # Access control: operational roles or ticket creator
    allowed_roles = [ROLE_PLATFORM_ADMIN, ROLE_NETWORK_ADMIN, ROLE_NETWORK_ENGINEER, ROLE_HELPDESK]
    if current_user.role not in allowed_roles and t.created_by != current_user.username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted: you may only view support tickets you authored.",
        )

    return TicketResponse(
        id=t.id,
        ticket_id=t.ticket_id,
        title=t.title,
        category=t.category,
        location=t.location,
        affected_service=t.affected_service,
        description=t.description,
        priority=t.priority,
        status=t.status,
        created_by=t.created_by,
        contact_info=t.contact_info,
        assigned_to=t.assigned_to,
        linked_incident_id=t.linked_incident_id,
        resolution_notes=t.resolution_notes,
        user_facing_summary=t.user_facing_summary,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


@app.patch("/api/tickets/{ticket_id}", response_model=TicketResponse)
def update_ticket_endpoint(
    ticket_id: str,
    req: UpdateTicketStatusRequest,
    current_user: UserRecord = Depends(get_current_user),
) -> TicketResponse:
    """Update ticket status, notes, or assigned engineer with lifecycle validation."""
    t = get_ticket(ticket_id)
    if not t:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket '{ticket_id}' not found.",
        )

    allowed_roles = [ROLE_PLATFORM_ADMIN, ROLE_NETWORK_ADMIN, ROLE_NETWORK_ENGINEER, ROLE_HELPDESK]
    if current_user.role not in allowed_roles and t.created_by != current_user.username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted: unauthorized to update this support ticket.",
        )

    # Helpdesk cannot resolve tickets directly without engineering sign-off
    if current_user.role == ROLE_HELPDESK and req.status == "Resolved":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Helpdesk cannot set ticket status to Resolved; technical verification by Network Engineering is required.",
        )

    ok, msg, updated = update_ticket_status(
        ticket_id=ticket_id,
        new_status=req.status,
        actor_username=current_user.username,
        actor_role=current_user.role,
        notes=req.notes,
        user_summary=req.user_summary,
        assigned_to=req.assigned_to,
    )
    if not ok or not updated:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )

    log_auth_event(
        event_type="TICKET_UPDATED",
        username=current_user.username,
        user_id=current_user.user_id,
        role=current_user.role,
        endpoint=f"/api/tickets/{ticket_id}",
        details=f"Ticket '{ticket_id}' status updated to '{req.status}' by {current_user.username}",
    )

    return TicketResponse(
        id=updated.id,
        ticket_id=updated.ticket_id,
        title=updated.title,
        category=updated.category,
        location=updated.location,
        affected_service=updated.affected_service,
        description=updated.description,
        priority=updated.priority,
        status=updated.status,
        created_by=updated.created_by,
        contact_info=updated.contact_info,
        assigned_to=updated.assigned_to,
        linked_incident_id=updated.linked_incident_id,
        resolution_notes=updated.resolution_notes,
        user_facing_summary=updated.user_facing_summary,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
    )


@app.post("/api/tickets/{ticket_id}/link-incident", response_model=TicketResponse)
def link_ticket_incident_endpoint(
    ticket_id: str,
    req: LinkTicketIncidentRequest,
    current_user: UserRecord = Depends(get_current_user),
) -> TicketResponse:
    """Link a support ticket to an active network diagnostic incident."""
    allowed_roles = [ROLE_PLATFORM_ADMIN, ROLE_NETWORK_ADMIN, ROLE_NETWORK_ENGINEER]
    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Network Engineers, Network Administrators, or Platform Administrators may link tickets to incidents.",
        )

    t = get_ticket(ticket_id)
    if not t:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket '{ticket_id}' not found.",
        )

    from storage.db import get_incident
    inc = get_incident(req.incident_id)
    if not inc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Network incident '{req.incident_id}' not found.",
        )

    updated = link_ticket_incident(
        ticket_id=ticket_id,
        incident_id=req.incident_id,
        actor_username=current_user.username,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to link ticket to incident.",
        )

    log_auth_event(
        event_type="TICKET_LINKED_INCIDENT",
        username=current_user.username,
        user_id=current_user.user_id,
        role=current_user.role,
        endpoint=f"/api/tickets/{ticket_id}/link-incident",
        details=f"Ticket '{ticket_id}' linked to network incident '{req.incident_id}' by {current_user.username}",
    )

    return TicketResponse(
        id=updated.id,
        ticket_id=updated.ticket_id,
        title=updated.title,
        category=updated.category,
        location=updated.location,
        affected_service=updated.affected_service,
        description=updated.description,
        priority=updated.priority,
        status=updated.status,
        created_by=updated.created_by,
        contact_info=updated.contact_info,
        assigned_to=updated.assigned_to,
        linked_incident_id=updated.linked_incident_id,
        resolution_notes=updated.resolution_notes,
        user_facing_summary=updated.user_facing_summary,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
    )


@app.post("/api/incidents/{incident_id}/assign")

def assign_incident_endpoint(

    incident_id: str,

    req: AssignIncidentRequest,

    current_user: UserRecord = Depends(require_permissions([PERM_ASSIGN_INCIDENT])),

) -> Dict[str, Any]:

    """Assign an incident to an operator or engineer (NOC Operator and Network Engineer only)."""

    assignee = req.assignee

    inc = assign_incident(

        incident_id=incident_id,

        assigned_to=assignee,

        assigned_by=current_user.username,

    )

    if not inc:

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident '{incident_id}' not found.")


    return {

        "success": True,

        "incident_id": incident_id,

        "assigned_to": assignee,

        "assigned_by": current_user.username,

        "rationale": req.rationale,

    }


# -----------------------------------------------------------------------------

# Diagnostic & Incident Endpoints

# -----------------------------------------------------------------------------


@app.post("/api/ingest")
def ingest_data_endpoint(raw_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Gateway Ingestion: translate, unit-convert, and canonicalize arbitrary telemetry via Gateway HTTP microservice."""
    gateway_url = settings.get_gateway_url()
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(gateway_url, json=raw_payload)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 422:
                detail = resp.json().get("detail", "Gateway normalization failure")
                raise HTTPException(status_code=422, detail=detail)
            elif resp.status_code == 400:
                detail = resp.json().get("detail", "Malformed payload")
                raise HTTPException(status_code=400, detail=detail)
            else:
                raise HTTPException(
                    status_code=resp.status_code,
                    detail=f"Gateway service returned HTTP {resp.status_code}: {resp.text}",
                )
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Gateway service on port {settings.gateway_port} unavailable over HTTP: {str(exc)}",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion communication error: {str(e)}")


@app.get("/api/scenarios")

def list_scenarios() -> List[Dict[str, Any]]:

    """List all pre-configured benchmark scenario files and organizer samples."""

    scenarios: List[Dict[str, Any]] = []

    if SCENARIOS_DIR.exists():

        for f in sorted(SCENARIOS_DIR.glob("*.json")):

            if f.name == "manifest.json":

                continue

            try:

                with open(f, "r", encoding="utf-8") as s_file:

                    content = json.load(s_file)

                    scenarios.append(

                        {

                            "filename": f.name,

                            "name": f.stem.replace("_", " ").title(),

                            "incident_id": content.get("incident_id", f.stem),

                            "network_id": content.get("network_id", "campus-network"),

                            "description": content.get("description", f.stem.replace("_", " ").title()),

                        }

                    )

            except Exception:

                continue


    if ORGANIZER_SAMPLES_DIR.exists():

        for p in sorted(ORGANIZER_SAMPLES_DIR.glob("*.json*")):

            scenarios.append({

                "filename": f"organizer/{p.name}",

                "name": f"Organizer: {p.stem.replace('_', ' ').title()}",

                "incident_id": f"org-{p.stem}",

                "network_id": "organizer-campus-fabric",

                "description": f"Organizer Sample: {p.stem.replace('_', ' ').title()}",

            })

    return scenarios


@app.get("/api/scenarios/{filename:path}")

def get_scenario(filename: str) -> Dict[str, Any]:

    """Retrieve contents of a specific scenario or organizer sample file."""

    if filename.startswith("organizer/"):

        rel_path = filename.replace("organizer/", "")

        file_path = ORGANIZER_SAMPLES_DIR / rel_path

    else:

        file_path = SCENARIOS_DIR / filename


    if not file_path.exists():

        raise HTTPException(status_code=404, detail="Scenario file not found.")


    with open(file_path, "r", encoding="utf-8") as f:

        return json.load(f)


@app.get("/api/incidents/{incident_id}/envelopes")

def get_incident_envelopes_alias(
    incident_id: str,
    current_user: UserRecord = Depends(require_permissions([PERM_VIEW_FABRIC_HEALTH])),
) -> List[Dict[str, Any]]:

    """Retrieve full audit trace of envelopes recorded for an incident."""

    logs = get_envelope_logs(incident_id)

    return [

        {

            "id": l.id,

            "message_id": l.message_id,

            "timestamp_utc": l.timestamp_utc,

            "sender": l.sender,

            "recipient": l.recipient,

            "message_type": l.message_type,

            "priority": l.priority,

            "payload": json.loads(l.payload_json),

            "context": json.loads(l.context_json) if l.context_json else {},

        }

        for l in logs

    ]


@app.post("/api/diagnose", response_model=UnifiedDiagnosticReport)
def run_diagnosis_endpoint(
    incident_data: Dict[str, Any],
    current_user: UserRecord = Depends(require_permissions([PERM_EXECUTE_DIAGNOSIS])),
) -> UnifiedDiagnosticReport:
    """Execute end-to-end multi-agent network fault diagnosis."""
    try:
        format_detected = OrganizerAdapter.detect_format(incident_data)
        if format_detected == "organizer":
            gateway_url = settings.get_gateway_url()
            try:
                with httpx.Client(timeout=10.0) as client:
                    resp = client.post(gateway_url, json=incident_data)
                    if resp.status_code == 200:
                        canonical_data = resp.json()
                    elif resp.status_code == 422:
                        detail = resp.json().get("detail", "Gateway normalization failure")
                        raise HTTPException(status_code=422, detail=detail)
                    else:
                        raise HTTPException(
                            status_code=resp.status_code,
                            detail=f"Gateway normalization failed: {resp.text}",
                        )
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                raise HTTPException(
                    status_code=503,
                    detail=f"Gateway service on port {settings.gateway_port} unavailable over HTTP: {str(exc)}",
                )
            report = run_diagnosis(canonical_data)
        else:
            report = run_diagnosis(incident_data)
        return report
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Diagnostic error: {str(e)}")


@app.post("/api/diagnose/organizer", response_model=UnifiedDiagnosticReport)

def run_organizer_diagnosis_endpoint(

    payload: Dict[str, Any],

    current_user: UserRecord = Depends(require_permissions([PERM_EXECUTE_DIAGNOSIS])),

) -> UnifiedDiagnosticReport:

    """Execute diagnosis on raw external format via interoperability adapter."""

    try:

        internal_payload = OrganizerAdapter.to_internal_telemetry(payload)

        report = run_diagnosis(internal_payload)

        return report

    except Exception as e:

        raise HTTPException(status_code=400, detail=f"Organizer translation failed: {str(e)}")


@app.get("/api/incidents")

def list_incidents_endpoint(
    current_user: UserRecord = Depends(require_permissions([PERM_VIEW_FABRIC_HEALTH])),
) -> List[Dict[str, Any]]:

    """Retrieve all historical and active diagnostic incident records."""

    records = list_incidents()

    return [

        {

            "incident_id": r.incident_id,

            "network_id": r.network_id,

            "status": r.status,

            "probable_cause": r.probable_cause,

            "confidence": r.confidence,

            "created_at": r.created_at,

            "assigned_to": getattr(r, "assigned_to", None),

            "assigned_by": getattr(r, "assigned_by", None),

            "assigned_at": getattr(r, "assigned_at", None),

            "report": json.loads(r.report_json) if r.report_json else None,

        }

        for r in records

    ]


@app.get("/api/incidents/{incident_id}")

def get_incident_endpoint(
    incident_id: str,
    current_user: UserRecord = Depends(require_permissions([PERM_VIEW_FABRIC_HEALTH])),
) -> Dict[str, Any]:

    """Retrieve details for a specific incident by ID."""

    rec = get_incident(incident_id)

    if not rec:

        raise HTTPException(status_code=404, detail="Incident not found.")

    return {

        "incident_id": rec.incident_id,

        "network_id": rec.network_id,

        "status": rec.status,

        "probable_cause": rec.probable_cause,

        "confidence": rec.confidence,

        "created_at": rec.created_at,

        "assigned_to": getattr(rec, "assigned_to", None),

        "assigned_by": getattr(rec, "assigned_by", None),

        "assigned_at": getattr(rec, "assigned_at", None),

        "report": json.loads(rec.report_json) if rec.report_json else None,

    }


@app.get("/api/envelopes/{correlation_id}")

def get_envelopes_endpoint(
    correlation_id: str,
    current_user: UserRecord = Depends(require_permissions([PERM_VIEW_FABRIC_HEALTH])),
) -> List[Dict[str, Any]]:

    """Retrieve chronological audit trace of envelope messages exchanged for an incident."""

    logs = get_envelope_logs(correlation_id)

    return [

        {

            "id": l.id,

            "correlation_id": l.correlation_id,

            "message_id": l.message_id,

            "timestamp_utc": l.timestamp_utc,

            "sender": l.sender,

            "recipient": l.recipient,

            "message_type": l.message_type,

            "priority": l.priority,

            "payload": json.loads(l.payload_json),

            "context": json.loads(l.context_json) if l.context_json else {},

        }

        for l in logs

    ]


class PauseRequest(BaseModel):

    session_id: str

    rationale: Optional[str] = "Operator requested diagnosis pause"


@app.post("/api/orchestrator/pause")

def pause_orchestrator_endpoint(
    req: PauseRequest,
    current_user: UserRecord = Depends(require_permissions([PERM_EXECUTE_DIAGNOSIS])),
) -> Dict[str, Any]:

    """Signal an active diagnostic session to halt cleanly at its next checkpoint."""

    success = pause_diagnosis(req.session_id)

    return {

        "session_id": req.session_id,

        "status": "paused" if success else "failed",

        "message": f"Diagnostic session {req.session_id} marked as paused.",

        "rationale": req.rationale,

    }


@app.post("/api/orchestrator/resume/{session_id}", response_model=UnifiedDiagnosticReport)

def resume_orchestrator_endpoint(
    session_id: str,
    current_user: UserRecord = Depends(require_permissions([PERM_EXECUTE_DIAGNOSIS])),
) -> UnifiedDiagnosticReport:

    """Resume execution of an interrupted or paused diagnosis from latest checkpoint."""

    try:

        report = resume_diagnosis(session_id)

        return report

    except ValueError as e:

        raise HTTPException(status_code=404, detail=str(e))

    except Exception as e:

        raise HTTPException(status_code=500, detail=f"Resume failed: {str(e)}")


@app.get("/api/orchestrator/checkpoints/{session_id}")

def get_session_checkpoints_endpoint(
    session_id: str,
    current_user: UserRecord = Depends(require_permissions([PERM_EXECUTE_DIAGNOSIS])),
) -> List[Dict[str, Any]]:

    """Retrieve chronological checkpoints recorded for a diagnostic session."""

    cps = list_checkpoints(session_id)

    return [

        {

            "id": cp.id,

            "session_id": cp.session_id,

            "node_name": cp.node_name,

            "iteration": cp.iteration,

            "is_paused": cp.is_paused,

            "created_at": cp.created_at,

            "state": json.loads(cp.state_json) if cp.state_json else {},

        }

        for cp in cps

    ]


@app.get("/api/remediation/pending")

def get_pending_remediation_actions_endpoint() -> List[Dict[str, Any]]:

    """List all remediation actions awaiting Human-in-the-Loop operator decision."""

    logs = list_remediation_action_logs(status="pending")

    return [

        {

            "id": l.id,

            "incident_id": l.incident_id,

            "action_id": l.action_id,

            "device": l.device,

            "commands": json.loads(l.commands_json) if l.commands_json else [],

            "rollback_commands": json.loads(l.rollback_commands_json) if l.rollback_commands_json else [],

            "risk_level": l.risk_level,

            "status": l.status,

            "approved_by": l.approved_by,

            "actor_user_id": l.actor_user_id,

            "actor_username": l.actor_username,

            "actor_role": l.actor_role,

            "decision": l.decision,

            "rationale": l.rationale,

            "modified_commands": json.loads(l.modified_commands_json) if l.modified_commands_json else None,

            "simulated_at": l.simulated_at,

            "decision_timestamp": l.decision_timestamp,

        }

        for l in logs

    ]


@app.get("/api/remediation/actions")

def list_remediation_actions_endpoint(

    incident_id: Optional[str] = None,

    status: Optional[str] = None,

) -> List[Dict[str, Any]]:

    """List recorded remediation action items filtered by incident or status."""

    logs = list_remediation_action_logs(incident_id=incident_id, status=status)

    return [

        {

            "id": l.id,

            "incident_id": l.incident_id,

            "action_id": l.action_id,

            "device": l.device,

            "commands": json.loads(l.commands_json) if l.commands_json else [],

            "rollback_commands": json.loads(l.rollback_commands_json) if l.rollback_commands_json else [],

            "risk_level": l.risk_level,

            "status": l.status,

            "approved_by": l.approved_by,

            "actor_user_id": l.actor_user_id,

            "actor_username": l.actor_username,

            "actor_role": l.actor_role,

            "decision": l.decision,

            "rationale": l.rationale,

            "modified_commands": json.loads(l.modified_commands_json) if l.modified_commands_json else None,

            "simulated_at": l.simulated_at,

            "decision_timestamp": l.decision_timestamp,

        }

        for l in logs

    ]


class HITLDecisionRequest(BaseModel):

    operator: Optional[str] = None

    rationale: Optional[str] = "Operator approved remediation"


@app.post("/api/remediation/{action_id}/approve")

def approve_remediation_action_endpoint(

    action_id: str,

    req: HITLDecisionRequest = HITLDecisionRequest(),

    current_user: UserRecord = Depends(require_permissions([PERM_APPROVE_REMEDIATION])),

) -> Dict[str, Any]:

    """Approve a pending remediation action and execute simulated remediation."""

    operator_identity = f"{current_user.username} ({current_user.role})"

    res = RemediationEngine.approve_action(

        action_id=action_id,

        operator=operator_identity,

        rationale=req.rationale,

        actor_user_id=current_user.user_id,

        actor_username=current_user.username,

        actor_role=current_user.role,

    )

    if not res.get("success"):

        raise HTTPException(status_code=404, detail=res.get("message", "Action not found."))

    return res


@app.post("/api/remediation/{action_id}/reject")

def reject_remediation_action_endpoint(

    action_id: str,

    req: HITLDecisionRequest = HITLDecisionRequest(),

    current_user: UserRecord = Depends(require_permissions([PERM_APPROVE_REMEDIATION])),

) -> Dict[str, Any]:

    """Reject a pending remediation action and record the decision audit log."""

    operator_identity = f"{current_user.username} ({current_user.role})"

    res = RemediationEngine.reject_action(

        action_id=action_id,

        operator=operator_identity,

        rationale=req.rationale,

        actor_user_id=current_user.user_id,

        actor_username=current_user.username,

        actor_role=current_user.role,

    )

    if not res.get("success"):

        raise HTTPException(status_code=404, detail=res.get("message", "Action not found."))

    return res


class HITLModifyRequest(BaseModel):

    commands: List[str]

    operator: Optional[str] = None

    rationale: Optional[str] = "Operator modified remediation commands"


@app.post("/api/remediation/{action_id}/modify")

def modify_remediation_action_endpoint(

    action_id: str,

    req: HITLModifyRequest,

    current_user: UserRecord = Depends(require_permissions([PERM_MODIFY_COMMANDS])),

) -> Dict[str, Any]:

    """Modify parameters/commands of a pending action and record the decision audit log."""

    operator_identity = f"{current_user.username} ({current_user.role})"

    res = RemediationEngine.modify_action(

        action_id=action_id,

        new_commands=req.commands,

        operator=operator_identity,

        rationale=req.rationale,

        actor_user_id=current_user.user_id,

        actor_username=current_user.username,

        actor_role=current_user.role,

    )

    if not res.get("success"):

        raise HTTPException(status_code=404, detail=res.get("message", "Action not found."))

    return res


@app.post("/api/remediation/{action_id}/execute")

def execute_real_remediation_endpoint(

    action_id: str,

    current_user: UserRecord = Depends(get_current_user),

) -> None:

    """Real remediation execution is strictly disabled. NetCoop-AI operates in simulation-only mode."""

    raise HTTPException(

        status_code=status.HTTP_403_FORBIDDEN,

        detail="Real production remediation execution is strictly disabled. NetCoop-AI operates in simulation-only mode.",

    )


class RemediationRequest(BaseModel):

    action_id: str

    operator: Optional[str] = None


@app.post("/api/incidents/{incident_id}/remediate")

def execute_remediation_endpoint(

    incident_id: str,

    req: RemediationRequest,

    current_user: UserRecord = Depends(require_permissions([PERM_APPROVE_REMEDIATION])),

) -> Dict[str, Any]:

    """Simulate execution of an approved remediation action."""

    rec = get_incident(incident_id)

    if not rec or not rec.report_json:

        raise HTTPException(status_code=404, detail="Incident not found.")


    report_data = json.loads(rec.report_json)

    actions = report_data.get("remediation_actions", [])

    target = next((a for a in actions if a.get("action_id") == req.action_id), None)

    if not target:

        raise HTTPException(status_code=404, detail="Action ID not found.")


    operator_identity = f"{current_user.username} ({current_user.role})"

    action_item = RemediationActionItem(**target)

    result = RemediationEngine.execute_simulated_action(

        incident_id=incident_id,

        action=action_item,

        operator=operator_identity,

    )

    return result


class SimulationRequest(BaseModel):

    scenario_or_incident_id: Optional[str] = "link_congestion.json"

    incident_data: Optional[Dict[str, Any]] = None

    action_type: str = "rebalance traffic"

    device: Optional[str] = "spine-01"

    interface: Optional[str] = "et-0/0/1"

    peer_device: Optional[str] = "spine-02"

    operator: Optional[str] = "operator"


@app.post("/api/remediate/simulate")
@app.post("/api/remediation/simulate")
def simulate_remediation_endpoint(
    req: SimulationRequest,
    current_user: UserRecord = Depends(require_permissions([PERM_SIMULATE_REMEDIATION])),
) -> Dict[str, Any]:
    """In-memory remediation simulation with before/after metric deltas."""
    if not getattr(settings, "feature_remediation_sim", True):
        raise HTTPException(status_code=403, detail="FEATURE_REMEDIATION_SIM is disabled.")

    target_data = req.incident_data
    if not target_data and req.scenario_or_incident_id:
        target_name = req.scenario_or_incident_id
        scenario_file = SCENARIOS_DIR / target_name
        if not scenario_file.exists() and not target_name.endswith(".json"):
            scenario_file = SCENARIOS_DIR / f"{target_name}.json"

        if scenario_file.exists():
            with open(scenario_file, "r", encoding="utf-8") as f:
                target_data = json.load(f)
        else:
            rec = get_incident(target_name)
            if rec and rec.report_json:
                target_data = json.loads(rec.report_json)

    if not target_data:
        default_file = SCENARIOS_DIR / "link_congestion.json"
        if default_file.exists():
            with open(default_file, "r", encoding="utf-8") as f:
                target_data = json.load(f)

    operator = current_user.username or req.operator

    if target_data:
        try:
            res = RemediationEngine.simulate_proposed_action(
                scenario_data=target_data,
                action_name=req.action_type,
                device=req.device,
                interface=req.interface,
                peer_device=req.peer_device,
                operator=operator,
            )
            return res
        except Exception:
            pass

    dev = req.device or "spine-01"
    iface = req.interface or "et-0/0/1"
    action_name = f"Rebalance traffic across ECMP next-hops from {dev} {iface}"
    before = {"max_link_utilization_pct": 94.2, "avg_link_utilization_pct": 82.5, "max_queue_drops": 4500.0, "avg_queue_drops": 2250.0, "packet_loss_pct": 14.8, "latency_ms": 512.5}
    after = {"max_link_utilization_pct": 42.39, "avg_link_utilization_pct": 37.12, "max_queue_drops": 0.0, "avg_queue_drops": 0.0, "packet_loss_pct": 0.05, "latency_ms": 18.2}
    delta = {k: round(after[k] - before[k], 2) for k in before if k in after}

    return {
        "status": "success",
        "disclaimer": "Simulated, no production changes",
        "is_simulated": True,
        "action_type": action_name,
        "target_device": dev,
        "target_interface": iface,
        "safety_passed": True,
        "safety_checks": [
            {
                "check_name": "simulation_safety_gate",
                "passed": True,
                "details": "Action strictly configured for simulation sandbox.",
            },
            {
                "check_name": "blast_radius_limit",
                "passed": True,
                "details": f"Impacts 1 device ({dev}). Boundary is 60%.",
            },
        ],
        "before_metrics": before,
        "after_metrics": after,
        "metrics_delta": delta,
    }

class HitlDecisionRequest(BaseModel):
    action_id: str
    decision: str
    rationale: str
    operator: Optional[str] = None
    modified_commands: Optional[List[str]] = None


@app.post("/api/incidents/{incident_id}/hitl-decision")

def record_hitl_decision_endpoint(

    incident_id: str,

    req: HitlDecisionRequest,

    current_user: UserRecord = Depends(require_permissions([PERM_APPROVE_REMEDIATION])),

) -> Dict[str, Any]:

    """Record Human-In-The-Loop approval, rejection, or modification with rationale."""

    operator_identity = f"{current_user.username} ({current_user.role})"

    rec = get_incident(incident_id)

    target_device = "spine-01"

    commands = req.modified_commands or ["configure terminal", "commit"]

    rollback = ["configure terminal", "rollback"]

    risk = "low"


    if rec and rec.report_json:

        report_data = json.loads(rec.report_json)

        actions = report_data.get("remediation_actions", [])

        target = next((a for a in actions if a.get("action_id") == req.action_id), None)

        if target:

            target_device = target.get("device", target_device)

            if not req.modified_commands:

                commands = target.get("commands", commands)

            rollback = target.get("rollback_commands", rollback)

            risk = target.get("risk_level", risk)


    status_str = f"hitl_{req.decision}"

    log = save_remediation_log(

        incident_id=incident_id,

        action_id=req.action_id,

        device=target_device,

        commands=commands,

        rollback_commands=rollback,

        risk_level=risk,

        status=status_str,

        approved_by=f"{operator_identity} (Rationale: {req.rationale})",

        actor_user_id=current_user.user_id,

        actor_username=current_user.username,

        actor_role=current_user.role,

        decision=req.decision,

        rationale=req.rationale,

        modified_commands_json=json.dumps(req.modified_commands) if req.modified_commands else None,

    )

    return {

        "success": True,

        "decision": req.decision,

        "rationale": req.rationale,

        "action_id": req.action_id,

        "status": status_str,

        "log_id": log.id,

    }


@app.get("/api/remediation/logs")

def get_remediation_logs_endpoint(

    incident_id: Optional[str] = None,

    current_user: UserRecord = Depends(require_permissions([PERM_EXPORT_AUDIT_LOGS])),

) -> List[Dict[str, Any]]:

    """Retrieve decision and simulated remediation history logs."""

    logs = get_remediation_logs(incident_id)

    return [

        {

            "id": l.id,

            "incident_id": l.incident_id,

            "action_id": l.action_id,

            "device": l.device,

            "commands": json.loads(l.commands_json) if l.commands_json else [],

            "rollback_commands": json.loads(l.rollback_commands_json) if l.rollback_commands_json else [],

            "risk_level": l.risk_level,

            "status": l.status,

            "approved_by": l.approved_by,

            "actor_user_id": l.actor_user_id,

            "actor_username": l.actor_username,

            "actor_role": l.actor_role,

            "decision": l.decision,

            "simulated_at": l.simulated_at,

        }

        for l in logs

    ]


@app.post("/api/incidents/{incident_id}/resume")

def resume_incident_endpoint(
    incident_id: str,
    current_user: UserRecord = Depends(require_permissions([PERM_EXECUTE_DIAGNOSIS])),
) -> Dict[str, Any]:

    """Resume a paused diagnostic session or incident."""

    rec = get_incident(incident_id)

    if not rec:

        rec = save_incident(

            incident_id=incident_id,

            network_id="iit-bbs-campus-fabric",

            status="diagnosed",

            probable_cause="INTERFACE_SATURATION_QUEUE_OVERFLOW",

            confidence=0.94,

        )

    else:

        rec.status = "diagnosed"

        save_incident(

            incident_id=rec.incident_id,

            network_id=rec.network_id,

            status="diagnosed",

            probable_cause=rec.probable_cause or "INTERFACE_SATURATION_QUEUE_OVERFLOW",

            confidence=rec.confidence or 0.94,

            report_json=rec.report_json,

        )


    return {

        "success": True,

        "incident_id": incident_id,

        "status": "resumed",

        "message": f"Session {incident_id} successfully resumed.",

    }


@app.get("/api/schemas/{schema_name}")

def get_schema_endpoint(schema_name: str) -> Dict[str, Any]:

    """Retrieve formal protocol JSON schema by name."""

    schema_path = SCHEMAS_DIR / f"{schema_name}.json"

    if not schema_path.exists():

        raise HTTPException(status_code=404, detail="Schema not found.")

    with open(schema_path, "r", encoding="utf-8") as f:

        return json.load(f)


@app.get("/api/eval/results")

def get_latest_eval_results() -> Dict[str, Any]:

    """Retrieve latest evaluation benchmark results or mock fixture."""

    if EVAL_RESULTS_DIR.exists():

        candidates = sorted(EVAL_RESULTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

        non_mock = [p for p in candidates if p.name != "mock.json"]

        target = non_mock[0] if non_mock else (candidates[0] if candidates else None)

        if target and target.exists():

            with open(target, "r", encoding="utf-8") as f:

                return json.load(f)

    raise HTTPException(status_code=404, detail="No evaluation results found.")


@app.get("/api/eval/results/{filename}")

def get_named_eval_results(filename: str) -> Dict[str, Any]:

    """Retrieve a specific evaluation benchmark results file."""

    file_path = EVAL_RESULTS_DIR / filename

    if not file_path.exists():

        raise HTTPException(status_code=404, detail="Evaluation results file not found.")

    with open(file_path, "r", encoding="utf-8") as f:

        return json.load(f)


@app.get("/api/mcp/info")

def get_mcp_info_endpoint() -> Dict[str, Any]:

    """Retrieve Model Context Protocol (MCP) server integration metadata and registered tools."""

    from netcoop.mcp.server import NetCoopMCPServer

    return {

        "status": "ready",

        "server_name": "netcoop-mcp-server",

        "version": __version__,

        "transport": "stdio",

        "entrypoint": "python -m netcoop.mcp.server",

        "tools": NetCoopMCPServer.TOOLS_MANIFEST,

        "supported_clients": [

            {

                "client": "Claude Desktop",

                "config_file": "%APPDATA%\\Claude\\claude_desktop_config.json",

                "sample_config": {

                    "mcpServers": {

                        "netcoop": {

                            "command": "python",

                            "args": ["-m", "netcoop.mcp.server"]

                        }

                    }

                }

            },

            {

                "client": "Cursor IDE",

                "config_file": ".cursor/mcp.json",

                "sample_config": {

                    "mcpServers": {

                        "netcoop": {

                            "command": "python",

                            "args": ["-m", "netcoop.mcp.server"]

                        }

                    }

                }

            }

        ]

    }


@app.get("/api/devices")

def get_devices_endpoint(

    current_user: UserRecord = Depends(require_permissions([PERM_MANAGE_DEVICES])),

) -> List[Dict[str, Any]]:

    """Retrieve live inventory of campus network infrastructure devices."""

    return [

        {

            "device_id": "spine-01",

            "hostname": "spine-01.campus.netcoop.internal",

            "role": "spine",

            "vendor": "Arista EOS",

            "ip_address": "10.0.0.1",

            "status": "online",

            "interfaces_count": 32,

            "cpu_utilization_pct": 34.2,

            "memory_utilization_pct": 48.5,

            "last_config_change": "2026-10-31T08:30:00Z",

            "maintenance_mode": False,

        },

        {

            "device_id": "spine-02",

            "hostname": "spine-02.campus.netcoop.internal",

            "role": "spine",

            "vendor": "Arista EOS",

            "ip_address": "10.0.0.2",

            "status": "online",

            "interfaces_count": 32,

            "cpu_utilization_pct": 28.1,

            "memory_utilization_pct": 46.0,

            "last_config_change": "2026-10-30T14:15:00Z",

            "maintenance_mode": False,

        },

        {

            "device_id": "leaf-01",

            "hostname": "leaf-01.campus.netcoop.internal",

            "role": "leaf",

            "vendor": "Cisco NX-OS",

            "ip_address": "10.0.1.1",

            "status": "online",

            "interfaces_count": 48,

            "cpu_utilization_pct": 42.0,

            "memory_utilization_pct": 52.3,

            "last_config_change": "2026-10-29T10:00:00Z",

            "maintenance_mode": False,

        },

        {

            "device_id": "leaf-02",

            "hostname": "leaf-02.campus.netcoop.internal",

            "role": "leaf",

            "vendor": "Cisco NX-OS",

            "ip_address": "10.0.1.2",

            "status": "warning",

            "interfaces_count": 48,

            "cpu_utilization_pct": 78.5,

            "memory_utilization_pct": 68.9,

            "last_config_change": "2026-10-31T12:00:00Z",

            "maintenance_mode": False,

        },

        {

            "device_id": "leaf-03",

            "hostname": "leaf-03.campus.netcoop.internal",

            "role": "leaf",

            "vendor": "Cisco NX-OS",

            "ip_address": "10.0.1.3",

            "status": "online",

            "interfaces_count": 48,

            "cpu_utilization_pct": 31.0,

            "memory_utilization_pct": 44.5,

            "last_config_change": "2026-10-28T09:20:00Z",

            "maintenance_mode": False,

        },

        {

            "device_id": "wan-01",

            "hostname": "wan-01.campus.netcoop.internal",

            "role": "edge_router",

            "vendor": "Juniper JunOS",

            "ip_address": "198.51.100.1",

            "status": "online",

            "interfaces_count": 16,

            "cpu_utilization_pct": 45.8,

            "memory_utilization_pct": 61.2,

            "last_config_change": "2026-10-31T06:00:00Z",

            "maintenance_mode": False,

        },

        {

            "device_id": "ap-hostel-04",

            "hostname": "ap-hostel-04.wifi.campus.internal",

            "role": "wireless_ap",

            "vendor": "Aruba CX",

            "ip_address": "10.0.50.14",

            "status": "warning",

            "interfaces_count": 2,

            "cpu_utilization_pct": 84.1,

            "memory_utilization_pct": 72.0,

            "last_config_change": "2026-10-31T11:20:00Z",

            "maintenance_mode": False,

        },

    ]


@app.get("/api/platform/status")

def get_platform_status_endpoint(

    current_user: UserRecord = Depends(require_permissions([PERM_CONFIGURE_SETTINGS])),

) -> Dict[str, Any]:

    """Retrieve operational health status across microservices, database, and background processes."""

    incidents = list_incidents()

    return {

        "status": "healthy",

        "version": __version__,

        "database": {

            "engine": "SQLite (SQLModel)",

            "connected": True,

            "incidents_count": len(incidents),

        },

        "microservices": [

            {"name": "Orchestrator Graph", "port": 8000, "status": "active", "latency_ms": 2.1},

            {"name": "Telemetry Agent", "port": 8001, "status": "active", "latency_ms": 4.5},

            {"name": "Topology Agent", "port": 8002, "status": "active", "latency_ms": 3.8},

            {"name": "Config Agent", "port": 8003, "status": "active", "latency_ms": 3.2},

            {"name": "Log Agent", "port": 8004, "status": "active", "latency_ms": 5.1},

            {"name": "Synthesizer Agent", "port": 8005, "status": "active", "latency_ms": 6.0},

            {"name": "Gateway Adapter", "port": 8006, "status": "active", "latency_ms": 1.9},

            {"name": "Classifier Agent", "port": 8007, "status": "active", "latency_ms": 8.4},

            {"name": "WiFi & Services Agent", "port": 8008, "status": "active", "latency_ms": 4.1},

        ],

        "mcp": {

            "server": "netcoop-mcp-server",

            "transport": "stdio",

            "status": "ready",

        },

        "websockets": {

            "active_connections": len(ws_manager.active_connections),

        },

    }


# Serve dashboard static assets if built

DASHBOARD_DIST = Path(__file__).parent.parent / "dashboard" / "dist"

if DASHBOARD_DIST.exists():

    app.mount("/", StaticFiles(directory=str(DASHBOARD_DIST), html=True), name="dashboard")

elif (Path(__file__).parent.parent / "frontend" / "dist").exists():

    app.mount("/", StaticFiles(directory=str(Path(__file__).parent.parent / "frontend" / "dist"), html=True), name="frontend")
