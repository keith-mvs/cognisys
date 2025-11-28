# IFMOS Security Documentation

Security features, best practices, and hardening guide for the Intelligent File Management and Organization System.

## Security Features

### Rate Limiting ✅

**Implementation**: In-memory rate limiter tracking requests per IP address

**Limits**:
- **60 requests per minute** per IP address
- **1,000 requests per hour** per IP address

**Protected Endpoints**:
- `/process/document` - Main document processing pipeline
- `/ocr/extract` - OCR text extraction
- `/extract/document` - Content extraction

**Behavior**:
- Returns **HTTP 429** (Too Many Requests) when limit exceeded
- Includes `Retry-After` header with wait time in seconds
- Automatic cleanup of old request records
- Zero-dependency implementation (stdlib only)

**Example Response** (Rate Limited):
```json
{
  "error": "Rate limit exceeded",
  "message": "Too many requests. Please try again later.",
  "retry_after": 60
}
```

**Testing Rate Limits**:
```bash
# Test minute limit (send 61 requests rapidly)
for i in {1..61}; do
  curl -X POST http://localhost:5000/health
done
# 61st request should return 429
```

### CORS (Cross-Origin Resource Sharing) ✅

**Pol**icy**: Localhost-only access

**Allowed Origins**:
- `http://localhost:*` (any port)
- `http://127.0.0.1:*` (any port)
- `http://[::1]:*` (IPv6 localhost, any port)

**Blocked**: All other origins (prevents unauthorized web access)

**Headers Applied**:
```
Access-Control-Allow-Origin: <requesting-origin>
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS
Access-Control-Allow-Headers: Content-Type, Authorization
Access-Control-Max-Age: 3600
```

**Configuration**:
```python
from ifmos.ml.api.security import configure_cors

# Default (localhost only)
configure_cors(app)

# Custom allowed origins
configure_cors(app, allowed_origins=[
    'http://localhost:*',
    'http://myapp.local:*'
])
```

### Security Headers ✅

**OWASP Recommended Headers** applied to all responses:

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Frame-Options` | `DENY` | Prevents clickjacking attacks |
| `X-Content-Type-Options` | `nosniff` | Prevents MIME type sniffing |
| `X-XSS-Protection` | `1; mode=block` | Enables browser XSS protection |
| `Content-Security-Policy` | `default-src 'self'` | Restricts resource loading |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Controls referrer information |
| `Permissions-Policy` | `geolocation=(), microphone=(), camera=()` | Denies dangerous permissions |

**Excluded Headers** (for local development):
- `Strict-Transport-Security` - Commented out (HTTPS not required for localhost)

### Input Validation ✅

**File Path Validation**:
```python
# Checks performed on all file paths
1. File exists
2. File is readable
3. File extension is supported
4. File size within limits
```

**Content Type Validation**:
```python
# Supported formats enforced
Supported: .pdf, .txt, .docx, .xlsx, .csv, .png, .jpg, .jpeg, .webp, .tiff, .bmp, .gif
Unsupported formats rejected with error
```

## Security Best Practices

### 1. Network Security

**Recommendation**: Run API server on localhost only

```python
# Good - localhost binding
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000)


# Bad - all interfaces (allows remote access)
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

**Firewall Rules**:
```powershell
# Block external access to port 5000
New-NetFirewallRule -DisplayName "Block IFMOS External" `
    -Direction Inbound `
    -LocalPort 5000 `
    -Protocol TCP `
    -Action Block `
    -RemoteAddress !127.0.0.1,!::1
```

### 2. File System Security

**Principle**: Never trust user-provided file paths

**Good Practices**:
```python
from pathlib import Path


def safe_file_access(user_path, base_dir):
    """Safely validate file path"""
    # Resolve to absolute path
    file_path = Path(user_path).resolve()
    base_path = Path(base_dir).resolve()

    # Ensure path is within allowed directory
    if not str(file_path).startswith(str(base_path)):
        raise SecurityError("Path traversal detected")

    # Ensure file exists and is a file (not directory)
    if not file_path.is_file():
        raise FileNotFoundError(f"Not a file: {file_path}")

    return file_path
```

**Path Traversal Prevention**:
```python
# Bad - vulnerable to path traversal
file_path = request.get_json()['file_path']
with open(file_path) as f:  # Could access ../../etc/passwd
    content = f.read()


# Good - validated path
from pathlib import Path

file_path = Path(request.get_json()['file_path']).resolve()
if file_path.parent != expected_directory:
    raise SecurityError("Invalid path")
```

### 3. Database Security

**SQL Injection Prevention**:
```python
# Good - parameterized queries
cursor.execute(
    "SELECT * FROM documents WHERE id = ?",
    (doc_id,)
)


# Bad - string concatenation
cursor.execute(
    f"SELECT * FROM documents WHERE id = {doc_id}"
)
```

**Database Permissions**:
- Use read-only connections where possible
- Separate user credentials for read vs write
- Never store passwords in plaintext

### 4. Sensitive Data Handling

**Data at Rest**:
- Exclude `ifmos_ml.db` from version control (contains user documents)
- Store API keys in environment variables, not code
- Use `.env` files with `.gitignore` for secrets

```python
# Good - environment variables
import os

API_KEY = os.getenv('IFMOS_API_KEY')
if not API_KEY:
    raise ValueError("IFMOS_API_KEY not set")


# Bad - hardcoded secrets
API_KEY = "sk-1234567890abcdef"  # Never do this!
```

**Data in Transit**:
- For production: Use HTTPS (TLS/SSL)
- For localhost: HTTP acceptable (data never leaves machine)

### 5. Dependency Security

**Regular Updates**:
```bash
# Check for vulnerable packages
pip install safety
safety check --json

# Update dependencies
pip list --outdated
pip install --upgrade <package>
```

**Lock File**:
```bash
# Create reproducible environment
pip freeze > requirements-lock.txt

# Install exact versions
pip install -r requirements-lock.txt
```

## Security Checklist

### Development ✅

- [x] Rate limiting implemented
- [x] CORS configured (localhost only)
- [x] Security headers applied
- [x] Input validation on all endpoints
- [x] No hardcoded secrets
- [x] Database excluded from version control
- [x] `.gitignore` configured for sensitive files

### Production (To Implement)

- [ ] API authentication (OAuth2, JWT, or API keys)
- [ ] HTTPS/TLS encryption
- [ ] Request signing for integrity
- [ ] Audit logging for all requests
- [ ] Encrypted database (SQLCipher)
- [ ] Secrets management (HashiCorp Vault, AWS Secrets Manager)
- [ ] Security scanning in CI/CD
- [ ] Penetration testing

## Known Limitations

### Current Security Gaps

1. **No Authentication**
   - **Risk**: Anyone on localhost can access API
   - **Mitigation**: Run on trusted machines only
   - **Future**: Implement API key or JWT auth

2. **No Request Signing**
   - **Risk**: Requests can be replayed
   - **Mitigation**: Short-lived rate limits prevent abuse
   - **Future**: HMAC request signing

3. **No Encryption at Rest**
   - **Risk**: Database accessible if file system compromised
   - **Mitigation**: Use OS-level encryption (BitLocker, FileVault)
   - **Future**: SQLCipher for encrypted database

4. **No Audit Logging**
   - **Risk**: No record of who accessed what
   - **Mitigation**: Application logs capture basic info
   - **Future**: Structured audit log with retention

## Incident Response

### Security Issue Reporting

**If you discover a security vulnerability**:
1. **Do not** create a public GitHub issue
2. Email: [security contact - configure this]
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (optional)

### Response Process

1. **Acknowledge** report within 24 hours
2. **Investigate** and validate the issue
3. **Develop** fix in private branch
4. **Test** fix thoroughly
5. **Disclose** responsibly after patch released

## Security Updates

### How to Apply Security Patches

```bash
# Update to latest secure version
git pull origin master

# Reinstall dependencies
pip install -r requirements.txt -r requirements-ml.txt

# Restart API server
Stop-IFMOSMLServer
Start-IFMOSMLServer

# Verify security features
curl http://localhost:5000/health
# Should have security headers
```

### Monitoring for Vulnerabilities

```bash
# Install security scanners
pip install bandit safety

# Scan code for security issues
bandit -r ifmos/

# Check dependencies
safety check
```

## Security Configuration

### Environment Variables

```bash
# .env file (never commit this!)
IFMOS_DB_PATH=C:\Users\YourName\ifmos_data\ifmos_ml.db
IFMOS_RATE_LIMIT_MINUTE=60
IFMOS_RATE_LIMIT_HOUR=1000
IFMOS_ALLOWED_ORIGINS=http://localhost:*
IFMOS_LOG_LEVEL=INFO
```

### Loading Environment

```python
from dotenv import load_dotenv
import os

load_dotenv()  # Load .env file

DB_PATH = os.getenv('IFMOS_DB_PATH', 'default/path/ifmos_ml.db')
RATE_LIMIT_MINUTE = int(os.getenv('IFMOS_RATE_LIMIT_MINUTE', '60'))
```

## Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [OWASP API Security](https://owasp.org/www-project-api-security/)
- [CWE Top 25](https://cwe.mitre.org/top25/)
- [Python Security Best Practices](https://python.readthedocs.io/en/stable/library/security_warnings.html)

---

**Security Review Date**: 2025-11-27
**Next Review**: 2026-02-27 (90 days)
**Security Contact**: [Configure email address]
