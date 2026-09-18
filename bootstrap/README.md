# Guest bootstrap

Status: structure only; no setup scripts are implemented.

This directory will hold reusable Linux guest setup for the worker and Agent Vault gateway. Share scripts between cloud implementations only where the actual behavior is common; keep provider-specific network and identity provisioning under `infra/`.

Planned responsibilities:

- Worker: install development tools and agent runtimes, configure proxy settings, and trust the public gateway CA certificate.
- Gateway: install a pinned Agent Vault version and configure service startup and protected persistent storage.
- Bootstrap sequencing: prepare images or make the gateway available before worker installation needs external access.

Never put upstream credentials or the CA private key on the worker, even temporarily. Secret provisioning and gateway administration use the operator's protected path. Setup must not rely on a temporary unrestricted worker internet connection.

See [requirements F-03, F-05, and F-13](../requirements.md) and the [runtime architecture](../docs/architecture.md#6-runtime-view).
