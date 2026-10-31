"""Authentication, JWT signing, password hashing, and server-side RBAC dependencies."""

import hashlib
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from netcoop.config import settings, is_demo_mode_allowed
from netcoop.storage.models import UserRecord

# -----------------------------------------------------------------------------
# Canonical Roles and Explicit Least-Privilege Permissions
# -----------------------------------------------------------------------------

ROLE_NOC_OPERATOR = "noc_operator"
ROLE_NETWORK_ENGINEER = "network_engineer"
ROLE_NETWORK_ADMIN = "network_admin"
ROLE_SECURITY_ANALYST = "security_analyst"
ROLE_IT_MANAGER = "it_manager"
ROLE_PLATFORM_ADMIN = "platform_admin"
ROLE_AUDITOR = "auditor"
ROLE_HELPDESK = "helpdesk"

ALL_ROLES = [
    ROLE_NOC_OPERATOR,
    ROLE_NETWORK_ENGINEER,
    ROLE_NETWORK_ADMIN,
    ROLE_SECURITY_ANALYST,
    ROLE_IT_MANAGER,
    ROLE_PLATFORM_ADMIN,
    ROLE_AUDITOR,
    ROLE_HELPDESK,
]

PERM_VIEW_FABRIC_HEALTH = "VIEW_FABRIC_HEALTH"
PERM_ACKNOWLEDGE_ALERTS = "ACKNOWLEDGE_ALERTS"
PERM_ASSIGN_INCIDENT = "ASSIGN_INCIDENT"
PERM_EXECUTE_DIAGNOSIS = "EXECUTE_DIAGNOSIS"
PERM_SIMULATE_REMEDIATION = "SIMULATE_REMEDIATION"
PERM_MODIFY_COMMANDS = "MODIFY_COMMANDS"
PERM_APPROVE_REMEDIATION = "APPROVE_REMEDIATION"
PERM_EXECUTE_REMEDIATION = "EXECUTE_REMEDIATION"  # Declared unavailable in simulation mode
PERM_MANAGE_DEVICES = "MANAGE_DEVICES"
PERM_CONFIGURE_SETTINGS = "CONFIGURE_SETTINGS"
PERM_MANAGE_USERS = "MANAGE_USERS"
PERM_EXPORT_AUDIT_LOGS = "EXPORT_AUDIT_LOGS"

ROLE_PERMISSIONS_MAP: Dict[str, Set[str]] = {
    ROLE_HELPDESK: {
        PERM_VIEW_FABRIC_HEALTH,
        PERM_ACKNOWLEDGE_ALERTS,
    },
    ROLE_NOC_OPERATOR: {
        PERM_VIEW_FABRIC_HEALTH,
        PERM_ACKNOWLEDGE_ALERTS,
        PERM_ASSIGN_INCIDENT,
        PERM_EXECUTE_DIAGNOSIS,
    },
    ROLE_NETWORK_ENGINEER: {
        PERM_VIEW_FABRIC_HEALTH,
        PERM_ACKNOWLEDGE_ALERTS,
        PERM_ASSIGN_INCIDENT,
        PERM_EXECUTE_DIAGNOSIS,
        PERM_SIMULATE_REMEDIATION,
        PERM_MODIFY_COMMANDS,
        PERM_APPROVE_REMEDIATION,
    },
    ROLE_NETWORK_ADMIN: {
        PERM_VIEW_FABRIC_HEALTH,
        PERM_ACKNOWLEDGE_ALERTS,
        PERM_EXECUTE_DIAGNOSIS,
        PERM_SIMULATE_REMEDIATION,
        PERM_APPROVE_REMEDIATION,
        PERM_MANAGE_DEVICES,
    },
    ROLE_SECURITY_ANALYST: {
        PERM_VIEW_FABRIC_HEALTH,
        PERM_ACKNOWLEDGE_ALERTS,
        PERM_EXPORT_AUDIT_LOGS,
    },
    ROLE_IT_MANAGER: {
        PERM_VIEW_FABRIC_HEALTH,
        PERM_EXPORT_AUDIT_LOGS,
    },
    ROLE_PLATFORM_ADMIN: {
        PERM_VIEW_FABRIC_HEALTH,
        PERM_CONFIGURE_SETTINGS,
        PERM_MANAGE_USERS,
        PERM_EXPORT_AUDIT_LOGS,
    },
    ROLE_AUDITOR: {
        PERM_VIEW_FABRIC_HEALTH,
        PERM_EXPORT_AUDIT_LOGS,
    },
}

# -----------------------------------------------------------------------------
# Demonstration Accounts for Non-Production Environments
# -----------------------------------------------------------------------------

DEMO_SEED_ACCOUNTS = [
    {
        "username": "noc",
        "role": ROLE_NOC_OPERATOR,
        "full_name": "NOC Operations Specialist",
    },
    {
        "username": "engineer",
        "role": ROLE_NETWORK_ENGINEER,
        "full_name": "Senior Network Engineer",
    },
    {
        "username": "admin",
        "role": ROLE_NETWORK_ADMIN,
        "full_name": "Campus Network Administrator",
    },
    {
        "username": "security",
        "role": ROLE_SECURITY_ANALYST,
        "full_name": "Cyber Defense Analyst",
    },
    {
        "username": "it_manager",
        "role": ROLE_IT_MANAGER,
        "full_name": "IT Service Delivery Manager",
    },
    {
        "username": "platform_admin",
        "role": ROLE_PLATFORM_ADMIN,
        "full_name": "Platform & SRE Administrator",
    },
    {
        "username": "auditor",
        "role": ROLE_AUDITOR,
        "full_name": "Compliance & Audit Officer",
    },
    {
        "username": "helpdesk",
        "role": ROLE_HELPDESK,
        "full_name": "Campus Helpdesk Operator",
    },
]

# -----------------------------------------------------------------------------
# Password Hashing & Verification (PBKDF2-HMAC-SHA256, 600,000 iterations)
# -----------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with 600,000 rounds and random 16-byte salt."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        600_000,
    )
    return f"pbkdf2_sha256$600000${salt}${key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hashed string using constant-time comparison."""
    try:
        parts = hashed_password.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        iterations = int(parts[1])
        salt = parts[2]
        expected_hash = parts[3]
        computed_hash = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        ).hex()
        return secrets.compare_digest(computed_hash, expected_hash)
    except Exception:
        return False


# -----------------------------------------------------------------------------
# JWT Signing Secret & Production Fail-Safe
# -----------------------------------------------------------------------------

def get_jwt_secret() -> str:
    """Retrieve active signing key and enforce production strength."""
    env = os.getenv("NETCOOP_ENV", settings.environment).lower()
    secret = os.getenv("NETCOOP_JWT_SECRET", settings.jwt_secret_key)
    if env == "production":
        insecure_defaults = {
            "netcoop-production-signing-secret-key-change-in-production-env",
            "change-this-in-production-netcoop-secret-key-32chars",
            "development-jwt-secret-key-do-not-use-in-production",
        }
        if not secret or secret in insecure_defaults or len(secret) < 32:
            raise ValueError(
                "Insecure production configuration: NETCOOP_JWT_SECRET must be explicitly set and at least 32 characters in production."
            )
    return secret


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Sign and encode a new JWT access token with fixed HS256 algorithm and security claims."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)

    jti = to_encode.get("jti") or secrets.token_hex(16)
    to_encode.update({
        "exp": expire,
        "iat": now,
        "jti": jti,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    })
    return jwt.encode(to_encode, get_jwt_secret(), algorithm="HS256")


def decode_access_token(token: str) -> Dict[str, Any]:
    """Validate token signature, expiration, issuer, and audience using fixed HS256 algorithm."""
    return jwt.decode(
        token,
        get_jwt_secret(),
        algorithms=["HS256"],
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
    )


# -----------------------------------------------------------------------------
# Login Rate Limiting / Brute-Force Protection
# -----------------------------------------------------------------------------

_LOGIN_ATTEMPTS: Dict[str, List[float]] = {}


def check_login_rate_limit(key: str) -> None:
    """Raise HTTP 429 if more than 5 failed attempts occurred in the last 5 minutes."""
    now = time.time()
    attempts = [t for t in _LOGIN_ATTEMPTS.get(key, []) if now - t < 300]
    _LOGIN_ATTEMPTS[key] = attempts
    if len(attempts) >= 5:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Account temporarily locked due to excessive failed attempts. Please retry after 5 minutes.",
        )


def record_login_failure(key: str) -> None:
    """Record a timestamped failed login attempt."""
    now = time.time()
    attempts = [t for t in _LOGIN_ATTEMPTS.get(key, []) if now - t < 300]
    attempts.append(now)
    _LOGIN_ATTEMPTS[key] = attempts


def clear_login_failures(key: str) -> None:
    """Clear recorded failure timestamps following successful authentication."""
    _LOGIN_ATTEMPTS.pop(key, None)


# -----------------------------------------------------------------------------
# WebSocket Short-Lived Single-Use Connection Tickets
# -----------------------------------------------------------------------------

_WS_TICKETS: Dict[str, Dict[str, Any]] = {}


def create_ws_ticket(user: UserRecord, expiry_seconds: int = 60) -> str:
    """Generate a cryptographically secure, short-lived single-use ticket for WebSocket authentication."""
    ticket_id = secrets.token_urlsafe(32)
    now = time.time()
    _WS_TICKETS[ticket_id] = {
        "user_id": user.user_id,
        "username": user.username,
        "role": user.role,
        "created_at": now,
        "expires_at": now + expiry_seconds,
        "used": False,
    }
    return ticket_id


def consume_ws_ticket(ticket_id: str) -> Tuple[bool, str, Optional[UserRecord]]:
    """Atomically validate and consume a single-use WebSocket ticket."""
    now = time.time()
    # Prune tickets older than 5 minutes
    stale = [k for k, v in _WS_TICKETS.items() if now - v.get("created_at", 0) > 300]
    for k in stale:
        _WS_TICKETS.pop(k, None)

    ticket = _WS_TICKETS.get(ticket_id)
    if not ticket:
        return False, "Invalid or non-existent WebSocket ticket.", None

    if ticket.get("used"):
        return False, "WebSocket ticket has already been consumed (replay rejected).", None

    if now > ticket.get("expires_at", 0):
        return False, "WebSocket ticket has expired.", None

    # Mark as used immediately to prevent replay
    ticket["used"] = True

    from netcoop.storage.db import get_user_by_username
    user = get_user_by_username(ticket["username"])
    if not user or not user.is_active:
        return False, "User account is inactive or not found.", None

    perms = ROLE_PERMISSIONS_MAP.get(user.role, set())
    if PERM_VIEW_FABRIC_HEALTH not in perms:
        return False, "Insufficient permissions for event streaming.", None

    return True, "OK", user


# -----------------------------------------------------------------------------
# Pydantic Schemas
# -----------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str


class DemoLoginRequest(BaseModel):
    username: str


class WsTicketResponse(BaseModel):
    ticket: str
    expires_in: int = 60
    token_type: str = "ticket"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: str
    username: str
    full_name: Optional[str] = None
    permissions: List[str]


class UserProfileResponse(BaseModel):
    user_id: str
    username: str
    role: str
    full_name: Optional[str] = None
    permissions: List[str]
    is_active: bool
    created_at: str


class AssignIncidentRequest(BaseModel):
    assignee: str
    rationale: Optional[str] = "Incident assignment by authorized operator"


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str
    full_name: Optional[str] = None


# -----------------------------------------------------------------------------
# FastAPI Security Dependencies
# -----------------------------------------------------------------------------

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> UserRecord:
    """Extract and validate Bearer token against revoked list and persistent user store."""
    from netcoop.storage.db import get_user_by_username, is_token_revoked, log_auth_event

    client_ip = request.client.host if request.client else "unknown"
    path = request.url.path

    if not credentials or not credentials.credentials:
        log_auth_event(
            event_type="UNAUTHENTICATED_ACCESS_ATTEMPT",
            endpoint=path,
            client_ip=client_ip,
            details="Missing Authorization Bearer header",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        log_auth_event(
            event_type="TOKEN_EXPIRED",
            endpoint=path,
            client_ip=client_ip,
            details="Access token expired",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError as exc:
        log_auth_event(
            event_type="INVALID_TOKEN",
            endpoint=path,
            client_ip=client_ip,
            details=f"JWT validation failed: {str(exc)}",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check server-side token revocation (logout)
    jti = payload.get("jti")
    if jti and is_token_revoked(jti):
        log_auth_event(
            event_type="TOKEN_REVOKED",
            endpoint=path,
            client_ip=client_ip,
            details="Revoked token used after logout",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username: Optional[str] = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Load fresh active user record from database
    user = get_user_by_username(username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        log_auth_event(
            event_type="INACTIVE_USER_BLOCKED",
            username=user.username,
            user_id=user.user_id,
            role=user.role,
            endpoint=path,
            client_ip=client_ip,
            details="Deactivated account attempted operation",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive or disabled.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_roles(allowed_roles: List[str]) -> Callable[..., UserRecord]:
    """Dependency verifying role membership based on fresh database state."""
    def role_dependency(
        request: Request,
        current_user: UserRecord = Depends(get_current_user),
    ) -> UserRecord:
        if current_user.role not in allowed_roles:
            from netcoop.storage.db import log_auth_event

            client_ip = request.client.host if request.client else "unknown"
            log_auth_event(
                event_type="ACCESS_DENIED_ROLE",
                username=current_user.username,
                user_id=current_user.user_id,
                role=current_user.role,
                endpoint=request.url.path,
                client_ip=client_ip,
                details=f"Forbidden: role '{current_user.role}' required one of {allowed_roles}",
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' has insufficient permissions for this operation. Required: {allowed_roles}",
            )
        return current_user

    return role_dependency


def require_permissions(required_permissions: List[str]) -> Callable[..., UserRecord]:
    """Dependency verifying that the user's current database role possesses all required permissions."""
    def permission_dependency(
        request: Request,
        current_user: UserRecord = Depends(get_current_user),
    ) -> UserRecord:
        # Evaluate permissions strictly from current database role
        user_perms = ROLE_PERMISSIONS_MAP.get(current_user.role, set())
        missing = [p for p in required_permissions if p not in user_perms]
        if missing:
            from netcoop.storage.db import log_auth_event

            client_ip = request.client.host if request.client else "unknown"
            log_auth_event(
                event_type="ACCESS_DENIED_PERMISSION",
                username=current_user.username,
                user_id=current_user.user_id,
                role=current_user.role,
                endpoint=request.url.path,
                client_ip=client_ip,
                details=f"Forbidden: role '{current_user.role}' lacks permissions {missing}",
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' lacks required permissions: {missing}",
            )
        return current_user

    return permission_dependency


# -----------------------------------------------------------------------------
# Test Token & Header Helpers
# -----------------------------------------------------------------------------

def create_test_token(role: str = ROLE_PLATFORM_ADMIN, username: Optional[str] = None) -> str:
    """Generate a valid signed JWT for testing."""
    from netcoop.storage.db import get_user_by_username

    u_name = username or role
    user = get_user_by_username(u_name)
    user_id = user.user_id if user else f"test-{u_name}-id"
    payload = {
        "sub": u_name,
        "user_id": user_id,
        "role": role,
    }
    return create_access_token(payload)


def get_auth_headers(role: str = ROLE_PLATFORM_ADMIN, username: Optional[str] = None) -> Dict[str, str]:
    """Helper returning Bearer Authorization header for tests."""
    token = create_test_token(role=role, username=username)
    return {"Authorization": f"Bearer {token}"}
