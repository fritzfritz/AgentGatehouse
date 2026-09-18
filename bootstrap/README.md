# Guest bootstrap

Initial implementation; live VM integration remains unverified. See the [Azure deployment guide](../docs/deployment-azure.md).

- [gateway.sh](gateway.sh): install packages, initialize an empty dedicated data disk, and run digest-pinned Agent Vault plus TLS transport. Called by gateway cloud-init.
- [admin.py](admin.py): gateway-local hidden credential entry and unmatched-host policy updates. Other administration uses Agent Vault's CLI.
- [export-session.py](export-session.py): authenticate the operator on the gateway, mint a proxy-only session, and export only that capability and public certificates.
- [worker.py](worker.py): accept the bundle from a hidden paste prompt, install CA/proxy configuration and start the loopback relay. Also used for renewal.
- [tls-relay.py](tls-relay.py): forward opaque proxy bytes to the gateway through verified TLS. It does not authorize HTTP requests or inject credentials.
- [install-tools.sh](install-tools.sh): install development packages and operator-pinned Node/Codex/Claude versions through the proxy.

Cloud-init installs worker scripts without downloading anything. A browser-terminal handoff activates proxy access before package installation. There is no temporary direct internet exception. Cloud-init runs once; updating Bicep custom data does not reconfigure an existing guest automatically.

Never put upstream credentials or the CA private key on the worker, even temporarily. Secret provisioning and gateway administration use the operator's protected path. Setup must not rely on a temporary unrestricted worker internet connection.

The worker's proxy capability is intentionally available to cooperating project agents and expires. Azure disk mounting is currently handled by `gateway.sh`; separate that provider-specific logic if an AWS implementation is added.

See [requirements F-03, F-05, and F-13](../requirements.md) and the [runtime architecture](../docs/architecture.md#6-runtime-view).
