#!/usr/bin/env python3
"""Run on the worker after sourcing /etc/profile.d/agentgatehouse.sh.

Use an operator-controlled, independently verified reachable public endpoint.
This is a connectivity smoke test, not proof of every accepted security property.
"""
import argparse
import ipaddress
import socket
import subprocess
import sys


def blocked(address, port):
    try:
        with socket.create_connection((address, port), timeout=4):
            return False
    except OSError:
        return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allowed-url", required=True)
    parser.add_argument("--public-ip", required=True)
    parser.add_argument("--public-port", type=int, default=443)
    args = parser.parse_args()
    if not ipaddress.ip_address(args.public_ip).is_global:
        parser.error("Use a reachable public test endpoint's IP")
    checks = {
        "direct public TCP blocked": blocked(args.public_ip, args.public_port),
        "gateway management blocked": blocked("10.82.2.4", 14321),
        "gateway unencrypted proxy blocked": blocked("10.82.2.4", 14322),
        "gateway SSH blocked": blocked("10.82.2.4", 22),
        "metadata HTTP blocked": blocked("169.254.169.254", 80),
        "Azure DNS TCP blocked": blocked("168.63.129.16", 53),
        "external DNS TCP blocked": blocked(args.public_ip, 53),
    }
    # Do not expose curl diagnostics (which can include proxy credentials) or bodies.
    proxied = subprocess.run(
        ["curl", "--fail", "--silent", "--max-time", "20", "--output", "/dev/null", args.allowed_url],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    checks["allowed URL works via configured proxy"] = proxied.returncode == 0
    for name, passed in checks.items():
        print(f'{"PASS" if passed else "FAIL"}: {name}')
    print("UDP/DNS exfiltration, redirects, IPv6, credential reflection and gateway-outage tests still require the deployment runbook.")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
