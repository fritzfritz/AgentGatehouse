# Agent Gatehouse requirements

Status: agreed concept; implementation and verification pending.

Recorded: 2026-09-18.

## 1. Purpose and operating model

Provide a simple, open-source-based environment for powerful coding agents, initially Codex and/or Claude Code, without relying on model obedience for security enforcement. Agents may reason, execute code, and coordinate freely inside their project environment.

One project is the initial trust boundary: its repositories, development environment, and cooperating agents. Typical work includes feature development, bug investigation, public research, cloud-log analysis, testing, and preparing repository changes.

The operator grants capabilities in advance. Routine operations inside those grants should not require repeated approval. Changes to grants remain operator-controlled.

## 2. Functional requirements

| ID | Requirement |
| --- | --- |
| F-01 | Provision infrastructure reproducibly using Azure Bicep initially: a Linux project worker VM, a separate Agent Vault gateway, external network rules, and an administrative access path. A future AWS deployment will be an independent provider-specific implementation. |
| F-02 | Target a resource-rich worker VM with 64 GB RAM or more and many CPU cores. Allow agents to share available resources without initial per-agent CPU/RAM quotas or a custom resource scheduler. |
| F-03 | Install and configure Codex and/or Claude Code, Git, Docker, and a practical development tool baseline. Support disposable, devcontainer-like environments. |
| F-04 | Permit parallel cooperating agents and an agent-driven orchestrator. Do not require a new orchestration platform for v1. |
| F-05 | Configure worker tools to use Agent Vault, including proxy settings and trust in the gateway's public CA certificate. Never install its CA private key on the worker. |
| F-06 | Support project-scoped GitHub/GitLab workflows over HTTPS. Select and test the initial provider and workflows; Git over SSH is outside the initial HTTP scope. |
| F-07 | Support useful public web search and fetching. Make the tradeoff between broad browsing and destination restrictions explicit in the chosen policy. |
| F-08 | Support authenticated HTTP APIs through gateway-side bearer, API-key, Basic, or custom-header injection as appropriate. |
| F-09 | Enable cloud investigation, especially project logs, metrics, and deployment state, using scoped upstream identities. Cloud write access is an explicit project grant, not an automatic default. |
| F-10 | Prefer direct cloud API calls for initial integration. Use skills to explain endpoints and workflows; do not rely on skills to protect credentials. |
| F-11 | Use Agent Vault's documented OAuth refresh support where applicable. Validate the actual provider, scopes, audience, expiry, and revocation behavior. |
| F-12 | Provide private operator administration, persistent gateway state, and useful operational records that redact credentials. |
| F-13 | Define a reproducible bootstrap path: either prepared worker images or gateway-first provisioning. |

## 3. Security requirements

| ID | Requirement |
| --- | --- |
| S-01 | Enforce worker egress outside the worker VM. Worker root access must not permit changing the authoritative controls. |
| S-02 | Block direct internet connections and alternate bypass paths, including IPv6, unauthorized DNS, UDP/QUIC, and generic tunnels. Permit only specified gateway and operational endpoints. |
| S-03 | Keep upstream secrets outside worker files, environment variables, processes, images, and agent conversations. Gateway access capabilities are scoped exceptions: they must not reveal upstream secrets or grant administration. |
| S-04 | Keep Agent Vault administration, its credential store, infrastructure credentials, and external network configuration inaccessible to agents. Restrict worker cloud identity so it cannot alter these controls. |
| S-05 | Bind credential injection to the intended destinations and project scopes. Restrict repository permissions and cloud IAM independently of gateway URL matching. |
| S-06 | Prevent bypass through redirects, destination confusion, DNS rebinding, metadata endpoints, and unintended private-network access. Required private project services receive explicit exceptions. |
| S-07 | Gateway unavailability or failed authentication must not enable direct fallback access. |
| S-08 | Avoid credential exposure through upstream responses and logs. Deny or specifically mediate secret-returning operations; evaluate response exposure in integration tests. |
| S-09 | Define the permitted model provider and account. Provider-hosted tools and remote services are external capabilities too and must not silently bypass the agreed policy. |
| S-10 | Protect the worker-to-gateway transport and project identity. Do not assume upstream HTTPS alone protects proxy authentication on the first hop. |

These are target requirements, not claims that an unmodified Agent Vault deployment already satisfies every item.

## 4. Accepted tradeoffs

- Broad web research and access to private project data leave a residual exfiltration risk. GET paths, queries, headers, and repeated small requests can carry data. The operator accepts this risk; complete data-loss prevention is not a v1 promise.
- A worker can exhaust its VM's memory, CPU, or disk and interrupt sibling agents. Recreating the worker is an acceptable recovery approach. Continuous worker responsiveness is not guaranteed.
- Cooperating agents within a project are not mutually isolated security tenants.
- Upstream credentials are hidden, but the agent can still exercise the authority those credentials confer. External blast radius follows granted repository/cloud permissions, not merely the VM boundary.
- Approved model providers receive task context. This is an intended information flow, not an implicit claim of local-only processing.
- Proxy-scoped session tokens may be present on the worker. They are still capabilities and require limited scope, lifetime, and revocation.

## 5. Deferred scope

- Per-agent resource quotas, scheduling, Kubernetes, and multi-tenant agent isolation.
- A custom proxy/TLS implementation or mandatory custom mitmproxy addon.
- Complete compatibility with authenticated AWS/Azure CLIs.
- AWS SigV4 signing and unverified Azure service-principal/managed-identity token acquisition.
- Custom leakage heuristics: request-size rules, rolling byte budgets, content detection, anomaly alerts. These are optional later mitigations, distinct from VM resource quotas.
- Non-HTTP protocols such as SSH and direct database connections.
- A separate public-research agent or environment.

## 6. First-milestone acceptance criteria

All criteria below remain untested.

| ID | Demonstration |
| --- | --- |
| A-01 | Deploy and recreate the environment from IaC and documented configuration without storing live secrets in the public repository or exposing them in outputs. |
| A-02 | A worker with elevated local privileges cannot reach a controlled external test endpoint directly, with proxy variables removed, via IPv4/IPv6, or using unauthorized DNS/UDP. |
| A-03 | An agent can search/fetch public information, clone the selected project repository, run tests, and complete the chosen branch/PR workflow through the gateway. |
| A-04 | An authenticated project API succeeds, while a controlled canary credential is absent from worker-visible files, environment, tool output, and returned proxy diagnostics. |
| A-05 | Requests outside configured grants are rejected; redirects and host/path variations cannot cause credential injection into a different destination. |
| A-06 | Worker attempts to reach gateway administration, cloud metadata credentials, and network-control APIs fail. |
| A-07 | Stopping the gateway causes outbound requests to fail without a direct-access fallback. |
| A-08 | Multiple agents can cooperate and run builds on the same VM without newly imposed per-agent resource quotas. |
| A-09 | If OAuth is part of the chosen first integration, a token refresh succeeds without exposing access/refresh tokens; revocation or refresh failure produces a clear authentication failure. |
| A-10 | Query project cloud logs through the selected API integration, with unauthorized project/resource access rejected by gateway policy and/or upstream IAM. |

## 7. Open choices

- Azure region, VM sizing, OS image, and deployment/tool versions. Azure and Bicep are selected; future AWS tooling remains undecided.
- Private administrative access and worker-to-gateway transport.
- Initial repository provider, model authentication mode, and cloud-log API.
- Exact Agent Vault version and supported feature set.
- Broad browsing versus strict allowlisting; whether denylist requirements need an additional component.
- Gateway persistence/backup mechanism and worker artifact recovery.
- Bootstrap ordering and image/tool version management.

See [architecture](docs/architecture.md) for the design and [ADRs](docs/adr.md) for accepted decisions.
