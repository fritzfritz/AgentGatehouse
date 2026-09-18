#!/usr/bin/env python3
"""Run on the gateway. Export only a proxy session and public certificates."""
import argparse
import base64
import getpass
import json
import os
import textwrap
from pathlib import Path
import urllib.error
import urllib.request


def export(vault, email, password, ttl):
    # Loopback only; do not inherit an operator's proxy configuration.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(
        "http://127.0.0.1:14321/v1/auth/login",
        data=json.dumps({"email": email, "password": password, "device_label": "gatehouse-session-export"}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with opener.open(request, timeout=30) as response:
        operator_session = json.load(response)
    headers = {"Authorization": f'Bearer {operator_session["token"]}', "Content-Type": "application/json"}
    request = urllib.request.Request(
        "http://127.0.0.1:14321/v1/sessions",
        data=json.dumps({"vault": vault, "vault_role": "proxy", "ttl_seconds": ttl}).encode(), headers=headers,
    )
    with opener.open(request, timeout=30) as response:
        session = json.load(response)
    request = urllib.request.Request("http://127.0.0.1:14321/v1/mitm/ca.pem", headers=headers)
    with opener.open(request, timeout=30) as response:
        ca = response.read().decode()
    return {
        "token": session["token"], "vault": vault, "expires_at": session["expires_at"],
        "ca_certificate": ca,
        "transport_certificate": Path("/var/lib/agentgatehouse/config/transport.crt").read_text(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vault")
    parser.add_argument("output", type=Path, nargs="?")
    parser.add_argument("--clipboard", action="store_true", help="Print a base64 session bundle for transfer through the Bastion clipboard")
    parser.add_argument("--ttl", type=int, default=86400)
    args = parser.parse_args()
    if bool(args.output) == args.clipboard:
        parser.error("Choose an output file or --clipboard")
    if not 300 <= args.ttl <= 604800:
        parser.error("TTL must be between 300 and 604800 seconds")
    email = input("Owner/member email (gateway only): ").strip()
    password = getpass.getpass("Owner/member password (gateway only): ")
    try:
        bundle = export(args.vault, email, password, args.ttl)
        # Exclusive creation avoids accidentally replacing an existing capability file.
        if args.clipboard:
            print("Copy only the bundle lines below. They contain a scoped capability, not upstream credentials:")
            print("BEGIN GATEHOUSE BUNDLE")
            print("\n".join(textwrap.wrap(base64.b64encode(json.dumps(bundle).encode()).decode(), 1000)))
            print("END GATEHOUSE BUNDLE")
        else:
            fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as output:
                json.dump(bundle, output)
    except (OSError, KeyError, ValueError):
        raise SystemExit("Session export failed; check Agent Vault version, role and service health. No response body was logged.")
    print("Scoped session expires at", bundle["expires_at"])


if __name__ == "__main__":
    main()
