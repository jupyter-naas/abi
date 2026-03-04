# Security Policy

## Supported Versions

We release patches for security vulnerabilities in the following versions:

| Version | Supported          |
| ------- | ------------------ |
| main    | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

**Please DO NOT report security vulnerabilities through public GitHub issues.**

Instead, please report them via email to: **security@naas.ai**

### What to Include

When reporting a vulnerability, please include:

1. **Description** - Clear explanation of the vulnerability
2. **Impact** - What an attacker could do with this vulnerability
3. **Steps to Reproduce** - Detailed steps to reproduce the issue
4. **Affected Components** - Which parts of the system are affected
5. **Suggested Fix** - If you have ideas on how to fix it (optional)
6. **Your Contact Info** - How we can reach you for follow-up

### What to Expect

- **Acknowledgment**: We will acknowledge receipt within 48 hours
- **Initial Assessment**: We will provide an initial assessment within 1 week
- **Updates**: We will keep you informed as we investigate and fix the issue
- **Credit**: We will credit you in the security advisory (unless you prefer to remain anonymous)
- **Disclosure**: We follow coordinated disclosure practices

### Timeline

- **Critical vulnerabilities** (RCE, SQLi, auth bypass): Fixed within 7 days
- **High severity** (XSS, IDOR, information disclosure): Fixed within 14 days
- **Medium/Low severity**: Fixed in next regular release

## Security Best Practices

### For Users

1. **Environment Variables**
   - Never commit `.env` files
   - Use strong, unique values for `SECRET_KEY`
   - Rotate API keys regularly

2. **Database Security**
   - Use strong PostgreSQL passwords
   - Don't expose PostgreSQL port (5432) publicly
   - Enable SSL/TLS for database connections in production

3. **API Security**
   - Always use HTTPS in production
   - Enable rate limiting (already configured)
   - Monitor audit logs for suspicious activity

4. **Secrets Management**
   - Store API keys in NEXUS secrets vault (encrypted at rest)
   - Don't hardcode credentials in code
   - Use workspace-scoped secrets for multi-tenancy

5. **Updates**
   ```bash
   git pull origin main
   make install
   make db-migrate
   make restart
   ```

### For Developers

1. **Input Validation**
   - Always validate user input (Pydantic schemas)
   - Sanitize data before database queries (SQLAlchemy ORM)
   - Escape output in templates

2. **Authentication**
   - Use `get_current_user_required()` dependency
   - Check workspace permissions with `get_workspace_role()`
   - Never bypass auth middleware

3. **Database**
   - Use SQLAlchemy ORM (prevents SQL injection)
   - Never construct raw SQL from user input
   - Use parameterized queries if raw SQL needed

4. **Dependencies**
   - Run `pnpm audit` and `uv pip audit` regularly
   - Update vulnerable dependencies promptly
   - Review dependency licenses

5. **Secrets**
   - Use environment variables via `settings`
   - Never log sensitive data
   - Encrypt secrets at rest (already implemented)

## Known Security Features

NEXUS includes these security features:

- **Authentication**: JWT tokens with refresh mechanism
- **Authorization**: Role-based access control (RBAC)
- **Rate Limiting**: Protects against brute force attacks
- **Audit Logging**: Tracks sensitive operations
- **Session Management**: Token revocation on password change
- **Secrets Encryption**: API keys encrypted at rest
- **CORS Protection**: Whitelisted origins only
- **SQL Injection Protection**: SQLAlchemy ORM
- **Password Hashing**: bcrypt with salt

## Security Checklist for Production

Before deploying to production:

- [ ] Change `SECRET_KEY` from default
- [ ] Use strong database password
- [ ] Enable HTTPS (reverse proxy or CDN)
- [ ] Configure `CORS_ORIGINS` to production domains only
- [ ] Set `DEBUG=false` in production
- [ ] Enable security headers (HSTS, CSP, X-Frame-Options)
- [ ] Set up database backups
- [ ] Configure monitoring and alerting
- [ ] Review and rotate API keys
- [ ] Enable PostgreSQL SSL connections
- [ ] Implement firewall rules (whitelist IPs)
- [ ] Set up log aggregation and retention

## Vulnerability Disclosure

When we receive a security vulnerability report, we will:

1. **Investigate** - Validate and assess the vulnerability
2. **Fix** - Develop and test a patch
3. **Notify** - Inform affected users (if applicable)
4. **Release** - Publish patched version
5. **Disclose** - Publish security advisory on GitHub

We appreciate the security research community's efforts to improve NEXUS security.

## Hall of Fame

Contributors who have responsibly disclosed security vulnerabilities will be recognized here:

- (None yet - be the first!)

## Questions?

For general security questions (not vulnerabilities), open a GitHub Discussion or contact **security@naas.ai**.


