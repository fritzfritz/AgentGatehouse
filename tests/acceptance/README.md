# Acceptance checks

Status: worker smoke test implemented; no live Azure acceptance checks have run.

The authoritative scenarios are [A-01 through A-10](../../requirements.md#6-first-milestone-acceptance-criteria). [worker-network.py](worker-network.py) checks proxied connectivity and selected blocked TCP paths. It is preinstalled by cloud-init; use it with a controlled endpoint independently known to be reachable. A timeout against a dead endpoint is not proof of isolation. See the [runbook](../../docs/deployment-azure.md#acceptance-before-real-workloads).

Priorities:

1. Useful public browsing, repository access, and an authenticated project API work through the gateway.
2. Direct egress fails with proxy settings removed, including attempts from worker root and alternate network protocols.
3. Upstream credentials remain absent from worker-visible files, environment, diagnostics, and API responses in controlled canary tests.
4. Out-of-scope destinations, redirect-based credential leaks, and access to management/control endpoints are rejected.
5. Gateway failure does not permit direct fallback access.
6. The selected cloud-log and OAuth-refresh integrations behave as documented.

Use controlled endpoints and synthetic credentials. Keep captured traffic and secret-bearing test artifacts out of Git. Do not add resource-exhaustion tests without specific authorization; v1 intentionally has no per-agent resource quotas.

Local checks from the repository root:

```bash
az bicep build --file infra/azure/main.bicep --outfile /tmp/agentgatehouse-arm.json
python3 tests/check_arm.py /tmp/agentgatehouse-arm.json
python3 -m unittest discover -s tests -p 'test_*.py' -v
bash -n bootstrap/gateway.sh bootstrap/install-tools.sh infra/azure/deploy.sh
```

These check compiled network/identity properties, input rejection, session handling and TLS transport verification. They do not emulate Azure or Agent Vault. Live UDP/DNS, IPv6, credential reflection/redirects, public ingress, gateway outage and actual Git/model/cloud/OAuth checks remain required.
