#!/usr/bin/env python3
"""Gateway-local administration without exposing a web UI or secrets in argv.

Register/login and most administration use Agent Vault's CLI in its container.
This helper handles hidden credential input and the unmatched-host policy.
"""
import argparse
import getpass
import json
import urllib.request
from urllib.parse import quote


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("credential", "web-policy"))
    parser.add_argument("vault")
    parser.add_argument("value", help="Credential key or policy (deny/passthrough)")
    args = parser.parse_args()
    email = input("Owner email: ").strip()
    password = getpass.getpass("Owner password: ")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def request(method, path, data, token=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        req = urllib.request.Request("http://127.0.0.1:14321" + path,
                                     data=json.dumps(data).encode(), headers=headers, method=method)
        with opener.open(req, timeout=30) as response:
            return json.load(response)

    try:
        auth = request("POST", "/v1/auth/login", {"email": email, "password": password, "device_label": "gatehouse-admin-helper"})
        token = auth["token"]
        if args.action == "credential":
            secret = getpass.getpass("Upstream credential value: ")
            request("POST", "/v1/credentials", {"vault": args.vault, "credentials": {args.value: secret}}, token)
        else:
            if args.value not in ("deny", "passthrough"):
                parser.error("Policy must be deny or passthrough")
            request("PATCH", "/v1/vaults/" + quote(args.vault, safe="") + "/settings",
                    {"unmatched_host_policy": args.value}, token)
    except (OSError, KeyError, ValueError):
        raise SystemExit("Administration failed; verify login, permissions and API compatibility. Response body withheld.")
    print("Updated successfully. No credential value was logged.")


if __name__ == "__main__":
    main()
