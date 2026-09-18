# Agent Gatehouse architecture

Status: initial Azure implementation with local checks; not deployed or validated against live Azure/Agent Vault. Recorded 2026-09-18. Operational details: [deployment guide](deployment-azure.md).

Based on the user-supplied arc42 Template Version 9.0-EN, July 2025, maintained by Dr. Peter Hruschka, Dr. Gernot Starke, and contributors. See [arc42](https://arc42.org). The supplied template's 12 top-level sections are retained below; empty template examples have been replaced with project-specific content.

## 1. Introduction and Goals

### Requirements Overview

Agent Gatehouse provisions a powerful project VM for coding agents and a separate Agent Vault gateway for mediated external access. Agents develop features, investigate bugs, research the web, and query project cloud services. See [requirements](../requirements.md) for the authoritative scope and IDs.

### Quality Goals

| Priority | Goal | Meaning |
| --- | --- | --- |
| 1 | External enforcement | Worker-controlled software cannot bypass egress policy or obtain gateway administration. |
| 2 | Credential separation | Upstream credentials remain outside the worker; permitted operations still work. |
| 3 | Agent usefulness | Preserve normal coding, research, and parallel collaboration. |
| 4 | Simplicity | Reuse Agent Vault; start with one worker VM and one gateway, without per-agent quotas. |
| 5 | Reproducibility | Recreate infrastructure and configuration with IaC and documented secret provisioning. |

### Stakeholders

| Role | Expectations |
| --- | --- |
| Project owner/operator | Choose project authority, administer secrets privately, recreate environments. |
| Developers | Delegate useful work and review resulting changes. |
| Coding agents/orchestrator | Broad local tools, clear permitted services, actionable failures. |
| Infrastructure/security maintainers | Understand trust boundaries, audit decisions, verify controls. |

## 2. Architecture Constraints

- Linux project VM, targeting 64 GB RAM or more and multiple CPU cores.
- One project trust domain; cooperating agents may share data and resources.
- No initial per-agent CPU/RAM quotas or mandatory resource scheduler.
- Agent Vault is the selected gateway basis; its documented preview status and pinned-version behavior require evaluation.
- External network enforcement and gateway administration are outside worker authority, including worker cloud IAM.
- Initial application traffic is HTTP(S). AWS signing and full cloud CLI compatibility are deferred.
- Public repository: no live credentials or sensitive deployment state in source control.
- Azure with Bicep is selected. Bastion Developer provides browser-only administration. Only the gateway has a public IP, with unsolicited internet ingress denied; no NAT Gateway is provisioned. Exact deployment versions are operator-selected pins. Future AWS infrastructure will be independently implemented.

## 3. Context and Scope

### Business Context

| External participant | Interaction |
| --- | --- |
| Operator | Provisions infrastructure, grants project capabilities, registers credentials, handles recovery. |
| GitHub/GitLab | Project source, branches, issues, and pull/merge requests. |
| Cloud APIs | Logs, metrics, deployment inspection, and explicitly granted development changes. |
| Public web/search services | Public research; residual outward-data leakage is accepted. |
| Model provider | Approved inference service receiving agent task context. |

Agent Gatehouse does not implement a new coding model, require a custom agent loop, or promise complete data-loss prevention.

### Technical Context

Worker tools send HTTP(S) requests through an explicit proxy. TLS interception enables authentication-header injection for compatible clients. Tools must trust the public gateway CA; its private key stays on the gateway. Client-specific trust/proxy behavior needs testing. Certificate-pinned clients may require dedicated integration; they must not gain unrestricted passthrough as an accidental workaround.

External firewall/routing controls prohibit direct worker egress. DNS, IPv6, metadata endpoints, and operational exceptions form part of that design. A private operator channel provides management without exposing gateway administration to the worker. Exact networking depends on the selected provider.

## 4. Solution Strategy

Implement Azure-specific infrastructure in `infra/azure/` using Bicep. Keep reusable guest setup in `bootstrap/` and behavioral acceptance checks in `tests/acceptance/`. Add an independent `infra/aws/` implementation only when needed; shared requirements do not require shared resource definitions. See [ADR-007](adr.md#adr-007-azure-first-with-bicep-and-independent-provider-implementations).

Use the worker VM as the disposable local blast-radius boundary. Containers organize development tools and workspaces; they are not initially independent security tenants.

Use Agent Vault for credential storage/brokering, service matching, and supported OAuth refresh. Enforce upstream permissions with repository scopes and cloud IAM. Combine these with external egress restrictions so changing worker configuration cannot expand authority.

Prefer Agent Vault configuration over a new proxy implementation. Do not assume its service matcher provides method/body authorization or that its request-rate controls implement byte budgets. Those are potential later extensions.

Retain broad web research and explicitly accept residual leakage risk. No separate research agent is required for v1. See [ADRs 001–005](adr.md).

## 5. Building Block View

### Whitebox Overall System

```mermaid
flowchart LR
    subgraph Untrusted[Worker VM — project trust domain]
        O[Codex / Claude orchestrator]
        W[Cooperating workers and development tools]
        O <--> W
    end
    Untrusted --> N[External egress enforcement]
    N --> G[Agent Vault proxy]
    G --> E[Approved external services]
    S[Gateway credential storage] --> G
    P[Operator-managed policy] --> G
    Admin[Private operator access] --> P
```

| Block | Responsibility and interface | Requirements |
| --- | --- | --- |
| Worker VM | Runs agents, tools, containers, workspaces; proxy-only external application access. | F-02–F-05 |
| External network controls | Restrict routes/connections independently of worker root; close direct bypass paths. | S-01, S-02, S-06, S-07 |
| Agent Vault | Authenticate proxy sessions, match service routes, resolve/inject credentials, perform supported OAuth refresh. | F-08, F-11, S-03, S-05 |
| Operator configuration | Define project scope, provision secrets, configure private management and persistence. | F-01, F-12, S-04 |
| IaC/bootstrap | Recreate infrastructure and install/configure the worker and gateway. | F-01, F-13 |

### Level 2: Gateway responsibilities

The agent uses a project-scoped proxy session. Agent Vault resolves service rules and attaches the selected upstream authentication. Secrets and supported OAuth refresh state reside in protected gateway storage. Operator access is distinct from proxy-only agent access.

Agent Vault's documented service matcher uses host, port, and path; it does not inspect method/query/body to authorize an operation. Its unmatched-host policy defaults to forwarding unless configured otherwise. A strict allowlist can use deny-on-unmatched. Broad browsing with explicit blacklisting remains an integration question, not an established built-in capability.

The documented forward-proxy transport can expose proxy authentication in cleartext on the first hop. The implementation uses a worker loopback byte relay through verified TLS to stunnel on gateway private port 14443, which forwards only to Agent Vault's loopback proxy. The management API remains loopback-only. The relay adds transport encryption without custom HTTP authorization or credential injection. See [Agent Vault security](https://docs.agent-vault.dev/learn/security).

### Level 3

The [bootstrap directory](../bootstrap/README.md) contains a minimal TLS byte relay, session import/export and gateway-local administration helpers. These bridge browser-only provisioning and Agent Vault's APIs; they do not replace Agent Vault's HTTP policy or cryptography. Exact version compatibility is still unverified live.

## 6. Runtime View

### Provision and bootstrap

1. Operator provisions the network boundary, gateway, and worker using IaC.
2. Gateway cloud-init initializes protected storage and starts Agent Vault. The operator registers/logs in and configures rules through its CLI in Bastion Developer's browser terminal.
3. Operator mints a proxy-only scoped session on the gateway and transfers only the session and public certificates via the Bastion clipboard to the worker's hidden input prompt.
4. Worker installs proxy/CA configuration, starts its TLS relay, then installs tools through the gateway. No upstream or deployment credentials are handed off.
5. Boundary tests run before accepting the environment for normal work.

Bootstrap must never temporarily grant unrestricted internet access as an undocumented dependency.

### Authenticated project request

1. Agent constructs a request using ordinary tools and, if useful, a workflow skill.
2. External controls permit access only through the designated gateway path.
3. Gateway authenticates the project session and checks the configured service match.
4. Gateway resolves credentials and injects authentication for that service.
5. Upstream authorization independently enforces repository/cloud scope.
6. Response returns to the worker. Secret-returning endpoints and reflected credentials require prevention or explicit mediation; injection alone is insufficient.

### OAuth refresh

Operator completes a supported OAuth authorization flow. Agent Vault stores tokens and expiry and documents automatic refresh near expiry before injection. A provider refusal, revoked grant, or failed refresh must produce an authentication failure, not a fallback to worker-held credentials. Azure delegated OAuth needs scope/audience validation; other Azure identity flows are not yet established.

### Public research and failures

Public requests pass through the selected browsing policy without project credential injection. URLs and queries may carry private data: this residual risk is accepted. Denied requests should explain the policy reason without revealing secrets. If the gateway is unavailable, external work fails; local coding and tests may continue.

## 7. Deployment View

### Infrastructure Level 1

Initial implementation: one project worker VM and a separate gateway VM, in two subnets of `10.82.0.0/16`. The gateway has a Standard public IP for outbound access; NSGs deny internet-initiated inbound connections. The worker has no public IP/default outbound access and allows new outbound application connections only to gateway private port 14443. Bastion Developer provides browser administration without a dedicated Bastion subnet/public IP. No NAT Gateway exists.

| Infrastructure | Contents | Authority |
| --- | --- | --- |
| Worker VM | Agent runtimes, Docker/development images, workspaces, proxy client configuration | Broad local project freedom; no infrastructure/gateway administration |
| Gateway host | Agent Vault, protected credential/state storage, public-web/upstream connections | Operator-managed; agent access limited to necessary proxy/session endpoints |
| Network boundary | Firewall/routing and explicit operational exceptions | Operator/IaC only, inaccessible through worker IAM |
| Protected deployment metadata | Azure deployment history, parameters, and any sensitive deployment artifacts; no separate Bicep state backend | Operator-controlled, never public Git |

### Infrastructure Level 2

The [Bicep implementation](../infra/azure/main.bicep) defines worker `10.82.1.4` and gateway `10.82.2.4`, explicit inbound/outbound rules, platform DNS/IMDS denies for the worker, and no managed identities. The gateway's private TLS port accepts only the worker source IP. Its management API and raw proxy bind to loopback. Bastion SSH is scoped to Developer's platform source `168.63.129.16/32`; confirm regional behavior live. Azure WireServer has platform exceptions to ordinary NSG filtering; no claim of absolute platform-network isolation is made.

The default worker is D16s_v5 with 256 GiB OS storage; the gateway is B2ms with 64 GiB OS storage and a separate 32 GiB state disk. Gateway disk state includes protected master/transport keys and Agent Vault data. Bastion Developer means one browser VM connection at a time and no local SSH tunnels or SCP. See the [runbook](deployment-azure.md) for identity prerequisites, setup, costs and acceptance.

Gateway persistence and backup are required operational concerns; worker recovery may recreate the VM. Define where unfinished work is saved before destructive recovery. There is no initial high-availability commitment or per-agent resource isolation.

## 8. Cross-cutting Concepts

### Identity and capability scope

A proxy session is a capability, not an upstream secret. Scope it to the project, keep its lifetime appropriate, and support revocation. Use the least upstream authority that enables the chosen workflow. Agent Vault proxy roles must not read stored credentials or manage policy.

### Agent freedom and policy ownership

Agents can run code, coordinate, and organize containers. They cannot expand external authority. Repository instructions and skills guide behavior but are not enforcement. Gateway configuration must not be loaded from a worker-writable volume.

### Secrets and observability

Protect secrets in bootstrap, IaC state, gateway backups, debug traces, and API responses as well as environment variables. Record useful request decisions and transfer metadata with redaction. Raw URLs, headers, and bodies can themselves contain sensitive data; avoid indiscriminate capture.

### Resource model

Share the worker's CPU/RAM/disk. Accept local contention and exhaustion. Keep the gateway separate so worker overload does not directly consume gateway resources. No custom resource scheduler is required. Future network-volume heuristics are independent of CPU/RAM quotas.

### Cloud authentication

Agent Vault supports static headers and documented OAuth refresh-token flows. Direct APIs reduce CLI integration work but do not remove authentication requirements. AWS SigV4 is request-dependent signing, not static header injection. Azure token audience and grant type must match the selected API. A skill cannot replace these trusted mechanisms.

## 9. Architecture Decisions

The [ADR document](adr.md) records decisions and consequences:

- ADR-001: Project VM as the local boundary; external enforcement.
- ADR-002: Agent Vault as the initial gateway.
- ADR-003: Shared worker resources without per-agent quotas.
- ADR-004: Broad research with accepted residual leakage risk.
- ADR-005: Direct cloud APIs first; trusted authentication.
- ADR-006: Arc42 architecture plus a separate ADR history.
- ADR-007: Azure first with Bicep and independent provider implementations.
- ADR-008: Feature branches and pull requests; no direct commits to main.
- ADR-009: Bastion Developer and browser-terminal administration.
- ADR-010: Gateway public IP plus NSG, without NAT Gateway.

An accepted ADR records intent, not successful implementation. Supersede records when decisions change.

## 10. Quality Requirements

### Quality Requirements Overview

Prioritize enforceable boundaries, credential separation, useful workflows, and simplicity. Worker availability under overload and complete data confidentiality during broad browsing are explicitly excluded guarantees.

### Quality Scenarios

| Scenario | Expected response | Acceptance evidence |
| --- | --- | --- |
| Worker removes proxy configuration and attempts direct egress | External controls reject the connection | A-02 |
| Agent calls a permitted authenticated API | Request succeeds without upstream secret exposure | A-04 |
| Agent changes destination/path or follows a redirect | No out-of-scope credential injection | A-05 |
| Worker probes control/metadata endpoints | Access rejected | A-06 |
| Gateway stops | Outbound access fails closed | A-07 |
| Agents work concurrently | Shared resources usable without added per-agent quotas | A-08 |
| OAuth token nears expiry | Gateway refreshes or returns authentication failure | A-09 |
| Agent investigates a cloud issue | Scoped log queries work; other scopes are denied | A-10 |

Local test coverage and commands are described in [acceptance checks](../tests/acceptance/README.md). No live Azure measurements or acceptance results exist yet. See [requirements](../requirements.md) for the complete milestone criteria.

## 11. Risks and Technical Debts

| Risk/open item | Treatment |
| --- | --- |
| Agent Vault preview and version drift | Pin a version and verify capabilities; do not treat this research as an audit. |
| Broad browsing plus private context enables leakage | Accepted; optional later heuristics reduce but cannot eliminate it. |
| Blacklist/browsing policy mismatch | Verify actual support before promising a denylist; add a component only if needed. |
| Worker root reaches infrastructure control APIs | Scope IAM and enforce externally; include adversarial tests. |
| Allowed API returns secrets or allows harmful changes | Restrict upstream authority and sensitive operations; test response exposure. |
| Proxy session interception or replay | Protect first-hop transport, scope sessions, and revoke them. |
| Tool incompatibility with proxy/CA | Test actual tools; do not open unrestricted bypasses. |
| Gateway compromise | Gateway is trusted and holds secrets; minimize exposure and protect management/state. |
| Worker resource exhaustion/data loss | Accepted interruption risk; define artifact persistence and recovery. |
| Cloud identity/signing integration gaps | Validate Azure flow; defer AWS signing unless brought into scope. |
| Provider-hosted tools bypass local inspection | Explicitly decide which remote capabilities are allowed. |
| Bastion Developer limits and shared platform path | Verify region and source rules; browser-only, one connection at a time; no native-client assumptions. |
| Clipboard session handoff | Copy only the scoped capability/public certificates, clear clipboard, never export operator tokens. |
| Bootstrap/API compatibility | Compile/static tests are insufficient; validate image provisioning, selected Agent Vault API and service readiness live. |

### Primary references

Reviewed in the concept discussion on 2026-09-18; compatibility has not been tested:

- [Agent Vault project and preview status](https://github.com/Infisical/agent-vault)
- [Service matching and authentication](https://docs.agent-vault.dev/learn/services)
- [OAuth credential refresh](https://docs.agent-vault.dev/learn/credentials)
- [Security, roles, network guards, and transport](https://docs.agent-vault.dev/learn/security)

## 12. Glossary

| Term | Definition |
| --- | --- |
| Worker VM | Resource-rich, disposable machine where project agents and tools run. |
| Gateway | External Agent Vault deployment mediating HTTP(S) access and injecting credentials. |
| Capability | Granted authority to perform a defined class of external operations. |
| Upstream credential | Authentication material accepted by the destination service. |
| Proxy session | Scoped authority to use the gateway, without permission to reveal upstream credentials. |
| External enforcement | Controls the worker cannot change, even with local root. |
| OAuth refresh | Exchanging a refresh token for a new access token without exposing either to the worker. |
| SigV4 | AWS request-signing mechanism computed over request-specific information. |
| ADR | Architecture Decision Record: context, decision, alternatives, and consequences. |
