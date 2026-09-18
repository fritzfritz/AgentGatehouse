# Architecture decision records

This document records Agent Gatehouse's significant architectural decisions. The [arc42 architecture](architecture.md) describes the current design; [requirements](../requirements.md) define scope and acceptance.

All records below capture decisions agreed during the initial discussion on 2026-09-18. Accepted means agreed, not implemented or validated.

## Index

| Record | Decision | Status |
| --- | --- | --- |
| [ADR-001](#adr-001-project-vm-with-external-enforcement) | Project VM with external enforcement | Accepted |
| [ADR-002](#adr-002-use-agent-vault-as-the-initial-gateway) | Use Agent Vault as the initial gateway | Accepted |
| [ADR-003](#adr-003-share-worker-resources-without-per-agent-quotas) | Share worker resources without per-agent quotas | Accepted |
| [ADR-004](#adr-004-allow-broad-research-and-accept-residual-leakage-risk) | Allow broad research and accept residual leakage risk | Accepted |
| [ADR-005](#adr-005-prefer-cloud-apis-and-keep-authentication-trusted) | Prefer cloud APIs and keep authentication trusted | Accepted |
| [ADR-006](#adr-006-maintain-arc42-and-a-separate-decision-history) | Maintain arc42 and a separate decision history | Accepted |
| [ADR-007](#adr-007-azure-first-with-bicep-and-independent-provider-implementations) | Azure first with Bicep and independent provider implementations | Accepted |
| [ADR-008](#adr-008-use-feature-branches-and-pull-requests) | Use feature branches and pull requests | Accepted |
| [ADR-009](#adr-009-use-bastion-developer-for-browser-administration) | Use Bastion Developer for browser administration | Accepted |
| [ADR-010](#adr-010-gateway-public-ip-with-inbound-deny-nsg) | Gateway public IP with inbound-deny NSG | Accepted |

## ADR-001: Project VM with external enforcement

Date: 2026-09-18. Status: Accepted.

### Context

Coding agents need broad tools and parallel collaboration for one project's repositories and cloud environment. Security must not depend on agent obedience. The operator accepts the worker VM as the local blast radius.

### Decision

Use one project worker VM and a separate trusted gateway. Enforce egress through infrastructure outside the worker's control. Keep upstream credentials, gateway administration, and authority to modify network controls outside the worker. Containers provide development environments; v1 does not require mutual agent isolation.

### Alternatives considered

- Agent instructions or tool approvals alone: insufficient as an external enforcement boundary.
- Worker-local proxy/firewall only: root on the worker could bypass it.
- A strong sandbox per agent: potentially useful later, but beyond the initial project trust model.

### Consequences

Agents retain local freedom, including the ability to disrupt their own project VM. Worker cloud identity cannot grant infrastructure administration. External effects remain bounded by repository/cloud permissions, so the VM alone is not the entire blast radius. Direct bypass and management isolation require testing.

## ADR-002: Use Agent Vault as the initial gateway

Date: 2026-09-18. Status: Accepted.

### Context

The essential gateway requirements are mediated HTTP(S) access, hidden upstream credentials, and project scope. A custom mitmproxy addon was explored, but simplicity and reuse take precedence over speculative customization.

### Decision

Start with [Infisical Agent Vault](https://github.com/Infisical/agent-vault) outside the worker VM. Use its service configuration, credential injection, scoped proxy access, and supported OAuth refresh. Scope upstream credentials independently. Choose deployment version and browsing policy during implementation.

### Alternatives considered

- mitmproxy plus custom policy/injection code: flexible but creates security-sensitive code and maintenance before a demonstrated need.
- Envoy/OPA and a credential broker: useful for richer policy, but more components than the initial scope needs.
- Full sandbox/orchestration platforms: broader than the selected VM-and-gateway starting point.

### Consequences

Agent Vault's preview status requires validation. Host/port/path matching does not establish method/body authorization, arbitrary denylist support, or byte-budget heuristics. Missing features may justify a later extension or superseding decision, not immediate custom implementation. External network enforcement remains required.

## ADR-003: Share worker resources without per-agent quotas

Date: 2026-09-18. Status: Accepted.

### Context

The worker should provide abundant RAM and CPU for parallel agents. Introducing quota management or scheduling would complicate the initial design.

### Decision

Target a resource-rich VM, initially 64 GB RAM or more and multiple cores. Let project agents share available resources without new per-agent CPU/RAM quotas. Let the agent orchestrator decide how to parallelize work. Keep the gateway on separate infrastructure.

### Alternatives considered

- Fixed quotas for each container/agent: rejected for v1.
- Kubernetes or a custom scheduling service: unnecessary initial complexity.

### Consequences

Runaway workloads can interrupt sibling agents or render the worker unresponsive. Restart/recreation is acceptable; artifact recovery must be defined. This decision does not waive provider limits or forbid future gateway-side network-abuse controls. Revisit if observed contention prevents useful work.

## ADR-004: Allow broad research and accept residual leakage risk

Date: 2026-09-18. Status: Accepted.

### Context

Useful development needs public search and browsing alongside private code and logs. An allowed GET request or search query can encode private data; destination restrictions cannot guarantee confidentiality.

### Decision

Retain broad research through the gateway and explicitly accept residual data-leakage risk. Keep credential separation and externally enforced authority as core requirements. Do not require a separate research agent for v1. Consider content/volume heuristics later.

### Alternatives considered

- Offline or fully curated research: stronger confidentiality but inconsistent with desired usefulness.
- A separate researcher with approved outward information releases: a possible future stronger mode, with additional complexity.
- Claiming URL allowlists prevent leakage: technically unsound.

### Consequences

Documentation must not promise complete data-loss prevention. Future byte budgets must distinguish browsing from legitimate large Git, deployment, or model traffic. Exact broad-web/blacklist behavior must be validated for the selected gateway implementation.

## ADR-005: Prefer cloud APIs and keep authentication trusted

Date: 2026-09-18. Status: Accepted.

### Context

AWS/Azure CLI authentication can complicate keeping secrets outside a worker. Agents can construct API requests and handle pagination, polling, and retries with guidance from skills. Earlier discussion understated Agent Vault's OAuth refresh support; its credential documentation establishes refresh-token-based support.

### Decision

Prefer direct HTTP APIs initially. Let skills explain API workflows while trusted software obtains, refreshes, or signs authentication. Use Agent Vault's built-in OAuth refresh where the selected provider flow works. Validate Azure delegated OAuth; treat service-principal/managed-identity acquisition and AWS SigV4 signing as separate, unimplemented integrations.

### Alternatives considered

- Let the agent obtain tokens or sign with real keys: conflicts with credential separation.
- Require complete AWS/Azure CLI support in v1: unnecessary starting complexity.
- Build a refresh helper immediately: premature for supported OAuth flows.

### Consequences

Agents do more API-level work, but no less reasoning is available to them. Authentication complexity remains trusted infrastructure work. Cloud permissions must restrict resource scope and secret-returning operations. Validate token audience, scopes, refresh, expiry, and revocation for the actual service.

Reference: [Agent Vault OAuth credentials](https://docs.agent-vault.dev/learn/credentials).

## ADR-006: Maintain arc42 and a separate decision history

Date: 2026-09-18. Status: Accepted.

### Context

The repository needs both a current architectural description and a durable explanation of why decisions were made. The owner supplied the arc42 English GitHub Markdown template.

### Decision

Use `docs/architecture.md` with the template's 12 top-level arc42 sections and `docs/adr.md` as a numbered decision log. Keep human introduction in `readme.md`, requirements in `requirements.md`, and agent guidance in `AGENTS.md`.

### Alternatives considered

- README-only design: insufficient separation of introduction, requirements, and rationale.
- Separate file per ADR: reasonable as the history grows, but a single ADR document is simpler initially.

### Consequences

Update the living architecture as the system changes. Preserve accepted records; document a changed decision in a new ADR and mark the older record superseded. Keep requirement IDs stable and link documents to avoid conflicting sources of truth.

## ADR-007: Azure first with Bicep and independent provider implementations

Date: 2026-09-18. Status: Accepted.

### Context

The owner has access to Azure and AWS and prefers Azure for the first deployment. Infrastructure complexity is low: a worker VM, a gateway, networking, and storage. Separate provider implementations are acceptable; resource portability is not a goal.

### Decision

Use Azure Bicep for the initial deployment under `infra/azure/`. Reserve `infra/aws/` for a future independent implementation, with its tooling chosen when needed. Share requirements, acceptance criteria, and practical Linux bootstrap logic rather than introducing a cross-cloud resource abstraction.

Create `bootstrap/` for guest setup and `tests/acceptance/` for behavioral checks. Initially these directories contain scope notes; templates and executable scripts follow after the Azure network and administrative access design is settled.

### Alternatives considered

- Pulumi Azure Native: viable, but its separate state backend and general-purpose language toolchain are unnecessary for the selected simple Azure deployment.
- Shared Azure/AWS resource abstractions: not required; networking and identity semantics should remain explicit per provider.
- Implement both clouds immediately: unnecessary expansion of the first milestone.

### Consequences

Bicep avoids a separate IaC state backend; Azure deployment parameters, history, and outputs still require appropriate protection. A future AWS deployment duplicates some resource declarations deliberately. Shared acceptance criteria help prevent drift in security behavior. Provider/tool selection is now resolved for Azure; region, sizing, management access, and network details remain open.

Affects requirement F-01 and architecture sections 2, 4, and 7. Reference: [Microsoft Bicep overview](https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/overview).

## ADR-008: Use feature branches and pull requests

Date: 2026-09-18. Status: Accepted.

### Context

Initial project documentation and licensing were committed to `main`. The owner now requires feature branches and no direct commits to `main`.

### Decision

Create feature branches before making changes and integrate through pull requests. Do not commit directly to `main`. Require user authorization before merging; follow the task's scope for commits and pushes.

### Alternatives considered

- Continue direct commits to `main`: rejected by the owner.
- Add a complex branching/release model: unnecessary at this stage.

### Consequences

Agents must check the current branch before edits and commits. This workflow applies from this decision onward and does not rewrite existing history. Repository-side branch protection is not configured by this documentation change; the recorded policy is not a claim of server-side enforcement.

## ADR-009: Use Bastion Developer for browser administration

Date: 2026-09-18. Status: Accepted.

### Context

The operator wants no public SSH and prefers the free Bastion Developer tier over paid native-client access or a public jump host.

### Decision

Deploy Bastion Developer in a supported Azure region. Both VMs accept private SSH from its platform path only. Perform gateway administration with Agent Vault's CLI from the browser terminal; copy a short-lived proxy-session bundle through the Bastion clipboard to the worker's hidden prompt. No upstream credentials or operator session tokens are transferred.

### Alternatives considered

- Bastion Standard: supports native tunneling/file transfer but adds a standing hourly charge.
- Gateway SSH jump host: inexpensive but would expose restricted public SSH, contrary to the selected preference.
- Separate VPN: not required for the initial browser-only workflow.

### Consequences

One VM connection at a time, no local SSH/SCP/VS Code tunneling, and no port-forwarded gateway web UI. Native browser OAuth callback workflows require future integration work; static credential injection can be initialized entirely from the terminal. Developer is a dev/test service; region availability and the platform-source NSG rule need live validation. Clipboard contents include a revocable proxy capability and must be handled accordingly. Affects F-12 and F-14.

Reference: [Bastion SKU comparison](https://learn.microsoft.com/en-us/azure/bastion/bastion-sku-comparison).

## ADR-010: Gateway public IP with inbound-deny NSG

Date: 2026-09-18. Status: Accepted.

### Context

Agent Vault needs internet egress but no public inbound service. A NAT Gateway was initially proposed solely to keep both VM NICs private, adding cost unnecessary for the stated requirement.

### Decision

Attach a Standard static public IPv4 address only to the gateway NIC for outbound connectivity. Use an NSG to deny unsolicited internet ingress, permitting the worker proxy and Bastion management paths privately. Keep the worker without a public IP and with explicit outbound-deny rules. Provision no NAT Gateway.

### Alternatives considered

- NAT Gateway on the gateway subnet: achieves egress without a VM public IP, but adds standing and processing charges.
- Enable public SSH/proxy endpoints: unnecessary and rejected.

### Consequences

The gateway has a publicly routable address but no permitted internet-initiated application connections. Verify this from an independent external host; local service bindings are additional protection, not the external boundary. Stateful response traffic for gateway-initiated connections remains allowed. Saves NAT cost while retaining the public-IP charge. Affects F-15 and architecture section 7.

Reference: [Azure NSG behavior](https://learn.microsoft.com/en-us/azure/virtual-network/network-security-groups-overview).

## Adding a record

Use the next sequential ID, a descriptive title, date, and status (`Proposed`, `Accepted`, `Rejected`, or `Superseded`). Include Context, Decision, Alternatives considered, and Consequences. Link affected requirements and evidence where relevant.
