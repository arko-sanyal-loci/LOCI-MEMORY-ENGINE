# Security policy

Please do **not** report security problems in public issues.

Report them privately through GitHub's **Report a vulnerability** button on the affected
repository (Security tab → Advisories), or contact the maintainer, Arko Sanyal, through the
Billo Tech organization. Include what you found, how to reproduce it, and what it affects.

We aim to acknowledge reports within 3 days and to agree a fix and disclosure date with you.

In scope: the LOCI Memory Engine (including the coordination bus and MCP server) and the Arc
runtime. Retrieved memory, agent messages and documents are treated as untrusted data by design;
a way to make any of them grant permissions or run commands is a vulnerability.
