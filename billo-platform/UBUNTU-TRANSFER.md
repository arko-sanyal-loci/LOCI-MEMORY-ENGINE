# Ubuntu transfer and SaaS readiness

## What this folder is

This is a transfer copy extracted from `backup.zip` at:

```text
Drive BUP/E_drive_backup_20260910/03_Project-Billo-LOCI/Billo_Loci/extracted/billo_loci_unified/
```

The original archive remains unchanged. In this consolidated repository,
`SOURCE-ORIGINAL-MANIFEST.sha256` records the SHA-256 hashes of the 24 files
extracted from that archive. The Billo Docker compose file was sanitized in
the consolidated copy to require `ACME_EMAIL`; the USB source remains
unchanged.

Verify this consolidated copy from this directory:

```bash
sha256sum -c SOURCE-MANIFEST.sha256
```

The USB is FAT32 and the original snapshot has no `.git` history or remote. It
is suitable for carrying files, but not as the working Git repository. The
snapshot is now consolidated as `billo-platform/` in the canonical
LOCI-MEMORY-ENGINE Git checkout. Keep its Billo `loci/` implementation separate
from the root `loci_engine/` until their API, storage, and migration contracts
are explicitly designed and tested.

## Current deployment blockers

- `deploy/vps-install.sh` creates `/opt/billo` but does not copy this project's
  source into it. As written, it cannot install the application from a fresh
  checkout.
- `billo/app.py` exposes context-indexing, memory-query, handover, scratch, and
  operations endpoints without authentication. `CORSMiddleware` allows all
  origins together with credentials.
- `deploy/docker/docker-compose.yml` publishes the API through public Traefik
  routers; it does not add API authentication or rate limiting.
- The repository snapshot contains no automated tests or lockfile. Treat the
  installer and Docker deployment as unverified, not production-ready.

Do not run the VPS installer or expose these endpoints publicly until the
source deployment step is fixed, an authentication and authorization design is
implemented, CORS is restricted to approved origins, and a staging deployment
has passed verification.

## Workstation and media notes

- Keep secrets out of the USB and out of `.env.example`; create real
  environment files only on appropriately protected storage.
- The USB separately contains MSI BIOS files for the **PRO Z890-S WIFI
  (MS-7E54)**. See [`../../FIRMWARE-PROVENANCE.txt`](../../FIRMWARE-PROVENANCE.txt)
  for their recorded version and hashes. Do not flash as part of this software
  preparation.
- Claude-specific project memory is in [`CLAUDE.md`](./CLAUDE.md). It
  distinguishes project evidence from claims and sets a no-attacks boundary.
