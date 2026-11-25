# Billo platform status in the unified repository

This directory is the Billo deployment source snapshot consolidated into the
LOCI monorepo. Its original source hashes are retained in
[`SOURCE-ORIGINAL-MANIFEST.sha256`](./SOURCE-ORIGINAL-MANIFEST.sha256); the
USB source directory remains unchanged. The Docker compose file in this copy
uses the required `ACME_EMAIL` environment variable instead of embedding a
personal email address. `SOURCE-MANIFEST.sha256` verifies the current
consolidated copy.

The original [`README.md`](./README.md) is preserved as source documentation,
not as a current production-readiness guarantee. Follow the monorepo
[release gates](../docs/release-readiness.md) before deployment.
The accompanying architecture document and deployment examples also reflect
the source snapshot's assumptions; verify hardware, domains, and infrastructure
before reusing them.

## Known blockers

- The API has no authentication or authorization on context, scratch, and
  operational routes; CORS currently allows all origins with credentials.
- The VPS installer does not copy the application source into `/opt/billo`.
  It also upgrades the OS and changes firewall/services, so review and stage
  those side effects before any execution.
- The Billo `loci/` code and the root `loci_engine/` code are distinct memory
  implementations. Their persistence and runtime integration have not been
  validated.
- Automated coverage for the Billo API, worker, Docker deployment, and VPS
  installer is not present in this snapshot.

Run only in an isolated local development environment until these blockers
are addressed and staging verification passes. Do not expose it publicly or
run the installer against a live host.
