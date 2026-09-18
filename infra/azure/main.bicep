targetScope = 'resourceGroup'

@description('Short resource name prefix. Use lowercase letters, numbers and hyphens.')
@minLength(3)
@maxLength(20)
param namePrefix string = 'agentgatehouse'

param location string = resourceGroup().location
param adminUsername string = 'gatehouse'

@description('Operator SSH public key. Never supply a private key.')
param sshPublicKey string

@description('Immutable image reference: infisical/agent-vault@sha256:<digest>. Resolve and review a release before deployment.')
param agentVaultImage string

@description('Exact Ubuntu 24.04 LTS Gen2 image version available in the selected region; not latest.')
param ubuntuImageVersion string

param workerVmSize string = 'Standard_D16s_v5'
param gatewayVmSize string = 'Standard_B2ms'

var gatewayIp = '10.82.2.4'
var workerIp = '10.82.1.4'
// Developer uses shared platform infrastructure, not an AzureBastionSubnet.
// Verify this platform source in the chosen region during live acceptance.
var bastionSource = '168.63.129.16/32'
var tags = {
  project: 'AgentGatehouse'
  managedBy: 'Bicep'
}

resource workerNsg 'Microsoft.Network/networkSecurityGroups@2024-05-01' = {
  name: '${namePrefix}-worker-nsg'
  location: location
  tags: tags
  properties: {
    securityRules: [
      {
        name: 'AllowBastionSSH'
        properties: {
          priority: 100
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: bastionSource
          sourcePortRange: '*'
          destinationAddressPrefix: workerIp
          destinationPortRange: '22'
        }
      }
      {
        name: 'DenyOtherInbound'
        properties: {
          priority: 4000
          direction: 'Inbound'
          access: 'Deny'
          protocol: '*'
          sourceAddressPrefix: '*'
          sourcePortRange: '*'
          destinationAddressPrefix: '*'
          destinationPortRange: '*'
        }
      }
      {
        name: 'AllowGatewayTLSProxy'
        properties: {
          priority: 100
          direction: 'Outbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: '*'
          sourcePortRange: '*'
          destinationAddressPrefix: gatewayIp
          destinationPortRange: '14443'
        }
      }
      {
        name: 'DenyAzurePlatformDNS'
        properties: {
          priority: 110
          direction: 'Outbound'
          access: 'Deny'
          protocol: '*'
          sourceAddressPrefix: '*'
          sourcePortRange: '*'
          destinationAddressPrefix: 'AzurePlatformDNS'
          destinationPortRange: '*'
        }
      }
      {
        name: 'DenyAzureMetadata'
        properties: {
          priority: 120
          direction: 'Outbound'
          access: 'Deny'
          protocol: '*'
          sourceAddressPrefix: '*'
          sourcePortRange: '*'
          destinationAddressPrefix: 'AzurePlatformIMDS'
          destinationPortRange: '*'
        }
      }
      {
        name: 'DenyOtherOutbound'
        properties: {
          priority: 4000
          direction: 'Outbound'
          access: 'Deny'
          protocol: '*'
          sourceAddressPrefix: '*'
          sourcePortRange: '*'
          destinationAddressPrefix: '*'
          destinationPortRange: '*'
        }
      }
    ]
  }
}

resource gatewayNsg 'Microsoft.Network/networkSecurityGroups@2024-05-01' = {
  name: '${namePrefix}-gateway-nsg'
  location: location
  tags: tags
  properties: {
    securityRules: [
      {
        name: 'AllowBastionSSH'
        properties: {
          priority: 100
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: bastionSource
          sourcePortRange: '*'
          destinationAddressPrefix: gatewayIp
          destinationPortRange: '22'
        }
      }
      {
        name: 'AllowWorkerTLSProxy'
        properties: {
          priority: 110
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: workerIp
          sourcePortRange: '*'
          destinationAddressPrefix: gatewayIp
          destinationPortRange: '14443'
        }
      }
      {
        name: 'DenyOtherInbound'
        properties: {
          priority: 4000
          direction: 'Inbound'
          access: 'Deny'
          protocol: '*'
          sourceAddressPrefix: '*'
          sourcePortRange: '*'
          destinationAddressPrefix: '*'
          destinationPortRange: '*'
        }
      }
      {
        name: 'DenyVnetInitiatedConnections'
        properties: {
          priority: 100
          direction: 'Outbound'
          access: 'Deny'
          protocol: '*'
          sourceAddressPrefix: '*'
          sourcePortRange: '*'
          destinationAddressPrefix: 'VirtualNetwork'
          destinationPortRange: '*'
        }
      }
    ]
  }
}

resource gatewayPublicIp 'Microsoft.Network/publicIPAddresses@2024-05-01' = {
  name: '${namePrefix}-gateway-ip'
  location: location
  tags: tags
  sku: { name: 'Standard' }
  properties: { publicIPAllocationMethod: 'Static' }
}
resource vnet 'Microsoft.Network/virtualNetworks@2024-05-01' = {
  name: '${namePrefix}-vnet'
  location: location
  tags: tags
  properties: {
    addressSpace: { addressPrefixes: ['10.82.0.0/16'] }
    subnets: [
      {
        name: 'worker'
        properties: {
          addressPrefix: '10.82.1.0/24'
          defaultOutboundAccess: false
          networkSecurityGroup: { id: workerNsg.id }
        }
      }
      {
        name: 'gateway'
        properties: {
          addressPrefix: '10.82.2.0/24'
          defaultOutboundAccess: false
          networkSecurityGroup: { id: gatewayNsg.id }
        }
      }
    ]
  }
}

resource bastion 'Microsoft.Network/bastionHosts@2024-05-01' = {
  name: '${namePrefix}-bastion'
  location: location
  tags: tags
  sku: { name: 'Developer' }
  properties: {
    virtualNetwork: { id: vnet.id }
  }
}

resource gatewayDisk 'Microsoft.Compute/disks@2024-03-02' = {
  name: '${namePrefix}-gateway-data'
  location: location
  tags: tags
  sku: { name: 'StandardSSD_LRS' }
  properties: {
    creationData: { createOption: 'Empty' }
    diskSizeGB: 32
    publicNetworkAccess: 'Disabled'
    networkAccessPolicy: 'DenyAll'
  }
}

// JSON is valid YAML. Construct cloud-config as objects, not interpolated shell text.
var gatewayConfig = {
  package_update: false
  package_upgrade: false
  write_files: [
    {
      path: '/opt/agentgatehouse/gateway.sh'
      permissions: '0700'
      encoding: 'b64'
      content: base64(loadTextContent('../../bootstrap/gateway.sh'))
    }
    {
      path: '/opt/agentgatehouse/export-session.py'
      permissions: '0700'
      encoding: 'b64'
      content: base64(loadTextContent('../../bootstrap/export-session.py'))
    }
    {
      path: '/opt/agentgatehouse/admin.py'
      permissions: '0700'
      encoding: 'b64'
      content: base64(loadTextContent('../../bootstrap/admin.py'))
    }
  ]
  runcmd: [['bash', '/opt/agentgatehouse/gateway.sh', agentVaultImage]]
}
var workerConfig = {
  package_update: false
  package_upgrade: false
  write_files: [
    {
      path: '/opt/agentgatehouse/tls-relay.py'
      permissions: '0755'
      encoding: 'b64'
      content: base64(loadTextContent('../../bootstrap/tls-relay.py'))
    }
    {
      path: '/opt/agentgatehouse/worker.py'
      permissions: '0700'
      encoding: 'b64'
      content: base64(loadTextContent('../../bootstrap/worker.py'))
    }
    {
      path: '/opt/agentgatehouse/install-tools.sh'
      permissions: '0700'
      encoding: 'b64'
      content: base64(loadTextContent('../../bootstrap/install-tools.sh'))
    }
    {
      path: '/opt/agentgatehouse/worker-network.py'
      permissions: '0755'
      encoding: 'b64'
      content: base64(loadTextContent('../../tests/acceptance/worker-network.py'))
    }
  ]
}

module gateway 'modules/vm.bicep' = {
  name: 'gateway'
  params: {
    name: '${namePrefix}-gateway'
    location: location
    tags: tags
    subnetId: '${vnet.id}/subnets/gateway'
    privateIp: gatewayIp
    publicIpId: gatewayPublicIp.id
    vmSize: gatewayVmSize
    adminUsername: adminUsername
    sshPublicKey: sshPublicKey
    imageVersion: ubuntuImageVersion
    customData: base64('#cloud-config\n${string(gatewayConfig)}')
    dataDiskId: gatewayDisk.id
    osDiskGB: 64
  }
}
module worker 'modules/vm.bicep' = {
  name: 'worker'
  params: {
    name: '${namePrefix}-worker'
    location: location
    tags: tags
    subnetId: '${vnet.id}/subnets/worker'
    privateIp: workerIp
    vmSize: workerVmSize
    acceleratedNetworking: true
    adminUsername: adminUsername
    sshPublicKey: sshPublicKey
    imageVersion: ubuntuImageVersion
    customData: base64('#cloud-config\n${string(workerConfig)}')
    osDiskGB: 256
  }
}

output gatewayVmId string = gateway.outputs.vmId
output workerVmId string = worker.outputs.vmId
output bastionName string = bastion.name
output gatewayPrivateIp string = gatewayIp
output gatewayOutboundPublicIp string = gatewayPublicIp.properties.ipAddress
output workerPrivateIp string = workerIp
output proxyTlsPort int = 14443
