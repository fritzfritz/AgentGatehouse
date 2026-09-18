#!/usr/bin/env python3
"""Check critical network invariants in compiled ARM, without deploying."""
import json
import sys

with open(sys.argv[1]) as source:
    template = json.load(source)
resources = template["resources"]


def named(kind, suffix):
    return next(r for r in resources if r["type"] == kind and suffix in r["name"])


worker_nsg = named("Microsoft.Network/networkSecurityGroups", "worker-nsg")
rules = {r["name"]: r["properties"] for r in worker_nsg["properties"]["securityRules"]}
assert rules["AllowGatewayTLSProxy"]["destinationPortRange"] == "14443"
assert rules["DenyOtherOutbound"]["access"] == "Deny"
assert rules["DenyOtherOutbound"]["priority"] < 65000
assert rules["DenyOtherInbound"]["access"] == "Deny"
assert rules["AllowBastionSSH"]["sourceAddressPrefix"] == "[variables('bastionSource')]"
assert template["variables"]["bastionSource"] == "168.63.129.16/32"
assert rules["DenyAzurePlatformDNS"]["destinationAddressPrefix"] == "AzurePlatformDNS"
assert rules["DenyAzureMetadata"]["destinationAddressPrefix"] == "AzurePlatformIMDS"
outbound_allows = [r for r in rules.values() if r["direction"] == "Outbound" and r["access"] == "Allow"]
assert len(outbound_allows) == 1
vnet = next(r for r in resources if r["type"] == "Microsoft.Network/virtualNetworks")
subnets = {s["name"]: s["properties"] for s in vnet["properties"]["subnets"]}
assert subnets["worker"]["defaultOutboundAccess"] is False
assert "natGateway" not in subnets["worker"]
assert "natGateway" not in subnets["gateway"]
assert not any(r["type"] == "Microsoft.Network/natGateways" for r in resources)
assert "AzureBastionSubnet" not in subnets
bastion = next(r for r in resources if r["type"] == "Microsoft.Network/bastionHosts")
assert bastion["sku"]["name"] == "Developer"
assert "virtualNetwork" in bastion["properties"]
assert "enableTunneling" not in bastion["properties"]
assert "ipConfigurations" not in bastion["properties"]
public_ips = [r for r in resources if r["type"] == "Microsoft.Network/publicIPAddresses"]
assert len(public_ips) == 1 and "gateway-ip" in public_ips[0]["name"]
gateway_nsg = named("Microsoft.Network/networkSecurityGroups", "gateway-nsg")
gateway_rules = {r["name"]: r["properties"] for r in gateway_nsg["properties"]["securityRules"]}
assert gateway_rules["DenyOtherInbound"]["access"] == "Deny"
assert gateway_rules["DenyOtherInbound"]["priority"] < 65000
assert {r["destinationPortRange"] for r in gateway_rules.values() if r["direction"] == "Inbound" and r["access"] == "Allow"} == {"22", "14443"}
assert gateway_rules["AllowWorkerTLSProxy"]["sourceAddressPrefix"] == "[variables('workerIp')]"
assert gateway_rules["AllowBastionSSH"]["sourceAddressPrefix"] == "[variables('bastionSource')]"
assert gateway_rules["DenyVnetInitiatedConnections"]["access"] == "Deny"
for resource in resources:
    if resource["type"] == "Microsoft.Resources/deployments":
        params = resource["properties"]["parameters"]
        if resource["name"] == "worker":
            assert "publicIpId" not in params
        elif resource["name"] == "gateway":
            assert "publicIpId" in params
        for nested in resource["properties"]["template"]["resources"]:
            if nested["type"] == "Microsoft.Compute/virtualMachines":
                assert "identity" not in nested
            if nested["type"] == "Microsoft.Network/networkInterfaces":
                assert nested["properties"]["enableIPForwarding"] is False
                assert nested["properties"]["ipConfigurations"][0]["properties"]["publicIPAddress"].startswith("[if(empty(parameters('publicIpId'))")
print("Compiled ARM network/identity invariants passed (not live Azure verification).")
