# Azure infrastructure

Status: structure only; Bicep templates are not implemented and nothing has been deployed.

This directory will contain Azure-specific infrastructure for the project worker VM, separate Agent Vault gateway, external network enforcement, and private administration. See [ADR-007](../../docs/adr.md#adr-007-azure-first-with-bicep-and-independent-provider-implementations) and [requirement F-01](../../requirements.md).

Add Bicep entry points, modules, and clearly marked example parameters as the deployment design becomes concrete. Do not add empty deployment templates that could be mistaken for a working environment.

Before deployment implementation, decide the Azure region, VM images/sizes, network and DNS rules, gateway egress, management access, protected proxy transport, and bootstrap ordering. Upstream runtime secrets must not be embedded in templates or worker bootstrap data. Protect deployment parameters, history, and outputs even though Bicep does not require a separate IaC state backend.

Reusable guest setup belongs in [bootstrap/](../../bootstrap/README.md). Validate observable behavior against [acceptance criteria](../../tests/acceptance/README.md). Keep Azure networking and identity explicit; no shared Azure/AWS resource abstraction is required.
