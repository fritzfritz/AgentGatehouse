# Acceptance checks

Status: test plan only; no automated checks are implemented or have run against infrastructure.

The authoritative scenarios are [A-01 through A-10](../../requirements.md#6-first-milestone-acceptance-criteria). Future checks should test the same observable behavior across providers, with provider-specific setup where necessary.

Priorities:

1. Useful public browsing, repository access, and an authenticated project API work through the gateway.
2. Direct egress fails with proxy settings removed, including attempts from worker root and alternate network protocols.
3. Upstream credentials remain absent from worker-visible files, environment, diagnostics, and API responses in controlled canary tests.
4. Out-of-scope destinations, redirect-based credential leaks, and access to management/control endpoints are rejected.
5. Gateway failure does not permit direct fallback access.
6. The selected cloud-log and OAuth-refresh integrations behave as documented.

Use controlled endpoints and synthetic credentials. Keep captured traffic and secret-bearing test artifacts out of Git. Do not add resource-exhaustion tests without specific authorization; v1 intentionally has no per-agent resource quotas.
