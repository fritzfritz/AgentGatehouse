#!/usr/bin/env bash
# Runs on the trusted gateway through cloud-init. Contains no upstream secrets.
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run as root' >&2; exit 1; }
image=${1:?Supply a digest-pinned Agent Vault image}
[[ $image =~ ^infisical/agent-vault@sha256:[a-f0-9]{64}$ ]] || {
  echo 'Agent Vault image must use infisical/agent-vault@sha256:<64 lowercase hex characters>' >&2; exit 1;
}
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y docker.io stunnel4 openssl python3 ca-certificates
systemctl enable --now docker

# Only initialize the dedicated Azure LUN, never an OS disk or an existing filesystem.
disk=/dev/disk/azure/scsi1/lun0
for attempt in $(seq 1 60); do [[ -b $disk ]] && break; sleep 2; done
[[ -b $disk ]] || { echo 'Dedicated data disk LUN 0 missing' >&2; exit 1; }
if ! blkid "$disk" >/dev/null 2>&1; then
  [[ -z $(wipefs --no-act --noheadings "$disk") ]] || { echo 'Unrecognized disk signature; refusing format' >&2; exit 1; }
  mkfs.ext4 -L gatehouse-data "$disk"
fi
[[ $(blkid -s TYPE -o value "$disk") == ext4 ]] || { echo 'Data disk must be ext4' >&2; exit 1; }
mkdir -p /var/lib/agentgatehouse
uuid=$(blkid -s UUID -o value "$disk")
if ! grep -q "^UUID=$uuid " /etc/fstab; then
  printf 'UUID=%s /var/lib/agentgatehouse ext4 defaults 0 2\n' "$uuid" >> /etc/fstab
fi
mountpoint -q /var/lib/agentgatehouse || mount /var/lib/agentgatehouse
install -d -m 0700 /var/lib/agentgatehouse/config
install -d -m 0700 -o 65532 -g 65532 /var/lib/agentgatehouse/vault
config=/var/lib/agentgatehouse/config
if [[ ! -f $config/master.env ]]; then
  (umask 077; printf 'AGENT_VAULT_MASTER_PASSWORD=%s\n' "$(openssl rand -hex 32)" > "$config/master.env")
fi
if [[ ! -f $config/transport.key ]]; then
  (umask 077; openssl req -x509 -newkey rsa:3072 -sha256 -nodes -days 365 \
    -subj '/CN=agentgatehouse-gateway' -addext 'subjectAltName=IP:10.82.2.4' \
    -keyout "$config/transport.key" -out "$config/transport.crt")
fi
printf '%s\n' "$image" > "$config/image"
docker pull "$image"
cat > /etc/systemd/system/agentgatehouse-vault.service <<EOF
[Unit]
Description=Agent Gatehouse credential broker
Requires=docker.service
After=docker.service network-online.target
RequiresMountsFor=/var/lib/agentgatehouse
[Service]
ExecStartPre=-/usr/bin/docker rm agentgatehouse-vault
ExecStart=/usr/bin/docker run --name agentgatehouse-vault --pull never --env-file $config/master.env -e AGENT_VAULT_ADDR=http://localhost:14321 -p 127.0.0.1:14321:14321 -p 127.0.0.1:14322:14322 --mount type=bind,source=/var/lib/agentgatehouse/vault,target=/data $image server --host 0.0.0.0 --port 14321 --mitm-port 14322
ExecStop=/usr/bin/docker stop -t 20 agentgatehouse-vault
Restart=on-failure
RestartSec=5
[Install]
WantedBy=multi-user.target
EOF
cat > /etc/agentgatehouse-stunnel.conf <<EOF
foreground = yes
pid =
sslVersionMin = TLSv1.2
[proxy]
accept = 10.82.2.4:14443
connect = 127.0.0.1:14322
cert = $config/transport.crt
key = $config/transport.key
EOF
cat > /etc/systemd/system/agentgatehouse-transport.service <<'EOF'
[Unit]
Description=TLS transport for Agent Vault proxy only
After=network-online.target agentgatehouse-vault.service
RequiresMountsFor=/var/lib/agentgatehouse
[Service]
ExecStart=/usr/bin/stunnel4 /etc/agentgatehouse-stunnel.conf
Restart=on-failure
RestartSec=5
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now agentgatehouse-vault agentgatehouse-transport
echo 'Gateway services started. Complete owner setup in the Bastion Developer browser terminal before exporting a session.'
