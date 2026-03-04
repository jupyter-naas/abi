# Authentication Processes
## BFO 7 Buckets Compliant Ontologies

This folder contains individual Turtle ontology files for each authentication and authorization process in the NEXUS platform.

## Process Files

| File | Process | Description |
|------|---------|-------------|
| `user_registration_process.ttl` | **User Registration** | Creates new user accounts with personal workspace, encrypted credentials, and initial tokens |
| `user_login_process.ttl` | **User Login** | Authenticates credentials and issues JWT access/refresh tokens |
| `token_refresh_process.ttl` | **Token Refresh** | Rotates tokens implementing token rotation security |
| `token_revocation_process.ttl` | **Token Revocation** | Invalidates tokens (logout, password change, security breach) |
| `password_change_process.ttl` | **Password Change** | Updates password, revokes all sessions, logs security event |
| `workspace_access_control_process.ttl` | **Access Control** | Validates workspace permissions (owner/admin/member/viewer) |
| `rate_limiting_process.ttl` | **Rate Limiting** | Prevents brute force attacks (5 attempts per 15min window) |
| `audit_logging_process.ttl` | **Audit Logging** | Records security events for compliance and forensics |

## Implementation

**Backend:** `apps/api/app/api/endpoints/auth.py`, `apps/api/app/services/refresh_token.py`, `apps/api/app/services/rate_limit.py`, `apps/api/app/services/audit.py`

## Security Features

- **Password Hashing:** bcrypt with 12 salt rounds
- **Token Format:** JWT with JTI (JWT ID) for revocation tracking
- **Token Lifetime:** Access (15 minutes), Refresh (30 days)
- **Rate Limiting:** 5 attempts per 15-minute window per IP/user
- **Audit Logging:** All security events logged with IP, user-agent, timestamp
- **Token Rotation:** Refresh tokens are rotated on each use (old token revoked)

## BFO 7 Buckets Structure

Each process ontology follows the BFO 7 Buckets framework:

1. **WHAT (Process):** BFO_0000015 - The authentication process itself
2. **WHO (Material Entity):** BFO_0000040 - User, AuthenticationServer, DatabaseServer
3. **WHERE (Site):** BFO_0000029 - API endpoints (/api/auth/*), database tables
4. **WHEN (Temporal Region):** BFO_0000008 - Token lifetimes, rate limit windows
5. **HOW WE KNOW (GDC):** BFO_0000031 - Tokens, credentials, audit logs
6. **HOW IT IS (Quality):** BFO_0000019 - Password strength, token validity, security level
7. **WHY (Role/Disposition):** BFO_0000023/BFO_0000016 - Authenticator role, hashing disposition

## Usage

Import shared entities first, then specific processes:

```turtle
@prefix nexus: <http://nexus.platform/ontology/> .

# Import shared entities
owl:imports <http://nexus.platform/ontology/_shared/common_entities> .

# Import specific process
owl:imports <http://nexus.platform/ontology/authentication/user_login_process> .

# Query example
SELECT ?process ?participant WHERE {
    ?process a nexus:UserLoginProcess .
    ?process bfo:BFO_0000057 ?participant .  # has participant
}
```

## Related

- **Shared Entities:** `../_shared/common_entities.ttl`
- **Chat Processes:** `../chat_conversation/`
- **Main Index:** `../README.md`
