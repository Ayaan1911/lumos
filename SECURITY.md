# Security Policy

## Supported versions

|Version|Supported|
|-|-|
|latest|✅|

## Reporting a vulnerability

Do not open a public GitHub issue for security vulnerabilities.

Open a private GitHub security advisory at:
https://github.com/your-org/lumos/security/advisories/new

Include:

* Description of the vulnerability
* Steps to reproduce
* Potential impact
* Suggested fix (if known)

We will respond within 48 hours.

## Security design

Lumos is designed to be a security enforcement layer.
Its own security properties are therefore critical.

Key design decisions:

* All token validation is DB-backed and fail-closed
* Policy evaluation errors fail open only after successful authentication, to avoid blocking legitimate traffic due to transient policy issues.
* Admin token comparison uses hmac.compare\_digest (constant-time)
* Issuer private key stored with 0o600 permissions
* All audit events include a Merkle SHA-256 hash chain
* PII is redacted before writing to audit storage
* Sessions, capabilities, and nonces expire automatically

