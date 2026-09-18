#!/usr/bin/env python3
"""Reject example placeholders and unpinned deployment inputs before ARM calls."""
import json
import re
import sys


def validate(document):
    params = {key: value["value"] for key, value in document["parameters"].items()}
    if "REPLACE" in json.dumps(params):
        raise ValueError("Replace all example parameter values")
    if not re.fullmatch(r"infisical/agent-vault@sha256:[a-f0-9]{64}", params.get("agentVaultImage", "")):
        raise ValueError("Agent Vault image must be pinned by digest")
    if not re.fullmatch(r"\d+\.\d+\.\d+", params.get("ubuntuImageVersion", "")):
        raise ValueError("Supply an exact Ubuntu image version, not latest")
    if not re.fullmatch(r"[a-z][a-z0-9-]{2,19}", params.get("namePrefix", "agentgatehouse")):
        raise ValueError("Prefix must be 3-20 lowercase letters, numbers or hyphens, starting with a letter")
    key = params.get("sshPublicKey", "")
    if not re.match(r"^(ssh-ed25519|ssh-rsa) [A-Za-z0-9+/=]+(?: |$)", key) or "PRIVATE" in key or "\n" in key:
        raise ValueError("Supply a single operator SSH public key")


if __name__ == "__main__":
    try:
        with open(sys.argv[1]) as source:
            validate(json.load(source))
    except (ValueError, KeyError, OSError) as error:
        raise SystemExit(str(error))
