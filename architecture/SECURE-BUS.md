# Secure LOCI inter-agent bus

The first coordination slice is in `coordination_bus/bus.py`. It is local-first and uses SQLite so it can be adopted by any project without making that project's own data store the live lock service.

## Security boundary

Messages are untrusted data until they pass:

1. schema validation;
2. HMAC-SHA256 authentication;
3. project and operation authorization;
4. expiry, sequence, and idempotency checks;
5. relative-path validation;
6. payload authority-field rejection.

Payloads are never executed. A message cannot grant tools, permissions, credentials, shell access, or a larger path scope. Retrieved LOCI memory is context only and cannot authorize an action.

## Review and conflict flow

Workers claim a task lease, work only in their assigned Git worktree, commit and test their changes, request review, and wait for an explicitly authorized reviewer. A conflict blocks only the affected task; the decision, evidence, and accepted resolution should be written back to LOCI with the event ID and commit SHA.

## Real-time deployment

The current bus provides durable replay through `events(project_id, after_sequence)`. Add SSE/WebSockets or a durable stream adapter later; keep the SQLite/PostgreSQL event log authoritative. Use short-lived credentials or mTLS for remote transport, default-deny authorization, bounded progress events, and idempotent consumers.

## Limitations

No static filter detects every prompt injection. Security therefore comes from the architecture: untrusted text is data, authority is server-side, scopes are explicit, and destructive/external operations require a separate human approval gate.


## MCP service

coordination_bus/mcp_server.py binds one host-configured agent identity to a FastMCP stdio server. Install it with pip install -e '.[mcp]', then configure one process per agent with different identities and the same SQLite path.

The process requires LOCI_AGENT_ID, LOCI_AGENT_SECRET, LOCI_PROJECTS, and LOCI_OPERATIONS. Set LOCI_COORDINATION_DB to the shared SQLite file. Use LOCI_PEERS_JSON from the host secret store for peer registrations so recipient authorization works across MCP processes.

Never commit secrets or expose arbitrary shell, file, permission, credential, or tool-execution operations through MCP.