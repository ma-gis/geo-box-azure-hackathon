// GeoBox Infrastructure as Code (Azure Bicep)
// Deploys all Azure resources for the hackathon project

@description('Primary location for all resources')
param location string = resourceGroup().location

@description('Environment name (dev, staging, prod)')
@allowed([
  'dev'
  'staging'
  'prod'
])
param environment string = 'dev'

@description('Unique suffix for resource names')
param resourceSuffix string = uniqueString(resourceGroup().id)

@description('Azure OpenAI API Key')
@secure()
param azureOpenAIApiKey string

@description('Azure OpenAI Endpoint')
param azureOpenAIEndpoint string

@description('Azure OpenAI Deployment Name')
param azureOpenAIDeploymentName string = 'gpt-4o'

@description('Shared API key for MCP Gateway middleware (optional — leave empty to disable auth)')
@secure()
param mcpApiKey string = ''

@description('Box webhook HMAC signing key for signature validation (optional)')
@secure()
param boxWebhookSignatureKey string = ''

@description('Box JWT config as a JSON string (injected as Container Apps secret)')
@secure()
param boxConfigJson string = ''

// Variables
var containerRegistryName = 'geobox${resourceSuffix}'
var storageAccountName = 'geoboxst${resourceSuffix}'  // shared file volume
var containerAppEnvName = 'geobox-env-${environment}'
var containerAppName = 'geobox-app-${environment}'
var mcpExifToolAppName = 'geobox-mcp-exiftool-${environment}'
var mcpGeoAppName = 'geobox-mcp-geo-${environment}'
var logAnalyticsName = 'geobox-logs-${environment}'

// Storage Account + File Share — shared /tmp/geobox volume between orchestrator and MCP containers
resource storageAccount 'Microsoft.Storage/storageAccounts@2022-09-01' = {
  name: storageAccountName
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
  }
}

resource fileService 'Microsoft.Storage/storageAccounts/fileServices@2022-09-01' = {
  parent: storageAccount
  name: 'default'
}

resource fileShare 'Microsoft.Storage/storageAccounts/fileServices/shares@2022-09-01' = {
  parent: fileService
  name: 'geobox-tmp'
  properties: {
    shareQuota: 5  // 5 GB — more than enough for temp image files
  }
}

// Log Analytics Workspace (required for Container Apps)
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// Azure Container Registry
resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-01-01-preview' = {
  name: containerRegistryName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: true
  }
}

// Container Apps Environment
resource containerAppEnv 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: containerAppEnvName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

// Register the file share with the Container Apps Environment
resource envStorage 'Microsoft.App/managedEnvironments/storages@2023-05-01' = {
  name: 'geobox-shared'
  parent: containerAppEnv
  properties: {
    azureFile: {
      accountName: storageAccount.name
      accountKey: storageAccount.listKeys().keys[0].value
      shareName: 'geobox-tmp'
      accessMode: 'ReadWrite'
    }
  }
  dependsOn: [fileShare]
}

// Container App
resource containerApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: containerAppName
  location: location
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8080
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        {
          server: containerRegistry.properties.loginServer
          username: containerRegistry.listCredentials().username
          passwordSecretRef: 'registry-password'
        }
      ]
      secrets: [
        {
          name: 'registry-password'
          value: containerRegistry.listCredentials().passwords[0].value
        }
        {
          name: 'azure-openai-api-key'
          value: azureOpenAIApiKey
        }
        {
          name: 'mcp-api-key'
          value: mcpApiKey
        }
        {
          name: 'box-webhook-signature-key'
          value: boxWebhookSignatureKey
        }
        {
          name: 'box-config-json'
          value: boxConfigJson
        }
      ]
    }
    template: {
      volumes: [
        {
          name: 'geobox-tmp'
          storageType: 'AzureFile'
          storageName: 'geobox-shared'
        }
      ]
      containers: [
        {
          name: 'geobox'
          image: '${containerRegistry.properties.loginServer}/geobox:latest'
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            {
              name: 'AZURE_OPENAI_API_KEY'
              secretRef: 'azure-openai-api-key'
            }
            {
              name: 'AZURE_OPENAI_ENDPOINT'
              value: azureOpenAIEndpoint
            }
            {
              name: 'AZURE_OPENAI_DEPLOYMENT_NAME'
              value: azureOpenAIDeploymentName
            }
            {
              name: 'LOG_LEVEL'
              value: 'INFO'
            }
            {
              name: 'MCP_EXIFTOOL_URL'
              // Internal Container Apps ingress is on port 80; /sse is the MCP StreamableHTTP endpoint
              value: 'http://${mcpExifToolAppName}/sse'
            }
            {
              name: 'GEO_SERVER_URL'
              // Internal Container Apps ingress is on port 80 (plain REST API)
              value: 'http://${mcpGeoAppName}'
            }
            {
              name: 'MCP_API_KEY'
              secretRef: 'mcp-api-key'
            }
            {
              name: 'BOX_WEBHOOK_SIGNATURE_KEY'
              secretRef: 'box-webhook-signature-key'
            }
            {
              name: 'BOX_CONFIG_JSON'
              secretRef: 'box-config-json'
            }
          ]
          volumeMounts: [
            {
              volumeName: 'geobox-tmp'
              mountPath: '/tmp/geobox'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 10
        rules: [
          {
            name: 'http-scaling'
            http: {
              metadata: {
                concurrentRequests: '10'
              }
            }
          }
        ]
      }
    }
  }
  dependsOn: [envStorage]
}

// ExifTool MCP Server Container App
resource mcpExifToolApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: mcpExifToolAppName
  location: location
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      ingress: {
        external: false  // Internal only - called by orchestrator
        targetPort: 8081
        transport: 'http'
      }
      registries: [
        {
          server: containerRegistry.properties.loginServer
          username: containerRegistry.listCredentials().username
          passwordSecretRef: 'registry-password'
        }
      ]
      secrets: [
        {
          name: 'registry-password'
          value: containerRegistry.listCredentials().passwords[0].value
        }
        {
          name: 'mcp-api-key'
          value: mcpApiKey
        }
      ]
    }
    template: {
      volumes: [
        {
          name: 'geobox-tmp'
          storageType: 'AzureFile'
          storageName: 'geobox-shared'
        }
      ]
      containers: [
        {
          name: 'exiftool-mcp'
          image: '${containerRegistry.properties.loginServer}/exiftool-mcp-server:latest'
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            {
              name: 'LOG_LEVEL'
              value: 'INFO'
            }
            {
              name: 'MCP_API_KEY'
              secretRef: 'mcp-api-key'
            }
          ]
          volumeMounts: [
            {
              volumeName: 'geobox-tmp'
              mountPath: '/tmp/geobox'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0  // Scale to zero for cost savings
        maxReplicas: 5
        rules: [
          {
            name: 'http-scaling'
            http: {
              metadata: {
                concurrentRequests: '10'
              }
            }
          }
        ]
      }
    }
  }
  dependsOn: [envStorage]
}

// Geospatial MCP Server Container App
resource mcpGeoApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: mcpGeoAppName
  location: location
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      ingress: {
        external: false  // Internal only - called by orchestrator
        targetPort: 8082
        transport: 'http'
      }
      registries: [
        {
          server: containerRegistry.properties.loginServer
          username: containerRegistry.listCredentials().username
          passwordSecretRef: 'registry-password'
        }
      ]
      secrets: [
        {
          name: 'registry-password'
          value: containerRegistry.listCredentials().passwords[0].value
        }
        {
          name: 'mcp-api-key'
          value: mcpApiKey
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'geo-mcp'
          image: '${containerRegistry.properties.loginServer}/geo-mcp-server:latest'
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            {
              name: 'LOG_LEVEL'
              value: 'INFO'
            }
            {
              name: 'MCP_API_KEY'
              secretRef: 'mcp-api-key'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0  // Scale to zero for cost savings
        maxReplicas: 5
        rules: [
          {
            name: 'http-scaling'
            http: {
              metadata: {
                concurrentRequests: '10'
              }
            }
          }
        ]
      }
    }
  }
}

// Outputs
output containerRegistryLoginServer string = containerRegistry.properties.loginServer
output containerAppFqdn string = containerApp.properties.configuration.ingress.fqdn
output containerAppUrl string = 'https://${containerApp.properties.configuration.ingress.fqdn}'
output mcpExifToolAppFqdn string = mcpExifToolApp.properties.configuration.ingress.fqdn
output mcpExifToolAppUrl string = 'http://${mcpExifToolApp.properties.configuration.ingress.fqdn}'
output mcpGeoAppFqdn string = mcpGeoApp.properties.configuration.ingress.fqdn
output mcpGeoAppUrl string = 'http://${mcpGeoApp.properties.configuration.ingress.fqdn}'
output logAnalyticsWorkspaceId string = logAnalytics.id
