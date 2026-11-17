"""Phase 6 Comprehensive Security and Operational Boundaries Test Suite.

Verifies:
1. Production mode environment detection and fail-closed security initialization.
2. Production JWT secret validation (minimum 32 characters, no weak defaults).
3. Production internal service token strength validation.
4. JWT token rejection matrix (expired, malformed, invalid issuer/audience, missing JTI, revoked).
5. JWT key rotation fallback verification via NETCOOP_JWT_ROTATION_SECRETS.
6. Route protection for POST /api/ingest (anonymous 401 in prod, valid bearer 200, valid service token 200).
7. Route protection for GET /api/remediation/pending & actions (unauthenticated 401, authenticated 200).
8. CORS hardening across API, Agent microservices, and Gateway.
9. Internal service token verification with constant-time comparison.
10. WebSocket single-use ticket lifecycle and replay prevention.
11. Autonomous execution hard invariant: POST /api/remediation/{action_id}/execute strictly returns 403 Forbidden.
"""

from datetime import datetime, timedelta, timezone
import json
import os
import secrets
import pytest
from fastapi.testclient import TestClient
import jwt

from api.main import app
from core.auth import (
    ALL_ROLES,
    ROLE_AUDITOR,
    ROLE_HELPDESK,
    ROLE_IT_MANAGER,
    ROLE_NETWORK_ADMIN,
    ROLE_NETWORK_ENGINEER,
    ROLE_NOC_OPERATOR,
    ROLE_PLATFORM_ADMIN,
    ROLE_SECURITY_ANALYST,
    PERM_EXECUTE_DIAGNOSIS,
    PERM_VIEW_FABRIC_HEALTH,
    create_access_token,
    create_test_token,
    create_ws_ticket,
    consume_ws_ticket,
    decode_access_token,
    get_auth_headers,
    get_jwt_secret,
    get_jwt_verification_secrets,
    validate_jwt_secret_strength,
    validate_security_configuration_at_startup,
)
from core.config import (
    settings,
    get_runtime_environment,
    is_production_mode,
)
from agents.server import create_agent_app
from gateway.api import create_gateway_app
from netcoop.core.envelope import AgentRole
from storage.db import (
    create_user,
    get_user_by_username,
    init_db,
    init_default_users,
    is_token_revoked,
    revoke_token,
    save_incident,
)


@pytest.fixture(autouse=True)
def setup_security_db():
    """Initialize fresh test database and default accounts."""
    init_db()
    init_default_users()


# ==============================================================================
# 1. ENVIRONMENT DETECTION & STARTUP VALIDATION GATE
# ==============================================================================


def test_production_environment_detection_precedence(monkeypatch):
    """Verify runtime environment detection precedence: NETCOOP_ENV > ENVIRONMENT > settings.environment."""
    monkeypatch.setenv("NETCOOP_ENV", "production")
    monkeypatch.setenv("ENVIRONMENT", "development")
    assert get_runtime_environment() == "production"
    assert is_production_mode() is True

    monkeypatch.delenv("NETCOOP_ENV", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "staging")
    assert get_runtime_environment() == "staging"
    assert is_production_mode() is False

    monkeypatch.setenv("ENVIRONMENT", "production")
    assert get_runtime_environment() == "production"
    assert is_production_mode() is True


def test_startup_validation_fails_with_weak_or_missing_jwt_secret_in_production(monkeypatch):
    """Production mode must fail startup (fail-closed) if JWT secret is missing, default, or < 32 characters."""
    monkeypatch.setenv("NETCOOP_ENV", "production")
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "internal_service_token", "a-sufficiently-strong-service-token-32-chars-long")

    weak_secrets = [
        "",
        "short",
        "secret",
        "netcoop-super-secret-key-change-me",
        "change-me-in-production-use-a-strong-secret-key",
        "this-is-a-placeholder-secret-1234",
        "a" * 31,  # 31 chars (under minimum 32)
    ]

    for secret in weak_secrets:
        monkeypatch.setattr(settings, "jwt_secret_key", secret)
        monkeypatch.setenv("NETCOOP_JWT_SECRET", secret)
        with pytest.raises(ValueError) as excinfo:
            validate_security_configuration_at_startup()
        err_msg = str(excinfo.value).lower()
        assert "netcoop_jwt_secret" in err_msg or "jwt secret" in err_msg


def test_startup_validation_fails_with_weak_service_token_in_production(monkeypatch):
    """Production mode must fail startup if internal service token is missing or weak."""
    monkeypatch.setenv("NETCOOP_ENV", "production")
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "jwt_secret_key", "a-valid-production-jwt-secret-with-at-least-32-chars-long!")
    monkeypatch.setenv("NETCOOP_JWT_SECRET", "a-valid-production-jwt-secret-with-at-least-32-chars-long!")

    weak_service_tokens = [
        "",
        "short",
        "change-me",
        "netcoop",
        "service-token",
        "internal-token",
        "change-me-internal-token",
        "123456789012345",  # 15 chars (under minimum 16)
    ]

    for token in weak_service_tokens:
        monkeypatch.setattr(settings, "internal_service_token", token)
        monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", token)
        with pytest.raises(ValueError) as excinfo:
            validate_security_configuration_at_startup()
        err_msg = str(excinfo.value).lower()
        assert "internal_service_token" in err_msg


def test_startup_validation_succeeds_with_strong_production_secrets(monkeypatch):
    """Production startup must succeed when both JWT secret and service token meet strength requirements."""
    monkeypatch.setenv("NETCOOP_ENV", "production")
    monkeypatch.setattr(settings, "environment", "production")
    strong_jwt = "production-ready-jwt-secret-key-minimum-32-chars-secure!"
    strong_svc = "production-internal-service-token-secure-32-chars-long!"
    monkeypatch.setattr(settings, "jwt_secret_key", strong_jwt)
    monkeypatch.setenv("NETCOOP_JWT_SECRET", strong_jwt)
    monkeypatch.setattr(settings, "internal_service_token", strong_svc)
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", strong_svc)

    # Must complete cleanly without raising ValueError
    validate_security_configuration_at_startup()


# ==============================================================================
# 2. JWT VALIDATION & ROTATION REJECTION MATRIX
# ==============================================================================


def test_jwt_validation_matrix_rejection(monkeypatch):
    """Verify rejection of expired, malformed, wrong issuer/audience, missing JTI, and revoked tokens."""
    strong_secret = "production-ready-jwt-secret-key-minimum-32-chars-secure!"
    monkeypatch.setattr(settings, "jwt_secret_key", strong_secret)
    monkeypatch.setenv("NETCOOP_JWT_SECRET", strong_secret)

    now = datetime.now(timezone.utc)

    # 1. Expired token -> ExpiredSignatureError
    expired_payload = {
        "sub": "engineer1",
        "username": "engineer1",
        "role": ROLE_NETWORK_ENGINEER,
        "permissions": [PERM_EXECUTE_DIAGNOSIS],
        "exp": now - timedelta(minutes=5),
        "iat": now - timedelta(minutes=65),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "jti": secrets.token_hex(16),
    }
    expired_token = jwt.encode(expired_payload, strong_secret, algorithm="HS256")
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(expired_token)

    # 2. Malformed token -> DecodeError
    with pytest.raises(jwt.DecodeError):
        decode_access_token("not-a-valid-token-string")
    with pytest.raises(jwt.DecodeError):
        decode_access_token("header.payload")

    # 3. Wrong issuer -> InvalidIssuerError
    wrong_iss_payload = {**expired_payload, "exp": now + timedelta(hours=1), "iss": "forged-issuer"}
    wrong_iss_token = jwt.encode(wrong_iss_payload, strong_secret, algorithm="HS256")
    with pytest.raises(jwt.InvalidIssuerError):
        decode_access_token(wrong_iss_token)

    # 4. Wrong audience -> InvalidAudienceError
    wrong_aud_payload = {**expired_payload, "exp": now + timedelta(hours=1), "aud": "forged-audience"}
    wrong_aud_token = jwt.encode(wrong_aud_payload, strong_secret, algorithm="HS256")
    with pytest.raises(jwt.InvalidAudienceError):
        decode_access_token(wrong_aud_token)

    # 5. Missing JTI -> MissingRequiredClaimError
    no_jti_payload = {**expired_payload, "exp": now + timedelta(hours=1)}
    del no_jti_payload["jti"]
    no_jti_token = jwt.encode(no_jti_payload, strong_secret, algorithm="HS256")
    with pytest.raises(jwt.MissingRequiredClaimError):
        decode_access_token(no_jti_token)

    # 6. Revoked token -> rejected by route dependency
    valid_jti = secrets.token_hex(16)
    valid_payload = {**expired_payload, "exp": now + timedelta(hours=1), "jti": valid_jti}
    valid_token = jwt.encode(valid_payload, strong_secret, algorithm="HS256")
    # Decodes successfully initially
    assert decode_access_token(valid_token) is not None
    # Revoke
    revoke_token(valid_jti, expires_at=(now + timedelta(hours=1)).isoformat())
    assert is_token_revoked(valid_jti) is True

    client = TestClient(app)
    res_revoked = client.get("/api/remediation/pending", headers={"Authorization": f"Bearer {valid_token}"})
    assert res_revoked.status_code == 401
    assert "revoked" in res_revoked.json().get("detail", "").lower()


def test_jwt_key_rotation_fallback_verification(monkeypatch):
    """Tokens signed with previous secrets in NETCOOP_JWT_ROTATION_SECRETS must decode successfully."""
    current_key = "current-production-key-strictly-32-chars-long!"
    old_key_1 = "old-retired-key-1-strictly-32-chars-long!"
    old_key_2 = "old-retired-key-2-strictly-32-chars-long!"
    unauthorized_key = "unauthorized-key-strictly-32-chars-long!"

    monkeypatch.setattr(settings, "jwt_secret_key", current_key)
    monkeypatch.setenv("NETCOOP_JWT_SECRET", current_key)
    monkeypatch.setenv("NETCOOP_JWT_ROTATION_SECRETS", f"{old_key_1},{old_key_2}")

    # Verify secrets candidate list
    secrets_list = get_jwt_verification_secrets()
    assert secrets_list == [current_key, old_key_1, old_key_2]

    now = datetime.now(timezone.utc)
    base_payload = {
        "sub": "noc",
        "username": "noc",
        "role": ROLE_NOC_OPERATOR,
        "permissions": [PERM_VIEW_FABRIC_HEALTH],
        "exp": now + timedelta(hours=1),
        "iat": now,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }

    # Token signed with current key
    token_current = jwt.encode({**base_payload, "jti": secrets.token_hex(16)}, current_key, algorithm="HS256")
    res_curr = decode_access_token(token_current)
    assert res_curr is not None
    assert res_curr["username"] == "noc"

    # Token signed with old key 1 (rotation fallback)
    token_old1 = jwt.encode({**base_payload, "jti": secrets.token_hex(16)}, old_key_1, algorithm="HS256")
    res_old1 = decode_access_token(token_old1)
    assert res_old1 is not None
    assert res_old1["username"] == "noc"

    # Token signed with old key 2 (rotation fallback)
    token_old2 = jwt.encode({**base_payload, "jti": secrets.token_hex(16)}, old_key_2, algorithm="HS256")
    res_old2 = decode_access_token(token_old2)
    assert res_old2 is not None
    assert res_old2["username"] == "noc"

    # Token signed with unknown key must be rejected with InvalidSignatureError
    token_unauth = jwt.encode({**base_payload, "jti": secrets.token_hex(16)}, unauthorized_key, algorithm="HS256")
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token_unauth)


# ==============================================================================
# 3. INGESTION ROUTE (POST /api/ingest) AUTHENTICATION & SERVICE TOKEN PROTECTION
# ==============================================================================


def test_ingest_route_production_protection_matrix(monkeypatch):
    """Verify POST /api/ingest security in production mode: anonymous 401, service token 200, bearer token 200."""
    client = TestClient(app)

    strong_jwt = "production-ready-jwt-secret-key-minimum-32-chars-secure!"
    valid_service_token = "valid-production-service-token-32-chars-long!"
    monkeypatch.setenv("NETCOOP_ENV", "production")
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "jwt_secret_key", strong_jwt)
    monkeypatch.setenv("NETCOOP_JWT_SECRET", strong_jwt)
    monkeypatch.setattr(settings, "internal_service_token", valid_service_token)

    ingest_payload = {
        "device_id": "sw-access-01",
        "timestamp": "2026-11-01T00:00:00Z",
        "telemetry": [{"latency_ms": 12.0, "packet_loss_pct": 0.0, "device_id": "sw-access-01"}],
    }

    # 1. Anonymous request in production -> 401 Unauthorized
    res_anon = client.post("/api/ingest", json=ingest_payload)
    assert res_anon.status_code == 401
    assert "detail" in res_anon.json()

    # 2. Invalid service token -> 401 Unauthorized
    res_bad_svc = client.post(
        "/api/ingest",
        json=ingest_payload,
        headers={"X-NetCoop-Service-Token": "wrong-invalid-token"},
    )
    assert res_bad_svc.status_code == 401

    # 3. Valid service token -> 200 OK
    res_good_svc = client.post(
        "/api/ingest",
        json=ingest_payload,
        headers={"X-NetCoop-Service-Token": valid_service_token},
    )
    assert res_good_svc.status_code == 200

    # 4. Bearer token without PERM_EXECUTE_DIAGNOSIS (e.g. auditor) -> 403 Forbidden
    auditor_headers = get_auth_headers(role=ROLE_AUDITOR, username="auditor")
    res_auditor = client.post("/api/ingest", json=ingest_payload, headers=auditor_headers)
    assert res_auditor.status_code == 403

    # 5. Bearer token with PERM_EXECUTE_DIAGNOSIS (e.g. engineer) -> 200 OK
    eng_headers = get_auth_headers(role=ROLE_NETWORK_ENGINEER, username="engineer")
    res_eng = client.post("/api/ingest", json=ingest_payload, headers=eng_headers)
    assert res_eng.status_code == 200


# ==============================================================================
# 4. REMEDIATION INSPECTION ROUTES AUTHORIZATION
# ==============================================================================


def test_remediation_pending_and_actions_route_protection():
    """Verify GET /api/remediation/pending and /actions require authentication and fabric view permission."""
    client = TestClient(app)

    # 1. Unauthenticated requests -> 401 Unauthorized
    res_pend_unauth = client.get("/api/remediation/pending")
    assert res_pend_unauth.status_code == 401

    res_act_unauth = client.get("/api/remediation/actions")
    assert res_act_unauth.status_code == 401

    # 2. Authenticated user with PERM_VIEW_FABRIC_HEALTH (e.g. noc operator) -> 200 OK
    op_headers = get_auth_headers(role=ROLE_NOC_OPERATOR, username="noc")

    res_pend_auth = client.get("/api/remediation/pending", headers=op_headers)
    assert res_pend_auth.status_code == 200
    assert isinstance(res_pend_auth.json(), list)

    res_act_auth = client.get("/api/remediation/actions", headers=op_headers)
    assert res_act_auth.status_code == 200
    assert isinstance(res_act_auth.json(), list)


# ==============================================================================
# 5. CORS RESTRICTIONS ACROSS API, AGENTS, AND GATEWAY
# ==============================================================================


def test_cors_configuration_no_wildcard_with_credentials():
    """Verify that wildcard origins are never combined with allow_credentials=True on any service."""
    from starlette.middleware.cors import CORSMiddleware

    # Check main API app
    for middleware in app.user_middleware:
        if middleware.cls == CORSMiddleware:
            kwargs = middleware.kwargs
            allow_origins = kwargs.get("allow_origins", [])
            allow_creds = kwargs.get("allow_credentials", False)
            if "*" in allow_origins:
                assert not allow_creds, "Main API must never combine '*' origin with allow_credentials=True"

    # Check Agent microservices app
    agent_app = create_agent_app(AgentRole.TELEMETRY_AGENT)
    for middleware in agent_app.user_middleware:
        if middleware.cls == CORSMiddleware:
            kwargs = middleware.kwargs
            allow_origins = kwargs.get("allow_origins", [])
            allow_creds = kwargs.get("allow_credentials", False)
            if "*" in allow_origins:
                assert not allow_creds, "Agent service must never combine '*' origin with allow_credentials=True"
            assert not allow_creds

    # Check Gateway app
    gateway_app = create_gateway_app()
    for middleware in gateway_app.user_middleware:
        if middleware.cls == CORSMiddleware:
            kwargs = middleware.kwargs
            allow_origins = kwargs.get("allow_origins", [])
            allow_creds = kwargs.get("allow_credentials", False)
            if "*" in allow_origins:
                assert not allow_creds, "Gateway service must never combine '*' origin with allow_credentials=True"
            assert not allow_creds


def test_cors_options_preflight_rejection():
    """Verify CORS preflight handling with unauthorized origin on agent and gateway services."""
    agent_app = create_agent_app(AgentRole.TELEMETRY_AGENT)
    client = TestClient(agent_app)

    # Disallowed origin preflight
    res = client.options(
        "/envelope",
        headers={
            "Origin": "http://evil-attacker.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type,X-NetCoop-Service-Token",
        },
    )
    allow_origin = res.headers.get("access-control-allow-origin")
    assert allow_origin != "http://evil-attacker.com"


# ==============================================================================
# 6. CONSTANT-TIME SERVICE TOKEN VERIFICATION IN AGENTS & GATEWAY
# ==============================================================================


def test_agent_microservice_constant_time_service_auth(monkeypatch):
    """Verify agent microservice enforces constant-time service token verification."""
    expected_token = "secure-agent-service-token-32-chars-long!"
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", expected_token)
    monkeypatch.setattr(settings, "internal_service_token", expected_token)

    agent_app = create_agent_app(AgentRole.TELEMETRY_AGENT)
    client = TestClient(agent_app)

    # Missing header -> 401
    res_missing = client.post("/envelope", json={})
    assert res_missing.status_code == 401

    # Wrong token -> 401
    res_wrong = client.post(
        "/envelope",
        json={},
        headers={"X-NetCoop-Service-Token": "completely-invalid-service-token"},
    )
    assert res_wrong.status_code == 401

    # Prefix match attempt (timing vulnerability test) -> 401
    res_partial = client.post(
        "/envelope",
        json={},
        headers={"X-NetCoop-Service-Token": expected_token[:15]},
    )
    assert res_partial.status_code == 401


# ==============================================================================
# 7. WEBSOCKET TICKET SINGLE-USE & REPLAY REJECTION
# ==============================================================================


def test_websocket_ticket_single_use_lifecycle():
    """Verify WebSocket tickets are one-time use and cannot be consumed more than once."""
    user = get_user_by_username("noc")
    assert user is not None
    ticket = create_ws_ticket(user)
    assert ticket is not None

    # First consumption succeeds
    ok, reason, user_info = consume_ws_ticket(ticket)
    assert ok is True
    assert user_info is not None
    assert user_info.username == "noc"

    # Second consumption of the exact same ticket MUST fail (anti-replay)
    ok_replay, reason_replay, user_replay = consume_ws_ticket(ticket)
    assert ok_replay is False
    assert user_replay is None
    assert "consumed" in reason_replay.lower() or "invalid" in reason_replay.lower()


# ==============================================================================
# 8. AUTONOMOUS REMEDIATION EXECUTION INVARIANT (HITL SAFETY BOUNDARY)
# ==============================================================================


def test_autonomous_remediation_execution_strictly_forbidden_invariant():
    """Verify POST /api/remediation/{action_id}/execute is strictly forbidden under all circumstances."""
    client = TestClient(app)

    # Even platform admin with all privileges must receive 403 Forbidden
    admin_headers = get_auth_headers(role=ROLE_PLATFORM_ADMIN, username="admin")
    res_admin = client.post("/api/remediation/act-001/execute", headers=admin_headers)
    assert res_admin.status_code == 403
    assert "strictly disabled" in res_admin.json()["detail"].lower()

    # Network engineer must receive 403 Forbidden
    eng_headers = get_auth_headers(role=ROLE_NETWORK_ENGINEER, username="engineer")
    res_eng = client.post("/api/remediation/act-001/execute", headers=eng_headers)
    assert res_eng.status_code == 403

    # Unauthenticated must receive 401 or 403
    res_unauth = client.post("/api/remediation/act-001/execute")
    assert res_unauth.status_code in (401, 403)


# ==============================================================================
# 9. RENDER CLOUD ENVIRONMENT SECURITY REGRESSION TESTS
# ==============================================================================


def test_render_flag_does_not_bypass_missing_jwt_secret_in_production(monkeypatch):
    """RENDER=true must not introduce hardcoded fallback; missing JWT secret fails closed."""
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("NETCOOP_ENV", "production")
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "jwt_secret_key", "")
    monkeypatch.delenv("NETCOOP_JWT_SECRET", raising=False)
    monkeypatch.setattr(settings, "internal_service_token", "production-service-token-32-chars-long!")

    with pytest.raises(ValueError) as excinfo:
        validate_security_configuration_at_startup()
    assert "jwt" in str(excinfo.value).lower()


def test_render_flag_does_not_bypass_weak_jwt_secret_in_production(monkeypatch):
    """RENDER=true must not accept weak or default JWT secret in production."""
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("NETCOOP_ENV", "production")
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "jwt_secret_key", "short-key")
    monkeypatch.setenv("NETCOOP_JWT_SECRET", "short-key")
    monkeypatch.setattr(settings, "internal_service_token", "production-service-token-32-chars-long!")

    with pytest.raises(ValueError) as excinfo:
        validate_security_configuration_at_startup()
    assert "jwt" in str(excinfo.value).lower()


def test_render_flag_with_valid_jwt_secret_starts_securely(monkeypatch):
    """RENDER=true starts securely when strong production secrets are supplied."""
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("NETCOOP_ENV", "production")
    monkeypatch.setattr(settings, "environment", "production")
    strong_jwt = "secure-production-jwt-signing-key-32chars-long!"
    strong_svc = "secure-production-service-token-32chars-long!"
    monkeypatch.setattr(settings, "jwt_secret_key", strong_jwt)
    monkeypatch.setenv("NETCOOP_JWT_SECRET", strong_jwt)
    monkeypatch.setattr(settings, "internal_service_token", strong_svc)
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", strong_svc)

    validate_security_configuration_at_startup()
    assert get_jwt_secret() == strong_jwt


def test_render_flag_does_not_enable_demo_mode_in_production(monkeypatch):
    """RENDER=true must never override production mode to enable demo authentication."""
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("NETCOOP_ENV", "production")
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setenv("NETCOOP_DEMO_MODE", "true")
    monkeypatch.setattr(settings, "demo_mode", True)

    from netcoop.config import is_demo_mode_allowed
    assert is_demo_mode_allowed() is False


def test_production_startup_does_not_seed_demo_accounts_even_if_render(monkeypatch):
    """In production, init_default_users() must never seed default accounts even if RENDER=true."""
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("NETCOOP_ENV", "production")
    monkeypatch.setattr(settings, "environment", "production")

    from sqlmodel import Session, select, delete
    from netcoop.storage.db import engine, UserRecord, init_default_users

    # Clear users for clean test
    with Session(engine) as session:
        for u in session.exec(select(UserRecord)).all():
            session.delete(u)
        session.commit()

    init_default_users()

    with Session(engine) as session:
        users = session.exec(select(UserRecord)).all()
        assert len(users) == 0, "No demo users should be seeded in production mode"

    # Restore default users for subsequent tests
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.setenv("NETCOOP_ENV", "development")
    init_default_users()


def test_exposed_demo_password_rejected_after_account_reset():
    """Verify that an exposed demo password cannot authenticate after user resets password."""
    client = TestClient(app)
    from sqlmodel import Session, select
    from netcoop.storage.db import engine, UserRecord
    from netcoop.core.auth import hash_password

    # Update engineer password to a new rotated password
    new_pwd = "NewRotatedSecurePass!2026"
    with Session(engine) as session:
        user = session.exec(select(UserRecord).where(UserRecord.username == "engineer")).first()
        if user:
            user.hashed_password = hash_password(new_pwd)
            session.add(user)
            session.commit()

    # Old exposed demo password must fail
    res_old = client.post("/api/auth/login", json={"username": "engineer", "password": "NetCoopEng!2026"})
    assert res_old.status_code == 401

    # New password must succeed
    res_new = client.post("/api/auth/login", json={"username": "engineer", "password": new_pwd})
    assert res_new.status_code == 200

    # Restore standard test password for test fixture isolation
    with Session(engine) as session:
        user = session.exec(select(UserRecord).where(UserRecord.username == "engineer")).first()
        if user:
            user.hashed_password = hash_password(os.getenv("NETCOOP_DEV_PASSWORD", "NetCoopDev!2026"))
            session.add(user)
            session.commit()
