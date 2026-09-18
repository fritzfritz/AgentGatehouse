param name string
param location string
param tags object
param subnetId string
param privateIp string
param vmSize string
param adminUsername string
param sshPublicKey string
param imageVersion string
param customData string
param osDiskGB int
param dataDiskId string = ''
param publicIpId string = ''
param acceleratedNetworking bool = false

resource nic 'Microsoft.Network/networkInterfaces@2024-05-01' = {
  name: '${name}-nic'
  location: location
  tags: tags
  properties: {
    enableIPForwarding: false
    enableAcceleratedNetworking: acceleratedNetworking
    ipConfigurations: [{
      name: 'private'
      properties: {
        privateIPAllocationMethod: 'Static'
        privateIPAddress: privateIp
        privateIPAddressVersion: 'IPv4'
        subnet: { id: subnetId }
        publicIPAddress: empty(publicIpId) ? null : { id: publicIpId }
      }
    }]
  }
}

resource vm 'Microsoft.Compute/virtualMachines@2024-11-01' = {
  name: name
  location: location
  tags: tags
  // Intentionally no managed identity. Only the gateway receives a public IP.
  properties: {
    hardwareProfile: { vmSize: vmSize }
    osProfile: {
      computerName: name
      adminUsername: adminUsername
      customData: customData
      linuxConfiguration: {
        disablePasswordAuthentication: true
        provisionVMAgent: true
        ssh: {
          publicKeys: [{ path: '/home/${adminUsername}/.ssh/authorized_keys', keyData: sshPublicKey }]
        }
      }
    }
    storageProfile: {
      imageReference: {
        publisher: 'Canonical'
        offer: 'ubuntu-24_04-lts'
        sku: 'server'
        version: imageVersion
      }
      osDisk: {
        createOption: 'FromImage'
        deleteOption: 'Detach'
        diskSizeGB: osDiskGB
        managedDisk: { storageAccountType: 'StandardSSD_LRS' }
      }
      dataDisks: empty(dataDiskId) ? [] : [{
        lun: 0
        createOption: 'Attach'
        deleteOption: 'Detach'
        managedDisk: { id: dataDiskId }
      }]
    }
    networkProfile: {
      networkInterfaces: [{ id: nic.id, properties: { deleteOption: 'Detach' } }]
    }
    diagnosticsProfile: { bootDiagnostics: { enabled: true } }
  }
}
output vmId string = vm.id
