# Azure infrastructure

Initial Bicep implementation; not yet deployed or validated against live Azure. Read the [deployment guide](../../docs/deployment-azure.md) before provisioning.

| File | Purpose |
| --- | --- |
| [main.bicep](main.bicep) | VNet, two subnets/NSGs, Bastion Developer, gateway public IP, data disk, and two VMs |
| [modules/vm.bicep](modules/vm.bicep) | Linux VM/NIC, SSH key authentication, pinned image version and cloud-init payload |
| [example.bicepparam](example.bicepparam) | Nondeployable placeholders; copy to a gitignored local parameter file |
| [deploy.sh](deploy.sh) | Explicit-subscription validation, what-if and deployment into an existing resource group |
| [validate-parameters.py](validate-parameters.py) | Reject unfilled placeholders and mutable image references |

The worker has no public IP or default outbound access. Its NSG allows new outbound application connections only to the gateway's TLS proxy port. Only the gateway has a public IP; internet-initiated ingress is denied. No NAT Gateway, paid Bastion, or VM managed identities are created.

Bastion Developer provides browser terminals, not native SSH/SCP tunnels. The gateway's management API and raw proxy bind to loopback; a TLS listener exposes only the proxy to the worker's private IP. Exact regional platform behavior remains a live acceptance item. Upstream secrets do not belong in templates or bootstrap data.

Run local compilation and checks as documented in the deployment guide. Do not treat a successful build or ARM validation as proof of the live boundary. See [bootstrap](../../bootstrap/README.md), [acceptance checks](../../tests/acceptance/README.md), and [ADRs](../../docs/adr.md).
