# Instructions for agents working on Agent Gatehouse

## Project intent

Read [requirements.md](requirements.md), [docs/architecture.md](docs/architecture.md), and [docs/adr.md](docs/adr.md) before implementation. This project gives agents broad local freedom while enforcing external authority outside the worker VM.

This repository contains an initial Azure implementation with local checks; live deployment and integrations remain unverified. Do not describe infrastructure or integrations as deployed, tested, or secure until supported by evidence. Follow [docs/deployment-azure.md](docs/deployment-azure.md) for the current operational workflow.

## Architectural constraints

- Use a project worker VM and a separate Agent Vault gateway as the initial architecture.
- Enforce egress outside the worker VM. Proxy environment variables and worker-local firewall rules are configuration/defense in depth, not the security boundary.
- Keep upstream credentials, CA private keys, gateway administration, and infrastructure-control credentials outside the worker.
- Treat scoped proxy session tokens as capabilities. Give agents proxy-only access; never grant credential-reading or administrative roles to simplify setup.
- Use narrowly scoped upstream repository/cloud identities. A gateway cannot compensate for unrestricted cloud authority.
- Preserve broad local tool use and cooperation. Do not introduce per-agent CPU/RAM quotas, Kubernetes, mandatory gVisor, or an orchestration framework without a new requirement or decision.
- Public web leakage risk is accepted. Do not repeatedly block progress on that accepted tradeoff or claim that URL filtering eliminates it.
- Prefer existing Agent Vault features over custom proxy code. Verify pinned-version behavior before adding a workaround.
- Skills may guide API use. They must not retrieve upstream secrets into the worker or be treated as enforcement.
- Use Bastion Developer for browser-only administration. Do not add paid Bastion, a NAT Gateway, public SSH, SCP/port-forwarding dependencies, or a jump host without a new decision. Only the gateway VM has a public IP, for outbound access; its NSG denies unsolicited internet ingress.

## Implementation approach

Start with the smallest end-to-end deployment proving useful work, credential separation, and unavoidable gateway use. Implement Azure first using Bicep under `infra/azure/`. A future AWS implementation may use different tooling under `infra/aws/`; do not introduce a cross-cloud abstraction layer. Share bootstrap scripts and acceptance criteria where practical, while keeping network and identity configuration provider-specific.

Prefer direct HTTP APIs for initial cloud integrations. Agent Vault documents refresh-token-based OAuth support; do not generalize this to every Azure identity flow or to AWS SigV4 signing. Record compatibility evidence and remaining gaps.

Use a private management path. Ensure worker cloud permissions cannot change external firewall rules, gateway resources, or secret storage. Do not mount gateway secrets onto the worker, even temporarily during bootstrap.

Pin deployment dependencies and images appropriately. Keep gateway administrative configuration outside agent-editable project mounts. Explain blocked requests without disclosing credentials.

## Public repository and secrets

This is a public repository. Commit only examples and secret references, never live tokens, client secrets, certificates' private keys, credential databases, sensitive logs, or IaC state. Mark sample values unambiguously.

Consider IaC state, plans, crash logs, and CI artifacts as potential secret carriers. Avoid printing or committing them. Use appropriate protected state storage when IaC is implemented.

Preserve user changes. Never push, deploy cloud resources, create billable infrastructure, or change external access simply because a documentation or review task mentions them; follow the user's actual authorization.

## Documentation workflow

Create a feature branch before making changes. Never commit directly to `main`; integrate changes through pull requests. Do not merge without user authorization. Branch creation does not imply authorization to push, deploy, or change repository protection settings.

- `readme.md`: concise human introduction and accurate current status.
- `requirements.md`: scope, stable requirement IDs, accepted risks, and acceptance criteria.
- `docs/architecture.md`: living architecture following the 12 arc42 top-level sections.
- `docs/adr.md`: numbered records of significant architectural decisions, using context, decision, alternatives, and consequences.

Update the relevant documents when behavior or scope changes. Separate agreed decisions, proposals, and tested facts. Keep accepted ADRs as history; supersede them with a new record when a decision changes. Link architecture decisions rather than maintaining conflicting copies.

Use primary project/vendor documentation for third-party claims. Cite the exact page and record material uncertainty. No newsletter-specific structure or publishing workflow applies to this repository.

## Validation and handoff

Test security boundaries as well as successful workflows. Prioritize direct-egress bypass, credential injection scope, redirects, proxy failure, administrative isolation, and the selected Git/model/cloud integrations. Use controlled endpoints and synthetic canary secrets for leakage tests.

Do not run resource-exhaustion tests on shared or important systems without task-specific authorization. The accepted absence of quotas is not permission to disrupt environments.

For documentation-only changes, check internal links, consistency, and status claims. For implementation, run checks proportional to the change and report what actually passed, what was not tested, and any unresolved requirement.
