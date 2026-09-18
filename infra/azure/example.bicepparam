using './main.bicep'

// Copy to a gitignored *.local.bicepparam file. Replace every REPLACE value.
param namePrefix = 'agentgatehouse'
param location = 'westeurope'
param adminUsername = 'gatehouse'
param sshPublicKey = 'REPLACE_WITH_OPERATOR_SSH_PUBLIC_KEY'
param ubuntuImageVersion = 'REPLACE_WITH_EXACT_REGIONAL_UBUNTU_IMAGE_VERSION'
param agentVaultImage = 'infisical/agent-vault@sha256:REPLACE_WITH_REVIEWED_DIGEST'
param workerVmSize = 'Standard_D16s_v5'
param gatewayVmSize = 'Standard_B2ms'
