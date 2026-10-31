# NetCoop-AI: Phase 4 & Phase 4.2 Final Security Acceptance and Hardening Report

**Role**: Senior Application Security Engineer & Git Integration Maintainer  
**Date**: 2026-11-01  
**Target Branch**: `feat/ui`  
**Git Baseline Reference**: `871a4ce91cb215ebbf1278bed70653029539e7d3` (7 commits ahead of `origin/feat/ui` `36bfd07c2789697e6e850dccba836fc1de2215b2`)  
**Security Status**: HARDENED, TRACEABLE, AND ACCEPTED (ZERO REGRESSIONS)  

---

## 1. Executive Summary

Phase 4, Phase 4.1, and Phase 4.2 have completed the transformation of NetCoop-AI from a prototype with client-side role filtering into an enterprise-ready, zero-trust backend security architecture for multi-agent network fault diagnosis and Human-in-the-Loop (HITL) remediation.

Key security controls finalized and verified during Phase 4.2 include:
1. **Restored SEC-01 Through SEC-06 Traceability**: Complete direct HTTP verification of the original Phase 3 findings on real application endpoints, validating both unauthorized rejection (401/403) and authorized execution (200 OK) for each finding.
2. **Short-Lived Single-Use WebSocket Ticket Exchange**: Replacement of reusable JWTs in URLs with a single-use 60-second ticket pattern (`POST /api/auth/ws-ticket`), consumed on handshake and rejecting replays with WebSocket code 1008 (Policy Violation).
3. **Model Context Protocol (MCP) Credential Review**: Transparent documentation of stdio transport boundaries, support for the `NETCOOP_MCP_TOKEN` session environment variable, credential redaction from envelope traces, and rejection of unauthenticated tool calls.
4. **Structured HITL Audit Persistence**: Full independent verification of all seven audit fields (`actor_user_id`, `actor_username`, `actor_role`, `decision`, `rationale`, `decision_timestamp`, `action_id`), server-side identity derivation from token claims with discard of spoofed request fields, and explicit documentation of SQLite immutability boundaries.
5. **Secret Documentation Sanitization**: Elimination of all literal-looking secret keys from documentation and deployment guides, replacing them with dynamic generation commands.
6. **Git State Preservation**: All Phase 4 security changes remain preserved in the local working tree without destructive rebases, merges, or premature commits, ready for dedicated branch packaging into `feature/backend-auth-hardening`.

### Quantitative Verification Summary
- **Phase 4.2 Security Test Suite**: **29 / 29 test cases passed** in `tests/test_phase4_security.py` (100% pass rate in 4.83s).
- **Full Backend Regression Suite**: **193 / 193 tests passed** with 0 failures across all 24 test suites in 33.08s.
- **Frontend Production Build**: Vite compiled the production bundle in 1.92s with **0 TypeScript errors and 0 build errors**.
- **Repository Hygiene Audit**: Passed `scripts/audit_repo.py` with **zero emojis, zero secrets, zero large files, and zero gradients** across all 251 tracked files.

---

## 2. Threat Model and Core Security Invariants

NetCoop-AI enforces four non-negotiable security invariants across all microservices, gateways, and presentation interfaces:

1. **Zero-Trust Backend Authorization**:
   The frontend user interface is treated as untrusted presentation state. Every protected API endpoint, WebSocket stream, and MCP tool independently verifies caller credentials, checks account active status, resolves current database roles, and validates explicit required permissions.
2. **Simulation-Only Execution Sandbox**:
   Real network remediation execution is strictly disabled. NetCoop-AI operates exclusively in simulation mode. Any attempt to invoke real execution via `POST /api/remediation/{action_id}/execute` is intercepted and rejected with HTTP 403 Forbidden: `"Real production remediation execution is strictly disabled. NetCoop-AI operates in simulation-only mode."`
3. **Anti-Spoofing Operator Derivation**:
   Human-in-the-Loop decisions derive operator identity strictly from verified token claims (`username`, `user_id`, `role`). Client-supplied fields in request bodies attempting to spoof operator identities are discarded.
4. **Least-Privilege Role Separation**:
   Administrative roles are strictly segmented. Infrastructure administrators cannot approve or alter network remediation commands without engineering privileges. Compliance auditors cannot modify operational state. Helpdesk personnel cannot assign incidents or approve remediations.

---

## 3. Original Findings Traceability: SEC-01 Through SEC-06

To ensure full compliance with Phase 3 validation requirements, each original finding retains its assigned identifier, with tests proving both unauthorized rejection and authorized execution on real endpoints.

| Finding ID | Scope & Targeted Endpoint | Unauthorized Condition & Result | Authorized Condition & Result | Test Function in `test_phase4_security.py` |
| :--- | :--- | :--- | :--- | :--- |
| **SEC-01** | Remediation Approval (`POST /api/remediation/{id}/approve`) | Anonymous caller with no token returns **HTTP 401 Unauthorized**. | Authenticated Network Engineer with token returns **HTTP 200 OK** (`status: "approved"`). | `test_sec01_unauthenticated_remediation_approval_returns_401` |
| **SEC-02** | Remediation Approval (`POST /api/remediation/{id}/approve`) | Authenticated Helpdesk user lacking `APPROVE_REMEDIATION` returns **HTTP 403 Forbidden**. | Authenticated Network Admin possessing `APPROVE_REMEDIATION` returns **HTTP 200 OK**. | `test_sec02_helpdesk_remediation_approval_returns_403` |
| **SEC-03** | Remediation Modification (`POST /api/remediation/{id}/modify`) | Authenticated Compliance Auditor lacking `MODIFY_COMMANDS` returns **HTTP 403 Forbidden**. | Authenticated Network Engineer possessing `MODIFY_COMMANDS` returns **HTTP 200 OK**. | `test_sec03_auditor_remediation_modification_returns_403` |
| **SEC-04** | Device Inventory Access (`GET /api/devices`) | Unauthenticated caller returns **HTTP 401**; Helpdesk user returns **HTTP 403 Forbidden**. | Authenticated Network Administrator possessing `MANAGE_DEVICES` returns **HTTP 200 OK**. | `test_sec04_unauthenticated_device_inventory_returns_401` |
| **SEC-05** | Platform Status Probe (`GET /api/platform/status`) | Unauthenticated caller returns **HTTP 401**; Network Engineer returns **HTTP 403 Forbidden**. | Authenticated Platform Administrator possessing `CONFIGURE_SETTINGS` returns **HTTP 200 OK**. | `test_sec05_unauthenticated_platform_status_returns_401` |
| **SEC-06** | Audit Log Export (`GET /api/remediation/logs`) | Unauthenticated caller returns **HTTP 401**; Helpdesk user returns **HTTP 403 Forbidden**. | Authenticated Compliance Auditor possessing `EXPORT_AUDIT_LOGS` returns **HTTP 200 OK**. | `test_sec06_unauthenticated_audit_log_returns_401` |

---

## 4. Authentication Subsystem Architecture

```
[ Dashboard Client / CLI / MCP Client ]
                  │
                  ▼  Authorization: Bearer <JWT>
      ┌─────────────────────────┐
      │  FastAPI Security Gate  │
      └───────────┬─────────────┘
                  │
                  ▼  Decode & Validate (Fixed HS256, iss, aud, exp, iat, jti)
      ┌─────────────────────────┐
      │    netcoop.core.auth    │
      └───────────┬─────────────┘
                  │
                  ├──────────────────────────────┐
                  │                              │
                  ▼ Check Revocation Table       ▼ Query Active User & Live Role
      ┌─────────────────────────┐    ┌─────────────────────────┐
      │   revoked_tokens (db)   │    │       users (db)        │
      └───────────┬─────────────┘    └───────────┬─────────────┘
                  │ [If Revoked: 401]            │ [If Inactive: 401]
                  │                              │
                  ▼                              ▼
      ┌────────────────────────────────────────────────────────┐
      │             Role & Permission Evaluator                │
      └───────────────────────────┬────────────────────────────┘
                                  │
                                  ├─► [Missing Perm: 403 Forbidden]
                                  └─► [Authorized: Execute Handler]
```

### 4.1 Password Hashing Implementation
- **Algorithm**: PBKDF2 with HMAC-SHA256.
- **Work Factor**: 600,000 iterations (aligning with NIST SP 800-63B guidelines).
- **Salt Generation**: 16 cryptographically secure random bytes via `secrets.token_hex(16)`.
- **Hash Format**: `pbkdf2_sha256$600000${salt_hex}${hash_hex}`.
- **Verification**: Evaluated using constant-time comparison `secrets.compare_digest` to eliminate timing side-channel attacks.

### 4.2 JWT Token Lifecycle and Secret Management
- **Signing Algorithm**: Enforces fixed `HS256` algorithm; explicitly rejects the `none` algorithm and algorithm switching.
- **Production Secret Validation**: In production mode (`NETCOOP_ENV=production`), `get_jwt_secret()` verifies that `NETCOOP_JWT_SECRET` is set, is at least 32 characters in length, and is not a known development default. If weak or default, application startup immediately halts with a `ValueError`.
- **Claims Schema**:
  - `sub`: Authenticated username string.
  - `user_id`: Canonical user UUID string.
  - `role`: Role at token issuance.
  - `jti`: 32-character hexadecimal unique token identifier.
  - `iss`: Issuer identifier (`"netcoop-ai"`).
  - `aud`: Audience identifier (`"netcoop-dashboard"`).
  - `iat`: Timestamp of issuance (UTC).
  - `exp`: Timestamp of expiration (UTC, default: 60 minutes).
- **Session Revocation**:
  When a user logs out (`POST /api/auth/logout`), the token's `jti` is written to the SQLite `revoked_tokens` table. On subsequent requests, `get_current_user` queries this table; revoked tokens are immediately rejected with HTTP 401 Unauthorized.
- **Login Rate Limiting**:
  `POST /api/auth/login` tracks failed attempts per client IP. More than 5 failed attempts within 300 seconds triggers HTTP 429 Too Many Requests: `"Account temporarily locked due to excessive failed attempts. Please retry after 5 minutes."`

---

## 5. WebSocket Security Hardening: Short-Lived Ticket Exchange

### 5.1 Threat Model of Query Parameter JWTs
Transmitting long-lived reusable JWTs in WebSocket query strings (`ws://host/ws/events?token=eyJ...`) introduces severe security exposures:
- **Browser History & Cache**: Query parameters are logged in browser history.
- **Proxy and Web Server Access Logs**: Reverse proxies, load balancers, and CDN access logs record complete query strings, exposing bearer credentials in plaintext logs.
- **Shoulder Surfing**: Query parameters remain visible in browser address and developer tools network logs.
- **Token Replay**: An intercepted token can be reused repeatedly until expiration.

### 5.2 Short-Lived Single-Use Ticket Implementation
To eliminate these vulnerabilities, NetCoop-AI implements a secure ticket exchange pattern:
1. **Ticket Request**:
   The authenticated client invokes `POST /api/auth/ws-ticket` with its standard Bearer JWT header.
2. **Ticket Issuance**:
   The server generates a 32-byte cryptographically secure random ticket via `secrets.token_urlsafe(32)`.
   The ticket is cached in an in-memory registry with a strict 60-second time-to-live (TTL) and bound to the authenticated `UserRecord`.
3. **WebSocket Handshake**:
   The client establishes the WebSocket connection passing `ws://host/ws/events?ticket=<ticket>`.
4. **Single-Use Consumption**:
   During the handshake, `consume_ws_ticket(ticket)` validates that the ticket exists and has not expired, resolves the user, and **immediately deletes the ticket from memory**.
5. **Replay Rejection**:
   Any attempt to reconnect using the same ticket fails immediately with WebSocket code `1008` (Policy Violation): `"WebSocket ticket has expired or already been consumed."`
6. **Fallback Defense**:
   Anonymous connections without a ticket or token are rejected with code `1008`.

---

## 6. Model Context Protocol (MCP) Credential Handling & Transport Limitations

### 6.1 MCP Transport Security Posture
The NetCoop-AI MCP server (`netcoop.mcp.server`) communicates via standard input/output (`stdio`) following the Model Context Protocol specification.

> [!NOTE]
> **Honest Transport Limitation Disclosure**:
> When running over `stdio`, the MCP server process inherits the operating system execution context of the local host. Unlike HTTP-based transports, standard HTTP `Authorization: Bearer` headers cannot be attached to individual JSON-RPC messages over `stdio`. NetCoop-AI does not claim out-of-band cryptographic channel encryption on stdio. Security on stdio relies upon local process ownership and operating system access controls.

### 6.2 Credential Handling for Sensitive MCP Tools
To enforce role-based authorization for sensitive operations executed by AI agents or external MCP clients (`simulate_remediation`, `pause_session`, `resume_session`):
1. **Explicit Argument Authentication**:
   Sensitive tools inspect the incoming argument payload for `auth_token` or `token`.
2. **Session Environment Variable Support**:
   When invoking tools in headless or automated environments, the MCP server checks the `NETCOOP_MCP_TOKEN` environment variable as a fallback bearer credential.
3. **Cryptographic Validation**:
   The MCP server validates the token against `netcoop.core.auth`, checking signature integrity, expiration, token revocation in SQLite, active account status, and specific permissions (`PERM_SIMULATE_REMEDIATION`, `PERM_EXECUTE_DIAGNOSIS`).
4. **Credential Redaction in Traces**:
   Bearer tokens and credentials passed in tool arguments are strictly excluded from envelope logs, telemetry events, and audit traces to prevent credential exfiltration.

---

## 7. Structured Human-in-the-Loop (HITL) Persistence

### 7.1 Persisted Decision Attributes
Remediation decisions recorded in the SQLite database separately persist seven structured actor attributes:
- `actor_user_id`: Canonical UUID of the authenticated operator.
- `actor_username`: Username of the authenticated operator.
- `actor_role`: Canonical role of the operator at the time of decision.
- `decision`: Decision type (`approved`, `rejected`, `modified`).
- `rationale`: Operator-provided justification text.
- `decision_timestamp`: UTC ISO-8601 timestamp.
- `action_id`: Identifier of the targeted remediation action item.

### 7.2 Anti-Spoofing and Integrity Controls
The backend explicitly populates `actor_user_id`, `actor_username`, and `actor_role` from the cryptographic claims of the validated JWT bearer token. Any values supplied in the request body attempting to forge or spoof operator identity (`"operator": "spoofed_admin"`) are discarded.

### 7.3 Clarification on SQLite Persistence Boundaries
> [!WARNING]
> **Database Immutability Qualification**:
> NetCoop-AI utilizes SQLite (via SQLModel / SQLAlchemy) for local relational persistence and audit logging. While the application architecture implements append-only audit patterns through API access controls and logs all authentication and remediation events, **SQLite is a file-based relational database and does not provide cryptographic immutability or tamper-evidence** (such as hash chains, Merkle trees, write-once-read-many storage, or distributed consensus ledgers). An attacker with operating system file-system access to `netcoop.db` could alter or delete rows. In production enterprise environments, database file integrity monitoring (FIM), remote syslog forwarding, or cloud-managed relational databases with write-audit streams are required.

---

## 8. Client-Side Session Storage Analysis

The NetCoop-AI frontend persists the active JWT access token in `window.sessionStorage` (`netcoop_token`).

### Technical Comparison: `sessionStorage` vs `HttpOnly Secure SameSite` Cookies

| Security / Functional Dimension | `sessionStorage` (Current NetCoop Implementation) | `HttpOnly Secure SameSite=Strict` Cookie |
| :--- | :--- | :--- |
| **Cross-Site Request Forgery (CSRF)** | **Naturally Immune**: Outbound requests must manually attach `Authorization: Bearer <token>`. Malicious third-party sites cannot trigger authenticated state automatically. | **Requires Anti-CSRF Token**: Browsers attach cookies automatically. Demands synchronized anti-CSRF tokens or `SameSite=Strict`. |
| **Cross-Site Scripting (XSS) Vulnerability** | **Vulnerable**: Any malicious script injected via XSS can access `sessionStorage.getItem("netcoop_token")` and exfiltrate the credential. | **Resistant**: JavaScript cannot read `HttpOnly` cookies via `document.cookie`, mitigating direct token exfiltration (though session riding remains possible). |
| **Tab Isolation** | **Strict Tab Isolation**: Tokens exist exclusively within the browser tab that created them. Opening a second tab does not leak credentials. | **Shared Across Tabs**: Cookies are shared across all tabs and browser windows for that origin. |
| **API Architecture Compatibility** | **Ideal for Decoupled APIs**: Directly compatible with external CLI tools, Python SDKs, and MCP servers using Bearer headers. | Requires specialized reverse proxy or cookie-to-bearer translation layers for non-browser clients. |

> [!WARNING]
> NetCoop-AI's use of `sessionStorage` **does not protect against Cross-Site Scripting (XSS)**. To mitigate this risk, NetCoop-AI relies on strict React JSX contextual escaping, enforces zero inline scripts, and provides no raw `dangerouslySetInnerHTML` entry points.

---

## 9. Comprehensive Verification Results

### 9.1 Phase 4.2 Automated Security Suite (`tests/test_phase4_security.py`)
Executed via `pytest tests/test_phase4_security.py -v`:

| Test Identifier | Verified Security Requirement | Status |
| :--- | :--- | :---: |
| `test_production_mode_does_not_auto_login` | Production mode disables demo auth; unauthenticated requests receive 401 | **PASSED** |
| `test_production_mode_rejects_demo_login` | `POST /api/auth/demo-login` returns 403 Forbidden in production mode | **PASSED** |
| `test_no_default_production_users_seeded` | `init_default_users()` refuses to seed demo accounts in production | **PASSED** |
| `test_invalid_missing_expired_jwt_rejection` | Missing, malformed, and expired JWT tokens return 401 Unauthorized | **PASSED** |
| `test_weak_or_missing_production_jwt_secret_rejection` | Weak or default secret in production halts startup with `ValueError` | **PASSED** |
| `test_inactive_account_rejection` | Inactive accounts cannot log in and tokens are rejected with 401 | **PASSED** |
| `test_role_revocation_takes_effect_immediately` | Demoting user role in database immediately revokes operational permissions | **PASSED** |
| `test_unauthorized_incident_assignment` | Helpdesk and Auditor cannot assign incidents (403 Forbidden) | **PASSED** |
| `test_authorized_incident_assignment` | NOC Operator and Network Engineer assign incidents (200 OK) | **PASSED** |
| `test_unauthorized_user_management` | Non-Platform-Admin roles cannot manage users (403 Forbidden) | **PASSED** |
| `test_platform_admin_cannot_modify_or_approve_remediation` | Platform Administrator cannot modify or approve remediation (403) | **PASSED** |
| `test_authorized_engineer_remediation_modification` | Network Engineer modifies commands; persisted in SQLite (200 OK) | **PASSED** |
| `test_audit_access_restricted_correctly` | Auditor and Platform Admin access audit logs; Helpdesk receives 403 | **PASSED** |
| `test_hitl_actor_persistence_in_database` | Approvals persist all 7 structured actor attributes in SQLite | **PASSED** |
| `test_forged_actor_identity_rejected` | Client request body operator spoofing is discarded; binds token identity | **PASSED** |
| `test_logout_and_token_invalidation` | Logout writes `jti` to `revoked_tokens`; subsequent requests return 401 | **PASSED** |
| `test_websocket_ticket_exchange_endpoint` | `POST /api/auth/ws-ticket` issues short-lived single-use ticket | **PASSED** |
| `test_websocket_ticket_connection_and_replay_rejection` | WebSocket consumes ticket on handshake; replaying consumed ticket returns 1008 | **PASSED** |
| `test_websocket_invalid_and_expired_ticket_rejected` | Invalid or expired ticket connections are rejected with 1008 | **PASSED** |
| `test_websocket_anonymous_rejected` | Anonymous WebSocket connections without ticket or token return 1008 | **PASSED** |
| `test_mcp_authorization` | MCP sensitive tools require valid token via argument or `NETCOOP_MCP_TOKEN` | **PASSED** |
| `test_sec01_unauthenticated_remediation_approval_returns_401` | SEC-01: Direct unauthenticated remediation approval returns 401; authorized returns 200 | **PASSED** |
| `test_sec02_helpdesk_remediation_approval_returns_403` | SEC-02: Helpdesk remediation approval returns 403; authorized Admin returns 200 | **PASSED** |
| `test_sec03_auditor_remediation_modification_returns_403` | SEC-03: Auditor remediation modification returns 403; authorized Engineer returns 200 | **PASSED** |
| `test_sec04_unauthenticated_device_inventory_returns_401` | SEC-04: Unauthenticated device inventory returns 401; authorized Admin returns 200 | **PASSED** |
| `test_sec05_unauthenticated_platform_status_returns_401` | SEC-05: Unauthenticated platform status returns 401; authorized Admin returns 200 | **PASSED** |
| `test_sec06_unauthenticated_audit_log_returns_401` | SEC-06: Unauthenticated audit log export returns 401; authorized Auditor returns 200 | **PASSED** |
| `test_rate_limiting_locks_account_after_5_failed_attempts` | IP rate limiting locks account or returns 429 after 5 failed attempts in 5 minutes | **PASSED** |
| `test_real_remediation_execution_blocked_with_403` | Production remediation real execution returns 403 (simulation mode enforced) | **PASSED** |

**Security Test Suite Summary**: **29 passed in 4.83s** (100% pass rate).

### 9.2 Full Repository Regression Suite
Executed via `pytest tests/ -q`:
```
........................................................................ [ 37%]
........................................................................ [ 74%]
.................................................                        [100%]
193 passed, 4 warnings in 33.08s
```
**Regression Summary**: **193 passed, 0 failed** across all 24 test modules.

### 9.3 Frontend Build Verification
Executed via `npm run build` in `dashboard`:
```
> netcoop-frontend@1.0.0 build
> tsc && vite build

vite v5.4.21 building for production...
transforming...
[PASS] 227 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.87 kB │ gzip:   0.50 kB
dist/assets/index-DfM9YTW2.css   37.71 kB │ gzip:   7.30 kB
dist/assets/index-xRpcMFnD.js   522.74 kB │ gzip: 140.67 kB
[PASS] built in 1.92s
```

### 9.4 Repository Hygiene Audit
Executed via `python scripts/audit_repo.py`:
```
=== REPO AUDIT REPORT ===
Total tracked files scanned: 251
Large files (> 5MB): 0
Secrets detected: 0
Emojis detected: 0
Gradients detected: 0
Audit PASSED cleanly: zero emojis, zero secrets, zero large files, zero gradients.
```

---

## 10. Production Deployment Guidelines

For deployment into staging or production campus environments:

### 10.1 Environment Configuration
```bash
# Enforce strict production security policies
export NETCOOP_ENV="production"
export NETCOOP_DEMO_MODE="false"

# Generate and export a high-entropy secret using the recommended generation command:
export NETCOOP_JWT_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(48))")
```

On Windows PowerShell:
```powershell
$env:NETCOOP_ENV = "production"
$env:NETCOOP_DEMO_MODE = "false"
$env:NETCOOP_JWT_SECRET = python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### 10.2 Initial Administrative Account Provisioning
In production mode, default demo accounts are not seeded. The initial Platform Administrator account must be provisioned via an administrative bootstrap script with a securely chosen password:

```bash
python -c "
from netcoop.storage.db import init_db, provision_admin_user
import getpass
init_db()
admin_pass = getpass.getpass('Enter secure password for initial administrator: ')
provision_admin_user(
    username='prod_admin',
    password=admin_pass,
    full_name='Production Platform Administrator'
)
print('Initial administrator account created.')
"
```

### 10.3 Subsequent User Management
The Platform Administrator signs in and registers enterprise accounts via `POST /api/users` with assigned roles and complex passwords.

---

## 11. Git State Preservation & Dedicated PR Recommendation

### 11.1 Current Git Status and Verification
- **Local HEAD SHA**: `871a4ce91cb215ebbf1278bed70653029539e7d3`
- **Upstream `origin/feat/ui` SHA**: `36bfd07c2789697e6e850dccba836fc1de2215b2`
- **Status**: Local `HEAD` is 7 commits ahead of `origin/feat/ui`, representing Phase 3 UI dashboard and orchestrator integration work.
- **Phase 4 Changes**: Preserved in the local working tree without destructive resets or premature commits.

### 11.2 Working Tree File Classification
1. **Phase 3 Dashboard & Validation Artifacts (Staged)**:
   - `docs/performance_benchmark_results.json`
   - `docs/persistence_validation_results.json`
   - `docs/phase3_validation_report.md`
   - `docs/security_audit_findings.json`
   - `docs/test_workflow_results.json`
   - `docs/websocket_validation_results.json`
   - `tests/test_phase3_validation.py`
2. **Phase 4 Backend Authentication & Security Hardening (Unstaged & Untracked)**:
   - Core Security Logic: `core/auth.py`, `netcoop/core/auth.py`
   - API Security Gates: `api/main.py`, `netcoop/main.py`
   - Configuration Hardening: `core/config.py`, `netcoop/config.py`
   - Database Models & User Store: `storage/db.py`, `netcoop/storage/db.py`, `storage/models.py`, `netcoop/storage/models.py`
   - MCP Server Credential Review: `mcp_server/server.py`, `netcoop/mcp/server.py`
   - Frontend Authentication & Ticket Integration: `dashboard/src/auth/`, `dashboard/src/components/LoginModal.tsx`, `dashboard/src/App.tsx`
   - Security Verification Suite: `tests/test_phase4_security.py`
   - Security Documentation: `docs/phase4_security_report.md`

### 11.3 Recommended Dedicated PR Workflow
To keep Phase 3 UI work cleanly separated from Phase 4 Security Hardening, the engineering team should create a dedicated branch and PR:

```bash
# 1. Create and switch to a dedicated security feature branch from current state
git checkout -b feature/backend-auth-hardening

# 2. Stage Phase 4 authentication, hardening, tests, and documentation files
git add core/auth.py netcoop/core/auth.py
git add api/main.py netcoop/main.py
git add core/config.py netcoop/config.py
git add storage/db.py netcoop/storage/db.py
git add storage/models.py netcoop/storage/models.py
git add mcp_server/server.py netcoop/mcp/server.py
git add dashboard/src/auth/ dashboard/src/components/LoginModal.tsx dashboard/src/App.tsx
git add tests/test_phase4_security.py
git add docs/phase4_security_report.md

# 3. Commit Phase 4 changes cleanly
git commit -m "feat(security): implement backend authentication, least-privilege rbac, ws tickets, and hitl audit persistence"

# 4. Push to remote for isolated security peer review
git push -u origin feature/backend-auth-hardening
```
