# Deploy Agent Gatehouse on Azure

Status: initial implementation; live Azure deployment and Agent Vault integration are not yet verified. Run the acceptance checks before using real project credentials. Administration uses Bastion **Developer**, and only the gateway VM has a public IP, for outbound connections. Its NSG denies internet-initiated inbound traffic. There is no NAT Gateway.

## Preconditions and deployment user

Use a trusted operator workstation, not the Agent Gatehouse worker. You need:

- An Azure subscription and a pre-created, dedicated resource group. A subscription administrator creates the group and registers `Microsoft.Compute` and `Microsoft.Network` if necessary.
- **Contributor on that resource group** for the deployment identity, or a custom role with equivalent permissions for the template's resources and `Microsoft.Resources/deployments/*`. The template creates no role assignments, so Owner/User Access Administrator is not required for routine deployment. Creating the resource group or assigning Contributor is a separate administrator action.
- Permission under your organization’s Azure policies to create the selected VM sizes, networking and disks, plus regional vCPU quota and capacity. The default worker is `Standard_D16s_v5`; select a size appropriate to your approved budget and region.
- Azure CLI with Bicep, Python 3.10+, OpenSSH, and Docker or another registry inspection tool on the workstation. The Docker tool is only needed to resolve an immutable Agent Vault image digest.
- An SSH key pair dedicated to operator access. Only the public key enters Bicep. Never copy the private key to either VM or enable SSH agent forwarding into the worker.
- A region supporting Bastion Developer, such as West Europe. Developer provides one browser-based VM connection at a time; local SSH, SCP, VS Code Remote SSH, port forwarding and browser access to the gateway web UI are not available through this SKU. Use the CLI/browser-terminal steps below.
- Exact reviewed versions: an Ubuntu 24.04 image version, Agent Vault image digest, Node archive/version/checksum, and Codex/Claude Code package versions. Examples deliberately contain placeholders and cannot be deployed unchanged.

The deployment identity has powerful control over the environment. Never run `az login` as that identity on the worker, store its credentials there, or grant it to an agent. Neither VM receives a managed identity in this implementation. Project cloud API identities are separate and have only their intended project permissions.

The same resource-group Contributor can operate the development environment. If separating deployment from daily operation, grant the operator only the required Bastion/VM/NIC read access plus OS key access, and verify that combination against the [Bastion prerequisites](https://learn.microsoft.com/en-us/azure/bastion/quickstart-host-portal). Do not give project agents either role.

For later CI, use workload identity federation with an explicitly scoped deployment identity. This implementation does not create a CI identity or configure federation.

## Prepare local configuration

Log in interactively on the operator workstation and verify the tenant/subscription before any deployment. All deployment commands below take an explicit subscription ID.

```bash
az login --tenant YOUR_TENANT_ID
az account show --query '{tenant:tenantId,subscription:id,name:name}' -o table
az bicep version

cp infra/azure/example.bicepparam infra/azure/dev.local.bicepparam
```

Edit `dev.local.bicepparam`; it is ignored by Git. The SSH value must be a public key. Choose an exact regional Ubuntu image version:

```bash
az vm image list --subscription YOUR_SUBSCRIPTION_ID --location westeurope \
  --publisher Canonical --offer ubuntu-24_04-lts --sku server --all \
  --query '[].version' -o tsv
```

Select and review an Agent Vault release. Inspect its published image and record the immutable digest:

```bash
docker buildx imagetools inspect infisical/agent-vault:YOUR_REVIEWED_RELEASE
```

Set `agentVaultImage` to `infisical/agent-vault@sha256:...`. Do not use `latest`. The current integration follows Agent Vault's documented proxy/session API; a digest pin alone does not establish compatibility or security. Test the selected release. Ubuntu packages receive current distribution updates during bootstrap; byte-for-byte reproducibility would require a package snapshot or baked image, which is not implemented here.

The network currently uses `10.82.0.0/16`. Check for overlap before linking it to any existing network. No peering is created.

## Validate, review and deploy

First compile and run offline checks:

```bash
az bicep build --file infra/azure/main.bicep --outfile /tmp/agentgatehouse-arm.json
python3 tests/check_arm.py /tmp/agentgatehouse-arm.json
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

The deployment helper rejects unfilled placeholders and unpinned image references. Validation and what-if contact Azure but do not create the template's resources:

```bash
bash infra/azure/deploy.sh validate YOUR_SUBSCRIPTION_ID YOUR_RESOURCE_GROUP infra/azure/dev.local.bicepparam
bash infra/azure/deploy.sh what-if YOUR_SUBSCRIPTION_ID YOUR_RESOURCE_GROUP infra/azure/dev.local.bicepparam
```

Review the resource list, network rules and costs. Then explicitly deploy:

```bash
bash infra/azure/deploy.sh deploy YOUR_SUBSCRIPTION_ID YOUR_RESOURCE_GROUP infra/azure/dev.local.bicepparam
```

Bicep success means resources were provisioned, not that cloud-init or the gateway is healthy. Follow the initialization and acceptance stages below. Changes to custom data do not rerun cloud-init automatically on an existing VM; upgrades require an explicit operator procedure or recreation after protecting state.

Local validation performed for this implementation: Bicep template and example-parameter compilation, compiled network/identity assertions, shell syntax, eight Python tests (including loopback TLS and scoped-session export), and local documentation links. The example parameters were correctly rejected by the deployment guard because they contain placeholders. No ARM validate/what-if, cloud-init execution, live Agent Vault container, or Azure acceptance run has been performed. Local Docker integration was unavailable because the Docker daemon was not running.

## Gateway initialization and session handoff

In the Azure portal, select the gateway VM, then **Connect → Bastion**. Verify the selected resource is the deployed **Developer** SKU; do not accept a one-click upgrade to a paid tier. Authenticate as `gatehouse` (or your configured username) using the matching SSH private key through the portal's supported key authentication option. SSH runs privately from the Bastion service to the VM; no internet SSH rule exists.

1. Run `sudo cloud-init status --wait`. Inspect failures locally; cloud-init contains setup output, not intentionally supplied upstream credentials.
2. Check `sudo systemctl status agentgatehouse-vault agentgatehouse-transport`.
3. Register the first owner and log in with the CLI inside the gateway container. Password prompts are hidden. The first registration becomes owner; management is loopback-only, so complete this before sharing gateway operator access.

```bash
sudo docker exec -it agentgatehouse-vault agent-vault auth register --address http://127.0.0.1:14321
sudo docker exec -it agentgatehouse-vault agent-vault auth login --address http://127.0.0.1:14321
sudo docker exec -it agentgatehouse-vault agent-vault vault create project
sudo python3 /opt/agentgatehouse/admin.py web-policy project deny
```

For initial testing, add an explicitly allowed public destination:

```bash
sudo docker exec -it agentgatehouse-vault agent-vault vault service add \
  --vault project --name public-example --host example.com --auth-type passthrough
```

Set the unmatched-host policy deliberately. For initial canary tests use `deny` and explicit passthrough services. To allow broad research and package downloads later:

```bash
sudo python3 /opt/agentgatehouse/admin.py web-policy project passthrough
```

This enables forwarding of unmatched hosts; it does **not** implement a blacklist. Inject credentials only into narrowly scoped service destinations. For a model API, for example, enter the real key at the helper's hidden prompt, then configure the header rule:

```bash
sudo python3 /opt/agentgatehouse/admin.py credential project ANTHROPIC_KEY
sudo docker exec -it agentgatehouse-vault agent-vault vault service add \
  --vault project --name anthropic-api --host api.anthropic.com \
  --auth-type api-key --api-key-key ANTHROPIC_KEY --api-key-header x-api-key
```

The owner login remains on the gateway. For a GitHub project API, store a repository-scoped token using the same helper and create a bearer rule scoped to `api.github.com/repos/OWNER/REPO/*`. Git-over-HTTPS uses different paths and authentication; configure and test it separately before treating A-03 as passed.

Now export a worker session through the browser terminal:

```bash
sudo python3 /opt/agentgatehouse/export-session.py project --clipboard --ttl 86400
```

This asks for a gateway owner/member login, creates a **proxy-role** scoped session, and exports only that session, its vault/expiry, and two public certificates. The owner password/token is never exported. Proxy-only agents cannot mint sessions themselves, so renewal is an operator action.

Copy the base64 bundle block including its BEGIN/END markers using Bastion's clipboard. It is wrapped into short lines to avoid terminal input-length limits. Disconnect from the gateway (Developer allows one VM connection at a time), open the worker VM's Bastion connection, and run:

```bash
sudo python3 /opt/agentgatehouse/worker.py --paste
```

Paste the bundle at the hidden prompt. This avoids placing it in shell history. The bundle is a capability despite containing no upstream secrets: do not put it into chat, tickets, or Git. Clear the clipboard and avoid terminal recording. The optional exporter file mode is for operators with a separate approved transfer mechanism; SCP is not required or supported by this Developer workflow.

Open a new worker login shell. Proxy settings and the Agent Vault public CA are now installed. The local relay wraps proxy bytes in verified TLS to `10.82.2.4:14443`; it does not implement HTTP parsing, policy or credential injection. Those remain Agent Vault's responsibility. The worker does not connect to the management API.

Renew by exporting a fresh session and running `worker.py --paste` again before expiry. Open new shells and restart running agents and Docker so they pick up the new capability. Expiry/rotation intentionally interrupts old sessions; no credential fallback is configured. Revoke unused sessions and operator login sessions using Agent Vault's gateway-local CLI. The helpers create operator login sessions, so include those in session hygiene.

## Install worker tools and configure an agent

For installation, permit the Ubuntu package mirrors, `nodejs.org`, `registry.npmjs.org` and any required package artifact destinations in the project vault, or deliberately enable broad unmatched-host forwarding. This does not require adding direct worker egress.

Choose reviewed exact package versions and verify the Node archive checksum using the upstream release checksums. Supply the checksum for the `linux-x64.tar.xz` archive:

```bash
sudo bash /opt/agentgatehouse/install-tools.sh NODE_VERSION NODE_SHA256 CODEX_VERSION CLAUDE_VERSION
```

Node must be at least 22.21.0 for the documented native proxy environment support. The script installs Git, Python, build tools, Docker and both coding-agent CLIs. Run `codex --version` and `claude --version` to check the selected binaries. npm installation of Claude Code is a compatibility choice; validate support for the exact selected version against its vendor documentation.

Store provider keys in Agent Vault and configure the appropriate service headers for the exact model endpoints. If a client needs a local API-key value to start, supply an obvious non-secret placeholder and have Agent Vault overwrite the authentication header. Do not perform an upstream OAuth/API-key login on the worker. Actual Codex/Claude requests and any remote tools need an integration smoke test before accepting the environment.

Docker daemon pulls use a systemd proxy environment file. Processes inside development containers also need proxy and CA configuration. For this single-project trust model, Linux `--network host` lets containers reach the loopback relay; mount only the worker's public CA bundle and supply the proxy environment. This grants worker-host networking, not a route around the external NSG. Do not use gateway mounts or credentials. Non-host-network devcontainers require a separately configured reachable relay address and remain unvalidated.

## Persistence, recovery and secrets

The gateway's dedicated data disk holds Agent Vault state, transport keys and its generated master password under `/var/lib/agentgatehouse`. The master password file is protected from worker access, but it resides on the same trusted disk as encrypted state; this is not protection against gateway-root compromise or theft of the whole disk. Protect backups accordingly.

The bootstrap formats only an empty, signature-free LUN 0 and refuses a recognized non-ext4 disk. Existing data is reused. The template detaches disks on VM deletion; resource-group deletion still destroys resources and is not a backup strategy. Back up gateway state consistently with the service stopped, and protect snapshots/exports through Azure access control. A full backup/restore automation is not included.

The worker OS disk holds workspaces and Docker data. Push or back up unfinished work before recreation. No per-agent CPU, RAM or disk quotas are added.

The gateway transport certificate expires after one year. Rotate it on the gateway, redistribute its public certificate to the worker, and restart transport services. Keep the private key on the gateway. Certificate mismatch or expiry must fail closed.

## Acceptance before real workloads

The network smoke test is preinstalled on the worker. Use a public test endpoint you control and have independently confirmed reachable from your workstation/gateway:

```bash
python3 /opt/agentgatehouse/worker-network.py --allowed-url https://YOUR_TEST_HOST/health --public-ip YOUR_TEST_IPV4
```

Repeat as worker root with proxy environment loaded. A timeout against a dead endpoint is not evidence of a firewall. The smoke test covers positive proxy use and selected blocked TCP connections. Separately verify:

- DNS/UDP probes to Azure and a controlled external collector do not arrive. Verify IPv6 has no usable bypass route; IPv6 is not provisioned by this template.
- An authenticated canary endpoint sees an injected synthetic credential while worker-visible response content and diagnostics do not expose it. Do not use an echo endpoint that reflects real credentials.
- Credential-bearing redirects and changed destinations cannot send the canary to another host.
- Stop `agentgatehouse-vault` on the gateway during an agreed test window. Both proxied and direct worker requests must fail; restart it afterward.
- Access outside repository/cloud scope fails; project logs can be queried with the chosen integration.
- From an independent internet host, verify that gateway public-IP ports 22, 14321, 14322 and 14443 reject connections. Verify Bastion still connects privately to both VMs.
- For OAuth, test refresh and revocation. Test parallel-agent work without exhausting the machine.

Record the tested image digest, tool versions, environment and results. Offline tests do not establish these live properties.

Azure platform communication has exceptions: WireServer VM-agent traffic is not ordinary NSG-filtered egress. The template explicitly denies Azure platform DNS and IMDS, but image provisioning and platform behavior must be verified live. If those restrictions break bootstrap, diagnose and document a narrow platform exception rather than adding general internet access.

Developer's target-VM SSH rule uses platform source `168.63.129.16/32`, rather than a dedicated Bastion subnet. This follows the Developer pattern in the [DevBox Image Builder implementation](https://github.com/dstamand-msft/DevBoxImageBuilder); verify actual connectivity in the selected region. Do not widen it to all internet/VNet traffic to work around a failure.

## Costs and shutdown

West Europe Linux pay-as-you-go USD estimates checked 2026-09-18 through the [Azure retail pricing API](https://prices.azure.com/api/retail/prices), using 730 hours/month:

| Component | Configuration | Monthly base estimate |
| --- | --- | ---: |
| Worker VM | D16s_v5, 16 vCPU / 64 GiB, $0.92/hour | $671.60 |
| Gateway VM | B2ms, 2 vCPU / 8 GiB, $0.096/hour | $70.08 |
| Bastion Developer | Browser only | $0 |
| Gateway Standard public IPv4 | $0.005/hour | $3.65 |
| Standard SSD LRS disks | Worker 256 GiB, gateway OS 64 GiB, gateway data 32 GiB | $26.40 |
| VNet, subnets, NSGs | No separate base charge | $0 |
| Total, always on | No NAT Gateway | **$771.73** |

With the worker allocated for 176 hours/month and the gateway always on: about **$262.05/month**. With both VMs allocated for 176 hours: about **$208.87/month**. These exclude disk transactions, bandwidth, backups, model-provider charges, tax, and negotiated pricing. B2ms is burstable; validate gateway throughput before large parallel workloads. Pricing and region availability may change.

Use Azure **deallocate**, not just guest shutdown, to stop VM compute billing. Persistent disks and the static public IP remain billable. No auto-stop scheduler or budget alert is provisioned. Start the gateway before worker operations that need the proxy; check session expiry after downtime.

No paid Bastion SKU or NAT Gateway is deployed. NAT was removed because the gateway's public IP plus inbound-deny NSG provides the required outbound connectivity.

## References

- [Bicep deployment permissions](https://learn.microsoft.com/en-us/azure/azure-resource-manager/templates/deploy-cli)
- [Azure NSG semantics](https://learn.microsoft.com/en-us/azure/virtual-network/network-security-groups-overview)
- [Bastion Developer features and regions](https://learn.microsoft.com/en-us/azure/bastion/bastion-sku-comparison)
- [Azure platform address exceptions](https://learn.microsoft.com/en-us/azure/virtual-network/what-is-ip-address-168-63-129-16)
- [Agent Vault installation](https://docs.agent-vault.dev/installation)
- [Agent Vault proxy roles](https://docs.agent-vault.dev/agents/overview)
- [Agent Vault session API implementation](https://github.com/Infisical/agent-vault/blob/main/sdks/sdk-typescript/src/resources/sessions.ts)
- [Agent Vault security and transport](https://docs.agent-vault.dev/learn/security)
- [Codex CLI](https://learn.chatgpt.com/docs/codex/cli)
- [Claude Code setup](https://code.claude.com/docs/en/setup)
