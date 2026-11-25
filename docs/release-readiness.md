# Release readiness

## Current assessment

The source is consolidated into one Git repository, but the product is **not
yet a stable, production-ready end-to-end deployment**. The LOCI engine and
Billo snapshot are separate implementations with no validated shared runtime
contract.

## Required gates before production

- [ ] Define and test the LOCI-to-Billo API, identity, persistence, and
  migration contracts. Do not share or migrate databases by assumption.
- [ ] Add authentication and authorization to Billo's context, scratch, and
  operational endpoints.
- [ ] Replace Billo's wildcard CORS configuration with an explicit
  environment-controlled allowlist.
- [ ] Repair and test the VPS installer so it installs the intended checkout
  into `/opt/billo`; the current script creates directories and installs
  services but does not deploy the application source. Review its OS upgrade,
  firewall, and service changes before executing it.
- [ ] Add automated tests for the Billo API, worker, database initialization,
  and deployment configuration.
- [x] Lock the current Python runtime and development dependencies for
  reproducible review. Supported production Python/OS versions and recurring
  vulnerability audits still require release approval.
- [ ] Audit tracked environment/configuration files before publishing. In
  particular, `config/nodes.env` is tracked in the LOCI repository; verify it
  contains no credentials. If credentials were committed, rotate them and
  follow the repository's approved history-cleanup process.
- [ ] Verify backup, restore, monitoring, secret handling, and rollback on a
  non-production staging system.
- [ ] Keep benchmark claims tied to exact datasets, code revisions, commands,
  outputs, evaluator versions, and per-question results. See the Billo
  [LongMemEval reconciliation](../billo-platform/LONGMEMEVAL-RECONCILIATION.md).

## Safe local checks

Run the LOCI suite from the repository root:

```bash
python -m pytest -q
```

Verify the consolidated Billo source copy from its directory:

```bash
cd billo-platform
sha256sum -c SOURCE-MANIFEST.sha256
```

The original USB directory remains unchanged and can be verified there using
its `SOURCE-MANIFEST.sha256`. The consolidated copy intentionally replaces the
personal ACME email literal with the required `ACME_EMAIL` deployment
variable; the original hashes are preserved in
`billo-platform/SOURCE-ORIGINAL-MANIFEST.sha256`.

These checks do not establish that the Billo service is secure, that the two
memory implementations interoperate, or that a production deployment works.
Do not run `billo-platform/deploy/vps-install.sh` against a live host as a
substitute for staging verification.
