#!/usr/bin/env python3
"""Install/renew an operator-exported proxy session on the worker, as root."""
import argparse
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shlex
import ssl
import subprocess
import sys
import termios
from urllib.parse import quote


def proxy_environment(bundle):
    expiry = datetime.fromisoformat(bundle["expires_at"].replace("Z", "+00:00"))
    if expiry <= datetime.now(timezone.utc):
        raise ValueError("Session has expired")
    for key in ("ca_certificate", "transport_certificate"):
        ssl.create_default_context(cadata=bundle[key])
    for key in ("token", "vault"):
        if not isinstance(bundle[key], str) or not bundle[key]:
            raise ValueError("Missing session identity")
    proxy = f'http://{quote(bundle["token"], safe="")}:{quote(bundle["vault"], safe="")}@127.0.0.1:14322'
    env = {key: proxy for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy")}
    env.update(NO_PROXY="localhost,127.0.0.1,::1", no_proxy="localhost,127.0.0.1,::1", NODE_USE_ENV_PROXY="1")
    for key in ("SSL_CERT_FILE", "NODE_EXTRA_CA_CERTS", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE", "GIT_SSL_CAINFO", "DENO_CERT"):
        env[key] = "/etc/ssl/certs/ca-certificates.crt"
    return env


def write(path, content, mode=0o644):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    target.chmod(mode)


def read_bundle(stream):
    lines = []
    total = 0
    for raw in stream:
        line = raw.strip()
        if line == "BEGIN GATEHOUSE BUNDLE":
            continue
        if not line or line == "END GATEHOUSE BUNDLE":
            break
        total += len(line)
        if total > 65536:
            raise ValueError("Bundle is unexpectedly large")
        lines.append(line)
    return json.loads(base64.b64decode("".join(lines), validate=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, nargs="?")
    parser.add_argument("--paste", action="store_true", help="Read base64 bundle at a hidden terminal prompt")
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error("Run as root")
    if bool(args.bundle) == args.paste:
        parser.error("Choose a bundle file or --paste")
    if args.paste:
        print("Paste bundle lines including BEGIN/END markers, or finish with an empty line. Input is hidden.")
        if not sys.stdin.isatty():
            parser.error("--paste requires an interactive terminal")
        fd = sys.stdin.fileno()
        previous = termios.tcgetattr(fd)
        hidden = termios.tcgetattr(fd)
        hidden[3] &= ~termios.ECHO
        try:
            # Change terminal mode once, without flushing a multi-line paste.
            termios.tcsetattr(fd, termios.TCSANOW, hidden)
            bundle = read_bundle(sys.stdin)
        finally:
            termios.tcsetattr(fd, termios.TCSANOW, previous)
            print()
    else:
        bundle = json.loads(args.bundle.read_text())
    env = proxy_environment(bundle)
    write("/usr/local/share/ca-certificates/agentgatehouse.crt", bundle["ca_certificate"])
    write("/etc/agentgatehouse/transport.crt", bundle["transport_certificate"])
    subprocess.run(["update-ca-certificates"], check=True)
    write("/etc/profile.d/agentgatehouse.sh", "\n".join(f"export {k}={shlex.quote(v)}" for k, v in env.items()) + "\n")
    write("/etc/agentgatehouse/proxy.env", "\n".join(f"{k}={v}" for k, v in env.items()) + "\n")
    write("/etc/agentgatehouse/session-expiry", bundle["expires_at"] + "\n")
    # Session capabilities are deliberately visible to this project's worker users.
    # No upstream credentials or gateway administration capabilities belong here.
    write("/etc/apt/apt.conf.d/80agentgatehouse", f'Acquire::http::Proxy "{env["HTTP_PROXY"]}";\nAcquire::https::Proxy "{env["HTTPS_PROXY"]}";\n')
    write("/etc/systemd/system/docker.service.d/proxy.conf", "[Service]\nEnvironmentFile=/etc/agentgatehouse/proxy.env\n")
    write("/etc/systemd/system/agentgatehouse-relay.service", """[Unit]
Description=Verified TLS transport to Agent Vault
After=network-online.target
[Service]
User=nobody
ExecStart=/usr/bin/python3 /opt/agentgatehouse/tls-relay.py
Restart=on-failure
RestartSec=3
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
[Install]
WantedBy=multi-user.target
""")
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "enable", "--now", "agentgatehouse-relay"], check=True)
    subprocess.run(["systemctl", "restart", "agentgatehouse-relay"], check=True)
    print("Proxy session installed. Open a new login shell. If Docker is running, restart it to load renewed proxy settings.")


if __name__ == "__main__":
    main()
